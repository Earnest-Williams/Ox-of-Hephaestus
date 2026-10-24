# G16f — native Decider 6/20/40 CPU throughput result (24 October 2026)

**Measured, not synthetic.** [GitHub Actions #40048062817](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40048062817) completed all actor and full-weight native checks. The retained artifact `ox-g16f-actual-q4-cpu-six-twenty-forty` contains `native-throughput.json`, `native-throughput.txt` and the model-provenance manifest. Source experiment commit: `e9e266a3f6d4c37b67b280dc778eb36cf2927942`. The G16f implementation subsequently merged in [PR #119](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/119) at `717e713` after **32/32 exact-head CI checks passed**.

## Native workload

- **Real Decider 4B Q4_K_M GGUF**, verified SHA-256 `c03deb433d539ef49579fca5a015d5090c739a331448493aded7a57ad9b4261b`, publisher model revision `3b02c98fa0b19e9daab247d633095b6e8a6cd4c5`, tokenizer revision `d3a78581751d518bbfa9e871a6d84059554d53c5`.
- Runner Linux x86-64, Python 3.12.15; 4 reported logical CPUs; one shared native model, **2 native inference threads**, **one scoring worker**. Peak observed Linux ru_maxrss **5,339,288 KiB** (sample, not complete fleet memory).
- **66 real distinct Concordia actor consultations**, in cohorts 6, 20 and 40. Each had an original character mind/private memories and a tagged, finite G16c choice; one unexecuted pending action and an fsynced personality-choice checkpoint. **198 genuine native System One forward calls** across all cohorts, no provider mocks, no Evennia work commands.
- This benchmark used *sequential* decision arrivals, not a simultaneously active 40-actor queue. A separate synthetic two-worker burst test checks scheduler logic but is **not** real native concurrency evidence.

| Measurement | Native result |
| --- | ---: |
| All native forwards | 198/198 |
| Median single forward | 6.8512 s |
| P95 single forward | 7.1067 s |
| Three-forward median-based estimate | 20.5537 s |
| Configured production decision timeout | **25 s** |
| Default concurrent scheduler capacity | 2 |
| Per-hour inference budget (configured, not achieved) | 2,500 forwards |

| Actors | Real forwards | Completed decisions | Cohort wall time | Median end-to-end | P95 end-to-end | Measured decisions/hour |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6 | 18 | 6/6 | 119.53 s | 19.97 s | 20.14 s | 180.71 |
| 20 | 60 | 20/20 | 414.77 s | 20.85 s | 21.29 s | 173.59 |
| 40 | 120 | 40/40 | 822.39 s | 20.55 s | 21.09 s | 175.10 |

The CPU service rate is **approximately 175 completed three-forward decisions per hour** on the measured machine, or ~4.4 deliberations per hour per character when averaged across forty equally active characters at full saturation. This latter figure is an arithmetic capacity allocation, not a measured duty schedule or real decision arrival rate. A robust operational budget needs headroom and a measured burst profile. The written 2,500-forward/hour quota does **not** mean this CPU can deliver ~833 three-forward choices/hour.

## Engineering interpretation — performance is not yet an acceptance gate

With a 25-second deadline, a single ~20.5-second deliberation fits when started immediately, with little margin for waiting or machine contention. **Forty requests arriving simultaneously are not supported by this sequential profile**: queued requests would exhaust their deadlines even if the model later became free. The current experiment never measured parallel native throughput and must not be interpreted as a 40-actor burst pass.

Next verify the real 40-character supervisor's per-hour *demand* for deliberate routes, burst-size distribution, queue waits and expired requests. Keep routine/low-consequence choices on personality-weighted GOAP to avoid burning CPU on every action. Potential improvements (staggered scheduling, deadline-aware priority, additional inference capacity or a justified *new* adaptive balance experiment) require independent tests; do not silently replace G15's full three-position score with a biased one-pass choice.

A real hardware throughput result supports designing the capacity policy, **not** G16e personality correctness, G16g speech preference, or live-supervisor activation.
