# Ox implementation status

**Snapshot: 19 October 2026.** This document is the current-state index for
Ox-specific documentation. Earlier ADRs and P2/P3 scenario documents preserve
the design and acceptance criteria of those milestones; they are not live
feature inventories.

**Forward plan (remaining milestones):** [reliability-to-autonomy roadmap](ROADMAP.md) and [ADR 0009](decisions/0009-durable-events-and-work.md). Phase 0 planning merged in [PR #21](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/21). GitHub Issues were disabled when tracking was attempted.

## Verified implementation

| Stage | Status | Evidence and scope |
| --- | --- | --- |
| P0 — independent packages and contracts | Tested | Handler and interface import/test scaffolds, scoped Ox CI |
| P1 — native Concordia entity | Tested | `ox-concordia.yml`; individual observe/decide/snapshot/restore |
| P2 — three-person deterministic mock | Tested | `ox-watch-handover.yml` and `ox-coolant-incident.yml`; isolated memories, GOAP, mock world authority |
| P3a — real external Evennia sessions | Tested and merged | [PR #10](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/10); client login, puppet challenge, scoped commands |
| P3b — durable equipment actions | Tested and merged | [PR #11](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/11); actor-bound world receipts and lost-ACK recovery |
| P3c — three live crew characters | Tested and merged | [PR #12](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/12); radio, inspection, safety approval, handover on real Evennia |
| P4a — native Concordia across three live crew | Tested and merged | [PR #13](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/13); per-character Concordia entities, finite decisions, MockModel used in CI |
| P4b — ongoing watch supervisor and repeated incident | Tested and merged | [PR #14](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/14); Evennia duty Script, changed active engineer, two real pump incidents, two-process recovery |
| P4c — unattended event dispatch and player hails | Tested and merged | [PR #16](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/16); one continuous supervisor processes pump repair, world-timed watch handover and an addressed human hail |
| P4d — specialist ship departments | Tested and merged | [PR #17](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/17); seven compartments, cargo and atmosphere state machines, five persistent crew bodies, authority and inventory tests |
| P4e — five independently autonomous crew | Tested and merged | [PR #19](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/19); two additional nonprivileged Concordia actors, world-confirmed cargo/environmental work and a lost-ACK cartridge-replacement gate |
| P4f — indexed, paginated crew events | Tested and merged | [PR #22](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/22); world-owned indexed journal, schema-v2 recipient replay, safe legacy import, private handler checkpoints; all 14 applicable CI workflows passed before merge. |
| P4g stage 1 — global world work receipts | Tested and merged | [PR #23](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/23); typed `oxwork` / `oxworkreceipt` interface, global actor-bound receipt IDs and transactional effects; all 15 applicable workflows passed. |
| P4h — restartable pump stages | Tested and merged | [PR #24](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/24); exact work ID checkpointed for repair, request, independent approval, commissioning and resolution. Eight process launches across seven restarts and independent world-effect assertions passed; 14/14 workflows green. |
| P4i — restartable crew coordination | Tested and merged | [PR #26](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/26); bridge radio, posted handover and private hail answers checkpoint and reconcile original world work IDs. Three real-server restart cases and all 15 Ox workflows passed. |
| P4j — globally receipted specialist jobs | Tested and merged | [PR #27](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/27); cargo and environmental stages use global world-work receipts and preserve historical P4e pending-ID recovery. Three real-server restart/upgrade scenarios and all 18 focused workflows passed. |
| G1-PG — independent PostgreSQL concurrency gate | Tested and merged | [PR #28](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/28); real PostgreSQL 16, two distinct writer connections, identical-ID and last-cartridge races, row-lock blocking and transaction rollback; 17/17 workflows passed. |
| G2a — persistent crew agendas | Tested and merged | [PR #29](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/29); five character-bound private agenda records, specialist priority interruption and evidence-triggered reconsideration after a world-blocked replacement. Pure agenda invariants and both independent live-server scenarios passed; all 17 applicable workflows green. |
| G2 character foundations — reusable personalities | Tested and merged (PRs #31 and #32) | [PR #31](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/31) introduced versioned, composable per-person blueprints; [PR #32](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/32) adds optional live-role binding and **offline** identical-observation decision probes. MockModel is deliberately not personality-sensitive; no new world permissions or recruitment mechanics. |
| G2b — nonblocking cognition and supervisor exclusion | Tested and merged (25/25 jobs green across 18 workflows) | [PR #33](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/33): detached Concordia inference, per-agent serialization and revision checks, global bounded parallelism, timeout quarantine, hourly quotas, independent recipient hail work, and a single-host lease shared by both handler variants. No world-enforced multi-host fencing. |
| G2c — world-owned capabilities and GOAP navigation | Tested and merged (PR #35: 22/22 jobs; PR #36: 35/35 jobs, 23 workflows) | [PR #35](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/35) introduced local actor-scoped exit and equipment capability advertisements, 22 green CI jobs. [PR #36](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/36) adds private learned maps, GOAP exploration, fresh-observation exit traversal, blocked-path handling, and existing supervisor station recovery. No global map, teleport or remote equipment authority. |
| G3a — actor epistemic boundary (Rumsfeld / open-world) | Tested and merged (33/33 jobs across 21 workflows) | [PR #38](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/38) introduces per-person bounded evidence, provisional beliefs, explicit unknown questions, retrospective surprises, expiry and provenance; Teo ingests genuine local cartridge readouts and addressed events without mistaking hearsay for world truth. Inventory/handoff are subsequent stages. |
| G3b — world-owned inventory and supply orders | Tested and merged (38/38 jobs across 25 workflows) | Serialized item states, local-only stock observations, globally receipted request/accept/collect/deliver, real carrier/location transitions, A-01 consumption without duplicating legacy spares. [PR #39](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/39). |
| G3c — cooperative Teo/Mara supply | Tested and merged (37/37 jobs across 23 workflows) | Real addressed supply-request chain, independent local inventory observations, Mara's physical GOAP travel and carrying, lost delivery ACK reconciliation on restart, Teo's new verified physical replacement, actor-private open-world epistemics. [PR #40](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/40). |
| G3 epistemic semantics — actor-relative unknown unknowns | Tested and merged (42/42 jobs across 27 workflows) | The world/operator may classify an already-existing hidden fact as an unknown unknown **for a particular actor before discovery**. No such fact, hint or classification is sent to that actor; subsequent surprise is separate. Actor/private runtime schema remains unchanged. [PR #42](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/42). |
| G5-a — adversarial voyage / concurrency gates | **Verified: 27/27 focused workflows on code commit 93cdd019 (PR #45)** | Deterministically seeded three-system world incidents, direct-command fault/safety/handover rollback tests, real PostgreSQL simultaneous hails/clock ticks, 180-event privacy and rollback storm, 72 handler crash/restart stages. [Scope and limits](prototypes/g5-adversarial-voyage.md). No claim of long-running continuous autonomy. |
| G3d — self-directed preventive rounds | Tested and merged | [PR #46](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/46): bounded world-clock rounds and receipted C-01/A-01 preventive work; opt-in, not continuous model polling. |
| G3e — genuinely uncertain ship investigations | Tested and merged | [PRs #47–#51](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/51): actor-private, fallible sampling, challenge/reconsideration and independent unanswered-question investigations; no hidden-cause oracle. |
| G3f — six-person captain follow-through | Tested and merged | [PR #54](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/54): sixth separately authenticated captain owns open obligations, delegates and reviews without overriding specialist expertise or certifying speculative repairs. |
| G4a — versioned character traits and character-command reduction | Tested and merged | [PR #55](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/55): twelve aptitudes, twelve psychological dimensions, v1 blueprint compatibility; explicit Ox character command allowlist. |
| G4b — world-owned character identities and skills | Tested and merged | [PR #56](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/56): six stable persons, 55 skill IDs across sixteen disciplines; Django per-person skill ledger. |
| G4c — account command reduction | Tested and merged | [PR #57](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/57): Ox account command allowlist preserves login/puppeting while excluding stock character creation, global chat and builder shortcuts. |
| G4d — authoritative diagnostic skill and task shadows | Tested and merged (27/27 workflows) | [PR #58](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/58): captain inspection reads skill >= 40/100; old 0–4 competencies retired. Read-only routine/novel task comparisons have no physical effects. |
| G4e — separate conceptual knowledge and procedure familiarity | Tested and merged (28/28 workflows) | [PR #59](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/59): personal theoretical foundation and exact equipment/procedure ledgers; independently sourced, initially estimates, no hidden-fact disclosure. |
| G4f — verified practical experience | Tested and merged (29/29 workflows) | [PR #60](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/60): successful physical work receipts increment bounded practical skill and procedure familiarity, with replay and rate limits. No routine theory XP or graded real-world failure mechanics yet. |
| P5 — browser observatory | **Deferred / not built** | No browser UI, joined handler/world API, or operator dashboard |

**Naming note:** the original Prototype 1 plan used “P4” for the first
real-world pump mechanic, which was actually implemented early. PRs #13 and
#14 use **P4a/P4b** for the later live-cognition and autonomous-runtime work.
These names denote different scopes, not a missing pump milestone.

The [P4b Actions workflow](../.github/workflows/ox-p4b-autonomy.yml) retains
the detailed engineering restart and reviewer regression. It starts real
Evennia, resolves an initial cooling failure, waits for the game-owned watch
deadline, transfers watch from Ari to Iona, injects a second fault, stops and
restarts an external handler, reconciles a deliberately lost isolation ACK,
and verifies the persisted physical event journal without duplicate isolation.
The full focused CI suite passed on `main` following PR #14.

## G3d independent-initiative pilot (merged)

[G3d PR #46](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/46)
introduced **experimental, opt-in** world-clock independent rounds for the
original five technical crewmembers, bounded C-01/A-01 wear observations
and receipted preventive maintenance. It is verified on the focused live
five-client scenario, not general goal generation or indefinite freeform work.
[Implementation contract](prototypes/g3d-independent-rounds.md).

## P4e verified five-crew runtime

[PR #19](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/19)
was merged after **13/13 focused Ox workflows passed** on its final commit.
[The P4e design](prototypes/p4e-five-crew-autonomy.md) details five
independently persisted native Concordia agents, authenticated ordinary
Evennia clients, recipient-private alarms and actor-scoped world receipts
for C-01/A-01. [The new live CI](../.github/workflows/ox-p4e-five-crew.yml)
deliberately loses the acknowledgement of an actual cartridge replacement
before handler restart, then independently verifies that only one spare was
consumed while all three equipment incidents, two player hails and the
engineering watch handover complete. Existing P3–P4d scenarios remain green.

## P4f journal boundary

PR #22 introduces a dedicated `world.CrewEvent` Django table and migrations,
replacing the growing private event list on P-01 as the live event authority.
`oxinbox <cursor>` returns up to 128 recipient-specific records plus a
versioned `ox_inbox_done` continuation marker. The separate handler reads
every page, deduplicates observation IDs and checkpoints per-character
high-water cursors after saving its private Concordia state.

Existing P4e procedural consumers still need full addressed-history scans.
A bounded per-agent incremental work queue, retained-history compaction,
broader crash-safe physical/social actions and the autonomy scheduler remain
future work. P4f does **not** establish arbitrary mid-scene transaction
recovery or general LLM-driven planning.

## What the prototype does today

- **Evennia** owns the seven-room ship, three stateful physical systems
  (cooling P-01, cargo restraints C-01 and atmospheric scrubber A-01),
  the roster, role-local readouts, alarms, private recipient-specific events,
  authoritative timestamps and validated physical effects.
- **The standard five-person handler** connects as Lin, Ari, Iona, Mara and
  Teo with independent native Concordia state, observations and checkpoints.
  The **opt-in sixth captain** owns unresolved follow-up and can delegate
  without replacing the specialists. The earlier three-person handler
  remains supported separately; do not run competing supervisors together.
- **Deterministic GOAP** plans familiar equipment operations; Concordia
  chooses bounded, explicitly offered actions. Evennia alone executes
  permitted actions and supplies the confirmed physical outcome.
- **P4e's `five_crew_service serve`** is an external event-driven supervisor.
  It handles P-01 cooling, A-01 environmental, C-01 cargo, player hails
  and the world-timed engineering handover. Durable isolation/cartridge
  requests are reconciled by the original world request ID after an
  interrupted handler. Idle operation does not require model polling.
- After the handover, **Iona** is the active engineer and **Ari** is the
  separately authorised safety reviewer. Iona cannot certify her own
  commissioning. The first incident has the reverse arrangement.

## What passing tests do NOT prove

- Both three- and five-crew CI use **Concordia's deterministic MockModel**,
  not independently reasoning live hosted models. An earlier opt-in
  single-engineer Gemini trial succeeded, but unconstrained multi-agent
  negotiation, novel diagnosis and language-based coordination are not
  validated by these workflows.
- This remains a **small proving-ground**, with seven compartments and up
  to six independently authenticated crew. C-01 and A-01 are locally
  actionable state machines, not general freight commerce or high-fidelity
  life support. Some genuine work can now improve practical skill and exact
  procedure familiarity, but outcome difficulty still does not use the
  shadow competency formula. Propulsion, full ship economics, general
  training and the complete freighter remain future work.
- `serve` is a runnable runtime, **not a hosted deployment or a system
  service**. Disposable CI trials cover two consecutive incidents and
  seven sequential handler restarts across a separate pump cycle; no
  long-duration soak test or production operations guarantee exists.
- **P-01, C-01 and A-01 physical actions** have actor-bound durable
  receipts, with a common typed world work ledger available. P4h adds
  restartable repair, safety request, independent approval, commissioning
  and resolution stages in the cooling supervisor. Initial alarm radio,
  autonomous handover, player hails and specialist task stage bookkeeping
  are not all migrated to the general restartable protocol. Full
  mid-scene recovery remains an unmet G1 acceptance criterion.
- Development account provisioning uses **disposable three-, five- or
  six-actor fixtures** and test credentials. It is not a production
  account-management scheme. The prototype server binds to loopback and
  disables registration.
- P5 and its dual-source authenticated read APIs do **not** exist.

## Read next

- [Getting started](../INSTALL.md) and [ship game commands](../game/README.md)
- [AI-handler runtime and tests](../services/ai-handler/README.md)
- [Architecture and authority boundaries](../ARCHITECTURE.md)
- [Prototype 1 gates](prototypes/01-autonomous-crew.md)
- [P4a](prototypes/p4a-live-cognition.md), [P4b](prototypes/p4b-autonomous-watch.md)
  [P4d departments](prototypes/p4d-ship-departments.md) and
  [P4e five-crew autonomy](prototypes/p4e-five-crew-autonomy.md)
- [G4a character foundation](prototypes/g4a-character-foundation.md),
  [G4d shadow resolution](prototypes/g4d-skill-shadow.md),
  [G4e knowledge and techniques](prototypes/g4e-independent-knowledge-techniques.md)
  and [G4f verified experience](prototypes/g4f-world-receipt-learning.md)
- [Archived P2 test scenarios](../scenarios/shift_handover/README.md) and
  [cooling fault](../scenarios/coolant_fault/README.md)

The inherited `evennia/` package and `docs/` manual remain upstream Evennia
material, not a description of current Ox functionality.


## G3e-1 / G3e-2 actor-driven investigation

**G3e-1 merged (PR #47, 46/46 final-head checks):** the five existing
characters individually inspect a probabilistic anomaly with three hidden
possible causes; the world stores actual cause, observations and a provisional
bridge hypothesis separately. This feature is opt-in.

**G3e-2 merged (PR #48; 46/46 final-head checks):** specialists can challenge Lin's
provisional hypothesis, take a new non-oracular local diagnostic,
file an evidence-backed report, and change or retain their own interpretation.
Lin can then revise or retain the bridge explanation after receiving
independent engineering and specialist testimony. The old interpretation,
actual cause and separately addressed private observations are preserved.
[Detailed contract and verified gate](prototypes/g3e-contradictory-evidence.md).
This is not a general reasoner or physics simulator; deterministic MockModel
CI checks the integration, not open-ended diagnosis competence.

## G3e-3 — Independent investigation of unanswered questions

**Verified and merged in PR #51 (50/50 final-head checks), 19 October 2026.**
After a firsthand G3e-1 report, each existing specialist can independently
register a known-unknown question and conduct one local, fallible follow-up
experiment. They need not challenge Lin, and Lin need not have issued a
provisional theory. Measurements and their provenance can be reported while
leaving the cause unknown. The earlier challenge-based system remains available
behind an opt-in feature switch.

The hosted-model A/B comparison against the same five seeded cases showed
**0 baseline versus 15 final-head extra tests** across the four Gemini runs;
three of four final cases ended with a correct *available but unverified*
provisional theory. The fourth retained a wrong theory even after four tests.
A prior rerun collected 16 extra Gemini tests, illustrating variation in
actual choices despite identical world seeds. No expansion of ship, crew,
personality or skills was required. This is bounded, one-extra-test autonomy,
not general freeform inquiry. [Full operator-audited comparison](prototypes/g3e3-independent-questions-results.md).

## G4 boundaries after verified practical progression

Authoritative person profiles persist aptitudes (1–10), continuous psychology
(0–100), practical skills, independent theoretical foundations and equipment-
specific procedures (each 0–100). Six original people have neutral initial
aptitudes and explicit, **unverified** initial professional/knowledge/familiarity
estimates. Existing characters keep their values when duties change.

The live captain qualification uses a world-owned professional skill threshold,
but **ordinary repairs do not yet roll against the shadow Task Resolver**.
The resolver's weighting for routine versus novel work is provisional, private
to world/operator experiments, and not an LLM fact-discovery mechanism.

The G4f `CharacterLearningEvidence` ledger credits limited, successful P-01
repair, C-01 restow and A-01 cartridge replacement with replay-safe, capped
practical practice. It does **not** grant knowledge for routine repairs, award
experience for rejected commands, or resolve actual physical failures by
aptitude. Gameplay still needs a graded attempt/result model and verified
instruction or inquiry before those forms of learning can be activated.

Stock Evennia gameplay command sets are no longer inherited wholesale:
Ox uses explicit character and account allowlists. Authentication, command
routing, sessions, exits, locks, typeclasses, ORM and server infrastructure
remain Evennia's supported underpinnings. This is framework reduction, not
an unsupported fork-wide deletion of engine internals.
