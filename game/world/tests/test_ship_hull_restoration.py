"""Pure material-backed ship hull restoration tests; no voyage simulation."""
import copy
import math
import unittest

from world.ship_hull_restoration import (
    HullError, initial_hull, validate_hull, register_breach, effective_leak,
    expected_repair_condition, finish_hull_work,
)


class HullRestorationTests(unittest.TestCase):
    def setUp(self):
        self.empty = initial_hull()
        self.open = register_breach(
            self.empty, zone="PZ-HAB-03", site_room="HAB-03-ENTRY",
            leak_kg_s=0.05)

    def test_commissioned_breach_is_finite_and_original_unchanged(self):
        self.assertTrue(validate_hull(self.open))
        self.assertEqual(self.empty, initial_hull())
        self.assertEqual(effective_leak(self.open["breaches"]["PZ-HAB-03"]), 0.05)
        self.assertEqual(expected_repair_condition(self.open, "PZ-HAB-03"), "jammed")

    def test_patch_reduces_leak_without_creating_gas(self):
        patched, rate = finish_hull_work(
            self.open, zone="PZ-HAB-03", condition="jammed", installed_kg=2)
        self.assertAlmostEqual(rate, 0.005)
        self.assertEqual(patched["breaches"]["PZ-HAB-03"]["phase"], "patched")
        self.assertEqual(patched["breaches"]["PZ-HAB-03"]["installed_spares_kg"], 2)
        self.assertEqual(self.open["breaches"]["PZ-HAB-03"]["phase"], "open")

    def test_full_replacement_requires_first_patch_and_four_more_kg(self):
        with self.assertRaises(HullError):
            finish_hull_work(self.open, zone="PZ-HAB-03",
                             condition="severed", installed_kg=4)
        patched, _ = finish_hull_work(
            self.open, zone="PZ-HAB-03", condition="jammed", installed_kg=2)
        restored, rate = finish_hull_work(
            patched, zone="PZ-HAB-03", condition="severed", installed_kg=4)
        self.assertEqual(rate, 0)
        self.assertEqual(expected_repair_condition(restored, "PZ-HAB-03"), None)
        self.assertEqual(restored["patches_completed"], 1)
        self.assertEqual(restored["restorations_completed"], 1)
        self.assertEqual(restored["breaches"]["PZ-HAB-03"]["installed_spares_kg"], 6)

    def test_cannot_double_finish_or_install_wrong_parts(self):
        patched, _ = finish_hull_work(
            self.open, zone="PZ-HAB-03", condition="jammed", installed_kg=2)
        for payload in ((self.open, "jammed", 1), (patched, "jammed", 2),
                        (patched, "severed", 0), (patched, "severed", 5)):
            with self.subTest(payload=payload[1:]):
                with self.assertRaises(HullError):
                    finish_hull_work(payload[0], zone="PZ-HAB-03",
                                     condition=payload[1], installed_kg=payload[2])

    def test_duplicate_zone_or_unknown_room_refused(self):
        with self.assertRaises(HullError):
            register_breach(self.open, zone="PZ-HAB-03", site_room="x", leak_kg_s=1)
        for rate in (0, -1, float("nan"), math.inf, 50, True):
            with self.subTest(rate=rate):
                with self.assertRaises(HullError):
                    register_breach(self.empty, zone="PZ-HAB-03",
                                    site_room="HAB-03-ENTRY", leak_kg_s=rate)

    def test_registry_counters_and_staged_parts_detect_corruption(self):
        damaged = copy.deepcopy(self.open)
        damaged["patches_completed"] = 1
        with self.assertRaises(HullError):
            validate_hull(damaged)
        damaged = copy.deepcopy(self.open)
        damaged["breaches"]["PZ-HAB-03"]["installed_spares_kg"] = 2
        with self.assertRaises(HullError):
            validate_hull(damaged)

    def test_multiple_pressure_cells_keep_independent_state(self):
        both = register_breach(self.open, zone="PZ-BR-03",
                               site_room="BR-03", leak_kg_s=.02)
        patched, _ = finish_hull_work(
            both, zone="PZ-HAB-03", condition="jammed", installed_kg=2)
        self.assertEqual(patched["breaches"]["PZ-BR-03"]["phase"], "open")
        self.assertEqual(patched["patches_completed"], 1)


if __name__ == "__main__":
    unittest.main()
