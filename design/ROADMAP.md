# Ox of Hephaestus — execution roadmap after P4e

**Baseline:** `main` commit `100f4ff6eb5acdcfccb73fba7e2651e80c0cdf9a` (18 October 2026). The baseline had 13 passing focused Ox workflows. **This roadmap is planning, not implementation evidence.** GitHub Issues were disabled when this plan was recorded, so this file is the canonical backlog until issue tracking is enabled.

## Invariants

1. Evennia is authoritative for physical world state, time, character identity, permissions, items, skill outcomes, assignments, and consequential action receipts.
2. The Ox handler owns per-agent beliefs, memories, proposed plans, agendas, inference metadata, checkpoints, and unfinished requests. Never read or write Evennia's DB from the handler.
3. All AI characters use their own authenticated sessions. Every action is validated in-world. A model proposal is not evidence of a world effect.
4. Unknown outcomes must be reconciled by the **same** persisted request ID. Never mint a fresh ID to compensate for a lost acknowledgment.
5. Idle agents require zero model calls. The world progresses through events, coarse game-owned ticks and lazy catch-up; do not optimize for high-fidelity always-running simulation.
6. Preserve the legacy three-crew integration as a regression, but do not run it alongside the five-crew controller on the same world.
7. Favor additive migrations with backward-compatible readers; never reset a live character, event history, inventory or checkpoint on bootstrap.

## Release procedure for every implementation PR

- Define authoritative owner, schema, invariants, and anticipated failure modes.
- Include tests for permitted and refused actions, cross-character scope, duplicate requests, stale state, and interrupted work.
- Exercise real Evennia DB transactions as well as an independent authenticated handler. Add PostgreSQL checks where concurrent DB writers or row locks matter; SQLite alone cannot certify these guarantees.
- Re-run the 13 existing focused Ox workflows plus new affected tests on the **final** PR commit. A test that passes with Concordia MockModel proves integration, not open-ended model competence.
- Update STATUS.md, ARCHITECTURE.md, guides, and the milestone evidence links in the same PR. No merge if documentation overstates implementation.
- Merge only after the new acceptance gate is met, the complete required CI is green, and the result has been checked on the merged main branch.

## Phase 0: safety and planning (first PR)

- Preserve baseline SHA and CI evidence; prepare **synthetic** database and handler-checkpoint fixtures for upgrade tests. Never commit live credentials or snapshot secrets.
- Review historical documentation for stale claims and label archived descriptions as historical.
- Establish ADRs for event persistence and recovery, split world-owned work orders from private agent agendas, and define migration/rollback policy.
- User must rotate the previously shared Gemini credential through the provider UI. Do not read or attempt to rotate private account secrets through the repository.
- GitHub Issues currently disabled: maintain this checklist here; optionally enable Issues later.

## G1: Reliable foundations

### PR 21 — world-owned event ledger and lossless addressed replay
**Dependency:** Phase 0. **Owner:** Evennia DB; handler tracks recipient cursors.

- Move private `ox_event` records off P-01 into indexed shipwide append-only storage. Use a monotonic global sequence, stable event ID, recipient/sender, kind, game time, correlation ID, schema version, and bounded validated payload.
- Use authenticated, paginated `oxinbox` cursor semantics; reply with `next_cursor`, `has_more`, and explicit schema version while retaining compatibility with legacy `oxinbox 0` tests.
- Cursor update and per-agent observation checkpoint must be crash-consistent. Replayed event IDs are harmless. Publish live notifications only after DB commit; replay is authoritative, socket delivery is advisory.
- Add deterministic legacy Attribute-to-ledger migration; make it idempotent, validated, and reversible until cutover. Event retention must not prune unread entries without an explicit archive/recovery mechanism.
- **Acceptance:** >2,000 events with >128 addressed to one actor, mixed recipients, cursor paging, disconnect/restart mid-page, no unauthorized leak, no lost/duplicate observations, transactional rollback produces no emitted event, migrated P4e histories preserve order and content.

### PR 22 — common action executor and exact-effect reconciliation
**Dependency:** PR 21. **Owner:** world for effects/receipts; handler for durable intended work.

- Define typed `ActionIntent`, `ActionReceipt`, `WorkExecution` schemas, indexed unique request IDs and actor/target/operation binding.
- Persist intent before network submission; atomically transact physical effects and receipt. On unknown, lookup by the **original** ID and do not resubmit as a new request.
- Generalize to P-01, C-01, A-01 and social obligations (release, radio, handover, answer), distinguishing exactly-once **effects** from at-least-once network delivery.
- Test contention for a single resource on PostgreSQL, plus SQLite compatibility.
- **Acceptance:** kill/restart before intent, before send, before commit, after commit/before ACK, after ACK/before checkpoint and between steps; each action is applied at most once, fully attributed, or explicitly unresolved with no unsafe replay.

## G2: Individual autonomy

