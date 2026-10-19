"""G3e-3: actor-owned uncertainty and diagnostic tests without a dispute."""
from __future__ import annotations

from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.event_journal import inbox
from world.investigation import arm_anomaly, take_sample
from world.investigation_followup import take_probe
from world.models import CrewEvent, InvestigationCase, WorkReceipt
from world.work_actions import execute_work


class IndependentQuestionsTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()
        self.case_id = arm_anomaly(cause="scrubber_bypass", seed=6)
        for i, role in enumerate(("officer", "watch", "chief", "cargo", "environment"), 1):
            actor = self.ship[role]
            self.assertIsNotNone(take_sample(actor, self.case_id))
            outcome = execute_work(
                actor, format(i, "032x"), "anomaly_report",
                arguments={"case_id": self.case_id},
            )
            self.assertEqual(outcome["status"], "succeeded")

    def attempt(self, who, nonce, operation, hypothesis=None):
        args = {"case_id": self.case_id}
        if hypothesis is not None:
            args["hypothesis"] = hypothesis
        return execute_work(self.ship[who], nonce * 32, operation, arguments=args)

    def interrogate(self, who, q, p, *, opinion=None, r=None):
        self.assertEqual(self.attempt(who, q, "anomaly_question")["status"], "succeeded")
        observed = take_probe(self.ship[who], self.case_id)
        self.assertIsNotNone(observed)
        self.assertEqual(take_probe(self.ship[who], self.case_id), observed)
        self.assertEqual(self.attempt(who, p, "anomaly_probe_report")["status"], "succeeded")
        if opinion is not None:
            self.assertIsNotNone(r)
            self.assertEqual(self.attempt(
                who, r, "anomaly_reconsider", hypothesis=opinion,
            )["status"], "succeeded")
        return observed

    def test_world_allows_questions_before_any_bridge_diagnosis(self):
        self.assertEqual(InvestigationCase.objects.get(pk=self.case_id).assessment, {})
        self.assertEqual(self.attempt("officer", "a", "anomaly_question")["status"], "failed")
        self.assertEqual(self.attempt("watch", "b", "anomaly_reconsider",
                                      hypothesis="bus_interference")["status"], "failed")
        ari = self.interrogate("watch", "c", "d", opinion="bus_interference", r="e")
        mara = self.interrogate("cargo", "f", "6", opinion="cargo_vapors", r="7")
        self.assertIn(ari["reading"], ("supports", "does_not_support"))
        self.assertIn(mara["reading"], ("supports", "does_not_support"))
        case = InvestigationCase.objects.get(pk=self.case_id)
        self.assertEqual(len(case.questions), 2)
        self.assertEqual(case.challenges, {})
        self.assertEqual(case.assessment, {})
        self.assertEqual(case.reconsiderations[self.ship["watch"].dbref]["previous_hypothesis"], None)
        self.assertEqual(self.attempt(
            "officer", "0", "anomaly_reassess", hypothesis="bus_interference",
        )["status"], "succeeded")
        case.refresh_from_db()
        self.assertEqual(case.cause, "scrubber_bypass")
        self.assertEqual(case.assessment, {})
        self.assertEqual(case.reassessment["previous_hypothesis"], None)
        self.assertEqual(case.reassessment["hypothesis"], "bus_interference")
        self.assertIsNone(case.reassessment["changed"])
        self.assertEqual(case.reassessment["verification"], "unconfirmed")
        self.assertEqual(case.status, "open")
        for role in ("officer", "watch", "chief", "cargo", "environment"):
            for event in inbox(self.ship[role]):
                if event["kind"].startswith("anomaly_"):
                    self.assertNotIn("true_cause", str(event))
                    self.assertNotIn("root_cause", str(event))

    def test_question_can_be_asked_without_challenge_to_existing_diagnosis(self):
        self.assertEqual(self.attempt(
            "officer", "a", "anomaly_assess", hypothesis="cargo_vapors",
        )["status"], "succeeded")
        self.interrogate("chief", "b", "c")
        self.interrogate("environment", "d", "e")
        case = InvestigationCase.objects.get(pk=self.case_id)
        self.assertEqual(case.challenges, {})
        self.assertEqual(case.reconsiderations, {})
        self.assertEqual(len(case.questions), 2)
        # Two independent raw measurements suffice for a tentative bridge
        # reassessment; crew members are not forced to propose a hypothesis.
        self.assertEqual(self.attempt(
            "officer", "f", "anomaly_reassess", hypothesis="scrubber_bypass",
        )["status"], "succeeded")
        case.refresh_from_db()
        self.assertEqual(case.assessment["hypothesis"], "cargo_vapors")
        self.assertEqual(case.reassessment["hypothesis"], "scrubber_bypass")
        self.assertEqual(case.reassessment["changed"], True)

    def test_locality_source_provenance_and_failed_receipt_replay(self):
        mara = self.ship["cargo"]
        mara.move_to(self.ship["bridge"], quiet=True)
        self.assertIsNone(take_probe(mara, self.case_id))
        denied = self.attempt("cargo", "a", "anomaly_question")
        self.assertEqual(denied["status"], "failed")
        mara.move_to(self.ship["cradle"].location, quiet=True)
        self.assertEqual(self.attempt("cargo", "a", "anomaly_question"), denied)
        self.assertEqual(self.attempt("cargo", "b", "anomaly_question")["status"], "succeeded")
        self.assertEqual(self.attempt("cargo", "c", "anomaly_question")["status"], "failed")
        self.assertEqual(self.attempt("cargo", "d", "anomaly_probe_report")["status"], "failed")
        sampled = take_probe(mara, self.case_id)
        self.assertIsNotNone(sampled)
        mara.move_to(self.ship["bridge"], quiet=True)
        self.assertEqual(self.attempt("cargo", "e", "anomaly_probe_report")["status"], "failed")
        mara.move_to(self.ship["cradle"].location, quiet=True)
        self.assertEqual(self.attempt("cargo", "f", "anomaly_probe_report")["status"], "succeeded")
        self.assertFalse(any(
            e["kind"] == "anomaly_probe_sampled" for e in inbox(self.ship["officer"])
        ))
        self.assertEqual(len([
            e for e in inbox(mara) if e["kind"] == "anomaly_probe_sampled"
        ]), 1)
        with self.assertRaises(PermissionError):
            self.attempt("watch", "b", "anomaly_question")
        self.assertEqual(
            self.attempt("cargo", "f", "anomaly_probe_report"),
            self.attempt("cargo", "f", "anomaly_probe_report"),
        )

    def test_operator_removing_a_report_does_not_grant_permission(self):
        case = InvestigationCase.objects.get(pk=self.case_id)
        reports = dict(case.reports)
        reports.pop(self.ship["cargo"].dbref)
        case.reports = reports
        case.save(update_fields=["reports"])
        self.assertEqual(self.attempt("cargo", "a", "anomaly_question")["status"], "failed")
        self.assertIsNone(take_probe(self.ship["cargo"], self.case_id))

    def test_bridge_requires_two_departments_after_questioning(self):
        self.interrogate("watch", "a", "b")
        self.assertEqual(self.attempt(
            "officer", "c", "anomaly_reassess", hypothesis="bus_interference",
        )["status"], "failed")
        self.interrogate("cargo", "d", "e")
        # Failures are immutable, including if the evidence improves later.
        self.assertEqual(self.attempt(
            "officer", "c", "anomaly_reassess", hypothesis="bus_interference",
        )["status"], "failed")
        self.assertEqual(self.attempt(
            "officer", "f", "anomaly_reassess", hypothesis="bus_interference",
        )["status"], "succeeded")

    def test_partial_two_recipient_question_is_rolled_back(self):
        from world import investigation_followup
        ari = self.ship["watch"]
        events_before = CrewEvent.objects.count()
        original = investigation_followup.emit
        calls = 0

        def interrupted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected journal failure")
            return original(*args, **kwargs)

        with patch.object(investigation_followup, "emit", side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                self.attempt("watch", "a", "anomaly_question")
        self.assertEqual(CrewEvent.objects.count(), events_before)
        self.assertFalse(WorkReceipt.objects.filter(pk="a" * 32).exists())
        self.assertEqual(InvestigationCase.objects.get(pk=self.case_id).questions, {})
        self.assertEqual(self.attempt("watch", "a", "anomaly_question")["status"], "succeeded")
        self.assertEqual(len([
            e for e in inbox(ari) if e["kind"] == "anomaly_question_recorded"
        ]), 1)
