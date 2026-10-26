"""EVA: finite source stock, exact airlock gas custody, external transit."""
import unittest

from world.ship_eva_operations import (
    EVAError, SUIT_O2_KG, initial_eva, validate_eva, stage_suit_oxygen,
    checkout_suit, suit_of, return_suit, begin_cycle, step_cycles,
    transfer_recovered_gas, step_suit_metabolism, begin_eva_transit,
    step_eva_transits, finish_eva_transit,
)

class EVATests(unittest.TestCase):
    def setUp(self):
        e = initial_eva()
        self.staged = stage_suit_oxygen(
            e, actor="#42", room="ENG-LOCKER", kg=SUIT_O2_KG)
        self.eva, _, issue = checkout_suit(
            self.staged, actor="#42", lock="EVA-FWD",
            supplied_oxygen_kg=SUIT_O2_KG)
        self.assertEqual(issue, SUIT_O2_KG)

    def test_issues_are_finite_and_deduplicated(self):
        self.assertTrue(validate_eva(self.eva))
        self.assertEqual(self.eva["issued_kg"], self.eva["charged_kg"])
        self.assertFalse(self.eva["staged_kg"])
        self.assertEqual(initial_eva()["suits"]["EVA-FWD-SUIT-1"]["holder"], None)
        with self.assertRaises(EVAError):
            checkout_suit(self.eva, actor="#42", lock="EVA-AFT",
                          supplied_oxygen_kg=SUIT_O2_KG)
        with self.assertRaises(EVAError):
            stage_suit_oxygen(self.eva, actor="#43",
                              room="NOT-A-STORE", kg=1)
        with self.assertRaises(EVAError):
            checkout_suit(initial_eva(), actor="#42", lock="EVA-FWD",
                          supplied_oxygen_kg=.75)

    def test_two_airlock_cycles_reuse_actual_gas_exactly(self):
        eva = begin_cycle(self.eva, lock="EVA-FWD", direction="pumpdown")
        cells = {
            "PZ-BOW-EVA": {
                "mass": 220., "oxygen": 50., "co2": 1.,
                "smoke": .1, "temperature": 295.,
                "capacity": 5000., "energy": (5000+220*1.005)*295,
            }}
        baseline = cells["PZ-BOW-EVA"].copy()
        for i in range(9):
            eva, finished = step_cycles(eva, 10, ready_locks={"EVA-FWD"})
            if i < 8:
                self.assertFalse(finished)
        self.assertEqual(finished, (("EVA-FWD", "pumpdown"),))
        eva, cells = transfer_recovered_gas(
            eva, cells, lock="EVA-FWD", cycle="pumpdown")
        self.assertEqual(cells["PZ-BOW-EVA"]["mass"], 0)
        self.assertEqual(eva["locks"]["EVA-FWD"]["buffer"]["mass"], 220)
        eva = begin_cycle(eva, lock="EVA-FWD", direction="repressurise")
        for _ in range(9):
            eva, finished = step_cycles(eva, 10, ready_locks={"EVA-FWD"})
        self.assertEqual(finished, (("EVA-FWD", "repressurise"),))
        eva, cells = transfer_recovered_gas(
            eva, cells, lock="EVA-FWD", cycle="repressurise")
        for key in ("mass", "oxygen", "co2", "smoke"):
            self.assertAlmostEqual(cells["PZ-BOW-EVA"][key], baseline[key])
        self.assertEqual(eva["locks"]["EVA-FWD"]["buffer"]["mass"], 0)
        self.assertEqual(eva["locks"]["EVA-FWD"]["cycles"], 2)

    def test_closed_damper_or_failed_pump_cannot_advance_airlock(self):
        eva = begin_cycle(self.eva, lock="EVA-FWD", direction="pumpdown")
        for _ in range(20):
            eva, done = step_cycles(eva, 10, ready_locks=set())
            self.assertFalse(done)
        self.assertEqual(eva["locks"]["EVA-FWD"]["remaining_s"], 90)

    def test_worn_suit_breathes_real_stock_and_exterior_travel_is_timed(self):
        e = begin_eva_transit(
            self.eva, actor="#42", link="ACC-EVA-FWD-EXT",
            source="EVA-FWD", destination="EXT-BOW", seconds=45,
            request_id="a" * 32)
        for i in range(5):
            e = step_suit_metabolism(e, 10)
            e, ready = step_eva_transits(
                e, 10, ready_links={"ACC-EVA-FWD-EXT"})
        self.assertEqual(len(ready), 1)
        self.assertLess(suit_of(e, "#42")[1]["exposure"]["suit_oxygen_kg"],
                        SUIT_O2_KG)
        with self.assertRaises(EVAError):
            return_suit(e, actor="#42", lock="EVA-FWD")
        e = finish_eva_transit(e, actor="#42", request_id="a" * 32)
        self.assertEqual(e["completed_transits"], 1)
        self.assertFalse(e["transits"])

    def test_no_free_survival_if_breathing_stock_expires(self):
        e = self.eva
        for _ in range(100):
            e = step_suit_metabolism(e, 10)
        self.assertAlmostEqual(
            suit_of(e, "#42")[1]["exposure"]["suit_oxygen_kg"],
            SUIT_O2_KG - 1000 * 0.00001)
        self.assertAlmostEqual(e["consumed_oxygen_kg"], 0.01)
        self.assertLessEqual(e["consumed_oxygen_kg"], e["charged_kg"])

    def test_gas_buffer_capacity_and_corrupt_ledger_refused(self):
        e = begin_cycle(self.eva, lock="EVA-FWD", direction="pumpdown")
        for _ in range(9):
            e, _ = step_cycles(e, 10, ready_locks={"EVA-FWD"})
        with self.assertRaises(EVAError):
            transfer_recovered_gas(
                e, {"PZ-BOW-EVA": {"mass": 400}}, lock="EVA-FWD",
                cycle="pumpdown")
        damaged = initial_eva()
        damaged["issued_kg"] = 200
        with self.assertRaises(EVAError):
            validate_eva(damaged)

if __name__ == "__main__":
    unittest.main()
