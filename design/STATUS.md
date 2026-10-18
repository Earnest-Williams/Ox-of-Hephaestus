# Ox implementation status

**Snapshot: 18 October 2026.** This document is the current-state index for
Ox-specific documentation. Earlier ADRs and P2/P3 scenario documents preserve
the design and acceptance criteria of those milestones; they are not live
feature inventories.

## Verified implementation

| Stage | Status | Evidence and scope |
| --- | --- | --- |
| P0 — independent packages and contracts | Tested | Handler and interface import/test scaffolds, scoped Ox CI |
| P1 — native Concordia entity | Tested | `ox-concordia.yml`; individual observe/decide/snapshot/restore |
| P2 — three-person deterministic mock | Tested | `ox-watch-handover.yml` and `ox-coolant-incident.yml`; isolated memories, GOAP, mock world authority |
| P3a — real external Evennia sessions | Tested and merged | [PR #10](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/10); client login, puppet challenge, scoped commands |
| P3b — durable equipment actions | Tested and merged | [PR #11](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/11); actor-bound world receipts and lost-ACK recovery |
| P3c — three live crew characters | Tested and merged | [PR #12](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/12); radio, inspection, safety approval, handover on real Evennia |
| P4a — native Concordia across three live crew | Tested and merged | [PR #13](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/13); per-character Concordia entities, finite decisions, MockModel used in CI |
| P4b — ongoing watch supervisor and repeated incident | Tested and merged | [PR #14](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/14); Evennia duty Script, changed active engineer, two real pump incidents, two-process recovery |
| P4c — unattended event dispatch and player hails | Tested and merged | [PR #16](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/16); one continuous supervisor processes pump repair, world-timed watch handover and an addressed human hail |
| P4d — specialist ship departments | Tested and merged | [PR #17](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/17); seven compartments, cargo and atmosphere state machines, five persistent crew bodies, authority and inventory tests |
| P5 — browser observatory | **Deferred / not built** | No browser UI, joined handler/world API, or operator dashboard |

**Naming note:** the original Prototype 1 plan used “P4” for the first
real-world pump mechanic, which was actually implemented early. PRs #13 and
#14 use **P4a/P4b** for the later live-cognition and autonomous-runtime work.
These names denote different scopes, not a missing pump milestone.

The [P4b Actions workflow](../.github/workflows/ox-p4b-autonomy.yml) is
the most complete executable integration demonstration. It starts real
Evennia, resolves an initial cooling failure, waits for the game-owned watch
deadline, transfers watch from Ari to Iona, injects a second fault, stops and
restarts an external handler, reconciles a deliberately lost isolation ACK,
and verifies the persisted physical event journal without duplicate isolation.
The full focused CI suite passed on `main` following PR #14.

## What the prototype does today

- **Evennia** owns the seven-room ship, three stateful physical systems
  (cooling P-01, cargo restraints C-01 and atmospheric scrubber A-01),
  the roster, role-local readouts, alarms, private recipient-specific events,
  authoritative timestamps and validated physical effects.
- **One external handler** can connect as three separately authenticated
  characters (Ari, Lin, Iona) through ordinary Evennia WebSocket sessions.
  Each character has its own native Concordia state, observations, choice
  history and durable checkpoint.
- **Deterministic GOAP** plans familiar equipment operations; Concordia
  chooses bounded, explicitly offered actions. Evennia alone executes
  permitted actions and supplies the confirmed physical outcome.
- **P4c's `serve` entry point** runs the independent event-driven supervisor.
  It handles pump alarms, the initial world-timed watch handover and addressed
  human hails. An interrupted pump isolation can be reconciled by world
  request ID. Idle operation does not require model polling.
- After the handover, **Iona** is the active engineer and **Ari** is the
  separately authorised safety reviewer. Iona cannot certify her own
  commissioning. The first incident has the reverse arrangement.

## What passing tests do NOT prove

- The three-crew CI uses **Concordia's deterministic MockModel**, not
  three independently reasoning live hosted models. An earlier opt-in
  single-engineer Gemini trial succeeded, but unconstrained multi-agent
  negotiation, novel diagnosis and language-based coordination are not
  validated by these workflows.
- This remains a **small proving-ground**, even with seven compartments
  and five crew bodies. Mara (cargo) and Teo (environmental) are present
  as ordinary world characters but not yet Concordia entities. C-01
  and A-01 are locally actionable state machines, not general freight
  commerce or high-fidelity life support. Propulsion, skill-by-use
  progression, wider schedules and the full freighter remain future work.
- `serve` is a runnable runtime, **not a hosted deployment or a system
  service**. A disposable CI trial demonstrates two incidents and one
  unknown-isolation recovery; no long-duration soak test or production
  operations guarantee exists.
- **P-01 equipment** commands have durable, actor-bound receipts.
  The new cargo and atmosphere verbs have physical journals but not yet
  an AI-ready generic receipt/recovery protocol. Not every social
  command is idempotent or crash-transactional. Arbitrary
  mid-scene service restarts must fail closed until reconciliation logic is
  added; they are not proven to resume every obligation automatically.
- Development account provisioning uses a **disposable three-bot fixture**
  and a shared test credential. It is not a production account-management
  scheme. The prototype server binds to loopback and disables registration.
- P5 and its dual-source authenticated read APIs do **not** exist.

## Read next

- [Getting started](../INSTALL.md) and [ship game commands](../game/README.md)
- [AI-handler runtime and tests](../services/ai-handler/README.md)
- [Architecture and authority boundaries](../ARCHITECTURE.md)
- [Prototype 1 gates](prototypes/01-autonomous-crew.md)
- [P4a](prototypes/p4a-live-cognition.md), [P4b](prototypes/p4b-autonomous-watch.md)
  and [P4d departments](prototypes/p4d-ship-departments.md)
- [Archived P2 test scenarios](../scenarios/shift_handover/README.md) and
  [cooling fault](../scenarios/coolant_fault/README.md)

The inherited `evennia/` package and `docs/` manual remain upstream Evennia
material, not a description of current Ox functionality.
