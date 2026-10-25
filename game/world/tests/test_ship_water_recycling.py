"""Water and solid-waste conservation, isolation and 730-day endurance."""
import copy
import math
import unittest

from world.ship_water_recycling import (
    WaterError, initial_water, step_water, transfer_discard, validate_water,
    water_inventory_total, DAY,
)


def stock():
    return {
        "normal": 162000.0, "reserve": 70000.0,
        "sanitary": 0.0, "industrial": 0.0, "hazardous": 0.0,
    }


def healthy():
    return {
        "potable": True,
        "process": {"A": True, "B": True},
        "fixed": {"grey": True, "black": True},
        "oxygen": True,
        "bins": {
            "sanitary": {"A": True, "B": True},
            "industrial": {"A": True, "B": True},
            "hazardous": {"A": True, "B": True},
        },
    }


class WaterLedgerTests(unittest.TestCase):
    def test_two_year_endurance_matches_selected_domestic_budget(self):
        w, s = initial_water(), stock()
        initial = water_inventory_total(w, s)
        for day in range(730):
            w, s, r = step_water(w, DAY, stocks=s, hardware=healthy())
            if day in (0, 364, 729):
                validate_water(w, s)
                self.assertGreaterEqual(r["domestic_kg"], 999.999)
        self.assertAlmostEqual(w["cumulative"]["domestic_used_kg"], 730000, places=3)
        self.assertAlmostEqual(w["cumulative"]["water_recovered_kg"], 657000, places=3)
        self.assertAlmostEqual(w["cumulative"]["sanitary_solids_kg"], 7300, places=3)
        self.assertAlmostEqual(s["sanitary"], 7300, places=3)
        self.assertAlmostEqual(w["cumulative"]["reject_kg"], 65700, places=3)
        self.assertAlmostEqual(s["reserve"], 70000, places=5)
        self.assertGreaterEqual(s["normal"], -1e-5)
        self.assertLess(s["normal"], 200)
        self.assertAlmostEqual(
            initial,
            water_inventory_total(w, s) + w["cumulative"]["reject_kg"]
            + w["cumulative"]["technical_kg"],
            delta=0.005,
        )

    def test_processor_failure_stores_dirty_water_then_forces_rationing(self):
        w, s, h = initial_water(), stock(), healthy()
        h["process"] = {"A": False, "B": False}
        h["fixed"] = {"grey": False, "black": False}
        w, s, first = step_water(w, DAY, stocks=s, hardware=h)
        self.assertGreater(first["domestic_kg"], 0)
        self.assertEqual(first["processed_kg"], 0)
        w, s, second = step_water(w, DAY, stocks=s, hardware=h)
        self.assertGreater(second["unserved_kg"], 0)
        self.assertEqual(second["processed_kg"], 0)
        self.assertLessEqual(sum(w["local"][side]["grey"] for side in "AB"), 1000)
        self.assertEqual(w["fixed"]["black"], 0)
        validate_water(w, s)

    def test_single_train_can_carry_all_forty_with_no_shared_infinite_plant(self):
        w, s, h = initial_water(), stock(), healthy()
        h["process"]["A"] = False
        w, s, r = step_water(w, DAY, stocks=s, hardware=h)
        self.assertAlmostEqual(r["domestic_kg"], 1000)
        self.assertAlmostEqual(r["processed_kg"], 1000)
        self.assertAlmostEqual(s["sanitary"], 10)
        validate_water(w, s)

    def test_dual_rotary_outage_stops_offloading_to_fixed_holding(self):
        w, s, h = initial_water(), stock(), healthy()
        h["process"] = {"A": False, "B": False}
        h["fixed"] = {"grey": True, "black": True}
        for _ in range(5):
            w, s, _ = step_water(w, DAY, stocks=s, hardware=h)
        self.assertGreater(w["fixed"]["grey"], 0)
        before_fixed = dict(w["fixed"])
        h["fixed"] = {"grey": False, "black": False}
        w, s, r = step_water(w, DAY, stocks=s, hardware=h)
        self.assertGreater(r["unserved_kg"], 0)
        self.assertEqual(w["fixed"], before_fixed)
        validate_water(w, s)

    def test_full_sanitary_receivers_bar_recycling_without_overflow(self):
        w, s, h = initial_water(), stock(), healthy()
        w["cassettes"]["sanitary"] = {"A": 8000, "B": 8000}
        s["sanitary"] = 16000
        w, s, r = step_water(w, DAY, stocks=s, hardware=h)
        self.assertEqual(r["processed_kg"], 0)
        for _ in range(15):
            w, s, _ = step_water(w, DAY, stocks=s, hardware=h)
        self.assertLessEqual(s["sanitary"], 16000)
        self.assertGreater(w["cumulative"]["domestic_unserved_kg"], 0)
        validate_water(w, s)

    def test_reserve_requires_explicit_command_and_real_tank_headroom(self):
        w, s, h = initial_water(), stock(), healthy()
        w["working_kg"] = 100
        s["normal"] = 0
        w, s, _ = step_water(w, DAY, stocks=s, hardware=h, crew_count=0)
        self.assertEqual(s["reserve"], 70000)
        w["reserve_released"] = True
        w, s, r = step_water(w, DAY, stocks=s, hardware=h, crew_count=0)
        self.assertGreater(r["makeup_kg"], 0)
        self.assertLess(s["reserve"], 70000)
        validate_water(w, s)

    def test_emergency_reserve_cannot_feed_routine_crops_or_servicing(self):
        w, s, h = initial_water(), stock(), healthy()
        w["working_kg"] = 100.0
        s["normal"] = 0.0
        w["reserve_released"] = True
        w, s, report = step_water(w, DAY, stocks=s, hardware=h)
        self.assertGreater(report["domestic_kg"], 0)
        self.assertGreater(report["oxygen_kg"], 0)
        self.assertGreater(report["makeup_kg"], 0)
        self.assertLess(s["reserve"], 70000.0)
        restricted = (35000.0 + 21924.0) / 730.0
        self.assertAlmostEqual(
            report["rationed_nonessential_kg"], restricted, places=5)
        self.assertAlmostEqual(
            w["cumulative"]["rationed_nonessential_kg"], restricted, places=5)
        self.assertLess(report["technical_kg"], 45.0)
        self.assertGreaterEqual(
            w["cumulative"]["technical_unserved_kg"], restricted)
        validate_water(w, s)
        # With no explicit reserve release, even this essential draw stops.
        blocked = initial_water()
        blocked["working_kg"] = 0.0
        normal_empty = stock()
        normal_empty["normal"] = 0.0
        result, balances, report = step_water(
            blocked, DAY, stocks=normal_empty, hardware=h)
        self.assertEqual(report["makeup_kg"], 0.0)
        self.assertEqual(balances["reserve"], 70000.0)

    def test_contamination_and_blackout_cannot_manufacture_potable_water(self):
        w, s, h = initial_water(), stock(), healthy()
        before = water_inventory_total(w, s)
        w["potable_quarantined"] = True
        w, s, r = step_water(w, DAY, stocks=s, hardware=h)
        self.assertEqual(r["domestic_kg"], 0)
        self.assertEqual(r["makeup_kg"], 0)
        h["potable"] = False
        w, s, r = step_water(w, DAY, stocks=s, hardware=h)
        self.assertEqual(r["domestic_kg"], 0)
        self.assertAlmostEqual(
            before, water_inventory_total(w, s)
            + w["cumulative"]["reject_kg"] + w["cumulative"]["technical_kg"],
            delta=.001,
        )

    def test_segregated_disposal_debits_verified_existing_source(self):
        w, s, h = initial_water(), stock(), healthy()
        s["spares"] = 25000
        w, s = transfer_discard(w, s, category="industrial",
                                source="spares", kg=1000, hardware=h)
        self.assertEqual(s["spares"], 24000)
        self.assertEqual(s["industrial"], 1000)
        self.assertEqual(sum(w["cassettes"]["industrial"].values()), 1000)
        with self.assertRaises(WaterError):
            transfer_discard(w, s, category="hazardous",
                             source="spares", kg=25000, hardware=h)
        with self.assertRaises(WaterError):
            transfer_discard(w, s, category="sanitary",
                             source="spares", kg=1, hardware=h)
        self.assertEqual(s["spares"], 24000)

    def test_waste_stock_mismatch_and_corrupt_values_fail_closed(self):
        w, s = initial_water(), stock()
        w["cassettes"]["sanitary"]["A"] = 5
        with self.assertRaises(WaterError):
            validate_water(w, s)
        w, s = initial_water(), stock()
        w["working_kg"] = float("nan")
        with self.assertRaises(WaterError):
            step_water(w, 10, stocks=s, hardware=healthy())
        with self.assertRaises(WaterError):
            step_water(initial_water(), DAY * 2,
                       stocks=stock(), hardware=healthy())


if __name__ == "__main__":
    unittest.main()
