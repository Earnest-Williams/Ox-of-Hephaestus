"""Per-character persistent agenda, separate from world-owned obligations.

An agenda is an *intention ledger*: it can accept, defer, reconsider,
preempt and resume work the CHARACTER legitimately learned about. It cannot
create a WorkOrder, grant a role, move a person or assert a physical success.
The world remains authoritative for facts, permissions and action receipts.

The caller persists this JSON-compatible record with the character's
Concordia snapshot before treating a change as durable.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

VERSION = 1
ACTIVE = frozenset({"offered", "accepted", "in_progress", "interrupted"})
WAITING = frozenset({"deferred", "blocked"})
TERMINAL = frozenset({"completed", "declined", "delegated", "escalated"})
STATES = ACTIVE | WAITING | TERMINAL
ALLOWED = {
    "offered": frozenset({"accepted", "deferred", "declined", "escalated"}),
    "accepted": frozenset({"in_progress", "deferred", "blocked", "declined",
                           "delegated", "escalated"}),
    "in_progress": frozenset({"interrupted", "deferred", "blocked",
                              "completed", "declined", "escalated"}),
    "interrupted": frozenset({"in_progress", "deferred", "blocked",
                              "completed", "escalated"}),
    "deferred": frozenset({"accepted", "escalated"}),
    "blocked": frozenset({"accepted", "escalated"}),
    "completed": frozenset(),
    "declined": frozenset(),
    "delegated": frozenset(),
    "escalated": frozenset(),
}


def _sequence(event: Mapping) -> int:
    value = event.get("sequence")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("A world event must carry its authoritative sequence")
    return value


def _game_time(event: Mapping) -> float:
    value = event.get("game_time")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("A world event must have a numeric game time")
    when = float(value)
    if not math.isfinite(when) or when < 0:
        raise ValueError("Invalid world game time")
    return when


def _reason(reason: str) -> str:
    if not isinstance(reason, str) or not 1 <= len(reason) <= 240:
        raise ValueError("Every disposition requires a bounded reason")
    return reason


class AgentAgenda:
    """Mutable JSON-serializable private agenda for exactly one world character."""

    def __init__(self, record: dict, *, role: str, character_id: str) -> None:
        if not isinstance(record, dict) or not isinstance(role, str):
            raise TypeError("Invalid agent agenda record")
        if not isinstance(character_id, str) or not character_id.startswith("#"):
            raise ValueError("A real character DB ref is required")
        if record:
            if (record.get("version") != VERSION
                    or record.get("role") != role
                    or record.get("character_id") != character_id
                    or not isinstance(record.get("tasks"), dict)):
                raise PermissionError("Agenda cannot be rebound to another character")
        else:
            record.update({
                "version": VERSION, "role": role, "character_id": character_id,
                "last_sequence": 0, "tasks": {},
            })
        self.record = record
        for item in record["tasks"].values():
            if (item.get("role") != role or
                    item.get("character_id") != character_id or
                    item.get("status") not in STATES):
                raise PermissionError("Corrupt or cross-character agenda task")

    @property
    def tasks(self) -> dict:
        return self.record["tasks"]

    def task(self, source_event_id: str) -> dict | None:
        return self.tasks.get(source_event_id)

    def offer(self, event: Mapping, *, priority: int, kind: str) -> dict:
        """Register exactly one role-addressed, authoritative observation."""
        if event.get("recipient_dbref") != self.record["character_id"]:
            raise PermissionError("Observation addressed to a different character")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("Missing event identity")
        if not isinstance(kind, str) or kind != event.get("kind"):
            raise ValueError("Task source does not match world event")
        if isinstance(priority, bool) or not isinstance(priority, int) or not 1 <= priority <= 100:
            raise ValueError("Priority must be a bounded local scheduling hint")
        seq = _sequence(event)
        stamp = _game_time(event)
        existing = self.tasks.get(event_id)
        if existing is not None:
            if (existing["source_kind"] != kind
                    or existing["source_sequence"] != seq):
                raise PermissionError("Event ID reused with different source metadata")
            return existing
        item = {
            "task_id": event_id,
            "role": self.record["role"],
            "character_id": self.record["character_id"],
            "source_kind": kind,
            "source_sequence": seq,
            "source_game_time": stamp,
            "priority": priority,
            "status": "offered",
            "reason": "observed_authoritative_event",
            "reconsider": None,
            "revisions": 0,
            "history": [],
            "world_effects": [],
        }
        self.tasks[event_id] = item
        self.record["last_sequence"] = max(self.record["last_sequence"], seq)
        return item

    def set_status(self, event_id: str, status: str, *, reason: str,
                   effects: Sequence[str] = ()) -> dict:
        item = self.tasks[event_id]
        prior = item["status"]
        if status not in ALLOWED[prior]:
            raise ValueError(f"Disallowed agenda transition {prior} -> {status}")
        why = _reason(reason)
        if effects:
            if status != "completed" or any(
                not isinstance(e, str) or not e for e in effects
            ):
                raise ValueError("Only completed work can attach verified world receipts")
        if status == "completed" and not effects:
            raise ValueError("A physical obligation needs world receipt evidence")
        item["status"] = status
        item["reason"] = why
        item["reconsider"] = None
        if effects:
            item["world_effects"] = list(effects)
        item["revisions"] += 1
        item["history"] = (item["history"] + [{
            "from": prior, "to": status, "reason": why,
        }])[-32:]
        return item

    def defer(self, event_id: str, *, reason: str,
              event_kinds: Sequence[str], after_sequence: int,
              blocked: bool = False) -> dict:
        """No silent skipping: a deferral MUST name future world evidence."""
        if (not event_kinds
                or any(not isinstance(k, str) or not k or len(k) > 64
                       for k in event_kinds)
                or isinstance(after_sequence, bool)
                or not isinstance(after_sequence, int)
                or after_sequence < 0):
            raise ValueError("Deferral must name valid future event kinds and cursor")
        item = self.tasks[event_id]
        after_sequence = max(after_sequence, item["source_sequence"])
        prior = item["status"]
        value = self.set_status(
            event_id, "blocked" if blocked else "deferred", reason=reason,
        )
        value["reconsider"] = {
            "event_kinds": sorted(set(event_kinds)),
            "after_sequence": after_sequence,
        }
        return value

    def observe(self, event: Mapping) -> list[str]:
        """Reconsider only on a *new*, correctly addressed world observation."""
        if event.get("recipient_dbref") != self.record["character_id"]:
            raise PermissionError("Cannot wake another character's agenda")
        seq = _sequence(event)
        _game_time(event)
        kind = event.get("kind")
        if not isinstance(kind, str):
            raise ValueError("Invalid world event kind")
        # Replay of inbox pages is normal; it must not refire a defer trigger.
        if seq <= self.record["last_sequence"]:
            return []
        self.record["last_sequence"] = seq
        awakened = []
        for item in self.tasks.values():
            trigger = item.get("reconsider")
            if (item["status"] in WAITING and isinstance(trigger, Mapping)
                    and seq > trigger["after_sequence"]
                    and kind in trigger["event_kinds"]):
                self.set_status(item["task_id"], "accepted",
                                reason="new_world_evidence:" + kind)
                awakened.append(item["task_id"])
        return awakened

    def ready(self) -> list[dict]:
        """Return locally selectable obligations in priority / oldest order."""
        return sorted(
            (item for item in self.tasks.values() if item["status"] in ACTIVE),
            key=lambda item: (-item["priority"], item["source_sequence"],
                              item["task_id"]),
        )

    def interrupt(self, event_id: str, *, urgent: dict) -> bool:
        """Suspend only between physical steps; never cancel a world request."""
        item = self.tasks[event_id]
        if (item["status"] != "in_progress" or
                urgent.get("status") not in ACTIVE or
                urgent["priority"] <= item["priority"]):
            return False
        self.set_status(event_id, "interrupted",
                        reason="higher_priority_world_obligation")
        return True
