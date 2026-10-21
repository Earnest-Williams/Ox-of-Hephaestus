"""Actor-private, indexed, disposable history of verified Evennia inbox events.

The world remains the source of truth. Each handler process builds a separate
on-disk SQLite index *only* from the actor's authenticated oxinbox pages.
The index is intentionally disposable: no process may start from an
unvalidated local cache and claim it observed world evidence.

The old P4e/G3 consumers still expect ordered history, but it is now an
immutable, lazy Sequence view. No permanent Python list of every voyage event
is retained. A full historical query may still be O(voyage length); indexed
lookups by event identity, kind, case, or ticket avoid that scan.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3


_ACTOR = re.compile(r"^#[0-9]+$")
_DATA_KEY = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")


class ActorEvidenceIndex:
    """One actor, one fresh process-local SQLite database, no world writes."""

    def __init__(self, path: Path, actor_dbref: str) -> None:
        if not isinstance(actor_dbref, str) or not _ACTOR.fullmatch(actor_dbref):
            raise PermissionError("Evidence index needs one authenticated actor ID")
        self.actor_dbref = actor_dbref
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path), isolation_level=None)
        self._db.execute("PRAGMA cache_size=-512")  # 512 KiB per actor cache
        self._db.execute("PRAGMA temp_store=FILE")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS scope (actor TEXT NOT NULL PRIMARY KEY)"
        )
        owners = [r[0] for r in self._db.execute("SELECT actor FROM scope")]
        if owners and owners != [actor_dbref]:
            self._db.close()
            raise PermissionError("Foreign actor's indexed evidence")
        if not owners:
            self._db.execute(
                "INSERT INTO scope(actor) VALUES (?)", (actor_dbref,)
            )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "sequence INTEGER PRIMARY KEY CHECK(sequence > 0), "
            "event_id TEXT UNIQUE NOT NULL, "
            "kind TEXT NOT NULL, "
            "payload TEXT NOT NULL)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS event_kind_seq "
            "ON events(kind, sequence)"
        )
        for key in ("ticket_id", "case_id", "order_id", "alarm_id", "hail_id"):
            self._db.execute(
                f"CREATE INDEX IF NOT EXISTS event_{key}_seq "
                f"ON events(kind, json_extract(payload, '$.data.{key}'), sequence)"
            )
        # Materialised *addressed* obligation transitions, not a second
        # authority. Closed rows remain for pinned historical snapshots.
        # Only still-open obligations are visited during normal dispatch.
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS obligations ("
            "category TEXT NOT NULL, reference TEXT NOT NULL, "
            "source_sequence INTEGER NOT NULL, "
            "resolved_sequence INTEGER, "
            "PRIMARY KEY (category, reference), "
            "CHECK (category IN ('hail', 'captain')))"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS obligation_state_seq "
            "ON obligations(category, resolved_sequence, source_sequence)"
        )

    def close(self) -> None:
        self._db.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """All pages from one authenticated read commit or none do."""
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._db.rollback()
            raise
        else:
            self._db.commit()

    @property
    def cursor(self) -> int:
        return int(self._db.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM events"
        ).fetchone()[0])

    def append_page(self, page: list[dict]) -> None:
        """Called only with a validated oxinbox page inside a transaction."""
        previous = self.cursor
        rows = []
        for event in page:
            if (not isinstance(event, dict)
                    or event.get("recipient_dbref") != self.actor_dbref):
                raise PermissionError("Foreign recipient in history index")
            sequence = event.get("sequence")
            event_id = event.get("event_id")
            kind = event.get("kind")
            if (type(sequence) is not int or sequence <= previous
                    or not isinstance(event_id, str) or not event_id
                    or not isinstance(kind, str) or not kind
                    or not isinstance(event.get("data"), dict)):
                raise ValueError("Invalid or unordered world evidence")
            rows.append((
                sequence, event_id, kind,
                json.dumps(event, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False),
            ))
            previous = sequence
        if rows:
            self._db.executemany(
                "INSERT INTO events(sequence,event_id,kind,payload)"
                " VALUES (?,?,?,?)", rows,
            )
        # Derived obligation state advances in the *same* transaction as
        # the event pages. A truncated replay cannot partially close work.
        openings = {"crew_hail": ("hail", "hail_id"),
                    "captain_problem_open": ("captain", "ticket_id")}
        endings = {"hail_answered": ("hail", "hail_id"),
                   "captain_world_resolved": ("captain", "ticket_id")}
        for event in page:
            kind = event["kind"]
            entry = openings.get(kind)
            closing = False
            if entry is None:
                entry = endings.get(kind)
                closing = entry is not None
            if entry is None:
                continue
            category, key = entry
            reference = event["data"].get(key)
            if not isinstance(reference, str) or not reference:
                raise ValueError("World obligation event lacks identity")
            if closing:
                # An unmatched completion is not evidence of an opening.
                # Never invent an obligation on a closing notification.
                self._db.execute(
                    "UPDATE obligations SET resolved_sequence = ? "
                    "WHERE category = ? AND reference = ? "
                    "AND resolved_sequence IS NULL",
                    (event["sequence"], category, reference),
                )
            else:
                try:
                    self._db.execute(
                        "INSERT INTO obligations(category,reference,source_sequence) "
                        "VALUES (?,?,?)",
                        (category, reference, event["sequence"]),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValueError("Duplicate world obligation identity") from exc

    def view(self, *, after: int = 0, through: int | None = None) -> EvidenceView:
        if type(after) is not int or after < 0:
            raise ValueError("Invalid historical lower cursor")
        if through is None:
            through = self.cursor
        if type(through) is not int or through < 0:
            raise ValueError("Invalid historical upper cursor")
        return EvidenceView(self, after, through)

    def _query(
        self, after: int, through: int, *, kind: str | None = None,
        event_id: str | None = None, data: Mapping[str, object] | None = None,
        newest_first: bool = False, limit: int | None = None,
        offset: int = 0,
    ) -> Iterator[dict]:
        clauses = ["sequence > ?", "sequence <= ?"]
        values: list[object] = [after, through]
        if kind is not None:
            if not isinstance(kind, str) or not kind:
                raise ValueError("Invalid event kind selector")
            clauses.append("kind = ?")
            values.append(kind)
        if event_id is not None:
            if not isinstance(event_id, str) or not event_id:
                raise ValueError("Invalid event identity selector")
            clauses.append("event_id = ?")
            values.append(event_id)
        for key, value in (data or {}).items():
            if not isinstance(key, str) or not _DATA_KEY.fullmatch(key):
                raise ValueError("Invalid indexed event field")
            if value is None:
                clauses.append(f"json_extract(payload, '$.data.{key}') IS NULL")
            elif type(value) in (str, int, float, bool):
                clauses.append(f"json_extract(payload, '$.data.{key}') = ?")
                values.append(value)
            else:
                raise ValueError("Invalid indexed event selector value")
        query = (
            "SELECT payload FROM events WHERE " + " AND ".join(clauses)
            + (" ORDER BY sequence DESC" if newest_first
               else " ORDER BY sequence ASC")
        )
        if limit is not None:
            if type(limit) is not int or limit < 0:
                raise ValueError("Invalid evidence selection limit")
            query += " LIMIT ? OFFSET ?"
            values.extend((limit, offset))
        elif offset:
            query += " LIMIT -1 OFFSET ?"
            values.append(offset)
        for (payload,) in self._db.execute(query, values):
            event = json.loads(payload)
            if event.get("recipient_dbref") != self.actor_dbref:
                raise PermissionError("Cached evidence belongs to a foreign actor")
            yield event

    def _pending(
        self, category: str, after: int, through: int,
    ) -> Iterator[dict]:
        """Source events for obligations still open at this view's cursor."""
        if category not in ("hail", "captain"):
            raise ValueError("Unknown addressed obligation category")
        query = (
            "SELECT e.payload FROM obligations AS o "
            "JOIN events AS e ON e.sequence = o.source_sequence "
            "WHERE o.category = ? AND o.source_sequence > ? "
            "AND o.source_sequence <= ? "
            "AND (o.resolved_sequence IS NULL OR o.resolved_sequence > ?) "
            "ORDER BY o.source_sequence"
        )
        for (payload,) in self._db.execute(
            query, (category, after, through, through),
        ):
            event = json.loads(payload)
            if event.get("recipient_dbref") != self.actor_dbref:
                raise PermissionError("Foreign actor in obligation index")
            yield event

    def _count(self, after: int, through: int) -> int:
        return int(self._db.execute(
            "SELECT COUNT(*) FROM events WHERE sequence > ? AND sequence <= ?",
            (after, through),
        ).fetchone()[0])


