# Ox design, decisions and test evidence

This is **Ox-specific** project documentation. The repository's `docs/`
directory is the inherited Evennia manual, not the Ox implementation guide.

**Authoritative current-state index:** [STATUS.md](STATUS.md), updated
through merged **G4h (PR #63, 19 October 2026)**. The
[ROADMAP](ROADMAP.md) separates completed gates from pending implementation.
Earlier ADRs, P2 scenarios and milestone plans retain their original
historical framing; an old “not yet implemented” in one of those documents
is not a description of today's `main`. P5 is postponed.

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
- [G5 adversarial/restart tests](prototypes/g5-adversarial-voyage.md)

## Retained early scenarios

[P2 watch handover](../scenarios/shift_handover/README.md) and
[P2 cooling incident](../scenarios/coolant_fault/README.md) remain useful
deterministic regressions. Real server, multi-client and PostgreSQL tests
are covered by focused `.github/workflows/ox-*` actions.

See [setup](../INSTALL.md), [game commands](../game/README.md) and
[AI-handler operations](../services/ai-handler/README.md).
