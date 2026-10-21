"""Database-backed, recipient-scoped Ox event journal.

Normal Evennia character commands have no authority to query aggregate
history. Evennia owns this table; the independent AI handler only receives
addressed pages over the ordinary authenticated client connection.

The one-time legacy import is additive and idempotent. A fixture may clear
the journal only through the explicitly disposable operator setup.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
import re

from django.db import connection, transaction
from evennia.utils import gametime

from world.bootstrap import find_fixture
from world.models import CrewEvent

PAGE_SIZE = 128
SCHEMA_VERSION = 2
_EVENT_ID = re.compile(r"oxevt-[0-9]+")
# A public character may name a historical ID, but never a recipient.
# Keep legacy oxevt-0010 as well as sequence-derived oxevt-v2-0010.
_LOOKUP_EVENT_ID = re.compile(r"oxevt-(?:v2-)?[0-9]+")
# Fixed transaction-scoped namespace: all journal writers must use this lock.
# PostgreSQL sequences are allocated at INSERT, not in commit order.
_PG_JOURNAL_ADVISORY_LOCK = 0x4F584A4F55524E4C
_CAPTURED_EVENTS: ContextVar[list[dict] | None] = ContextVar(
    "ox_journal_action_events", default=None,
)


def _serialize_journal_transaction() -> None:
    """Hold the append lock through the *outermost* writer transaction commit.

    SQLite serializes writes already. Every PostgreSQL writer (including legacy
    import) must take this lock immediately before allocating an event sequence.
    It must never be released at a nested savepoint exit.
    """
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s)", [_PG_JOURNAL_ADVISORY_LOCK],
            )


@contextmanager
def capture_emitted_events():
    """Capture precisely this execution context's new authoritative events.

    An oxwork caller uses this around one ship operation so the durable receipt
    points to an event actually emitted by that operation, not an unrelated
    concurrently committed event with a nearby database sequence.
    """
    events: list[dict] = []
    token = _CAPTURED_EVENTS.set(events)
    try:
        yield events
    finally:
        _CAPTURED_EVENTS.reset(token)



def _details(data: Mapping | None) -> dict:
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise TypeError("World event details must be a mapping")
    result = {}
    for key, value in data.items():
        if not isinstance(key, str) or not key.isidentifier() or key.startswith("datum_"):
            raise ValueError("Invalid world observation field")
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise TypeError("World observation fields must be scalar")
        result[key] = value
    return result


def wire_event(event: dict) -> dict:
    """Flatten JSON details for Evennia's first-level-only OOB protocol."""
    result = {key: value for key, value in event.items() if key != "data"}
    for key, value in _details(event.get("data")).items():
        result["datum_" + key] = value
    return result


def _as_dict(record: CrewEvent) -> dict:
    return {
        "event_id": record.event_id,
        "sequence": int(record.sequence),
        "recipient_dbref": record.recipient_dbref,
        "sender_dbref": record.sender_dbref,
        "kind": record.kind,
        "data": dict(record.details),
        "text": record.text,
        "game_time": float(record.game_time),
    }


def migrate_legacy_events(pump=None) -> int:
    """Import P4e's P-01 Attribute history once without renumbering event IDs.

    Existing world databases can run their ordinary 'evennia migrate' first.
    The first journal access imports the old source, in original order. If
    interrupted, retries check unique event IDs and compare exact contents.
    """
    if pump is None:
        pump = find_fixture("pump-p01")
    if pump is None or pump.db.ox_event_journal_migrated:
        return 0
    count = 0
    with transaction.atomic():
        _serialize_journal_transaction()
        if pump.db.ox_event_journal_migrated:
            return 0
        legacy = list(pump.db.ox_private_events or [])
        for event in legacy:
            eid = event.get("event_id")
            if not isinstance(eid, str) or _EVENT_ID.fullmatch(eid) is None:
                raise ValueError("Unsafe legacy event ID; refusing to discard history")
            record = {
                "recipient_dbref": str(event["recipient_dbref"]),
                "sender_dbref": (str(event["sender_dbref"])
                                 if event.get("sender_dbref") is not None else None),
                "kind": str(event["kind"]),
                "details": _details(event.get("data")),
                "text": str(event.get("text", "")),
                "game_time": float(event["game_time"]),
            }
            stored, created = CrewEvent.objects.get_or_create(
                event_id=eid, defaults=record,
            )
            if not created and any(
                getattr(stored, name) != value for name, value in record.items()
            ):
                raise RuntimeError("Conflicting historical event; import aborted")
            count += int(created)
        # Preserve the old Attribute as an emergency rollback source.
        pump.db.ox_event_journal_migrated = True
    return count


