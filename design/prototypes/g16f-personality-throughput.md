# G16f — measure genuine 6/20/40 actor scheduler capacity

The existing [G12](g12-concordia-profile.md) benchmark measured only
native **Concordia dispatch** with a cheap synthetic response. G16f
measures the implemented **G16c** character choice path: original
Concordia memory context, per-character dispositions, three position-
balanced calls, independent ephemeral worker, exact actor's G16a tagged
menu, BLAKE2b draw, durable actor-private choice ledger, fsynced
checkpoint, and pre-adoption request validation. Neither path sends
work or makes the world accept a proposal.

The [test/fixture workflow](../../.github/workflows/ox-g16f-throughput.yml)
profiles six, twenty and forty native Concordia brains both *sequentially*
and in a simultaneous burst with a single shared two-worker scheduler.
Each real actor gets a distinct identity, six seeded private recollections,
two temporal memory entries, and one paired/recorded choice. Every
cohort must complete exactly 3 Decider-format backend forwards
per actor, leaving exactly one pending unexecuted finite command.
Thus 18 + 60 + 120 = **198 forwards per three-cohort run**.
The synthetic System One backend returns fixed probabilities and
the measured result is **not a real GGUF inference latency**.
No inference-quality result may be inferred from this fixture.

[G16f profiler](../../scenarios/profiling/g16f_personality_throughput.py)
also accepts `--engine decider-q4` with a verified exact
GGUF/model+tokenizer SHA manifest. This genuine native mode runs
the **same 66 actor consultations, 198 real Decider Q4_K_M forwards**
on one pinned 2-thread CPU engine with `max_parallel=1`, a
120-second per-decision timeout for this isolated benchmark, and
the identical durable router/agent code paths. By running its cohorts
sequentially, it measures actual forward latency and sustained service
capacity with 6, 20 and 40 actors, but **not** concurrent native engine
speedup. That latter claim would require separate thread-safe engine
testing. The configured live default `DecisionScheduler` timeout
is 25 seconds and parallel cap is 2; those are compared explicitly
against the measured actual Decider three-pass latency.

Record the median and P95 end-to-end decision latency, each real/native
forward latency, checkpoint write times, memory footprint and
decisions/hour **per measured backend**. Peak Python+native process RSS
from Linux `ru_maxrss` is only a sample, not a complete fleet model.
Never substitute synthetic throughput for native results, extrapolate
linear parallel speedup, or treat a model choice as completed ship work.
With 40 characters sharing a CPU, the decision-arrival pattern and
queue deadlines are as important as the nominal per-actor forward budget.

**Activation remains withheld** until the separate G16e preregistered
personality evidence, G16g dialogue comparison, balanced alternative-model
experiment and real supervisor soak demonstrate a viable policy.
