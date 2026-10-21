"""Authenticated exact-event lookup over an ordinary Evennia character socket.

This is a read of world-authored, recipient-addressed journal evidence, not a
local ledger and not permission to perform the historical operation again.
A missing response means absent OR not addressed to this character; it says
nothing about whether a ship-wide obligation has been resolved.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import math
import re
import secrets

from ox_ai.ports.evennia.client import EvenniaWebSocketClient

_EVENT_ID = re.compile(r"oxevt-(?:v2-)?[0-9]+")
_ACTOR = re.compile(r"#[1-9][0-9]*")
_NONCE = re.compile(r"[0-9a-f]{32}")
_RESPONSE_BYTES = 48000
_FIELDS = frozenset((
    "event_id", "sequence", "recipient_dbref", "sender_dbref", "kind",
    "data", "text", "game_time",
))


def _valid_id(event_id: object) -> bool:
    return (isinstance(event_id, str) and len(event_id) <= 64
            and _EVENT_ID.fullmatch(event_id) is not None)


@dataclass(frozen=True, slots=True)
class EventProof:
    """A typed result scoped to one challenged authenticated recipient."""

    actor_dbref: str
    event_id: str
    status: str
    event: dict | None

    @classmethod
    def parse(
        cls, payload: object, *, actor_dbref: str, event_id: str, nonce: str,
    ) -> "EventProof":
        if not (_valid_id(event_id) and isinstance(nonce, str)
                and _NONCE.fullmatch(nonce) is not None
                and isinstance(actor_dbref, str)
                and _ACTOR.fullmatch(actor_dbref) is not None):
            raise ValueError("Invalid event proof request")
        if not isinstance(payload, dict) or set(payload) != {
            "version", "nonce", "actor_dbref", "event_id", "status", "event",
        }:
            raise ValueError("Malformed world exact-event response")
        if type(payload["version"]) is not int or payload["version"] != 1:
            raise ValueError("Unknown exact-event protocol version")
        if payload["nonce"] != nonce:
            raise PermissionError("Event proof is not from this challenge")
        if payload["actor_dbref"] != actor_dbref:
            raise PermissionError("Exact event proof belongs to another character")
        if payload["event_id"] != event_id:
            raise PermissionError("Exact event response references another event")
        status = payload["status"]
        if status not in ("found", "missing", "oversized") or not isinstance(status, str):
            raise ValueError("Invalid world exact-event status")
        item = payload["event"]
        if status != "found":
            if item is not None:
                raise ValueError("Negative exact-event response supplied source data")
            return cls(actor_dbref, event_id, status, None)
        if not isinstance(item, dict) or set(item) != _FIELDS:
            raise ValueError("Malformed addressed event proof")
        if item["event_id"] != event_id or item["recipient_dbref"] != actor_dbref:
            raise PermissionError("World event source is not addressed to this actor")
        if type(item["sequence"]) is not int or item["sequence"] < 1:
            raise ValueError("Invalid historical world sequence")
        sender = item["sender_dbref"]
        if sender is not None and (
                not isinstance(sender, str) or _ACTOR.fullmatch(sender) is None):
            raise ValueError("Invalid event sender identity")
        kind = item["kind"]
        if not isinstance(kind, str) or not 1 <= len(kind) <= 64:
            raise ValueError("Invalid exact-event kind")
        timestamp = item["game_time"]
        if (type(timestamp) not in (int, float) or not math.isfinite(timestamp)
                or timestamp < 0):
            raise ValueError("Invalid world event timestamp")
        if not isinstance(item["text"], str) or not isinstance(item["data"], dict):
            raise ValueError("Invalid world evidence content")
        for key, value in item["data"].items():
            if (not isinstance(key, str) or not key.isidentifier()
                    or key.startswith("datum_")):
                raise ValueError("Malformed world event data key")
            if not (value is None or type(value) in (str, int, bool, float)):
                raise ValueError("Nested world event data is not supported")
            if type(value) is float and not math.isfinite(value):
                raise ValueError("Nonfinite world event datum")
        return cls(actor_dbref, event_id, status, item)

    def require(self, *, kind: str, sender_dbref: str | None = None) -> dict:
        """Fail closed unless the exact addressed event has the expected type."""
        if self.status == "oversized":
            raise RuntimeError("World exact-event response exceeds the wire bound")
        if self.event is None:
            raise LookupError("No addressed world evidence for the event ID")
        if self.event["kind"] != kind:
            raise PermissionError("World proof does not have the expected event kind")
        if sender_dbref is not None and self.event["sender_dbref"] != sender_dbref:
            raise PermissionError("World proof has an unexpected sender")
        return self.event


class WorldEventPort:
    """Look up old event IDs without paging all of the character's history."""

    def __init__(
        self, client: EvenniaWebSocketClient, *, timeout: float = 10.0,
    ) -> None:
        if (type(timeout) not in (int, float) or not math.isfinite(timeout)
                or not 0 < timeout <= 60):
            raise ValueError("Event lookup timeout must be finite and bounded")
        self.client = client
        self.timeout = float(timeout)

    async def lookup(self, event_id: str) -> EventProof:
        if not self.client.authenticated:
            raise PermissionError("Event lookup requires authenticated puppeting")
        if not _valid_id(event_id):
            raise ValueError("Invalid historical event identity")
        nonce = secrets.token_hex(16)
        await self.client.send_line(f"oxevent {nonce} {event_id}")

        def matching(packet) -> bool:
            if packet.kind != "ox_event_lookup":
                return False
            # A response without an attributable nonce is *not* this
            # request's evidence. Leave it buffered for another reader.
            if len(packet.args) != 1 or not isinstance(packet.args[0], str):
                return False
            try:
                message = json.loads(packet.args[0])
            except (ValueError, TypeError):
                return False
            return isinstance(message, dict) and message.get("nonce") == nonce

        try:
            async with asyncio.timeout(self.timeout):
                packet = await self.client.receive_matching(
                    matching, frame_budget=256,
                )
        except TimeoutError:
            raise TimeoutError("No authenticated exact-event reply") from None

        raw = packet.args[0]
        if len(raw.encode("utf-8")) > _RESPONSE_BYTES:
            raise ValueError("Oversized exact-event response")
        return EventProof.parse(
            json.loads(raw), actor_dbref=self.client.character_dbref,
            event_id=event_id, nonce=nonce,
        )
