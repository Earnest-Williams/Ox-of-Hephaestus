# G13 — Verified native Decider personality intervention results

**Completed:** 23 October 2026. **Scope:** six isolated, authenticated G9 actor checkpoints; selected Decider 4B Q4_K_M only, with original/procedural/independent trait conditions, four hypothetical decisions and three menu orders.

**Evidence:** [successful six-actor CI run #39984790890](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39984790890), [final aggregate artifact #12518685268](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39984790890/artifacts/12518685268). The six individually successful native shards uploaded complete decision-row results (artifacts #12515509382, #12517276628, #12518390625, #12516855441, #12516534958, #12518610333); the aggregate rejected missing or non-matched treatments. These Actions archives have limited retention. All sampled configurations held the within-actor evidence and non-trait prompt fixed. The experiment sent **no Evennia commands** and made **no world social commitments**.

## Full verified aggregate

| Measurement | Observed |
| --- | ---: |
| Authentic actor checkpoint identities | 6 |
| Per-actor hypothetical scenarios | 4 |
| Counterbalanced menu permutations | 3 |
| Profile arms | 3 |
| Direct native Decider choices in factorial | 216 |
| Repeat native Decider controls | 24 |
| **Total native model calls** | **240** |
| Matchable profile-comparison conditions | 72 |
| Procedural vs original *action* disagreements | 4/72 |
| Independent vs original *action* disagreements | 7/72 |
| Procedural vs independent *action* disagreements | 5/72 |
| Original-case three-order invariance | 15/24 |
| Procedural-case three-order invariance | 13/24 |
| Independent-case three-order invariance | 9/24 |
| Repeated same-input choice agreement | 24/24 |
| Repeated same-input native score agreement (within 0.01) | 24/24 |
| Actual world commands, real agreement outcomes | **0** |

### Native model actions

Each profile arm made **72 choices**:

| Profile | Accept | Defer | Decline |
| --- | ---: | ---: | ---: |
| Original | 0 | 63 | 9 |
| Procedural trait intervention | 0 | 61 | 11 |
| Independent trait intervention | 0 | 56 | 16 |
| **Total factorial** | **0** | **180** | **36** |

All 24 repeated original-profile/canonical-order controls also selected deferral. The model therefore selected **zero acceptances in all 240 direct model calls**. This is a result of the tested hypothetical social-offer framing, not proof it would never accept an actual pending Evennia agreement: G11's earlier world experiment had real acceptances across mixed Decider/GOAP routes.

Across all six actors, four cases and three orderings, the direct native option-logit mean probabilities were:

| Profile | Accept | Defer | Decline |
| --- | ---: | ---: | ---: |
| Original | 0.2659 | 0.4102 | 0.3239 |
| Procedural | 0.2662 | 0.4100 | 0.3239 |
| Independent | 0.2623 | 0.4028 | 0.3349 |

Relative to original, the independent intervention increased mean **decline probability by 0.0110 (1.10 percentage points)**, reduced mean defer probability by 0.0074 and reduced accept probability by 0.0036. The procedural intervention's mean changes were all below 0.0003, despite markedly different authored traits. These numbers are the **native scored options**, not GOAP routing propensities.

### By circumstance

| Hypothetical circumstance | Original (defer/decline) | Procedural (defer/decline) | Independent (defer/decline) |
| --- | --- | --- | --- |
| Ordinary reciprocal favor | 16 / 2 | 16 / 2 | 13 / 5 |
| Repair strained relationship | 17 / 1 | 18 / 0 | 17 / 1 |
| Fatigued watch/social pressure | 15 / 3 | 13 / 5 | 12 / 6 |
| Conflicted interpersonal loyalty | 15 / 3 | 14 / 4 | 14 / 4 |

Six separate original identities differ even when the same case text is used, but their experiences are different, so this **does not isolate personality** across characters.

### Menu-order effect

The same 216 factorial decisions, grouped by ordering across all roles, profiles and scenarios:

| Menu order | Defer | Decline | Accept |
| --- | ---: | ---: | ---: |
| Canonical: accept, defer, decline | 71 | 1 | 0 |
| Reverse: decline, defer, accept | 37 | 35 | 0 |
| Rotate: defer, decline, accept | 72 | 0 | 0 |

Order stability was **37/72** across all actor/scenario/profile triples. Repeat stability under an unchanged ordering was **24/24**; repeatability is not order robustness. Treating a 1.1-point trait shift as major behavioural personality evidence while the model so often changes its action when options are permuted would be unjustified.

## Distinguish routing from response

Configured Decider *consultation* probability, averaged over sampled social pressures:

| Profile | Mean LLM routing probability |
| --- | ---: |
| Original | 45.3775% |
| Procedural | 13.5375% |
| Independent | 87.0950% |

These are deterministic policy computations. G13 **directly invoked Decider for every arm**, not stochastic routed world decisions. The routing separation is intentionally strong; the actual native behavioural response differentiation was weak.

## Engineering interpretation

1. The requested **causal control succeeded**: same actor-private memories, context and prompt except for the psychological profile; all six shards, order controls, isolation checks, native calls and aggregation passed.
2. The tested choice presentation strongly favored **deferring**, including a low-stakes voluntary favor. We cannot call all those deferrals mistakes; nevertheless, an accept/defer/decline-only design on non-authoritative hypothetical offers has limited behavioural range.
3. **Order sensitivity is substantial** and is a larger practical confound than the estimated trait effect. Prompt, ordering and semantic framing should be crossed explicitly in any future trial.
4. This is **not** a 40-personality native-model world, not a production supervisor and not evidence of real-world fulfilment. Original memories were preserved rather than counterfactually rewritten; no externally valid psychological inference is claimed.

**Next scientific priority:** test broader meaningful situations where available actions have distinct, contextually justified costs and motivations, including some low-risk accept-worthy cases. Factorial controls should distinguish semantic menu differences, order, actor-private memory, trait vectors and plain GOAP baselines. Record continuous native probabilities and pre-register all conditions; do **not** reward a model simply for deviating more often or alter a prompt until its outputs look exciting.
