"""Full installed-world G19 port-side waste shipment and equipment restoration."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    arm_continuous_physics, commission_g19_water,
    commission_g19_repairs, survey_g19_repair_site,
    commission_commercial_port,
    commission_waste_acceptance, survey_waste_freight_route,
    survey_g19_water_material, crew_physical_action, _clock,
    tick_continuous_physics, PhysicsError, local_physics_readout,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_component_condition, set_isolator, state,
)
from world.ship_world import build_canonical_ship, find_ship_space
from world.models import WorkReceipt, CanonicalShipEvent, CanonicalShipState
from world.ship_crew_access import CrewTransitError


class InstalledWasteAndRepairTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000.0)
        self.assertTrue(commission_g19_water(operator_approved=True)["commissioned"])
        self.assertTrue(commission_g19_repairs(operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_repairs(operator_approved=True)["commissioned"])
        set_isolator("ISO-GEN-M", "closed", operator=True)
        self.crew = build_ship()
        self.tech, self.cargo = self.crew["watch"], self.crew["cargo"]

    def _action(self, actor, token, action, target, value):
        return crew_physical_action(
            actor, token * 32, action, target, value)

    def _tick(self, seconds, start=1000.0):
        now = start
        for _ in range(int(seconds / 60)):
            now += 60
            tick_continuous_physics(now_game_time=now)
        return now

    def _toolkit(self):
        self.tech.move_to(find_ship_space("TOOL-CRIB"), quiet=True)
        receipt = self._action(self.tech, "0", "repair", "TOOL-CRIB",
                               "pickup_toolkit")
        self.assertEqual(receipt["status"], "succeeded")
        return receipt

    def _industrial(self):
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="SPARES-CENTRAL", verified_kg=4)
        self.tech.move_to(find_ship_space("SPARES-CENTRAL"), quiet=True)
        self._action(self.tech, "a", "waste", "IND-SCRAP-HOLD-A",
                     "deposit:INV-SPARES:2")
        self.assertAlmostEqual(
            state("inventory", "INV-INDUSTRIAL-SCRAP").quantity, .002, places=6)

    def test_real_berth_cassette_haul_offload_return_and_departure_mass(self):
        self._industrial()
        self.assertEqual(_clock().details["water"]["cassettes"]["industrial"]["A"], 2)
        commission_waste_acceptance(
            operator_approved=True, acceptance_id="BERTH-IND-A",
            portal_id="DR-01-P1", berth_id="YARD-IND",
            category="industrial", limit_kg=5000)
        route = survey_waste_freight_route(
            operator_approved=True, receiver_id="IND-SCRAP-HOLD-A",
            portal_id="DR-01-P1")
        self.assertGreater(route["segments"], 2)
        first = self._action(
            self.tech, "b", "waste", "IND-SCRAP-HOLD-A",
            "stage:BERTH-IND-A")
        self.assertEqual(first["status"], "succeeded")
        self.assertEqual(self._action(
            self.tech, "b", "waste", "IND-SCRAP-HOLD-A",
            "stage:BERTH-IND-A"), first)
        self.tech.move_to(find_ship_space("DR-01-FREIGHT-LOCK"), quiet=True)
        with self.assertRaises(PhysicsError):
            self._action(self.tech, "c", "wasteport", "IND-SCRAP-HOLD-A", "haul")
        self._action(self.tech, "d", "rotor", "DR-01", "freight_extend")
        self._action(self.tech, "e", "wasteport", "IND-SCRAP-HOLD-A", "capture_open")
        self._action(self.tech, "c", "wasteport", "IND-SCRAP-HOLD-A", "haul")
        mass_before = _clock().details["motion"]["dry_mass_kg"]
        self._tick(240)
        self.assertEqual(
            _clock().details["water"]["waste_offload"]["jobs"][
                "IND-SCRAP-HOLD-A"]["phase"], "port_ready")
        self.assertEqual(
            _clock().details["water"]["cassettes"]["industrial"]["A"], 0)
        self.assertAlmostEqual(
            state("inventory", "INV-INDUSTRIAL-SCRAP").quantity, .002, places=6)
        self.assertEqual(_clock().details["motion"]["dry_mass_kg"], mass_before)
        self._action(self.tech, "f", "wasteport", "IND-SCRAP-HOLD-A", "capture_close")
        self._action(self.tech, "0", "rotor", "DR-01", "freight_retract")
        commission_commercial_port(
            operator_approved=True, operation="dock",
            portal_id="DR-01-P1", berth_id="YARD-IND")
        with self.assertRaises(PhysicsError):
            commission_commercial_port(
                operator_approved=True, operation="undock",
                portal_id="DR-01-P1", berth_id="YARD-IND")
        self.cargo.move_to(find_ship_space("CARGO-CTRL-FWD"), quiet=True)
        self._action(self.cargo, "1", "wasteport", "IND-SCRAP-HOLD-A", "offload")
        tick_continuous_physics(now_game_time=1300)
        self.assertEqual(
            state("inventory", "INV-INDUSTRIAL-SCRAP").quantity, .002)
        tick_continuous_physics(now_game_time=1310)
        self.assertEqual(state("inventory", "INV-INDUSTRIAL-SCRAP").quantity, 0)
        self.assertAlmostEqual(
            _clock().details["motion"]["dry_mass_kg"], mass_before - 2)
        self.assertEqual(
            _clock().details["water"]["waste_offload"]["delivered_kg"]["industrial"], 2)
        self.assertEqual(
            _clock().details["water"]["waste_offload"]["jobs"][
                "IND-SCRAP-HOLD-A"]["phase"], "return_ready")
        commission_commercial_port(
            operator_approved=True, operation="undock",
            portal_id="DR-01-P1", berth_id="YARD-IND")
        self._action(self.tech, "2", "rotor", "DR-01", "freight_extend")
        self._action(self.tech, "3", "wasteport", "IND-SCRAP-HOLD-A", "capture_open")
        self._action(self.tech, "4", "wasteport", "IND-SCRAP-HOLD-A", "return")
        self._tick(240, start=1310)
        self.assertFalse(_clock().details["water"]["waste_offload"]["jobs"])
        self.assertEqual(_clock().details["water"]["cassettes"]["industrial"]["A"], 0)
        self.assertEqual(
            _clock().details["water"]["waste_offload"]["acceptances"][
                "BERTH-IND-A"]["accepted_kg"], 2)
        self.assertFalse(WorkReceipt.objects.filter(pk="e" * 32).count() > 1)

    def test_cross_class_acceptance_and_nonlocal_work_are_denied(self):
        self._industrial()
        commission_waste_acceptance(
            operator_approved=True, acceptance_id="BERTH-HAZ",
            portal_id="DR-02-P1", berth_id="YARD-HAZ",
            category="hazardous", limit_kg=50)
        survey_waste_freight_route(
            operator_approved=True, receiver_id="IND-SCRAP-HOLD-A",
            portal_id="DR-02-P1")
        with self.assertRaises(PhysicsError):
            self._action(self.tech, "5", "waste", "IND-SCRAP-HOLD-A",
                         "stage:BERTH-HAZ")
        self.assertFalse(WorkReceipt.objects.filter(pk="5" * 32).exists())
        commission_waste_acceptance(
            operator_approved=True, acceptance_id="BERTH-IND",
            portal_id="DR-02-P1", berth_id="YARD-IND",
            category="industrial", limit_kg=200)
        self._action(self.tech, "7", "waste", "IND-SCRAP-HOLD-A",
                     "stage:BERTH-IND")
        with self.assertRaises(PermissionError):
            self._action(self.cargo, "6", "wasteport",
                         "IND-SCRAP-HOLD-A", "offload")

    def test_crew_carried_spares_repair_failed_water_processor_after_real_work(self):
        self._toolkit()
        self.tech.move_to(find_ship_space("HAB-06-ECLSS-A"), quiet=True)
        self._action(self.tech, "a", "water", "WATER-PROC-A", "off")
        set_component_condition("equipment", "WATER-PROC-A",
                                "failed", operator=True)
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=4)
        self.tech.move_to(find_ship_space("STORE-CRIT-SPARES"), quiet=True)
        original = state("inventory", "INV-SPARES").quantity
        issued = self._action(self.tech, "b", "repair", "INV-SPARES", "pickup:3")
        self.assertEqual(issued["status"], "succeeded")
        self.assertEqual(self._action(
            self.tech, "b", "repair", "INV-SPARES", "pickup:3"), issued)
        self.assertAlmostEqual(state("inventory", "INV-SPARES").quantity,
                               original - .003, places=7)
        with self.assertRaises(PermissionError):
            self._action(self.tech, "c", "repair",
                         "equipment:WATER-PROC-A", "start")
        self.tech.move_to(find_ship_space("HAB-06-ECLSS-A"), quiet=True)
        self._action(self.tech, "d", "repair",
                     "equipment:WATER-PROC-A", "start")
        self.assertEqual(state("equipment", "WATER-PROC-A").condition, "failed")
        tick_continuous_physics(now_game_time=1060)
        remaining = _clock().details["repairs"]["jobs"][
            "equipment:WATER-PROC-A"]["remaining_s"]
        self.assertEqual(remaining, 540)
        self.tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        tick_continuous_physics(now_game_time=1120)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:WATER-PROC-A"]["remaining_s"], 540)
        self.tech.move_to(find_ship_space("HAB-06-ECLSS-A"), quiet=True)
        self._tick(540, start=1120)
        self.assertEqual(state("equipment", "WATER-PROC-A").condition, "serviceable")
        self.assertFalse(_clock().details["repairs"]["jobs"])
        self.assertEqual(_clock().details["repairs"]["completed"], 1)
        self.assertEqual(_clock().details["repairs"]["installed_kg"], 3.0)
        self.assertEqual(_clock().details["water"]["water_train"]["A"], "off")
        self.assertEqual(state("equipment", "WATER-PROC-A").details[
            "repair_cumulative_kg"], 3)


    def test_damaged_access_door_is_repaired_at_actual_safe_endpoint(self):
        self._toolkit()
        door = state("access", "ACC-STORE-FLUID-AFT")
        self.assertIsNone(door.space_id)
        set_component_condition(
            "access", "ACC-STORE-FLUID-AFT", "failed", operator=True)
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=3)
        self.tech.move_to(find_ship_space("STORE-CRIT-SPARES"), quiet=True)
        self._action(self.tech, "9", "repair", "INV-SPARES", "pickup:3")
        self.tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        with self.assertRaises(PermissionError):
            self._action(self.tech, "8", "repair",
                         "access:ACC-STORE-FLUID-AFT", "start")
        self.tech.move_to(find_ship_space("TRUNK-A-AFT"), quiet=True)
        self._action(self.tech, "7", "repair",
                     "access:ACC-STORE-FLUID-AFT", "start")
        self._tick(600)
        repaired = state("access", "ACC-STORE-FLUID-AFT")
        self.assertEqual(repaired.condition, "serviceable")
        self.assertNotEqual(repaired.setting, "open")
        self.assertEqual(_clock().details["repairs"]["completed"], 1)

    def test_incapacitated_worker_cannot_progress_or_issue_repair_work(self):
        self._toolkit()
        self.tech.move_to(find_ship_space("HAB-06-ECLSS-A"), quiet=True)
        self._action(self.tech, "a", "water", "WATER-PROC-A", "off")
        set_component_condition("equipment", "WATER-PROC-A",
                                "failed", operator=True)
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=3)
        self.tech.move_to(find_ship_space("STORE-CRIT-SPARES"), quiet=True)
        self._action(self.tech, "b", "repair", "INV-SPARES", "pickup:3")
        self.tech.move_to(find_ship_space("HAB-06-ECLSS-A"), quiet=True)
        started = self._action(self.tech, "c", "repair",
                               "equipment:WATER-PROC-A", "start")
        health = CanonicalShipState.objects.create(
            key="crew_health:" + str(self.tech.dbref),
            category="crew_health", source_id=str(self.tech.dbref),
            source_model="ox.g19.crew-health", condition="incapacitated")
        with self.assertRaises(CrewTransitError):
            self._action(self.tech, "d", "repair",
                         "equipment:WATER-PROC-A", "join")
        with self.assertRaises(CrewTransitError):
            self._action(self.tech, "e", "wasteport",
                         "IND-SCRAP-HOLD-A", "pause")
        self.assertEqual(self._action(self.tech, "c", "repair",
                                      "equipment:WATER-PROC-A", "start"), started)
        tick_continuous_physics(now_game_time=1060)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:WATER-PROC-A"]["remaining_s"], 600)
        health.condition = "serviceable"
        health.save(update_fields=["condition"])
        tick_continuous_physics(now_game_time=1120)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:WATER-PROC-A"]["remaining_s"], 540)

    def test_failed_generator_needs_isolation_and_never_restarts_after_repair(self):
        self._toolkit()
        self.tech.move_to(find_ship_space("GEN-B-ROOM"), quiet=True)
        self._action(self.tech, "e", "plant", "GEN-B", "off")
        set_isolator("ISO-GEN-B", "open", operator=True)
        set_component_condition("equipment", "GEN-B", "failed", operator=True)
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=4)
        self.tech.move_to(find_ship_space("STORE-CRIT-SPARES"), quiet=True)
        self._action(self.tech, "f", "repair", "INV-SPARES", "pickup:3")
        self.tech.move_to(find_ship_space("GEN-B-ROOM"), quiet=True)
        with self.assertRaises(PhysicsError):
            self._action(self.tech, "1", "repair", "equipment:GEN-B", "start")
        survey_g19_repair_site(
            operator_approved=True, room_id="GEN-B-ROOM",
            work_class="suited_service")
        with self.assertRaises(PhysicsError):
            self._action(self.tech, "2", "repair", "equipment:GEN-B", "start")
        self.tech.db.ox_suit_verified = True
        self._action(self.tech, "3", "repair", "equipment:GEN-B", "start")
        self.tech.db.ox_suit_verified = False
        tick_continuous_physics(now_game_time=1060)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:GEN-B"]["remaining_s"], 600)
        self.tech.db.ox_suit_verified = True
        self._tick(600, start=1060)
        self.assertEqual(state("equipment", "GEN-B").condition, "serviceable")
        self.assertFalse(state("equipment", "GEN-B").details["physics_online"])
        self.assertEqual(state("isolator", "ISO-GEN-B").setting, "open")
        self.assertFalse(state("equipment", "GEN-B").details["physics_commanded_on"])


if __name__ == "__main__":
    import unittest
    unittest.main()