@dataclass(frozen=True)
class EvidenceView(Sequence[dict]):
    """Immutable sequence/cursor snapshot backed by a bounded SQLite cache."""

    archive: ActorEvidenceIndex
    after: int
    through: int

    def __iter__(self) -> Iterator[dict]:
        return self.select()

    def __reversed__(self) -> Iterator[dict]:
        return self.select(newest_first=True)

    def __len__(self) -> int:
        return self.archive._count(self.after, self.through)

    def __getitem__(self, key: int | slice) -> dict | list[dict]:
        if isinstance(key, slice):
            return [self[i] for i in range(*key.indices(len(self)))]
        if type(key) is not int:
            raise TypeError("Evidence indexes must be integers or slices")
        count = len(self)
        index = key if key >= 0 else count + key
        if not 0 <= index < count:
            raise IndexError(key)
        return next(self.archive._query(
            self.after, self.through, limit=1, offset=index,
        ))

    def select(
        self, *, kind: str | None = None, event_id: str | None = None,
        data: Mapping[str, object] | None = None,
        newest_first: bool = False, limit: int | None = None,
        after: int | None = None,
    ) -> Iterator[dict]:
        """Use kind/field/sequence indexes inside this pinned cursor view."""
        if after is not None and (type(after) is not int or after < 0):
            raise ValueError("Invalid historical selection cursor")
        return self.archive._query(
            max(self.after, after) if after is not None else self.after,
            self.through, kind=kind, event_id=event_id,
            data=data, newest_first=newest_first, limit=limit,
        )

    def pending(self, category: str) -> Iterator[dict]:
        """Only unresolved hails or captain problems, at the pinned cursor."""
        return self.archive._pending(category, self.after, self.through)

    def get(
        self, event_id: str, *, kind: str | None = None,
    ) -> dict | None:
        """Exact, actor-scoped O(log N) world event proof lookup."""
        return next(self.select(event_id=event_id, kind=kind, limit=1), None)

    def latest(
        self, kind: str, *, data: Mapping[str, object] | None = None,
        after: int | None = None,
    ) -> dict | None:
        return next(self.select(
            kind=kind, data=data, newest_first=True, limit=1, after=after,
        ), None)
