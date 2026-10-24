# G16h — actual non-position-confounded Decider Q4 versus Qwen3.5-4B result

**Completed and independently reconciled on 24 October 2026.** The isolated [GitHub Actions run #40049040761](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40049040761) finished its fixture source gate, genuine Decider Q4 System One arm, genuine Qwen3.5-4B Q4 chat arm and independent two-artifact comparison job, **all green**. Its artifact `ox-g16h-clean-qwen-versus-decider` contains `clean-comparison.json`; source artifacts `ox-g16h-decider-q4-native` and `ox-g16h-qwen4b-native` retain all 96 per-model decisions. Experiment source commit `af7b6e3d74099c1423a4cfa66d3dfb49c5dfc6f2`. Later development-head changes to the workflow's PR-only cancellation expression and independent fixture tests did not change the scorer or comparison source.

## Matched native outcomes

The complete 24-case historical G11 evidence-flip suite was retained intact and run under **both** original and reversed caller option orders, with the expected action appearing first **48 times** and second **48 times** for each model.

| Prespecified measure | Decider 4B Q4_K_M | Qwen3.5-4B Q4_K_M |
| --- | ---: | ---: |
| Correct / 96 real decisions | **94/96 (97.9%)** | 87/96 (90.6%) |
| Correct when expected answer first | 47/48 | 42/48 |
| Correct when expected answer second | 47/48 | 45/48 |
| Both-correct counterfactual cases — canonical outer order | 23/24 | 19/24 |
| Both-correct counterfactual cases — reversed outer order | 23/24 | 20/24 |
| Same semantic choice across caller orders | 46/48 | 43/48 |
| Median full decision time on separate CI CPU runners | 17.79 s | **7.01 s** |
| Genuine underlying model requests | **192** (two native code rotations/decision) | **96** (one chat request/decision) |
| Authenticated game commands / work receipts | 0 / 0 | 0 / 0 |

The independent aggregator verified **all 96 matched Concordia prompt hashes**, historical evidence/recollection SHA-256 digests, two expected option positions per case, and (for each Decider decision) both recorded native probability vectors and their arithmetic means keyed by semantic action rather than letter position. An independent cross-check of the complete raw archived rows reproduced these metrics: 86 decisions both models correct, 8 only Decider correct, 1 only Qwen correct, and 1 both incorrect. These 96 observations are **not independent draws**: each of 24 authored case pairs is presented under two outer orders.

The Decider Q4 model used exact GGUF SHA-256 `c03deb433d539ef49579fca5a015d5090c739a331448493aded7a57ad9b4261b` and publisher revisions pinned in the workflow. Local generative Qwen Q4 used SHA-256 `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4`.

## What is and is not supported

**Supported:** the originally position-confounded per-decision scores are superseded by position-balanced evidence. Within this small authored finite-action suite, **Decider Q4 is a better-accurate but more CPU-expensive local choice scorer** than Qwen3.5-4B chat. That supports retaining Decider as the *proposed* position-balanced finite-action scoring backend while a separate generative model handles dialogue.

**Not demonstrated:** consistent safety or permission correctness, genuine 40-actor burst capacity, believable personality differences, or authority to change world state. Decider's two errors were `repeat_refusal / earlier / canonical` and `spares_priority / earlier / reversed`; the latter conserved a critical spare under an authored emergency scenario and must not be mistaken for safe behaviour. Qwen's errors included both caller orders of `isolation_clearance / changed` (proposing isolation after permission was refused), and both `cooldown / earlier` orders (requesting waiting despite an acceptable temperature). World eligibility/safety rules must still vet *every* proposed command.

The raw Decider comparator was semantically invariant under 46/48 caller-order tests, **not 48/48**, despite balancing its native answer-token positions. The outer Concordia prompt still presented options in differing order; G16c's actual handler instead canonicalizes the menu before scoring and is tested separately. Do not replace that runtime invariant with the comparator's success rate.

Cost is not directly comparable at the raw model-forward level: Decider needed two genuine System One calls and Qwen one chat completion per binary choice, with different model-serving interfaces and runner load. See [G16f real 6/20/40 native throughput](g16f-native-throughput-results-2026-10-24.md) for the separate three-option production-path capacity issue.

**Decision status: proposed, not adopted.** Accept the clean evidence as a positive comparative result for the proposed Decider Q4 scorer, but retain the default-off policy until G16e's genuine six-actor personality holdout, G16f supervisor capacity/queue admission, G16g blinded speech review and an authenticated Evennia supervisor soak pass.
