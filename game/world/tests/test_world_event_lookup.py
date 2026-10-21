"""Actor-scoped world exact event lookups: command, migration and refusal."""
from __future__ import annotations

import json
from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase

from commands.crew import CmdOxEvent
from commands.default_cmdsets import CharacterCmdSet
from world.bootstrap import build_ship
from world.event_journal import addressed_event, emit
from world.live_crew import fixture_setup
from world.models import CrewEvent


class AuthenticatedEventLookupTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        fixture_setup(scheduled_clock=True)
        self.ship = build_ship()
        self.pump = self.ship["pump"]
        self.lin = self.ship["officer"]
        self.ari = self.ship["watch"]

    def _command(self, actor, text):
        command = CmdOxEvent()
        command.caller = actor
        command.args = text
        with patch.object(actor, "msg") as sent:
            command.func()
        return sent

    @staticmethod
    def _reply(sent):
        assert sent.call_count == 1
        return json.loads(sent.call_args.kwargs["ox_event_lookup"][0][0])

    def test_world_only_returns_exact_recipient_events_without_mutation(self):
        own = emit(self.pump, self.lin, "private_note", data={"number": 3},
                   text="Lin's own observation")
        foreign = emit(self.pump, self.ari, "private_note",
                       text="Only Ari may read this")
        count = CrewEvent.objects.count()
        self.assertEqual(addressed_event(self.lin, own["event_id"]), own)
        self.assertEqual(addressed_event(self.ari, foreign["event_id"]), foreign)
        self.assertIsNone(addressed_event(self.lin, foreign["event_id"]))
        self.assertIsNone(addressed_event(self.ari, own["event_id"]))
        self.assertIsNone(addressed_event(self.lin, "oxevt-v2-999999999999"))
        self.assertEqual(CrewEvent.objects.count(), count)

    def test_ordinary_character_command_and_indistinguishable_missing(self):
        cmdset = CharacterCmdSet()
        cmdset.at_cmdset_creation()
        self.assertIn("oxevent", {cmd.key for cmd in cmdset.commands})
        nonce = "a" * 32
        own = emit(self.pump, self.lin, "evidence", data={"ticket_id": "abc"})
        foreign = emit(self.pump, self.ari, "secret", text="Ari private report")
        found = self._reply(self._command(
            self.lin, nonce + " " + own["event_id"],
        ))
        self.assertEqual(found, {
            "version": 1, "nonce": nonce, "actor_dbref": self.lin.dbref,
            "event_id": own["event_id"], "status": "found", "event": own,
        })
        alien = self._reply(self._command(
            self.lin, nonce + " " + foreign["event_id"],
        ))
        absent = self._reply(self._command(
            self.lin, nonce + " oxevt-v2-999999999999",
        ))
        self.assertEqual(alien["status"], absent["status"])
        self.assertEqual(alien["event"], absent["event"])
        self.assertEqual(alien["status"], "missing")
        self.assertNotIn("Ari private report", str(alien))
        self.assertEqual(
            self._reply(self._command(
                self.ari, nonce + " " + foreign["event_id"],
            ))["event"], foreign,
        )

    def test_invalid_commands_never_query_world(self):
        legitimate = emit(self.pump, self.lin, "evidence")["event_id"]
        attempts = (
            "", legitimate, "0" * 31 + " " + legitimate,
            "Z" * 32 + " " + legitimate,
            "a" * 32 + " ../../private",
            "a" * 32 + " oxevt-v2-1 extra",
            "a" * 32 + " oxevt-v2-" + "9" * 60,
        )
        with patch("world.event_journal.addressed_event") as query:
            for value in attempts:
                with self.subTest(command=value):
                    sent = self._command(self.lin, value)
                    self.assertEqual(sent.call_count, 1)
                    self.assertNotIn("ox_event_lookup", sent.call_args.kwargs)
            query.assert_not_called()
        for value in (None, "", "../abc", "oxevt-v2-abc", "oxevt-v2-" + "1" * 65):
            with self.subTest(value=value), self.assertRaises(ValueError):
                addressed_event(self.lin, value)
        with self.assertRaises(ValueError):
            addressed_event(None, legitimate)

    def test_oversized_event_fails_without_partial_source(self):
        own = emit(self.pump, self.lin, "log_report", text="short")
        CrewEvent.objects.filter(event_id=own["event_id"]).update(
            text="large-and-private:" + "Z" * 60000
        )
        sent = self._command(self.lin, "f" * 32 + " " + own["event_id"])
        answer = self._reply(sent)
        self.assertEqual(answer["status"], "oversized")
        self.assertIsNone(answer["event"])
        self.assertEqual(answer["event_id"], own["event_id"])
        self.assertNotIn("large-and-private", str(answer))

    def test_legacy_id_migration_is_available_by_exact_read(self):
        CrewEvent.objects.all().delete()
        self.pump.db.ox_event_journal_migrated = False
        self.pump.db.ox_private_events = [{
            "event_id": "oxevt-0010", "recipient_dbref": self.ari.dbref,
            "sender_dbref": self.lin.dbref, "kind": "release_request",
            "data": {"alarm_id": "old-incident"},
            "text": "Original legacy proof", "game_time": 123.0,
        }]
        recovered = addressed_event(self.ari, "oxevt-0010")
        self.assertEqual(recovered["event_id"], "oxevt-0010")
        self.assertEqual(recovered["text"], "Original legacy proof")
        self.assertIsNone(addressed_event(self.lin, "oxevt-0010"))
        result = self._reply(self._command(self.ari, "e" * 32 + " oxevt-0010"))
        self.assertEqual(result["event"], recovered)
        self.assertEqual(CrewEvent.objects.count(), 1)
