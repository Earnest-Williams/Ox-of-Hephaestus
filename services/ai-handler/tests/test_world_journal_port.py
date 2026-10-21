"""Journal attestation client rejects foreign/stale/prefix-divergent proof."""
from __future__ import annotations

import json
import unittest

from ox_ai.ports.evennia.client import WebPacket
from ox_ai.ports.evennia.journal import (
    JournalCertificate, WorldJournalPort, continue_digest, journal_seed,
)


def sample(nonce="a" * 32, cursor=0, *, actor="#42", generation="e" * 32):
    genesis = journal_seed(generation, actor)
    return {
        "version": 1, "nonce": nonce, "actor_dbref": actor,
        "generation": generation, "requested_cursor": cursor,
        "prefix_digest": genesis if cursor == 0 else None,
        "head_cursor": 0, "head_digest": genesis,
    }


class CertificateParsingTests(unittest.TestCase):
    def test_empty_journal_and_rewind_or_generation_rejected(self):
        ask = dict(actor_dbref="#42", cursor=0, nonce="a" * 32)
        certificate = JournalCertificate.parse(sample(), **ask)
        certificate.require_prefix("e" * 32, 0, certificate.prefix_digest)
        for changed in (
            {"nonce": "b" * 32}, {"actor_dbref": "#78"},
            {"requested_cursor": 1}, {"version": 2},
            {"generation": "bad"}, {"head_digest": "bad"},
            {"prefix_digest": None}, {"extra": True},
            {"head_cursor": -1},
        ):
            with self.subTest(changed=changed), self.assertRaises(
                PermissionError if any(x in changed for x in
                                   ("nonce", "actor_dbref", "requested_cursor"))
                else ValueError
            ):
                JournalCertificate.parse({**sample(), **changed}, **ask)
        with self.assertRaises(RuntimeError):
            certificate.require_prefix("f" * 32, 0, certificate.prefix_digest)
        with self.assertRaises(RuntimeError):
            certificate.require_prefix("e" * 32, 0, "0" * 64)

    def test_valid_nonzero_prefix_and_foreign_cursor_must_not_be_trusted(self):
        event = {
            "event_id": "oxevt-v2-0008", "sequence": 8,
            "recipient_dbref": "#42", "sender_dbref": "#6",
            "kind": "world_notice", "data": {"ticket_id": "9"},
            "text": "original", "game_time": 234.0,
        }
        digest = continue_digest(journal_seed("e" * 32, "#42"), event)
        source = {**sample(cursor=8), "prefix_digest": digest,
                  "head_cursor": 8, "head_digest": digest}
        certificate = JournalCertificate.parse(
            source, actor_dbref="#42", cursor=8, nonce="a" * 32,
        )
        self.assertEqual(certificate.prefix_digest, digest)
        certificate.require_prefix("e" * 32, 8, digest)
        with self.assertRaises(RuntimeError):
            certificate.require_prefix("e" * 32, 7, digest)
        unknown = JournalCertificate.parse(
            {**source, "requested_cursor": 6, "prefix_digest": None},
            actor_dbref="#42", cursor=6, nonce="a" * 32,
        )
        with self.assertRaises(RuntimeError):
            unknown.require_prefix("e" * 32, 6, digest)


class FakeClient:
    character_dbref = "#42"

    def __init__(self, *, authenticated=True, mutation=None):
        self.authenticated = authenticated
        self.sent = []
        self.inbox = [
            WebPacket("ox_event", ({"recipient_dbref": "#42"},), {}),
            WebPacket("ox_journal_proof", (json.dumps(sample()),), {}),
        ]
        self.mutation = mutation

    async def send_line(self, line):
        self.sent.append(line)
        _, nonce, cursor = line.split()
        value = sample(nonce=nonce, cursor=int(cursor))
        if self.mutation:
            value = self.mutation(value)
        self.inbox.append(WebPacket(
            "ox_journal_proof", (json.dumps(value),), {},
        ))

    async def receive_matching(self, predicate, *, frame_budget=256):
        for i, packet in enumerate(self.inbox):
            if predicate(packet):
                self.inbox.pop(i)
                return packet
        raise RuntimeError("No authenticated certificate")


class WorldJournalPortTests(unittest.IsolatedAsyncioTestCase):
    async def test_nonce_and_actor_bound_without_consuming_old_packets(self):
        client = FakeClient()
        certificate = await WorldJournalPort(client).attest(0)
        self.assertEqual(certificate.actor_dbref, "#42")
        self.assertEqual(client.inbox[0].kind, "ox_event")
        self.assertEqual(client.inbox[1].kind, "ox_journal_proof")
        self.assertEqual(len(client.inbox), 2)
        second = await WorldJournalPort(client).attest(0)
        self.assertEqual(second.generation, certificate.generation)
        self.assertNotEqual(client.sent[0].split()[1], client.sent[1].split()[1])

    async def test_mismatch_unknown_version_and_unauthed_refused(self):
        for wrong, exception in (
            ({"actor_dbref": "#70"}, PermissionError),
            ({"requested_cursor": 1}, PermissionError),
            ({"head_digest": "untrusted"}, ValueError),
        ):
            with self.subTest(wrong=wrong), self.assertRaises(exception):
                await WorldJournalPort(
                    FakeClient(mutation=lambda proof: {**proof, **wrong})
                ).attest(0)
        blocked = FakeClient(authenticated=False)
        with self.assertRaises(PermissionError):
            await WorldJournalPort(blocked).attest(0)
        self.assertEqual(blocked.sent, [])
        with self.assertRaises(ValueError):
            await WorldJournalPort(FakeClient()).attest(-1)
        for timeout in (0, True, 61, float("nan")):
            with self.assertRaises(ValueError):
                WorldJournalPort(FakeClient(), timeout=timeout)
