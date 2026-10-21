# P4f — forty-character historical-evidence restart comparison

**Status:** Instrumentation proposed for review. Do not treat the original
single-actor measurements as observed fleet startup latency.

## What is compared

The [fleet profiler](../../scenarios/profiling/fleet_evidence_restart.py) uses
the production `ActorEvidenceIndex`, original world-compatible cumulative hash
and obligation reconstruction, and complete retained hot/cold records. It builds
40 independent actor-private SQLite archives. Record sequences are **globally
interleaved but addressed to only one character**, so neither identity nor
proof visibility is accidentally shared. The synthetic fleet has:

- 10 actors with 20,000 addressed records each;
- 20 actors with 40,000 records each;
- 10 actors with 60,000 records each;
- 1.6 million total original records, 1,200 characters of text per record;
- enduring source pins and open hails/captain tickets, with matched historical
  openings and resolutions, and production proportional lossless repacking.

Every archive stores its exact generation, addressed cursor and prefix digest.
The timed restart opens the real SQLite file, checks the locally saved
attestation, replays **every original record** through the hash chain and
independently verifies outstanding obligations, then retrieves old proofs.
Disagreement or cross-actor access fails the operation.

Two *hypothetical* startup schedules are measured, alternating AB/BA across
two trials to reduce page-cache ordering bias:

1. **Staggered:** up to four separate actor-local verifications executing at a
   time, with the next queued actor beginning on completion.
2. **Simultaneous:** all 40 actor-local verifications eligible immediately.

These are thread-based local probes for possible service scheduling, **not** a
claim that the current production supervisor starts verification this way.
The existing supervisor services actor inboxes through a single Python process;
the benchmark must not be used to justify a scheduling change without profiling
the actual supervisor. The GIL may limit the benefit of threads while SQLite
I/O contention may increase it.

## Measurements and decision criteria

A machine-readable record captures each actor's SQLite open time, complete
prefix/obligation verification time, historical lookup time, CPU use and time
until its evidence is ready; aggregate wall time, p95 readiness, first readiness,
process CPU, maximum resident memory and Linux block/disk-read counters are
reported separately. Fixture creation, compression and VACUUM are measured
**outside** all restart cohorts. Per-actor CSV-equivalent JSON preserves
heterogeneous history sizes for subsequent diagnosis.

Do **not** change the full-prefix attestation policy merely because aggregate
wall time grows. Compare per-actor CPU to wall time, concurrency throughput
and filesystem counters. If wall time grows with little corresponding CPU
increase, investigate SQLite page-cache misses, I/O or scheduling. If CPU
tracks wall time, inspect JSON decoding, zlib and canonical event hashing
before changing anything. Measure separately on the actual host if deciding
how many actor verifiers to admit concurrently.

## Reproduce

The inexpensive PR smoke, with the actual SQLite code and four actors:

```sh
python -m unittest discover -s services/ai-handler/tests \
  -p test_fleet_evidence_restart.py -v
python scenarios/profiling/fleet_evidence_restart.py \
  --actors 4 --events-per-actor 800 --payload-chars 160 \
  --stagger-width 2 --trials 2 \
  --output .ox-state/profiles/p4f-fleet-smoke.json
```

The heavier experiment, by manually dispatching the dedicated
[GitHub Actions workflow](../../.github/workflows/ox-p4f-fleet-restart.yml)
(or running locally with sufficient time and temporary disk):

```sh
python scenarios/profiling/fleet_evidence_restart.py \
  --actors 40 --events-per-actor 40000 --payload-chars 1200 \
  --stagger-width 4 --trials 2 \
  --output .ox-state/profiles/p4f-fleet-forty.json
```

The 40-actor profile is **not** a routine PR gate. Its initial building pass
creates 1.6 million complete synthetic records; its cost and disk requirements
must be allowed for. A GitHub shared runner cannot guarantee cold OS page
cache or dedicated disk bandwidth. Repeated trial results measure warm-cache
behaviour; do not label them cold-disk measurements.

## What it deliberately does not measure

- Native Concordia `CrewAgent.from_checkpoint` deserialization and memory
  restoration, including any changes in the size of character memory;
- 40 independent authenticated Evennia WebSocket connections and login;
- nonce-bound `oxjournal` certificate round trips or live world inbox deltas;
- 40 concurrently operating supervisor instances or actual physical work;
- LLM calls, cognition scheduling, world journal writes or Postgres contention.

Those are **separate startup stages** and are not to be filled in with
unmeasured constants. A complete operational readiness study should instrument
real authenticated `CrewWatchSupervisor.read_inbox` calls and native
brain restoration on the expected deployment host, without altering world
ownership or loosening receipt authenticity.

**Invariant:** entire world and actor-private history retained, source proofs
available by exact identity, failures closed, no archive promoted without
fresh authenticated world continuity.
