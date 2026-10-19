# Ox design, decisions and test evidence

This directory holds **Ox-specific** architecture, accepted decisions,
historical proof-of-concept phases and runnable evidence. The repository's
`docs/` folder remains the inherited Evennia engine manual.

For the next implementation sequence see [the execution roadmap](ROADMAP.md) and [ADR 0009](decisions/0009-durable-events-and-work.md). GitHub Issues were disabled at roadmap creation, so roadmap entries are the tracked backlog.

**Current truth:** [P0–P4 status and documented limitations](STATUS.md).
Do not read a P2/P3 historical description of “future P3 integration” as
the present implementation; those milestones are now merged. P5 is
deliberately postponed.

## Accepted architectural decisions

| Record | Original decision |
| --- | --- |
| [ADR 0001](decisions/0001-concordia-first.md) | Concordia as the initial cognitive foundation |
| [ADR 0002](decisions/0002-game-master-world-authority.md) | Deterministic GM, Evennia as sole live authority |
| [ADR 0003](decisions/0003-three-services.md) | Independent game, AI handler and future UI |
| [ADR 0004](decisions/0004-ci-scope.md) | Targeted Ox tests, upstream matrix manual |
| [ADR 0005](decisions/0005-typed-decisions-free-api.md) | Bounded hosted decisions (Gemini trial) |
| [ADR 0006](decisions/0006-zero-inference-goap.md) | Model-free GOAP for known engineering tasks |
| [ADR 0007](decisions/0007-three-crew-watch-supervision.md) | Three-crew mock handover, scoped memory |
| [ADR 0008](decisions/0008-coordinated-coolant-incident.md) | Mock coolant incident and safety signoff |

These ADRs preserve their **original decision context**. Later milestone
outcomes are cross-linked instead of retroactively erasing the history.

## Prototype and implementation notes

- [Prototype 1: goals and acceptance gates](prototypes/01-autonomous-crew.md)
- [P3a: ordinary authenticated transport](prototypes/p3a-transport.md)
- [P3b: durable physical receipts and GOAP](prototypes/p3b-durable.md)
- [P3c: three real client characters](prototypes/p3c-live-crew.md)
- [P4a: three native Concordia actors](prototypes/p4a-live-cognition.md)
- [P4b: persistent supervisor, world-owned watch deadline](prototypes/p4b-autonomous-watch.md)
- [G3e-3: independent unanswered-question protocol](prototypes/g3e-independent-questions.md)
- [G4g: supervised conceptual learning and transfer assessment](prototypes/g4g-verified-conceptual-learning.md)
- [G4h: firsthand investigative learning and evidence limits](prototypes/g4h-investigative-learning.md)

## Retained deterministic regression fixtures

- [P2 Scenario 0: watch handover](../scenarios/shift_handover/README.md)
- [P2 Scenario 1: cooling-fault coordination](../scenarios/coolant_fault/README.md)

The P2 mock suites remain useful for rapid permission, model-free
routing and checkpoint regressions. **Live** P3/P4 behavior is tested
separately by focused Evennia-server GitHub workflows.

For setup and operations, use [INSTALL.md](../INSTALL.md) and
[AI handler README](../services/ai-handler/README.md).
