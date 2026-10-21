# P4f — forty-character historical-evidence restart comparison

**Status:** The initial 40-character, two-width profile passed on 21 October
2026 in [GitHub Actions run 39676403054](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39676403054). A follow-up six-width experiment extends the measurements, without changing actor counts, evidence rules or live supervisor concurrency. These local archive timings are not end-to-end fleet startup latency.

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

The first experiment compared **four concurrently active verifiers** with
**forty concurrently active verifiers**, processing the same forty distinct
characters. The follow-up profiles worker widths **1, 2, 4, 8, 16, 40**,
again keeping the same 40 historical archives. Two trials run candidate
widths in forward/reverse order to reduce page-cache and runner-order bias.

Each width controls the number of simultaneous *archive verification tasks*,
never the number of characters represented. The 1-worker case verifies all
forty characters, one after another. The 40-worker case also verifies all
forty, but all tasks compete immediately.

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
  --stagger-width 2 --widths 1,2,4 --trials 2 \
  --output .ox-state/profiles/p4f-fleet-smoke.json
```

The heavier experiment, by manually dispatching the dedicated
[GitHub Actions workflow](../../.github/workflows/ox-p4f-fleet-restart.yml)
(or running locally with sufficient time and temporary disk):

```sh
python scenarios/profiling/fleet_evidence_restart.py \
  --actors 40 --events-per-actor 40000 --payload-chars 1200 \
  --stagger-width 4 --widths 1,2,4,8,16,40 --trials 2 \
  --output .ox-state/profiles/p4f-fleet-forty.json
```

The 40-actor profile is **not** a routine PR gate. Its initial building pass
creates 1.6 million complete synthetic records; its cost and disk requirements
must be allowed for. A GitHub shared runner cannot guarantee cold OS page
cache or dedicated disk bandwidth. Repeated trial results measure warm-cache
behaviour; do not label them cold-disk measurements.

## Completed initial 40-actor two-width measurement

The [first full Actions benchmark](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39676403054)
completed successfully on an Ubuntu runner with four logical CPUs, Python
3.12.15, SQLite 3.46.1 and 1,267,527,680 bytes (~1.18 GiB) of retained
local actor archives. All 1.6 million original records and private obligations
were reverified in each test. Fixture creation took 222.416 seconds and is
**excluded** from the following figures.

| Metric (median, 2 trials) | 4 verifier threads | 40 verifier threads |
| --- | ---: | ---: |
| Cohort wall time | 142.35 s | 237.24 s |
| First character evidence ready | 7.22 s | 117.94 s |
| 95th-percentile character ready | 137.93 s | 237.23 s |
| Process CPU time | 229.69 CPU-s | 467.22 CPU-s |

All rounds reported zero physical disk-read bytes and zero major page faults.
The 40-thread penalty in this environment is therefore not demonstrated
physical disk contention. The measurements do **not** distinguish the GIL,
Python scheduling and internal SQLite thread competition individually.
Four-way startup is significantly better than forty-way startup on that
runner, but the optimal width is **not yet known**.

## Follow-up width sweep

The expanded profiler preserves the initial two-width CLI by default.
The opt-in full 40-character suite now runs worker widths
`1,2,4,8,16,40` with the exact same generated actor-private archives.
The dedicated PR smoke uses four actors and widths `1,2,4`, solely for
regression testing of measurement and identity invariants; the actual
full-scale benchmark always specifies `--actors 40`.

The sweep must report whether concurrency pays for itself on the four-vCPU
runner. It must **not** silently introduce a production scheduler or change
which events can be known, remembered or authenticated by an actor.

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
