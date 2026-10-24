# G16j — measured queue observability before any 40-actor supervisor soak

**Scope:** instrumentation only. Adds **no personality activation**, no new
world commands, no route-selection changes and no queue admission policy.
The existing `DecisionScheduler` still uses its original timeout, per-actor
quarantine, detached synchronous Concordia snapshot, global semaphore and
world-authority separation. G16i's real-native-informed queue forecasts
remain hypothetical until these process-local measurements are gathered
under an actual supervisor workload.

## What the scheduler records

`DecisionScheduler.metrics["queue_observability"]` exposes:

- Requests accepted for scheduling (one per eligible model request);
  detached inference invocations **started** and **finished**. In G16,
  one invocation may perform **three native System One forwards**. These
  invocations are **not** actual GGUF forward counters.
- Proposals adopted into the original actor's pending request ledger,
  invalid/stale choices refused, errors sanitized, cancellations,
  timeout while **waiting for the global native slot** and timeout
  **while a detached provider invocation is already active**.
- Queued expired entries discarded before ever contacting the provider,
  and model workers that only finished after the caller abandoned the
  decision. Neither counts as a completed choice or a world receipt.
- Current role names waiting/active, highest observed number of
  concurrent **scheduled invocations**, and bounded 256-entry rolling
  samples for queue waiting, time in a provider invocation, and
  end-to-end **adopted** decision latency (median or P95 as appropriate).
  These may be inspected from the event-loop owner without copying
  prompts, memories, API credentials, or model error text.

The pre-existing `metrics["started"]` name remains for compatibility
but counts **billed inference quota units**, not underlying forwards
and not necessarily successful starts. G16 charges 3 units for one
three-pass native request. In particular 2,500 quota units/hour does
not demonstrate 2,500 physical forwards/hour.

## What tests verify

A real async Concordia `CrewAgent` with bounded fake providers:
one successful actual model callback reports one invocation/adoption;
three charged units remain **one** invocation. A blocked real worker
causes a **different** actor to time out while waiting for the same
semaphore: the two failure categories are independently observed;
the queued actor is never sent to inference after expiry. A detached
late completion is quarantined, cannot become a valid action, and is
counted only as abandoned work. A provider exception containing a
fake API secret is never leaked into `metrics` or the public
exception. Bounded samples do not grow beyond 256.

This is instrumentation of **real async scheduling** with fake test
providers, **not** a real two-worker GGUF speedup test. Model profiles
do not become safety or correctness probabilities. Metrics reset on
handler process restart; they are diagnostics, not an authoritative
Evennia journal or event-sourced world receipt.

## Next measured acceptance

Use authentic world event arrivals from the 40-actor Evennia harness
and a genuine G15 three-pass Decider backend, with a bounded duty
schedule and crash/restart recovery. Record true arrival counts, queue
wait medians and tails, actual expired/abandoned native decisions,
the real single/two-worker throughput, the number of unexecuted
proposals, and separately authoritative Evennia receipts. Do not
turn on `OX_PERSONALITY_CHOICE` solely because the telemetry tests
pass. G16e's native personality holdout and G16g blinded speech
quality remain separate required evidence.
