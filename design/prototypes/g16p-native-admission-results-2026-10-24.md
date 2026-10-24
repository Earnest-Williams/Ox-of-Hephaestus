# G16p — verified native asynchronous queue acceptance

**24 October 2026. Bounded asynchronous acceptance PASS: 40/40 admitted
native decisions completed. Production personality routing remains off.**

[Raw native record](g16p-native-admitted-forty-2026-10-24.json) ·
[Preregistered queue/service contract](g16p-measured-capacity-admission.md) ·
[Code PR #132](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/132).

## Result

| Quantity | Observed |
| --- | --- |
| Completed admitted batch | **40 / 40** unexecuted proposals |
| Batch duration | **1118.287 s** (18 min 38 s) |
| Calibration decisions | 6, uncensored |
| Calibration maximum | 29.668 s |
| Frozen provider service limit | 44.501 s, maximum + 50% |
| Separate queue lifetime | 3600 s |
| Peak pending identities | 40 |
| Actual native forwards | **94**: 12 calibration + 80 batch + 2 retry |
| Native worker concurrency | **1** |
| Queue expirations / service overruns | **0 / 0** |
| Final pending / draining roles | **0 / 0** |
| Final unbilled quota reservations | **0** |
| Event-loop heartbeat samples | 56681 |
| Largest observed heartbeat gap | **47.276 ms** |
| Submitted world commands / claimed receipts | **0 / 0** |

Every actor used actual native Concordia components, the unchanged binary
offline gauge menu, a separate synthetic private history and the genuine
Decider Q4 backend. Proposals were checkpointed before adoption and remained
unexecuted. This is native cognition capacity evidence; authenticated
forty-person Evennia work/receipt acceptance remains separate.

The 41st arrival was refused while admission was full, before its brain was
forked or its quota billed. Its original LLM route remained saved without
creating a choice or pending request. After the admitted batch completed,
that same actor retried and obtained the original deterministic request ID,
using two actual native forwards. Billing was 80 units before retry and 82
after retry, with exactly two units for each of 41 dispatched actors.

Queue waiting is recorded in `metrics.capacity_admission.queue_wait_seconds`
and the actor rows' end-to-end durations. The underlying worker's own queue
and service telemetry starts after dispatch; it does not include the outer
admission wait. All 40 requested decisions were served; refusing excess work
was tested in addition to completion, not used as its substitute.

## Independent verification and provenance

The retained JSON SHA-256 is `1d5dfee1f399b065342f1289d84efeff9c021c970f2201153e528687e956c05d`.
The measurement ran locally against the published candidate. The executed source is preserved at
[commit `7347c73`](https://github.com/Earnest-Williams/Ox-of-Hephaestus/commit/7347c732903c9c28d64c28fa678b12e343f3a9d1).
All thirteen retained code/catalog SHA-256 values matched that commit and
were checked again against the local files. All 41 deterministic request
IDs were independently reconstructed from the original actor/profile/route
seeds. Calibration arithmetic, forward counts, adopted actor identities,
quota reservations, worker counts, retry identity and final empty state
were independently checked from the raw record.

The model SHA-256 remains
`c03deb433d539ef49579fca5a015d5090c739a331448493aded7a57ad9b4261b`,
weight revision `3b02c98fa0b19e9daab247d633095b6e8a6cd4c5`, publisher-tokenizer
revision `d3a78581751d518bbfa9e871a6d84059554d53c5`.
This host reported **AMD EPYC 9V74 80-Core Processor**, a cgroup quota of eight CPUs,
nine CPUs in its affinity set, and two native CPU inference threads.
The exact runtime package versions and host metadata are in the raw record.
No model, scoring gain, temperature, personality tag or holdout was retuned.

## What changed operationally

The old shared 25-second queue-plus-service deadline caused callers to expire
behind one worker. The new scheduler reserves bounded admission and quota,
waits for a real slot, rejects changed actor evidence before copying it,
then applies the frozen measured service limit. Cancelled/late workers keep
their physical slot until drain, and a service overrun closes admission for
fresh calibration. Controlled tests exercise those failure paths; none was
required during this successful native batch.

The [original G16o 25-second CPU burst gate](g16o-three-host-native-results-2026-10-24.md)
remains failed and was not retested or reclassified here. This new test proves
bounded asynchronous service over minutes. A strict requirement to answer
all forty within 25 seconds still requires sufficient backend throughput.
The observed heartbeat progress is a process-local measurement, not a live
MUD latency guarantee. Urgent decisions need their own admission/latency
policy; a long routine queue must not silently become their response budget.

Native binary behavioural calibration, independent blinded speech review,
source-tagged live duty offers and authenticated world receipt recovery
remain independent activation gates.
