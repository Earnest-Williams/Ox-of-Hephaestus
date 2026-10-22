# G11 counterfactual decision suite (experimental)

## Purpose

Replace repeated identical choice prompts with **24 independent authored
situations**, each having two mutually exclusive actor-visible evidence states:
**48 choice requests per model**. This is still a small diagnostic experiment,
not evidence of production-level cognition. All inputs are synthetic and
contain no private user or live ship data.

Five backends use the same `scenarios/counterfactual_decision_trial.py`
fixture collection through the native Concordia `CrewAgent`:

- Qwen3.5-0.8B Q4_K_M (local llama.cpp chat)
- Qwen3.5-4B Q4_K_M (local llama.cpp chat)
- Laya English (local Ollaya typed choice)
- Laya typed-decisions (local Ollaya typed choice)
- JevK5-4B (local Ollaya typed choice)
- Decider 2B (local Ollaya typed choice)

The two states in each pair share the exact same actor identity, authored
historical recollection, candidate action set, memory-projection mode and
role brief. The **single world observation** differs. The model cannot see
the alternative state's observation.

## Cases and measurement

Situations span commitments, equipment readings, contradicting sensors,
stock availability, chief authorisation, lost work receipts, cargo faults,
confidentiality, duty handovers, repeat refusals, emergency triage, hatch
access, radio responses, spare allocation, fire confirmation, qualifications,
handover acknowledgement, medical privacy, superseded reports, revised
agreements, commissioning permission, motor temperature, deadlines and
navigation.

The two predeclared expected verbs differ for each pair. Results report:

- **Individual match rate:** proportion of individual choices matching the
  authored expected action.
- **Counterfactual pair success:** proportion of cases where *both* the
  unchanged state and the modified state received their expected actions.
- **Decision flip rate:** proportion of cases where the two decisions differ,
  whether justified or not.
- Per-case chosen/expected verbs, duration, category, and the native typed
  model's option probabilities (where the API provides them).

Pair success is the most informative diagnostic: a model that always selects
the first offered action will appear 50% accurate but fail every pair.
The report separately marks `real_model=false` for deterministic capture
smoke testing.

One native Concordia inference request produces one proposed action. No
Evennia game, world port, game command, work receipt or completion claim is
created. Invalid model labels and missing or truncated Ollaya response fields
fail the run; no MockModel fallback is allowed in real-model modes.

## Execution

The branch-scoped, opt-in test workflows execute 48 counterfactual decisions
after their previously verified G11 smoke / memory comparisons. All 24 pairs
are integrity-tested offline beforehand. Model fetch, binary setup and
inference occur on disposable CPU-only GitHub runners. The original workflows
are isolated from ordinary pull-request or `main` inference triggers.

The suite permits selecting `decider:2b` by its native Ollaya model ID.
Its dedicated workflow avoids re-downloading the larger Laya/JevK5 corpus.

## Limitations

This is **authored binary-choice evaluation**, not an independent blind
benchmark. Option descriptions may cue expected behaviour, observation
semantics are explicit, and full world state is absent. Neither raw matches
nor model-reported option probabilities demonstrate calibration or action
authority. Laya/Decider/JevK5 expose probabilities through Ollaya; Qwen
provides lettered chat choices, so their response interfaces are not
directly comparable. Prompt/KV caching affects speed. Do not promote a
ranking to runtime policy without varied cases, outcome adjudication and
real-character world tests.
