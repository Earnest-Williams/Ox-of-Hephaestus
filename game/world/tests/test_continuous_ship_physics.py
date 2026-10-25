"""Database-backed G18 physical coupling and authority regression."""
from __future__ import annotations

from django.db import transaction
from evennia.utils.test_resources import EvenniaTestCase

from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, configure_scenario_casualty,
    crew_physical_action, local_physics_readout, tick_continuous_physics,
)
from world.full_ship_operations import (
    ShipOperationsError, install_candidate, install_pressure_cells,
    initialize_nominal_atmosphere, state, set_component_condition,
    set_isolator, vent_pressure_cell, equalize_cells,
)
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_world import build_canonical_ship, find_ship_space
from world.bootstrap import build_ship


class PhysicsRuntimeTests(EvenniaTestCase):

    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)

    def test_clock_bounded_replay_and_restart_catchup(self):
        self.assertFalse(tick_continuous_physics(now_game_time=1000)["advanced"])
        result = tick_continuous_physics(now_game_time=1200)
        self.assertTrue(result["advanced"])
        self.assertEqual(result["last_game_time"], 1060)
        self.assertEqual(tick_continuous_physics(now_game_time=1200)["last_game_time"], 1120)
        self.assertFalse(arm_continuous_physics(operator_approved=True)["armed"])
        with self.assertRaises(PhysicsError):
            tick_continuous_physics(now_game_time=900)

    def test_finite_leak_and_nonduplication(self):
        a = state("pressure", "PZ-HAB-03")
        before = a.quantity
        configure_scenario_casualty("PZ-HAB-03", leak_kg_s=0.1, operator=True)
        result = tick_continuous_physics(now_game_time=1010)
        self.assertAlmostEqual(state("pressure", "PZ-HAB-03").quantity,
                               before - 1, delta=0.1)
        again = tick_continuous_physics(now_game_time=1010)
        self.assertFalse(again["advanced"])
        self.assertEqual(CanonicalShipState.objects.get(pk="meta:installation").condition,
                         "installed")
        with self.assertRaises(ShipOperationsError):
            vent_pressure_cell("PZ-HAB-03", 1.0, operator=True)
        with self.assertRaises(ShipOperationsError):
            equalize_cells("PZ-HAB-03", "PZ-BR-03", operator=True)

    def test_fire_thermal_and_finite_water(self):
        before = state("inventory", "INV-WATER-NORMAL").quantity
        configure_scenario_casualty(
            "PZ-HAB-03", fire_fuel_kg=3, fire_burn_kg_s=0.1, operator=True)
        result = tick_continuous_physics(now_game_time=1010)
        cell = state("pressure", "PZ-HAB-03")
        self.assertLess(cell.details["physics_fuel_kg"], 3)
        self.assertGreater(cell.details["physics_smoke_kg"], 0)
        self.assertGreater(cell.details["temperature_k"], 293.15)
        self.assertAlmostEqual(result["fuel_kg"] + result["gas_kg"],
                               sum(c.quantity + c.details["physics_fuel_kg"]
                                   for c in CanonicalShipState.objects.filter(category="pressure")),
                               places=4)
        self.assertEqual(state("inventory", "INV-WATER-NORMAL").quantity, before)

    def test_power_requires_selected_dispatch_and_real_feeder(self):
        # GEN-M is not dispatchable merely because 'on' in the registry.
        set_component_condition("edge", "EDGE-GEN-M", "severed", operator=True)
        result = tick_continuous_physics(now_game_time=1010)
        self.assertLessEqual(result["available_mw"], 0.65)
        self.assertFalse(result["power_assured"])

    def test_local_operator_authority_and_request_replay(self):
        crew = build_ship()
        watch, officer = crew["watch"], crew["officer"]
        watch.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        with self.assertRaises(PermissionError):
            crew_physical_action(watch, "1" * 32, "plant", "GEN-M", "off")
        gen = state("equipment", "GEN-M")
        watch.move_to(find_ship_space(gen.space_id), quiet=True)
        before_events = CanonicalShipEvent.objects.count()
        receipt = crew_physical_action(watch, "1" * 32, "plant", "GEN-M", "off")
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(
            crew_physical_action(watch, "1" * 32, "plant", "GEN-M", "off"),
            receipt,
        )
        self.assertEqual(CanonicalShipEvent.objects.count(), before_events + 1)
        self.assertEqual(WorkReceipt.objects.get(pk="1" * 32).outcome, receipt)
        # A legacy receipt reserves the same global request-ID namespace.
        WorkReceipt.objects.create(
            request_id="2" * 32, actor_dbref=watch.dbref, target="ship",
            operation="radio", arguments={}, outcome={"status": "succeeded"},
            game_time=1000,
        )
        with self.assertRaises(PermissionError):
            crew_physical_action(watch, "2" * 32, "plant", "GEN-M", "off")
        with self.assertRaises(PermissionError):
            crew_physical_action(watch, "1" * 32, "plant", "GEN-M", "on")
        with self.assertRaises(PermissionError):
            crew_physical_action(officer, "1" * 32, "plant", "GEN-M", "off")
        self.assertFalse(state("equipment", "GEN-M").details["physics_online"])
        self.assertEqual(local_physics_readout(watch, "GEN-M")["online"], False)
        watch.db.ox_terminal_dead = True
        with self.assertRaises(PermissionError):
            crew_physical_action(watch, "3" * 32, "plant", "GEN-M", "on")

    def test_generator_connected_feeder_is_required_for_assured_power(self):
        # The G17 candidate's main feeder is normally open; a healthy
        # generator cannot energise a board until its real breaker closes.
        set_isolator("ISO-GEN-M", "closed", operator=True)
        ready = tick_continuous_physics(now_game_time=1010)
        self.assertGreaterEqual(ready["available_mw"], 3.0)
        self.assertTrue(ready["power_assured"])
        set_component_condition("edge", "EDGE-GEN-M", "severed", operator=True)
        failed = tick_continuous_physics(now_game_time=1020)
        self.assertLessEqual(failed["available_mw"], 0.65)
        self.assertFalse(failed["power_assured"])

    def test_rollbacks_preserve_gas_and_receipts(self):
        before = state("pressure", "PZ-HAB-03").quantity
        count = CanonicalShipEvent.objects.count()
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                configure_scenario_casualty("PZ-HAB-03", leak_kg_s=2, operator=True)
                tick_continuous_physics(now_game_time=1010)
                raise RuntimeError("force rollback")
        self.assertEqual(state("pressure", "PZ-HAB-03").quantity, before)
        self.assertEqual(CanonicalShipEvent.objects.count(), count)

    def test_invalid_faults_fail_closed(self):
        with self.assertRaises(PermissionError):
            configure_scenario_casualty("PZ-HAB-03", leak_kg_s=10)
        with self.assertRaises(PhysicsError):
            configure_scenario_casualty("PZ-HAB-03", leak_kg_s=float("nan"), operator=True)
        with self.assertRaises(PhysicsError):
            configure_scenario_casualty("PZ-HAB-03", fire_fuel_kg=2, operator=True)
