# G16m — measured real Decider 25-second 6/20/40 actor burst (24 October 2026)

**Actual-native experiment completed successfully; configured deadline
capacity failed.** [Actions run #40123141056](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40123141056),
source commit `b1623ddcc761c4c470701a701cc9b8fe10ccb73a`,
artifact `ox-g16m-actual-q4-25second-six-twenty-forty-burst`
(`native-burst.json`, `native-burst.txt`, `model-manifest.json`).
Its program and structural fixture tests merged via
[PR #129](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/129)
at `a2710ce`, with **32/32 exact-head CI checks**.

## Provenance and workload

The genuine GGUF matches G16f exactly: Decider 4B Q4_K_M SHA-256
`c03deb433d539ef49579fca5a015d5090c739a331448493aded7a57ad9b4261b`,
publisher revision `3b02c98fa0b19e9daab247d633095b6e8a6cd4c5`,
tokenizer revision `d3a78581751d518bbfa9e871a6d84059554d53c5`,
GGUF size 2,708,804,928 bytes. Four reported logical CPUs, native
inference `n_threads=2`, one shared safe native model/worker,
Python 3.12.15. Process Linux peak RSS approximately 5,334,840 KiB.

Each cohort consisted of **6, 20, or 40 distinct original Concordia
brains** with the same private seeded memory/trait workload, opt-in
G16c tagged, three-option G14 non-safety social menu, durable actor
route checkpoint and planned pre-adoption personality-choice checkpoint
as G16f. Their requests were launched within one event-loop scheduling
turn at the configured **25-second wall-clock deadline** (this includes
time waiting for the global scoring worker). The bursts were launched
with measured first-to-last skew 0.0052, 0.0154, 0.0298 seconds
respectively. No Evennia port or ship command was opened.

## Actual native results — not extrapolated G16i queue models

| Actors arriving almost simultaneously | On-time proposals | Deadline-expired decisions | True GGUF System One forwards | Native invocations started | Queued before provider and timed out | Timed out while provider active | Native provider runtime |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6 | **0** | 6 | 3 | 1 | 5 | 1 | 36.680 s |
| 20 | **0** | 20 | 3 | 1 | 19 | 1 | 36.545 s |
| 40 | **0** | 40 | 3 | 1 | 39 | 1 | 36.698 s |
| **Total** | **0/66** | **66/66** | **9** | **3** | **63** | **3** | — |

All three cohorts' callers returned at approximately 25.03 seconds.
The single already-running provider per cohort continued for another
approximately 11.6 seconds after the caller timeout, then was
quarantined and fully drained. Exactly **63 queued expired entries were
discarded before native inference**; no expired queued entry was
inappropriately started. Exactly **three active native workers
completed after abandonment**, with zero adopted proposals, no
personality-choice ledger entry for any expired actor, no pending
original actor request, no leaked active task, and **zero Evennia
commands or work receipts**.

This is **not** a behavioural failure of Decider's choices. Most
actors never reached a model call, and none finished before the
configured deadline. Their durable routing boundaries stayed recorded
as originally deliberative; no fabricated GOAP fallback was made.
The test demonstrates correctly fail-closed containment under
under-provisioned native inference capacity.

## Compare previous actual G16f sequential measurement

[G16f run #40048062817](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40048062817)
on another 4-logical-CPU GitHub runner completed its *sequential*
6/20/40 actor cohort with a measured median of approximately
20.55 seconds per three-pass decision (40-actor P95 21.09 s).
G16i reasonably used that observed time as a **fixed service-time
assumption** and projected one successful decision among 40 arriving
together. The new actual G16m service duration was **36.5–36.7 seconds**
per three native forwards, or approximately 1.78 times as long as
the earlier median. Consequently, **zero**, not one, could finish
under the same 25-second deadline in these actual runner conditions.

Both reports use the exact same pinned GGUF/tokenizer and reported
4 logical CPUs, but GitHub runner CPU entitlement, silicon, contention
and actual effective compute are **not** established as identical.
We cannot identify which hardware/load difference caused the
throughput shift from these two experiments alone. We must not
replace the actual measured tail with a claimed stable 20.55 s
service time, assume all 4-vCPU runners are interchangeable, or
conclude that the user's host CPU/GPU would have the same timing.

## Adoption and next genuine measurements

**The current 25-second timeout is unfit for native Decider Q4
three-pass deliberation in the measured slower CPU environment,
even when no other actor was using the scoring lane.** Automatically
increasing the deadline is *not* an adequate solution for bursts:
it extends waits and can still leave a 40-character queue without
useful duty capacity.

Required before live acceptance:

1. Measure sustained/tail three-forward service time on **the intended
   production host**, with actual co-running Evennia, Concordia and
   ship-simulation load, not only a shared CI runner.
2. Measure real 40-crew *arrival* patterns and route probability;
   routine personality-weighted GOAP should not pay for Decider at
   every trivial action. Evaluate deliberate-route admission,
   bounded queueing and replay-safe deferral **before** committing
   an action. Do not silently turn a timed-out Decider route into a
   different GOAP decision.
3. Test dedicated native inference capacity and scheduling headroom,
   including parallel worker model isolation if explored. Do not share
   one stateful GGUF engine across unsafely concurrent threads.
4. Keep exact position-balanced three-pass scoring. The post-hoc
   adaptive one-pass shortcut changed some personality-adjusted
   choices and is **not** an accepted performance optimization.
5. Independently validate original G16l safety mechanics in real
   safety cases and Evennia action permissions, G16g blinded dialogue
   quality, and authenticated 40-actor receipt/restart recovery.
   All downstream model outputs remain *proposals*.

**No full G16 personality routing adoption or live-supervisor
activation follows from a successfully completed experimental run.
`OX_PERSONALITY_CHOICE` remains OFF.** The objective remains
believable freighter operations and coherent failure consequences,
not certifiable real-spacecraft construction engineering.
