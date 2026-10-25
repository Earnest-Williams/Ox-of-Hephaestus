# G16o — verified three-host native binary capacity

**24 October 2026. The experiment completed successfully; the operational
25-second burst-capacity gate failed. Production personality choice stays off.**

[Native run #40134451210](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40134451210)
completed all three independently allocated jobs.
[PR #132](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/132)
also passed **56/56 regular code-head checks** at `b5c29a7`.
The [protocol](g16o-balanced-binary-capacity.md) was fixed before execution.

[Host 1 raw JSON](g16o-ci-host-1-capacity-2026-10-24.json) · [Host 2 raw JSON](g16o-ci-host-2-capacity-2026-10-24.json) · [Host 3 raw JSON](g16o-ci-host-3-capacity-2026-10-24.json)

## Measured service and simultaneous arrivals

All hosts reported four logical CPUs. Each used the same pinned Q4 weights,
two native CPU threads, one shared worker, unchanged experimental binary
policy v2 and the existing offline gauge menu. Private actor histories were
explicitly synthetic. Virtual host conditions were uncontrolled.

| Sample | Reported CPU | Sequential median | Six-sample P95 / maximum | On-time proposals: 6 / 20 / 40 arrivals |
| --- | --- | --- | --- | --- |
| 1 | EPYC 9V45 96-Core | 13.804 s | 13.954 s | 1 / 1 / 1 |
| 2 | EPYC 9V74 80-Core | 23.638 s | 23.785 s | 1 / 1 / 1 |
| 3 | EPYC 7763 64-Core | 39.797 s | 39.986 s | 0 / 0 / 0 |

Each sequential baseline had six independently owned Concordia actors and a
120-second ceiling so service time could be measured without censoring these
samples. All eighteen baseline proposals completed. The burst deadline was
unchanged at **25 seconds including queue wait**.

Across the three hosts' 198 burst requests, **6 proposals arrived in time**
and **192 expired**. Of those expirations, **183 never entered native
inference**, while **9 already-running workers completed after abandonment**.
Every late worker drained; the original actors adopted no late choice, and
no timeout changed an already-saved model route into GOAP.

There were **66 real System One forwards**, zero synthetic forwards,
zero submitted world commands and zero claimed world receipts. Proposals
remained unexecuted. These are independent native-controller performance
samples, not authenticated forty-person Evennia work acceptance.

The fastest host served an immediate binary request within the deadline;
the slowest host required about 40 seconds even without queue contention.
Every host failed to serve its full 6/20/40 burst. Binary support alone
therefore does not establish sufficient capacity or a safe universal
25-second service deadline. The separate [local run](g16o-local-binary-results-2026-10-24.md)
measured a 27.024-second median and 0/66 on-time burst proposals.

## Independent archive and source verification

Each ZIP SHA-256 matched GitHub's artifact metadata. Both archived files
were read directly: `binary-capacity.json` and `model-manifest.json`.
The manifest and result agree on the exact 2,708,804,928-byte model, Q4
SHA-256 `c03deb433d539ef49579fca5a015d5090c739a331448493aded7a57ad9b4261b`,
weight revision `3b02c98fa0b19e9daab247d633095b6e8a6cd4c5` and publisher-tokenizer
revision `d3a78581751d518bbfa9e871a6d84059554d53c5`.

All eleven code/catalog source hashes in **each** archive matched PR code
commit `b5c29a7` (33 individual checks). Run commit `11e519c` differs from
that code head only in the final workflow log marker, which says a
measurement was recorded rather than implying a capacity pass.
The jobs installed decider-ai 1.10.0, llama-cpp-python 0.3.36,
Transformers 5.20.2, PyTorch 2.14.1+cpu and the pinned Concordia source.

Actor-row counts, independent identities, adoption/timeout totals, queued
versus active expirations, started/finished invocation counts, two actual
forwards per invocation, empty post-drain worker lists, zero world effects,
median/P95/maximum and the recorded 25% planning headroom were independently
recomputed from the raw records. Fixture timings and censored baselines
cannot establish native capacity.

| Sample | GitHub ZIP SHA-256 | Retained raw JSON SHA-256 |
| --- | --- | --- |
| 1 | `1cb347404343b712486a12251f7ef900d5ff507b2d6fded5178e5fd920d80660` | `5b2bd88e9a184f9b8fd87bbfe76fb25633db46a888ff7ab2d80e6947b35fd168` |
| 2 | `b00c4f3e34d39259cee3d24c6ed6f830f92ac4e7a7c9781a7492b9191d0d6b35` | `0d053f3bd7996edf2e885ecbf611c35c751a0566cc0b44b037fa284461c746c7` |
| 3 | `c33f11d158db9a390dea14876d342e4b46d3c566661345374319a78e9abd4313` | `77f1c3747727c21617f85edea5e244da2c5461b7e78549b4d48e1243f8ec6732` |

## Disposition

Retain Decider Q4 as the already selected scorer and retain the two-pass
binary implementation as an experimental interface improvement. No gain,
temperature, confidence threshold or holdout was retuned. The prior
three-action G16b/G16e evidence retains its original scope.

Before production activation, measure the intended host, provision enough
inference capacity and enforce a compatible admission/deadline policy, then
verify source-tagged offers and authenticated forty-person duty/receipt
recovery. Binary behavioural calibration and independent blinded speech
review remain distinct outstanding gates. No production flag was enabled.
