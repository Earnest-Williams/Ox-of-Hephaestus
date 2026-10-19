"""G3d: optional autonomous rounds remain world-owned and evidence-gated."""
from __future__ import annotations

from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.event_journal import inbox
from world.independent_rounds import (
    schedule_rounds, tick_rounds, note_round_inspection,
)
from world.models import CrewEvent, WorkReceipt
from world.work_actions import execute_work


class IndependentRoundWorldTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()
        self.roster = self.ship["roster"]
        self.mara = self.ship["cargo"]
        self.teo = self.ship["environment"]
        schedule_rounds(period_game_seconds=10)

    def test_idle_zero_events_then_coalesced_time_windows_without_secret_leak(self):
        self.assertFalse(tick_rounds(now_game_time=100))
        self.assertFalse(tick_rounds(now_game_time=109.9))
        self.assertTrue(tick_rounds(now_game_time=140))
        self.assertEqual(int(self.roster.db.ox_round_cycle), 4)
        self.assertEqual(int(self.ship["cradle"].db.ox_round_wear), 4)
        self.assertEqual(int(self.ship["scrubber"].db.ox_round_wear), 4)
        self.assertFalse(tick_rounds(now_game_time=140))
        for crew in (self.ship["officer"], self.ship["watch"],
                     self.ship["chief"], self.mara, self.teo):
            events = [e for e in inbox(crew) if e["kind"] == "crew_round_window"]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["data"],
                             {"cycle": 4, "missed_windows": 3})
            self.assertNotIn("wear", str(events[0]))
        with self.assertRaises(RuntimeError):
            schedule_rounds(period_game_seconds=10)

    def test_fresh_local_evidence_role_guard_repeat_and_preventive_repair(self):
        tick_rounds(now_game_time=100)
        tick_rounds(now_game_time=140)
        other = execute_work(self.teo, "1" * 32, "round_report",
                             arguments={"station": "cargo"})
        self.assertEqual(other["status"], "failed")
        before = execute_work(self.mara, "2" * 32, "round_report",
                              arguments={"station": "cargo"})
        self.assertEqual(before["status"], "failed")
        note_round_inspection(self.mara, self.ship["cradle"])
        receipt = execute_work(self.mara, "3" * 32, "round_report",
                               arguments={"station": "cargo"})
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(execute_work(self.mara, "3" * 32, "round_report",
                                      arguments={"station": "cargo"}), receipt)
        self.assertEqual(execute_work(self.mara, "4" * 32, "round_report",
                                      arguments={"station": "cargo"})["status"], "failed")
        messages = [e for e in inbox(self.ship["officer"])
                    if e["kind"] == "crew_round_report"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["data"]["finding"], "maintenance_due")
        self.assertEqual(execute_work(self.teo, "5" * 32, "retension",
                                      "cargo")["status"], "failed")
        self.assertEqual(execute_work(self.mara, "6" * 32, "retension",
                                      "cargo")["status"], "succeeded")
        self.assertEqual(int(self.ship["cradle"].db.ox_round_wear), 0)
        self.assertEqual(execute_work(self.mara, "6" * 32, "retension",
                                      "cargo")["status"], "succeeded")
        self.assertEqual(execute_work(self.mara, "7" * 32, "retension",
                                      "cargo")["status"], "failed")

    def test_second_event_failure_does_not_publish_or_record_report(self):
        from world import independent_rounds
        tick_rounds(now_game_time=100)
        tick_rounds(now_game_time=140)
        note_round_inspection(self.teo, self.ship["scrubber"])
        original = independent_rounds.emit
        calls = 0
        def fail_second(*a, **kw):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("journal rollback")
            return original(*a, **kw)
        before = CrewEvent.objects.count()
        with patch.object(independent_rounds, "emit", side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                execute_work(self.teo, "8" * 32, "round_report",
                             arguments={"station": "scrubber"})
        self.assertEqual(CrewEvent.objects.count(), before)
        self.assertFalse(WorkReceipt.objects.filter(pk="8" * 32).exists())
        receipt = execute_work(self.teo, "8" * 32, "round_report",
                               arguments={"station": "scrubber"})
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(execute_work(self.teo, "9" * 32, "purge",
                                      "scrubber")["status"], "succeeded")
        self.assertEqual(int(self.ship["scrubber"].db.ox_round_wear), 0)

    def test_inspections_expire_on_world_time_and_world_changes(self):
        tick_rounds(now_game_time=100)
        tick_rounds(now_game_time=140)
        note_round_inspection(self.mara, self.ship["cradle"])
        tick_rounds(now_game_time=150)
        self.assertEqual(execute_work(self.mara, "a" * 32, "round_report",
                                      arguments={"station": "cargo"})["status"], "failed")
        note_round_inspection(self.mara, self.ship["cradle"])
        self.assertEqual(execute_work(self.mara, "b" * 32, "round_report",
                                      arguments={"station": "cargo"})["status"], "succeeded")
        self.assertEqual(execute_work(self.mara, "c" * 32, "retension",
                                      "cargo")["status"], "succeeded")
