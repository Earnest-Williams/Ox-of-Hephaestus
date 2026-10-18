# Scenario 0 — deterministic P2 watch handover

**Status:** Implemented and retained as a **mock-world regression**.
The scenario below is not a networked Evennia session; **later P3/P4
milestones are**. The real-world counterpart is
[P3c](../../design/prototypes/p3c-live-crew.md), extended with an
[actual game-owned duty timer in P4b](../../design/prototypes/p4b-autonomous-watch.md).
See [today's status](../../design/STATUS.md).

## Crew and authority in this historical fixture

| Member | Room | Start duty | After due handover |
| --- | --- | --- | --- |
| Ari Sen | Engineering | Engineering watch | Relieved |
| Iona Vek | Engineering | Chief engineer, on call | Accepts engineering watch |
| Lin Sato | Bridge | Bridge watch | Remains on bridge; never reads private engineering note |

The P2 mock world owns the roster, locations, virtual clock,
delivered observations, social-command receipts and actual duty
transfer. None of these facts can be changed by describing a desired
outcome in agent text.

## Deterministic virtual-clock timeline

1. `00:00–07:20`: the mock clock advances with no work waiting,
   so there are no agent wake-ups or model calls.
2. `07:30`: Ari receives a **private, unverified** sensor concern.
   Lin receives an unrelated Bridge status; Iona does not learn
   Ari's concern by omniscience.
3. `07:54`: time advances again, without waking anyone.
4. `07:55`: a due-duty observation wakes Ari; he briefs Iona
   face to face in Engineering and preserves the concern as
   **unverified**.
5. The delivered report wakes Iona. Her acknowledgment authorizes
   the **mock world** to change the active engineering watch.
   The world reports the transfer back to the two engineers;
   Lin does not acquire their private observations.

Policies and events are fully deterministic. This is deliberately
not evidence of general conversational negotiation.

## Run the regression

From the repository root with Python 3.12+:

~~~sh
python -m pip install -e ./services/ai-handler
python -m unittest discover -s services/ai-handler/tests -p 'test_watch_*.py' -v
python -m ox_ai.scenarios.watch_handover
~~~

Or select **GitHub Actions → Ox three-crew watch handover →
Run workflow** on `main`. This test requires no LLM, Gemini secret
or Evennia game server.

## What it proves

- Character-private observations and secondhand testimony remain
  distinct; world operator logs never enter agent memories.
- Only a due watch with physical co-location and a matching
  briefing can change assigned duty.
- The handler wakes on observations/duties, not each clock tick.
- The mock world's idempotent action IDs permit lost-ACK recovery
  after checkpoint/restore without replaying world effects.

Source: `ox_ai.ports.mock.watch_world`,
`ox_ai.agents.mock_watch`,
`ox_ai.scheduler.watch` and
`ox_ai.scenarios.watch_handover`.

**Later milestone:** P3 delivered normal Evennia sessions and real
world-authoritative handover; P4b added a persistent Script-owned
due-time event and tested two incidents across a watch change.
Neither newer capability is asserted by this P2 mock alone.
