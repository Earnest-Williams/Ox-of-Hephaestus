"""G19 installed pressure-shell restoration; one engineer, no voyage."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    PhysicsError, _clock, _topology, arm_continuous_physics,
    commission_g19_water, commission_g19_repairs, commission_g19_hull,
    register_g19_hull_breach, survey_g19_water_material,
    crew_physical_action, local_physics_readout, tick_continuous_physics,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    state, set_isolator,
)
from world.models import WorkReceipt, CanonicalShipEvent
from world.ship_world import build_canonical_ship, find_ship_space


class InstalledHullRepairTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        self.assertTrue(commission_g19_hull(operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_hull(operator_approved=True)["commissioned"])
        set_isolator("ISO-GEN-M", "closed", operator=True)
        self.tech = build_ship()["watch"]
        link = state("access", "ACC-BR-03-HAB-03")
        zones = _topology()[0]
        self.site = next(room for room in
                         (link.reference["from"], link.reference["to"])
                         if zones.get(room) == "PZ-HAB-03")
        self.zone = "PZ-HAB-03"

    def action(self, digit, action, target, value):
        return crew_physical_action(self.tech, digit * 32, action, target, value)

    def tick(self, start, seconds):
        now = start
        for _ in range(int(seconds // 60)):
            now += 60
            tick_continuous_physics(now_game_time=now)
        return now

    def prepare_repair_parts(self, kg=6):
        self.tech.move_to(find_ship_space("TOOL-CRIB"), quiet=True)
        self.action("0", "repair", "TOOL-CRIB", "pickup_toolkit")
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=kg)
        self.tech.move_to(find_ship_space("STORE-CRIT-SPARES"), quiet=True)
        self.action("1", "repair", "INV-SPARES", f"pickup:{kg}")
        self.tech.move_to(find_ship_space(self.site), quiet=True)

    def register(self, rate=.002):
        return register_g19_hull_breach(
            operator_approved=True, zone_id=self.zone,
            site_room_id=self.site, leak_kg_s=rate)

    def test_real_timed_patch_permanent_restore_and_material_custody(self):
        self.prepare_repair_parts()
        spare_after_pickup = state("inventory", "INV-SPARES").quantity
        initial_air = state("pressure", self.zone).quantity
        self.register(.002)
        self.assertEqual(local_physics_readout(self.tech, "hull")[
            "breaches_here"][self.zone]["phase"], "open")
        with self.assertRaises(PhysicsError):
            self.action("2", "hull", self.zone, "restore")
        first = self.action("3", "hull", self.zone, "patch")
        self.assertEqual(first["status"], "succeeded")
        self.assertEqual(self.action("3", "hull", self.zone, "patch"), first)
        self.assertEqual(len(WorkReceipt.objects.filter(pk="3" * 32)), 1)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "hull:" + self.zone]["remaining_s"], 600)
        self.tick(1000, 600)
        patched = state("pressure", self.zone)
        self.assertAlmostEqual(patched.details["physics_leak_kg_s"], .0002)
        self.assertLess(patched.quantity, initial_air)
        self.assertEqual(_clock().details["hull"]["breaches"][
            self.zone]["phase"], "patched")
        self.assertEqual(_clock().details["repairs"]["installed_kg"], 2)
        self.action("4", "hull", self.zone, "restore")
        self.tick(1600, 900)
        finished = state("pressure", self.zone)
        self.assertEqual(finished.details["physics_leak_kg_s"], 0)
        self.assertEqual(_clock().details["hull"]["breaches"][
            self.zone]["phase"], "restored")
        self.assertEqual(_clock().details["hull"]["restorations_completed"], 1)
        self.assertAlmostEqual(_clock().details["repairs"]["installed_kg"], 6)
        self.assertAlmostEqual(_clock().details["repairs"]["delivered_spares_kg"], 6)
        self.assertAlmostEqual(state("inventory", "INV-SPARES").quantity,
                               spare_after_pickup)
        self.assertLess(finished.quantity, initial_air)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="crew_hull_restoration_complete").count(), 2)
        self.assertFalse(_clock().details["repairs"]["jobs"])
        self.assertEqual(self.action("4", "hull", self.zone, "restore")["status"],
                         "succeeded")

    def test_no_remote_repair_and_work_pauses_if_worker_leaves(self):
        self.prepare_repair_parts(2)
        self.register(.001)
        self.tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        with self.assertRaises(PermissionError):
            self.action("5", "hull", self.zone, "patch")
        self.assertFalse(WorkReceipt.objects.filter(pk="5" * 32).exists())
        self.tech.move_to(find_ship_space(self.site), quiet=True)
        self.action("6", "hull", self.zone, "patch")
        self.tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        tick_continuous_physics(now_game_time=1060)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "hull:" + self.zone]["remaining_s"], 600)
        self.tech.move_to(find_ship_space(self.site), quiet=True)
        tick_continuous_physics(now_game_time=1120)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "hull:" + self.zone]["remaining_s"], 540)

    def test_large_leak_needs_suited_access_and_does_not_issue_parts(self):
        self.prepare_repair_parts(2)
        self.register(1.0)
        with self.assertRaises(PhysicsError):
            self.action("7", "hull", self.zone, "patch")
        self.assertFalse(WorkReceipt.objects.filter(pk="7" * 32).exists())
        self.assertFalse(_clock().details["repairs"]["jobs"])
        self.assertEqual(_clock().details["repairs"]["carried_kg"][
            self.tech.dbref], 2)
        original_air = state("pressure", self.zone).quantity
        tick_continuous_physics(now_game_time=1010)
        self.assertLess(state("pressure", self.zone).quantity, original_air)

    def test_active_fire_stops_hull_work_without_refunding_reserved_parts(self):
        from world.continuous_ship_physics import configure_scenario_casualty
        self.prepare_repair_parts(2)
        self.register(.001)
        self.action("8", "hull", self.zone, "patch")
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "hull:" + self.zone]["staged_kg"], 2)
        configure_scenario_casualty(
            self.zone, fire_fuel_kg=2, fire_burn_kg_s=.1, operator=True)
        tick_continuous_physics(now_game_time=1060)
        job = _clock().details["repairs"]["jobs"]["hull:" + self.zone]
        self.assertEqual(job["remaining_s"], 600)
        self.assertEqual(job["staged_kg"], 2)
        self.assertEqual(state("pressure", self.zone).details["physics_leak_kg_s"],
                         .001)

    def test_operator_cannot_relabel_existing_leak_or_reset_registered_breach(self):
        from world.continuous_ship_physics import configure_scenario_casualty
        configure_scenario_casualty(self.zone, leak_kg_s=.02, operator=True)
        with self.assertRaises(PhysicsError):
            self.register(.01)
        configure_scenario_casualty(self.zone, leak_kg_s=0, operator=True)
        self.register(.002)
        with self.assertRaises(PhysicsError):
            self.register(.003)
        with self.assertRaises(PhysicsError):
            configure_scenario_casualty(self.zone, leak_kg_s=0, operator=True)
        self.assertEqual(state("pressure", self.zone).details["physics_leak_kg_s"],
                         .002)


