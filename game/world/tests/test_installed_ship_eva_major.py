"""Real installed Evennia EVA / major breach tests, no 40-crew voyage."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.ship_world import build_canonical_ship, find_ship_space, find_world_entity
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition, state,
)
from world.continuous_ship_physics import (
    PhysicsError, _clock, arm_continuous_physics, tick_continuous_physics,
    commission_g19_water, commission_g19_repairs, commission_g19_hull,
    commission_g19_eva, commission_g19_major_damage,
    register_g19_hull_breach, register_g19_major_breach_site,
    survey_g19_water_material, crew_physical_action,
    local_physics_readout,
)
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.models import WorkReceipt, CanonicalShipEvent


class InstalledEVAMajorDamageTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        set_isolator("ISO-DB-A-BOW", "closed", operator=True)
        set_isolator("ISO-DB-A-HAB-HUB-SERVICES", "closed", operator=True)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_hull(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        commission_g19_major_damage(operator_approved=True)
        self.crew = build_ship()
        self.tech = self.crew["watch"]
        self.now = 1000
        self.serial = 100

    def ident(self):
        self.serial += 1
        return f"{self.serial:032x}"

    def action(self, kind, target, value):
        return crew_physical_action(self.tech, self.ident(), kind, target, value)

    def move(self, room):
        self.tech.move_to(find_ship_space(room), quiet=True)

    def advance(self, seconds):
        while seconds > 0:
            dt = min(60, seconds)
            self.now += dt
            tick_continuous_physics(now_game_time=self.now)
            seconds -= dt

    def transit(self, access, destination):
        exit_obj = find_world_entity("access:" + access + ":forward")
        return traverse_canonical_exit(
            self.tech, exit_obj, find_ship_space(destination),
            request_id=self.ident())

    def issue_suit_at_forward_airlock(self):
        self.move("ENG-LOCKER")
        self.action("eva", "INV-DC-CONSUMABLES", "stage:0.75")
        self.move("TRUNK-B-BOW")
        self.action("eva", "EVA-FWD", "inner_open")
        self.assertEqual(self.transit("ACC-EVA-FWD", "EVA-FWD")["status"],
                         "succeeded")
        self.action("eva", "EVA-FWD", "inner_close")
        self.action("eva", "EVA-FWD", "checkout")
        self.action("switch", "ISO-AIR-FIXED-EVA-FWD", "closed")
        self.action("switch", "ISO-LP-EVA-FWD", "closed")

    def pumpout_and_exit_forward(self):
        self.action("eva", "EVA-FWD", "pumpdown")
        self.advance(90)
        self.assertEqual(_clock().details["eva"]["locks"]["EVA-FWD"]["mode"],
                         "vacuum")
        self.action("eva", "EVA-FWD", "outer_open")
        started = self.transit("ACC-EVA-FWD-EXT", "EXT-BOW")
        self.assertEqual(started["status"], "queued")
        self.assertEqual(started["travel_seconds"], 45)
        self.advance(45)
        self.assertEqual(self.tech.location.db.ox_space_id, "EXT-BOW")

    def test_two_fitted_oxygen_and_recovery_ledgers_support_real_eva(self):
        store_before = state("inventory", "INV-DC-CONSUMABLES").quantity * 1000
        lock_before = state("pressure", "PZ-BOW-EVA").quantity
        self.issue_suit_at_forward_airlock()
        stock = state("inventory", "INV-DC-CONSUMABLES").quantity * 1000
        self.assertAlmostEqual(store_before - stock, .75)
        self.assertAlmostEqual(_clock().details["eva"]["issued_kg"], .75)
        with self.assertRaises(PhysicsError):
            self.action("eva", "EVA-FWD", "outer_open")
        self.pumpout_and_exit_forward()
        self.assertAlmostEqual(state("pressure", "PZ-BOW-EVA").quantity, 0)
        self.assertAlmostEqual(
            _clock().details["eva"]["locks"]["EVA-FWD"]["buffer"]["mass"],
            lock_before, delta=.5)
        self.assertLess(
            _clock().details["eva"]["suits"]["EVA-FWD-SUIT-1"][
                "exposure"]["suit_oxygen_kg"], .75)
        self.assertGreater(
            _clock().details["eva"]["consumed_oxygen_kg"], 0)
        self.assertEqual(_clock().details["eva"]["completed_transits"], 1)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="crew_eva_transit_complete").count(), 1)
        self.assertEqual(local_physics_readout(self.tech, "eva")[
            "suit"]["home"], "EVA-FWD")

    def test_large_breach_isolation_and_suited_exterior_hull_recovery(self):
        zone = "PZ-DR-01-SVC"
        register_g19_hull_breach(
            operator_approved=True, zone_id=zone,
            site_room_id="DR-01-GALLERY", leak_kg_s=.5)
        survey = register_g19_major_breach_site(
            operator_approved=True, zone_id=zone,
            exterior_room_id="EXT-DR01-SKIN")
        self.assertGreaterEqual(len(survey["rated_boundaries"]), 3)
        self.move("ENG-CONTROL")
        self.action("switch", "ISO-LP-ENG-CONTROL", "closed")
        self.action("damage", zone, "isolate")
        self.advance(60)
        self.assertFalse(
            _clock().details["major_damage"]["sites"][zone]["isolated"])
        self.advance(60)
        major = _clock().details["major_damage"]["sites"][zone]
        self.assertTrue(major["isolated"])
        for door in survey["rated_boundaries"]:
            self.assertEqual(state("access", door).setting, "closed")
        self.assertEqual(_clock().details["major_damage"][
            "containments_completed"], 1)

        self.move("TOOL-CRIB")
        self.action("repair", "TOOL-CRIB", "pickup_toolkit")
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=6)
        self.move("STORE-CRIT-SPARES")
        self.action("repair", "INV-SPARES", "pickup:6")
        self.issue_suit_at_forward_airlock()
        self.pumpout_and_exit_forward()

        self.assertEqual(self.transit(
            "ACC-EXT-BOW-EXT-DR01", "EXT-DR01")["status"], "queued")
        self.advance(30)
        self.assertEqual(self.tech.location.db.ox_space_id, "EXT-DR01")
        self.action("eva", "ACC-EXT-DR01-EXT-DR01-SKIN", "deploy")
        self.assertEqual(self.transit(
            "ACC-EXT-DR01-EXT-DR01-SKIN", "EXT-DR01-SKIN")[
                "travel_seconds"], 180)
        self.advance(180)
        self.assertEqual(self.tech.location.db.ox_space_id, "EXT-DR01-SKIN")

        pressure_before_repair = state("pressure", zone).quantity
        self.action("hull", zone, "patch")
        self.advance(600)
        self.assertAlmostEqual(
            state("pressure", zone).details["physics_leak_kg_s"], .05)
        self.action("hull", zone, "restore")
        self.advance(900)
        self.assertEqual(
            state("pressure", zone).details["physics_leak_kg_s"], 0)
        self.assertEqual(_clock().details["hull"]["breaches"][zone][
            "phase"], "restored")
        self.assertAlmostEqual(_clock().details["repairs"]["installed_kg"], 6)
        self.assertLessEqual(state("pressure", zone).quantity, pressure_before_repair)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="crew_hull_restoration_complete").count(), 2)

    def test_broken_bulkhead_pauses_containment_and_preserves_leak(self):
        zone = "PZ-DR-02-SVC"
        register_g19_hull_breach(
            operator_approved=True, zone_id=zone,
            site_room_id="DR-02-GALLERY", leak_kg_s=.7)
        survey = register_g19_major_breach_site(
            operator_approved=True, zone_id=zone,
            exterior_room_id="EXT-DR02-SKIN")
        damaged = survey["rated_boundaries"][0]
        set_component_condition("access", damaged, "failed", operator=True)
        self.move("ENG-CONTROL")
        self.action("switch", "ISO-LP-ENG-CONTROL", "closed")
        self.action("damage", zone, "isolate")
        self.advance(120)
        site = _clock().details["major_damage"]["sites"][zone]
        self.assertFalse(site["isolated"])
        self.assertEqual(site["remaining_s"], 120)
        self.assertEqual(state("pressure", zone).details["physics_leak_kg_s"], .7)
        self.assertFalse(CanonicalShipEvent.objects.filter(
            operation="major_hull_containment_complete").exists())


