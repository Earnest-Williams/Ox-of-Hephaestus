# G16h — unconfound the 24 G11 counterfactual model comparisons

**Status: preregistered and implemented experimental harness, no native
G16h result or model-selection adoption yet.**

The historical [G11 local comparison](g11-local-model-comparison.md)
had a serious per-decision positional confound: in every one of the
24 authored original evidence states the correct semantic action
appeared first; after the evidence changed the correct action
appeared second. Even a generic first-choice tendency could inflate
the original-state score. The pair-level **both-correct** metric
remained meaningful but did not measure complete semantic
order-invariance.

G16h preserves **all 24 original authored cases without rewriting
their expected answers** in
[immutable fixtures](../../scenarios/g16h_counterfactual_cases.py)
and the [preregistered comparison schema](g16h-balanced-model-comparison-preregistration.json).
It runs both evidence variants under both original and **reversed**
caller option orders. Thus every model sees 96 candidate decisions,
with the expected choice in position one **48 times** and position
two **48 times**. Each actor has the same seeded recollection,
the same privately addressed evidence and only two finite authorized
options. No world receipt or Evennia command is ever produced.

## Providers and cost accounting

- **Decider 4B Q4_K_M** uses the real publisher's System One API
  and an explicit two-option G15-like position-balanced adapter.
  Each of 96 Concordia decisions scores **both** native code
  positions and averages by **semantic action key**, totaling
  **192 genuine native forwards**. Each raw two-pass vector
  is preserved, not just the chosen action.
- **Qwen3.5-4B Q4_K_M** uses one genuine local llama.cpp
  OpenAI-compatible chat inference per 96 Concordia decisions.
  The same model weights and verified SHA-256 as the historical
  G11 4B comparison are reused. Each original/reversed caller
  menu is explicitly presented and compared.

**These providers do not have identical interfaces or inference
cost:** Decider takes two true native forwards to balance response
tokens, whereas generative Qwen gets one chat request and may
interpret descriptions differently. Measure both per-decision
latency and underlying requests; never claim a Qwen-versus-Decider
latency speedup while silently comparing different amounts of work.

The [full runner](../../scenarios/g16h_balanced_model_comparison.py)
records exact actor prompt hashes, original observation and memory
hashes, semantic option keys, expected position, actual choice,
real latency and unexecuted request validation. The independent
[aggregator](../../scenarios/g16h_compare_results.py) refuses a
missing or duplicate matched case, fake output, altered actor
prompt/evidence, unexpected provider, unbalanced native probability
mapping or claimed world effect.

Publish **both-correct out of 24 by caller order**, per-decision
accuracy separately for expected positions one/two, 48
same-evidence order-invariance comparisons, and median latency.
Do not select a flattering order, discard weak categories or
equate 24/24 expected-pair success with authentic human personality.

Passing G16h can support the proposed finite-action model choice,
but it does not adopt the complete G16 routing architecture.
G16e must separately show coherent trait-sensitive behaviour,
G16f must measure 40-character throughput, G16g must select
a speech model, and the authenticated supervisor soak must verify
real proposals and Evennia outcomes independently.

## Native outcome (24 October 2026)

The isolated [native comparison run #40049040761](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40049040761) **completed with all four jobs green**. Its independent aggregator matched every original/reversed actor prompt and factual evidence, verified all 192 underlying Decider native vectors and both correct-option positions, and retained no game commands. **Decider Q4: 94/96 correct; Qwen3.5-4B Q4: 87/96 correct**. Both-correct pairs were Decider 23/24 in each order and Qwen 19/24 canonical, 20/24 reversed. Decider was slower at 17.79 s median binary choice (two native forwards) versus 7.01 s for Qwen chat (one). Decider 46/48 raw caller-order consistency still falls short of full invariance; the actual G16c controller separately canonicalizes its menu. [Complete results, exceptions and limitations](g16h-verified-native-results-2026-10-24.md).

This is **positive comparative support for the proposed finite-action Decider Q4 scorer**, not a claim of engineering safety, autonomous psychological realism, hardware scalability or an adopted production personality policy. Keep the feature disabled until the other G16 behavioural/soak gates pass.
