# Ox design documents

This directory contains **Ox-specific architectural decisions and prototype specifications**. The repository's `docs/` directory remains Evennia's inherited engine manual.

## Accepted decisions

- [ADR 0001: Use Concordia as the initial cognitive foundation](decisions/0001-concordia-first.md)
- [ADR 0002: Deterministic GM, world authority and clock ownership](decisions/0002-game-master-world-authority.md)
- [ADR 0003: Three independently operable systems](decisions/0003-three-services.md)
- [ADR 0004: Focus CI on Ox; upstream matrix manual only](decisions/0004-ci-scope.md)

## Prototype plan

- [Prototype 1: Autonomous Crew](prototypes/01-autonomous-crew.md)
- [Scenario 0: Watch handover](../scenarios/shift_handover/README.md)
- [Scenario 1: Cooling pump incident](../scenarios/coolant_fault/README.md)
- [Cross-system contract principles](../contracts/README.md)

Decision records specify the intended design; they do not imply that the components have been implemented or verified.
