"""Authenticated world event proof port, replay and cross-recipient denial."""
from __future__ import annotations

import copy
import json
import unittest

from ox_ai.ports.evennia.client import WebPacket
from ox_ai.ports.evennia.evidence import EventProof, WorldEventPort


def original(event_id="oxevt-v2-0012", *, actor="#42"):
    return {
        "event_id": event_id, "sequence": 12, "recipient_dbref": actor,
        "sender_dbref": "#7", "kind": "release_request",
        "data": {"alarm_id": "p01-old", "observed": True},
        "text": "World-recorded approval requested", "game_time": 800.25,
    }


def reply(nonce="a" * 32, *, actor="#42", event_id="oxevt-v2-0012",
          status="found", event=None):
    return {
        "version": 1, "nonce": nonce, "actor_dbref": actor,
        "event_id": event_id, "status": status,
        "event": original(event_id, actor=actor) if event is None and status == "found"
                 else event,
    }


class ExactEventProofTests(unittest.TestCase):
    def setUp(self):
        self.ask = {
            "actor_dbref": "#42", "event_id": "oxevt-v2-0012", "nonce": "a" * 32,
        }

    def test_correct_proof_checks_type_and_sender(self):
        result = EventProof.parse(reply(), **self.ask)
        self.assertEqual(result.status, "found")
        self.assertEqual(result.require(kind="release_request")["sequence"], 12)
        self.assertEqual(
            result.require(kind="release_request", sender_dbref="#7")["kind"],
            "release_request",
        )
        with self.assertRaises(PermissionError):
            result.require(kind="release_granted")
        with self.assertRaises(PermissionError):
            result.require(kind="release_request", sender_dbref="#99")

    def test_foreign_actor_wrong_event_stale_challenge_and_fields_fail(self):
        for change, exc in (
            ({"nonce": "b" * 32}, PermissionError),
            ({"actor_dbref": "#99"}, PermissionError),
            ({"event_id": "oxevt-v2-0011"}, PermissionError),
            ({"version": 2}, ValueError),
            ({"version": True}, ValueError),
            ({"extra": "untrusted"}, ValueError),
            ({"status": "claimed_verified"}, ValueError),
            ({"status": "missing", "event": original()}, ValueError),
        ):
            with self.subTest(change=change), self.assertRaises(exc):
                EventProof.parse({**reply(), **change}, **self.ask)

    def test_nested_or_unaddressed_source_is_not_a_proof(self):
        item = original()
        variants = (
            ({"recipient_dbref": "#99"}, PermissionError),
            ({"event_id": "oxevt-v2-0009"}, PermissionError),
            ({"sequence": True}, ValueError),
            ({"sequence": -1}, ValueError),
            ({"sender_dbref": "not-an-actor"}, ValueError),
            ({"kind": ""}, ValueError),
            ({"data": {"nested": {"world": "secret"}}}, ValueError),
            ({"data": {"datum_fake": 1}}, ValueError),
            ({"data": {"float": float("nan")}}, ValueError),
            ({"game_time": float("inf")}, ValueError),
            ({"text": 17}, ValueError),
        )
        for change, exc in variants:
            with self.subTest(change=change), self.assertRaises(exc):
                EventProof.parse(
                    reply(event={**item, **change}), **self.ask,
                )

    def test_negative_results_are_not_world_resolution_proofs(self):
        for status in ("missing", "oversized"):
            result = EventProof.parse(
                reply(status=status), **self.ask,
            )
            self.assertIsNone(result.event)
            with self.assertRaises(LookupError if status == "missing" else RuntimeError):
                result.require(kind="release_request")


class FakeEventClient:
    authenticated = True
    character_dbref = "#42"

    def __init__(self, response=None, *, authenticated=True):
        self.authenticated = authenticated
        self.pending = [
            WebPacket("ox_event", ({"recipient_dbref": "#42"},), {}),
            WebPacket("ox_event_lookup", (json.dumps(
                reply("f" * 32, status="missing"),
            ),), {}),
            WebPacket("ox_event_lookup", ("malformed unrelated",), {}),
        ]
        self.sent = []
        self.response = response

    async def send_line(self, command):
        self.sent.append(command)
        _, nonce, event_id = command.split()
        data = reply(nonce, event_id=event_id)
        if self.response is not None:
            data = self.response(copy.deepcopy(data))
        self.pending.append(
            WebPacket("ox_event_lookup", (json.dumps(data),), {}),
        )

    async def receive_matching(self, predicate, *, frame_budget=256):
        for i, packet in enumerate(self.pending):
            if predicate(packet):
                self.pending.pop(i)
                return packet
        raise RuntimeError("No matching event lookup reply")


class WorldEventPortTests(unittest.IsolatedAsyncioTestCase):
    async def test_authentic_world_lookup_preserves_unrelated_and_old_packets(self):
        client = FakeEventClient()
        result = await WorldEventPort(client).lookup("oxevt-v2-0012")
        self.assertEqual(result.status, "found")
        self.assertEqual(result.require(kind="release_request")["data"]["alarm_id"],
                         "p01-old")
        self.assertEqual(client.sent[0].split()[0], "oxevent")
        self.assertEqual(client.pending[0].kind, "ox_event")
        self.assertEqual(client.pending[1].kind, "ox_event_lookup")
        self.assertEqual(len(client.pending), 3)
        # Retrying is a separate challenge. Stale packets cannot satisfy it.
        another = await WorldEventPort(client).lookup("oxevt-v2-0012")
        self.assertEqual(another.require(kind="release_request")["sequence"], 12)
        self.assertNotEqual(client.sent[0].split()[1], client.sent[1].split()[1])

    async def test_actor_and_event_mismatch_fail_closed_after_nonce_match(self):
        for change in (
            {"actor_dbref": "#99"},
            {"event_id": "oxevt-v2-0005"},
            {"event": original(actor="#99")},
        ):
            with self.subTest(change=change):
                client = FakeEventClient(
                    lambda response: {**response, **change},
                )
                with self.assertRaises(PermissionError):
                    await WorldEventPort(client).lookup("oxevt-v2-0012")

    async def test_unverified_actors_bad_ids_and_invalid_timeout_refused(self):
        blocked = FakeEventClient(authenticated=False)
        with self.assertRaises(PermissionError):
            await WorldEventPort(blocked).lookup("oxevt-v2-0012")
        self.assertEqual(blocked.sent, [])
        for event_id in ("another-actor", "oxevt-v2-abc", "oxevt-1\nlook",
                         "oxevt-v2-" + "1" * 65):
            with self.subTest(event_id=event_id), self.assertRaises(ValueError):
                await WorldEventPort(FakeEventClient()).lookup(event_id)
        for timeout in (0, -1, 61, True, float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                WorldEventPort(FakeEventClient(), timeout=timeout)

    async def test_negative_result_and_oversized_payload_refused(self):
        for status in ("missing", "oversized"):
            client = FakeEventClient(
                lambda data: {**data, "status": status, "event": None},
            )
            result = await WorldEventPort(client).lookup("oxevt-v2-0012")
            self.assertEqual(result.status, status)
            self.assertIsNone(result.event)
        client = FakeEventClient(
            lambda data: {**data, "event": {
                **data["event"], "text": "X" * 50000,
            }},
        )
        with self.assertRaisesRegex(ValueError, "Oversized"):
            await WorldEventPort(client).lookup("oxevt-v2-0012")
