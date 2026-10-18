"""Pure, deterministic G2 agent-agenda transitions without a world backdoor."""
from __future__ import annotations

import copy
import json
import unittest

from ox_ai.runtime.crew_agenda import AgentAgenda, ACTIVE, WAITING


def world_event(seq, kind, recipient="#31", *, event_id=None, time=None):
    return {
        "sequence": seq,
        "event_id": event_id or f"oxevt-v2-{seq:04d}",
        "kind": kind,
        "recipient_dbref": recipient,
        "game_time": float(seq if time is None else time),
        "text": kind,
        "data": {},
    }


class AgendaTests(unittest.TestCase):
    def setUp(self):
        self.record = {}
        self.agenda = AgentAgenda(
            self.record, role="mara", character_id="#31",
        )
        self.incident = world_event(12, "cargo_shift")
        self.item = self.agenda.offer(
            self.incident, priority=40, kind="cargo_shift",
        )

    def accept(self):
        self.agenda.set_status(
            self.item["task_id"], "accepted", reason="duty_selected",
        )
        self.agenda.set_status(
            self.item["task_id"], "in_progress", reason="local_work_started",
        )

    def test_offer_is_world_addressed_stable_and_idempotent(self):
        self.assertEqual(self.agenda.offer(
            self.incident, priority=40, kind="cargo_shift",
        ), self.item)
        self.assertEqual(len(self.agenda.tasks), 1)
        self.assertEqual(self.item["status"], "offered")
        for wrong in (
            world_event(13, "cargo_shift", "#99"),
            {**self.incident, "event_id": ""},
            {**self.incident, "sequence": True},
            {**self.incident, "game_time": float("nan")},
        ):
            with self.assertRaises((ValueError, PermissionError)):
                self.agenda.offer(wrong, priority=40, kind="cargo_shift")
        with self.assertRaises(ValueError):
            self.agenda.offer(self.incident, priority=101, kind="cargo_shift")
        with self.assertRaises(ValueError):
            self.agenda.offer(self.incident, priority=40, kind="atmosphere_alarm")

    def test_deferral_does_not_wake_on_replayed_or_unrelated_events(self):
        self.accept()
        self.agenda.defer(
            self.item["task_id"], reason="uncertain cargo rigging",
            event_kinds=("cargo_review",), after_sequence=12,
        )
        self.assertEqual(self.item["status"], "deferred")
        self.assertEqual(self.agenda.ready(), [])
        self.assertEqual(self.agenda.observe(self.incident), [])
        self.assertEqual(self.agenda.observe(world_event(13, "bridge_notice")), [])
        with self.assertRaises(PermissionError):
            self.agenda.observe(world_event(14, "cargo_review", "#99"))
        self.assertEqual(self.agenda.observe(world_event(15, "cargo_review")),
                         [self.item["task_id"]])
        self.assertEqual(self.item["status"], "accepted")
        self.assertIsNone(self.item["reconsider"])
        self.assertEqual(self.agenda.observe(world_event(15, "cargo_review")), [])
        self.assertEqual(len(self.agenda.ready()), 1)

    def test_blocked_task_survives_checkpoint_and_wakes_on_supply(self):
        self.accept()
        self.agenda.defer(
            self.item["task_id"], blocked=True,
            reason="world refused missing consumable",
            event_kinds=("supply_replenished", "duty_review"),
            after_sequence=16,
        )
        persisted = json.loads(json.dumps(self.record))
        restored = AgentAgenda(persisted, role="mara", character_id="#31")
        self.assertEqual(restored.tasks[self.item["task_id"]]["status"], "blocked")
        self.assertEqual(restored.observe(world_event(16, "supply_replenished")), [])
        self.assertEqual(restored.observe(world_event(17, "supply_replenished")),
                         [self.item["task_id"]])
        self.assertEqual(restored.task(self.item["task_id"])["status"], "accepted")

    def test_replaying_history_after_checkpoint_does_not_repeat_reconsideration(self):
        self.accept()
        self.agenda.defer(
            self.item["task_id"], reason="seek fresh inspection",
            event_kinds=("duty_review",), after_sequence=12,
        )
        self.assertEqual(self.agenda.observe(world_event(20, "duty_review")),
                         [self.item["task_id"]])
        saved = json.loads(json.dumps(self.record))
        restored = AgentAgenda(saved, role="mara", character_id="#31")
        self.assertEqual(restored.observe(world_event(20, "duty_review")), [])
        self.assertEqual(restored.task(self.item["task_id"])["status"], "accepted")

    def test_priority_selection_and_interrupt_resume(self):
        other = self.agenda.offer(
            world_event(9, "cargo_review"), priority=90, kind="cargo_review",
        )
        self.accept()
        self.agenda.set_status(other["task_id"], "accepted",
                               reason="higher priority duty claimed")
        ranked = self.agenda.ready()
        self.assertEqual([i["task_id"] for i in ranked],
                         [other["task_id"], self.item["task_id"]])
        self.assertTrue(self.agenda.interrupt(self.item["task_id"], urgent=other))
        self.assertEqual(self.item["status"], "interrupted")
        self.agenda.set_status(other["task_id"], "in_progress",
                               reason="urgent work started")
        self.agenda.set_status(other["task_id"], "completed",
                               reason="world receipt confirmed",
                               effects=["oxevt-v2-effect-0001"])
        self.agenda.set_status(self.item["task_id"], "in_progress",
                               reason="resuming after urgent work")
        self.assertFalse(self.agenda.interrupt(self.item["task_id"], urgent=other))
        self.agenda.set_status(self.item["task_id"], "completed",
                               reason="own world receipt confirmed",
                               effects=["c01-0003"])
        self.assertEqual(self.agenda.ready(), [])
        self.assertEqual(self.item["world_effects"], ["c01-0003"])

    def test_completed_task_cannot_be_reopened_or_unverified(self):
        self.accept()
        with self.assertRaises(ValueError):
            self.agenda.set_status(self.item["task_id"], "completed",
                                   reason="agent guessed success")
        self.agenda.set_status(self.item["task_id"], "completed",
                               reason="independently verified",
                               effects=["c01-0002"])
        with self.assertRaises(ValueError):
            self.agenda.set_status(self.item["task_id"], "accepted",
                                   reason="retry old outcome")
        self.assertEqual(self.agenda.offer(
            self.incident, priority=40, kind="cargo_shift",
        )["status"], "completed")

    def test_malformed_deferrals_are_rejected(self):
        self.accept()
        for kinds in ((), ("",), (5,), ("x" * 65,)):
            with self.assertRaises(ValueError):
                self.agenda.defer(
                    self.item["task_id"], reason="need evidence",
                    event_kinds=kinds, after_sequence=12,
                )
        self.assertEqual(self.item["status"], "in_progress")
        with self.assertRaises(ValueError):
            self.agenda.defer(
                self.item["task_id"], reason="",
                event_kinds=("duty_review",), after_sequence=12,
            )

    def test_wrong_identity_and_corrupted_checkpoint_fail_closed(self):
        state = json.loads(json.dumps(self.record))
        with self.assertRaises(PermissionError):
            AgentAgenda(state, role="teo", character_id="#31")
        with self.assertRaises(PermissionError):
            AgentAgenda(state, role="mara", character_id="#32")
        state["tasks"][self.item["task_id"]]["character_id"] = "#99"
        with self.assertRaises(PermissionError):
            AgentAgenda(state, role="mara", character_id="#31")

    def test_deferral_history_is_bounded_and_reason_preserved(self):
        self.accept()
        for i in range(45):
            self.agenda.defer(
                self.item["task_id"], reason="deferred inspection",
                event_kinds=("duty_review",), after_sequence=12 + i * 2,
            )
            self.agenda.observe(world_event(13 + i * 2, "duty_review"))
            self.agenda.set_status(self.item["task_id"], "in_progress",
                                   reason="resumed")
        self.assertLessEqual(len(self.item["history"]), 32)
        self.assertEqual(self.item["revisions"], 2 + 45 * 3)
        self.assertEqual(self.item["status"], "in_progress")

    def test_offered_task_cannot_be_cancelled_as_world_completion(self):
        with self.assertRaises(ValueError):
            self.agenda.set_status(self.item["task_id"], "completed",
                                   reason="world action nonexistent",
                                   effects=["not-an-event"])
        self.assertEqual(self.item["status"], "offered")
