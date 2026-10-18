# ADR 0002 — Minimal deterministic Game Master; world owns causality

**Status:** Accepted (2026-10-18); enforced in P2 mock and P3/P4 live tests.

> **Current implementation note:** The distinction between model proposal, private observations and world-owned outcomes is now executable in both mock and real Evennia modes. Later acceptance milestones do not require a narrating generative Game Master.

## Decision

A Concordia Game Master **need not be an LLM narrator**. For tests, use its deterministic/interrupt-driven scheduling facilities where practical; do not ask it to invent equipment outcomes, change ship state or adjudicate who knows what.

Prototype 1 will use **two hosting modes**, sharing the same entity factory and typed world port:

1. **Mock mode:** A tiny deterministic ship fixture owns rooms, equipment, authorised observations and a virtual clock. Experiment with Concordia's interrupt-driven GM, including event masks and timers. Replace its default narratively resolved action events with verified mock outcomes.
2. **Live Evennia mode:** The Ox handler supervisor invokes Concordia entity `observe()` / `act()` as needed. Each NPC initially uses a normal MUD-client connection. Evennia owns the clock, movement, permission checks, skills, duties and physical consequences.

Do not force the native Concordia simulation engine to drive the live Evennia clock merely to preserve the conventional GM object. A purpose-built GM bridge can remain a lightweight interpretation of the world port, not an additional simulation authority.

## Invariants

- `entity.act()` returns an **attempt**, never proof the action succeeded.
- The world backend decides outcome. Loss of acknowledgment means **unknown**, not failed and not safe to retry.
- The handler records state revisions and operation IDs so late LLM decisions cannot silently overwrite a newer situation.
- Character perceptions are scoped by visibility. An ignored event may later be recalled if legitimately recorded; an unobservable event cannot enter a character's memory as a catch-up summary.
- The scheduler is demand/event-driven; background progress may use coarse ticks or deferred catch-up without obliging every NPC to think continuously.
- The mock world's clock is authoritative *only within the mock fixture*. The real server's time comes from Evennia.

## Later evolution

Only after the ordinary-client approach works will we consider a dedicated authenticated Evennia service API acting for multiple characters. The game's normal rules remain authoritative through either transport. Avoid modifying inherited `evennia/` engine code for the first prototype.


## Implementation outcome (2026-10-18)

[P2](../../scenarios/coolant_fault/README.md) uses a deterministic mock world; [P3c](../prototypes/p3c-live-crew.md) and [P4a](../prototypes/p4a-live-cognition.md) operate with real ordinary Evennia characters. [P4b](../prototypes/p4b-autonomous-watch.md) assigns deadline delivery to Evennia's persistent `ShipDutyClock` rather than to Concordia. The live runtime invokes bounded Concordia choices only on relevant work. It does not make physical predictions authoritative, and it still lacks general crash-safe recovery for every social command.
