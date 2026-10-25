# G16p — measured service bounds and bounded asynchronous admission

**Registered before the native forty-actor run, 24 October 2026.**

G16o's original 25-second CPU burst-capacity gate failed. Its three verified
host medians were 13.804, 23.638 and 39.797 seconds. Those observations remain
unchanged. A scheduler cannot make forty serial CPU deliberations finish
in 25 seconds. G16p fixes the queue lifecycle for asynchronous deliberation:
admit a bounded amount of work, give dispatched work an appropriate measured
service allowance, and serve the admitted actors instead of expiring almost
everyone behind one worker.

## Runtime contract

`CapacityAwareDecisionScheduler` wraps the existing detached decision scheduler
with **one shared native lane**. It is injected into the actual
`CharacterRouteController` and preserves that controller's existing durable
route, choice, prompt and request-ID contracts. It never submits world work.
It is an opt-in replacement for the scheduler, not a production activation.

- Measure at least six current-backend, current-workload service samples.
  Freeze a planning bound at their maximum **plus 50% headroom**. Unsupported
  bounds above the existing 120-second worker limit are refused rather than
  clipped. Profiles for two and three forwards are separate; both may share
  the same queue. A binary measurement cannot authorize ternary service.
- Bound pending identities, including active, queued and quarantined actors,
  to at most forty in this trial. Same-body aliases cannot double-schedule.
  Reserve remaining quota before admission; bill the existing quota only at
  dispatch. Full admission fails before copying a brain or starting a model.
- Queue lifetime and service deadline are distinct. The trial queue lifetime
  is at most **3,600 seconds**, while each dispatched decision uses its frozen
  measured service bound. Configuration must fit the maximum pending queue
  within its queue lifetime. This permits minutes of waiting and is not a
  25-second response guarantee.
- Fork the actual brain only after acquiring the native slot. Both observation
  and private-cognition revisions must still match the queued ticket. Stale,
  cancelled or expired queued work releases its reservation without inference.
- Preserve the physical worker slot after cancellation or timeout until the
  detached worker really exits. An actual service overrun opens the capacity
  circuit: queued/new work is refused until fresh calibration creates a new
  scheduler. Late results still cannot be adopted or checkpointed.
- Refusal is not a character decision or a GOAP fallback. An unchanged actor
  may retry the original saved route and deterministic request identity.
  New evidence requires ordinary reconsideration, not a reroll of an old route.

The original `DecisionScheduler` retains its legacy default and historical
experiment semantics. Its new per-call service override may only **narrow**
its configured maximum. Production supervisors and personality activation
flags are unchanged; live duty/receipt acceptance remains separate.

## Fixed native acceptance protocol

Use the original SHA-256-pinned Decider Q4, publisher tokenizer, two CPU
threads and one shared engine. Use actual Concordia components, the unchanged
offline binary gauge menu, separately owned synthetic histories, and the
real G16c policy-v2 controller and fsynced route/choice checkpoints.

1. Measure six uncensored sequential decisions in this process under the
   existing 120-second measurement ceiling. Set the service bound once from
   those measurements; do not retune scores, temperatures or personality tags.
2. Offer **forty** distinct actors together to the new bounded queue.
   Acceptance requires **40/40** unexecuted proposals, eighty real native
   forwards and zero queue expirations or service overruns. Report their true
   end-to-end waiting times and total batch duration, even when they take minutes.
3. A 41st actor must be refused before copying, billing or provider execution.
   Preserve its model route. After the batch, retry that same actor and require
   the original deterministic request identity and two real native forwards.
4. Check all durable records and pending proposals, quota accounting, maximum
   pending identities, single-engine serialization, empty final reservations,
   and event-loop heartbeat progress. Retain source hashes and refuse to
   accept results if implementation files changed during execution.

A successful full run makes **94 actual System One forwards**: twelve for
calibration, eighty for the admitted forty, and two for the overload retry.
Fixture mode labels its synthetic profile and forwards explicitly and cannot
establish native throughput. Controlled native-interface unit tests separately
exercise cancellation, overload, quota reservations, stale evidence, safety,
pre-adoption checkpoint failure, service overruns and crash replay.

Passing G16p establishes that the measured asynchronous queue serves its
admitted workload within its declared queue/service limits. It does not erase
G16o's failed 25-second burst gate or prove live forty-person work, arbitrary
future latency bounds, binary psychological calibration or speech quality.
Urgent workloads require their own latency/admission policy; they must not
inherit a long routine deliberation queue merely to claim acceptance.

## Completed native acceptance

The [verified run](g16p-native-admission-results-2026-10-24.md) completed all forty admitted decisions in 1,118.287 seconds, safely refused the extra actor and retried its original route. All 94 real forwards and 41 request IDs were checked; no queue expiration or service overrun occurred. The maximum observed heartbeat gap was 47.276 ms. This passes the declared asynchronous contract while leaving the old 25-second burst gate failed.
