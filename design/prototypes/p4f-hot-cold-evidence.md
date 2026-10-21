# P4f hot/cold historical evidence — lossless first stage

**Status:** Introduced for PR review. This is an actor-scoped *read-index*
optimization in the external handler, not a change to world ownership.

## Why this design

Actual legacy callers still use synchronous `EvidenceView` iteration,
`select(kind, data)`, `latest()`, `get(event_id)`, and indexed
`pending("hail"|"captain")` snapshots. Their original event IDs, including
old work receipts and deferred tasks, must remain resolvable. Merely deleting
events older than a turn/count limit would silently change those contracts.

PR #88 provides `oxevent` for independent actor-authenticated exact proof.
It does **not** provide an authenticated world-wide indexed replacement for
every legacy selection, nor a journal-generation attestation allowing a
portable local archive to be trusted across process launches.

## Implemented hot/cold tiers

The handler continues to stream fully validated, per-actor `oxinbox` pages
into its **disposable SQLite index**. Within that same SQLite transaction it
classifies records into:

- **Hot:** newest 256 *addressed events* (not 256 global sequence IDs), all
  still-open hail/captain opening events, and source-event references found in
  this actor's active checkpoint work/agenda.
- **Cold:** every other event's full original record stored losslessly as a
  compressed blob, keyed by original sequence. A SHA-256 digest detects local
  cold-blob corruption. Records that would expand under compression are
  stored uncompressed, rather than spending additional disk.
- **Indexed metadata:** every event keeps its original `sequence`,
  `event_id`, `kind` and the scalar `data` projection used by case,
  ticket, order, alarm and hail queries. No historical selector is dropped.

A full history view, including snapshots pinned to an old upper cursor,
retrieves a hot row directly or decompresses the matching cold blob lazily.
`latest`, exact `get`, arbitrary `data` selections, forward and reverse
iteration, and ordinal slices continue to return complete original events.
This is not a blind migration of `EvidenceView` to a hot-only collection.

Checkpoint reference pinning is restricted to unfinished actor-local
`specialist_jobs`, rounds, investigation work and agendas, plus open
watch incident/handover and the actor's pending hail work. Historical
`completed`/handled collections are not permanently pinned merely
because their IDs appear in a checkpoint; they remain available cold.
A future reference may be *repinned* and promoted from cold into hot
without returning to Evennia. Dynamic world obligations remain hot even
when a checkpoint has not yet mentioned them.

The effective hot bound is **256 + the number of required live pins**.
An unbounded number of genuine open obligations must never be discarded
to satisfy an arbitrary RAM/row-count limit. The full metadata and cold
blobs remain on disk; therefore total local disk use is still proportional
to voyage history, although old payload text is compressed.

## Safety and recovery

- All insertions, derived obligation transitions, pin promotion and demotion
  happen transactionally. A failed later `oxinbox` page rolls back the batch;
  a checksum/codec mismatch raises rather than returning invented evidence.
- There is **no** Evennia schema/command migration. The cold tier grants no
  permissions, physical effects, private memory interpretations, or world
  truth. Actual work still requires world-owned receipts and verification.
- A fresh process must **still replay all** properly addressed history,
  reconstruct its own index, validate its native brain and agenda cursors,
  and refuse world rewind relative to its checkpoints.
- No local event is deleted. A character can still reconsider any legitimate
  prior episode stored in Concordia, and old exact event proofs are available
  from `EvidenceView` and independently via `WorldEventPort`.
- The index is **not reused** after process exit; rebuilding it costs
  O(history) network transfer, SQL inserts and eventual cold compression.

## Verification

Tests cover (1) 1,000 mixed-kind records before/after compaction with
identical chronological, typed, case-filtered, latest and ordinal results;
(2) historical pinned views before a world obligation is closed;
(3) live unresolved pins after 300 events, plus cold repinning; (4) rollback
of interrupted compression, corrupt cold record refusal; (5) actor-specific
checkpoint pin extraction; and (6) authentic replay/restart coverage over
630 actor-addressed events, showing no fabricated cursor progression.

## Conditions before reusing an on-disk cold archive on cold start

1. World-issued, nonce/actor-bound **journal generation** and authenticated
   high-water certificate, with explicit semantics across fixture reset,
   legacy import, DB rewind/restore and future historical corrections.
2. Cryptographic integrity for the local cache and its complete, ordered
   addressed event set, tied to the same world generation/checkpoint
   (a current latest event ID alone cannot attest every earlier row).
3. Durable coordination between the world-attested evidence cursor and
   independently saved native cognition, agenda, epistemic, pending-work and
   private-memory revisions. Failed checkpoint writes must not lose an
   event or prematurely retire a source proof.
4. Proof that all remaining legacy queries can be served across the
   hot/cold boundary, and that missing/oversized exact-event replies do not
   silently become negative world facts.

Only after those conditions are met can we safely skip full replay or
consider a bounded local-disk policy. **This PR implements none of those
unsafe shortcuts.**
