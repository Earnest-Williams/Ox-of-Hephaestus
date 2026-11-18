"""Read-only world clock contract for an ordinary authenticated character."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase
from commands.clock import CmdOxClock
from commands.default_cmdsets import CharacterCmdSet
from world.bootstrap import build_ship
from world.live_clock import ShipDutyClock
from world.world_time_source import (
    WorldTimeSourceError, describe_time_alignment, require_game_seconds,
    scheduler_game_seconds,
)


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
        with patch("world.world_time_source.gametime.gametime", return_value=123456.5) as now:
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
        with patch("world.world_time_source.gametime.gametime") as now:
            with patch.object(actor, "msg") as send:
                command.func()
        now.assert_not_called()
        self.assertEqual(send.call_count, 1)
        self.assertNotIn("ox_clock", send.call_args.kwargs)

    def test_duty_dispatch_shares_exactly_one_world_time_sample(self):
        with (
            patch("world.world_time_source.gametime.gametime",
                  return_value=481.125) as source,
            patch("world.live_clock.tick_game_clock") as handover,
            patch("world.independent_rounds.tick_rounds") as rounds,
            patch("world.captain.tick_captain_obligations") as captain,
        ):
            ShipDutyClock.at_repeat(None)
        source.assert_called_once_with(absolute=True)
        handover.assert_called_once_with(now_game_time=481.125)
        rounds.assert_called_once_with(now_game_time=481.125)
        captain.assert_called_once_with(now_game_time=481.125)

    def test_invalid_scheduler_time_refuses_all_duty_effects(self):
        with (
            patch("world.world_time_source.gametime.gametime",
                  return_value=float("nan")),
            patch("world.live_clock.tick_game_clock") as handover,
            patch("world.independent_rounds.tick_rounds") as rounds,
            patch("world.captain.tick_captain_obligations") as captain,
        ):
            with self.assertRaises(WorldTimeSourceError):
                ShipDutyClock.at_repeat(None)
        handover.assert_not_called()
        rounds.assert_not_called()
        captain.assert_not_called()


class WorldTimeSourcePolicyTests(unittest.TestCase):
    def test_sampler_uses_existing_evennia_clock_once(self):
        with patch("world.world_time_source.gametime.gametime",
                   return_value=1536.625) as clock:
            self.assertEqual(scheduler_game_seconds(), 1536.625)
            clock.assert_called_once_with(absolute=True)

    def test_invalid_clock_rejected_without_implicit_coercion(self):
        for value in (None, False, True, "100", -0.5,
                      float("nan"), float("inf"), float("-inf"), 10 ** 1000):
            with self.subTest(value=repr(value)):
                with self.assertRaises(WorldTimeSourceError):
                    require_game_seconds(value)
        for value in (0, 0.0, 1, 2.5):
            self.assertEqual(require_game_seconds(value), float(value))

    def test_alignment_is_diagnostic_and_no_alternative_clock(self):
        self.assertEqual(describe_time_alignment(120.0, 100.0), {
            "schema_version": "ox.world-time-alignment/1",
            "scheduler_source": "evennia_absolute_game_time",
            "scheduler_seconds": 120.0,
            "committed_physics_seconds": 100.0,
            "uncommitted_delta_seconds": 20.0,
            "relation": "scheduler_ahead",
        })
        self.assertEqual(
            describe_time_alignment(100, 100)["relation"], "aligned")
        self.assertEqual(
            describe_time_alignment(100, 101)["relation"], "committed_ahead")
        missing = describe_time_alignment(120)
        self.assertEqual(missing["relation"], "physics_not_provided")
        self.assertIsNone(missing["committed_physics_seconds"])
        self.assertIsNone(missing["uncommitted_delta_seconds"])
        with self.assertRaises(WorldTimeSourceError):
            describe_time_alignment(100, "120")

    def test_explicit_round_override_never_samples_scheduler_clock(self):
        from world.independent_rounds import _game_time

        with patch("world.world_time_source.gametime.gametime") as source:
            self.assertEqual(_game_time(150.25), 150.25)
            source.assert_not_called()
        with self.assertRaises(WorldTimeSourceError):
            _game_time(-1)

