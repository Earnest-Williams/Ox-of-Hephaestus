"""Installed v0.5 48 manifest compartments, 12 commercial sleeves, 3 voids."""
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells,
    initialize_nominal_atmosphere, state)
from world.ship_world import (
    build_canonical_ship, find_ship_space, find_world_entity)
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
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
            _clock().details["summary"]["crew_oxygen_consumed_kg"] > 0,True)
        self.leave(room)

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
        self.op("port",portal,"load:EXT-LOT-1")
        self.assertIn(portal,_clock().details["cargo"]["port_jobs"])
        with self.assertRaises(PhysicsError):
            commission_commercial_port(operator_approved=True,
                operation="undock",portal_id=portal,berth_id="BERTH-A")
        self.op("port",portal,"abort:EXT-LOT-1")
        # Do not let a parked, actively recovering job instantly vanish.
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
