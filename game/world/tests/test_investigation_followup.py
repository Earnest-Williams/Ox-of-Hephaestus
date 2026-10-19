"""G3e-2: independent contradictory evidence and revisable unverified theories."""
from __future__ import annotations

from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.event_journal import inbox
from world.investigation import arm_anomaly, take_sample
from world.investigation_followup import take_probe
from world.models import InvestigationCase, CrewEvent, WorkReceipt
from world.work_actions import execute_work


class FollowupWorldTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()
        self.cid = arm_anomaly(cause="scrubber_bypass", seed=6)
        for index, key in enumerate(("officer", "watch", "chief", "cargo", "environment"), 1):
            actor = self.ship[key]
            self.assertIsNotNone(take_sample(actor, self.cid))
            self.assertEqual(execute_work(
                actor, format(index, "032x"), "anomaly_report",
                arguments={"case_id": self.cid},
            )["status"], "succeeded")
        self.assertEqual(execute_work(
            self.ship["officer"], "a" * 32, "anomaly_assess",
            arguments={"case_id": self.cid, "hypothesis": "cargo_vapors"},
        )["status"], "succeeded")

    def work(self, who, label, op, *, hypothesis=None):
        args = {"case_id": self.cid}
        if hypothesis is not None:
            args["hypothesis"] = hypothesis
        return execute_work(self.ship[who], label * 32, op, arguments=args)

    def challenge(self, who, label, theory):
        self.assertEqual(self.work(
            who, label, "anomaly_challenge", hypothesis=theory,
        )["status"], "succeeded")

    def tested(self, who, a, b, c, hypothesis):
        self.challenge(who, a, "scrubber_bypass" if who != "watch" else "bus_interference")
        sample = take_probe(self.ship[who], self.cid)
        self.assertIsNotNone(sample)
        self.assertEqual(sample, take_probe(self.ship[who], self.cid))
        self.assertEqual(self.work(who, b, "anomaly_probe_report")["status"], "succeeded")
        self.assertEqual(self.work(
            who, c, "anomaly_reconsider", hypothesis=hypothesis,
        )["status"], "succeeded")

    def test_initial_locality_and_fallible_test_are_not_world_truth(self):
        mara = self.ship["cargo"]
        lin = self.ship["officer"]
        self.assertIsNone(take_probe(mara, self.cid))
        self.assertEqual(self.work("officer", "b", "anomaly_challenge",
                                   hypothesis="scrubber_bypass")["status"], "failed")
        self.assertEqual(self.work("cargo", "c", "anomaly_challenge",
                                   hypothesis="cargo_vapors")["status"], "failed")
        self.challenge("cargo", "d", "scrubber_bypass")
        start = len([e for e in inbox(mara) if e["kind"] == "anomaly_probe_sampled"])
        mara.move_to(self.ship["bridge"], quiet=True)
        self.assertIsNone(take_probe(mara, self.cid))
        self.assertEqual(self.work("cargo", "e", "anomaly_probe_report")["status"], "failed")
        mara.move_to(self.ship["cradle"].location, quiet=True)
        observed = take_probe(mara, self.cid)
        self.assertEqual(observed["indicator"], "cargo_blank")
        self.assertEqual(observed["tested_hypothesis"], "cargo_vapors")
        self.assertIn(observed["reading"], ("supports", "does_not_support"))
        self.assertEqual(len([e for e in inbox(mara)
                              if e["kind"] == "anomaly_probe_sampled"]), start + 1)
        self.assertEqual(take_probe(mara, self.cid), observed)
        self.assertFalse(any(e["kind"] == "anomaly_probe_sampled"
                             for e in inbox(lin)))
        self.assertNotIn("scrubber_bypass", str([
            e for e in inbox(lin) if e["kind"] == "anomaly_probe_report"
        ]))
        self.assertEqual(self.work("cargo", "f", "anomaly_probe_report")["status"], "succeeded")
        self.assertEqual(self.work("cargo", "g", "anomaly_probe_report")["status"], "failed")
        self.assertEqual(self.work("cargo", "h", "anomaly_reconsider",
                                   hypothesis="cargo_vapors")["status"], "succeeded")

    def test_independent_incompatible_views_can_produce_wrong_reassessment(self):
        self.tested("watch", "b", "c", "d", "bus_interference")
        self.tested("chief", "e", "f", "1", "scrubber_bypass")
        self.tested("cargo", "2", "3", "4", "cargo_vapors")
        self.tested("environment", "5", "6", "7", "scrubber_bypass")
        self.assertEqual(self.work(
            "environment", "8", "anomaly_reassess",
            hypothesis="bus_interference",
        )["status"], "failed")
        initial = InvestigationCase.objects.get(pk=self.cid)
        self.assertEqual(initial.cause, "scrubber_bypass")
        self.assertEqual(initial.assessment["hypothesis"], "cargo_vapors")
        self.assertEqual(len(initial.reconsiderations), 4)
        self.assertEqual(len(initial.probes), 4)
        self.assertTrue(all("report_event_id" in p for p in initial.probes.values()))
        self.assertEqual(self.work(
            "officer", "9", "anomaly_reassess",
            hypothesis="bus_interference",
        )["status"], "succeeded")
        after = InvestigationCase.objects.get(pk=self.cid)
        self.assertEqual(after.cause, "scrubber_bypass")
        self.assertEqual(after.reassessment["hypothesis"], "bus_interference")
        self.assertEqual(after.reassessment["verification"], "unconfirmed")
        self.assertEqual(after.status, "open")
        self.assertEqual(self.work(
            "officer", "9", "anomaly_reassess",
            hypothesis="bus_interference",
        ), self.work("officer", "9", "anomaly_reassess",
                     hypothesis="bus_interference"))
        self.assertEqual(self.work(
            "officer", "0", "anomaly_reassess",
            hypothesis="scrubber_bypass",
        )["status"], "failed")
        with self.assertRaises(PermissionError):
            self.work("officer", "9", "anomaly_reassess",
                      hypothesis="scrubber_bypass")
        for who in ("officer", "watch", "chief", "cargo", "environment"):
            # Actor-visible reports never leak the world cause as a factual
            # "true_cause" or "verified" field.
            for event in inbox(self.ship[who]):
                if event["kind"].startswith("anomaly_"):
                    self.assertNotIn("true_cause", str(event))
                    self.assertNotIn("root_cause", str(event))

    def test_no_shortcut_without_two_independent_departments(self):
        self.tested("watch", "b", "c", "d", "bus_interference")
        self.assertEqual(self.work(
            "officer", "e", "anomaly_reassess", hypothesis="scrubber_bypass",
        )["status"], "failed")
        # An immutable refusal cannot become a successful receipt later.
        self.tested("cargo", "f", "1", "2", "scrubber_bypass")
        self.assertEqual(self.work(
            "officer", "e", "anomaly_reassess", hypothesis="scrubber_bypass",
        )["status"], "failed")
        self.assertEqual(self.work(
            "officer", "3", "anomaly_reassess", hypothesis="scrubber_bypass",
        )["status"], "succeeded")

    def test_experiment_report_rollback_and_retry_original_request(self):
        from world import investigation_followup
        self.challenge("environment", "b", "scrubber_bypass")
        self.assertIsNotNone(take_probe(self.ship["environment"], self.cid))
        before = CrewEvent.objects.count()
        original = investigation_followup.emit
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("journal failure before commit")
            return original(*args, **kwargs)

        with patch.object(investigation_followup, "emit", side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.work("environment", "c", "anomaly_probe_report")
        self.assertEqual(CrewEvent.objects.count(), before)
        self.assertFalse(WorkReceipt.objects.filter(pk="c" * 32).exists())
        case = InvestigationCase.objects.get(pk=self.cid)
        self.assertNotIn("report_event_id", case.probes[self.ship["environment"].dbref])
        self.assertEqual(self.work(
            "environment", "c", "anomaly_probe_report",
        )["status"], "succeeded")

    def test_failed_reassessment_notification_is_atomically_unpublished(self):
        from world import investigation_followup
        self.tested("watch", "b", "c", "d", "bus_interference")
        self.tested("cargo", "e", "f", "1", "cargo_vapors")
        before = CrewEvent.objects.count()
        original = investigation_followup.emit
        calls = 0

        def fail_third(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RuntimeError("lost third recipient")
            return original(*args, **kwargs)

        with patch.object(investigation_followup, "emit", side_effect=fail_third):
            with self.assertRaises(RuntimeError):
                self.work("officer", "2", "anomaly_reassess",
                          hypothesis="scrubber_bypass")
        self.assertEqual(CrewEvent.objects.count(), before)
        self.assertFalse(WorkReceipt.objects.filter(pk="2" * 32).exists())
        self.assertEqual(InvestigationCase.objects.get(pk=self.cid).reassessment, {})
        self.assertEqual(self.work(
            "officer", "2", "anomaly_reassess",
            hypothesis="scrubber_bypass",
        )["status"], "succeeded")
