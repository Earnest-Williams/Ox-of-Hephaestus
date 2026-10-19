"""G3f: captain owns unresolved obligations, not diagnoses or repairs."""
from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.captain import (
    captain_qualified_observation, tick_captain_obligations,
)
from world.event_journal import inbox
from world.investigation import arm_anomaly, take_sample
from world.investigation_followup import take_probe
from world.models import CaptainObligation, CrewEvent, InvestigationCase, WorkReceipt
from world.work_actions import execute_work


class CaptainFollowthroughTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()
        self.case_id = arm_anomaly(cause="scrubber_bypass", seed=6)
        self.captain = self.ship["captain"]

    def work(self, who, nonce, verb, **arguments):
        return execute_work(
            self.ship[who], nonce * 32, verb, "ship",
            arguments={"ticket_id": self.case_id, **arguments},
        )

    def test_world_owned_ticket_is_open_even_without_a_bridge_theory(self):
        item = CaptainObligation.objects.get(pk=self.case_id)
        self.assertEqual(item.kind, "analyzer_anomaly")
        self.assertEqual(item.priority, 70)
        self.assertEqual(item.status, "open")
        self.assertEqual(item.captain_dbref, self.captain.dbref)
        notice = [e for e in inbox(self.captain)
                  if e["kind"] == "captain_problem_open"]
        self.assertEqual(len(notice), 1)
        self.assertEqual(notice[0]["data"]["ticket_id"], self.case_id)
        self.assertNotIn("scrubber_bypass", str(notice))
        self.assertEqual(InvestigationCase.objects.get(pk=self.case_id).assessment, {})
        self.assertEqual(self.work("officer", "a", "captain_claim")["status"], "failed")
        self.assertEqual(self.work("captain", "b", "captain_claim")["status"], "succeeded")

    def test_assignment_cannot_fake_a_result_or_silently_close_case(self):
        self.assertEqual(self.work("captain", "a", "captain_claim")["status"], "succeeded")
        self.assertEqual(self.work(
            "captain", "b", "captain_assign", role="teo",
        )["status"], "succeeded")
        # Even the captain is forbidden to submit another character's answer.
        self.assertEqual(self.work(
            "captain", "c", "captain_answer", mode="accept",
        )["status"], "failed")
        self.assertEqual(self.work(
            "captain", "d", "captain_assign", role="mara",
        )["status"], "failed")
        self.assertEqual(self.work(
            "environment", "e", "captain_answer", mode="accept",
        )["status"], "succeeded")
        self.assertEqual(self.work(
            "captain", "f", "captain_review",
        )["status"], "succeeded")
        item = CaptainObligation.objects.get(pk=self.case_id)
        self.assertEqual(item.status, "open")
        self.assertEqual(item.assignment["status"], "accepted")
        self.assertEqual(item.history[-1]["result"], "awaiting_verified_work")

        teo = self.ship["environment"]
        self.assertIsNotNone(take_sample(teo, self.case_id))
        self.assertEqual(execute_work(
            teo, "1" * 32, "anomaly_report", "ship",
            arguments={"case_id": self.case_id},
        )["status"], "succeeded")
        self.assertEqual(execute_work(
            teo, "2" * 32, "anomaly_question", "ship",
            arguments={"case_id": self.case_id},
        )["status"], "succeeded")
        self.assertIsNotNone(take_probe(teo, self.case_id))
        self.assertEqual(execute_work(
            teo, "3" * 32, "anomaly_probe_report", "ship",
            arguments={"case_id": self.case_id},
        )["status"], "succeeded")
        item.refresh_from_db()
        self.assertEqual(item.assignment["status"], "reported")
        evidence = [e for e in inbox(self.captain)
                    if e["kind"] == "captain_followup_evidence"]
        self.assertEqual(len(evidence), 1)
        self.assertNotIn("scrubber_bypass", str(evidence))
        self.assertEqual(self.work(
            "captain", "4", "captain_review",
        )["status"], "succeeded")
        item.refresh_from_db()
        self.assertEqual(item.status, "open")
        self.assertEqual(self.work(
            "captain", "5", "captain_assign", role="teo",
        )["status"], "failed")
        self.assertEqual(self.work(
            "captain", "6", "captain_assign", role="iona",
        )["status"], "succeeded")
        self.assertEqual(self.work(
            "captain", "6", "captain_assign", role="iona",
        ), self.work("captain", "6", "captain_assign", role="iona"))

    def test_preexisting_probe_does_not_fulfil_new_captain_order(self):
        self.assertEqual(self.work("captain", "a", "captain_claim")["status"], "succeeded")
        teo = self.ship["environment"]
        self.assertIsNotNone(take_sample(teo, self.case_id))
        self.assertEqual(execute_work(
            teo, "b" * 32, "anomaly_report",
            arguments={"case_id": self.case_id},
        )["status"], "succeeded")
        self.assertEqual(execute_work(
            teo, "c" * 32, "anomaly_question",
            arguments={"case_id": self.case_id},
        )["status"], "succeeded")
        self.assertIsNotNone(take_probe(teo, self.case_id))
        self.assertEqual(execute_work(
            teo, "d" * 32, "anomaly_probe_report",
            arguments={"case_id": self.case_id},
        )["status"], "succeeded")
        observed = [
            e for e in inbox(self.captain)
            if e["kind"] == "captain_specialist_test_logged"
        ]
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0]["data"]["role"], "teo")
        self.assertEqual(self.work(
            "captain", "e", "captain_assign", role="teo",
        )["status"], "failed")
        self.assertEqual(self.work(
            "captain", "f", "captain_assign", role="iona",
        )["status"], "succeeded")

    def test_declines_are_reported_and_enable_reassignment(self):
        self.assertEqual(self.work("captain", "a", "captain_claim")["status"], "succeeded")
        self.assertEqual(self.work(
            "captain", "b", "captain_assign", role="teo",
        )["status"], "succeeded")
        self.assertEqual(self.work(
            "environment", "c", "captain_answer", mode="decline",
        )["status"], "succeeded")
        self.assertEqual(self.work(
            "captain", "d", "captain_review",
        )["status"], "succeeded")
        self.assertEqual(self.work(
            "captain", "e", "captain_assign", role="ari",
        )["status"], "succeeded")
        self.assertEqual(CaptainObligation.objects.get(pk=self.case_id).status, "open")

    def test_no_direct_diagnostic_authority_without_proficiency(self):
        self.assertIsNone(captain_qualified_observation(self.captain, self.case_id))
        self.captain.db.ox_skills = {
            **self.captain.db.ox_skills, "diagnostics": 2,
        }
        measured = captain_qualified_observation(self.captain, self.case_id)
        self.assertEqual(measured["reading"], "analyzer_disagreement")
        self.assertNotIn("scrubber_bypass", str(measured))
        self.captain.move_to(self.ship["engineering"], quiet=True)
        self.assertIsNone(captain_qualified_observation(self.captain, self.case_id))

    def test_world_clock_reminds_captain_without_reopening_closed_work(self):
        item = CaptainObligation.objects.get(pk=self.case_id)
        due = item.due_game_time + 1.0
        self.assertEqual(tick_captain_obligations(now_game_time=due), 1)
        self.assertEqual(tick_captain_obligations(now_game_time=due), 0)
        self.assertEqual(len([
            e for e in inbox(self.captain) if e["kind"] == "captain_review_due"
        ]), 1)
        self.assertEqual(CaptainObligation.objects.get(pk=self.case_id).status, "open")

    def test_physical_life_support_restoration_is_only_legitimate_closure(self):
        scrubber = self.ship["scrubber"]
        self.assertTrue(scrubber.inject_fault()[0])
        life = CaptainObligation.objects.get(kind="atmosphere_alarm", status="open")
        self.assertEqual(life.priority, 100)
        self.assertEqual(execute_work(
            self.captain, "a" * 32, "captain_claim",
            arguments={"ticket_id": life.ticket_id},
        )["status"], "succeeded")
        self.assertEqual(execute_work(
            self.captain, "b" * 32, "captain_assign",
            arguments={"ticket_id": life.ticket_id, "role": "teo"},
        )["status"], "succeeded")
        self.assertEqual(execute_work(
            self.captain, "c" * 32, "captain_review",
            arguments={"ticket_id": life.ticket_id},
        )["status"], "succeeded")
        life.refresh_from_db()
        self.assertEqual(life.status, "open")
        teo = self.ship["environment"]
        self.assertEqual(execute_work(
            teo, "d" * 32, "captain_answer",
            arguments={"ticket_id": life.ticket_id, "mode": "accept"},
        )["status"], "succeeded")
        scrubber.note_inspection(teo)
        self.assertTrue(scrubber.isolate(teo)[0])
        self.assertTrue(scrubber.replace(teo)[0])
        scrubber.note_inspection(teo)
        self.assertTrue(scrubber.restart(teo)[0])
        self.assertEqual(execute_work(
            self.captain, "e" * 32, "captain_review",
            arguments={"ticket_id": life.ticket_id},
        )["status"], "succeeded")
        life.refresh_from_db()
        self.assertEqual(life.status, "resolved")
        self.assertEqual(InvestigationCase.objects.get(pk=self.case_id).status, "open")
        self.assertEqual(len([
            e for e in inbox(self.captain) if e["kind"] == "captain_world_resolved"
        ]), 1)
        self.assertEqual(execute_work(
            self.captain, "f" * 32, "captain_review",
            arguments={"ticket_id": life.ticket_id},
        )["status"], "failed")

    def test_partial_assignment_notice_rolls_back_world_and_receipt(self):
        from world import captain
        self.assertEqual(self.work("captain", "a", "captain_claim")["status"], "succeeded")
        original = captain.emit
        before = CrewEvent.objects.count()
        times = 0
        def fail_second(*args, **kwargs):
            nonlocal times
            times += 1
            if times == 2:
                raise RuntimeError("uncommitted recipient")
            return original(*args, **kwargs)
        with patch.object(captain, "emit", side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.work("captain", "b", "captain_assign", role="teo")
        self.assertEqual(CrewEvent.objects.count(), before)
        self.assertFalse(WorkReceipt.objects.filter(pk="b" * 32).exists())
        self.assertEqual(CaptainObligation.objects.get(pk=self.case_id).assignment, {})
        self.assertEqual(self.work(
            "captain", "b", "captain_assign", role="teo",
        )["status"], "succeeded")
