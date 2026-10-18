# Prototype 1 — Autonomous Crew

**Status:** Approved design and preparatory package structure. **Not implemented.**

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
