"""Installed v0.5 48 manifest compartments, 12 commercial sleeves, 3 voids."""
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells,
    initialize_nominal_atmosphere, state)
from world.ship_world import (
    build_canonical_ship, find_ship_space, find_world_entity)
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.models import CanonicalShipState
from world.ship_unclassified_spaces import (
    SECTORS, FREIGHT_ROUTES, PORTALS, VOIDS)
from world.continuous_ship_physics import (
    PhysicsError, _clock, arm_continuous_physics,
    commission_g19_electrical, commission_g19_water,
    commission_g19_repairs, commission_g19_eva,
    commission_g19_crew_physiology,
    commission_g19_unclassified_spaces, survey_g19_cargo_sector,
    inspect_g19_portal_sleeve, witness_g19_cargo_sector_leak,
    commission_commercial_port, survey_cargo_lot,
    survey_g19_water_material,
    crew_physical_action, local_physics_readout,
    tick_continuous_physics)


class OriginalCargoAndVoidClosure(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True,now_game_time=1000)
        crew=build_ship()
        self.worker=crew["watch"]
        self.worker.move_to(find_ship_space("ENG-CONTROL"),quiet=True)
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        commission_g19_crew_physiology(
            operator_approved=True,actor_dbrefs=[self.worker.dbref])
        self.assertTrue(commission_g19_unclassified_spaces(
            operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_unclassified_spaces(
            operator_approved=True)["commissioned"])
        self.counter=300
        self.now=1000

    def rid(self):
        self.counter+=1
        return f"{self.counter:032x}"

    def at(self,room):
        self.assertTrue(self.worker.move_to(find_ship_space(room),quiet=True))

    def op(self,action,target,value):
        return crew_physical_action(self.worker,self.rid(),action,target,value)

    def walk(self,link,direction):
        ex=find_world_entity("access:"+link+":"+direction)
        self.assertIsNotNone(ex,link)
        return traverse_canonical_exit(
            self.worker,ex,ex.destination,request_id=self.rid())

    def tick(self,seconds):
        while seconds:
            dt=min(seconds,60)
            seconds-=dt
            self.now+=dt
            tick_continuous_physics(now_game_time=self.now)

    def survey_drum(self):
        survey_cargo_lot(operator_approved=True,operation="verify",drum="DR-01")
        for sector in SECTORS[:8]:
            survey_g19_cargo_sector(
                operator_approved=True,sector=sector,free_volume_m3=50,
                pressure_pa=101000,temperature_k=293.15,
                oxygen_mass_fraction=.232,co2_mass_fraction=.0004,
                smoke_mass_fraction=0,cargo_class="empty",lot_ids=[])

    def suit(self):
        self.at("ENG-LOCKER")
        self.op("eva","INV-DC-CONSUMABLES","stage:0.75")
        self.at("EVA-FWD")
        self.op("eva","EVA-FWD","checkout")

    def enter(self,sector):
        self.at(sector[:5]+"-GALLERY")
        self.op("cargo_sector",sector,"secure")
        self.op("hatch","ACC-"+sector,"open")
        result=self.walk("ACC-"+sector,"forward")
        self.assertEqual(result["status"],"succeeded")
        self.op("hatch","ACC-"+sector,"closed")

    def leave(self,sector):
        self.op("hatch","ACC-"+sector,"open")
        self.assertEqual(
            self.walk("ACC-"+sector,"reverse")["status"],"succeeded")
        self.op("hatch","ACC-"+sector,"closed")
        self.op("cargo_sector",sector,"release")

    def test_all_sixty_three_original_space_identity_and_no_new_gas(self):
        d=_clock().details["unclassified_spaces"]
        self.assertEqual(tuple(map(len,(
            d["sectors"],d["portals"],d["voids"]))),(48,12,3))
        for sector in SECTORS:
            p=state("access","ACC-"+sector)
            f=state("access","ACC-"+sector[:5]+"-FREIGHT-"+sector[6:])
            self.assertEqual(p.reference["to"],sector)
            self.assertEqual(p.reference["kind"],"cargo_service_door")
            self.assertEqual(f.reference["to"],sector)
            self.assertEqual(f.reference["kind"],"freight_handling_route")
        for portal in PORTALS:
            self.assertEqual(
                state("access","ACC-"+portal).reference["to"],portal)
        self.assertEqual(len(VOIDS),3)
        self.assertTrue(all(row["gas"] is None for row in d["sectors"].values()))

    def test_manifest_evidenced_real_sector_passage_and_duplicate_refusal(self):
        room="DR-01-SEC-01"
        self.at("DR-01-GALLERY")
        with self.assertRaises(PhysicsError):
            self.op("hatch","ACC-"+room,"open")
        with self.assertRaises(CrewTransitError):
            self.walk("ACC-"+room,"forward")
        self.survey_drum()
        self.enter(room)
        reading=local_physics_readout(self.worker,"cargo_sectors")["sectors"][room]
        self.assertGreater(reading["gas_kg"],0)
        self.assertEqual(reading["class"],"empty")
        self.op("cargo_sector",room,"inspect")
        with self.assertRaises(CrewTransitError):
            self.walk("ACC-DR-01-FREIGHT-SEC-01","forward")
        self.leave(room)
        self.assertEqual(
            _clock().details["unclassified_spaces"]["sectors"][room]["entries"],1)

    def test_open_cargo_sector_hatch_exchanges_real_gallery_gas(self):
        sector="DR-01-SEC-02"
        self.survey_drum()
        self.at("DR-01-GALLERY")
        self.op("cargo_sector",sector,"secure")
        old=_clock().details["unclassified_spaces"]["sectors"][sector]["gas"]
        before_sector_mass=old["mass_kg"]
        before_gallery=state("pressure","PZ-DR-01-SVC").quantity
        before_lost=_clock().details["lost_to_space_kg"]
        self.op("hatch","ACC-"+sector,"open")
        self.tick(60)
        after=_clock().details
        sampled=after["unclassified_spaces"]["sectors"][sector]
        gallery=state("pressure","PZ-DR-01-SVC").quantity
        self.assertAlmostEqual(
            (sampled["gas"]["mass_kg"]-before_sector_mass)
            +(gallery-before_gallery),0,places=4)
        self.assertAlmostEqual(after["lost_to_space_kg"],before_lost,places=4)
        self.assertEqual(after["unclassified_spaces"]["version"],2)
        self.assertAlmostEqual(sampled["gallery_net_kg"],
                               sampled["gas"]["mass_kg"]-before_sector_mass,
                               places=5)
        self.op("hatch","ACC-"+sector,"closed")
        closed=sampled["gas"]["mass_kg"]
        self.tick(60)
        self.assertAlmostEqual(
            _clock().details["unclassified_spaces"]["sectors"][sector]["gas"]["mass_kg"],
            closed,places=5)
        self.op("cargo_sector",sector,"release")

    def test_open_hatch_major_shell_breach_gallery_loss_isolation_and_rotor_hold(self):
        sector="DR-01-SEC-05"
        self.survey_drum()
        self.at("DR-01-GALLERY")
        self.op("cargo_sector",sector,"secure")
        self.op("hatch","ACC-"+sector,"open")
        original_gallery=state("pressure","PZ-DR-01-SVC").quantity
        report=witness_g19_cargo_sector_leak(
            operator_approved=True,sector=sector,leak_kg_s=.8)
        self.assertEqual(report["rated_hatch_at_casualty"],"open")
        self.tick(60)
        active=_clock().details
        site=active["unclassified_spaces"]["sectors"][sector]
        self.assertGreater(site["lost_kg"],0)
        self.assertGreater(site["gallery_net_kg"],0)
        self.assertIn("ACC-"+sector,
            active["summary"]["cargo_open_breached_hatches"])
        self.assertLess(state("pressure","PZ-DR-01-SVC").quantity,
                        original_gallery)
        # Attempted restart must not bypass the real damaged cargo shell.
        self.at("DR-01-SERVICE-LOCK")
        with self.assertRaises(PhysicsError):
            self.op("rotor","DR-01","start")
        self.at("DR-01-GALLERY")
        self.op("hatch","ACC-"+sector,"closed")
        saved_net=site["gallery_net_kg"]
        saved_loss=site["lost_kg"]
        self.tick(60)
        sealed=_clock().details["unclassified_spaces"]["sectors"][sector]
        self.assertAlmostEqual(sealed["gallery_net_kg"],saved_net,places=6)
        self.assertGreater(sealed["lost_kg"],saved_loss)
        self.assertEqual(_clock().details["summary"][
            "cargo_open_breached_hatches"],[])
        with self.assertRaises(PhysicsError):
            self.op("hatch","ACC-"+sector,"open")
        self.op("cargo_sector",sector,"release")

    def test_broken_open_cargo_boundary_continues_physics_and_denies_entry(self):
        sector="DR-01-SEC-04"
        self.survey_drum()
        self.at("DR-01-GALLERY")
        self.op("cargo_sector",sector,"secure")
        self.op("hatch","ACC-"+sector,"open")
        # A subsequent physical hardware failure does not seal the actual
        # opening or make a new shell breach impossible to observe.
        door=state("access","ACC-"+sector,lock=True)
        door.condition="failed"
        door.revision+=1
        door.save(update_fields=["condition","revision"])
        report=witness_g19_cargo_sector_leak(
            operator_approved=True,sector=sector,leak_kg_s=.7)
        self.assertEqual(report["rated_hatch_at_casualty"],"open")
        self.tick(60)
        site=_clock().details["unclassified_spaces"]["sectors"][sector]
        self.assertGreater(site["lost_kg"],0)
        self.assertGreater(site["gallery_net_kg"],0)
        with self.assertRaises(PhysicsError):
            self.op("hatch","ACC-"+sector,"closed")
        with self.assertRaises(CrewTransitError):
            self.walk("ACC-"+sector,"forward")
        self.assertEqual(state("access","ACC-"+sector).setting,"open")

    def test_ambulatory_suited_owner_escapes_through_already_open_failed_sector(self):
        from world.ship_unclassified_runtime import (
            access_ready, open_hatch_casualty_egress)
        sector="DR-01-SEC-06"
        self.survey_drum()
        self.suit()
        self.enter(sector)
        self.op("hatch","ACC-"+sector,"open")
        witness_g19_cargo_sector_leak(
            operator_approved=True,sector=sector,leak_kg_s=.9)
        self.tick(60)
        world=_clock().details
        self.assertFalse(access_ready(
            self.worker,world,sector,from_inside=True,
            allow_small_leak=True,retreat_only=True))
        self.assertTrue(open_hatch_casualty_egress(
            self.worker,world,sector))
        evacuated=self.walk("ACC-"+sector,"reverse")
        self.assertEqual(evacuated["status"],"succeeded")
        self.assertEqual(self.worker.location.db.ox_space_id,
                         "DR-01-GALLERY")
        self.op("hatch","ACC-"+sector,"closed")
        self.op("cargo_sector",sector,"release")
        self.assertIsNone(_clock().details["unclassified_spaces"][
            "sectors"][sector]["permit"])
        self.assertGreater(_clock().details["unclassified_spaces"][
            "sectors"][sector]["lost_kg"],0)
        self.assertFalse(open_hatch_casualty_egress(
            self.worker,_clock().details,sector))

    def test_compound_breach_isolation_and_three_real_crew_casualty_carry(self):
        """Real cargo loss, manual isolation, and attended recovery to the hub.

        The patient has a separately recorded handling-impact injury; gas
        and the other two people's physical transport remain world-owned.
        This is three crew, never a synthetic forty-person voyage.
        """
        from world.continuous_ship_physics import (
            commission_g19_medical, commission_g19_rescue)
        crew=build_ship()
        leader=crew["environment"]
        patient=crew["cargo"]
        gallery=find_ship_space("DR-01-GALLERY")
        hub=find_ship_space("DR-01-HUB")
        for person in (self.worker, leader, patient):
            self.assertTrue(person.move_to(gallery,quiet=True))
        commission_g19_crew_physiology(
            actor_dbrefs=[leader.dbref,patient.dbref],
            operator_approved=True)
        commission_g19_medical(
            operator_approved=True,dressings=4,fluid_kg=2)
        commission_g19_rescue(operator_approved=True)
        self.survey_drum()
        sector="DR-01-SEC-03"
        self.op("cargo_sector",sector,"secure")
        self.op("hatch","ACC-"+sector,"open")
        witness_g19_cargo_sector_leak(
            operator_approved=True,sector=sector,leak_kg_s=.7)
        self.tick(60)
        vented=_clock().details["unclassified_spaces"][
            "sectors"][sector]["lost_kg"]
        self.assertGreater(vented,0)
        self.op("hatch","ACC-"+sector,"closed")
        self.op("cargo_sector",sector,"release")
        # Crew member injured by cargo handling during the casualty; this
        # fixture uses the existing physiological injury schema, not a
        # fabricated ship physics or medical intervention.
        hp=CanonicalShipState.objects.get(
            pk="crew_health:"+patient.dbref)
        injury=dict(hp.details)
        injury.update(injury=.7,condition="incapacitated")
        hp.details=injury
        hp.condition="incapacitated"
        hp.save(update_fields=["details","condition"])
        self.op("hatch","ACC-DR-01-HUB-GALLERY","open")
        result=crew_physical_action(
            leader,self.rid(),"rescue",patient.dbref,
            f"{self.worker.dbref}:ACC-DR-01-HUB-GALLERY:reverse")
        self.assertEqual(result["status"],"succeeded")
        self.assertEqual(patient.location,gallery)
        self.tick(60)
        for person in (leader,self.worker,patient):
            self.assertEqual(person.location,hub)
        self.assertEqual(_clock().details["rescue"]["completed"],1)
        self.assertFalse(_clock().details["rescue"]["jobs"])
        self.assertGreater(_clock().details["unclassified_spaces"][
            "sectors"][sector]["lost_kg"],vented)
        self.assertEqual(_clock().details["summary"][
            "cargo_open_breached_hatches"],[])

    def test_closed_breached_hatch_cannot_be_used_as_emergency_teleport(self):
        sector="DR-01-SEC-07"
        self.survey_drum()
        self.suit()
        self.enter(sector)
        witness_g19_cargo_sector_leak(
            operator_approved=True,sector=sector,leak_kg_s=.9)
        with self.assertRaises(PhysicsError):
            self.op("hatch","ACC-"+sector,"open")
        with self.assertRaises(CrewTransitError):
            self.walk("ACC-"+sector,"reverse")
        self.assertEqual(self.worker.location.db.ox_space_id,sector)

    def test_unsuited_worker_actually_breathes_measured_sector_air(self):
        room="DR-01-SEC-03"
        self.survey_drum()
        self.enter(room)
        initial=_clock().details["unclassified_spaces"]["sectors"][room]["gas"]
        first_o2=initial["oxygen_kg"]
        first_co2=initial["co2_kg"]
        first_mass=initial["mass_kg"]
        self.tick(60)
        actual=_clock().details["unclassified_spaces"]["sectors"][room]["gas"]
        self.assertLess(actual["oxygen_kg"],first_o2)
        self.assertGreater(actual["co2_kg"],first_co2)
        self.assertAlmostEqual(actual["mass_kg"],first_mass)
        self.assertGreater(actual["temperature_k"],293.15)
        self.assertEqual(
            _clock().details["summary"]["crew_o2_used_this_tick_kg"] > 0,True)
        self.leave(room)

    def test_time_on_task_over_ten_minutes_allows_measured_safe_retreat(self):
        sector="DR-01-SEC-04"
        self.survey_drum()
        self.enter(sector)
        self.tick(660)
        # Admission survey is now stale, but the real model has continued
        # to account for air and physiology; no instant re-survey is possible
        # while the maintenance permit is occupied.
        live=_clock().details["unclassified_spaces"]["sectors"][sector]
        self.assertGreater(self.now-live["gas"]["sample_s"],600)
        self.assertIsNotNone(live["permit"])
        with self.assertRaises(PhysicsError):
            survey_g19_cargo_sector(
                operator_approved=True,sector=sector,free_volume_m3=50,
                pressure_pa=101000,temperature_k=293.15,
                oxygen_mass_fraction=.232,co2_mass_fraction=.0004,
                smoke_mass_fraction=0,cargo_class="empty",lot_ids=[])
        self.leave(sector)
        self.assertEqual(self.worker.location.db.ox_space_id,"DR-01-GALLERY")
        self.assertIsNone(
            _clock().details["unclassified_spaces"]["sectors"][sector]["permit"])

    def test_real_aborted_patch_leaves_unsealed_sector_and_unspent_spares(self):
        sector="DR-01-SEC-06"
        self.survey_drum()
        self.at("TOOL-CRIB")
        self.op("repair","TOOL-CRIB","pickup_toolkit")
        survey_g19_water_material(
            operator_approved=True,source="INV-SPARES",
            room_id="SPARES-CENTRAL",verified_kg=2)
        self.at("SPARES-CENTRAL")
        self.op("repair","INV-SPARES","pickup:2")
        self.suit()
        self.enter(sector)
        witness_g19_cargo_sector_leak(
            operator_approved=True,sector=sector,leak_kg_s=.003)
        self.op("cargo_sector",sector,"seal")
        self.tick(60)
        self.op("hatch","ACC-"+sector,"open")
        self.walk("ACC-"+sector,"reverse")
        self.op("hatch","ACC-"+sector,"closed")
        with self.assertRaises(PhysicsError):
            self.op("cargo_sector",sector,"release")
        self.op("cargo_sector",sector,"abort_seal")
        self.op("cargo_sector",sector,"release")
        row=_clock().details["unclassified_spaces"]["sectors"][sector]
        self.assertEqual(row["seals_completed"],0)
        self.assertEqual(row["leak_kg_s"],.003)
        self.assertIsNone(row["permit"])
        self.assertIsNone(row["seal"])
        self.assertAlmostEqual(row["lost_kg"],.18,places=5)
        self.assertAlmostEqual(
            _clock().details["repairs"]["carried_kg"][self.worker.dbref],2)
        self.tick(60)
        self.assertAlmostEqual(
            _clock().details["unclassified_spaces"]["sectors"][sector]["lost_kg"],
            .36,places=5)

    def test_suited_finite_cargo_sector_shell_patch_conserves_gas_and_material(self):
        room="DR-01-SEC-02"
        self.survey_drum()
        self.at("TOOL-CRIB")
        self.op("repair","TOOL-CRIB","pickup_toolkit")
        survey_g19_water_material(operator_approved=True,
            source="INV-SPARES",room_id="SPARES-CENTRAL",verified_kg=2)
        self.at("SPARES-CENTRAL")
        self.op("repair","INV-SPARES","pickup:2")
        self.suit()
        self.enter(room)
        d=_clock().details
        original=d["unclassified_spaces"]["sectors"][room]["gas"]["mass_kg"]
        previously_lost=d["lost_to_space_kg"]
        witness_g19_cargo_sector_leak(
            operator_approved=True,sector=room,leak_kg_s=.002)
        with self.assertRaises(PhysicsError):
            self.op("cargo_sector",room,"inspect")
        self.op("cargo_sector",room,"seal")
        self.tick(180)
        d=_clock().details
        sector=d["unclassified_spaces"]["sectors"][room]
        self.assertEqual(sector["leak_kg_s"],0.0)
        self.assertEqual(sector["seals_completed"],1)
        self.assertAlmostEqual(sector["lost_kg"],.36,places=5)
        self.assertAlmostEqual(original-sector["gas"]["mass_kg"],.36,places=5)
        self.assertAlmostEqual(d["lost_to_space_kg"]-previously_lost,.36,places=5)
        self.assertAlmostEqual(d["repairs"]["installed_kg"],2)
        self.leave(room)

    def test_portal_dock_is_not_pressure_certification_or_passage(self):
        portal="DR-01-P1"
        commission_commercial_port(operator_approved=True,operation="dock",
            portal_id=portal,berth_id="BERTH-A")
        commission_commercial_port(operator_approved=True,operation="register",
            portal_id=portal,berth_id="BERTH-A",
            lot_id="EXT-LOT-1",mass_kg=1000,kind="bulk")
        self.at("DR-01-GALLERY")
        with self.assertRaises(CrewTransitError):
            self.walk("ACC-"+portal,"forward")
        with self.assertRaises(PhysicsError):
            self.op("hatch","ACC-"+portal,"open")
        with self.assertRaises(PhysicsError):
            self.op("port",portal,"load:EXT-LOT-1")
        inspect_g19_portal_sleeve(operator_approved=True,
            portal=portal,berth_id="BERTH-A")
        self.assertTrue(local_physics_readout(
            self.worker,"cargo_portals")["portals"][portal]["ready"])
        # The original ship leaves berth with its reference cargo aboard;
        # a valid pressure-sleeve certificate is NOT a grant of extra hold
        # capacity. Preserve the real 1000 kg overload refusal.
        with self.assertRaises(PhysicsError):
            self.op("port",portal,"load:EXT-LOT-1")
        # Locate an actual portion of that existing onboard reference cargo,
        # then perform a physically valid outbound transfer instead.
        survey_cargo_lot(
            operator_approved=True,operation="declare",lot_id="OUT-LOT-1",
            mass_kg=3000,drum="DR-01",azimuth_deg=0,radius_m=5,
            kind="bulk",restrained=True)
        self.op("port",portal,"unload:OUT-LOT-1")
        self.assertIn(portal,_clock().details["cargo"]["port_jobs"])
        with self.assertRaises(PhysicsError):
            commission_commercial_port(operator_approved=True,
                operation="undock",portal_id=portal,berth_id="BERTH-A")
        self.op("port",portal,"abort:OUT-LOT-1")
        # Abort takes the physical rail reversal path, not a mass-deleting
        # mutation that makes an occupied berth suddenly disappear.
        self.assertIn(portal,_clock().details["cargo"]["port_jobs"])

    def test_bow_water_trim_are_remote_controls_not_walkable_pressure_zones(self):
        for room in ("TRUNK-B-BOW","WATER-FWD","WR-ROTOR-MACHINERY"):
            self.at(room)
            if room=="WATER-FWD":
                self.op("switch","ISO-GAS-BANK-A","closed")
            target={
                "TRUNK-B-BOW":"BOW-SHIELD-FOREPEAK",
                "WATER-FWD":"WATER-SHIELD-FWD",
                "WR-ROTOR-MACHINERY":"WR-TRIM-TANK-BAY"}[room]
            self.op("shield_trim",target,"inspect")
            reading=local_physics_readout(self.worker,"shield_trim")
            self.assertFalse(reading["closed_enclosures"][target]["walkable"])
        self.at("TRUNK-B-BOW")
        with self.assertRaises(PhysicsError):
            self.op("hatch","ACC-BOW-SHIELD-FOREPEAK","open")
        with self.assertRaises(CrewTransitError):
            self.walk("ACC-BOW-SHIELD-FOREPEAK","forward")
        self.at("WATER-FWD")
        with self.assertRaises(CrewTransitError):
            self.walk("ACC-WATER-SHIELD-FWD","forward")
        self.assertIsNone(_clock().details["unclassified_spaces"]["sectors"][
            "DR-01-SEC-01"]["gas"])
