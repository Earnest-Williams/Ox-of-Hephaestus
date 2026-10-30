"""G19 real workshop spindle/press output and coasting safety tests."""
import copy
import random
import unittest

from world.ship_workshop_dynamics import (
    WORKSHOP_DRIVES, GAUGE_FIELD, WorkshopGaugeError,
    gauge_valid, step_workshop_gauge, machine_output_confirmed,
    machine_safely_stopped,
)


class WorkshopDynamicsTests(unittest.TestCase):
    def test_exact_original_six_shop_drives_no_invented_welding_arc(self):
        self.assertEqual(set(WORKSHOP_DRIVES), {
            "SHOP-CNC-LATHE", "SHOP-CNC-MILL", "SHOP-MANUAL-LATHE",
            "SHOP-GRINDER", "SHOP-BALANCER", "SHOP-PRESS",
        })
        self.assertNotIn("WELD-CELL-A", WORKSHOP_DRIVES)
        self.assertFalse(machine_output_confirmed(
            "WELD-CELL-A", {"physics_online": True,
                             "physics_commanded_on": True},
            observed_s=10, operating=True))

    def test_all_six_drives_have_positive_real_output_and_inertia(self):
        for name in sorted(WORKSHOP_DRIVES):
            with self.subTest(name=name):
                first = step_workshop_gauge(
                    name, None, dt_s=10, now_s=1010, driven=True)
                second = step_workshop_gauge(
                    name, first, dt_s=10, now_s=1020, driven=True)
                self.assertTrue(gauge_valid(name, second))
                self.assertGreater(second["value"], 0)
                self.assertGreater(second["cumulative_output"], first["cumulative_output"])
                self.assertEqual(second["driven_s"], 20)
                details = {
                    "physics_commanded_on": True, "physics_online": True,
                    "physics_startup_s": 0, GAUGE_FIELD: second,
                }
                self.assertTrue(machine_output_confirmed(
                    name, details, observed_s=1020, operating=True))
                self.assertFalse(machine_output_confirmed(
                    name, details, observed_s=1030, operating=True))
                self.assertFalse(machine_output_confirmed(
                    name, details, observed_s=1020, operating=False))
                self.assertFalse(machine_output_confirmed(
                    name, {**details, "physics_online": False},
                    observed_s=1020, operating=True))
                coasting = step_workshop_gauge(
                    name, second, dt_s=10, now_s=1030, driven=False)
                self.assertLess(coasting["value"], second["value"])
                self.assertEqual(coasting["driven_s"], second["driven_s"])
                self.assertFalse(machine_output_confirmed(
                    name, {**details, GAUGE_FIELD: coasting},
                    observed_s=1030, operating=False))
                if coasting["value"]:
                    self.assertFalse(machine_safely_stopped(
                        name, {GAUGE_FIELD: coasting}))
                latest = coasting
                for time in range(1040, 1201, 10):
                    latest = step_workshop_gauge(
                        name, latest, dt_s=10, now_s=time, driven=False)
                self.assertEqual(latest["value"], 0)
                self.assertTrue(machine_safely_stopped(
                    name, {GAUGE_FIELD: latest}))

    def test_tamper_duplicate_and_impossible_instant_output_refused(self):
        g = step_workshop_gauge(
            "SHOP-CNC-MILL", None, dt_s=10, now_s=10, driven=True)
        for t in (-5, 0, 10, float("nan"), float("inf")):
            with self.assertRaises(WorkshopGaugeError):
                step_workshop_gauge("SHOP-CNC-MILL", g, dt_s=10,
                                    now_s=t, driven=True)
        with self.assertRaises(WorkshopGaugeError):
            step_workshop_gauge("SHOP-CNC-MILL", g, dt_s=20,
                                now_s=30, driven=True)
        with self.assertRaises(WorkshopGaugeError):
            step_workshop_gauge("SHOP-CNC-MILL", g, dt_s=10,
                                now_s=20, driven=1)
        bogus = copy.deepcopy(g)
        bogus["value"] = 999999
        with self.assertRaises(WorkshopGaugeError):
            machine_output_confirmed("SHOP-CNC-MILL",
                {GAUGE_FIELD: bogus}, observed_s=10, operating=True)
        with self.assertRaises(WorkshopGaugeError):
            step_workshop_gauge("SHOP-CNC-MILL", bogus, dt_s=10,
                                now_s=20, driven=True)

    def test_seeded_power_cycles_never_invent_speed_or_reverse_tally(self):
        rng = random.Random(6119)
        for name, (kind, rated, _rise, _decay, _min) in WORKSHOP_DRIVES.items():
            sample = None
            previous_total = 0.0
            previous_driven = 0.0
            for i in range(160):
                sample = step_workshop_gauge(
                    name, sample, dt_s=10, now_s=10 * (i + 1),
                    driven=(rng.randrange(4) != 0))
                self.assertGreaterEqual(sample["value"], 0)
                self.assertLessEqual(sample["value"], rated)
                self.assertGreaterEqual(sample["cumulative_output"], previous_total)
                self.assertGreaterEqual(sample["driven_s"], previous_driven)
                previous_total = sample["cumulative_output"]
                previous_driven = sample["driven_s"]


if __name__ == "__main__":
    unittest.main()
