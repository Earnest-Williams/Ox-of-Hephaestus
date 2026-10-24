# G16e — preregistered native character disposition experiment

**State:** **protocol frozen before the first G16e native inference**.
This is not a passed test, a working production character policy,
or an endorsement of the frozen parameters. The machine-readable
[preregistration](g16e-preregistration-v1.json) lists all eight case
definitions, arms, model-call ceiling and acceptance thresholds.
No result should be edited into the preregistration after execution.

## Purpose

[G13](g13-experimental-results.md) and [both G14 v2 native runs](g14-experimental-results.md)
showed that merely describing personality to Decider caused few semantic
choice changes. [G16b](g16b-native-margin-calibration.md) already froze
`gain=0.10`, `max_shift=0.21`, base temperature `0.33`,
urgent temperature `0.11`, individual temperature formula and
`evidence_lock=0.85` **without seeing G16e holdout outcomes**.

G16e must measure whether explicit disposition adjustment differentiates
same-evidence procedural versus independent characters in believable,
non-safety choices while retaining bounded, reproducible and actor-scoped
outcomes. Increasing arbitrary disagreement is **not** sufficient to
claim personality realism or operational competence.

## Experimental unit and provenance

Use the six exact G9 authentic actor-private brain snapshots from
[successful source run #39872687597](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39872687597):
Ari, Captain, Iona, Lin, Mara and Teo. Restore each snapshot independently
with its original identity, world evidence, episodic memories, authorized
private state and cognition revision. Use the reviewed G13
`isolated_snapshot` mechanism to cross procedural versus independent
trait interventions **without changing the brain's evidence or other
components**. Never combine histories from different characters.

The four G14 menus keep the **same immutable G16a authored tags**.
Four additional non-safety situations are preregistered, using exactly
those menus instead of inventing a second tag catalog. Their full
scenario narratives and menu-key assignments are in the JSON record.

| Scenario class | Cases | Purpose |
| --- | ---: | --- |
| Original G14 hypotheticals | 4 | Reuse published evidence protocol, including one safety-critical spare |
| Additional peer-help conflicts | 2 | Autonomy, cooperation and strained expectations, all permissible |
| Additional approved-watch conflict | 1 | Reciprocal help versus personal inconvenience |
| Additional private-apology conflict | 1 | Reconciliation versus autonomous boundaries |
| **Total** | **8** | Four genuinely new, preregistered scene texts |

The four *new* scenes must each yield a median **native** top-two
position-balanced margin below 0.30 across matched actor/trait conditions
to qualify as non-ceiling. Otherwise report the preregistered
non-ceiling gate as **failed** rather than substituting easier cases
after seeing the outcome. Record raw winner and three-score margins
regardless of whether their adjusted action changes.

## Native inference and control design

Each actor sees all eight cases under both procedural and independent
traits. Each matched case/profile is presented in three **caller**
menu orders (canonical/cycle left/cycle right); within each order,
G15 scores three **native** code rotations. The actor-private scene
prompt outside the supplied case/profile treatment must be held fixed,
and G16c canonicalizes the outer Concordia finite-menu order before
scoring. This is 6 actors × 8 scenes × 2 profiles × 3 caller orders ×
3 genuine native forwards = **864 forwards**.

A separate unchanged-input repeat of each of the four original G14
cases on each actor adds 24 × 3 = **72 native forwards**. Total
planned native calls: **936**, or **156 per actor**. Do not count one
Concordia sample-choice request as one underlying Decider call.
No other model, hosted provider, generated explanation or Evennia
world command is part of the experiment.

The **raw** arm uses the native position-balanced semantic argmax.
The **adjusted** arm uses the *same recorded three native probabilities*
with the frozen explicit disposition/tag scores, bounded shift,
character temperature and BLAKE2b draw. This avoids rerunning the model
in a second arm and confounding differences with new inference noise.
All raw probabilities, shifts, adjusted probabilities, actor/scenario
IDs, catalog SHA, actual prompt digest, result and draw must be archived
in the independent per-actor artifacts.

For profile comparisons, keep the stable draw keyed to actor identity
and *scenario boundary*, **not** to menu order or profile treatment;
otherwise apparent personality differences may reflect different random
draws rather than different dispositions. Separately measure
between-run score variation rather than treating repeat success within
one run as a universal determinism guarantee.

## Frozen acceptance rules

1. Among the **42 unique actor × non-safety scenario pairs** (six
   characters × seven non-safety scenes), adjusted procedural versus
   independent selections must disagree in **at least 11 pairs**
   (≥25%). The raw scorer's disagreement rate is separately reported;
   roughly 5% is a historical reference, not a hard equality
   requirement. Repeated caller orders must not inflate this denominator.
2. **Zero personality overrides** in strong-evidence safety-locked
   cases. In unlocked safety-critical cases, report explicit **refusal**
   rather than hiding an unsafe random choice. Also include a synthetic
   high-native-confidence lock control so zero observed native locks
   cannot make this assertion vacuous.
3. **100% caller-order semantic invariance** within every
   actor/scenario/profile comparison, including any safety refusals.
   The full outer actor prompt and three inner native rotations must be
   checked rather than assuming invariance from the source-code design.
4. **24/24 unchanged-input repeats** must make identical selections
   with unchanged prompt digest. Report native score differences
   separately, with at least the historical within-0.01 check.
5. Require **zero** unauthorized actions, world commands, foreign
   observations, actor crossovers, changes to original G9 private
   evidence or unsupported completions. The native model never
   authorizes a physical or social world outcome.
6. Archive the *entire* factorial and repeat data, including failed
   and unpopular outcomes. Do not filter cases, tune gains on this
   holdout or change the thresholds and then relabel the same run as
   preregistered success.

## Post-experiment decisions

Any failed hard criterion keeps `OX_PERSONALITY_CHOICE` disabled and
requires a new, explicitly versioned protocol before further testing.
Passing G16e would establish only the specified *native model
behavioural comparison*, **not** authentic 40-actor scheduler throughput,
dialogue quality, the position-balanced Qwen-versus-Decider clean
comparison, or live supervisor recovery. Those remain independent
G16f, G16g and final adoption gates.

Engineering verisimilitude, durable world consequences and character
individuality are the design objectives, not certification as a real
spacecraft or universal psychological truth.

## Immutable experiment provenance

The preregistration's exact Git blob identity is `e8529be931bebb6cda5c00fab90458cf5ef52a3c`.
The native runner refuses any changed manifest bytes, verifies the
GGUF's complete SHA-256 against the six-shard model-provisioning
manifest, and records the publisher tokenizer revision and weight
revision. The aggregator requires the identical GGUF hash in all six
actor outputs. Each of the 936 underlying System One forwards must
produce a raw response-code probability vector, its code-to-semantic
mapping, all three source menu positions and a prompt digest; the
aggregator reconstructs the balanced arithmetic means independently.
The native original-text prompts and memories stay private.
