# Ox human interface — intentionally deferred

**Status (21 October 2026, through G12): package scaffold only.**
P5—the read-only ship/crew observatory—remains postponed after the
later G6–G12 experiments, memory/clock integration and journal hardening.
There is **no running browser app, frontend, HTTP API server or
production operator-control endpoint**. Do not confuse GitHub test
artifacts or private JSONL journals with a user-facing interface.

## Intended data sources

The eventual interface is the third independently operated component:

1. An **Evennia-facing read model** will expose legitimately authorized
   equipment conditions, rooms, posted watches, sensors and in-world
   events. All game actions still pass Evennia permissions.
2. An **AI-handler-owned API** will expose authorized per-character
   observations, memories, beliefs, decisions, pending actions, outcome
   reconciliation and inference diagnostics, without sharing private
   cognition by default.

The interface may use a lightweight backend-for-frontend to join those
responses and present charts, ship overviews and crew drill-downs. It
must not read the game or handler databases directly, independently
simulate ship conditions, grant itself omniscience or mutate either
component's state. The game and handler operate without the browser.

For a minimal future acceptance test, show **P-01's actual Evennia
state alongside each relevant engineer's possibly stale belief**,
a timeline of proposed vs attempted vs world-confirmed actions, and
permission checks denying ordinary users another character's private
cognitive records.

## Existing package vs future work

- `src/ox_interface/clients/` and `src/ox_interface/views/` are scaffolds
  for typed clients and presentation/read models.
- No browser stack (NiceGUI, JavaScript or otherwise) is selected.
- No stable handler inspection schema, telemetry API, operator-control
  protocol or live event stream is published.
- Current inspectable development evidence is GitHub Actions artifacts,
  game-world logs and handler-local checkpoint/trace files, not a UI.

See [implementation status](../../design/STATUS.md),
[system architecture](../../ARCHITECTURE.md) and
[service boundary ADR](../../design/decisions/0003-three-services.md).
