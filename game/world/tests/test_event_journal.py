"""World-owned event journal: paging, privacy, migration, and rollback."""
from unittest.mock import patch

from django.db import transaction
from evennia.utils.test_resources import EvenniaTestCase

from commands.crew import CmdOxInbox
from world.bootstrap import build_ship
from world.event_journal import emit, inbox_page, migrate_legacy_events
from world.live_crew import fixture_setup, inbox
from world.models import CrewEvent


class CrewJournalTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        fixture_setup(scheduled_clock=True)
        self.ship = build_ship()
        self.pump = self.ship["pump"]
        self.lin = self.ship["officer"]
        self.ari = self.ship["watch"]

    def test_two_thousand_events_must_paginate_without_leak(self):
        for index in range(2100):
            recipient = self.lin if index % 3 else self.ari
            emit(self.pump, recipient, "journal_trial", data={"sample": index})
        self.assertEqual(CrewEvent.objects.count(), 2101)
        self.assertEqual(len(inbox(self.lin)), 128)
        self.assertEqual(len(inbox(self.ari)), 128)
        for actor, expected in ((self.lin, 1401), (self.ari, 700)):
            recovered = []
            cursor = 0
            while True:
                page = inbox_page(actor, after=cursor)
                self.assertLessEqual(page["count"], 128)
                self.assertTrue(all(
                    event["recipient_dbref"] == actor.dbref
                    for event in page["events"]
                ))
                recovered.extend(page["events"])
                self.assertGreaterEqual(page["next_cursor"], cursor)
                if not page["has_more"]:
                    break
                self.assertGreater(page["next_cursor"], cursor)
                cursor = page["next_cursor"]
            self.assertEqual(len(recovered), expected)
            self.assertEqual(len({e["event_id"] for e in recovered}), expected)
        self.assertEqual(inbox(self.ship["chief"]), [])

    def test_authenticated_command_reports_continuation(self):
        for index in range(140):
            emit(self.pump, self.lin, "journal_trial", data={"sample": index})
        command = CmdOxInbox()
        command.caller = self.lin
        command.args = "0"
        with patch.object(self.lin, "msg") as messages:
            command.func()
        frames = [call.kwargs for call in messages.call_args_list]
        events = [frame["ox_event"][0][0] for frame in frames if "ox_event" in frame]
        done = [frame["ox_inbox_done"][0][0] for frame in frames
                if "ox_inbox_done" in frame]
        self.assertEqual(len(events), 128)
        self.assertEqual(done[0]["version"], 2)
        self.assertTrue(done[0]["has_more"])
        self.assertGreater(done[0]["next_cursor"], 0)
        self.assertIn("datum_sample", events[1])
        command.args = str(done[0]["next_cursor"])
        with patch.object(self.lin, "msg") as second:
            command.func()
        frames = [call.kwargs for call in second.call_args_list]
        self.assertEqual(sum("ox_event" in frame for frame in frames), 13)
        self.assertFalse(frames[-1]["ox_inbox_done"][0][0]["has_more"])

    def test_migrate_old_attribute_without_renumbering(self):
        CrewEvent.objects.all().delete()
        self.pump.db.ox_event_journal_migrated = False
        original = {
            "event_id": "oxevt-0010", "recipient_dbref": self.ari.dbref,
            "sender_dbref": self.lin.dbref, "kind": "radio_alert",
            "data": {"alarm_id": "p01-old"},
            "text": "Old radio message", "game_time": 123.5,
        }
        self.pump.db.ox_private_events = [original]
        self.assertEqual(migrate_legacy_events(self.pump), 1)
        self.assertEqual(migrate_legacy_events(self.pump), 0)
        self.assertEqual(inbox_page(self.ari)["events"][0]["event_id"], "oxevt-0010")
        self.assertEqual(CrewEvent.objects.count(), 1)
        new = emit(self.pump, self.ari, "new_report")
        self.assertTrue(new["event_id"].startswith("oxevt-v2-"))
        self.assertEqual(len(inbox_page(self.ari)["events"]), 2)
        self.assertEqual(self.pump.db.ox_private_events, [original])

    def test_failed_transaction_does_not_emit(self):
        before = CrewEvent.objects.count()
        with patch.object(self.lin, "msg") as notifications:
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(RuntimeError):
                    with transaction.atomic():
                        emit(self.pump, self.lin, "rolled_back")
                        raise RuntimeError("Simulated rollback")
            notifications.assert_not_called()
        self.assertEqual(CrewEvent.objects.count(), before)
        with patch.object(self.lin, "msg") as notifications:
            with self.captureOnCommitCallbacks(execute=True):
                emit(self.pump, self.lin, "committed")
            notifications.assert_called_once()
        self.assertEqual(CrewEvent.objects.count(), before + 1)

    def test_invalid_cursors_fail_closed(self):
        for cursor in (-1, True, "0"):
            with self.assertRaises(ValueError):
                inbox_page(self.lin, after=cursor)
        with self.assertRaises(ValueError):
            inbox_page(self.lin, limit=129)
        with self.assertRaises(TypeError):
            emit(self.pump, self.lin, "bad", data={"nested": {"x": 1}})
