# Qwen3.5-0.8B local CPU integration probe

Status: experimental branch only. A green real-model workflow is required
before claiming that live CPU inference worked.

## Goal

Use the existing ox_ai.inference.compatible_chat.CompatibleChatModel with
native Concordia and a real Qwen3.5-0.8B model on a standard CPU-only
GitHub Actions runner. The OpenAI Python library talks only to localhost,
not to a hosted provider. No API secrets or GPU are required.

The probe feeds one synthetic character a directly observed pressure reading,
then offers two world-command proposals: inspect a gauge or defer. Either
valid choice passes. The chosen command stays pending, with no world
command, receipt, mutation, or verified repair. Model errors and invalid
choices fail rather than falling back to the MockModel.

## Workflow and resources

- .github/workflows/ox-qwen-local-cpu.yml is branch-push triggered only
  for named experiment source files on experiment/qwen3.5-0.8b-ci.
  It is also manually dispatchable after being registered on main.
- It is never automatically run on ordinary PRs or main pushes.
- Installs Python 3.12, pinned native Concordia, and the OpenAI SDK.
- Downloads notschmee/Qwen3.5-0.8B-GGUF, Q4_K_M to an Actions cache.
  The **observed first-run model SHA-256** is verified on every run:
  `be5b3cb8c2f3ebd791349c9c775ea38950f23a2b9e792ca2f0411597dd172988`.
  The upstream URL references a floating branch, but unexpected changes now
  fail closed rather than silently altering evaluation. Update both the
  expected digest and cache key when deliberately changing weights.
- Uses a pinned llama.cpp b11819 CPU-only release with SHA-256 verification,
  no GPU offload, non-thinking output, one inference slot, and a 4096-token
  context. Startup and workflow runtimes are bounded.
- Runs existing adapter unit tests plus a new offline native Concordia
  test before starting the real model. Archives probe result, model digest,
  and local server log for seven days.

## What passing means

One real model answered a native Concordia finite-menu prompt, preserving
actor identity and observation revision; the action remained an unconfirmed
proposal. This is not proof of realistic choices, memory A/B improvement,
multi-agent behaviour, 500-turn throughput, or Evennia recovery.

Next steps are bounded repeated-turn latency measurements, matched-evidence
memory interpretation A/B, then opt-in multi-character world experiments.
Do not place this inference workflow in fast PR CI.

## First real CPU run (22 October 2026)

[GitHub Actions #39801133657](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39801133657)
completed successfully at commit `fd07d3e`. The real model selected
`inspect gauge`, preserving character `#801` and observation revision 1.
Its single Concordia inference call measured **2.0768 seconds** on the
GitHub CPU runner. The model file was downloaded and cached; no physical
world commands were sent. This single sample is not a throughput estimate.

## Follow-up: G11 paired memory decisions

The branch-specific Qwen workflow now also runs the existing G11 pilot
using `--provider qwen-local`: four synthetic fixtures (promise withdrawal,
contradictory cargo evidence, confidentiality, and redundant refusal)
under baseline and memory-augmented Concordia context, **24 genuine model calls** over three repetitions. Both arms start with identical actor-visible
evidence; only the bounded memory projection differs. The pilot archives
per-case choice, expected-label match, prompt size, and inference latency.
Invalid responses fail rather than being counted as valid decisions.

These results are **descriptive model-behaviour observations**, not reliable
evidence that memory improves choices. Neither scoring nor model output
authorises a world action. The original hosted G11 workflow remains manual.

## Three-repetition G11 result (22 October 2026)

[GitHub Actions #39808706470](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39808706470)
completed successfully at executable commit `c3d050c`. All 24
model requests returned accepted finite choices; the same action
was selected in each of the three repeats for a given case/arm.
There were **12 decisions per arm**, across four authored cases
repeated three times, not 12 independent evidence scenarios.

| Fixture | Baseline action (3/3) | With memory projection (3/3) | Authored expected |
| --- | --- | --- | --- |
| Withdrawn watch-swap pledge | clarify | assume | clarify |
| New contradictory cargo evidence | inspect | inspect | inspect |
| Private letter without permission | disclose | withhold | withhold |
| Previously refused identical request | repeat | repeat | investigate |

Both arms matched authored expected actions **6/12 (50%)**. Baseline
disclosed the private letter on three of three repeats, augmented on
zero. Both repeated an unchanged refused request on all three repeats.
Memory context helped confidentiality but hurt response to a recanted
promise. This is **not** a reliable aggregate estimate of cognition
quality, and no command was submitted to Evennia.

Elapsed time per choice was **confounded by llama.cpp KV/prefix reuse**.
The first augmented prompts in this run took around 2.0–2.4 seconds,
whereas exact repeated augmented prompts fell to around 0.10 seconds.
Baseline prompts were around 1.2 seconds in this run. Accordingly,
neither aggregate median nor arm-to-arm latency comparison measures
independent cold prompt processing. A dedicated performance experiment
should control cache state and account for prompt and sampled tokens.

## Disposition

Local Qwen CPU inference is **proven viable** for integration testing and
bounded model-behaviour probes. The smoke and G11 repeated trials
passed. Do not make authored expected actions a hard CI gate: the
model has exhibited stable poor choices despite correct integration.
Keep MockModel deterministic regression gates and world-authority
invariants separate from optional real-model observational experiments.
