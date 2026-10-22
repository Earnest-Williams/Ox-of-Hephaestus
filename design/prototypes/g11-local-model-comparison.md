# G11 follow-up: stronger generative model and native decision heads

Status: opt-in GitHub CPU experiments on experiment/qwen3.5-0.8b-ci.
Never treat a queued workflow as a completed model evaluation.

## Models

| Model | Purpose | Serving | Weights |
|---|---|---|---|
| Qwen3.5-0.8B Q4_K_M | Existing baseline | llama.cpp OpenAI-compatible chat | 0.56 GB |
| Qwen3.5-4B Q4_K_M | Larger generative comparison | llama.cpp OpenAI-compatible chat | 2.74 GB (Unsloth) |
| Laya English | Fast specialised decision head | Ollaya /api/decide | ModernBERT-large, 421M |
| Laya typed-decisions | Specialised fine-tuned decision head | Ollaya /api/decide | ModernBERT-large, 421M |
| JevK5-4B v0.3 Q8_0 | Qwen3.5-4B decision specialist | Ollaya /api/decide, llama.cpp | 4.48 GB |
| Decider 2B | Purpose-trained decision head | Ollaya /api/decide | 3.76 GB (registry ONNX plus safetensors) |

Laya, JevK5 and Decider are **not chat models**: they consume a state, an
explicit question and a bounded menu, returning choice probabilities
with no free text. The first native-entity adapter feeds Concordia's
authored choice prompt to /api/decide; the action descriptions come
from the SAME caller-supplied command options. This differs from
the Qwen chat-completion interface, so score comparisons are
descriptive, not a controlled architecture comparison.

## Protocol

Use the unchanged G11 four synthetic actor-scoped evidence fixtures.
Each arm receives identical seeded memory, observations, interpretations,
time and Concordia state. The only arm difference is bounded
OxMemoryContext visibility. Three paired repetitions create 12 decisions
per arm, 24 per model. The order alternates to reduce warm-cache bias.

Success requires local inference to return validated finite options
and a pending proposal. Failed HTTP requests, missing probabilities,
invalid labels, and truncated input fail closed. No model result can
send a game-world command, forge a world receipt, or grant authority.

The original 0.8B results are recorded in qwen3.5-local-cpu.md.
The follow-ups run from:

- .github/workflows/ox-qwen-4b-cpu.yml
- .github/workflows/ox-decision-models-cpu.yml
- .github/workflows/ox-decider-2b-cpu.yml (isolated Decider pull/run)

Qwen 4B weights use a verified upstream SHA-256:
00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4.
Both llama.cpp and Ollaya binaries are release-pinned and checksum
verified. Ollaya additionally pins registry manifests and their
downloaded blobs to the model publishers' hashes.

## Interpretation

A high authored expected-choice rate is NOT evidence that a model
understands the world. This is a small, synthetic four-case pilot:
retracted commitments, contradictory cargo evidence, confidentiality
and identical repeated refusal. Individual choices and the full
option-probability distribution matter more than a pooled score.

The larger model will usually cost more CPU time. Decision-head
models might be much faster, but they cannot perform the rest of
Concordia cognition that requires language generation.

Repeated identical prompts reuse prompt / KV caches for decoder
models, so median wall-time is an observed run statistic, not a
cold-prompt benchmark. Good results warrant more varied cases,
repeated independent contexts and a separate real-world authority
integration experiment.

## Decider 2B addition (22 October 2026)

The Ollaya `decider:2b` registry manifest names an ONNX inference graph,
a 3,763,692,048-byte weight layer from `Mapika/decider-2b` at the
publisher-pinned revision `9839cc9d908be16c5988c0d041034b5fdf82c7a2`, and
tokenizer/decision/calibration layers with SHA-256 digests. The separate
branch-scoped Decider workflow avoids re-downloading all three Laya/JevK5
models. The same bounded Concordia adapter and existing G11 fixtures are
used, with three repetitions (24 decisions). Model-choice accuracy is
observational rather than a prerequisite for integration success.

The common `MODELS` allowlist includes `decider:2b`, so future enlarged
counterfactual runs can select the same ID without a new adapter.

## Decider 2B verified G11 result and counterfactual extension

[Decider G11 CPU workflow #39817607191](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39817607191)
completed successfully. Both baseline and augmented memory matched authored
expected choices on **9/12** repeated cases (75%), with zero private-letter
disclosures and **three unchanged-refusal repeats in each arm**. The median
per-decision latency was approximately 4.63 seconds without memory projection
and 6.85 seconds with it; these are observational CPU figures, not controlled
cold-cache timings. This places Decider between the original Laya variants
and JevK5 on this very small fixture set.

The follow-up counterfactual harness in
`scenarios/counterfactual_decision_trial.py` contains 24 distinct situations,
each with two mutually exclusive actor-visible evidence states. It runs one
augmented-memory native Concordia choice in each state (48 per selected
model), preserving an identical finite menu and private seed across the
pair. Evaluation reports **both-correct pairs**, individual authored-choice
matches, and actual decision flips separately. The expected labels reverse
across variants; the model's actual choice is never a world receipt.

The dedicated Decider workflow runs these counterfactuals after its existing
24-call G11 test and checks fixture/inference invariants offline first.
The counterfactual result is not established until the expanded workflow
completes successfully.
