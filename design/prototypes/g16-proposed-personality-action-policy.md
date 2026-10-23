# G16 — proposed character-disposition action policy

**Status: proposed, not adopted.** This is an experimental design and preregistration outline. No production supervisor flag is enabled; no world authority, skill or memory rule is changed. Adoption requires the G16 acceptance tests, balanced native model comparison and an opt-in live soak.

## Model decision (proposed)

- **Decider 4B Q4_K_M** is proposed as the local finite-action *scorer* only. It is not a dialogue engine and cannot authorize Evennia actions.
- Run `PositionBalancedDeciderChoiceModel` (G15) for precisely three typed options using stable semantic keys; all three option-code positions must be scored, validated and averaged. Do not rely on raw one-pass action-letter logits.
- Personality affects both habitual planning and deliberate selection **explicitly and deterministically**, rather than trusting the model to infer a stable behavioural policy from prose/numeric trait magnitude alone.
- Use a separate generative dialogue model, selected through an independent quality-and-cost evaluation; pass its character's prose style profile. Generated dialogue cannot mint actionable commands, authorise agreements or substitute for receipt validation.
- All new components are opt-in behind `OX_PERSONALITY_CHOICE` (default false). Do not mark this policy **adopted** until G16's preregistered native, replay, safety, performance, dialogue and model-comparison gates have passed.

## Rationale / evidence

[G13](g13-experimental-results.md) measured procedural vs original 4/72, independent vs original 7/72 action changes with strong order effects. [G14 v2](g14-experimental-results.md) corrected the position-cover confound and found numeric trait 3/72 in each of two native runs, with prose trait 5/72 then 2/72 action differences; first display position was selected in 119/288 and 121/288 cases respectively. Treat these as separate samples, not an identical replication. The pre-existing `PersonalityRouter` changes GOAP-vs-model consultation probability (roughly 2–90%) without making ordinary shared-cost GOAP plans disposition-specific. These are distinct parameters: **consultation propensity ≠ choice propensity**.

## G16a — one source of authored option tags

Define a **strict Pydantic schema in `contracts/`**, with five finite numeric disposition tags per action, each bounded to [-1,1]: `risk`, `deference`, `social`, `autonomy`, `procedure`. Every offered action must have a stable semantic action key and a record of authored tags. No inference model may silently fabricate a missing disposition, and the world/handler must share the same validated semantics. Tag current live finite-action menus and the four G14 hypotheticals; check the signs of seven unambiguous G14 actions against the measured native directional shifts as a sanity check, **not** as an inference-derived ground truth.

Tagging never changes physical permissions, actor beliefs, or actual equipment procedure correctness; this is an actor-private proposal preference layer.

## G16b — calibration must precede holdout tests

