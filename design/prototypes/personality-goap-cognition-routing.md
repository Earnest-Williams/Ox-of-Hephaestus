# Personality-weighted GOAP and cognition routing (prototype P1)

**Status:** Decider Q4 behavioural prototype validated in opt-in CI; no production supervisor activation or Evennia authority changes.

## Goal

Every character has a distinctive chance at *meaningful decision boundaries* to consult its native Concordia mind instead of simply executing GOAP's next competent planned step. The LLM is not instructed to make errors. It sees actor-scoped observations and memories, the existing CrewBlueprint personality, subjective stress/fatigue/uncertainty/social pressure, and a finite permitted-action menu. It can select the same action GOAP would have selected, or a different offered alternative.

## Existing contracts

- Blueprint: reuse the immutable existing 12-dimension OCEAN plus Ox psychological profile, not a competing trait system.
- GOAP: existing GoapPlanner does genuine cost-based search over actor beliefs, authored operators, preconditions and positive costs. Predicted effects are not world facts.
- Cognition: existing native CrewAgent and DecisionScheduler use detached inference with observation/cognition revision checks. This prototype adds a bounded optional decision_context to the single-choice prompt; it never becomes a world observation, memory, or permission.
- World authority: Evennia's identity, action, role, receipt and event contracts are unchanged. The new controller returns an ActionRequest proposal but has no world port and sends no commands.

## Probability and boundaries

A stable Bernoulli draw is made once per distinct event/decision boundary, not on every micro-step of an active GOAP plan. The caller supplies an actor-local PersonalState, situation kind and a durable checkpoint callback.

An authored heuristic starts at 0.19, increases with openness, risk tolerance and authority challenge, decreases with conscientiousness; stress interacts with neuroticism. Fatigue, social pressure, uncertainty and situation type also influence the rate. It is bounded to 0.02–0.90. Actor-perceived success/failure adjusts future LLM reliance within a bounded ±0.20. Success reinforces the route actually used: an LLM success increases future consultation, whereas a GOAP success decreases it. Failures normally reverse that tendency; an authority-challenging character may respond defensively to an apparent LLM failure. Feedback entries bind the source event to their original decision boundary, preventing the same evidence from teaching contradictory lessons. These are experimental tendencies, not empirical claims about personality.

Crucially, routing to an LLM never forces a wrong choice. A model may choose the same action GOAP would have selected.

## Persistence and restart

The policy records the seed, authenticated actor DBref, blueprint fingerprint, event ID, Bernoulli draw, probability, route and actor revisions BEFORE invoking either planning branch. The draw uses keyed BLAKE2b and is stable across replay and evaluation order. Reconsideration from genuinely new evidence requires a new decision boundary; resuming the old boundary never rerolls. Corrupt or cross-character snapshots are rejected. Max 2048 boundaries and 2048 feedback evidence IDs; exhaustion fails closed pending future archival.

Feedback requires an actor-addressed WorldObservation and source event ID. It represents the character's *interpretation* of a consequence, never authoritative verification of success. Duplicates do not update twice. Persistence failures roll back the change.

The caller must use the existing durable WorkStepLedger and Evennia authentication/receipt pipeline before sending any future physical action. The offline personality controller itself has no world connection.

## Verification

The new native tests check idempotent restart/replay, trait-driven frequency, feedback and provenance, checkpoint failures and cross-character rejection. They execute a real GoapPlanner branch with zero model calls, or the real native Concordia agent and asynchronous DecisionScheduler with a bounded action menu; no unoffered commands, silent inference-to-GOAP fallback or fake physical success are permitted.

The offline pilot runs three different authored personalities through 48 synthetic decision boundaries each, reporting model-call and route counts. It deliberately uses native Concordia MockModel for integration, **not** to claim genuine spontaneous personality, reasoning, mistakes or model comparison.

## Explicitly deferred

This change does NOT turn personality routing on in the production three/five-crew supervisor. The live supervisor's WorkStepLedger and interrupted-command recovery need a distinct incident-level checkpoint integration before action submission can be enabled. It also does not add an actual Decider/Qwen provider: the comparative local model adapter remains on separate experimental PR #99.

The reversible, real-world pump boundary was subsequently integrated and validated (see below). Decider Q4_K_M is now selected; further Qwen comparisons are not a decision requirement. Measure story-relevant, attributable departures separately from incoherent provider mistakes. No world permissions or approved procedures are waived by model delegation.

## Live-world validation, not merely a mock choice

