# Ox design, decisions and test evidence

This is **Ox-specific** project documentation. The repository's `docs/`
directory is the inherited Evennia manual, not the Ox implementation guide.

**CI workflow and path-filter policy:** [CI.md](CI.md). Documentation-only changes should never trigger gameplay integration suites.

**Current index:** [STATUS.md](STATUS.md), updated for G19 closure on 30 October 2026. The [current roadmap](ROADMAP.md) distinguishes engineering hardening and full-ship autonomous-crew integration from the accepted physical ship. [Archived planning and architecture](archive/README.md) retain the original dated evidence. P5 remains deferred.

## Decisions and authority

| Decision | Accepted subject |
| --- | --- |
| [ADR 0001](decisions/0001-concordia-first.md) | Concordia for initial private agent cognition |
| [ADR 0002](decisions/0002-game-master-world-authority.md) | Deterministic Evennia world authority |
| [ADR 0003](decisions/0003-three-services.md) | Separate game, handler and deferred interface |
| [ADR 0004](decisions/0004-ci-scope.md) | Focused Ox CI rather than mandatory upstream matrix |
| [ADR 0005](decisions/0005-typed-decisions-free-api.md) | Bounded model decisions; optional hosted-model experiments |
| [ADR 0006](decisions/0006-zero-inference-goap.md) | Model-free planning for familiar work |
| [ADR 0007](decisions/0007-three-crew-watch-supervision.md) | Historical mock watch supervision |
| [ADR 0008](decisions/0008-coordinated-coolant-incident.md) | Historical mock safety signoff |
| [ADR 0009](decisions/0009-durable-events-and-work.md) | World-issued events and durable action ledger |

## Important implementation trails

- [Original prototype](prototypes/01-autonomous-crew.md) ·
  [P3 authenticated sessions](prototypes/p3a-transport.md) ·
  [P4e five-crew runtime](prototypes/p4e-five-crew-autonomy.md)
- [G3 private epistemics](prototypes/g3-epistemics.md) ·
  [G3c real supply cooperation](prototypes/g3-cooperation.md) ·
  [G3e independent questions](prototypes/g3e-independent-questions.md) ·
  [five-scenario comparison](prototypes/g3e3-independent-questions-results.md)
- [G3f sixth captain](prototypes/g3f-captain-followthrough.md)
- [G4a traits](prototypes/g4a-character-foundation.md) ·
  [G4b identity/skills](prototypes/g4b-world-character-ledger.md) ·
  [G4c account boundary](prototypes/g4c-account-boundary.md)
- [G4d task shadows](prototypes/g4d-skill-shadow.md) ·
  [G4e knowledge/techniques](prototypes/g4e-independent-knowledge-techniques.md) ·
  [G4f practical learning](prototypes/g4f-world-receipt-learning.md)
- [G4g taught conceptual assessment](prototypes/g4g-verified-conceptual-learning.md) ·
  [G4h firsthand investigative method](prototypes/g4h-investigative-learning.md)
- [G5 adversarial/restart tests](prototypes/g5-adversarial-voyage.md) ·
  [P4f actor-indexed evidence follow-up](prototypes/p4f-indexed-evidence-v2.md)
- [G6 terminal loss](prototypes/g6-terminal-full-world.md) ·
  [G6b continuous crisis](prototypes/g6b-continuous-crisis.md)
- [G7 apartment GOAP](prototypes/g7-social-goap-apartment.md) ·
  [G7b bargaining](prototypes/g7b-reusable-social-negotiation.md) ·
  [world-persistent agreements](prototypes/g7c-world-social-authority.md)
- [G8 temporal memory](prototypes/g8-private-memory-seeding.md) ·
  [G9 native context](prototypes/g9-native-memory-context.md)
- [G10 memory clock](prototypes/g10-memory-clock-bridge.md) ·
  [G10b authenticated read](prototypes/g10b-world-clock-read.md)
- [G11 matched evidence](prototypes/g11-model-memory-ab.md) ·
  [G12 profiler](prototypes/g12-concordia-profile.md)

## Installed full-ship world

The [ship engineering index](ship/README.md) covers the 421-room installed Evennia topology, fitted v0.5 register (808 equipment units and 133 pressure cells) and G19 accepted full-ship physics. The separate seven-compartment fixture still hosts the autonomous Concordia/GOAP crew. Read the [G19 acceptance record](ship/G19_ACCEPTANCE_RECORD_2026-10-29.md) and [post-merge fuzzing](ship/G19_FUZZ_CAMPAIGN_2026-10-30.md) for exact evidence and remaining hardening.

Historical [architectures and roadmaps](archive/README.md) and [prototype reports](prototypes/README.md) are retained as dated reference material.

## Retained early scenarios

[P2 watch handover](../scenarios/shift_handover/README.md) and
[P2 cooling incident](../scenarios/coolant_fault/README.md) remain useful
deterministic regressions. Real server, multi-client and PostgreSQL tests
are covered by focused `.github/workflows/ox-*` actions.

See [setup](../INSTALL.md), [game commands](../game/README.md) and
[AI-handler operations](../services/ai-handler/README.md).
