# G14 — Factor numerical vs descriptive personality conditioning against meaningful choices

**Status:** initial native experiment completed 23 October 2026 ([Actions run #39996157362](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39996157362)), but its three orders were not position-counterbalanced. Preserve those observations as historical protocol-v1 evidence; see [G14 experimental results](g14-experimental-results.md). Protocol v2 uses cyclic position-balanced options and stronger fail-closed validations. Do not conflate original run with a subsequent v2 run.

## Motivation: what G13 actually found

[G13's complete matched-evidence experiment](g13-experimental-results.md) made 240 real Decider 4B Q4_K_M calls, with all six original G9 actor-private histories held fixed inside each actor's three personality arms. In its hypothetical **accept / defer / decline** menus, it produced **zero accepts**, only 4/72 procedural-vs-original and 7/72 independent-vs-original action changes, and substantial option-order sensitivity (37/72 three-way order-invariant combinations). The independent trait intervention changed mean native decline probability only +1.10 percentage points, while the separate consultation router's configured probabilities changed dramatically.

That result does not tell us whether (a) numerical trait vectors are insufficiently legible to the model, (b) abstract commitment framing encourages deferral, or (c) the model naturally discounts private history and stable dispositions relative to a local task. G14 tests (a) and a controlled part of (b) without selecting scenarios until their answers look interesting.

## Four preregistered counterfactual treatments

Use all **six exact authenticated G9 205-turn actor brains**, identified by the existing source digest and per-actor snapshot SHA-256. Within each actor, every test shares the **same original world history, private temporal memories, observations, identity, counterpart, and other Concordia state**.

| Arm | Psychological traits | Read-only CharacterProfile |
| --- | --- | --- |
| numeric_original | Historical G9 original | Current canonical numeric profile |
| numeric_independent | Same six high-risk / high-authority / autonomy intervention values as G13 | Canonical numeric profile |
| prose_original | Historical G9 original | Qualitative interpretation of six selected traits |
| prose_independent | Same independent intervention | Qualitative interpretation of those six traits |

The other **six untouched psychological dimensions, all aptitudes, starting skills, history, style, authorization disclaimer and private memory** remain present. The alternative prose is derived mechanically from trait magnitudes; it does not name case-specific actions, instruct the character to be daring, grant authority, or encode an expected response. Each profile transformation is round-trip checked against the original, and a within-actor, within-case **hash of the actual native inference prompt with only the profile span normalized** must be identical across all four treatments. Replacing the read-only characterization is a **prompt-presentation treatment**, not a factual world event.

### Meaningful, authored scenarios

All four are explicit **hypotheticals**, not world invitations or authorized work:

1. **Verified mutual aid:** a competent colleague offers a harmless review of ordinary notes (accept available help / work alone / reschedule).
2. **Scarce life-support cartridge:** a colleague requests the last spare for nonurgent work (reserve / support lending / request authorized arbitration).
3. **Approved watch relief:** two qualified crew may exchange an authorized shift at mild personal cost (cover / retain existing watch / offer another favor).
4. **Uncertain apology:** a peer offers private reconciliation after a minor conflict (accept conversation / decline / postpone).

The alternatives are valid *considerations*, never executable world commands. A real symbolic GOAP planning baseline is evaluated for each case to identify a procedural reference, but the native Decider is intentionally invoked for every arm; routing propensity is not treated as the observed action. No option is marked the required native answer. In particular, the experiment does **not** demand more acceptances or more deviations in order to pass.

## Coverage, controls and interpretation

Six actors × four cases × three cyclic, position-balanced semantic menu-order permutations × four profile arms = **288 native scored decisions**, plus **24 independent unchanged-input repeat controls**, for **312 calls per complete native Decider 4B Q4_K_M run**. Every paired group must preserve identical non-profile prompt hash, evidence digest and offered option semantics; every semantic option must occupy each of the three display positions, and each repeat must match its baseline prompt hash and offered menu; per-case outcomes and native scored probabilities are retained with semantic action labels, not display letters.

The separate six-shard aggregate rejects any missing actor, omitted/replayed treatment, mocked backend, altered evidence, invalid numeric score, or failed repeat provenance. It reports:

- Trait effect **within numeric presentation**, and trait effect **within prose presentation**;
- Format effect **within original**, and format effect **within independent** personality;
- Full native choice and probability distributions by case and treatment;
- Menu-order invariance and index preferences in every arm;
- Repeat consistency, without mistaking deterministic same-input reruns for order robustness.

**Interpretation threshold:** a model that produces the same answer in every arm, fails a menu-order control, or exhibits no additional personality differentiation will still pass an honest experiment if the records are complete and valid. Declines, unusual favors or support for scarcity risks are not automatically faults or desirable storyline; there are no authoritative consequences in this study.

## Running it

Use the opt-in [G14 GitHub Actions workflow](../../.github/workflows/ox-g14-profile-salience.yml). The workflow reuses the verified G9 artifact and the same pinned Decider Q4_K_M GGUF source and publisher tokenizer as G10/G13; no hosted model comparison is introduced. Only bounded action decisions, scores and prompt digests are archived; the private brain checkpoint and GGUF are never uploaded. The experiment does not enable the production supervisor or alter existing G11 world-authority code.
