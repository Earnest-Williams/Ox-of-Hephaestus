# Scenario 0 — Event-driven watch handover (runnable P2 mock)

**Status:** Implemented mock-world scenario and regression tests in the handler.
This is **not** yet an external Evennia connection, real-time ship server
or general crew AI.

## Cast and duty roster

| Member | Location | Duty at 00:00 | After 07:55 handover |
| --- | --- | --- | --- |
| Ari Sen | Engineering | Engineering watch, 00:00–08:00 | Relieved |
| Iona Vek | Engineering | Chief engineer, on call | Accepts engineering watch |
| Lin Sato | Bridge | Bridge watch, 00:00–08:00 | Continues her bridge watch in this bounded mock |

Iona temporarily acts as Ari's relief; this first fixture does not
introduce a fourth engineer. Her acceptance changes the mock world's
authoritative engineering-watch roster. Lin is neither part of the
engineering conversation nor given access to its contents.

## Timeline

- 00:00–07:20: the mock clock advances. No observation or scheduled
  obligation arrives. **No agent is awakened and no inference occurs.**
- 07:30: the engineering sensor delivers an **unverified**
  pressure-oscillation observation **only to Ari**. The bridge plot sends an
  unrelated status **only to Lin**. Iona has received neither.
- 07:54: the world clock advances again. No new work is initiated.
- 07:55: a scheduled duty wakes Ari via a world-authorised event. He uses
  his own remembered sensor note to deliver a handover report to Iona, who
  is physically in the same Engineering compartment.
- Iona is awakened by the **delivered report**, not by reading Ari's memory.
  She accepts the briefing; only the mock world changes the active engineer.
- The acceptance is delivered back to Ari and Iona. Lin still knows
  nothing about the unverified engineering concern.

This is deterministic event-driven policy, not generalized planning.
No high-frequency NPC polling occurs. Actual time is advanced explicitly
by the fixture; resident background process integration comes later.

## Run locally

From the repository root, Python 3.12+:

```bash
python -m pip install -e ./services/ai-handler
python -m unittest discover -s services/ai-handler/tests -p 'test_watch_*.py' -v
python -m ox_ai.scenarios.watch_handover
```

Or after merge, on GitHub: **Actions > Ox three-crew watch handover >
Run workflow** (branch main). This job needs neither the Gemini secret
nor Concordia. Its JSON artifact contains an **operator-only** event ledger
and independent character memories.

## Invariants and acceptance

- Mock world authoritative for clock, rooms, character membership,
  delivered communications and duty transfers.
- Agents receive typed WorldObservation events addressed to their own
  character. Privileged world operator logs are never delivered to policies.
- Chief receives Ari's report as **secondhand testimony**, not as the
  original sensor observation. Bridge officer never learns the concern.
- A briefing requires a due handover and physical co-location. Iona
  cannot take watch without a delivered, matching report.
- Each request ID is executed at most once. After a lost acknowledgment,
  a restarted handler queries world history rather than retrying.
- Quiet simulated time means **zero wakeups** and zero model calls.
- Tests cover scope isolation, clock, forged reports, delivery budget,
  deduplication, snapshots and unknown outcomes.

## Source boundaries

- `services/ai-handler/src/ox_ai/ports/mock/watch_world.py` — mock roster,
  world clock, scoped communications and audit history.
- `services/ai-handler/src/ox_ai/agents/mock_watch.py` — three independent,
  deterministic agent policies and private event memories.
- `services/ai-handler/src/ox_ai/scheduler/watch.py` — wake-up routing, duty
  events, checkpoint and world outcome reconciliation.
- `services/ai-handler/src/ox_ai/scenarios/watch_handover.py` — runnable story.
- `services/ai-handler/tests/test_watch_handover.py` — acceptance tests.

**Still incomplete:** P2 mock coolant-fault coordination, P3 ordinary-client
transport into Evennia, live duty scheduling, durable world/handler storage,
and the read-only observatory. This test alone does not complete all P2 gates.
