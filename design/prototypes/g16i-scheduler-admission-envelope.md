# G16i — model actor queue admission using verified G16f native latency

**Status: explicitly hypothetical throughput planning, no production scheduler
change, no native concurrency experiment and no Evennia work.** The corresponding
[model](../../scenarios/profiling/g16i_scheduler_envelope.py) reads the
immutable [G16f native output](g16f-native-throughput-results-2026-10-24.md)
from [run #40048062817](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40048062817)
and requires a matching original Decider Q4 GGUF SHA, all three 6/20/40
native cohorts, **198 actual three-pass forwards**, and a **single**
measured serial inference worker. G16i performs **zero new model forwards**.

The real 40-actor *sequential* G16f cohort measured median 20.55 s and
P95 21.09 s per actual three-pass character choice; the production
`DecisionScheduler` currently times a request out after 25 seconds
**including time spent queued for its semaphore**. A serial backend
has at most ~4 seconds of queueing headroom at the observed P95.
This is an empirical capacity reference and a deterministic scheduling
model, **not** a guarantee that P95 is a hard upper latency bound.

The model contrasts normal `queued` behavior (a backend call can start
just before its 25-second deadline and still finish too late, consuming
CPU on an orphaned inference) against a *proposal-only* bounded-admission
policy that refuses a request **before any native work** if the predicted
completion would exceed its deadline. A refused request does not generate
an action, authorize a GOAP fallback, or rewrite an already checkpointed
personality-routing decision. Any future live policy must separately
document and preserve the original route ledger's authority and replay
semantics. No changes are made to the existing scheduler.

Reproducible envelope scenarios cover populations **6, 20, 40**;
all-at-once bursts and staggered arrivals at **3, 10 or 22 seconds**;
40-actor measured median and P95 treated separately as **constant
hypothetical** service times; one real-measured serial service lane
versus **two independent idealized lanes**, explicitly labelled as
*unmeasured hypothetical concurrency*. A separate frozen grid spans
0.5/1/2/4 duty opportunities per actor-hour, deliberation probabilities
0.10/0.38/0.66/1.00 and 12 seeded one-hour Poisson arrival replicates
per condition. These rates and arrival models are **assumptions**, not
observed crew demand or a validated probabilistic model.

Under the P95-as-constant one-lane queue model, **only one of 40
simultaneous deliberations** could complete within the configured 25 s.
Even an idealized unmeasured two-lane system would complete at most two.
Staggering 40 independent decisions at 22-second intervals instead
allows forty modeled completions, conditional on the assumed service
duration, without new hardware or less complete personality scoring.
This is a strong warning against equating **175 serial decisions/hour**
with a **40-at-once** operational guarantee.

Before any live-soak activation: (1) measure real G16 character
deliberation **arrival** distributions under actual authenticated
observations/duty schedules; (2) test actual native inference concurrency
and full scheduler deadlines, including pending/abandoned workers;
(3) decide a replay-stable admission/defer rule **before** persisting
a new route or fail safely without inventing GOAP behavior;
(4) preserve all G16e safety/behavioural evidence and G16g dialogue
limits; (5) verify authoritative Evennia world receipts separately.

Do not claim this model is a real 40-character stress test, 40 simultaneous
native model runs, a service-level guarantee or a passing G16 policy gate.
