# Ox Human Interface

**Status: importable Python package scaffold and design notes only. No browser app or API server exists yet.**

The interface is the third, independently operated system alongside Evennia and the AI handler. It provides a shipboard operations console and—under separate permissions—an agent/simulation observatory.

## Dual data sources

- **Evennia-facing interface:** ship state, rooms, equipment, duties and permitted in-world actions. Evennia is authoritative.
- **AI handler-facing API:** agent identity mapping, cognition status, beliefs, decisions, event histories and privileged execution controls. The handler is authoritative for its own agent state.

The frontend may use a Python backend-for-frontend to join these sources and protect secrets. Neither backend depends on the browser. It must not access either backend's database directly or invent world state.

An initial read-only view will correlate one pump's true condition (Evennia) with each relevant engineer's observed events and beliefs (handler). A player-view and an operator-view must not expose the same private details by default. Prefer explicit role/permission checks at the server boundary.

## Proposed source layout

- `src/ox_interface/clients/` — eventual typed clients for the two APIs.
- `src/ox_interface/views/` — presentation/read-model composition, not game mutation.
- Additional visual frontend code will be added after the UI framework is selected; the existing Python package does **not** commit us to NiceGUI over a separate JavaScript client.

The package currently has no runtime entry point or web dependencies. Do not document it as a functioning dashboard.

See [the system architecture](../../ARCHITECTURE.md) and [service-boundary decision](../../design/decisions/0003-three-services.md).
