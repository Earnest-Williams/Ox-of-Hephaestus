# ADR 0009 — World events, work obligations, and crash safety

**Status:** Proposed (18 October 2026). This records the design direction only; code remains P4e until a passing implementation PR merges.

## Decision

Evennia will own a shipwide append-only, recipient-scoped event journal with pagination and stable IDs, authoritative work orders, equipment and social-action outcomes, and all material resources. The handler will own each character's private observation cursor, agent agenda, cognitive checkpoint, plans and pending action intents. Do not store globally addressed event history forever on P-01.

An event observed over the live WebSocket is only a notification: durable replay confirms what an offline recipient was legitimately entitled to see. Cursor advancement must be checkpointed with observation consumption. Events emitted by a rolled-back world transition are forbidden.

For consequential operations, the handler checkpoints a request ID **before** transmission; Evennia validates and atomically commits any world effect and an actor-bound receipt. If the result is uncertain, reconciliation uses the original ID; physical and social world effects must be idempotent. A world refusal remains a refusal for that ID. Network packets can be duplicated; effects must not be.

World-owned `WorkOrder` records represent externally assigned obligations. The private `AgentAgenda` may include goals, ideas, plans, deferred decisions and blocked states. Agent reports are never evidence of physical success or permission grants.

## Alternatives not selected

- A second independent database treated as authoritative for ship physics.
- LLM narration as evidence of repaired equipment or transferred inventory.
- Treating delivery acknowledgments as transactional proof.
- Continuous per-tick model calls for idle agents.
- A full dedicated AI service endpoint before ordinary-client transport requires replacement.

## Compatibility and rollout

Preserve three-crew/old command regressions. Stage additive migrations with an idempotent import of old P-01 private events and explicit verification. Maintain a reversible pre-cutover snapshot. Introduce indexed Django tables for event and receipt history if transaction/isolation tests prove appropriate. Run PostgreSQL contention tests before promising concurrent writer safety.

## Validation

See `design/ROADMAP.md` G1 acceptance. A successful deterministic CI run is not proof of unscripted hosted-model intelligence.
