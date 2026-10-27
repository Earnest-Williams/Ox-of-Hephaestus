"""Installed-world G19 electrical operation and casualty tests (no voyage)."""
from __future__ import annotations

from django.db import transaction
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    state, set_component_condition, set_isolator,
)
from world.ship_world import build_canonical_ship, find_ship_space
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_electrical,
    survey_g19_electrical_source, configure_g19_electrical_fault,
    crew_physical_action, tick_continuous_physics, local_physics_readout,
)


class InstalledElectricalTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.worker = build_ship()["watch"]

    def crew_at(self, room):
        location = find_ship_space(room)
        self.assertIsNotNone(location, room)
        self.worker.move_to(location, quiet=True)

    def test_full_authored_graph_and_nonresetting_commission(self):
        result = commission_g19_electrical(operator_approved=True)
        self.assertEqual((result["nodes"], result["feeders"], result["breakers"]),
                         (438, 450, 466))
        self.assertEqual(result["rated_battery_kwh"], 0)
        self.assertFalse(commission_g19_electrical(operator_approved=True)["commissioned"])
        tick = tick_continuous_physics(now_game_time=1010)
        self.assertIn("electrical", tick)
        self.assertGreater(tick["electrical"]["meter"]["served_kwh"], 0)
        self.assertEqual(tick["electrical"]["meter"]["battery_discharge_kwh"], 0)
        self.assertEqual(tick["electrical"]["meter"]["shore_import_kwh"], 0)

    def test_generator_feeder_failure_browns_out_normal_work(self):
        commission_g19_electrical(operator_approved=True)
        set_component_condition("edge", "EDGE-GEN-M", "severed", operator=True)
        tick = tick_continuous_physics(now_game_time=1010)
        self.assertLessEqual(tick["available_mw"], 0.65)
        self.assertFalse(tick["power_assured"])
        self.assertGreater(tick["electrical"]["meter"]["unserved_kwh"], 0)
        self.assertFalse(tick_continuous_physics(now_game_time=1010)["advanced"])

    def test_real_breaker_overload_trips_and_requires_reset(self):
        commission_g19_electrical(operator_approved=True)
        breaker = state("isolator", "ISO-GEN-M")
        self.assertEqual(breaker.reference["network"], "power")
        if breaker.setting != "closed":
            set_isolator("ISO-GEN-M", "closed", operator=True)
        configure_g19_electrical_fault(
            operator_approved=True, breaker_id="ISO-GEN-M",
            rating_mw=1.0, measured_mw=2.0)
        tick = tick_continuous_physics(now_game_time=1010)
        opened = state("isolator", "ISO-GEN-M")
        self.assertEqual(opened.setting, "open")
        self.assertTrue(opened.details["physics_power_trip_latched"])
        self.assertLessEqual(tick["available_mw"], .65)
        self.crew_at(opened.space_id)
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "9" * 32, "switch", "ISO-GEN-M", "closed")
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "8" * 32, "power", "ISO-GEN-M", "reset")
        configure_g19_electrical_fault(
            operator_approved=True, breaker_id="ISO-GEN-M",
            rating_mw=1.0, measured_mw=0)
        result = crew_physical_action(
            self.worker, "7" * 32, "power", "ISO-GEN-M", "reset")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(
            crew_physical_action(self.worker, "7" * 32,
                                 "power", "ISO-GEN-M", "reset"), result)
        self.assertIsNone(state("isolator", "ISO-GEN-M").details.get(
            "physics_power_trip_latched"))
        self.assertEqual(WorkReceipt.objects.get(pk="7" * 32).operation, "power")
        # Reset releases the latch; it NEVER recloses the actual contacts.
        self.assertEqual(state("isolator", "ISO-GEN-M").setting, "open")

    def test_meter_advances_once_only_and_persists_exactly(self):
        commission_g19_electrical(operator_approved=True)
        first = tick_continuous_physics(now_game_time=1010)
        energy = first["electrical"]["meter"]
        self.assertFalse(tick_continuous_physics(now_game_time=1010)["advanced"])
        self.assertEqual(state("meta", "continuous-physics").details["electrical"]["meter"],
                         energy)
        second = tick_continuous_physics(now_game_time=1020)
        self.assertGreater(second["electrical"]["meter"]["served_kwh"],
                           energy["served_kwh"])

    def test_operator_cannot_invent_a_battery_or_unapproved_source(self):
        commission_g19_electrical(operator_approved=True)
        with self.assertRaises(PermissionError):
            survey_g19_electrical_source(
                source="BAT-COMMON-PROT", capacity_kwh=3, initial_kwh=2,
                max_charge_mw=.3, max_discharge_mw=.3)
        with self.assertRaises(PhysicsError):
            survey_g19_electrical_source(
                operator_approved=True, source="BAT-UNAUTHORISED",
                capacity_kwh=3, initial_kwh=2,
                max_charge_mw=.3, max_discharge_mw=.3)

    def test_generator_trips_do_not_destroy_real_refit_buses(self):
        commission_g19_electrical(operator_approved=True)
        node_ids = {r.source_id for r in
                    CanonicalShipState.objects.filter(category="node",
                        reference__network="power")}
        self.assertIn("NODE-PWR-HAB-03-CAB-07-FANCOIL", node_ids)
        self.assertIn("NODE-HAB-03-CAB-07-LP", node_ids)
        self.assertIn("PWR-MSB-A", node_ids)
        self.assertIn("PWR-MSB-B", node_ids)
        self.assertIn("PWR-PROT", node_ids)
        self.assertEqual(CanonicalShipState.objects.filter(
            category="edge", reference__network="power").count(), 450)


if __name__ == "__main__":
    import unittest
    unittest.main()
