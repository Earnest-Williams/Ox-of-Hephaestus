# P4f — measured restart verification and SQLite storage footprint

**Status:** Deterministic, local-only profiling. No changes to world journal
retention, cognition, on-disk archive trust, or existing verification gates.

## Purpose

Ox retains every authoritative world event. The question is not how to cap
historical storage, but whether its complete local prefix verification is
too costly to perform on every handler restart, and whether SQLite's
hot-to-cold transition leaves avoidable *allocated space* behind.

Command used in [the dedicated CI profiler](../../.github/workflows/ox-p4f-evidence-profile.yml):

```sh
python scenarios/profiling/evidence_restart.py \
  --sizes 1000,10000,40000 --payloads 160,1200 \
  --trials 3 --hotspot \
  --output .ox-state/profiles/p4f-evidence-restart.json
```

The exact production `ActorEvidenceIndex` is used. Each case creates
actor-addressed original events in 128-record batches, maintains its exact
journal digest and open/closed world obligation projection, compresses
unneeded bodies while retaining old source IDs, persists its attestation,
closes SQLite and reopens it for **complete** local-prefix and obligation
verification. Three verification passes show first-pass versus
warm-page-cache costs. Timed work also includes 200 exact historical
lookups, a typed case selection and a further 128-event append.

The two payload sizes simulate short and moderately long textual
observations. They are **not** real dialogue or actual world telemetry.
Measured on a GitHub Actions Ubuntu runner with Python 3.12.15 and SQLite
3.46.1; shared-runner figures are observations, not performance guarantees.

## Recorded results

| Actor event count | Text characters | First full verified restart | Median of 3 full checks | Initial local build/hash/compaction | SQLite file |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 160 | 0.023 s | 0.023 s | 0.045 s | 0.98 MB |
| 10,000 | 160 | 0.244 s | 0.243 s | 0.533 s | 9.94 MB |
| 40,000 | 160 | 0.973 s | 0.968 s | 2.509 s | 39.94 MB |
| 1,000 | 1,200 | 0.032 s | 0.032 s | 0.062 s | 2.62 MB |
| 10,000 | 1,200 | 0.332 s | 0.332 s | 0.747 s | 26.56 MB |
| 40,000 | 1,200 | 1.329 s | 1.332 s | 3.272 s | 106.49 MB |

The 128-event warm extension took approximately 7–12 ms across
the six cases. Indexed exact historical lookups had 0.054–0.061 ms
median latency across 200 lookups per case. No historical events,
source proofs or unresolved obligations were eliminated.

These build measurements include local synthetic-event generation and
SQLite writes; **they exclude network transfer and a live Evennia server**.
Verification cost includes decoding/checking full retained original
events, recomputing their cryptographic prefix and independently
reconstructing the derived outstanding-obligation projection.

## CPU and physical storage observations

One separately instrumented 40,000-event / 1,200-character verification
reported approximately 1.92 million Python function calls in 2.02 seconds
(with cProfile overhead). Notable cumulative costs included event-row
decoding, JSON decoding/re-encoding, the canonical world hash, and zlib
decompression. Hashing is not the only, or dominant, expense.

The 40,000-event verbose archive stored **11.90 MB of compressed cold
event bodies**, but its full SQLite file occupied **106.49 MB**. Most of
that difference is metadata, indexes and allocated B-tree space; it
cannot be equated directly to expendable bytes without an integrity-
preserving repack.

To test repacking without touching the original, the profiler executed
an offline `VACUUM INTO` SQLite copy **after adding 128 further events**.
The resulting comparison was:

| Original complete SQLite archive | Repacked complete SQLite copy | Repack duration | Approximate allocated-byte reduction |
|---:|---:|---:|---:|
| 106.83 MB | 27.37 MB | 0.069 s | 74.4% |

The profiler reopened the copied database and successfully reverified
its **complete** journal prefix, cursor, original events and archived
open-obligation projection. No source records were retired, and the
original file was not replaced.

The 74.4% number is **specific to this synthetic payload and initial
demotion pattern**; it is not a promised compression ratio for
real ship history, nor a measurement of long-lived incremental behavior.

## Engineering decision

- **Retain full local prefix and obligation verification.** The
  measurements do not justify weakening authenticated historical checks.
  A larger voyage and actual 40-crew restart may need their own profiling
  before treating these single-actor numbers as service startup latency.
- **Apply a narrowly scoped, lossless SQLite repack** only after an
  accumulated 2,048 hot-to-cold demotions **and** enough new cold
  records to represent at least 25% of the total cold archive. This
  prevents quadratic lifetime rewriting at very large voyage scales.
  SQLite's transactional `VACUUM` runs *after* the authenticated
  page/continuity-seal transaction,
  before the native cognition checkpoint advances. The maintenance counter
  persists across smaller reads and resets only after successful completion;
  a crash between those operations can cause a harmless repeat, not lost
  world evidence. No world journal or character-memory data is retired.
  [Implementation and recovery contract](p4f-lossless-repack.md).
- **Do not cap the journal or character knowledge.** World and local
  storage remain O(history). Compaction merely improves allocated-byte
  efficiency; exact old evidence and unfinished work remain addressable.

The standalone [JSON profiler](../../scenarios/profiling/evidence_restart.py)
and machine-readable GitHub Actions artifact make the experiment
reproducible without the expensive world or hosted-model acceptance suite.
