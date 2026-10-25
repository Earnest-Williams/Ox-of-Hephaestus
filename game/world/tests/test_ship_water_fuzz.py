"""Seeded G19 water-system fault campaign: conservation across mixed conditions."""
import copy
import math
import random
import unittest

from world.ship_water_recycling import (
    WaterError, DAY, initial_water, step_water, validate_water,
    water_inventory_total,
)
from world.tests.test_ship_water_recycling import healthy, stock


class WaterFaultFuzzTests(unittest.TestCase):
    def test_seeded_variable_clock_and_casualty_matrix(self):
        for seed in (101, 619, 1009, 2026, 41031, 999999):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                w, s = initial_water(), stock()
                s["filter"] = 8000.0
                # Start with a genuinely installed finite cartridge instead
                # of drawing chemicals from an arbitrary remote store.
                w["filter_staged_kg"]["A"] = 1.0
                s["filter"] -= 1.0
                initial_mass = water_inventory_total(w, s)
                elapsed = 0.0
                # Random simultaneous power, waste-cassette isolation,
                # one/both processors and exhausted/blocked rotary unions.
                # The source stock, all cassettes and any exposed process loss
                # have no non-physical negative values at any intermediate step.
                for iteration in range(400):
                    h = healthy()
                    h["potable"] = rng.random() < .85
                    h["process"] = {
                        side: rng.random() < .65 for side in "AB"
                    }
                    h["fixed"] = {
                        medium: rng.random() < .7
                        for medium in ("grey", "black")
                    }
                    h["oxygen"] = rng.random() < .65
                    for category in h["bins"]:
                        for side in "AB":
                            h["bins"][category][side] = rng.random() < .92
                    # Contamination is a quality state, not generated mass.
                    if iteration == 5:
                        w["potable_quarantined"] = True
                        w["suspected_contamination_kg"] = min(
                            1.5, w["working_kg"])
                        w["decontaminate"]["A"] = True
                        w["decontaminate"]["B"] = True
                    if w["potable_quarantined"] and w["suspected_contamination_kg"] == 0:
                        w["potable_quarantined"] = False
                    dt = rng.choice((0, 1, 2.5, 10, 30, 59, 60))
                    crew = rng.randint(0, 40)
                    before_w, before_s = copy.deepcopy(w), dict(s)
                    next_w, next_s, report = step_water(
                        w, dt, stocks=s, hardware=h, crew_count=crew)
                    # Pure deterministic results independent of duplicate
                    # evaluation before world-clock commit.
                    check_w, check_s, check_report = step_water(
                        before_w, dt, stocks=before_s, hardware=h,
                        crew_count=crew)
                    self.assertEqual((next_w, next_s, report),
                                     (check_w, check_s, check_report))
                    w, s = next_w, next_s
                    elapsed += dt
                    validate_water(w, s)
                    total = water_inventory_total(w, s)
                    expected = (initial_mass -
                                w["cumulative"]["reject_kg"] -
                                w["cumulative"]["technical_kg"])
                    self.assertAlmostEqual(total, expected, delta=.003)
                    for key in ("normal", "reserve", "sanitary",
                                "industrial", "hazardous", "filter"):
                        self.assertTrue(math.isfinite(s[key]))
                        self.assertGreaterEqual(s[key], -1e-7)
                    self.assertEqual(s["reserve"], 70000.0)
                self.assertGreater(elapsed, 0.0)
                self.assertGreaterEqual(
                    w["cumulative"]["domestic_unserved_kg"], 0.0)

    def test_randomised_corruption_fail_closed(self):
        rng = random.Random(3112)
        for _ in range(100):
            w, s = initial_water(), stock()
            field = rng.choice(("working_kg", "local", "fixed",
                                "cassettes", "cumulative"))
            if field == "working_kg":
                w[field] = rng.choice((float("inf"), float("nan"), -5))
            elif field == "local":
                w[field][rng.choice("AB")]["grey"] = 100000
            elif field == "fixed":
                w[field]["black"] = float("-inf")
            elif field == "cassettes":
                w[field]["hazardous"]["A"] = 4000
            else:
                w[field]["domestic_used_kg"] = -100
            with self.assertRaises(WaterError):
                step_water(w, 60, stocks=s, hardware=healthy())


if __name__ == "__main__":
    unittest.main()
