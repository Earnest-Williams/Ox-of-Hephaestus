"""Typed, actor-bound Evennia clock read protocol and no-event aging."""
from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from ox_ai.ports.evennia.clock import WorldClockPort, WorldClockSample
from ox_ai.ports.evennia.client import WebPacket


class ClockProtocolTests(unittest.TestCase):
    def setUp(self):
        self.nonce = "e" * 32
        self.payload = {
            "version": 1, "nonce": self.nonce,
            "actor_dbref": "#42", "game_seconds": 500.25,
        }

    def test_exact_nonce_and_actor_binding(self):
        sample = WorldClockSample.parse(self.payload, actor_dbref="#42",
                                        nonce=self.nonce)
        self.assertEqual(sample.game_seconds, 500.25)
        for key, value in (("nonce", "f" * 32), ("actor_dbref", "#12")):
            changed = {**self.payload, key: value}
            with self.subTest(key=key), self.assertRaises(PermissionError):
                WorldClockSample.parse(changed, actor_dbref="#42",
                                       nonce=self.nonce)
        for value in (-1, True, float("inf"), float("nan"), "now"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                WorldClockSample.parse(
                    {**self.payload, "game_seconds": value},
                    actor_dbref="#42", nonce=self.nonce)

    def test_unknown_field_and_version_rejected(self):
        with self.assertRaises(ValueError):
            WorldClockSample.parse({**self.payload, "hidden_state": "secret"},
                                   actor_dbref="#42", nonce=self.nonce)
        with self.assertRaises(ValueError):
            WorldClockSample.parse({**self.payload, "version": 2},
                                   actor_dbref="#42", nonce=self.nonce)


class FakeClockClient:
    def __init__(self, *, authenticated=True, actor="#42", wrong_actor=False):
        self.authenticated = authenticated
        self.character_dbref = actor
        self.sent = []
        self.wrong_actor = wrong_actor
        self.seen = []
        self.pending = [WebPacket("ox_event", ("unrelated private message",), {})]

    async def send_line(self, command):
        self.sent.append(command)
        nonce = command.split(" ")[1]
        payload = {
            "version": 1, "nonce": nonce,
            "actor_dbref": "#99" if self.wrong_actor else self.character_dbref,
            "game_seconds": 86400.0,
        }
        self.pending.append(WebPacket("ox_clock", (json.dumps(payload),), {}))

    async def receive_matching(self, predicate, *, frame_budget=256):
        for i, packet in enumerate(self.pending):
            if predicate(packet):
                self.pending.pop(i)
                return packet
        raise RuntimeError("Expected a matching clock reply")


class ClockPortTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_clock_preserves_unrelated_packets(self):
        client = FakeClockClient()
        sample = await WorldClockPort(client).observe()
        self.assertEqual(sample.game_seconds, 86400.0)
        self.assertEqual(sample.actor_dbref, "#42")
        self.assertEqual(client.sent[0].split(" ")[0], "oxclock")
        self.assertEqual(client.pending[0].kind, "ox_event")

    async def test_not_authenticated_or_wrong_actor_fails_closed(self):
        client = FakeClockClient(authenticated=False)
        with self.assertRaises(PermissionError):
            await WorldClockPort(client).observe()
        self.assertEqual(client.sent, [])
        other = FakeClockClient(wrong_actor=True)
        with self.assertRaises(PermissionError):
            await WorldClockPort(other).observe()
