# AGENTS.md — repository guidance

This is an **Evennia fork plus an implemented Ox prototype**, not a new
`evennia` distribution. Read [Ox status](design/STATUS.md),
[architecture](ARCHITECTURE.md) and [setup](INSTALL.md) before changes.

## Ox boundaries

- **World authority:** only Evennia changes rooms, pumps, assigned duties,
  safety approvals and physical outcomes. Models propose actions.
- **Cognition:** Concordia is the chosen foundation; GOAP handles routine
  engineering. Three live crew have separate identities and private memory.
- **Transport:** ordinary authenticated Evennia WebSocket sessions,
  world-issued receipt IDs, recipient-scoped events; never fabricate an ACK.
- **Recovery:** reconcile unknown physical actions by request ID, never
  blindly retry. Generic mid-scene crash recovery is still incomplete.
- **Runtime:** `ox_ai.runtime.watch_service serve` is implemented, but is
  not a managed deployment. Only deterministic CI cognition is proven.
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
