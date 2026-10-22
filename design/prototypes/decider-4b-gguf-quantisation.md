# Decider 4B quantised native-choice comparison

**Scope:** one-pass option scoring, not free-text generation or GOAP planning.
This is an opt-in CPU-only implementation experiment on PR #99, not part of
ordinary CI.

## Arms

- Q2_K, approximately 1.9–2.0 GB GGUF.
- Q4_K_M, approximately 2.7–2.8 GB GGUF.

Both are fetched from the same resolved commit of
`mradermacher/decider-4b-GGUF`. The
`Mapika/decider-4b-GGUF` tokenizer and `decider_config.json` are fetched
at one separately resolved publisher commit. Hashes of the actual downloaded
GGUF files are preserved in separate artifacts. The source repository commit
is not itself proof of equivalence to the publisher's Ollaya BF16 v3
checkpoint: compare file and model metadata before making that claim.

**Crucial implementation:** model inference calls
`decider.infer.Decider(..., gguf_options={n_gpu_layers:0, n_threads:4,
n_ctx:4096, n_seq_max:1}).system_one(state, questions)`. This reads
option-token logits from the GGUF's answer slots. There is no text
generation, JSON completion, invented action, hidden world port or fallback.
The question instructions and candidate codes/descriptions match the
previous Ollaya BF16 experiment as closely as the publisher's GGUF API
permits.

## Metrics and acceptance

Every arm performs:

1. All four G11 synthetic situations with and without private memory
   projection: eight bounded decisions.
2. 24 separate authored counterfactual pairs, each varying exactly one
   observed fact while preserving the candidate command menu, identity and
   private history: 48 bounded decisions.

The result records the chosen and expected action, per-case both-correct
pair scores, decision flips, elapsed wall time, native probabilities,
checkpoint SHA-256 and the specific repository commits. Only **top-choice
accuracy** is used as behavioural evaluation. Probability values are kept
for diagnostics but are not treated as calibrated confidence thresholds.

Hard integration invariants: no unsupported option labels, one inference
request per choice, character- and revision-scoped pending proposals,
zero world effects. Behavioural expected-label accuracy is **not** used
as a hard pass/fail condition: the test must finish and record honest
wrong answers. The offline mock tests verify that an engine choosing the
first option passes integration checks but fails every both-correct pair.

### Existing reference (different serving engine)

The previous BF16 Ollaya Decider-4B run
[39820459716](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39820459716)
recorded 8/8 G11 choices and 47/48 authored counterfactual decisions
(23/24 both-correct evidence pairs) on a four-core 15 GiB RAM GitHub CPU
runner with additional swap. This is a *reference* rather than a
guaranteed matched-weights quantisation baseline. Native GGUF uses
llama.cpp, fewer CPU-resident weight bytes and may have different
runtime/quantisation semantics.

The quantised runs have their own branch-scoped workflow:
`.github/workflows/ox-decider-gguf-quants.yml`. It resolves a single
quantisation repository SHA for both matrix jobs and records a separate
publisher config/tokenizer SHA. No default PR or main-branch model
downloads are enabled.
