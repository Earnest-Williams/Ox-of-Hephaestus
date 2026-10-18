# Prototype 1 — autonomous crew implementation and test gates

**Status: P0–P4b implemented/tested as bounded proofs; P5 deferred.**
This supersedes earlier “P3 is still pending” prose in the original
planning notes. See [current implementation matrix](../STATUS.md) and
[system architecture](../../ARCHITECTURE.md) for the verified boundaries.

## Aim

Prove three distinct persistent cognitive agents can observe the
same authoritative Evennia spaceship from **different legitimate
perspectives**, use model-free technical procedures and selective
bounded decisions, and coordinate consequential in-world work
without a second omniscient Game Master.

This is **not** yet a full bulk cargo ship, a generic NPC personality
system or a high-fidelity real-time economic simulation.

## Implemented gates

| Gate | Current status | Executable evidence |
| --- | --- | --- |
| P0 — separate packages/contracts | **Passed** | Importable handler and interface scaffolds, focused contract tests |
| P1 — one Concordia engineer | **Passed** | Native component graph, observe/act, journal, checkpoint/restore |
| P2 — deterministic mock three-crew | **Passed** | Scenario 0 watch handover and Scenario 1 GOAP coolant fault, mock receipts and scope tests |
| P3a — ordinary client transport | **Passed** | Per-account WebSocket authentication and character binding, real Evennia sessions ([PR #10](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/10)) |
| P3b — durable physical actions | **Passed** | World-held receipt IDs and GOAP restart/reconcile test ([PR #11](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/11)) |
| P3c — live three-crew coordination | **Passed** | Game-authoritative radio, physical inspection, chief release, handover and private events ([PR #12](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/12)) |
| P4a — three native Concordia actors | **Passed (deterministic test model)** | Each character independently observes and chooses from bounded options on real Evennia ([PR #13](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/13)) |
| P4b — persistent event-driven runtime | **Passed (bounded two-incident trial)** | Game-owned duty timer, changed duty/reviewer, handler process restart, no duplicate isolation ([PR #14](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/14)) |
| P5 — observatory | **Deferred / unimplemented** | No joint world/cognition web view or published inspection APIs |

**Historic naming:** The *original* milestone called “P4” meant
installing a simple Ox-specific pump mechanic in the Evennia game,
and that mechanic was completed *before* the later P4a/P4b PRs.
P4a and P4b refer to further cognition/autonomy work, not delayed
construction of P-01.

A gate is marked passed only within the acceptance scope of its
runnable tests; a model making a finite MockModel choice is **not**
evidence of general unscripted reasoning.

## Character cognition, GOAP and Game Master

Each significant prototype crewmember has an individual native
Concordia `EntityAgentWithLogging`, immutable character identity,
personal observations and memory, duties, goals and a checkpointable
pending-request record. Multiple logical agents are supervised by
one external process, not one OS process per character.

Routine engineering decisions can use **zero-inference GOAP**
search on known technical prerequisites and learned physical state.
Selective Concordia decisions use a **finite, world-relevant
menu**. A model may defer; there is no hidden direct world-write
capability. The native deterministic MockModel used in CI verifies
software integration and replayability. The earlier hosted Gemini
experiment is a separate **single-engineer** evaluation.

The P2 Game Master is deterministic: it routes world events and
validates scenarios but does not invent physical changes. In live
Evennia the game itself is the sole physics, time and authority
provider. The external handler invokes entities on genuine events
without a narrating LLM GM or per-NPC calls every world tick.

## Scope of legitimate observation and action

- A Bridge alarm initially belongs to Lin. Ari or Iona learns it
  only after an in-world radio delivery. A local pump readout is
  delivered only to a character actually in Engineering.
- Recipient-specific `ox_event` packets have stable event IDs,
  explicit character dbrefs and game timestamps. Private inbox
  catch-up is filtered by Evennia and checked again by the handler.
- Physical `oxaction` operations require location, the active
  engineering role, applicable pump state and any independent
  commissioning authorization. A world `ox_receipt` confirms the
  actual result; missing ACK means **unknown**.
- World-owned `ShipDutyClock` fires due-watch events. After the
  tested handover, Iona becomes the active engineer and Ari
  the independent safety reviewer. They may not self-approve.
- The handler checkpoints native memory and unresolved requests
  and can reconcile the specifically tested lost-isolation ACK
  without reapplying the physical command.

See [P3a transport](p3a-transport.md), [P3b receipts](p3b-durable.md),
[P3c live crew](p3c-live-crew.md),
[P4a cognition](p4a-live-cognition.md) and
[P4b runtime](p4b-autonomous-watch.md).

## How the demonstrations differ

**Scenario 0/1 (P2):** zero-model, isolated Python mock ship and
deterministic world clock. These are retained rapid regressions; they
**do not** involve actual network characters.

**P3c:** three ordinary client sessions coordinate one game-owned
incident with scripted role policies. Private information stays
private, but broad cognitive autonomy is not claimed.

**P4a:** three native Concordia entities each make bounded choices,
a GOAP engineer performs world-approved physical work, and the
world enforces chief release and watch handover. CI is
**deterministic**, not a hosted-model intelligence benchmark.

**P4b:** Evennia's real persistent duty Script (not the P3
incident-close time jump) triggers watch handover. The second
cooling incident belongs to Iona; Ari reviews. The external
supervisor's process is restarted after an unknown isolation,
which is reconciled against the same Evennia world receipt.
Two complete pump cycles are independently verified.

The [P4b CI workflow](../../.github/workflows/ox-p4b-autonomy.yml)
contains the most demanding present acceptance test.

## Remaining validation and development risks

- **Not proven:** unscripted three-LLM discussion, novel
  diagnosis, independent long-term objectives, adaptive free-form
  escalation or broad skills/use-based progression.
- **Limited recovery:** unknown physical-isolation reconciliation
  passes; generic interruption during every later radio, approval,
  handover or other non-idempotent action does not.
- **No permanent deployment:** `serve` exists, but there is no
  managed daemon/unit, lifecycle monitor, long-duration soak
  test, public network hardening or multi-account secret manager.
- **No interface:** P5's read-only joining of game truth and
  individual beliefs is intentionally postponed.
- **No full freighter:** only P-01, the roster, three crew and
  three rooms are present.

Reevaluate the architecture if synchronous Concordia work blocks
urgent decisions, recovery fails under documented states, or
per-agent inference demand becomes unmanageable. Keep the
authoritative Evennia boundary intact even if the cognitive
provider or transport changes.

## Earlier mock phases and historical design

- [Watch handover fixture](../../scenarios/shift_handover/README.md)
  with [ADR 0007](../decisions/0007-three-crew-watch-supervision.md).
- [Cooling fault fixture](../../scenarios/coolant_fault/README.md)
  with [ADR 0008](../decisions/0008-coordinated-coolant-incident.md).
- [Concordia selection](../decisions/0001-concordia-first.md)
  and [world causality](../decisions/0002-game-master-world-authority.md).

The mock documents describe **historical steps** that led to P3/P4;
their earlier “future P3” phrasing should not be interpreted as the
current project status.
