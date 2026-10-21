"""Authoritative actor/nonce journal prefix certificates and generation resets."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.db import transaction
from evennia.utils.test_resources import EvenniaTestCase

from commands.crew import CmdOxJournal
from commands.default_cmdsets import CharacterCmdSet
from world.bootstrap import build_ship
from world.event_journal import emit, journal_certificate, migrate_legacy_events
from world.journal_chain import append_digest, seed
from world.live_crew import fixture_setup
from world.models import CrewEvent, JournalEpoch


class JournalContinuityTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        fixture_setup(scheduled_clock=True)
        self.ship = build_ship()
        self.pump = self.ship["pump"]
        self.lin = self.ship["officer"]
        self.ari = self.ship["watch"]

    def _command(self, actor, args):
        command = CmdOxJournal()
        command.caller = actor
        command.args = args
        with patch.object(actor, "msg") as messages:
            command.func()
        return messages

    def test_recipient_prefixes_and_cross_recipient_cursor_never_leak(self):
        cmdset = CharacterCmdSet()
        cmdset.at_cmdset_creation()
        self.assertIn("oxjournal", {cmd.key for cmd in cmdset.commands})
        first = emit(self.pump, self.lin, "private_report", data={"case_id": "lin"})
        hidden = emit(self.pump, self.ari, "private_report",
                      data={"case_id": "ari"})
        latest = emit(self.pump, self.lin, "private_report", data={"step": 2})
        world = journal_certificate(self.lin, cursor=latest["sequence"])
        genesis = seed(world["generation"], self.lin.dbref)
        expected = genesis
        for item in (first, latest):
            expected = append_digest(expected, item)
        self.assertEqual(world["head_digest"], expected)
        self.assertEqual(world["prefix_digest"], expected)
        self.assertEqual(world["head_cursor"], latest["sequence"])
        self.assertEqual(
            journal_certificate(self.lin, cursor=first["sequence"])["prefix_digest"],
            append_digest(genesis, first),
        )
        other_cursor = journal_certificate(self.lin, cursor=hidden["sequence"])
        self.assertIsNone(other_cursor["prefix_digest"])
        self.assertNotIn(hidden["event_id"], str(other_cursor))
        self.assertEqual(
            journal_certificate(self.lin, cursor=0)["prefix_digest"], genesis,
        )
        nonce = "b" * 32
        reply = self._command(self.lin, nonce + " " + str(latest["sequence"]))
        self.assertEqual(reply.call_count, 1)
        payload = json.loads(
            reply.call_args.kwargs["ox_journal_proof"][0][0]
        )
        self.assertEqual(payload, {**world, "nonce": nonce})
        self.assertNotIn("ari", payload["head_digest"])

    def test_empty_actor_and_invalid_command_and_cursor(self):
        actor = self.ship["chief"]
        seen = journal_certificate(actor, cursor=0)
        self.assertEqual(seen["head_cursor"], 0)
        self.assertEqual(seen["head_digest"], seed(seen["generation"], actor.dbref))
        for args in ("", "a" * 32, "Z" * 32 + " 0",
                     "a" * 32 + " -1", "a" * 32 + " 0 extra",
                     "a" * 32 + " 01", "a" * 32 + " " + "1" * 50):
            with self.subTest(args=args):
                response = self._command(actor, args)
                self.assertEqual(response.call_count, 1)
                self.assertNotIn("ox_journal_proof", response.call_args.kwargs)
        for cursor in (-1, True, 1.5, "0"):
            with self.assertRaises(ValueError):
                journal_certificate(actor, cursor=cursor)
        with self.assertRaises(ValueError):
            journal_certificate(None, cursor=0)

    def test_rollback_keeps_head_and_reused_cursor_is_not_new_evidence(self):
        before = journal_certificate(self.lin, cursor=0)
        with self.assertRaisesRegex(RuntimeError, "rolled back"):
            with transaction.atomic():
                emit(self.pump, self.lin, "temporary_observation")
                raise RuntimeError("rolled back")
        self.assertEqual(
            journal_certificate(self.lin, cursor=0)["head_digest"],
            before["head_digest"],
        )
        committed = emit(self.pump, self.lin, "committed_observation")
        after = journal_certificate(self.lin, cursor=committed["sequence"])
        self.assertNotEqual(after["head_digest"], before["head_digest"])

    def test_operator_reset_rotates_epoch_and_old_prefix_cannot_match(self):
        prior = journal_certificate(self.lin, cursor=0)
        # Operator-only destructive journal reset, not an in-world command.
        CrewEvent.objects.all().delete()
        JournalEpoch.objects.update_or_create(
            id=1, defaults={"generation": "f" * 32},
        )
        newest = journal_certificate(self.lin, cursor=0)
        self.assertNotEqual(prior["generation"], newest["generation"])
        self.assertNotEqual(prior["prefix_digest"], newest["prefix_digest"])

    def test_legacy_import_reseals_unmodified_old_event(self):
        CrewEvent.objects.all().delete()
        self.pump.db.ox_event_journal_migrated = False
        self.pump.db.ox_private_events = [{
            "event_id": "oxevt-0007", "recipient_dbref": self.ari.dbref,
            "sender_dbref": self.lin.dbref, "kind": "private_legacy",
            "data": {"case_id": "old"}, "text": "original text",
            "game_time": 123.5,
        }]
        self.assertEqual(migrate_legacy_events(self.pump), 1)
        saved = CrewEvent.objects.get(event_id="oxevt-0007")
        self.assertEqual(len(saved.chain_hash), 64)
        proof = journal_certificate(self.ari, cursor=saved.sequence)
        self.assertEqual(proof["prefix_digest"], saved.chain_hash)
        self.assertEqual(migrate_legacy_events(self.pump), 0)
