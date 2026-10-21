"""Authenticated actor-private journal generation and prefix continuity.

Journal proofs are received only from the ordinary puppeted Evennia command.
The hash chain detects changed/rewound journal prefixes; it never represents
current permissions, equipment state, or private Concordia cognition.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import math
import re
import secrets

from ox_ai.ports.evennia.client import EvenniaWebSocketClient


_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_ACTOR = re.compile(r"#[1-9][0-9]*")


def journal_seed(generation: str, actor_dbref: str) -> str:
    if not isinstance(generation, str) or _HEX32.fullmatch(generation) is None:
        raise ValueError("Invalid world journal generation")
    if not isinstance(actor_dbref, str) or _ACTOR.fullmatch(actor_dbref) is None:
        raise ValueError("Invalid world journal actor")
    return hashlib.sha256(
        f"ox-journal-v1:{generation}:{actor_dbref}".encode("utf-8")
    ).hexdigest()


def continue_digest(previous: str, event: dict) -> str:
    if not isinstance(previous, str) or _HEX64.fullmatch(previous) is None:
        raise ValueError("Invalid historical prefix digest")
    if not isinstance(event, dict) or set(event) != {
        "event_id", "sequence", "recipient_dbref", "sender_dbref",
        "kind", "data", "text", "game_time",
    }:
        raise ValueError("Malformed canonical world journal event")
    encoded = json.dumps(
        event, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(bytes.fromhex(previous) + encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class JournalCertificate:
    actor_dbref: str
    generation: str
    requested_cursor: int
    prefix_digest: str | None
    head_cursor: int
    head_digest: str

    @classmethod
    def parse(
        cls, value: object, *, actor_dbref: str, cursor: int, nonce: str,
    ) -> "JournalCertificate":
        if (not isinstance(actor_dbref, str)
                or _ACTOR.fullmatch(actor_dbref) is None
                or type(cursor) is not int or cursor < 0
                or not isinstance(nonce, str)
                or _HEX32.fullmatch(nonce) is None):
            raise ValueError("Invalid historical continuity challenge")
        if not isinstance(value, dict) or set(value) != {
            "version", "actor_dbref", "generation", "requested_cursor",
            "prefix_digest", "head_cursor", "head_digest", "nonce",
        }:
            raise ValueError("Malformed journal continuity certificate")
        if type(value["version"]) is not int or value["version"] != 1:
            raise ValueError("Unknown journal continuity version")
        if value["nonce"] != nonce:
            raise PermissionError("Journal response belongs to another nonce")
        if value["actor_dbref"] != actor_dbref:
            raise PermissionError("Journal response belongs to another character")
        if value["requested_cursor"] != cursor or type(value["requested_cursor"]) is not int:
            raise PermissionError("Journal response covers another historical cursor")
        generation = value["generation"]
        prefix = value["prefix_digest"]
        head = value["head_digest"]
        head_cursor = value["head_cursor"]
        if (not isinstance(generation, str)
                or _HEX32.fullmatch(generation) is None
                or type(head_cursor) is not int or head_cursor < 0
                or not isinstance(head, str) or _HEX64.fullmatch(head) is None
                or prefix is not None
                and (not isinstance(prefix, str) or _HEX64.fullmatch(prefix) is None)):
            raise ValueError("Malformed journal epoch or digest")
        genesis = journal_seed(generation, actor_dbref)
        if head_cursor == 0 and head != genesis:
            raise ValueError("Empty journal has a non-genesis head")
        if cursor == 0 and prefix != genesis:
            raise ValueError("Empty cursor has a non-genesis prefix")
        if cursor > head_cursor and prefix is not None:
            raise ValueError("Journal cannot attest a future prefix")
        if cursor == head_cursor and prefix is not None and prefix != head:
            raise ValueError("Head and prefix certificates disagree")
        return cls(actor_dbref, generation, cursor, prefix, head_cursor, head)

    def require_prefix(self, generation: str, cursor: int, digest: str) -> None:
        """Refuse a rewound, reset or changed historical actor prefix."""
        if self.generation != generation:
            raise RuntimeError("World journal generation changed since checkpoint")
        if self.requested_cursor != cursor or self.prefix_digest != digest:
            raise RuntimeError("World journal diverges from retained evidence")
        if self.head_cursor < cursor:
            raise RuntimeError("World journal is behind handler evidence cursor")


class WorldJournalPort:
    """Read authoritative actor prefix proofs without replaying older events."""

    def __init__(self, client: EvenniaWebSocketClient, *, timeout: float = 10.0):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError("Journal request timeout must be bounded")
        self.client = client
        self.timeout = float(timeout)

    async def attest(self, cursor: int) -> JournalCertificate:
        if not self.client.authenticated:
            raise PermissionError("Journal proof requires authenticated puppeting")
        if type(cursor) is not int or cursor < 0:
            raise ValueError("Invalid journal attestation cursor")
        nonce = secrets.token_hex(16)
        await self.client.send_line(f"oxjournal {nonce} {cursor}")

        def matching(packet) -> bool:
            if packet.kind != "ox_journal_proof":
                return False
            if len(packet.args) != 1 or not isinstance(packet.args[0], str):
                return False
            try:
                data = json.loads(packet.args[0])
            except (TypeError, ValueError):
                return False
            return isinstance(data, dict) and data.get("nonce") == nonce

        try:
            async with asyncio.timeout(self.timeout):
                packet = await self.client.receive_matching(
                    matching, frame_budget=256,
                )
        except TimeoutError:
            raise TimeoutError("No authenticated journal continuity response") from None
        raw = packet.args[0]
        if len(raw.encode("utf-8")) > 1024:
            raise ValueError("Oversized world journal certificate")
        return JournalCertificate.parse(
            json.loads(raw), actor_dbref=self.client.character_dbref,
            cursor=cursor, nonce=nonce,
        )
