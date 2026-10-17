# Scenario 1 — Cooling pump fault

**Fixture specification only. Not yet executable.**

## World

Three connected areas: engineering compartment, connecting passage, bridge. Three full NPCs: chief engineer, watch engineer, bridge watch officer. The mock backend owns the authoritative equipment and time state.

A minimal pump state machine for the fixture is `normal -> low_pressure -> isolated -> repaired`. Exact repair mechanics are intentionally trivial. This is a test of NPC autonomy, not mechanical fidelity.

## Initial knowledge

The watch engineer can encounter the original pressure indication. Other NPCs initially have no direct observation of the fault and must learn through valid communications, later inspection, or other available in-world channels.

## Exercise

Over a nominal eight-hour **simulated** watch:

1. Begin with routine duties and no critical event.
2. Introduce declining coolant pressure as a scoped observation.
3. Allow investigation, communication and coordination; do not script the agents' decisions.
4. Inject an urgent interruption during a pending deliberation; reject or reconsider stale proposals.
5. Restart the AI handler while a task is outstanding, restore state, and reconcile ambiguous game outcomes without blind retries.
6. Compare authoritative world events with each NPC's knowledge, plans and decisions.

## Acceptance signals

- The Game Master uses no model inference to decide equipment outcomes.
- No NPC acquires information it could not observe or receive.
- A model action cannot mutate pump state without a successful backend command.
- At least one plausible cooperative response emerges without hardcoded dialogue.
- No repeated physical action solely because a response was lost.
- Agent memories, commitments and provenance survive the handler restart.
- Inspectable traces include world event IDs, agent revisions, decisions and inference workload.

The mock world may advance time deterministically for tests; the actual Evennia integration must follow Evennia's authoritative game clock.
