# Personality-weighted GOAP and cognition routing (prototype P1)

**Status:** experimental branch, no production supervisor activation or Evennia changes.

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

The caller must use the existing durable WorkStepLedger and Evennia authentication/receipt pipeline before sending any future physical action. The prototype itself has no world connection.

## Verification

The new native tests check idempotent restart/replay, trait-driven frequency, feedback and provenance, checkpoint failures and cross-character rejection. They execute a real GoapPlanner branch with zero model calls, or the real native Concordia agent and asynchronous DecisionScheduler with a bounded action menu; no unoffered commands, silent inference-to-GOAP fallback or fake physical success are permitted.

The offline pilot runs three different authored personalities through 48 synthetic decision boundaries each, reporting model-call and route counts. It deliberately uses native Concordia MockModel for integration, **not** to claim genuine spontaneous personality, reasoning, mistakes or model comparison.

## Explicitly deferred

This change does NOT turn personality routing on in the production three/five-crew supervisor. The live supervisor's WorkStepLedger and interrupted-command recovery need a distinct incident-level checkpoint integration before action submission can be enabled. It also does not add an actual Decider/Qwen provider: the comparative local model adapter remains on separate experimental PR #99.

Next: integrate one reversible, real-world decision boundary with durable world receipts; run model-free versus persona-routed Decider Q4_K_M and generative Qwen with identical actor-scoped evidence. Measure story-relevant mistakes and character consistency separately from incoherent provider mistakes. No world permissions or approved procedures are waived by model delegation.

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
