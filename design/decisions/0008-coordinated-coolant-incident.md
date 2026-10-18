# ADR 0008 — Model-free three-crew coolant cooperation

**Status:** Historical P2 model-free mock (2026-10-18); its live counterpart and reviewer interlock now exist.

> **Current implementation note:** The original “chief-release is mock-only” statement below was correct for the first mock experiment, not for the merged P3/P4 game code. Read the appended outcome for today's behavior.

## Motivation and relationship to P1/P2

The live Gemini trial showed unscripted bounded model choices driving the
actual Evennia P-01 pump. The GOAP trial showed symbolic planning could
restore that real pump with zero inference. The P2 watch-handover scenario
demonstrated separate crew memories, an event-driven supervisor, scoped
communications and loss-of-ACK recovery on a deterministic mock world.

This experiment combines those primitives in a *cooperative incident*,
while preserving the world-authority boundary. It remains a mock proof of
the handler's coordination logic, NOT an Evennia network integration.

## Decision

Extend `MockWatchWorld` via `MockCoolantWorld` with a small world-owned
pump state machine and an explicit chief commissioning interlock. Keep
individual crew contexts and use the existing `WatchSupervisor` event
dispatch mechanics:

- **Lin**, on Bridge watch, alone sees the initial bridge alarm and sends
  a radio alert using an authenticated character action.
- **Ari**, on Engineering watch, learns the alarm via Lin and inspects
  equipment locally. His model-free GOAP planner selects physical
  isolation, repair and commissioning actions using symbolic preconditions
  and effects. No predicted effect becomes a world fact.
- **Iona**, on call as chief, receives a secondhand release request.
  She personally inspects the repaired pump and submits an approval;
  the *world* enforces the release and informs Ari. Authorization cannot
  be forged by text or a planner.
- **Ari** independently verifies normal pressure before sending a
  resolution radio report to Lin and Iona.

Every observation has exactly one recipient and a source event ID.
The world records actual transitions and attempts. The handler maintains
separate agent snapshots and an operator-only aggregate trace that is
never passed to agent policies.

Physical actions are idempotent by request ID. A deliberately lost
isolation acknowledgement is reconciled after a handler checkpoint and
restore by looking up the world receipt: no blind replay. An urgent
safety-recheck event increments Ari's observation revision before a
prepared action is submitted; both the supervisor and the world reject
unsafe stale work until Ari inspects P-01 again.

The chief's request/attempt/approval and the engineer's planned effects
remain *beliefs and intents* until individual authoritatively produced
receipt events arrive. No LLM call is required on idle ticks or during
this deterministic incident.

## Validation and boundaries

The incident's default trajectory and failure cases are executable and
verified by stdlib-only unit tests and an optional GitHub Actions trial.
A passing test demonstrates coordination on one specific authored fault,
not general cooperation. In particular, synthetic duty policies and a
predefined radio channel do not yet represent general language dialogue.

The mock chief-release step is additional mechanics beyond the current
real Evennia pump fixture. P3 must either implement it in Evennia as a
world-side interlock or explicitly test the simpler real pump. These two
world scenarios must not be represented as mechanically identical.

Next: external handler-to-Evennia character transport, identity/session
binding and durable reconnect reconciliation, then richer ship systems.


## Later authoritative Evennia implementation (2026-10-18)

[P3c](../prototypes/p3c-live-crew.md) brought actual world-enforced inspection, chief release and radio into ordinary authenticated Evennia sessions. [P4a](../prototypes/p4a-live-cognition.md) added three separate native Concordia actors making bounded decisions (deterministic test model in CI). [P4b](../prototypes/p4b-autonomous-watch.md) then implemented a world-owned duty deadline and a **second fault after handover**: Iona becomes the active engineer, while Ari is delegated independent safety-review authority. The game prevents Iona from signing off her own commissioning. Durable physical action receipts and the tested lost-isolation recovery remain world-authoritative; full arbitrary social-command crash recovery remains outstanding.
