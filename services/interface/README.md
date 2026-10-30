# Ox human interface — intentionally deferred

**Status (30 October 2026, after G19): package scaffold only.**
P5—the joined world/crew observatory—remains postponed. The accepted
G19 ship has a **separate Developer-only, read-only spatial
terminal** ([ship documentation](../../design/ship/LIVE_TERMINAL.md)),
but no deployed browser app joining world state with private AI cognition,
no combined HTTP API and no production operator-control endpoint. Do not
confuse GitHub artifacts or private JSONL journals with that future UI.

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

For a minimal future acceptance test, display **an installed G19 machine's
actual Evennia state alongside an authorized engineer's possibly stale belief**.
Include a timeline of proposed, attempted and world-confirmed actions,
and deny ordinary users access to another character's private cognition.
Retain the historical P-01 comparison as a regression scenario.

## Existing package vs future work

- `src/ox_interface/clients/` and `src/ox_interface/views/` are scaffolds
  for typed clients and presentation/read models.
- No browser stack (NiceGUI, JavaScript or otherwise) is selected.
- No stable handler inspection schema, telemetry API, operator-control
  protocol or live event stream is published.
- Current development inspection includes the restricted G19 spatial
  terminal, GitHub Actions artifacts, game logs and handler-local checkpoint
  traces; none is a joined world-and-cognition UI.

See [implementation status](../../design/STATUS.md),
[system architecture](../../ARCHITECTURE.md) and
[service boundary ADR](../../design/decisions/0003-three-services.md).
