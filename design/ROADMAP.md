# Ox of Hephaestus — execution roadmap after P4e

**Historical planning baseline:** `main` commit `100f4ff6eb5acdcfccb73fba7e2651e80c0cdf9a` (18 October 2026), with 13 focused workflows at that time. **This roadmap separates planned work from verified implementation evidence.** For live milestones and test links see [STATUS](STATUS.md), updated through G4f on 19 October 2026. GitHub Issues were disabled when this plan was recorded.

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

### Implementation correspondence (18 October 2026)

The roadmap's early provisional PR numbering differed from actual GitHub
allocations. **Merged PR #22** implements the addressed-event ledger and
lossless replay; **merged PR #23** implements the common world work receipt
namespace and authenticated client adapter. **P4h** adds durable handler
intents for five pump-cycle stages and a multi-process restart test.
G1's subsequent focused milestones implemented the then-current
radio, watch, hail and specialist operations (PRs #26–27), while PR #28
verified the existing shared protocol under real PostgreSQL contention.
These scoped gates are complete. New or unimplemented gameplay actions
still require their own authorization, crash recovery and concurrency
evidence; do not treat G1 as a blanket certification of future systems.

**P4i (merged PR #26):** This G1 implementation
migrated bridge alarm relay, scheduled engineering offer/accept and
addressed hail answers to persistent handler intent records with
actor-bound world receipt reconciliation. The old ordinary character
commands remain supported. The subsequent G1 milestones covered specialist stages and
real PostgreSQL resource contention.

**P4j (merged PR #27):** Both specialist departments' newly
scheduled physical steps now use the global world-work namespace
and handler-side stage ledger. Old P4e pending IDs retain the
fixture-specific recovery path; after safe reconciliation the
remaining steps migrate. Three isolated server tests exercise
pre-send, post-commit and old-checkpoint recovery. PostgreSQL multi-writer contention was separately verified
in merged PR #28 for the existing action protocol.

**G1-PG (merged PR #28):** A dedicated PostgreSQL CI job
races independent world writers and verifies the actual row lock,
global request ID uniqueness, one-unit resource consumption and
rollback of world-owned event/receipt records. This does not
constitute a production-grade Postgres deployment recipe, nor a
general property proof for every future inventory system.

## G2: Individual autonomy

### G2a implemented (merged PR #29)

Introduce a generic private `AgentAgenda` for each of the five existing
characters, persist dispositions and future-event reconsideration
triggers, retain old saved jobs, and dispatch specialist obligations
by meaningful local priority. Two game-server acceptance cases must
demonstrate world-triggered reprioritization/interruption and an
A-01 supply refusal followed by a later resupply observation and safe
new attempt. The world owns both failed and successful work receipts.
This slice deliberately precedes deadline escalation, cross-department
delegation, freeform goal selection, threaded/provider-isolated cognition
and general autonomous movement.

### PR 23 — persistent agendas and reconsideration
**Dependency:** PR 22. Persistent private goals, ranked obligations, blockers, due times and accepted/deferred/declined/delegated/escalated/completed states; world-owned `WorkOrder` is distinct from handler-owned `AgentAgenda`. A deferral records its next trigger; no indefinite silent skip. **Acceptance:** priority interruption, later resumption and missing-supply reconsideration survive restarts.

### G2b — nonblocking cognition and local exclusive supervision (merged PR #33)

The original provisional PR 24 is now [actual PR #33](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/33). Detached native Concordia snapshots provide nonblocking, role-scoped inference, bounded global concurrency, model timeouts and quarantine, stale decision rejection, limited hourly inference budgets and safe failure. Hails on independently authenticated crew clients may be scheduled in parallel; the existing real physical duty order is preserved. Both supervisor variants share one POSIX lock file. **Acceptance:** a delayed model does not block another agent's inference or observation; an out-of-date result is never adopted; a competing local supervisor is refused. **Limit:** the local flock epoch is not a world-enforced or distributed fence—multi-host operation needs a later authoritative fencing protocol. [Design and tests](prototypes/g2-nonblocking-cognition.md).

### G2c — world-owned capability discovery and learned GOAP travel (PRs #35, #36)

The old provisional PR 25 is implemented in two real PRs: [#35](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/35) (merged; 22/22 CI jobs), and [#36](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/36) (merged; full authenticated navigation and live-crew acceptance, all 35 jobs passed). World command `oxcapabilities` advertises only currently traversable **local** exits and currently eligible local fixture actions, with an actor-bound challenge. The handler learns a private map of visited rooms and builds bounded GOAP travel steps exclusively from those observations; it navigates by stock exit commands and verifies arrival from a fresh world response. Locked hatches are excluded and a discovered alternative may be used; physical work still requires separate game-owned authorisation and receipts. Acceptance requires a live authenticated Mess -> Passage -> Engineering walk, denied-hatch safe block, alternate Machine Shop route, and displaced Teo returning to A-01 before work. [Design](prototypes/g2-navigation.md).

## G3: Cooperative shipboard operations

### G3a / G3b — character epistemics and authoritative inventory (merged PRs #38–39)

[PR #38](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/38) establishes per-character open-world observations, beliefs, explicit unanswered questions and retrospective surprises. [PR #39](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/39) implements physical serialized cartridges, real carriers, actor-local stock evidence, and a bounded supply order with globally typed idempotent request/accept/collect/deliver commands. Two orders cannot consume the same last item. These are narrower than the provisional generalized inventory/order PR 26–27 language. [Epistemics](prototypes/g3-epistemics.md) · [Inventory](prototypes/g3-inventory.md).

### G3 epistemic clarification — systemic but actor-hidden unknown unknowns (merged PR #42)

An authoritative world fact can be an **unknown unknown to a particular
character right now**, without a future revelation or surprise. In a mostly
closed simulation, a privileged operator may compare the world-owned fact
with that actor's actual observations, specific questions, beliefs and
exposure records. This must not enumerate hidden facts in agent memory,
prompts, action options or character-facing events. A question such as
"what is behind that moon?" does not itself reveal the specific pirate
waiting there. [Detailed contract](prototypes/g3-epistemics.md).

### G3c — real world-receipted Teo/Mara delivery (merged PR #40)

[PR #40](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/40) connects those world contracts to the five-crew supervisor: Teo's world-verified shortage triggers a real request, Mara receives an independently addressed assignment, physically inspects/collects and navigates an actual item, then Teo verifies real delivery and resumes repair. A lost delivery acknowledgment is reconciled with the SAME persisted ID across handler and Evennia restart. **Acceptance passed:** 37/37 jobs across 23 workflows, including final-source world conservation and epistemic provenance checks. This is an opt-in bounded single-order vertical slice, **not** general multi-order coordination. [Design](prototypes/g3-cooperation.md).

Generalised work orders, deadline escalation, cross-department prioritisation under simultaneously urgent incidents, reservation expiry and use-based skills remain later G3 increments.

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


## G3e — real uncertainty ahead of ship/skills/personality expansion

G3e-1 merged in PR #47 after 46/46 checks: five individually authenticated
existing crewmembers receive only ambiguous world-sourced observations of a
world-secret atmospheric analyzer fault. Lin's preliminary theory may be
wrong and never becomes world truth. The case is opt-in; not a freeform
diagnostic model.

G3e-2 merged in PR #48 after 46/46 final-head checks: specialists can raise competing hypotheses,
run fallible, repeat-safe role-local experiments, independently reconsider
their positions, and send evidence/provenance to Lin. A revised or retained
bridge interpretation is explicitly unconfirmed and requires reports from
more than one department. World-only hidden causes and probe randomness
must never become an actor-visible affordance or model context.
[Design and gates](prototypes/g3e-contradictory-evidence.md).
The uncertainty-to-reassessment path is now verified. New compartments,
skills and personalities remain deferred until a deliberate next-stage plan.

## G3e-3 complete — Known unknowns can drive work without disagreement

G3e-3 is merged in PR #51 (50/50 final-head checks). A specialist's
independently identified unanswered analyzer question can cause one
world-authorized local experiment after that actor's original firsthand
report, without needing a dissenting alternative to Lin's theory. Lin can
make a provisional assessment from cross-department second measurements,
including after previously deferring; no model receives the world-owned
latent cause. Old G3e-2 challenge-only behavior remains as an explicit
control. [Implementation and three-run comparison](prototypes/g3e3-independent-questions-results.md).

Next acceptance study, before adding more roles or rooms: vary bounded
choice-menu ordering and experimental evidence, repeat hosted-model trials,
and distinguish genuine evidence-seeking from menu-position biases. Probe
selection is not yet open-ended, and one follow-up per character does not
support indefinite pursuit of unanswered questions. Diagnose rather than
paper over the retained wrong theory in the all-elevated case.

## G4 — Character competence and practical progression (19 October 2026)

**Merged and verified:** G3f (#54) introduced the sixth, accountable captain.
G4a–G4c (#55–#57) established version-two aptitudes/psychology, durable
per-person 55-skill records and explicit restricted Evennia character/account
command sets. G4d (#58) moved the captain's technical qualification to a
world-owned 0–100 skill threshold and retired role-based 0–4 competency
attributes, then introduced a read-only task comparison. G4e (#59)
independently persisted theoretical foundations and exact equipment/procedure
familiarity. G4f (#60) made real successful physical work generate
replay-resistant, bounded practical skill and technique practice. All
G4d–G4f final-head workflow matrices passed before merge (27/27, 28/28,
and 29/29 respectively).

**Next acceptance gates, in causal order:**

1. **Verified conceptual learning.** A separately validated, locally performed
   investigation or documented supervised lesson can generate bounded
   theoretical-foundation evidence. Mere declarations, ordinary repairs,
   hearsay or repetition of a rejected command cannot. Record instructional
   identity, activity, provenance and specific before/after improvement.
2. **Typed, graded task attempts.** Distinguish invalid/refused commands from
   real attempts that fail, partially succeed, succeed imperfectly or succeed
   fully. Use individual practical skill, conceptual knowledge, relevant
   aptitudes, procedure familiarity and current acquired conditions. Keep
   authority, physical access and interlocks independent from proficiency.
3. **One reversible physical pilot.** Feature-gate quality resolution on a
   well-instrumented fixture, preferably P-01 bearing/service work. Preserve
   the current real-world state machine and receipt semantics as the control.
   Commit tool wear, parts, elapsed time, terminal readings, physical outcome
   and character learning within one world transaction. Test failed repairs,
   retries, interruption and delayed defects before using it more broadly.
4. **Acquired attribute ledger.** Model fatigue, injury, acclimatisation,
   practice-dependent habits and environmental penalties as provenance-rich
   world effects; do not rewrite a person's foundational aptitude each time
   they are tired. Avoid automatically assigning stereotyped psychological
   consequences.
5. **Cognition and staffing consequences.** Permit autonomous scheduling to
   weigh fallible personal estimates of ability, actual witnessed outcomes,
   pay/availability, working conditions and incomplete crews. Characters
   must not receive latent world causes or other people's private skill data.
6. **Continue Evennia contraction.** Replace only those remaining generic
   stock mechanisms that conflict with authoritative Ox semantics, such as
   inventory shortcuts, role-to-skill aliasing or user-modifiable world facts.
   Keep supported engine authentication, sessions, typeclasses, locks, exits,
   database transactions and event infrastructure. Every replacement needs
   migration and actor-local integration tests.

The shadow resolver is **not** a live success/failure roll. Current
experience credit is only from already-authorised and already-successful
physical work; it does not make general world repairs skill-sensitive yet.
Neither character recruitment, full ship economics, theoretical training,
nor an acquired-attribute engine is complete.
