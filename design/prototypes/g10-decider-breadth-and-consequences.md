# G10 — Broad choice-space and character-sensitivity experiment

## Fixed constraints

The local decision model remains **Decider 4B Q4_K_M**. Never reopen
model selection or use Qwen for the decision head. Real Evennia remains the
sole authority for equipment and relationship state. No experiment gives an
unverified model choice the ability to issue world commands.

G9 ([merged PR #103](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/103))
demonstrated 205 real six-character turns, 12 live bounded Decider
social decisions, 74 source-attributed remembered observations used at
decision boundaries, two completed real equipment fault recoveries, and
3 of 6 counterfactual replays changing when independently witnessed
indexed private memory was disabled. That was meaningful but narrow:
Decider disproportionately picked *reflect* or *reassure* in a seven-option
conversation menu.

G10 challenges the resulting actor minds with **consequential planning
alternatives, rather than only spoken dialogue styles**. It deliberately
does **not** imply the hypothetical incidents happened aboard the ship.

## Factorial test design

Full **6 x 6 x 3 x 2 = 216 real native Decider choices** across:

- All six independently saved G9 crew: Lin, Ari, Iona, Mara, Teo, Captain.
- Six planning situations: truthful cargo paperwork after repair; a
  hypothetical fresh scrubber alarm; conflicting testimony; an authorized
  watch swap; limited life-support spares; an exhausted watchkeeper.
- Three option positions: canonical, reversed, and cyclic rotated.
- Two private memory projection arms: on and off, preserving every
  underlying G9 native observation, persona, personality and existing
  private memory bank in both arms. Only the read-only indexed Ox prompt
  projection is ablated.

Each alternative is a bounded *propose.<approach>* to a fictional
G10 planning target, **not** a real Evennia command. The baseline action
comes from a real symbolic GoapPlanner with explicit preconditions and
effects; GOAP never asserts hypothetical effects were observed.
The model itself scores native finite option letters; no language-generation
rationale and no hand-picked correct answer.

A further **9,216 deterministic personality-routing boundary draws**
(256 for each of 36 actor/situation cells) test the configured GOAP/Decider
consultation policy independently of observed model choices. Route
frequency is not confused with behavioural correctness.

## Authentic evidence provenance

Source is [G9 Actions run #39872687597](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39872687597).
Its state, full world-proof report, and each of the six private actor
checkpoints are SHA-256 pinned in g10_decider_battery.py. Import rejects
any changed byte, pending physical proposal, incorrect actor profile,
changed bounded recent-observation window, or incomplete voyage proof.
The runner does not publish private G9 snapshots, prompts or the GGUF.

The experiment is parallelized into six per-person CI jobs, each running
36 real Decider selections, a separate deterministic fixture, selected
existing G9 and personality regression tests, and independently
pinned model/tokenizer provisioning. A seventh job collects all six reports
and fails if any arm, identity, native score or world-isolation claim
is missing. The experiment archives actual *observations*, including failures,
not a chosen subset.

## Judging evidence

Report the *complete* distribution, not only positive anecdotes:

- Whether traits affect the **rate of consultation** differently from
  GOAP baseline choice content.
- Different actions for the same person with and without acquired private
  memory; count every one of the 108 matched pair comparisons.
- Invariance across option order; count the 72 within-person case/treatment
  combinations (three orderings each), and explicitly flag position bias.
- Cases where a model-selected proposal implies ignoring procedure,
  concealing records, or taking unauthorized action. These are **hypothetical
  unsafe intentions**; no actual incident or world effect occurs.
- Whether individual characters consistently make distinguishable,
  potentially coherent choices or all collapse to one safe-sounding option.
- Native Decider probability differences and actual chosen action;
  model confidence is not calibrated by the native option scores.

Do not define success as high error rate. Some characters should follow
GOAP often, and a human-like character can make a sensible choice.
A mistake must be connected to their specific situation/interpretation
and subsequently judged against actual observed consequences if ever
tested in a real world branch.

### Limitations

G10 situations are *authored hypothetical briefs* delivered only as
transient decision-context text, not new world events. The personal
histories were naturally accumulated through a staged G9 voyage, but
the new hypotheticals are not independent shipboard incidents. This
assay measures counterfactual sensitivity and option-menu behaviour,
not causal psychological validity or live operational recovery. Unsafe
world requests are never submitted. The reference G9 Actions evidence
artifact expires after its retention window; this expensive one-shot
assay is for immediate experimental evaluation, not a perpetually reliable
CI test dependent on ephemeral archive retrieval.

The next genuine world-level experiment must connect model-chosen
*permitted* actions to observed incidents and their actual consequences,
with no silent fallback or false receipt.