The opt-in P4a scene in
`ox_ai.scenarios.p4a_personality_gate` starts from a genuine world
cooling alarm. Lin's authenticated character sends the shipboard radio
alert; Ari receives its addressed world event, physically inspects the
pump and only then encounters an incident-level choice. The GOAP branch
runs the actual pump action model over Ari's beliefs. The other branch
uses native Concordia with actor personality and subjective state.

The selected alternative can leave the fault unresolved. Any actual
isolation travels through the existing `WorkStepLedger` and
`DurableEvenniaPort.submit_work`, with an original request ID
checkpointed before sending. The restart fixture simulates an
interruption **after Evennia commits the physical isolation**, then
restores the brain, routing ledger and original WorkReceipt in a fresh
Python process, without repeating the world operation.

[Live world CI #39844286854](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39844286854)
passed all three isolated cases:

| Case | Chosen route and effect | World assertion |
| --- | --- | --- |
| Methodical character | GOAP, isolate P-01 | P-01 isolated, exactly one isolate event |
| Independent character | Concordia mock chooses to defer | P-01 still low-pressure; no isolate |
| GOAP crash and restart | Same saved route and exact work ID | Isolate committed once; reconnected process reconciles |

The synthetic branch-coverage harness deliberately searches for stable
seeds selecting each branch, so these three outcomes are **not evidence
of empirical routing rates**. They prove the actual actor/world/receipt
wiring under each route. Prior 48-decision-per-person smoke tests are
the separate personality-rate distribution fixture, still with a
deterministic MockModel.

A further optional workflow at
`.github/workflows/ox-personality-models-live.yml` tests the **same
world-observed boundary and same independent blueprint** with two
genuine Q4_K_M models on separate independently provisioned worlds:

- Decider 4B Q4_K_M uses the real `decider-ai` native
  `system_one` option-logit readout from pinned GGUF weights,
  with zero generated text.
- Qwen3.5-4B Q4_K_M uses the previous pinned Unsloth SHA-256 and
  pinned llama.cpp CPU server with the strict local chat-choice API.

Each model's choice is allowed to be `isolate` or `defer`: no
benchmark expected label is secretly substituted. Evennia's independent
state and event-count verification establishes what really occurred.

This is still **one world decision per real model**, not an operational
quality estimate or evidence for believable character mistakes across
a long voyage. The live supervisor stays unchanged until a separate
recovery-aware activation is accepted.

### First real local 4B model choices (verified)

[CPU-only P4a world model workflow #39846130944](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39846130944)
**passed both independently provisioned jobs**. The model choices were
genuine, not scripted, and both used the exact same person profile, route
probability 0.6138, stable route roll 0.3159028547, observations and
offered action menu. Each used one model call.

| Engine | Model-chosen action | Evennia physical result | World isolation events |
| --- | --- | --- | ---: |
| Decider 4B Q4_K_M via native option logits | isolate | verified isolated | 1 |
| Qwen3.5-4B Q4_K_M via local llama.cpp chat choice | isolate | verified isolated | 1 |

The Decider probability distribution was
`isolate=0.7463, defer=0.2537`. These probabilities are a
diagnostic, not a certified confidence measure. Both actor-private
checkpoints include exactly one route and one durable world WorkReceipt.

The first Qwen attempt in an earlier workflow used a 20-second cold CPU
deadline and was correctly rejected by the scheduler without physical
effects. The corrected **experiment-only** deadline was 110 seconds;
the production scheduler was not modified. An unrelated CI provisioning
error from placing credential export and database migration in the same
step was also fixed before the successful run.

These two choices are **not** evidence that Decider is psychologically
more or less credible than Qwen. They shared a plainly justified
operational decision, and both followed it. Next behavioural work
should present genuine competing personal commitments, ambiguous
interpretation, colleagues' disputed authority and the possibility
of acting against a *known* procedural preference. Quality metrics
must distinguish inconsistent model mistakes from attributable
character mistakes, while preserving native GOAP and world authority.



## Chosen decision head and next behavioural assay (2026-10-22)

**Decision fixed:** Decider 4B Q4_K_M is the single selected finite-action
consultation model. Qwen is historical comparative evidence, not an ongoing
selection candidate. The optional real-model workflow now runs Decider only.

`ox_ai.scenarios.personality_dilemmas` defines two **authored, actor-scoped**
dilemmas: an engineer deciding how to respond to a low-pressure pump when Mara
asks for a favour, and an engineer responding to a red cargo-restraint gauge
when Jon asks for leniency. Three characters are methodical, personally loyal,
and authority-challenging. Each character receives the same perceived situation
and the same four available actions, once without and once with a relevant
private recollection. The GOAP reference is a real planner result, not a
hard-coded outcome; Decider may agree, recheck, escalate, or defer.

The expanded validation is a **48-decision / 24-pair assay** (four conflicts,
three personas, two memory arms and two offered-action orders); it does not
imply 48 independent samples of psychological behaviour. Each private-memory pairing shares the
identical actor, observation, trait blueprint, boundary ID, routing seed and
finite action menu. Routing seeds intentionally cover the LLM branch for
measurement; the natural routing-frequency tests remain separate.

The output records the chosen option, the GOAP baseline, native Decider option
probabilities, changed choices after memory, counterbalanced option positions,
and stable route draws. Because
Decider is an option scorer, **it does not generate reasons**. Inferences
such as loyalty or mistrust being causal are hypotheses to investigate, not
assertions of access to the character's internal reasoning.

All evidence in this assay is authored experiment fixture material, not
world-authenticated Evennia observations. There is **no world port, no physical
command, no receipt, and no modification to production supervisor activation**.
The existing independent live-pump test retains the authoritative Evennia and
work-receipt checks. Fixture-only test results must never be reported as
Decider outcomes.

Validation: `python -m unittest discover -s services/ai-handler/tests -p
test_personality_dilemmas.py -v` and `python -m ox_ai.scenarios.personality_dilemmas
--model fixture --output .ox-state/personality-routing/dilemmas-fixture.json`
run in the regular personality CI. A separate opt-in Decider CPU workflow runs
the corresponding real GGUF assay and archives the individual decision records.
Interpret the data before expanding to actual longitudinal interaction,
staggered information, contradictory testimony, or action consequences.


### Behavioural assay acceptance: real Decider Q4 (2026-10-22)

[Green workflow #39858425168](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39858425168)
on commit `e47ddf85` used the selected **Decider 4B Q4_K_M** with
unchanged native model scoring and no scripted action selection. Every
model choice was an actor-scoped proposal. The separate live Evennia
pump operation passed receipt reconciliation and independent world
event-state verification.

| Metric | Observed |
| --- | ---: |
| Real Decider decisions | 48 |
| Changed from GOAP's symbolic first step | 20 / 48 |
| Memory changed the selected option (order-specific pairs) | 6 / 24 |
| Distinct persona/dilemma memory effects reproduced in **both** orders | 3 / 12 |
| Semantic choice unchanged when action-menu order reversed | 22 / 24 |

**Specific reproduced memory effects (same perceived facts, profile and
routing draw):**

- **Loyal engineer, nonurgent filter:** filing the maintenance ticket
  changed to **help Rae replace the filter before filing** when recalling
  Rae's earlier personal help. The methodical engineer consistently
  filed the ticket. This is the clearest relationship-driven,
  role-appropriate deviation.
- **Authority-challenging engineer, low-pressure pump:** immediate
  isolation changed to **rechecking** after recalling wrongful blame
  for an unnecessary isolation. This held in both menu orders.
- **Methodical engineer, low-pressure pump:** immediate isolation also
  changed to **rechecking** when recalling a previous missed problem
  and rupture. This may reflect caution or overchecking, but is not
  evidence of a uniquely defiant motive.

**Useful negative controls and limitations:** All three personas secured
the red cargo restraint rather than protecting Jon's record. All chose
to request an authorized watch swap rather than instantly taking over
Lio's duty. Those choices are sensible, but the watch-swap case did
not distinguish personalities. The defiant engineer's minor-filter
deferral was **order-sensitive** (record in canonical order, defer in
reversed order); do not count it as a robust trait result. The remaining
22/24 order checks agreed.

No social goals, personalities, preferred actions, or final outcomes
were hard-coded into the model adapter. The case histories were
authored, not naturally acquired; this probes behavioural sensitivity,
**not** causal psychological validity or a longitudinal voyage.
The earlier 12-choice experiment is a subset and should not be added
as independent evidence. Native option scores are diagnostic
preferences, not calibrated confidence or generated explanations.

**Acceptance:** The three reproducible, actor-specific memory effects,
especially the loyal engineer's safe assistance deviation, establish a
meaningful behavioral response rather than simply passing a harness
integration test. Retain Decider Q4 as selected. The next high-value
experiment is an operational sequence in which crew members encounter
each other's real world-observed actions and update memories over time;
do not reactivate model comparison or infer personality from a single
choice. The prototype does **not** enable personality routing in the
production supervisor.
