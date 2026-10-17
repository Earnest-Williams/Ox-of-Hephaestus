# Cross-system contracts

**Status: planned contracts and invariants, not a published API schema.**

The independent AI handler and human interface will eventually exchange versioned information with Evennia and with each other. This directory will contain those schemas and examples. For now, the Python-only provisional `WorldPort` is in [services/ai-handler/src/ox_ai/ports/base.py](../services/ai-handler/src/ox_ai/ports/base.py).

## Source of truth

| Information | Owner | Rule |
| --- | --- | --- |
| Character location, equipment, cargo, skill, world conditions | Evennia | Must be queried or reported by the game |
| Official in-world orders and assigned duties | Evennia | Agents can misunderstand or disregard them, but not redefine them |
| Individual beliefs, episodic memories, plans and reasoning status | AI handler | Can be wrong about the world |
| Charts, dashboards, joined incident timelines | Interface | Derived views, no independent authority |

## Contract invariants

- An **observation** is information legitimately delivered to a specific character, not a raw omniscient game event. Keep its source ID, recipient and authoritative game timestamp.
- An **action request** is an intention to attempt something; it is not the corresponding world result. Attach request IDs and agent revisions for deduplication and stale-decision checks.
- **Outcomes** may be pending or unknown. Traditional MUD commands may not supply unambiguous acknowledgments; reconnecting must trigger reconciliation rather than automatic re-execution.
- An **agent memory** may cite an observation or conversation while preserving uncertainty. Do not equate a model's belief with a world fact.
- The handler's future API is distinct from the **game transport**. Inspection by ordinary users and operator intervention require different scopes.
- Game time comes from the active world backend: mock fixture or Evennia. Wall time is recorded separately for diagnostics.
- Event subscriptions must enforce visibility before delivery. A catch-up summary may include missed but legitimately recorded events; it may not reveal events that were never observable.

## Versioning approach

Before exposing a real network endpoint, define an explicit schema version, stable game-character-to-agent identity mapping, correlation IDs, authentication, authorisation and endpoint semantics. Do not infer the final API shape from the Python type hints alone.

See [architecture](../ARCHITECTURE.md) and [prototype plan](../design/prototypes/01-autonomous-crew.md).