### PR 23 — persistent agendas and reconsideration
**Dependency:** PR 22. Persistent private goals, ranked obligations, blockers, due times and accepted/deferred/declined/delegated/escalated/completed states; world-owned `WorkOrder` is distinct from handler-owned `AgentAgenda`. A deferral records its next trigger; no indefinite silent skip. **Acceptance:** priority interruption, later resumption and missing-supply reconsideration survive restarts.

### PR 24 — nonblocking cognition and exclusive supervision
**Dependency:** PR 23. Isolate synchronous Concordia/provider inference from socket dispatch; bound per-actor serialization, global concurrency, latency, timeouts, stale-choice cancellation, inference quotas, and safe provider failure. Add a fenced single-owner lease preventing concurrent three- and five-crew supervisors. **Acceptance:** a delayed model does not delay another crew's event handling; stale decisions cannot commit; second controller denied.

### PR 25 — capability discovery, GOAP generalization and travel
**Dependency:** PR 24. Authenticated world-advertised typed `ActionCapability`s, validated at execution; plan over learned room knowledge and local affordances; use ordinary world exits for movement. **Acceptance:** independent navigation from mess to engineering, reroute or safely block on inaccessible path, no teleport or unauthorized remote equipment action.

## G3: Cooperative shipboard operations

### PR 26 — inventory, ownership and atomic handoff
**Dependency:** PRs 22, 25. World-owned items, quantities, locations, carriers, reservations and real scarcity; idempotent move/transfer/consume receipts. **Acceptance:** two actors contest the final cartridge; no double consumption, duplication or loss across crash.

### PR 27 — interdepartment work orders and dependencies
**Dependency:** PR 26. Authenticated requests, assignment, acceptance, completion evidence, escalations and handoff. **Acceptance:** Teo requests a cartridge, Mara fetches and delivers it, Teo resumes maintenance, and a competing coolant emergency interrupts without deleting either responsibility.

### PR 28 — continuous skills and evidence
**Dependency:** PRs 22, 27. World-owned competency vectors, bounded practice/learning tied to verified consequential receipts, task difficulty, novelty and actual contribution; distinguish skill from role and authorization. **Acceptance:** proficiency changes through real work, not repeated IDs or meaningless repetitions; skilled actors still need permission.

### PR 29 — reusable duty assignments and relief
**Dependency:** PRs 23, 28. World-owned shift and on-call scheduling, independent review, delegated authority and unfinished-job handoff. **Acceptance:** several watch changes with concurrent work and strict self-review denial.

## G4: Consequential simulation

### PR 30 — causally linked world systems
**Dependency:** G3. Add modest power/thermal/life-support dependencies, equipment wear, recurring inspections and coarse or deferred catch-up. **Acceptance:** world-generated chain of linked failures, consistent outcomes under stepped vs lazy advancement, idle zero-inference operation.

### PR 31 — player-directed work and grounded dialogue
**Dependency:** PRs 23, 27, 30. Bounded natural-language interpretation into typed requests, confirmation/refusal, delegated tasks, deadlines and source-grounded answers. **Acceptance:** human requests supply delivery; unauthorized and privacy-invasive commands denied; no prompt can bypass world permissions.

## G5: Observability and operations

### PR 32 — authorized read-only operator diagnostics
**Dependency:** G2 (may be parallel with G3). Show world facts and independently sourced agent beliefs, event cursors, outstanding intents/receipts, task status, decisions and inference metrics; strict operator-only cognition access. **Acceptance:** trace any delayed/failed job from origin to disposition without reading another agent's private state as an ordinary player.

### PR 33 — adversarial, endurance and hosted-model evaluations
**Dependency:** G4. Deterministic randomized scenarios, long accelerated game-time soak, failure injection, latency/event loss and ledger growth checks. Opt-in hosted model benchmarks with budgets and recorded prompts; hosted CI is not required. **Acceptance:** no missing world effects, duplication, unauthorized transfer or unbounded agenda growth under defined stress windows.

### PR 34 — supported local runtime, migrations and release
**Dependency:** G5. One maintained runtime, supervised local process, identity/credential hardening, explicit upgrades/backups/rollback, production config separation, documentation reconciliation and dependency review. Keep network exposure private until independently hardened. **Acceptance:** fresh install, P4e upgrade, restart, restore, clean shutdown and complete regression suite.

## Deferred independently

**P5 browser observatory:** wait for PR 32 versioned permissioned read models; the UI must not become world authority. Ship expansion, economy, propulsion, fabrication and additional crew may resume after **G3**, using capabilities/work orders instead of bespoke new supervisors.

## Gate policy

- **G1:** >128-event offline catch-up and all-action crash reconciliation.
- **G2:** five crew maintain agendas, choose safe alternatives, travel, defer and reconsider despite delayed models.
- **G3:** cargo-to-environment delivery and work-order handoff through several watches with use-based competency evidence.
- **G4:** a world-owned system generates interdependent work without a developer driving each scenario.
- **G5:** results are observable, reproducible and robust through accelerated-world endurance and controlled restarts.

Unmet gates are blockers, not merely documentation TODOs.
