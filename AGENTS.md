# AGENTS.md — repository guidance

This is an Evennia fork implementing the Ox ship simulation and a separate
bounded autonomous-crew prototype, not an Evennia distribution. Read [status](design/STATUS.md), [architecture](ARCHITECTURE.md)
and [setup](INSTALL.md) before changing code.

## Ox boundaries

- **World:** Evennia owns physics, time, identities, permissions and receipts.
- **Cognition:** native Concordia plus bounded GOAP; separate actor minds.
- **Memory:** G8–G9 private temporal/reinterpreted records, owner mutations and revision-protected read-only native context.
- **Clock:** G10/G10b use authenticated game time, not handler wall time.
- **Transport:** authenticated per-actor sockets; bounded, lossless unmatched-frame buffering; never treat a malformed/unverified receipt as success.
- **Capabilities:** world owns aptitudes, psychology, 55 skills, theory and procedure ledgers; G4 learning is receipt-gated, not model-awarded.
- **Recovery:** reconcile uncertain work under its original request ID.
- **Ship:** G19 421-room installed physical world and 808 units are accepted; autonomous Concordia/GOAP still uses the seven-compartment proving ground. [Acceptance](design/ship/G19_ACCEPTANCE_RECORD_2026-10-29.md).
- **Runtime:** five specialist agents, optional sixth captain; never run the legacy three-crew supervisor on the same world concurrently.
- **PostgreSQL:** preserve commit-ordered journal sequences, exact receipt event provenance and P-01 → captain ticket → journal lock order (PRs #82–83).
- **Evidence:** G6/G8 bounded world trials; G11 manual model A/B; G12 local 6/20/40 brain profile is not live-crew scaling.
- **UI:** no public API or live observatory.
- **Scope/CI:** isolate Ox code in game/services/contracts/design/scenarios; use focused Ox checks, not the inherited engine matrix.

## Pointers

- [Ox component/test map](design/README.md)
- [Active ship and commands](game/README.md)
- [AI runtime](services/ai-handler/README.md)
- [Evennia core beliefs](.agents/docs/core-beliefs.md)
- [Engine architecture](.agents/docs/architecture.md)
- [Engine testing](.agents/docs/testing.md)
- [Engine code style](.agents/docs/code-style.md)
- [Engine commands](.agents/docs/commands.md)
- [Upstream CI](.agents/docs/ci.md)
- [GitHub tooling](.agents/docs/github.md)

After editing agent-context files, run `make cleanrot`.
