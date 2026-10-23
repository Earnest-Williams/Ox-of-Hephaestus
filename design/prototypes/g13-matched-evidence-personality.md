# G13 — Within-character matched-evidence personality counterfactuals

This follows the merged G10 (216 native Decider choices), G11 (21 real Evennia social replies) and forty-personality routing checkpoint stress (#108). Those experiments **do not** identify how much of a response difference comes from personality itself: G11 has unequal opportunity exposure; G10 holds genuine per-actor memories, but each person also has different traits, experiences, counterpart and evidence.

## Intervention

For each of **six authenticated G9 brains** (original 205-turn world archive, independently SHA-256 checked), branch **three** isolated trial states: the original twelve traits, a procedural intervention of six traits, and an independent/risk-tolerant intervention of the same six traits. Within an actor and condition, **the identity, original memories, witnessed observations, native component state, cognition revision, counterpart, hypothetical circumstances and option labels are held fixed**. Only the six chosen trait values and the corresponding read-only Concordia CharacterProfile text change.

No experimental treatment overwrites the original brain, creates an authoritative observation, issues a live social offer, or calls an Evennia command. A reversible checkpoint transformation and **native prompt hash after substituting a neutral placeholder for the trait text** reject evidence or non-profile prompt changes. Actual native Decider choice probabilities are recorded for each semantic option (accept, defer, decline), regardless of display order.

Each actor: **four distinct hypothetical commitment scenarios** × **three menu orders** × **three profile arms** = **36** native choices, plus **four** repeated original-profile/canonical-order controls. Six actors = **240 native model calls**, including 216 factorial choices and 24 repeat controls. The final aggregator refuses any missing actor, treatment, model outcome, prompt equivalence, or source evidence digest.

These cases test whether **trait conditioning** changes model preference under controlled evidence. They do **not** recreate an individual with a different life history and do **not** measure causal changes to lived shipboard behaviour. G11 remains the evidence for *actual receipted world consequences*. The separate offline personality router's computed consultation probabilities are recorded but do **not** change G13's direct Decider experimental assignments.

## Acceptance and uncertainty

A valid result can find **zero** stable personality change: the purpose is not to force interesting deviations. Report:
- Matched original-versus-procedural, original-versus-independent and procedural-versus-independent disagreements;
- Each profile arm's acceptance/deferral/decline distribution;
- Response differences caused by menu-order permutations;
- Repeated identical-input agreement and option-score stability;
- Differences in *configured* Decider consultation propensity, kept distinct from native action choice.

Do **not** claim that every difference is psychologically realistic, harmful, or story-worthy. G10 had only 40/72 order-invariant three-way cases, so the order and repeat controls are essential for interpreting even seemingly dramatic trait effects.

## Execution

Run the opt-in [G13 native workflow](../../.github/workflows/ox-g13-personality-causal.yml) on this PR (not the inherited full Evennia suite). Each shard downloads the previously verified G9 archived source from Actions run 39872687597, uses the pinned Decider 4B Q4_K_M native GGUF choice backend, and uploads bounded anonymisation-free actor-local **summary data only**; no GGUF and no private full-brain checkpoint are uploaded. The six-role aggregate rejects partial data.

**Status:** implementation prepared; live experiment and its complete report must be verified in GitHub Actions before claims of empirical success or merge.
