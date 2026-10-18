# ADR 0003 — Keep three systems independently operable

**Status:** Accepted (2026-10-18); game and AI runtime integrated, third system deferred.

> **Current implementation note:** The first two independently runnable components now exist; P5's browser and dual read APIs were explicitly postponed. The list below is an ownership decision, not a claim that all three services are deployed.

## Decision

1. **Evennia**: world authority, character state, mechanical skills, ship machinery, game time, assigned duties and action outcomes.
2. **Ox AI Handler**: persistent individual Concordia entities, memories, beliefs, goal interpretation, inference workload, cognitive scheduling, and an independent inspection/operator API.
3. **Ox Human Interface**: ship control views, histories and privileged agent observability. It obtains world facts/actions from Evennia and cognition from the handler's API.

Both new components are separately packaged in `services/`. Neither is part of the `evennia` Python distribution. Interface technology remains undecided; the Python package can become a backend-for-frontend even if the final browser UI uses another stack.

## Boundaries

- The interface may combine API responses but may not access backend databases or turn inferred agent beliefs into world facts.
- Human in-world commands route through Evennia and its permissions. Operator commands such as pausing a cognitive worker route through the handler's separately authenticated API.
- A human interface is optional: closing every UI session cannot halt ship activity or NPC cognition.
- Agent/character mappings, game timestamps, observation/event IDs and action-request IDs must permit reliable correlation for timelines.
- The initial UI milestone is a **read-only** view of one real-world equipment state plus the corresponding NPC observations and decisions.
- Stock Evennia APIs are a starting point, **not a completed ship telemetry or permissions API**.

## Consequences

The codebase remains one repository for now, but separate environments/dependencies and test suites prevent accidental coupling. Transport implementations should be swappable without changing the entities themselves.


## Implementation outcome (2026-10-18)

`game/` contains the persistent Evennia ship, world event journal, physical receipts and game-owned duty Script. `services/ai-handler/` contains native Concordia crew, the ordinary WebSocket adapter and the separately runnable watch supervisor. [P4b](../prototypes/p4b-autonomous-watch.md) tests game/handler operation without any UI. `services/interface/` remains a package scaffold: no authenticated read endpoints, browser observatory or operator controls exist. See [current status](../STATUS.md).