def emit(pump, recipient, kind: str, *, sender=None, data=None, text="") -> dict:
    """Atomically append one addressed observation; notify only after commit."""
    if recipient is None or not isinstance(recipient.dbref, str):
        raise ValueError("An authoritative recipient character is required")
    if not isinstance(kind, str) or not 1 <= len(kind) <= 64:
        raise ValueError("Invalid world event kind")
    details = _details(data)
    with transaction.atomic():
        migrate_legacy_events(pump)
        _serialize_journal_transaction()
        record = CrewEvent.objects.create(
            event_id=None,
            recipient_dbref=recipient.dbref,
            sender_dbref=sender.dbref if sender else None,
            kind=kind,
            details=details,
            text=str(text),
            game_time=float(gametime.gametime(absolute=True)),
        )
        record.event_id = f"oxevt-v2-{record.sequence:04d}"
        record.save(update_fields=["event_id"])
        event = _as_dict(record)
        captured = _CAPTURED_EVENTS.get()
        if captured is not None:
            captured.append(event)
        # Socket packets are advisory. Only a committed journal row is truth.
        transaction.on_commit(
            lambda: recipient.msg(ox_event=([wire_event(event)], {}))
        )
    return event


def inbox_page(actor, *, after: int = 0, limit: int = PAGE_SIZE) -> dict:
    """Address-scoped, strictly ordered, restart-safe page of world history."""
    if isinstance(after, bool) or not isinstance(after, int) or after < 0:
        raise ValueError("Invalid event cursor")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= PAGE_SIZE:
        raise ValueError("Invalid event page size")
    if actor is None or not isinstance(actor.dbref, str):
        raise ValueError("Authenticated character required")
    migrate_legacy_events()
    entries = list(
        CrewEvent.objects.filter(
            recipient_dbref=actor.dbref, sequence__gt=after,
        ).order_by("sequence")[:limit + 1]
    )
    has_more = len(entries) > limit
    messages = [_as_dict(record) for record in entries[:limit]]
    return {
        "version": SCHEMA_VERSION,
        "events": messages,
        "count": len(messages),
        "next_cursor": messages[-1]["sequence"] if messages else after,
        "has_more": has_more,
    }


def addressed_event(actor, event_id: str) -> dict | None:
    """Retrieve one *addressed* historical event by its exact world identity.

    This is a read of the same canonical journal as oxinbox, not a world
    snapshot or a grant of permission to act. Missing and foreign-recipient
    IDs deliberately have identical results. Do not accept a recipient from
    the requester; the caller's authenticated puppet supplies the scope.
    """
    if (actor is None or not isinstance(getattr(actor, "dbref", None), str)
            or re.fullmatch(r"#[1-9][0-9]*", actor.dbref) is None):
        raise ValueError("Authenticated character required")
    if (not isinstance(event_id, str) or len(event_id) > 64
            or _LOOKUP_EVENT_ID.fullmatch(event_id) is None):
        raise ValueError("Invalid historical event identity")
    # Keep the original P4e migration semantics: a legacy event remains
    # queryable even when the first action after upgrade is exact retrieval.
    migrate_legacy_events()
    record = CrewEvent.objects.filter(
        recipient_dbref=actor.dbref, event_id=event_id,
    ).first()
    return _as_dict(record) if record is not None else None


def inbox(actor, *, after: int = 0) -> list[dict]:
    """Compatibility API: one page; callers needing all history must paginate."""
    return inbox_page(actor, after=after)["events"]
