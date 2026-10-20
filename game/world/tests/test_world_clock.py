"""Read-only world clock contract for an ordinary authenticated character."""
from __future__ import annotations

import json
from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase
from commands.clock import CmdOxClock
from commands.default_cmdsets import CharacterCmdSet
from world.bootstrap import build_ship


class AuthenticatedWorldClockTests(EvenniaTestCase):
    def test_oxclock_is_on_character_allowlist_and_world_time_only(self):
        ship = build_ship()
        actor = ship["watch"]
        cmdset = CharacterCmdSet()
        cmdset.at_cmdset_creation()
        self.assertIn("oxclock", {command.key for command in cmdset.commands})

        command = CmdOxClock()
        command.caller = actor
        command.args = "e" * 32
        with patch("commands.clock.gametime.gametime", return_value=123456.5) as now:
            with patch.object(actor, "msg") as send:
                command.func()
            now.assert_called_once_with(absolute=True)
        self.assertEqual(send.call_count, 1)
        payload = json.loads(send.call_args.kwargs["ox_clock"][0][0])
        self.assertEqual(payload, {
            "version": 1, "nonce": "e" * 32,
            "actor_dbref": actor.dbref, "game_seconds": 123456.5,
        })
        self.assertNotIn("private", str(payload).lower())

    def test_bad_nonce_never_reads_clock_or_emits_clock_packet(self):
        actor = build_ship()["officer"]
        command = CmdOxClock()
        command.caller = actor
        command.args = "invalid"
        with patch("commands.clock.gametime.gametime") as now:
            with patch.object(actor, "msg") as send:
                command.func()
        now.assert_not_called()
        self.assertEqual(send.call_count, 1)
        self.assertNotIn("ox_clock", send.call_args.kwargs)
