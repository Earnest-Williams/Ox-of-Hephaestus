"""Deterministic G19 crew exposure unit tests; no autonomous voyage."""
import unittest

from world.ship_crew_exposure import (
    ExposureError, initial_exposure, step_exposure, OXYGEN_KG_S,
)

NORMAL = dict(pressure_pa=101325, oxygen_fraction=0.21,
              co2_fraction=0.0004, smoke_density=0, temperature_k=294)
VACUUM = dict(pressure_pa=0, oxygen_fraction=0,
              co2_fraction=0, smoke_density=0, temperature_k=294)


class ExposureTransitionsTests(unittest.TestCase):
    def test_nominal_room_breathing_is_finite(self):
        s, gas = step_exposure(initial_exposure(), NORMAL, 10)
        self.assertEqual(s["condition"], "fit")
        self.assertAlmostEqual(gas["o2_kg"], OXYGEN_KG_S * 10)
        self.assertGreater(gas["co2_kg"], 0)
        self.assertGreater(s["water_deficit_kg"], 0)

    def test_vacuum_exposure_accumulates_until_incapacity(self):
        s = initial_exposure()
        for _ in range(18):
            s, _ = step_exposure(s, VACUUM, 10)
        self.assertEqual(s["condition"], "incapacitated")
        self.assertEqual(s["hypoxia_s"], 180)

    def test_finite_suit_supply_and_bounded_co2(self):
        s = initial_exposure()
        s["suit_oxygen_kg"] = 0.0002
        for _ in range(2):
            s, used = step_exposure(s, VACUUM, 10, suited=True, suit_integrity=1)
            self.assertAlmostEqual(used["o2_kg"], 0.0001)
        self.assertAlmostEqual(s["suit_oxygen_kg"], 0)
        s, used = step_exposure(s, VACUUM, 10, suited=True, suit_integrity=1)
        self.assertEqual(used["o2_kg"], 0)
        self.assertEqual(s["hypoxia_s"], 10)

    def test_suit_integrity_and_environment_fail_closed(self):
        with self.assertRaises(ExposureError):
            step_exposure(initial_exposure(), VACUUM, 10, suited=True)
        with self.assertRaises(ExposureError):
            step_exposure(initial_exposure(), {}, 10)
        with self.assertRaises(ExposureError):
            step_exposure(initial_exposure(), NORMAL, 11)
        with self.assertRaises(ExposureError):
            step_exposure(initial_exposure(), NORMAL, float("nan"))

    def test_unsafe_co2_and_smoke_incur_persistent_dose(self):
        bad = dict(NORMAL, co2_fraction=0.02, smoke_density=1)
        s = initial_exposure()
        for _ in range(8):
            s, _ = step_exposure(s, bad, 10)
        self.assertGreater(s["smoke_dose"], 30)
        self.assertGreater(s["co2_dose"], 1)
        self.assertGreater(s["injury"], 0)

    def test_recovery_breathing_does_not_erase_injury(self):
        s = initial_exposure()
        s["hypoxia_s"] = 50
        s["injury"] = 0.2
        s, _ = step_exposure(s, NORMAL, 10)
        self.assertEqual(s["hypoxia_s"], 47.5)
        self.assertEqual(s["injury"], 0.2)

    def test_dead_crew_do_not_metabolise(self):
        s = initial_exposure()
        s["condition"] = "dead"
        s, gas = step_exposure(s, NORMAL, 10)
        self.assertEqual(gas["o2_kg"], 0)
        self.assertEqual(s["condition"], "dead")


if __name__ == "__main__":
    unittest.main()
