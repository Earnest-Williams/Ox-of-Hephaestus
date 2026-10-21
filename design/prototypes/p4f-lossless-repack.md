# Periodic lossless SQLite repack of historical evidence

**Status:** Implementation in PR review following the
[measured P4f local profile](p4f-evidence-restart-profile.md).

The world journal and all historical evidence continue to grow with
simulation history. This optimization only reclaims inefficient *physical
SQLite page allocation* caused by transferring complete record bodies
from the hot `events.payload` column into compressed `cold_events.body`
rows. A repack does **not** delete a world event or suppress an archived
observation. The canonical journal remains wholly owned by Evennia.

## Trigger

`ActorEvidenceIndex.compact_hot()` maintains a persistent actor-local
count of original bodies demoted since the last successful file repack.
The counter advances transactionally with those demotions. Small, frequent
world deltas accumulate toward the same maintenance threshold as a large
initial inbox rehydration; they do not force a repack per read.

A repack requires **both** at least **2,048 accumulated demotions**
and demotions numbering at least **25% of the current cold-row total**.
The second condition is important: rewriting an ever-growing archive
every fixed number of new events would have quadratic lifetime cost.
Requiring proportional growth makes full-file maintenance progressively
less frequent as the voyage grows. The supervisor invokes
`ActorEvidenceIndex.repack_if_worthwhile()` only **outside** the
authenticated page/obligation/prefix-seal SQLite transaction while
owning the normal per-role inbox lock.

The threshold is a filesystem maintenance interval, **not** a count or
age limit on retained events. Actual unresolved obligations and source
IDs remain pinned hot. Every previously demoted record stays cold but
retrievable with the original event ID.

## Crash/continuity invariants

SQLite's native `VACUUM` reconstructs the database transactionally.
It is invoked after the new event pages, the per-recipient generation
and cumulative world prefix digest, and hot/cold obligation indexes have
been committed as one logical evidence transaction.

- `VACUUM` is prohibited while an archive transaction is open.
- The archive's saved world generation, cursor and historical digest
  must be unchanged after a successful repack.
- The durable demotion counter is reset **only after VACUUM succeeds**.
  A crash after VACUUM but before the counter reset can cause another
  physical repack, but never a lost original event or acknowledged work.
- A repack failure cannot advance the native character checkpoint. A
  new handler still independently rehashes every original retained
  event and reconstructs the outstanding-obligation projection before
  trusting the archive or requesting only later world inbox pages.
- A crash **after** a successful archive-seal/repack but **before**
  persisting the Concordia brain's private cursor is recovered by
  re-observing missed world evidence from that verified local archive.
  No historical work command or physical receipt is replayed as an
  effect.

This remains a local-handler file optimization. It creates no Evennia
schema migration, receipt authority, history cutoff, or new cognitive
memory interpretation.

## Measurement and regression

The profiling fixture's 40,128-record verbose-history comparison observed
106.83 MB of allocated SQLite storage before an independent `VACUUM
INTO` copy, and 27.37 MB after. That copy took 0.069 seconds on one
shared Linux CI runner and passed complete history verification. It is
not a guaranteed compression ratio or service latency.

The production path uses SQLite's ordinary transactional `VACUUM`
rather than replacing its live file with an independently assembled
copy. Focused regression tests verify complete source identities, old
hot/cold lookups, unchanged open obligations, preserved attestations,
persisted and rolled-back maintenance counters, threshold behavior, and
checkpoint recovery after the repack boundary. The usual world/handler
integration workflows continue to exercise authenticated transport and
work-authorization boundaries.

**World storage: O(history). Local cache: O(history). Full restart
attestation: O(history) local I/O.** Those are retained deliberately.
