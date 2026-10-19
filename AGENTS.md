# AGENTS.md — repository guidance

This is an **Evennia fork plus an implemented Ox prototype**, not a new
`evennia` distribution. Read [Ox status](design/STATUS.md),
[architecture](ARCHITECTURE.md) and [setup](INSTALL.md) before changes.

## Ox boundaries

- **World authority:** only Evennia changes rooms, pumps, assigned duties,
  safety approvals and physical outcomes. Models propose actions.
- **Cognition:** Concordia is the chosen foundation; GOAP handles routine
  engineering. Five technical crew plus an opt-in sixth captain have separate identities and private memory; the historical three-crew runtime remains a regression fixture.
- **Transport:** ordinary authenticated Evennia WebSocket sessions,
  world-issued receipt IDs, recipient-scoped events; never fabricate an ACK.
- **Capabilities:** the world owns stable character identity, twelve aptitudes, twelve psychology dimensions, 55 skills, separate theory and equipment-technique ledgers. G4f–G4h grant narrow receipt-backed practice and assessed learning; the task shadow is **not** the live outcome system. No model-written narrative awards XP.
- **Recovery:** reconcile unknown physical actions by request ID, never
  blindly retry. Generic mid-scene crash recovery is still incomplete.
- **Runtime:** `ox_ai.runtime.five_crew_service serve` controls the five-specialist fixture (optional `OX_CAPTAIN_OVERSIGHT=1`); the legacy `watch_service serve` must never run concurrently against the same ship. Neither is
  a managed deployment. Only deterministic CI cognition is proven.
- **UI:** deferred; no public handler API or observatory. Do not claim one.
- **Isolation:** keep Ox changes in `game/`, `services/`, `contracts/`,
  `design/`, `scenarios/` unless a justified upstream engine change is required.
- **CI:** prefer focused `ox-*` workflows; the upstream nine-job engine
  matrix is manual. Never publish upstream Evennia images from this fork.

## Pointers


- [Ox component/test map](design/README.md)
- [Active ship and local commands](game/README.md)
- [AI runtime and experiments](services/ai-handler/README.md)
- [Evennia core beliefs](.agents/docs/core-beliefs.md)
- [Engine architecture](.agents/docs/architecture.md)
- [Engine testing](.agents/docs/testing.md)
- [Engine code style](.agents/docs/code-style.md)
- [Engine development commands](.agents/docs/commands.md)
- [Upstream CI reference](.agents/docs/ci.md)
- [GitHub tooling reference](.agents/docs/github.md)

After editing agent-context files, run `make cleanrot`. Follow the
repository's tests and docstring conventions for code changes.
