"""G19 F1/F2 sealed, two-lock original source and finite progress."""
import unittest

from world.ship_hazardous_access import (
    BayAccessError, LOCKS, CYCLE_S, initial_bay_access,
    validate_bay_access, survey_bay, begin_bay_transit,
    step_bay_transits, finish_bay_transit,
)


class BayAccessTests(unittest.TestCase):
    def setUp(self):
        self.original = initial_bay_access()
        self.surveyed = survey_bay(survey_bay(
            self.original, "F1-BAY"), "F2-BAY")

    def begin(self, **kwargs):
        args = dict(actor="#12", link="ACC-F1-BAY",
                    direction="forward", source="TRUNK-A-F1",
                    destination="F1-BAY", request_id="a"*32)
        args.update(kwargs)
        return begin_bay_transit(self.surveyed, **args)

    def test_survey_does_not_invent_an_air_cell_or_initial_worker(self):
        self.assertEqual(self.original, initial_bay_access())
        self.assertEqual(self.surveyed["surveyed_bays"], ["F1-BAY", "F2-BAY"])
        self.assertTrue(validate_bay_access(self.surveyed))
        self.assertFalse(self.surveyed["jobs"])
        with self.assertRaises(BayAccessError):
            survey_bay(self.surveyed, "GEN-A-ROOM")
        with self.assertRaises(BayAccessError):
            begin_bay_transit(self.original, actor="#12", link="ACC-F1-BAY",
                              direction="forward", source="TRUNK-A-F1",
                              destination="F1-BAY", request_id="b"*32)

    def test_finite_180_second_double_sealed_cycle(self):
        transit = self.begin()
        for _ in range(2):
            transit, done = step_bay_transits(
                transit, 60, ready_links={"ACC-F1-BAY"})
            self.assertFalse(done)
        transit, done = step_bay_transits(
            transit, 60, ready_links={"ACC-F1-BAY"})
        self.assertEqual(done[0][0], "#12")
        self.assertEqual(done[0][1]["to"], "F1-BAY")
        finished = finish_bay_transit(
            transit, actor="#12", request_id="a"*32)
        self.assertEqual(finished["completed"], 1)
        self.assertFalse(finished["jobs"])

    def test_outbound_and_inbound_use_same_authored_passage(self):
        first = self.begin()
        for _ in range(3):
            first, _ = step_bay_transits(first, 60, ready_links={"ACC-F1-BAY"})
        done = finish_bay_transit(first, actor="#12", request_id="a"*32)
        back = begin_bay_transit(
            done, actor="#12", link="ACC-F1-BAY", direction="reverse",
            source="F1-BAY", destination="TRUNK-A-F1",
            request_id="b"*32)
        self.assertEqual(back["jobs"]["#12"]["to"], "TRUNK-A-F1")

    def test_two_independent_bays_and_one_body_per_lock(self):
        first = self.begin()
        second = begin_bay_transit(
            first, actor="#23", link="ACC-F2-BAY", direction="forward",
            source="TRUNK-A-F2", destination="F2-BAY", request_id="b"*32)
        self.assertEqual(len(second["jobs"]), 2)
        with self.assertRaises(BayAccessError):
            begin_bay_transit(first, actor="#23", link="ACC-F1-BAY",
                              direction="forward", source="TRUNK-A-F1",
                              destination="F1-BAY", request_id="b"*32)

    def test_power_or_seal_loss_suspends_clock_not_teleports(self):
        transit = self.begin()
        halted, done = step_bay_transits(
            transit, 60, ready_links=set())
        self.assertEqual(halted, transit)
        self.assertFalse(done)
        with self.assertRaises(BayAccessError):
            finish_bay_transit(halted, actor="#12", request_id="a"*32)
        for bad in (dict(destination="F2-BAY"),
                    dict(direction="reverse"), dict(actor="not-a-crew"),
                    dict(link="ACC-LOGI-F1-BAY"),
                    dict(request_id="bad")):
            with self.subTest(bad=bad), self.assertRaises(BayAccessError):
                self.begin(**bad)
        with self.assertRaises(BayAccessError):
            step_bay_transits(transit, float("nan"),
                              ready_links={"ACC-F1-BAY"})
