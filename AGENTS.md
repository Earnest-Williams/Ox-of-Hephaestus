# AGENTS.md — repository guidance

This is an **Evennia fork plus an implemented Ox prototype**, not a new
`evennia` distribution. Read [Ox status](design/STATUS.md),
[architecture](ARCHITECTURE.md) and [setup](INSTALL.md) before changes.

## Ox boundaries

- **World authority:** only Evennia changes rooms, pumps, assigned duties,
  safety approvals and physical outcomes. Models propose actions.
- **Cognition:** Concordia supplies native choices; symbolic GOAP covers
  bounded engineering and experimental social plans. Five technical crew
  and an opt-in captain maintain separate memories and observations.
  G8 adds actor-private temporal episodes and reinterpretation; G9
  protects private mutation/revisions and exposes bounded read-only context
  to Concordia. G10/G10b use explicit simulated-time ownership and
  authenticated clock reads. The three-crew mode remains a regression.
- **Transport:** ordinary authenticated Evennia WebSocket sessions, exact
  world-issued receipt IDs and recipient-scoped events. Preserve unrelated
  packets in bounded wire order; overflow must not consume the next frame.
  Malformed unattributable receipts do not establish a different request's
  outcome. Never fabricate an ACK or substitute a new request ID.
- **Capabilities:** the world owns stable character identity, twelve aptitudes, twelve psychology dimensions, 55 skills, separate theory and equipment-technique ledgers. G4f–G4h grant narrow receipt-backed practice and assessed learning; the task shadow is **not** the live outcome system. No model-written narrative awards XP.
- **Recovery:** reconcile unknown physical actions by request ID, never
  blindly retry. Generic mid-scene crash recovery is still incomplete.
- **Runtime:** `ox_ai.runtime.five_crew_service serve` controls the
  five-specialist fixture (optional `OX_CAPTAIN_OVERSIGHT=1`); never run
  legacy `watch_service serve` concurrently against the same ship.
  Neither is a managed deployment. G6/G8 have distinct bounded live-server
  experiments; G11's manual hosted-model A/B and G12's 6/20/40
  native-brain profile are not general model-quality or scaling proof.
- **World chronology:** PostgreSQL event-journal sequence allocation must
  remain serialized through commit (PR #82). Preserve the P-01 → captain
  ticket → journal lock order (PR #83) and exact operation-event receipt
  provenance, not a global before/after-sequence guess.
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
