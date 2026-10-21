# Reusable actor-private historical evidence cache

## Retention policy

The Ox ship **retains its full authoritative journal forever**, subject to
the operator's own archival/storage policy. Local storage consequently grows
with retained history. This is an acceptable and deliberate property.

This change addresses the *unnecessary retransmission and re-indexing* of
that history each time the AI handler restarts. It does not add a fixed
history cutoff, erase character knowledge, or relax work-receipt checks.

## Two independent continuity checks

1. Every actor's local SQLite file at
   `<handler-state-directory>/attested-evidence-v1/<role>.sqlite3` now stores
   the verified world generation, addressed cursor and cumulative prefix
   digest **transactionally together** with its corresponding hot/cold event
   rows. The directory is owner-only; the local file is mode 0600.
2. On each new handler process, that file is opened strictly for its
   authenticated character. The handler recomputes the SHA-256 prefix over
   *all* original events (hot and compressed cold), and validates all indexed
   kind/data metadata. It requires a locally stored matching digest and an
   `oxjournal` certificate obtained under the freshly authenticated,
   separately puppeted character session. World generation, actor, old
   cursor, full prefix digest and current head must agree. Missing prefix,
   divergence, corruption, generation reset or world rewind is a hard
   failure—**never an implicit reset or successful work receipt**.

Only after those checks may the handler begin `oxinbox` at the *verified
local high-water mark*. It streams new pages into the same transaction as
the updated prefix hash, mandatory evidence pins and hot/cold compression,
and confirms that updated hash against a second world certificate.
An interruption during page ingestion rolls back all new records and the
associated cache seal together.

## Cognition and interrupted-work continuity

The authenticated archive may legitimately be ahead of the last **saved**
Concordia brain checkpoint or private agenda. A crash can happen after
the indexed event pages commit but before saving the native brain and
supervisor state. On restart:

- The cached world prefix is validated first.
- Every legitimately addressed event **after the old saved cognition cursor**
  is observed or replayed from verified SQLite, with normal event-ID
  deduplication. This does not re-execute physical work or advance an
  unresolved receipt.
- The native brain checkpoint is saved **before** advancing its durable
  supervisor cursor, just as in the existing implementation.
- Five/six-person specialist agenda and epistemic cursors remain distinct;
  they backfill from the indexed `EvidenceView` when their own checkpoint
  lagged the supervisor.
- Old completed-work proof references, private episodes and changed
  interpretations remain recoverable from the cold tier and the
  world-owned `oxevent` API. Actual permissions still come from Evennia.

An unauthenticated or unsealed pre-feature SQLite file is not accepted as
a world-backed cache. A missing new cache begins with cursor zero and full
authenticated rehydration, then obtains an attested seal.

## Cost and limits

- **World storage:** O(history), intentionally. Every old event retains its
  exact original world ID, full body and per-recipient chain hash.
- **Local disk:** O(history), compressed hot/cold with indexed metadata.
  It is a cache, not the only copy of the voyage's history.
- **Cold-start local verification:** O(history) disk reads, hashes and
  decompression. This first implementation favors strong correctness.
- **Cold-start network history transfer:** O(new addressed events), after
  successful validation. On an unchanged world and archive, one empty
  inbox page and two small continuity certificates suffice for the first
  read on each character session.
- **Warm read:** one addressed `oxinbox` delta plus a world prefix check;
  old full-history pages are not resent.

This is not a digitally signed third-party audit or a defense against a
hostile operator with the ability to rewrite the world database, the local
cache and its software. It is an authenticated in-system continuity check
with full local crash/corruption detection.

## Verification

New offline regression tests cover a reused 800-event hot/cold archive,
no old-world network paging on restart, a 100-event delta, changed world
history, generation rotation, rewind, corrupted old compressed bodies and
the archive-before-cognition-checkpoint crash boundary. Existing
world/handler CI checks still exercise authentic multi-character Evennia,
work receipts, investigations and private agendas.

The cache is never rehydrated from another character's historical records,
and a negative world journal certificate does not imply any resolved work.
