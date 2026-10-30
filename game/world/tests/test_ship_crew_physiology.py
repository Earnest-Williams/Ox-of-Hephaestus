"""G19 finite crew respiratory and casualty physics; no voyage simulation."""
import copy
import math
import unittest

from world.ship_crew_exposure import initial_exposure
from world.ship_crew_physiology import (
    CrewPhysiologyError, measured_environment,
    step_crew_in_space, validate_crew_health,
)


def gas():
    mass = 118.0
    temp = 294.0
    return {
        "mass": mass, "oxygen": mass * .232, "co2": mass * .0006,
        "smoke": 0.0, "volume": 100., "temperature": temp,
        "capacity": 5000.0, "energy": (5000 + mass * 1.005) * temp,
    }


class CrewRespirationTests(unittest.TestCase):
    def test_real_room_consumes_oxygen_without_making_gas_mass(self):
        old = gas()
        health, next_gas, report = step_crew_in_space(
            initial_exposure(), old, 10)
        self.assertEqual(health["condition"], "fit")
        self.assertGreater(report["o2_used_kg"], 0)
        self.assertEqual(report["o2_used_kg"], report["co2_added_kg"])
        self.assertAlmostEqual(next_gas["oxygen"] + next_gas["co2"],
                               old["oxygen"] + old["co2"], places=10)
        self.assertEqual(next_gas["mass"], old["mass"])
        self.assertGreater(next_gas["temperature"], old["temperature"])
        self.assertEqual(old, gas())
        self.assertGreater(health["water_deficit_kg"], 0)

    def test_two_people_draw_twice_the_same_real_compartment_stock(self):
        before = gas()
        a, sample, first = step_crew_in_space(initial_exposure(), before, 10)
        b, sample, second = step_crew_in_space(initial_exposure(), sample, 10)
        self.assertAlmostEqual(before["oxygen"] - sample["oxygen"],
                               first["o2_used_kg"] + second["o2_used_kg"])
        self.assertAlmostEqual(sample["mass"], before["mass"])
        self.assertTrue(validate_crew_health(a))
        self.assertTrue(validate_crew_health(b))

    def test_vacuum_accumulates_disabling_then_terminal_exposure(self):
        health = initial_exposure()
        for step in range(120):
            health, cell, used = step_crew_in_space(health, None, 10)
            self.assertIsNone(cell)
            self.assertEqual(used["o2_used_kg"], 0)
            if step == 17:
                self.assertEqual(health["condition"], "incapacitated")
        self.assertEqual(health["condition"], "dead")
        before = copy.deepcopy(health)
        health, _, used = step_crew_in_space(health, None, 10)
        self.assertEqual(health, before)
        self.assertEqual(used["o2_used_kg"], 0)

    def test_smoke_and_high_co2_affect_a_real_actor(self):
        bad = gas()
        bad["smoke"] = 1.2
        bad["co2"] = 2.4
        bad["oxygen"] -= 2.0
        result, _, _ = step_crew_in_space(initial_exposure(), bad, 10)
        self.assertGreater(result["smoke_dose"], 0)
        self.assertGreater(result["co2_dose"], 0)

    def test_corrupt_or_unmeasured_envelope_rejected(self):
        for key, value in (("mass", float("nan")), ("oxygen", -2),
                           ("volume", 0), ("temperature", float("inf")),
                           ("smoke", 200)):
            bad = gas()
            bad[key] = value
            with self.subTest(key=key):
                with self.assertRaises(CrewPhysiologyError):
                    step_crew_in_space(initial_exposure(), bad, 10)
        with self.assertRaises(CrewPhysiologyError):
            step_crew_in_space(initial_exposure(), gas(), 11)
        with self.assertRaises(CrewPhysiologyError):
            step_crew_in_space(initial_exposure(), gas(), -1)

    def test_nonbreathable_room_still_conserves_gas(self):
        low = gas()
        low["oxygen"] = .001
        old = copy.deepcopy(low)
        health, after, receipt = step_crew_in_space(initial_exposure(), low, 10)
        self.assertEqual(receipt["o2_used_kg"], 0)
        self.assertEqual(health["hypoxia_s"], 10)
        self.assertEqual(after["oxygen"], old["oxygen"])
        self.assertEqual(after["mass"], old["mass"])


if __name__ == "__main__":
    unittest.main()
