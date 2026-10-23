# G15 — Experimental position-balanced native Decider scoring

**Scope:** pure, opt-in choice-adapter preparation only. No production supervisor switch and **no native model-quality measurements yet**. G14 remains a separate experiment in progress; neither its incomplete results nor arbitrary trait-success thresholds are used to tune this policy.

## Why

The completed [G13 240-choice experiment](g13-experimental-results.md) established a large **option-order effect** relative to small within-actor trait changes. The original Decider 4B Q4_K_M adapter scores three typed actions at positions A/B/C and returns one proposal. If presentation order strongly affects logits, a downstream personality narrative could be mistaken for an option position artefact. We should measure and, where justified, neutralize that source of variation before attributing differences to stable individual temperament.

## Implementation and boundaries

[Experimental scorer](../../services/ai-handler/src/ox_ai/inference/position_balanced_choice.py): a drop-in Concordia-shaped **choice-only** model adapter for exactly three immutable, nonempty action descriptions, each paired with a distinct stable **semantic action key**. Existing default Decider and native inference architecture remain unchanged.

For one prospective decision, preserve the identical actor-private prompt and native System One instruction across three model calls. Sort the stable semantic keys to establish a caller-order-independent canonical reference; score three cyclic permutations of those semantic options. Every action therefore appears **once in each** native A/B/C letter position, even if its order in the caller-supplied menu changes. Validate *every* native probability vector as a complete, finite, normalized distribution over exactly the offered codes; fail the entire proposal if any attempt fails.

Map each native vector back from its letter to its **stable semantic key**, average three per-option scores, select the maximal averaged probability, and resolve numerical ties within (10^{-9}) by sorted semantic key. Finally map the chosen key back to the caller's original finite menu and return exactly one caller-offered response code. No unconstrained text or world commands are permitted. In-memory result metadata explicitly counts **three real System One forwards per one proposed decision**. Any malformed or interrupted intermediate call produces no successful outcome and leaves the last-result field unset.

**This ensures invariance to changes in how the *caller* orders the three options**, because canonical scoring is defined over semantic keys. It does **not** prove immunity to how the underlying model interprets prompt phrasing, where semantics are genuinely ambiguous, or to native numerical nondeterminism. The cost is three native inference calls rather than one. It does not change whether a particular social reply is authorized by Evennia, nor does it make an acceptance inherently desirable.

## Pure-model regression gate

[Focused CI](../../.github/workflows/ox-g15-position-balance.yml) requires:
- All three options experience A, B and C positions exactly once;
- A positional-bias-only fake backend yields near-equal averaged probabilities and a stable semantic tie break;
- Semantically equivalent caller menu reorderings return **the same semantic action** even though Concordia letter labels change;
- A backend with a real semantic advantage preserves the preference after position balance;
- A malformed second native call refuses the whole action rather than falling back to a previously successful partial proposal;
- Ambiguous semantic keys or labels, unoffered codes, and unrestricted text generation are denied.

The structural CI's fake backend measures mathematical logic only. **It is not evidence of corrected native Decider character realism.** That must be separately established against real actor checkpoints and actual native score logs, ideally using G14's broader, independent scenarios and newly balanced three-position rotations. Repeated deterministic comparisons should retain option probabilities, real engine-call counts, and ideally a measured runtime cost.

## Adoption decision

Keep off the normal production path. Integrate only after live native inference confirms useful stability and after the tripled cost is budgeted against the existing nonblocking cognition scheduler, checkpoint, timeout and world-authority boundary. If average scores still encode a broad aversion to social commitment, that remains a separate behaviour-model limitation, not something position balancing alone fixes.
