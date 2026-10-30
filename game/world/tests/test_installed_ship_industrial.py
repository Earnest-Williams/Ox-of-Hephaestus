"""Authentic sixteen industrial sites: original hatch, metered air, leak patch."""
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    state)
from world.ship_world import build_canonical_ship, find_ship_space, find_world_entity
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.ship_industrial_access import SITES
from world.continuous_ship_physics import (
    PhysicsError, _clock, arm_continuous_physics,
    commission_g19_electrical, commission_g19_water, commission_g19_repairs,
    commission_g19_eva, commission_g19_crew_physiology,
    commission_g19_industrial_bays, survey_g19_industrial_bay,
    witness_g19_industrial_leak, survey_g19_water_material,
    crew_physical_action, local_physics_readout, tick_continuous_physics)


class FittedIndustrialMaintenance(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.crew=build_ship()
        self.worker=self.crew["watch"]
        # Physiology enrolls only characters physically aboard canonical
        # Evennia ship rooms; the bootstrap watch starts at a separate
        # scenario staging location.
        self.assertTrue(self.worker.move_to(
            find_ship_space("ENG-CONTROL"),quiet=True))
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        commission_g19_crew_physiology(
            operator_approved=True,actor_dbrefs=[self.worker.dbref])
        self.assertTrue(commission_g19_industrial_bays(
            operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_industrial_bays(
            operator_approved=True)["commissioned"])
        self.serial=200
        self.time=1000

    def rid(self):
        self.serial+=1
        return f"{self.serial:032x}"

    def at(self,room):
        self.assertTrue(self.worker.move_to(find_ship_space(room),quiet=True),room)

    def act(self,action,target,value,actor=None,rid=None):
        return crew_physical_action(actor or self.worker,rid or self.rid(),
                                     action,target,value)

    def walk(self,link,direction):
        door=find_world_entity("access:"+link+":"+direction)
        self.assertIsNotNone(door,link)
        return traverse_canonical_exit(
            self.worker,door,door.destination,request_id=self.rid())

    def tick(self,seconds):
        while seconds:
            dt=min(60,seconds)
            self.time+=dt
            tick_continuous_physics(now_game_time=self.time)
            seconds-=dt

    def survey(self,room):
        return survey_g19_industrial_bay(
            operator_approved=True,room_id=room,
            volume_m3=SITES[room]["max_m3"]*.7,
            pressure_pa=101000,temperature_k=293.15,
            oxygen_mass_fraction=.232,co2_mass_fraction=.0004,
            smoke_mass_fraction=0,skin_k=299)

    def wear_suit(self,trunk):
        # Checkout at the original EVA-AFT lock, do not invent oxygen.
        self.at("ENG-LOCKER")
        self.act("eva","INV-DC-CONSUMABLES","stage:0.75")
        self.at("TRUNK-B-AFT")
        self.act("eva","EVA-AFT","inner_open")
        self.walk("ACC-EVA-AFT","forward")
        self.act("eva","EVA-AFT","inner_close")
        self.act("eva","EVA-AFT","checkout")
        self.act("eva","EVA-AFT","inner_open")
        self.walk("ACC-EVA-AFT","reverse")
        self.act("eva","EVA-AFT","inner_close")
        self.at(trunk)

    def enter(self,room):
        spec=SITES[room]
        self.at(spec["trunk"])
        signed=self.act("industrial",room,"secure")
        self.assertEqual(self.act("industrial",room,"secure",
                                  rid=signed["request_id"]),signed)
        self.act("hatch",spec["door"],"open")
        self.assertEqual(self.walk(spec["door"],"forward")["status"],"succeeded")
        self.act("hatch",spec["door"],"closed")

    def leave(self,room):
        spec=SITES[room]
        self.act("hatch",spec["door"],"open")
        self.assertEqual(self.walk(spec["door"],"reverse")["status"],"succeeded")
        self.act("hatch",spec["door"],"closed")
        self.act("industrial",room,"release")

    def test_original_ftl_hatch_suit_and_finite_air(self):
        room="FTL-SVC"
        self.survey(room)
        self.at("TRUNK-A-AFT")
        with self.assertRaises(PhysicsError):
            self.act("hatch",SITES[room]["door"],"open")
        with self.assertRaises(CrewTransitError):
            self.walk(SITES[room]["door"],"forward")
        self.wear_suit("TRUNK-A-AFT")
        self.enter(room)
        reading=local_physics_readout(self.worker,"industrial")["sites"][room]
        self.assertTrue(reading["entry_ready"])
        self.assertGreater(reading["finite_gas_kg"],0)
        self.assertIsNone(_clock().details["industrial_bays"]["sites"]["FUEL-SVC"]["gas"])
        self.act("industrial",room,"inspect")
        self.assertTrue(self.crew["officer"].move_to(
            find_ship_space("CMD-PRIMARY"),quiet=True))
        with self.assertRaises(PhysicsError):
            self.act("ftl","UNPLANNED","engage",actor=self.crew["officer"])
        self.leave(room)
        self.assertEqual(_clock().details["industrial_bays"]["sites"][room]["entries"],1)
        self.assertEqual(_clock().details["industrial_bays"]["sites"][room]["inspections"],1)

    def test_bearing_suited_minor_leak_consumes_real_parts_and_ship_air(self):
        room="BE-01-SVC"
        self.at("TOOL-CRIB")
        self.act("repair","TOOL-CRIB","pickup_toolkit")
        survey_g19_water_material(operator_approved=True,
            source="INV-SPARES",room_id="SPARES-CENTRAL",verified_kg=2)
        self.at("SPARES-CENTRAL")
        self.act("repair","INV-SPARES","pickup:2")
        self.survey(room)
        self.wear_suit("TRUNK-B-DR-01")
        self.enter(room)
        first=_clock().details["industrial_bays"]["sites"][room]["gas"]["mass_kg"]
        lost_before=_clock().details["lost_to_space_kg"]
        witness_g19_industrial_leak(
            operator_approved=True,room_id=room,leak_kg_s=.002)
        with self.assertRaises(PhysicsError):
            self.act("industrial",room,"inspect")
        self.act("industrial",room,"seal")
        self.tick(180)
        site=_clock().details["industrial_bays"]["sites"][room]
        self.assertIsNone(site["seal"])
        self.assertEqual(site["repairs"],1)
        self.assertEqual(site["leak_kg_s"],0)
        self.assertAlmostEqual(site["lost_kg"],.36,places=6)
        self.assertAlmostEqual(site["gas"]["mass_kg"],first-.36,places=6)
        self.assertAlmostEqual(_clock().details["lost_to_space_kg"]-lost_before,.36,places=6)
        self.assertAlmostEqual(_clock().details["repairs"]["installed_kg"],2)
        self.leave(room)
        self.assertIsNone(_clock().details["industrial_bays"]["sites"][room]["permit"])

    def test_large_unattended_bearing_breach_prevents_drum_restart(self):
        room="BE-02-SVC"
        self.survey(room)
        witness_g19_industrial_leak(
            operator_approved=True,room_id=room,leak_kg_s=.15)
        self.wear_suit("TRUNK-B-DR-01")
        with self.assertRaises(PhysicsError):
            self.act("industrial",room,"secure")
        self.at("ENG-CONTROL")
        with self.assertRaises(PhysicsError):
            self.act("rotor","DR-01","start")
        before=_clock().details["lost_to_space_kg"]
        self.tick(20)
        self.assertGreater(_clock().details["lost_to_space_kg"],before)
        self.assertEqual(_clock().details["rotors"]["DR-01"]["target_rpm"],0)

    def test_failed_ftl_controller_finite_repair_requires_local_isolation(self):
        """Operator-observed machinery fault cannot be repaired live or remotely.

        The actual LCS-FTL is inside the original unclassified FTL-SVC room.
        A suited, toolkit-carrying engineer closes the rated hatch, isolates
        its separate local panel feed, works 600 real ship seconds and
        consumes three kilograms of previously surveyed carried spares.
        """
        from world.full_ship_operations import set_component_condition
        room="FTL-SVC"
        self.at("TOOL-CRIB")
        self.act("repair","TOOL-CRIB","pickup_toolkit")
        survey_g19_water_material(
            operator_approved=True,source="INV-SPARES",
            room_id="SPARES-CENTRAL",verified_kg=3)
        self.at("SPARES-CENTRAL")
        self.act("repair","INV-SPARES","pickup:3")
        self.survey(room)
        set_component_condition("equipment","LCS-FTL","failed",operator=True)
        self.wear_suit("TRUNK-A-AFT")
        self.enter(room)
        # The fitted ship defaults this original in-room panel feeder OPEN.
        # Positively energise it BEFORE proving live-tool repair refusal;
        # do not test an imagined default breaker state.
        self.act("switch","ISO-LP-FTL-SVC","closed")
        self.assertEqual(state("isolator","ISO-LP-FTL-SVC").setting,"closed")
        with self.assertRaises(PhysicsError):
            self.act("repair","equipment:LCS-FTL","start")
        self.act("switch","ISO-LP-FTL-SVC","open")
        started=self.act("repair","equipment:LCS-FTL","start")
        self.assertEqual(started["status"],"succeeded")
        self.assertEqual(state("equipment","LCS-FTL").condition,"failed")
        with self.assertRaises(PhysicsError):
            self.act("switch","ISO-LP-FTL-SVC","closed")
        self.tick(600)
        self.assertEqual(state("equipment","LCS-FTL").condition,"serviceable")
        self.assertGreaterEqual(_clock().details["repairs"]["completed"],1)
        self.assertAlmostEqual(_clock().details["repairs"]["installed_kg"],3)
        self.assertAlmostEqual(
            _clock().details["repairs"]["carried_kg"][self.worker.dbref],0)
        self.leave(room)
        self.assertEqual(
            state("isolator","ISO-LP-FTL-SVC").setting,"open")

    def test_fitted_sixteen_sites_match_real_objects(self):
        self.assertEqual(len(SITES),16)
        for room,spec in SITES.items():
            hatch=state("access",spec["door"])
            self.assertEqual(hatch.reference["from"],spec["trunk"])
            self.assertEqual(hatch.reference["to"],room)
            self.assertTrue(hatch.reference["pressure_boundary"])
            self.assertEqual(state("equipment",spec["panel"]).space_id,room)
            self.assertEqual(state("isolator",spec["breaker"]).space_id,room)
        self.assertEqual(len(_clock().details["industrial_bays"]["sites"]),16)
