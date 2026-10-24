# G16l — real native six/twenty/forty-character burst, original 25-second deadline

**Status:** preregistered source and fixture tests prepared; the genuine
Decider Q4 measurement is **not yet a result**. This is specifically the
missing real-workload cross-check for G16f's *sequential* native throughput,
G16i's **hypothetical** queue envelope, and G16j's actual async semaphore
observability. It never activates a production ship supervisor or grants
Evennia world permission.

## Frozen experiment

[Machine-readable preregistration](g16l-native-burst-preregistration-v1.json)
and [reproducible runner](../../scenarios/profiling/g16l_real_native_burst.py).
Use the **same validated 6, 20, 40 private Concordia agent blueprints,
private memories, three-option G16a menu and real G16c position-balanced
personality scorer** as G16f, but now schedule all character requests on
the same asyncio event-loop tick and keep the original *production*
`DecisionScheduler` **25-second queue-inclusive timeout**, not G16f's
120-second relaxed profiling deadline.

Original Decider Q4 native SHA
`c03deb433d539ef49579fca5a015d5090c739a331448493aded7a57ad9b4261b`;
publisher revision `3b02c98fa0b19e9daab247d633095b6e8a6cd4c5`
and tokenizer revision
`d3a78581751d518bbfa9e871a6d84059554d53c5`, two inference
threads. **One shared scoring lane**, deliberately matching the single
actually measured G16f CPU worker rather than assuming the two default
scheduler workers double Q4 throughput.

For every actor: route must be checkpointed before inference, and each
result must be either (a) one fully three-pass scored, personality-shifted,
actor-bound **unexecuted** proposal committed to its own original private
choice ledger, or (b) timeout with **zero adopted proposals and zero choice
ledger**. Expired queued requests must not contact the native model.
A provider already running when its caller times out may continue, but
must be counted as abandoned and waited for; its late output is
permanently discarded. There is **no GOAP fallback**, no synthetic world
success and no server command.

Measure: genuine native System One forward count (three per completed
backend invocation), observed max active native forwards, number of
adopted/expired proposals for all 6/20/40 roles, timeout while queued
versus while active, discarded queued entries, time to expire, time to
reap native orphans, full original identity/checkpoint provenance,
and CPU-runner metadata. Validity is **not** judged by whether a
particular number of actors succeeds before timeout; zero would be an
honestly recorded operational capacity failure.

## Experiment isolation

The lightweight source/fixture PR job runs the real scheduler and Concordia
entity code with a clearly labeled **fake System One scorer**. It also
injects a slow fake native function into the true one-lane asynchronous
scheduler to demonstrate that 6 timed-out actors produce **zero** world
proposals while a real started worker is separately counted from five
never-started queued requests. None of these fixtures is evidence for
actual native Q4 speed or behavioural correctness.

The **genuine model workload** runs only on a dedicated
`experiment/g16l-native-run` branch, with exact pinned GGUF and a
retained raw GitHub Actions artifact. No model call occurs on unrelated PRs.
Original historical G16e actor work and safety thresholds are unchanged.

## What even a passing native run will not establish

This is one measured CPU runner with **one actual native scoring lane**,
using authored synthetic G16f private memories rather than genuine
Evennia 40-character work incidents. It does not measure two concurrently
executing GGUF engines, real-world duty arrival distributions, long-run
model availability, authenticated remote world receipts, six-actor
personality realism, or independent blinded dialogue quality.

Production `OX_PERSONALITY_CHOICE` remains OFF until the original G16e
holdout resolves, G16g human speech evaluation is complete, real
40-actor world/scheduler work is authorized and durable, and decisions
survive recovery with zero duplicate world consequences.
