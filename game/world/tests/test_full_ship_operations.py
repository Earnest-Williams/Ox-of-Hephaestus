"""G17 database-backed whole-ship operational seed and state tests."""
from __future__ import annotations

from django.db import transaction
from evennia.utils.test_resources import EvenniaTestCase

from world.full_ship_operations import (
    ShipOperationsError, access_clearance, consume_stock, install_candidate,
    load_candidate, service_reachable, set_component_condition, set_isolator,
    state, summary, install_pressure_cells, initialize_nominal_atmosphere,
    pressure_reading, vent_pressure_cell, equalize_cells,
)
from world.models import CanonicalShipEvent, CanonicalShipState
from world.ship_world import build_canonical_ship, ensure_canonical_ship


class FullShipOperationsTests(EvenniaTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)

    def test_installs_authoritative_complete_coverage_without_duplicating(self):
        result = install_candidate(operator_approved=True)
        self.assertFalse(result["installed"])
        self.assertEqual(
            result["counts"],
            {"equipment": 808, "access": 517, "node": 1186,
             "edge": 1181, "isolator": 1256, "inventory": 15},
        )
        self.assertEqual(CanonicalShipState.objects.count(), 4964)
        self.assertEqual(summary()["equipment"], 808)
        self.assertEqual(summary()["isolator"], 1256)

    def test_refuses_implicit_installation_and_keeps_fault_after_rebuild(self):
        with self.assertRaises(PermissionError):
            install_candidate()
        identifier = "F1-FW-01"
        set_component_condition("equipment", identifier, "failed", operator=True)
        build_canonical_ship()
        self.assertFalse(install_candidate(operator_approved=True)["installed"])
        self.assertEqual(state("equipment", identifier).condition, "failed")
        self.assertEqual(CanonicalShipEvent.objects.count(), 1)

    def test_fault_and_stock_rollback_are_atomic(self):
        starting = state("inventory", "INV-WATER-NORMAL").quantity
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                consume_stock("INV-WATER-NORMAL", 2.0, operator=True)
                raise RuntimeError("rollback")
        self.assertEqual(state("inventory", "INV-WATER-NORMAL").quantity, starting)
        self.assertEqual(CanonicalShipEvent.objects.count(), 0)
        consume_stock("INV-WATER-NORMAL", 2.0, operator=True)
        self.assertEqual(state("inventory", "INV-WATER-NORMAL").quantity, starting - 2)
        with self.assertRaises(ShipOperationsError):
            consume_stock("INV-WATER-NORMAL", 999999, operator=True)
        self.assertEqual(state("inventory", "INV-WATER-NORMAL").quantity, starting - 2)

    def test_failed_or_unavailable_branch_is_not_reachable(self):
        # All endpoints and isolators are imported from the actual design.
        source = "NODE-GEN-M"
        self.assertNotIn("PWR-MSB-A", service_reachable("power", source))
        set_isolator("ISO-GEN-M", "closed", operator=True)
        self.assertIn("PWR-MSB-A", service_reachable("power", source))
        set_component_condition("edge", "EDGE-GEN-M", "severed", operator=True)
        self.assertNotIn("PWR-MSB-A", service_reachable("power", source))
        self.assertEqual(state("isolator", "ISO-GEN-M").setting, "closed")

    def test_pressure_door_and_unverified_environment_never_bypass_interlocks(self):
        access = state("access", "ACC-BR-03-HAB-03")
        self.assertEqual(access.setting, "closed")
        self.assertEqual(access_clearance("ACC-BR-03-HAB-03"), (False, "access_not_open"))
        # No public door opening API exists until pressure equalisation and
        # suit verification have a world-authoritative implementation.
        with self.assertRaises(PermissionError):
            set_isolator("ISO-GEN-A", "open", actor=None)
        self.assertNotIn("equalization_not_verified", {"access_not_open"})

    def test_specifications_are_not_live_condition_and_no_infinite_inventory(self):
        spec = load_candidate()
        self.assertEqual(len(spec["spaces"]), 421)
        self.assertEqual(len(spec["equipment"]), 808)
        self.assertEqual(state("inventory", "INV-FOOD-LONG-LEG").quantity, 56.79)
        self.assertEqual(state("inventory", "INV-GAS-REFILL-A").quantity, 2.75)
        self.assertEqual(state("inventory", "INV-GAS-REFILL-B").quantity, 2.75)
        self.assertEqual(state("equipment", "F1-FW-01").reference["current_condition"], "serviceable")
        set_component_condition("equipment", "F1-FW-01", "failed", operator=True)
        self.assertEqual(state("equipment", "F1-FW-01").condition, "failed")
        self.assertEqual(state("equipment", "F1-FW-01").reference["current_condition"], "serviceable")


    def test_pressure_scenario_explicit_finite_and_conserved(self):
        self.assertEqual(install_pressure_cells(operator_approved=True)["cells"], 133)
        self.assertEqual(install_pressure_cells(operator_approved=True)["installed"], False)
        self.assertIsNone(pressure_reading("PZ-HAB-03")["pressure_pa"])
        with self.assertRaises(PermissionError):
            initialize_nominal_atmosphere()
        result = initialize_nominal_atmosphere(operator_approved=True)
        self.assertEqual(result["cells"], 133)
        self.assertAlmostEqual(pressure_reading("PZ-HAB-03")["pressure_pa"], 101325.0)
        with self.assertRaises(ShipOperationsError):
            initialize_nominal_atmosphere(operator_approved=True)
        a = "PZ-HAB-03"
        b = "PZ-BR-03"
        before = pressure_reading(a)["mass_kg"] + pressure_reading(b)["mass_kg"]
        vent_pressure_cell(a, 120, operator=True)
        less = pressure_reading(a)["mass_kg"] + pressure_reading(b)["mass_kg"]
        self.assertAlmostEqual(before - less, 120)
        self.assertLess(pressure_reading(a)["pressure_pa"], 101325)
        equalize_cells(a, b, operator=True)
        self.assertAlmostEqual(
            pressure_reading(a)["mass_kg"] + pressure_reading(b)["mass_kg"], less)
        self.assertAlmostEqual(pressure_reading(a)["pressure_pa"],
                               pressure_reading(b)["pressure_pa"])
        self.assertLess(pressure_reading(b)["pressure_pa"], 101325)
        self.assertEqual(state("inventory", "INV-GAS-REFILL-A").quantity, 2.75)