**Completed descriptive G16b, defaults frozen before G16e:** all six `ox-g14-role-*` artifacts were recovered from both [v2 native run #40016163471](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40016163471) and [exact-head rerun #40028008764](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40028008764). The pooled three-position native median top-two log gap was 0.2273 (P75 0.4129). [G16b preregistered calibration](g16b-native-margin-calibration.md) freezes `gain=0.10`, `max_shift=0.21`, base temperature `0.33`, urgent `0.11`, and personal range `[0.20,0.45]`, with an authored per-character formula. **Native top score never exceeded 0.529; `evidence_lock=0.85` triggered 0/48**, so it remains a nonvalidated safety heuristic, not a calibrated correctness probability. G16e must independently validate locked safety fixtures and non-ceiling *behavioural* scenarios. In locked safety cases the controller must force native argmax; cancelling shifts alone cannot prevent a stochastic override.

## G16c/d — branches and replay

`PersonalityRouter` continues to select *habit* (GOAP) versus *deliberate* (Decider) at meaningful decision boundaries, preserving durable actor-bound keyed draws and world-authority separation.

**Habit:** for operator cost `c > 0`, profile dispositions `d` and authored tags `t`, score `z = Σ(d_i × t_i)`; apply `c' = c × clamp(exp(-k × z), 0.5, 2.0)`. Preserve positive costs and the planner's admissibility assumptions; recalculate for every valid operator with this exact same schema. Planner unit tests must demonstrate *different* plans between procedural and autonomy-valuing characters holding observations, capabilities and mission context constant.

**Deliberate:** collect raw three-pass, position-balanced Decider semantic scores; apply bounded `shift_i = clamp(gain × Σ(d_j × t_ij), -max_shift, max_shift)` to each `log(max(p_i, ε))`, normalise via stable softmax and draw from the adjusted distribution with a **replay-stable character-and-boundary-keyed BLAKE2b** value and bounded per-character temperature. Do not use Python's global RNG. Explicitly specify semantic tie handling, zero and near-zero probabilities, reproducibility across permuted menus, and fail-closed behaviour for an invalid scorer pass.

Persist the exact option-key set, tags/schema version, character and cognition revisions, native scores and per-pass evidence, shifts, adjusted probabilities, temperature, safety lock decision, draw, final action and model-call budget in the route ledger **before** any action proposal is sent. Resume an existing boundary without rerolling, even after lost ACK, supervisor crash or changed evaluation order. A later observation must use a newly identified boundary. Enforce a bounded record size and exact snapshot provenance.

**Safety:** on safety-critical choices, forbid personality overrides when a predeclared native evidence-lock rule holds; use reduced temperature on urgent choices. Require independent world permissions, specialist qualification and existing work-receipt gates *regardless* of the proposed action; a locked score is not permission or certified physical safety. Uncertain but critical cases need explicitly authored safety defaults and must not be decided merely by a temperature setting.

## G16e — preregistered behavioural acceptance

Use the six exact G9 native actor-private histories and G14 harness, plus **at least four non-ceiling scenarios**, chosen in advance where the original native top-two margin is < 0.3. Contrast raw position-balanced scorer against adjusted scorer; each sees crossed procedural / independent trait interventions with matched evidence.

Proposed decision gates, fixed before the run:

1. Adjusted procedural vs independent actors disagree on at least **25%** of **non-safety paired** choices, with a separately reported raw unadjusted disagreement rate (expected around 5% from earlier experiments; not a required equality).
2. **Zero personality overrides** in preregistered safety evidence-locked cases.
3. **100% semantic action invariance** to caller menu permutation with fixed prompt, semantic keys and draw.
4. **24/24** same-input repeat choices *and* ledger snapshots identical.
5. No unoffered actions, character-crossing context, unsupported receipts or inferred world completion.
6. Track native-vs-adjusted regret under authored evidence constraints, not mere disagreement. More arbitrary divergence is not a success metric.

If these gates fail, report the failures and leave the feature disabled; do not tune on the evaluation outcomes and rerun the same preregistration as if independent.

## G16f/g and later activation

Profile 6, 20 and 40 actor schedulers, measuring actual native request durations, queueing, idle calls and memory/checkpoint cost. Three Decider forwards imply roughly 3 × 7.7 s CPU **at the historical same-runner median**; 23 s is a planning estimate, not an actual end-to-end 40-actor measurement. An adaptive one-pass/three-pass method conditioned on top-two margin (< 0.15 suggested) is a **new experiment**, never a silent substitute for required balanced scoring.

Separately evaluate a local Qwen3.5-4B speech model and a hosted speech alternative using blinded voice/persona prompts, cost and latency; choose one generative speech provider. The speech model must not select actions from prose.

Rerun the previous 24-pair Qwen3.5-4B versus Decider Q4 comparison with counterbalanced authored expected-choice positions before confirming the local scorer. The [historical local CPU tests](g11-counterfactual-suite.md) confounded the expected first-state action with option 1, so their individual-choice rates cannot justify an architecture ranking. Only after **all** these criteria pass should the model decision be marked adopted and the flag enabled for an opt-in authenticated-supervisor soak; log world receipts, actual crew work and failed/declined proposals separately.

## Engineering guardrails

- Existing Evennia authority and explicit work-ID reconciliation remain unchanged.
- No model inference as a proxy for consent, social commitment, instruction, skill or verified diagnosis.
- No unauthorized role access via stronger personality, procedural compliance or deference.
- Fictional ship verisimilitude and durable consequences—not a real-spacecraft certification process—remain the physical-system design objectives.
