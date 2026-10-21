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

from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zlib


_ACTOR = re.compile(r"^#[0-9]+$")
_DATA_KEY = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")
_EVENT_ID = re.compile(r"^oxevt-(?:v2-)?[0-9]+$")

# The hot bound does not cap genuine open world obligations or source proofs
# referenced by still-persisted handler work. Those must win over eviction.
DEFAULT_HOT_EVENTS = 256
COLD_BATCH = 128
# Minimum physical maintenance batch; large archives also require
# >=25% of current cold-row count demoted since the previous VACUUM.
# This avoids quadratic lifetime rewriting without deleting evidence.
REPACK_AFTER_DEMOTIONS = 2048


_ARCHIVED_STATE_ROOTS = frozenset({
    "completed", "specialist_completed", "specialist_handled",
    "handled_alarms", "navigation_knowledge", "epistemic_event_cursors",
    "inbox_cursors",
})
_TERMINAL_AGENDA_STATES = frozenset({
    "completed", "declined", "delegated", "escalated",
})


def checkpoint_evidence_pins(state: Mapping, role: str) -> set[str]:
    """Find original source IDs in *unfinished* actor-owned work records.

    Durable finished work and character memory are not deleted; their source
    evidence remains readable from cold storage. This is a hot-priority hint
    only and cannot authorize an unaddressed event or physical action.
    """
    if not isinstance(state, Mapping) or not isinstance(role, str):
        raise TypeError("Private checkpoint scope required")
    pins: set[str] = set()

    def collect(node: object) -> None:
        if isinstance(node, str):
            if len(node) <= 64 and _EVENT_ID.fullmatch(node):
                pins.add(node)
        elif isinstance(node, Mapping):
            for key, value in node.items():
                if key not in _ARCHIVED_STATE_ROOTS:
                    collect(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                collect(value)

    # Most live work is role-local. A shared watch incident can contain
    # source IDs addressed to several workers; the index will pin only
    # those that actually occur in its recipient-owned rows.
    for key in ("current", "handover_work", "hail_work"):
        records = state.get(key)
        if key == "hail_work" and isinstance(records, Mapping):
            for work in records.values():
                if isinstance(work, Mapping) and work.get("role") == role:
                    collect(work)
        else:
            collect(records)
    for key in (
        "specialist_jobs", "independent_rounds", "g3e_investigations",
        "g3e_followup", "g3e_questions",
    ):
        records = state.get(key)
        if isinstance(records, Mapping):
            record = records.get(role)
            if not (isinstance(record, Mapping) and record.get("done") is True):
                collect(record)
    agendas = state.get("agendas")
    if isinstance(agendas, Mapping):
        owner = agendas.get(role)
        if isinstance(owner, Mapping) and isinstance(owner.get("tasks"), Mapping):
            for task in owner["tasks"].values():
                if (isinstance(task, Mapping)
                        and task.get("status") not in _TERMINAL_AGENDA_STATES):
                    collect(task)
    return pins


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
            "data_index TEXT NOT NULL, "
            "payload TEXT)"
        )
        # Old full event bodies leave the active table but are NEVER dropped:
        # the cold tier is lossless, content-hashed and addressed by sequence.
        # Both tables are in the same disposable, actor-scoped SQLite file.
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cold_events ("
            "sequence INTEGER PRIMARY KEY CHECK(sequence > 0), "
            "body BLOB NOT NULL, codec TEXT NOT NULL, digest TEXT NOT NULL, "
            "CHECK(codec IN ('plain', 'zlib')))"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS pinned ("
            "event_id TEXT PRIMARY KEY NOT NULL)"
        )
        # A persisted archive is not evidence by itself. Its exact complete
        # local prefix is verified against this saved seal AND an independent
        # actor/nonce-bound world certificate before it is used after restart.
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS attestation ("
            "singleton INTEGER PRIMARY KEY CHECK(singleton = 1), "
            "generation TEXT NOT NULL, cursor INTEGER NOT NULL, "
            "digest TEXT NOT NULL)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS local_maintenance ("
            "singleton INTEGER PRIMARY KEY CHECK(singleton = 1), "
            "demoted_since_repack INTEGER NOT NULL DEFAULT 0 "
            "CHECK(demoted_since_repack >= 0))"
        )
        self._db.execute(
            "INSERT OR IGNORE INTO local_maintenance(singleton,demoted_since_repack) "
            "VALUES (1,0)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS event_hot_sequence "
            "ON events(sequence) WHERE payload IS NOT NULL"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS event_kind_seq "
            "ON events(kind, sequence)"
        )
        for key in ("ticket_id", "case_id", "order_id", "alarm_id", "hail_id"):
            self._db.execute(
                f"CREATE INDEX IF NOT EXISTS event_{key}_seq "
                f"ON events(kind, json_extract(data_index, '$.{key}'), sequence)"
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

    def _read_row(self, row: tuple) -> dict:
        """Decode one indexed hot/cold record and verify its local integrity."""
        sequence, event_id, kind, data_index, payload, body, codec, digest = row
        if payload is None:
            if body is None or codec not in ("plain", "zlib"):
                raise RuntimeError("Missing local cold event body")
            try:
                raw = zlib.decompress(body) if codec == "zlib" else bytes(body)
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise RuntimeError("Corrupt local cold event checksum")
                payload = raw.decode("utf-8")
            except (zlib.error, UnicodeError) as exc:
                raise RuntimeError("Corrupt local cold event encoding") from exc
        elif body is not None:
            raise RuntimeError("Contradictory hot and cold event bodies")
        event = json.loads(payload)
        if (event.get("recipient_dbref") != self.actor_dbref
                or event.get("event_id") != event_id
                or type(event.get("sequence")) is not int
                or event["sequence"] != sequence):
            raise PermissionError("Local evidence does not match its actor or identity")
        # Indexed metadata is part of the evidence representation. A valid
        # compressed body with altered kind/case/ticket selectors is NOT an
        # acceptable local archive.
        if event.get("kind") != kind or event.get("data") != json.loads(data_index):
            raise RuntimeError("Indexed metadata disagrees with original world event")
        return event

    def _materialize(self, sequence: int) -> dict:
        record = self._db.execute(
            "SELECT e.sequence,e.event_id,e.kind,e.data_index,e.payload,"
            "c.body,c.codec,c.digest FROM events AS e "
            "LEFT JOIN cold_events AS c ON e.sequence=c.sequence "
            "WHERE e.sequence=?", (sequence,),
        ).fetchone()
        if record is None:
            raise LookupError("Indexed world event was not found")
        return self._read_row(record)

    def stored_attestation(self) -> tuple[str, int, str] | None:
        """The local transaction's saved prefix, never world authority."""
        row = self._db.execute(
            "SELECT generation,cursor,digest FROM attestation WHERE singleton=1"
        ).fetchone()
        if row is not None:
            if (not isinstance(row[0], str) or not re.fullmatch(r"[0-9a-f]{32}", row[0])
                    or type(row[1]) is not int or row[1] < 0
                    or not isinstance(row[2], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", row[2])):
                raise RuntimeError("Invalid persisted journal cache attestation")
        return tuple(row) if row is not None else None

    def seal_attestation(self, generation: str, digest: str) -> None:
        """Bind the atomically committed archive to its verified world prefix."""
        if (not isinstance(generation, str)
                or re.fullmatch(r"[0-9a-f]{32}", generation) is None
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
            raise ValueError("Invalid actor journal seal")
        if not self._db.in_transaction:
            raise RuntimeError("Cache continuity must be committed with indexed pages")
        cursor = self.cursor
        self._db.execute(
            "INSERT INTO attestation(singleton,generation,cursor,digest) "
            "VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET "
            "generation=excluded.generation, cursor=excluded.cursor, "
            "digest=excluded.digest",
            (generation, cursor, digest),
        )

    def recompute_prefix(self, generation: str) -> str:
        """Scan *every* retained original record for local crash/tamper safety.

        O(history) local sequential SQLite I/O is deliberate for this first
        reuse gate. Unlike replay, it does not transfer the voyage over the
        network or rebuild SQLite indexes. All hot and compressed cold
        records, including their indexed metadata, are checked.
        """
        from ox_ai.ports.evennia.journal import continue_digest, journal_seed

        digest = journal_seed(generation, self.actor_dbref)
        # The obligations table is a derived but consequential index: a
        # corrupted closed/open flag could silently skip pending world work
        # even when every event body and its prefix hash are still valid.
        # Rebuild it as a TEMP projection while already scanning all records.
        self._db.execute("DROP TABLE IF EXISTS temp.verified_obligations")
        self._db.execute(
            "CREATE TEMP TABLE verified_obligations ("
            "category TEXT NOT NULL, reference TEXT NOT NULL, "
            "source_sequence INTEGER NOT NULL, resolved_sequence INTEGER, "
            "PRIMARY KEY(category,reference))"
        )
        openings = {"crew_hail": ("hail", "hail_id"),
                    "captain_problem_open": ("captain", "ticket_id")}
        endings = {"hail_answered": ("hail", "hail_id"),
                   "captain_world_resolved": ("captain", "ticket_id")}
        try:
            for event in self.view():
                digest = continue_digest(digest, event)
                kind = event["kind"]
                opening = openings.get(kind)
                ending = endings.get(kind)
                entry = opening or ending
                if entry is None:
                    continue
                category, key = entry
                ref = event["data"].get(key)
                if not isinstance(ref, str) or not ref:
                    raise RuntimeError("Invalid restored world obligation identity")
                if opening is not None:
                    try:
                        self._db.execute(
                            "INSERT INTO verified_obligations "
                            "(category,reference,source_sequence) VALUES (?,?,?)",
                            (category, ref, event["sequence"]),
                        )
                    except sqlite3.IntegrityError as exc:
                        raise RuntimeError(
                            "Duplicate opening in restored world obligations"
                        ) from exc
                else:
                    self._db.execute(
                        "UPDATE verified_obligations SET resolved_sequence=? "
                        "WHERE category=? AND reference=? "
                        "AND resolved_sequence IS NULL",
                        (event["sequence"], category, ref),
                    )
            fields = "category,reference,source_sequence,resolved_sequence"
            forward = (
                f"SELECT {fields} FROM obligations EXCEPT "
                f"SELECT {fields} FROM verified_obligations"
            )
            backward = (
                f"SELECT {fields} FROM verified_obligations EXCEPT "
                f"SELECT {fields} FROM obligations"
            )
            if (self._db.execute(forward + " LIMIT 1").fetchone() is not None
                    or self._db.execute(backward + " LIMIT 1").fetchone() is not None):
                raise RuntimeError(
                    "Cached open obligations differ from authenticated history"
                )
            return digest
        finally:
            self._db.execute("DROP TABLE IF EXISTS temp.verified_obligations")

    @property
    def hot_count(self) -> int:
        return int(self._db.execute(
            "SELECT COUNT(*) FROM events WHERE payload IS NOT NULL"
        ).fetchone()[0])

    @property
    def cold_count(self) -> int:
        return int(self._db.execute(
            "SELECT COUNT(*) FROM cold_events"
        ).fetchone()[0])

    def replace_pins(self, event_ids: Iterable[str]) -> None:
        """Set references held by live handler checkpoints for this actor.

        This does not assert a world right or authorize a work request.
        Unknown IDs remain harmless references until an addressed page
        supplies them; foreign actors' rows cannot enter this index.
        """
        refs = set(event_ids)
        if any(not isinstance(eid, str) or not _EVENT_ID.fullmatch(eid)
               or len(eid) > 64 for eid in refs):
            raise ValueError("Invalid private evidence pin")
        self._db.execute("DELETE FROM pinned")
        self._db.executemany(
            "INSERT INTO pinned(event_id) VALUES (?)",
            ((eid,) for eid in sorted(refs)),
        )
        # A reactivated checkpoint reference must be hot again, even if
        # compaction previously relegated it to compressed local cold proof.
        rows = list(self._db.execute(
            "SELECT e.sequence FROM events AS e "
            "JOIN pinned AS p ON p.event_id=e.event_id "
            "WHERE e.payload IS NULL"
        ))
        for (sequence,) in rows:
            event = self._materialize(sequence)
            encoded = json.dumps(
                event, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            )
            self._db.execute(
                "UPDATE events SET payload=? WHERE sequence=?",
                (encoded, sequence),
            )
            self._db.execute(
                "DELETE FROM cold_events WHERE sequence=?", (sequence,),
            )

    def compact_hot(
        self, *, recent: int = DEFAULT_HOT_EVENTS,
        batch_size: int = COLD_BATCH,
    ) -> int:
        """Losslessly demote unpinned older bodies; all queries still work.

        The newest N *recipient* events, all open hail/captain source
        obligations, and all checkpoint-pinned source proofs remain hot.
        Every other original event remains in a compressed local cold tier.
        This is not world retention or an authorization to skip hydration.
        """
        if (type(recent) is not int or recent < 1
                or type(batch_size) is not int or not 1 <= batch_size <= 1024):
            raise ValueError("Invalid hot evidence retention budget")
        if not self._db.in_transaction:
            with self.transaction():
                return self.compact_hot(recent=recent, batch_size=batch_size)
        boundary = self._db.execute(
            "SELECT sequence FROM events ORDER BY sequence DESC "
            "LIMIT 1 OFFSET ?", (recent - 1,),
        ).fetchone()
        if boundary is None:
            return 0
        demoted = 0
        while True:
            records = list(self._db.execute(
                "SELECT e.sequence,e.payload FROM events AS e "
                "WHERE e.sequence < ? AND e.payload IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM pinned AS p "
                "WHERE p.event_id=e.event_id) "
                "AND NOT EXISTS (SELECT 1 FROM obligations AS o "
                "WHERE o.source_sequence=e.sequence "
                "AND o.resolved_sequence IS NULL) "
                "ORDER BY e.sequence LIMIT ?",
                (boundary[0], batch_size),
            ))
            if not records:
                if demoted:
                    self._db.execute(
                        "UPDATE local_maintenance SET demoted_since_repack="
                        "demoted_since_repack+? WHERE singleton=1",
                        (demoted,),
                    )
                return demoted
            for sequence, payload in records:
                raw = payload.encode("utf-8")
                packed = zlib.compress(raw, level=6)
                body, codec = ((packed, "zlib") if len(packed) < len(raw)
                               else (raw, "plain"))
                self._db.execute(
                    "INSERT INTO cold_events(sequence,body,codec,digest) "
                    "VALUES(?,?,?,?)",
                    (sequence, body, codec, hashlib.sha256(raw).hexdigest()),
                )
                self._db.execute(
                    "UPDATE events SET payload=NULL WHERE sequence=?",
                    (sequence,),
                )
                demoted += 1

    def repack_if_worthwhile(
        self, *, after_demotions: int = REPACK_AFTER_DEMOTIONS,
    ) -> bool:
        """Periodically reclaim SQLite allocation slack, retaining all evidence.

        A VACUUM is a transactional SQLite file rebuild, NOT a world event
        deletion. It may run only after page + prefix-seal commit and outside
        all actor index transactions. Failure leaves the prior archive
        protected by SQLite crash recovery; do not advance a cognition
        checkpoint after an unsuccessful repack.
        """
        if type(after_demotions) is not int or after_demotions < 1:
            raise ValueError("Invalid lossless-repack maintenance interval")
        if self._db.in_transaction:
            raise RuntimeError("Cannot repack during an evidence transaction")
        count = self._db.execute(
            "SELECT demoted_since_repack FROM local_maintenance "
            "WHERE singleton=1"
        ).fetchone()
        if count is None:
            raise RuntimeError("Missing local evidence maintenance state")
        if count[0] < after_demotions:
            return False
        # Rewriting the complete voyage after each fixed-size new batch
        # would be quadratic over time. At larger history sizes, require
        # enough new cold data to amortize one full-file VACUUM. This is
        # a physical maintenance cadence, never a history retention cap.
        if count[0] < self.cold_count // 4:
            return False

        attested = self.stored_attestation()
        # SQLite VACUUM itself is atomic and fail-safe on interruption.
        # No temp copy is promoted and no actor-scoped row is discarded.
        self._db.execute("VACUUM")
        if self.stored_attestation() != attested:
            raise RuntimeError("Journal evidence seal changed after SQLite repack")
        # If interrupted between VACUUM and this administrative update, a
        # later pass can safely repeat VACUUM. Never reset the counter first.
        with self.transaction():
            self._db.execute(
                "UPDATE local_maintenance SET demoted_since_repack=0 "
                "WHERE singleton=1"
            )
        return True

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
                json.dumps(event["data"], sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False),
                json.dumps(event, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False),
            ))
            previous = sequence
        if rows:
            self._db.executemany(
                "INSERT INTO events(sequence,event_id,kind,data_index,payload)"
                " VALUES (?,?,?,?,?)", rows,
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
        clauses = ["e.sequence > ?", "e.sequence <= ?"]
        values: list[object] = [after, through]
        if kind is not None:
            if not isinstance(kind, str) or not kind:
                raise ValueError("Invalid event kind selector")
            clauses.append("e.kind = ?")
            values.append(kind)
        if event_id is not None:
            if not isinstance(event_id, str) or not event_id:
                raise ValueError("Invalid event identity selector")
            clauses.append("e.event_id = ?")
            values.append(event_id)
        for key, value in (data or {}).items():
            if not isinstance(key, str) or not _DATA_KEY.fullmatch(key):
                raise ValueError("Invalid indexed event field")
            if value is None:
                clauses.append(f"json_extract(e.data_index, '$.{key}') IS NULL")
            elif type(value) in (str, int, float, bool):
                clauses.append(f"json_extract(e.data_index, '$.{key}') = ?")
                values.append(value)
            else:
                raise ValueError("Invalid indexed event selector value")
        query = (
            "SELECT e.sequence,e.event_id,e.kind,e.data_index,e.payload,"
            "c.body,c.codec,c.digest "
            "FROM events AS e LEFT JOIN cold_events AS c "
            "ON c.sequence=e.sequence WHERE " + " AND ".join(clauses)
            + (" ORDER BY e.sequence DESC" if newest_first
               else " ORDER BY e.sequence ASC")
        )
        if limit is not None:
            if type(limit) is not int or limit < 0:
                raise ValueError("Invalid evidence selection limit")
            query += " LIMIT ? OFFSET ?"
            values.extend((limit, offset))
        elif offset:
            query += " LIMIT -1 OFFSET ?"
            values.append(offset)
        for row in self._db.execute(query, values):
            yield self._read_row(row)

    def _pending(
        self, category: str, after: int, through: int,
    ) -> Iterator[dict]:
        """Source events for obligations still open at this view's cursor."""
        if category not in ("hail", "captain"):
            raise ValueError("Unknown addressed obligation category")
        query = (
            "SELECT e.sequence,e.event_id,e.kind,e.data_index,e.payload,"
            "c.body,c.codec,c.digest "
            "FROM obligations AS o "
            "JOIN events AS e ON e.sequence = o.source_sequence "
            "LEFT JOIN cold_events AS c ON c.sequence=e.sequence "
            "WHERE o.category = ? AND o.source_sequence > ? "
            "AND o.source_sequence <= ? "
            "AND (o.resolved_sequence IS NULL OR o.resolved_sequence > ?) "
            "ORDER BY o.source_sequence"
        )
        for row in self._db.execute(
            query, (category, after, through, through),
        ):
            yield self._read_row(row)

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
