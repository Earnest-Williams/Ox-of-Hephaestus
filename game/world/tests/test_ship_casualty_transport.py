"""Bounded two-carrier physical rescue orders, no anonymous crew."""
import unittest

from world.ship_casualty_transport import (
    RescueError, initial_rescue, validate_rescue,
    begin_rescue, step_rescue, finish_rescue,
)


def queue(ledger=None, **change):
    args = dict(patient="#9", lead="#3", helper="#4",
                link="ACC-HAB-04-MED-TREAT", direction="forward",
                origin="HAB-04-COR", destination="HAB-04-MED-TREAT",
                seconds=30.0, request_id="b"*32)
    args.update(change)
    return begin_rescue(initial_rescue() if ledger is None else ledger, **args)


class RescueTransportTests(unittest.TestCase):
    def test_queue_is_independent_of_input_and_durable(self):
        baseline = initial_rescue()
        pending = queue(baseline)
        self.assertEqual(baseline, initial_rescue())
        self.assertEqual(pending["jobs"]["#9"]["remaining_s"], 30)
        self.assertTrue(validate_rescue(pending))

    def test_no_progress_for_closed_door_or_missing_staff(self):
        pending = queue()
        paused, finished = step_rescue(
            pending, 60, ready_patients=set())
        self.assertEqual(paused, pending)
        self.assertEqual(finished, ())
        with self.assertRaises(RescueError):
            finish_rescue(paused, patient="#9", request_id="b"*32)

    def test_bounded_transfer_and_no_double_delivery(self):
        pending = queue()
        pending, ready = step_rescue(
            pending, 10, ready_patients={"#9"})
        self.assertEqual(ready, ())
        pending, ready = step_rescue(
            pending, 20, ready_patients={"#9"})
        self.assertEqual([person for person, _ in ready], ["#9"])
        completed = finish_rescue(pending, patient="#9", request_id="b"*32)
        self.assertEqual(completed["completed"], 1)
        self.assertEqual(completed["jobs"], {})
        with self.assertRaises(RescueError):
            finish_rescue(completed, patient="#9", request_id="b"*32)
        self.assertEqual(initial_rescue()["completed"], 0)

    def test_cancel_is_finite_and_unique(self):
        cancelled = finish_rescue(
            queue(), patient="#9", request_id="b"*32, cancelled=True)
        self.assertEqual(cancelled["cancelled"], 1)
        self.assertEqual(cancelled["completed"], 0)

    def test_no_parallel_reuse_of_patient_or_team(self):
        with self.assertRaises(RescueError):
            queue(queue())
        with self.assertRaises(RescueError):
            queue(queue(), patient="#10", helper="#4", request_id="c"*32)
        with self.assertRaises(RescueError):
            queue(queue(), patient="#10", lead="#5", helper="#6", request_id="b"*32)
        another = queue(queue(), patient="#10", lead="#5", helper="#6",
                        request_id="c"*32)
        self.assertEqual(len(another["jobs"]), 2)

    def test_corrupt_people_timing_and_links_fail_closed(self):
        for change in (
                dict(lead="#9"), dict(helper="#3"),
                dict(seconds=5), dict(seconds=float("nan")),
                dict(seconds=500), dict(origin="HAB-04-MED-TREAT"),
                dict(direction="sideways"),
                dict(link="ACC-EVA:UNVERIFIED"),
                dict(request_id="not-a-request")):
            with self.subTest(change=change), self.assertRaises(RescueError):
                queue(**change)
        corrupt = queue()
        corrupt["jobs"]["#9"]["remaining_s"] = -1
        with self.assertRaises(RescueError):
            validate_rescue(corrupt)
        with self.assertRaises(RescueError):
            step_rescue(queue(), 61, ready_patients={"#9"})


if __name__ == "__main__":
    unittest.main()
