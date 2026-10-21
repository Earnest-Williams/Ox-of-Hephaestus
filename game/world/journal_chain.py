"""Versioned per-recipient cryptographic continuity for Ox's world journal.

Pure, frozen v1 representation shared with the one-time migration. Each
recipient's prefix depends on exactly the original world event records in
sequence order, not on any other character's private events. An epoch change
invalidates every saved local archive. This is not an authentication token:
the ordinary authenticated game session authenticates the world response.
"""
from __future__ import annotations

import hashlib
import json


VERSION = 1
EMPTY = "0" * 64


def canonical_event(event: dict) -> bytes:
    """Serialize one *complete*, world-authored, recipient-scoped event."""
    if set(event) != {
        "event_id", "sequence", "recipient_dbref", "sender_dbref",
        "kind", "data", "text", "game_time",
    }:
        raise ValueError("Historical journal event does not match v1 schema")
    return json.dumps(
        event, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def seed(generation: str, actor_dbref: str) -> str:
    if not isinstance(generation, str) or len(generation) != 32:
        raise ValueError("Invalid journal generation")
    if not isinstance(actor_dbref, str) or not actor_dbref.startswith("#"):
        raise ValueError("Invalid journal recipient")
    return hashlib.sha256(
        ("ox-journal-v1:" + generation + ":" + actor_dbref).encode("utf-8")
    ).hexdigest()


def append_digest(previous: str, event: dict) -> str:
    if not isinstance(previous, str) or len(previous) != 64:
        raise ValueError("Invalid journal prefix digest")
    return hashlib.sha256(
        bytes.fromhex(previous) + canonical_event(event)
    ).hexdigest()
