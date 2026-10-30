"""Persistent finite repair custody, multiworker work and hard fault gates."""
import unittest

from world.ship_water_recycling import WaterError
from world.ship_equipment_repair import (
    initial_repairs, take_parts, begin_repair, join_repair, move_toolkit,
    step_repairs, validate_repairs, REPAIR_CLASSES)


class SharedRepairContractTests(unittest.TestCase):
    def test_spares_follow_worker_and_are_installed_only_after_time(self):
        r = initial_repairs()
        r = move_toolkit(r, actor_dbref="#15", verb="pickup_toolkit")
        r, stock = take_parts(
            r, actor_dbref="#15", kg=3, stock_kg=25000)
        self.assertEqual(stock, 24997)
        r = begin_repair(
            r, target="equipment:GEN-M", room="GEN-M-ROOM",
            actor_dbref="#15", condition="failed")
        self.assertEqual(r["carried_kg"]["#15"], 0)
        r, done = step_repairs(
            r, 60, present_workers={}, safe_targets={"equipment:GEN-M"})
        self.assertFalse(done)
        self.assertEqual(r["jobs"]["equipment:GEN-M"]["remaining_s"], 600)
        r, done = step_repairs(
            r, 60, present_workers={"GEN-M-ROOM": {"#15"}},
            safe_targets=set())
        self.assertFalse(done)
        self.assertEqual(r["jobs"]["equipment:GEN-M"]["remaining_s"], 600)
        for _ in range(10):
            r, done = step_repairs(
                r, 60, present_workers={"GEN-M-ROOM": {"#15"}},
                safe_targets={"equipment:GEN-M"})
        self.assertEqual(done[0][:2], ("equipment:GEN-M", "failed"))
        self.assertFalse(r["jobs"])
        self.assertEqual(r["installed_kg"], 3)
        self.assertEqual(r["completed"], 1)
        validate_repairs(r)

    def test_shared_assistance_is_limited_and_cannot_invent_parts(self):
        r = initial_repairs()
        for worker in ("#15", "#20"):
            r = move_toolkit(r, actor_dbref=worker, verb="pickup_toolkit")
        r, stock = take_parts(r, actor_dbref="#15", kg=2, stock_kg=50)
        r = begin_repair(
            r, target="isolator:ISO-GEN-M", room="GEN-M-ROOM",
            actor_dbref="#15", condition="jammed")
        r = join_repair(
            r, target="isolator:ISO-GEN-M",
            actor_dbref="#20", room="GEN-M-ROOM")
        r, done = step_repairs(
            r, 60, present_workers={"GEN-M-ROOM": {"#15", "#20"}},
            safe_targets={"isolator:ISO-GEN-M"})
        self.assertEqual(done, ())
        self.assertEqual(r["jobs"]["isolator:ISO-GEN-M"]["remaining_s"], 516)
        with self.assertRaises(WaterError):
            join_repair(r, target="isolator:ISO-GEN-M",
                        actor_dbref="#20", room="GEN-M-ROOM")
        self.assertAlmostEqual(stock + r["installed_kg"] +
            sum(r["carried_kg"].values()) +
            sum(job["staged_kg"] for job in r["jobs"].values()), 50)

    def test_six_reusable_crib_toolkits_cannot_be_invented_or_returned_mid_job(self):
        r = initial_repairs()
        for n in range(1, 7):
            r = move_toolkit(r, actor_dbref="#" + str(n), verb="pickup_toolkit")
        self.assertEqual(r["toolkits_at_crib"], 0)
        with self.assertRaises(WaterError):
            move_toolkit(r, actor_dbref="#7", verb="pickup_toolkit")
        r, remaining = take_parts(r, actor_dbref="#1", kg=3, stock_kg=30)
        r = begin_repair(r, target="equipment:GEN-M", room="GEN-M-ROOM",
                         actor_dbref="#1", condition="failed")
        with self.assertRaises(WaterError):
            move_toolkit(r, actor_dbref="#1", verb="return_toolkit")
        r = move_toolkit(r, actor_dbref="#6", verb="return_toolkit")
        self.assertEqual(r["toolkits_at_crib"], 1)
        self.assertEqual(remaining, 27)
        validate_repairs(r)
        r["toolkits_at_crib"] = 6
        with self.assertRaises(WaterError):
            validate_repairs(r)

    def test_nonexistent_spares_and_unrepairable_damage_fail_closed(self):
        with self.assertRaises(WaterError):
            take_parts(initial_repairs(), actor_dbref="#1",
                       kg=13, stock_kg=25000)
        with self.assertRaises(WaterError):
            take_parts(initial_repairs(), actor_dbref="#1",
                       kg=4, stock_kg=2)
        with self.assertRaises(WaterError):
            begin_repair(
                initial_repairs(), target="equipment:LCS-PROP",
                room="PROP-SVC", actor_dbref="#1", condition="destroyed")
        with self.assertRaises(WaterError):
            begin_repair(
                initial_repairs(), target="equipment:LCS-PROP",
                room="PROP-SVC", actor_dbref="#1", condition="failed")

    def test_corrupted_material_custody_and_negative_ticks_fail_closed(self):
        r = initial_repairs()
        r["installed_kg"] = 1.0
        with self.assertRaises(WaterError):
            validate_repairs(r)
        with self.assertRaises(WaterError):
            step_repairs(initial_repairs(), -1,
                         present_workers={}, safe_targets=set())
        with self.assertRaises(WaterError):
            step_repairs(initial_repairs(), float("nan"),
                         present_workers={}, safe_targets=set())


if __name__ == "__main__":
    unittest.main()
