# Prototype 1 — Autonomous Crew

**Status:** P0/P1 are tested. Both Gemini and GOAP have repaired the real Evennia P-01. P2 includes verified deterministic mock watch-handover and coordinated coolant-fault scenarios with three scoped crew identities, GOAP repairs, urgent interruption, and lost-ACK recovery. Three Concordia-driven crew agents and P3 external Evennia transport remain unimplemented; P5 observatory remains future work.

## Aim

Prove persistent Concordia-powered NPC autonomy in a mechanically authoritative world, first with a deterministic mock fixture and then with ordinary Evennia clients. This is not a full spaceship or high-fidelity economic simulation.

## Non-goals

Do not change inherited `evennia/` engine code, add a privileged AI game API, build ship-wide mechanics, adopt a second agent framework, simulate every NPC at high frequency, or commit to a final web frontend or model.

## Work packages and gates

| Gate | Implementation | Acceptance |
| --- | --- | --- |
| P0 — scaffold | Separate handler/interface packages, ADRs, contract and scenarios | Importable package skeleton and contract tests; no misleading runtime claims |
| P1 — one entity | Concordia factory, model adapter, observe/act, structured traces, snapshot/restore | One engineer can observe, decide and restore their history |
| P2 — mock crew | Three entities, minimal deterministic GM, mock rooms/communication/clock, scoped event dispatch | Pass watch-handover and cooling-fault fixtures without GM model calls |
| P3 — live transport | Ordinary Evennia WebSocket clients, account/character binding, command framing, reconnect and game-time sync | Three NPCs move, look, speak and perform handover in a stock Evennia game |
| P4 — one Ox mechanic | Game-template pump object with inspect/fault/isolate/repair commands | Same fault scenario resolved by authoritative Evennia commands |
| P5 — observer | Read-only handler API and UI joined with authorised Evennia data | Inspect live ship condition, individual beliefs, attempted actions and outcomes |

A gate is complete only after runnable evidence is recorded; documentation alone does not qualify.

## Cognitive baseline

Build each Concordia entity from the minimal prefab or equivalent base. Start with identity, observation-to-memory, recent observations and list memory. Add Ox-specific duties, commitments and procedures. Introduce selective planning/reflection when a situation requires it.

Routine actions may take a deterministic path; surprising or social situations may request inference. No one-LLM-call-per-tick design. Use one inference backend for all logical actors, with explicit concurrency limits and urgent-event priority.

## World boundary

The temporary Python `WorldPort` contract lives in `services/ai-handler/src/ox_ai/ports/base.py`. It is provisional and not the eventual HTTP or WebSocket schema.

- `receive(character)` returns only observations that character could legitimately obtain.
- `submit(request)` returns a world outcome or an explicit ambiguous/pending state.
- Every request has an ID; agents carry state revisions to detect obsolete proposals.
- Game time is read from the world backend, not independently advanced by the AI model.
- On reconnect or restart, reconcile unknown actions; do not blindly retry a valve command.

Concordia's interrupt-driven Game Master can run the mock scenario, but it must not independently assert that text describing a repair makes that repair real. Live Evennia integration may call entities directly under an Ox supervisor without running Concordia's conventional simulation loop.

## Preparatory game fixture (not a completed integration gate)

The standalone [`game/`](../../game/README.md) test ship gives us real Evennia compartments and pump mechanics before hooking up the agents: bridge, passage, engineering, three idle NPC characters, a status console, a static watch roster and persistent pump state. It is populated once at initial startup (or through an idempotent manual bootstrap) and verified by separate SQLite-backed CI tests. A [local in-process trial](../../game/README.md#experiment-can-an-ai-engineer-physically-fix-p-01) now passes proposed Concordia commands through the regular Evennia command dispatcher, with a strict independent physical outcome verdict. CI's scripted-choice model only proves the wiring. P3 still requires normal-client connections, and P4 still requires autonomous fault resolution evidence from a live model.

## P2 watch-handover checkpoint (2026-10-18)

Scenario 0 now has a runnable deterministic mock:
`ox_ai.ports.mock.watch_world.MockWatchWorld` owns a 07:55 engineering
handover, physically scoped communications, monotonic clock, world events
and roster changes. `ox_ai.scheduler.watch.WatchSupervisor` drives three
distinct policies only when messages or scheduled duties arrive. Separate
Ari/Iona/Lin memories establish that Iona learns an unverified concern
from Ari's briefing while Lin never learns it by omniscience. Quiet periods
cause no wakeups or inference. Handler checkpoint/restore reconciles an
unknown world ACK using its request ID rather than resubmitting.

See [Scenario 0](../../scenarios/shift_handover/README.md) and
[ADR 0007](../decisions/0007-three-crew-watch-supervision.md).

**Gate assessment:** watch handover is tested, but P2 as defined above
remains open pending cooling-fault mock coordination. The mock test is
not a permanently running Evennia ship and does not satisfy P3.

## P2 coordinated coolant-fault checkpoint (2026-10-18)

The second P2 mock scenario, [Scenario 1](../../scenarios/coolant_fault/README.md),
is now executable. Lin receives the world-side bridge alarm, radios Ari,
and Ari inspects the local pump and plans operations using the same
dependency-free GOAP search engine. Iona receives a first-hand local
inspection opportunity only after Ari requests chief safety release.
The world validates permission, state transitions, the chief signoff and
the final resolution report.

An urgent world event invalidates an Ari action proposal before it reaches
the world; world permissions independently require a new safety readout.
A separate test loses the ACK for successful isolation, checkpoints the
handler, restores the three private cognitive states and reconciles the
operation by request ID without replaying it. Quiet periods still wake
no agents and use zero inference. See [ADR 0008](../decisions/0008-coordinated-coolant-incident.md).

**P2 interpretation:** Both authored mock acceptance scenarios have runnable
evidence for event routing, the mock world's authoritative clock, scoped
communication and physical effects. The policies are deliberately
deterministic; they do not prove open-ended emergent cooperation or three
native Concordia actors. The mock chief-release interlock is not yet
present in the actual Evennia pump fixture. P3 is the next substantial
integration: normal per-character Evennia clients and a separately
running, restartable supervisor.

## First scenarios

1. [Scenario 0 — Watch handover](../../scenarios/shift_handover/README.md): minimal observation, communication, memory, duty timing and permissions.
2. [Scenario 1 — Cooling fault](../../scenarios/coolant_fault/README.md): autonomous attention, diagnosis, coordination, interruption, physical resolution, and recovery.

## Evidence required for P2–P5

Track inference requests/tokens, model latency, decision trigger, retrieved memory IDs, relevant beliefs, state revision, command ID, world event ID, known outcome, and wall/game time. Evaluate:

- Three distinct coherent NPC identities with divergent legitimate knowledge.
- Correct scope of all observations and no accidental omniscience.
- Zero LLM calls by the deterministic GM and no pointless idle inference.
- Plausible unscripted cooperative action (not merely convincing prose).
- Correct response to an urgent event during a pending decision.
- No duplicated physical action after transport disconnect, timeout or service restart.
- Checkpoint and journal allow restoration of unfinished obligations.
- At least one inspectable read-only view joins game state to cognitive records.

## Stop / reevaluate conditions

Reconsider the specific Concordia integration strategy if synchronous `act()` calls block urgent-event handling, the richer prefabs require unsustainable inference, entity state cannot be safely restored, or the native interrupt scheduler proves costly to decouple from its environment. Keep the externally visible world port stable so we can swap the cognitive execution strategy without restructuring the game.
