# Ox implementation status

**Snapshot: 18 October 2026.** This document is the current-state index for
Ox-specific documentation. Earlier ADRs and P2/P3 scenario documents preserve
the design and acceptance criteria of those milestones; they are not live
feature inventories.

**Forward plan (later milestones not implemented):** [reliability-to-autonomy roadmap](ROADMAP.md) and [ADR 0009](decisions/0009-durable-events-and-work.md). Phase 0 planning merged in [PR #21](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/21). GitHub Issues were disabled when tracking was attempted.

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
| P4e — five independently autonomous crew | Tested and merged | [PR #19](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/19); two additional nonprivileged Concordia actors, world-confirmed cargo/environmental work and a lost-ACK cartridge-replacement gate |
| P4f — indexed, paginated crew events | Tested and merged | [PR #22](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/22); world-owned indexed journal, schema-v2 recipient replay, safe legacy import, private handler checkpoints; all 14 applicable CI workflows passed before merge. |
| P4g stage 1 — global world work receipts | Tested and merged | [PR #23](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/23); typed `oxwork` / `oxworkreceipt` interface, global actor-bound receipt IDs, transactional effects; all 15 applicable workflows passed. |\n| P4h — restartable pump stages | PR validation | World receipt IDs persisted before repair, request, independent approval, commissioning and resolution. Multiple killed external handler processes must reconcile the identical IDs without duplicate effects; does not cover arbitrary hail/handover crashes. |
| P5 — browser observatory | **Deferred / not built** | No browser UI, joined handler/world API, or operator dashboard |

**Naming note:** the original Prototype 1 plan used “P4” for the first
real-world pump mechanic, which was actually implemented early. PRs #13 and
#14 use **P4a/P4b** for the later live-cognition and autonomous-runtime work.
These names denote different scopes, not a missing pump milestone.

The [P4b Actions workflow](../.github/workflows/ox-p4b-autonomy.yml) retains
the detailed engineering restart and reviewer regression. It starts real
Evennia, resolves an initial cooling failure, waits for the game-owned watch
deadline, transfers watch from Ari to Iona, injects a second fault, stops and
restarts an external handler, reconciles a deliberately lost isolation ACK,
and verifies the persisted physical event journal without duplicate isolation.
The full focused CI suite passed on `main` following PR #14.

## P4e verified five-crew runtime

[PR #19](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/19)
was merged after **13/13 focused Ox workflows passed** on its final commit.
[The P4e design](prototypes/p4e-five-crew-autonomy.md) details five
independently persisted native Concordia agents, authenticated ordinary
Evennia clients, recipient-private alarms and actor-scoped world receipts
for C-01/A-01. [The new live CI](../.github/workflows/ox-p4e-five-crew.yml)
deliberately loses the acknowledgement of an actual cartridge replacement
before handler restart, then independently verifies that only one spare was
consumed while all three equipment incidents, two player hails and the
engineering watch handover complete. Existing P3–P4d scenarios remain green.

## P4f journal boundary

PR #22 introduces a dedicated `world.CrewEvent` Django table and migrations,
replacing the growing private event list on P-01 as the live event authority.
`oxinbox <cursor>` returns up to 128 recipient-specific records plus a
versioned `ox_inbox_done` continuation marker. The separate handler reads
every page, deduplicates observation IDs and checkpoints per-character
high-water cursors after saving its private Concordia state.

Existing P4e procedural consumers still need full addressed-history scans.
A bounded per-agent incremental work queue, retained-history compaction,
broader crash-safe physical/social actions and the autonomy scheduler remain
future work. P4f does **not** establish arbitrary mid-scene transaction
recovery or general LLM-driven planning.

## What the prototype does today

- **Evennia** owns the seven-room ship, three stateful physical systems
  (cooling P-01, cargo restraints C-01 and atmospheric scrubber A-01),
  the roster, role-local readouts, alarms, private recipient-specific events,
  authoritative timestamps and validated physical effects.
- **The P4e handler** connects as five separately authenticated characters
  (Lin, Ari, Iona, Mara and Teo). Each character has its own native Concordia
  state, scoped observations, choice history and checkpoint. The earlier
  three-crew handler remains supported separately; never run both together.
- **Deterministic GOAP** plans familiar equipment operations; Concordia
  chooses bounded, explicitly offered actions. Evennia alone executes
  permitted actions and supplies the confirmed physical outcome.
- **P4e's `five_crew_service serve`** is an external event-driven supervisor.
  It handles P-01 cooling, A-01 environmental, C-01 cargo, player hails
  and the world-timed engineering handover. Durable isolation/cartridge
  requests are reconciled by the original world request ID after an
  interrupted handler. Idle operation does not require model polling.
- After the handover, **Iona** is the active engineer and **Ari** is the
  separately authorised safety reviewer. Iona cannot certify her own
  commissioning. The first incident has the reverse arrangement.

## What passing tests do NOT prove

- Both three- and five-crew CI use **Concordia's deterministic MockModel**,
  not independently reasoning live hosted models. An earlier opt-in
  single-engineer Gemini trial succeeded, but unconstrained multi-agent
  negotiation, novel diagnosis and language-based coordination are not
  validated by these workflows.
- This remains a **small proving-ground**, even with seven compartments
  and five independent Concordia crew. C-01 and A-01 are locally
  actionable state machines, not general freight
  commerce or high-fidelity life support. Propulsion, skill-by-use
  progression, wider schedules and the full freighter remain future work.
- `serve` is a runnable runtime, **not a hosted deployment or a system
  service**. A disposable CI trial demonstrates two incidents and one
  unknown-isolation recovery; no long-duration soak test or production
  operations guarantee exists.
- **P-01, C-01 and A-01 physical actions** now have actor-bound,
  equipment-specific durable receipts and recovery. Not every social
  command is idempotent or crash-transactional. Arbitrary
  mid-scene service restarts must fail closed until reconciliation logic is
  added; they are not proven to resume every obligation automatically.
- Development account provisioning uses **disposable three- or five-bot
  fixtures** and a shared test credential. It is not a production account-management
  scheme. The prototype server binds to loopback and disables registration.
- P5 and its dual-source authenticated read APIs do **not** exist.

## Read next

- [Getting started](../INSTALL.md) and [ship game commands](../game/README.md)
- [AI-handler runtime and tests](../services/ai-handler/README.md)
- [Architecture and authority boundaries](../ARCHITECTURE.md)
- [Prototype 1 gates](prototypes/01-autonomous-crew.md)
- [P4a](prototypes/p4a-live-cognition.md), [P4b](prototypes/p4b-autonomous-watch.md)
  [P4d departments](prototypes/p4d-ship-departments.md) and
  [P4e five-crew autonomy](prototypes/p4e-five-crew-autonomy.md)
- [Archived P2 test scenarios](../scenarios/shift_handover/README.md) and
  [cooling fault](../scenarios/coolant_fault/README.md)

The inherited `evennia/` package and `docs/` manual remain upstream Evennia
material, not a description of current Ox functionality.
