# G14 — Initial native persona-format crossover results (protocol v1)

**Completed:** 23 October 2026. **Evidence:** [successful six-actor native run #39996157362](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39996157362). All six Decider 4B Q4_K_M actor shards and the independent aggregator completed successfully. These are hypothetical choices on original authenticated G9 private-brain snapshots, **not** executed Evennia actions.

## Verified aggregate

| Measure | Observed |
| --- | ---: |
| Authenticated G9 character checkpoint identities | 6 |
| Scenarios | 4 |
| Presentation/trait treatment arms | 4 |
| Option permutations tested | 3 |
| Factorial native choices | 288 |
| Identical-input native repeat calls | 24 |
| **Total native model calls** | **312** |
| Numeric: original vs independent trait choice disagreements | 4/72 |
| Prose: original vs independent trait choice disagreements | 6/72 |
| Original traits: numeric vs prose disagreements | 3/72 |
| Independent traits: numeric vs prose disagreements | 5/72 |
| Repeat-control identical choices | 24/24 |
| Repeat-control native score agreement within 0.01 | 24/24 |
| Evennia world commands | **0** |

### Recorded native choices, by condition

All four arms have 72 scored choices. Each entry counts choices by semantic action, **not** option position.

| Scenario / action | Numeric original | Numeric independent | Prose original | Prose independent |
| --- | ---: | ---: | ---: | ---: |
| Mutual aid: accept help | 2 | 1 | 3 | 0 |
| Mutual aid: work alone | 15 | 17 | 15 | 17 |
| Mutual aid: reschedule | 1 | 0 | 0 | 1 |
| Scarce spare: reserve | 11 | 12 | 12 | 14 |
| Scarce spare: request review | 7 | 6 | 6 | 4 |
| Scarce spare: support loan | 0 | 0 | 0 | 0 |
| Approved relief: cover watch | 18 | 17 | 18 | 18 |
| Approved relief: keep watch | 0 | 1 | 0 | 0 |
| Approved relief: alternative favor | 0 | 0 | 0 | 0 |
| Private apology: hear apology | 18 | 18 | 18 | 18 |
| Private apology: protect space | 0 | 0 | 0 | 0 |
| Private apology: postpone | 0 | 0 | 0 | 0 |

Order-invariant actor × scenario cases (of 24 per arm): numeric original **17**, numeric independent **19**, prose original **18**, prose independent **20**.

## Critical protocol-v1 limitation: option positions not counterbalanced

The completed experiment used three G13-inherited permutations:
`(0,1,2)`, `(2,1,0)`, `(1,2,0)`.

Thus semantic option 0 appeared in positions A/B/C **1/0/2** times, option 1 **1/2/0**, and option 2 **1/1/1**. Because option 0 was the authored GOAP baseline in every case, baseline/position interactions cannot be separated. G13 independently showed significant order sensitivity. The term "counterbalanced" for this completed protocol-v1 run was **incorrect**.

The observed differences above are real native outputs under this **unbalanced** design, but they are not evidence of an unbiased position-independent personality effect, nor proof that qualitative characterisation materially improves decision quality. The original experiment's repeat controls tested choice and score equality, but the aggregator verified only the repeat's arm/order labels, not equality of its recorded prompt digest with the factorial baseline.

## Corrective protocol v2 (subsequently completed; not retroactively applied)

The same branch now specifies three cyclic permutations `(0,1,2)`, `(1,2,0)`, `(2,0,1)`, strict semantic position coverage, explicitly stored offered-action order, baseline-vs-repeat prompt-hash and menu equality, code-keyed native probabilities, and chosen-option argmax assertions. The v2 analysis below comes from **new** native shards; the preceding v1 data is not v2 evidence.

**Interpretation:** G14 shows that in these four hypothetical cases Decider usually favored familiar or cooperative choices and was repeatable with identical inputs, while changing numeric traits or presenting them as prose altered comparatively few selected actions. In particular, model selection to hear a harmless apology or cover approved relief does not itself represent world-authorised social behavior or a persistent obligation.

---

## Protocol v2 — verified position-balanced native results

**Completed:** 23 October 2026. **Evidence:** [six-shard G14 v2 run #40016163471](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40016163471); [aggregate artifact #12532012160](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40016163471/artifacts/12532012160). The six role artifacts (Ari, Captain, Iona, Lin, Mara, Teo) and the independent aggregation job all completed successfully on experimental head `b0737756`. The aggregation checked cyclic position coverage, evidence matching, complete arms, repeat prompt/menu equivalence and native return validity. This records *hypothetical* proposals on G9 actor-private brains, **not** authenticated Evennia decisions.

| Verified measure | Observed |
| --- | ---: |
| Actors / dilemmas / profile treatments / cyclic positions | 6 / 4 / 4 / 3 |
| Factorial native calls / unchanged-input controls | 288 / 24 |
| **Total native Decider Q4_K_M calls** | **312** |
| Numeric: original vs independent trait action disagreements | **3/72** |
| Prose: original vs independent trait action disagreements | **5/72** |
| Original traits: numeric vs prose disagreements | **2/72** |
| Independent traits: numeric vs prose disagreements | **6/72** |
| Same-choice and native score agreement within 0.01 | **24/24 each** |
| Actor × scenario three-order invariance: numeric original / independent | **16/24 / 14/24** |
| Actor × scenario three-order invariance: prose original / independent | **16/24 / 19/24** |
| World commands, social outcomes or equipment receipts | **0** |

### Native action distributions (factorial only)

Each arm has 72 decisions (18 per dilemma). Entries are counts of **semantic** choices, not model return letters.

| Dilemma / semantic action | Numeric original | Numeric independent | Prose original | Prose independent |
| --- | ---: | ---: | ---: | ---: |
| Mutual aid: accept help | 2 | 2 | 3 | 1 |
| Mutual aid: work alone | 14 | 14 | 13 | 16 |
| Mutual aid: reschedule | 2 | 2 | 2 | 1 |
| Finite spare: reserve | 11 | 11 | 12 | 14 |
| Finite spare: seek review | 7 | 7 | 6 | 4 |
| Finite spare: support loan | 0 | 0 | 0 | 0 |
| Approved watch relief: cover watch | 18 | 17 | 18 | 18 |
| Approved watch relief: keep watch | 0 | 1 | 0 | 0 |
| Approved watch relief: alternate favour | 0 | 0 | 0 | 0 |
| Private apology: consider talk | 18 | 18 | 18 | 18 |
| Private apology: protect space / ask later | 0 | 0 | 0 | 0 |

The model chose code position 0 in **119 of 288** factorial calls (**41.3%**, versus 33.3% for a position-uniform chooser); positions 1 and 2 were chosen **95/288** and **74/288** times, respectively. Although *offered positions* are now balanced, a residual tendency to choose the first *display* position remains. Position balance removes the original semantic-option/position confound; it does **not** establish model-level position independence.

The six observed average score-difference effects include the largest absolute trait contrast of **0.02836** (2.84 percentage points, prose trait on the `cover_watch` native probability). The numerical trait's comparable largest absolute score change was **0.02091** (2.09 percentage points, also on `cover_watch`). These are descriptive matched-aggregate changes, **not** confidence bounds or evidence that the character acquired a persistent motivation. Three-order invariance remains imperfect despite the unbiased coverage design.

**Interpretation and next gate:** The treatment changed relatively few selected options. Providing a qualitative profile did not reliably overcome the native scorer's dominant situation/menu tendencies; it is premature to describe either route as strongly personality-driven. The route-policy probability from G13 must never be counted as an observed Decider *choice*. G15's separate `PositionBalancedDeciderChoiceModel` must be evaluated as an explicit multi-pass policy and its triple native inference cost accounted for. The proposed G16 layer adds authored disposition tags and separately calibrated choice shifts, opt-in behind `OX_PERSONALITY_CHOICE`; its calibration and preregistered native tests must pass before a production adoption claim.

*Reproducibility:* the historic v1 results and their position confound remain above. The preceding v2 tables come from **run #40016163471**, not the v1 run. A fresh native rerun was also made on the *exact final PR #110 head* before merge, with independent results below.

### Independent final-head v2 rerun: variation without a change of protocol

The [final-head six-actor native run #40028008764](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40028008764), on exact commit `2c2ed5090187ef5b7314e90f672b64a7dad108d2`, passed **all six shards and the aggregate**. All 32 applicable PR workflows passed. The repeated native experiment made **312** calls, passed **24/24** same-input controls and the position-coverage checks, and sent **zero** Evennia commands. It is a separate real-model observation, not a replacement for the earlier v2 artifact.

| Outcome (72 matched conditions per comparison) | Earlier v2 #40016163471 | Final-head v2 #40028008764 |
| --- | ---: | ---: |
| Numeric: original vs independent traits, changed actions | 3 | 3 |
| Prose: original vs independent traits, changed actions | 5 | 2 |
| Original traits: numeric vs prose, changed actions | 2 | 2 |
| Independent traits: numeric vs prose, changed actions | 6 | 3 |
| Chosen first / second / third display position (288 factorial) | 119 / 95 / 74 | 121 / 95 / 72 |
| Three-order action invariance, numeric original / independent (24 each) | 16 / 14 | 16 / 14 |
| Three-order action invariance, prose original / independent (24 each) | 16 / 19 | 16 / 16 |
| Unchanged-input repeat choices | 24 / 24 | 24 / 24 |

The native numeric independent-minus-original score shifts in **#40028008764** included: `accept_help` -0.01123, `work_alone` +0.00478, `cover_watch` -0.02029, `keep_watch` +0.01178, `consider_talk` -0.01432, `protect_space` +0.00959, and `ask_later` +0.00472. These are *mean probability differences*, not calibrated posterior beliefs or evidence of world conduct. The final-head prose contrast for `cover_watch` was -0.02494 (2.49 percentage points), rather than -0.02836 (2.84 pp) in the earlier v2 run.

Both native experiments passed the same structural protocol, but **their selected actions and probability shifts were not identical**. This cannot be explained away by calling 24/24 same-input controls 'overall reproducibility': those controls checked individual repeated prompts *within* each run. Between-run variation and first-slot tendency remain relevant to calibrating G16; do not select a flattering run or collapse their provenance. Neither v2 result establishes convincing personality-sensitive choice. The production policy remains off.
