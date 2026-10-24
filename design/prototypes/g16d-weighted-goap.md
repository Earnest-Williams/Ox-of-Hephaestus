# G16d — disposition-weighted GOAP operator costs

**Implemented:** opt-in *mathematical/planner primitive* only. Runtime
`OX_PERSONALITY_CHOICE` integration is reserved for G16c and stays off.
No game command, native model, work receipt or real-world safety outcome is
part of this standalone planner test.

## Design

The unchanged character-owned `CrewBlueprint` projects to the same five
bounded dimensions as G16a: risk tolerance, authority deference, social
affiliation (mean agreeableness/collaboration), autonomy (authority challenge
minus collaboration), and conscientious procedure preference. These
projections are authored, not inferred psychological facts.

For a validated complete option menu in the **one G16a catalog**, all
GOAP steps must match an *exact tagged command signature*. No default
neutral tag is assumed for an unknown action. Define

`cost_new = cost_base * clamp(exp(-0.5 * (disposition dot action_tag)), 0.5, 2.0)`.

`GoapPlanner.plan(..., cost_overrides=...)` validates a complete exact
positive finite map before search. Its uniform-cost search still uses
original symbolic preconditions/effects and original GOAP action objects,
but supports positive finite fractional prices. Identical costs are
resolved deterministically by insertion order. Unflagged historical
plans and costs are unchanged.

## Restrictions

- These are subjective *planning prices*, never permission or physical
  equipment truth. The world validates any actual work independently.
- **Safety-critical menus reject disposition weighting** until an
  independently authored safety policy has been validated.
- Every planner operator, including intermediate route steps, must have
  a catalog entry. The current G16a catalog covers existing *finite
  offered menus*, not the entire multi-step vessel navigation domain;
  the latter therefore correctly fails closed rather than pretending
  all steps are neutrally tagged.
- Existing duplicate command signatures across distinct symbolic
  operators (e.g., inspection versus final verification) must get
  explicit differentiated semantic keys in a future contract revision.
  Do not silently infer tags or merge their meanings.

## Verification

Dedicated [G16d CI](../../.github/workflows/ox-g16d-weighted-goap.yml)
runs the complete model-free planner regressions plus
[test_g16_goap.py](../../services/ai-handler/tests/test_g16_goap.py):
same facts/operators/goals, but procedural and independent characters
choose different plans; costs stay positive and bounded; tie ordering
is repeatable; missing/stale actions, invalid prices, unsafe menus and
altered offers are rejected. This does **not** yet prove any native
Concordia model or live-world personality choice.

**Next:** G16c must enable both branches behind a single opt-in flag,
persist their chosen actions and draw before adopting a live proposal,
and preserve the existing independent actor/receipt boundary.
