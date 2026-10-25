# Ox implementation status

**Snapshot: 23 October 2026.** This document is the current-state index for
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
| G4g — verified conceptual instruction | Tested and merged in PR #62 (35/35 focused workflows) | [Design and verification](prototypes/g4g-verified-conceptual-learning.md): a qualified, separately identified instructor and consenting local learner complete a timed course and private transfer assessment. Passed work creates bounded conceptual progress under global receipts; no practical, permission or hidden-fact grants. |
| G4h — firsthand investigative learning | Tested and merged in [PR #63](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/63) (36/36 applicable workflows; 194 world and 150 handler tests) | [Design and verification](prototypes/g4h-investigative-learning.md): a saved pre-test forecast, real actor-local probe/report and assessed evidence-limits/source-independence reflection can generate bounded `investigation.methods` study progress. Hidden causes and diagnosis accuracy never determine credit. Autonomous study remains future work. |
| G6/G6b — terminal atmosphere crisis | Tested, merged, opt-in | [PR #66](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/66), [PR #67](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/67), [PR #68](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/68): a synthetic pilot followed by real Evennia six-client crisis trials with world-owned mortality, finite resources and decision ceilings. GOAP and hosted model experiments are separate, bounded evidence. |
| G7/G7b — social GOAP and bilateral authority | Tested and merged | [PR #69](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/69) and [PR #70](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/70): separate two-person apartment, reusable social GOAP and world-persistent typed agreements/obligations, receipts and post-restart fulfillment. World does not infer desire or consent from a model prediction. |
| G8 — private temporal memories and revision | Tested and merged | [PR #73](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/73): six authenticated clients, 500 model-free social/ship decisions across restarts, five repaired faults, typed personal episodes and independent interpretation revisions; fixed decision rotation and mostly templated speech. [PR #75](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/75) restores relevant 500-turn PR acceptance. |
| G9 — native memory relevance and lost-update guard | Tested and merged | [PR #74](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/74) and [PR #76](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/76): protected private-cognition revision/fork adoption, owner-only memory mutation, rehearsal/reconsideration and bounded read-only native Concordia context; no new world truth. |
| G10/G10b — explicit simulated-memory clock | Tested and merged | [PR #77](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/77) and [PR #81](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/81): explicit virtual-turn/game-second conversion, no future-memory leakage, and an authenticated `oxclock` read before ordinary native model decisions. No wall-clock substitute. |
| G11 — matched-evidence native choice A/B | Harness merged; manual hosted trial | [PR #80](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/80): baseline and read-only-memory augmented Concordia choices share identical evidence across four synthetic cases. Capture/mock mode is not model-quality evidence; hosted Gemini workflow requires explicit dispatch and credentials. |
| G12 — native Concordia 6/20/40 profiling | Tested and merged | [PR #78](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/78): local, deterministic native-component timing, memory/checkpoint and prompt-size measurements for *instantiated brains*. Not 20/40 authenticated ship crew or hosted inference latency. [PR #79](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/79) removed only an unused Concordia OpenAI provider extra. |
| G13 — matched-evidence native personality intervention | Verified experimental results; not live behaviour | [240-call six-actor native study](prototypes/g13-experimental-results.md) / [CI #39984790890](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39984790890): procedural vs original 4/72, independent vs original 7/72 selected-action differences. Substantial menu-position sensitivity; hypothetical actions only, zero world commands. |
| G14 — numeric/prose personality crossover | **Position-balanced protocol v2 twice verified; weak behavioural differentiation; not activated** | [G14 v2 CI #40016163471](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40016163471) and [exact-head rerun #40028008764](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40028008764): each 312 native calls, six shards, 24/24 repeat controls, zero world commands. Numeric trait 3/72 in both runs; prose trait changed actions 5/72 then 2/72, format-independent effect 6/72 then 3/72. Balanced options were still chosen from the first position 119/288 then 121/288. [V1 confound and both distinct v2 runs](prototypes/g14-experimental-results.md). |
| G15 — position-balanced choice adapter | Implemented and structurally tested; **not production-enabled** | [Experimental 3-forward native Decider scorer](prototypes/g15-position-balanced-decider.md) uses stable semantic action keys, cyclic A/B/C coverage and validated probabilities; offline invariance checks are not a G16 personality or live-world acceptance test. |
| G16a — one authored disposition catalog | **Merged and shared by opt-in G16c/d handler; no added world authority** | [G16a contract](../contracts/README.md) / [PR #114](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/114): strict five-dimensional authored metadata, 10 menus/32 signatures, all schema/source tests passed. G16c and G16d now consume this same catalog when explicitly opted in; the Evennia world still authorizes work and maintains its independent physical state. |
| G16b — native margin calibration | **Two verified native G14 runs measured; preregistered defaults proposed, not adopted** | [Frozen G16b score-scale calibration](prototypes/g16b-native-margin-calibration.md): 24 matched actor/case baselines in each of two native runs (48 non-independent vectors); pooled median top score 0.410, top-two margin 0.081; max top 0.529. Proposed gain 0.10, shift cap 0.21, base temperature 0.33, urgent 0.11. Evidence lock 0.85 was never reached in these cases; no production safety or personality conclusion. |
| G16c — durable opt-in Decider personality selection | **Merged, all 35 final-head workflows green; disabled in live supervisor** | [PR #117](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/117) squash commit `099e351`: G15 three native forwards, five-dimensional capped log-score shifts, bound BLAKE2b draw, catalog digest/actor-cognition provenance, pre-adoption checkpoint, exact request ID replay, genuine Concordia prompt menu-order invariance and fail-closed safety. Critically, safety score `0.85` is not a calibrated correctness measure. G16e native behavioural holdout now passes but does not establish high-confidence safety lock, actual 40-character queue capacity or live world authorization. [G16c design](prototypes/g16c-durable-personality-choice.md). |
| G16d — personality-weighted symbolic GOAP | **Merged and fully CI-verified; used only by opt-in policy** | [PR #116](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/116) squash commit `fbfaf494`: positive finite fractional GOAP costs from the identical five G16a action tags and actor dispositions, deterministic search, no mutation of shared operators, exact coverage and safety refusal. Differing plans from identical beliefs tested with synthetic characters. Actual world work remains separately authorized. [G16d design](prototypes/g16d-weighted-goap.md). |
| G16e — six-actor native personality holdout | **Native behavioural acceptance PASS (936/936 forwards); production safety and supervisor gates still outstanding** | [Five original actors #40047642031](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40047642031), recovered [Iona plus full six-actor evaluator #40094100849](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40094100849): original pinned G9 actor state and frozen G16b config, six complete verified GGUF Q4 results. Preregistered **13/42 (30.95%)** distinct personality-adjusted non-safety paired decisions versus **1/42** raw baseline; **96/96** caller order invariance, **24/24** identical choice and score-repeat controls, **4/4** non-ceiling new scenes. Independent full raw-record verification confirmed 288 factorial rows + 24 repeats. **36/36** safety-critical factorial rows refused; **zero actual high-confidence (≥0.85) safety locks**, so absence of locked overrides is vacuous and *does not establish live safety correctness*. All trials unexecuted: zero Evennia work commands. [Full verified results](prototypes/g16e-native-six-role-results-2026-10-24.md). Flag remains OFF. |
| G16f — model throughput at 6/20/40 actors | **Harness merged (32/32 CI); 198 true GGUF forwards measured; 40-actor concurrent queue not accepted** | [PR #119](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/119) squash commit `717e713`. [Native run #40048062817](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40048062817): 6/20/40 independent actors, all **66/66** sequential choices with **198/198** true Decider Q4 forwards; median native pass **6.85 s**, median 3-pass estimate **20.55 s**, 40-actor sequential **175.10 decisions/hour**; production timeout remains **25 s**. Burst/queue deadlines, not only serial capacity, remain a gate. [Full verified results](prototypes/g16f-native-throughput-results-2026-10-24.md). |
| G16i — real-native-informed 25-second queue admission envelope | **Hypothetical model verified in focused CI; subsequent genuine G16m measured zero successes** | [PR #123](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/123) reads [genuine G16f 198-forward CPU benchmark](prototypes/g16f-native-throughput-results-2026-10-24.md) and replays **fixed hypothetical** 6/20/40 arrival patterns against 25s queue-inclusive deadline. Under actual 40-actor P95 treated as constant (21.09 s), one **measured serial** scoring lane models **1/40** under its fixed 21.09s assumption, whereas the later actual G16m run observed **0/40**, versus **40/40** if 22 seconds apart. Two idealized workers are expressly *unverified*. G16i invokes **zero new native forwards** and **zero game operations**; do not mistake the planning envelope for live controller changes, a tested queue policy or confirmed actor demand. |
| G16j — actual inference queue observability | **Merged, 36/36 exact-head CI; no scheduler policy changes** | [PR #125](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/125), squash `51f3ab4`: scheduler now records bounded real async semaphore waits, executing-provider spans, queued-versus-active timeouts, abandoned completions and accepted proposals. A CI-discovered defect that counted an expired queued task as a late *provider* completion was corrected and verified. Metrics are CPU invocations and billed budget units—not actual native GGUF pass counts or authoritative ship receipts. [Design](prototypes/g16j-scheduler-queue-observability.md). The later [G16m actual native one-lane 6/20/40 burst](prototypes/g16m-native-forty-burst-results-2026-10-24.md) measured **0/66** successes under 25s; real fleet duty arrivals remain unmeasured. |
| G16m — real 25-second native 6/20/40 simultaneous queue | **Experiment completed, actual capacity FAIL; scheduler containment PASS** | [PR #129](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/129) merged after **32/32 exact-head CI**; [native Q4 run #40123141056](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40123141056) completed true Decider inference with unchanged model SHA, 2 native CPU threads and one worker. **0/6, 0/20, 0/40** on-time character decisions under the real **25s wall deadline**; only **9 actual System One forwards** (3 per cohort), three providers timed out active and **63 queued requests expired before inference**. Each full three-pass native invocation took ~**36.5–36.7 s**, substantially slower than G16f's 20.55s earlier runner median. All late workers drained without adopting a choice or issuing any world command. [Verified raw results and performance implications](prototypes/g16m-native-forty-burst-results-2026-10-24.md). **Do not activate local Decider routing at this deadline without host-specific capacity and queue policy tests.** |
| G16l — positive and uncertain safety-lock controller integration | **Merged, 32/32 CI; synthetic mechanics only, native safety remains unproven** | [PR #128](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/128) squash `704f52f`: real Concordia/G16c controller, checkpoint/replay and authored safety menus correctly lock controlled **0.96** synthetic confidence and refuse uncertain **0.34/0.33/0.33** with no GOAP fallback. This tests implementation and world-authority separation; original six-actor G16e native trial exercised **zero** high-confidence safety locks. No GGUF scoring, Evennia commands or safety calibration were added. |
| G16n — exact station-argument-bearing GOAP command signatures | **Merged at `4f21481`; no live actor activation** | [PR #130](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/130) adds immutable `(verb,target,sorted arguments)` to grounded GOAP operators and checks it in the personality-tag cost lookup, both routing branches and replay. Tests distinguish `round_report ship {station:cargo}` from `{station:pump}`; neither predicts or certifies completed ship work. Live binary report/defer choices still require separately validated two-position Decider scoring before the full P4k bridge. |
| G16o — two-position durable binary scoring | **56/56 code checks green; three-host native experiment complete; burst capacity FAILED** | [Binary scoring and registered host study](prototypes/g16o-balanced-binary-capacity.md): two real forwards per two-action offer, policy-v2 replay metadata, two-unit scheduler budget and synthetic real-Concordia recovery/timeout checks. Ternary policy-v1 records retain their meaning. [Local true Q4 run](prototypes/g16o-local-binary-results-2026-10-24.md): six sequential choices 26.736–27.565 s, 0/66 on-time burst proposals, 18 actual forwards, all late workers drained. [Three verified CI hosts](prototypes/g16o-three-host-native-results-2026-10-24.md): 13.804/23.638/39.797 s medians, 6/198 on-time burst proposals, 66 real forwards and all nine late workers drained. No world commands or production activation; binary behavioural quality and live forty-person acceptance remain outstanding. |
| G16p — measured asynchronous inference admission | **Native asynchronous 40/40 acceptance PASS; production off** | [Measured queue contract](prototypes/g16p-measured-capacity-admission.md): bounded identities and quota reservations before brain copying, separate queue/service deadlines, two/three-forward profiles, fresh-evidence dispatch and physical worker quarantine. [Verified native run](prototypes/g16p-native-admission-results-2026-10-24.md): 40/40 admitted decisions in 1,118.287 s, safe 41st-actor refusal and original-ID retry, 94 real forwards, zero queue expirations/overruns and 47.276 ms maximum observed heartbeat gap. Thirteen source hashes and 41 request IDs independently checked. Original G16o 25-second failure remains recorded; authenticated live work and other activation gates remain separate. |
| G16k — proposed adaptive one-pass Decider shortcut | **Post-hoc five-actor comparison rejects adoption** | [Exploratory score audit](prototypes/g16k-adaptive-shortcut-evidence.md) recomputed 70 canonical non-safety decisions from 780 authentic G16e native forwards. Initial score margin ≥0.15 would allow 20 early stops, **zero raw argmax disagreements but THREE differing final seeded, personality-adjusted choices** versus full G15 scoring; theoretical ~19% non-safety forward savings cannot justify behavioural changes. No new inference, native cost measurement or world receipts; retain all three Decider passes unless independently preregistered holdout validates an alternative. |
| G16g/h — independent dialogue and scorer decisions | **G16h genuine matched model comparison merged (32/32 final-head CI); scorer choice remains proposed, not adopted** | [PR #122](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/122) squash commit `9b8e5d3`: exact original 24 G11 counterfactual cases × two versions × both caller positions, 96 real decisions per model. **Decider 4B Q4_K_M: 94/96**, Qwen3.5-4B Q4_K_M: **87/96**; canonical/reversed both-correct Decider 23/24 each, Qwen 19/24 and 20/24; median binary-choice 17.79 versus 7.01 s (Decider two native passes; Qwen one chat). Independent final-head [native archive recheck](prototypes/g16h-verified-native-results-2026-10-24.md) pinned model SHA, original world evidence, 96 matched prompts and native score means. Real Qwen G16g 48/48 dialogue generations are [measured](prototypes/g16g-local-speech-results-2026-10-24.md), but initial [fidelity audit](prototypes/g16g-preliminary-voice-fidelity-audit-2026-10-24.md) warns of stock phrasing and invented details. [Draft #121](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/121) still needs two complete blind human reviews; no hosted Gemini trial or provider selection. **G16e six-actor behaviour has passed; native safety, G16m queue capacity, blinded voice and live Evennia soak remain independent gates; feature stays off.** |
| Transport — authentication, framing, buffering | Implemented, focused checks | [PR #71](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/71) and [PR #84](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/84): world-aligned command budget, interleaved private events/receipts, bounded unmatched packets and lossless overflow handling; malformed unattributable receipts cannot masquerade as the requested result. |
| PostgreSQL journal and captain locking | Tested and merged | [PR #82](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/82): commit-ordered global journal sequence and exact work-receipt source identity. [PR #83](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/83): P-01 → captain obligation → journal lock ordering and unique concurrent obligation creation; actual two-connection PostgreSQL regressions. |
| Handler inbox — incremental warm replay | Implemented in PR #85 | [PR #85](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/85): one full world-history hydration **per process**, then recipient-scoped `oxinbox <saved-cursor>` delta reads; independent five-crew private proof/agenda cursor recovery and strict page validation. The original implementation retained a complete Python history; see PR #86 for its indexed replacement. |
| Handler indexed historical evidence | Merged, extended by PRs #89–#93 | [PR #86](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/86): streamed actor-isolated SQLite evidence views. [PR #87](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/87): indexed unresolved hails and captain obligations. [PR #88](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/88): authenticated exact `oxevent` retrieval. Subsequent [PR #91](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/91) introduced authenticated cross-process cache reuse; full network rehydration is now needed only for a missing or unverified archive. |
| Handler lossless hot/cold evidence | Merged in PR #89 | [PR #89](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/89): typed indexes retain every event's identity and selectors. Bodies older than the recent 256 addressed events, except mandatory live pins, move to losslessly compressed SQLite cold storage. All previous knowledge remains available; disk grows with history. [Design](prototypes/p4f-hot-cold-evidence.md). |
| World journal continuity | Merged in PR #90 | [PR #90](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/90): immutable journal epoch, per-recipient cumulative SHA-256 prefix seals and authenticated `oxjournal` certificates, including migration/reset/legacy controls. [Design](prototypes/p4f-journal-continuity.md). |
| Handler attested archive reuse | Merged in PR #91 | [PR #91](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/91): recompute the complete local actor-specific hot/cold digest and open-obligation projection; require the matching world generation and original addressed prefix before resuming from the saved cursor. Crash-interrupted private checkpoints backfill without reproducing physical work. [Design](prototypes/p4f-attested-cache-reuse.md). |
| Historical evidence restart profile | Merged in PR #92 | [PR #92](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/92): reproducible local profile across 1k/10k/40k addressed events and two payload sizes, measuring entire restart attestation and a lossless offline SQLite repack. No historical cutoff or evidence-weakening inference. [Measurements](prototypes/p4f-evidence-restart-profile.md). |
| Periodic lossless SQLite repack | Merged and verified in PR #93 | [PR #93](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/93): transactionally reclaim SQLite B-tree allocation only after at least 2,048 demotions **and** demotions reaching 25% of the current cold archive; proportional cadence avoids repeatedly rewriting an ever-growing history. The archive seal, old events, private-source proofs, and unresolved obligations remain intact. 31/31 workflows passed. [Recovery contract](prototypes/p4f-lossless-repack.md). |
| Full ship physical-world model | **Spatial topology in PR #101; G17 operations and G18 physics subsequently installed** | v0.4 canonical 421-space / 517-link topology remains Evennia rooms and Developer-only exits. An explicit v0.5 operational register adds 808 equipment units, 1,256 isolators and 133 bounded gas cells without silently replacing the topology or seven-room proving ground. [Ship boundary](ship/EVENNIA_INTEGRATION.md). |
| G18 — continuous world physics | **Merged in [PR #135](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/135)**; 37/37 CI workflows green | Opt-in server-owned 10-second substeps, finite gas/species/fuel/water, electrical dispatch, cooling, smoke, fire, thermal damage, local equipment commands and common work receipts. Cross-process restart verified. Does not activate ordinary canonical-room traversal. [Scope](ship/G18_CONTINUOUS_PHYSICS.md). |
| G18b — coupled casualties and local recovery | **In [PR #136](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/136), acceptance pending** | Open HAB bridge pressure hatches exchange real gas/smoke; mechanically jammed-open ducts still pass gas; actual local valve closure can arrest a finite service-line leak. Authenticated HAB hatch and heat-protection reset commands receive world receipts. Multi-system seeded casualty and 80-tick fuzz regression added, **not yet certified green**. [Boundaries](ship/G18B_COUPLED_CASUALTY_RECOVERY.md). |
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

## G6–G12 acceptance and ongoing limits

The G8 500-decision acceptance trial used **six real authenticated Evennia
characters** and repaired **five separate ship faults**, with world receipts
and private memory/interpretation checkpoints across restarts. Its social
controller was **model-free, typed GOAP**, with a fixed rotating scheduler and
mostly templated utterances. It demonstrates causal bookkeeping and subjective
reinterpretation of supplied evidence; it does *not* prove the accuracy of
independent hosted-model interpretations or spontaneous social dialogue.

G11's matched-evidence harness is deliberately separate: both native
Concordia arms receive the same legitimate events, and only one receives an
extra read-only Ox memory projection. Its captured/mock mode verifies
plumbing, **not choice quality**. Hosted experiments are manual, small and
case-specific. G12's six/twenty/forty native-brain profile is a local
non-hosted benchmark, not a simulated ship population or throughput guarantee.

World invariants improved after G12: [PR #82](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/82) serializes PostgreSQL journal
sequence assignment through transaction commit and attributes receipts to
actual causal emissions; [PR #83](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/83) repairs the captain alarm/ticket/journal
lock inversion and retains exactly one active obligation under contention.
Neither gate eliminates the need for future adversarial transaction reviews.
PR #85 removed repeated full-history *network* scans. PR #86 also removes
the unbounded Python history list: historical proof is streamed to a
per-actor SQLite index and accessed through lazy snapshots or indexed
case/ticket/receipt queries. Validated local archives can now survive
process restarts and skip unnecessary old network-page transfers, after
the world generation and complete local-prefix continuity are checked.
Total historical storage intentionally grows with the voyage; local
cold-start integrity scanning and Concordia checkpoint rewrites remain
performance costs.

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

Existing P4e procedural consumers still need old addressed event identities.
PRs #85–#86 originally added delta inbox reads and actor-scoped SQLite
compatibility views. PRs #87–#89 added indexed outstanding obligations,
authenticated exact-event lookup, and losslessly compressed cold rows.
PR #90 provides world journal generations and actor-specific prefix
attestation; PR #91 now **persists and reuses verified archives between
handler processes**, retrieving only newer world events after their
unchanged historical prefix has been reauthenticated. Private cognition,
agenda, and epistemic checkpoints remain independently recoverable.
PR #92 profiled complete restart verification, and PR #93 introduced
proportional, lossless SQLite repacking. The complete authoritative journal
and every exact source event remain retained; storage grows with history.
PR #82 ensures sequence allocation follows PostgreSQL commit and PR #83
standardizes captain alarm lock ordering. Selective native cognition
checkpoint writes and broader crash-safe physical/social actions remain
future work. P4f does **not** establish arbitrary mid-scene transaction
recovery or general LLM-driven planning.

## What the prototype does today

G4g [PR #62](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/62) and G4h [PR #63](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/63) are now **merged and verified**, not merely proposed or under review. Together they supply one assessed supervised lesson and one firsthand investigative-method reflection. Neither is chosen autonomously by the ordinary handler.

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

- Legacy three-/five-crew regression flows primarily use **deterministic
  Concordia MockModel**, and G8's six-client 500-decision trial uses
  **model-free GOAP**. G6 has separate bounded hosted Gemini cases, and G11
  provides an optional matched-evidence hosted-model pilot. These do not
  validate unconstrained independent conversation, diagnoses or intention
  inference across a general ship population.
- This remains a **small proving-ground**, with seven compartments and up
  to six independently authenticated crew. C-01 and A-01 are locally
  actionable state machines, not general freight commerce or high-fidelity
  life support. Some genuine work can now improve practical skill and exact
  procedure familiarity, but outcome difficulty still does not use the
  shadow competency formula. Propulsion, full ship economics, general
  training and the complete freighter remain future work.
- `serve` is a runnable runtime, **not a hosted deployment or a system
  service**. Disposable CI trials cover two consecutive incidents and
  seven sequential handler restarts across a separate pump cycle. G8 also
  exercises 500 decisions across multiple real-server restarts, but no
  long-duration soak test or production operations guarantee exists.
- **P-01, C-01 and A-01 physical actions** have actor-bound durable
  receipts, with a common typed world work ledger available. P4h adds
  restartable repair, safety request, independent approval, commissioning
  and resolution stages in the cooling supervisor. Initial alarm radio,
  autonomous handover, player hails and specialist task stage bookkeeping
  now have specified supported restart/reconciliation stages (P4i/P4j).
  Arbitrary mid-scene actions and general social lives are **not** fully
  transactional; comprehensive recovery remains unimplemented.
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
- [G6 real-world terminal crisis](prototypes/g6-terminal-full-world.md),
  [G7 world social agreements](prototypes/g7c-world-social-authority.md),
  [G8 temporal memory](prototypes/g8-private-memory-seeding.md),
  [G9 Concordia context](prototypes/g9-native-memory-context.md),
  [G10 clock](prototypes/g10-memory-clock-bridge.md),
  [G11 matched A/B](prototypes/g11-model-memory-ab.md) and
  [G12 profile](prototypes/g12-concordia-profile.md)
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
not general freeform inquiry. [Protocol and operation flags](prototypes/g3e-independent-questions.md).
[Full operator-audited comparison](prototypes/g3e3-independent-questions-results.md).

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
aptitude. G4g and G4h add separate verified conceptual instruction and inquiry
activities. Gameplay still needs a graded physical attempt/result model.

Stock Evennia gameplay command sets are no longer inherited wholesale:
Ox uses explicit character and account allowlists. Authentication, command
routing, sessions, exits, locks, typeclasses, ORM and server infrastructure
remain Evennia's supported underpinnings. This is framework reduction, not
an unsupported fork-wide deletion of engine internals.
