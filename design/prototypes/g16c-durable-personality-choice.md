# G16c — opt-in, checkpoint-before-adoption personality choice

**Experimental implementation only.** `OX_PERSONALITY_CHOICE=0`
(default/unset) preserves the existing routed GOAP/Concordia branch unchanged.
Only the exact opt-in value `1` activates the separate G16c/d adapter,
and only when `CharacterRouteController.decide(..., menu_key=...)`
receives a validated **G16a authored menu**. Any unknown flag value
or missing menu fails closed. No production supervisor sets this flag.

## Deliberate choice

A per-boundary `PersonalityAdjustedDeciderChoiceModel` reuses G15's
three complete native Decider Q4_K_M forwards. Stable semantic-key
rotations give each authored option each code position once; the three
mapped native probabilities are averaged before selecting. The frozen
G16b policy adjusts each log-probability by a capped `gain=0.10`
five-trait dot product (`max_shift=0.21`), uses the preregistered
per-character `0.20..0.45` temperature (base 0.33), and draws
deterministically using actor/boundary/seed-bound BLAKE2b. Urgent
non-safety decisions use temperature 0.11. Native scores are **not**
calibrated safety correctness probabilities.

For a `safety_critical` menu, if the native top semantic probability
is at least `0.85`, personality shifts are **zero and the native
argmax is forced** (no stochastic override). Otherwise that choice
**refuses** with no proposed action: there is no invented safety
fallback. This policy is intentionally conservative and must receive
separate G16e world-authority and safety evaluation. Even a locked
choice is only a **proposal**: Evennia still checks real role, location,
qualifications, equipment and receipts.

## Persistence and concurrency

An unchanged `PersonalityRouter` first durably records which branch
the character consults. A detached Concordia shadow then obtains the
finite-choice decision (three actual native forwards). The event-loop
owner validates revisions and the offered command against the G16a
catalog, then appends a bounded actor-specific `personality_choices`
entry to the existing private router record and calls the caller's
durable `persist` callback **before** adopting the draft into the live
CrewAgent pending-request ledger. The score record includes raw native
semantic scores, precise shifts, adjusted probabilities, temperature,
BLAKE2b draw, forced safety lock, selected semantic key, original prompt
SHA-256, native call count, actor/revisions, model tag snapshot/catalog
SHA-256, original route and deterministic request ID.

On a crash after ledger commit but before proposal adoption, the saved
choice is re-presented to an isolated Concordia shadow, and its new
prompt **must** hash to the identical value before adopting the exact
original request ID. No new native calls or reroll are allowed. If the
live agent already has the identical pending request, replay returns
it rather than submitting another. Stale cognition, foreign actors,
changed menus/catalog fingerprints and corrupt saved probabilities
fail closed. A durable persist error rolls back the choice entry and
cannot adopt the detached proposal. DecisionScheduler counts each
three-pass call against **three** inference budget units, not one.
No model worker may write the ledger or world.

## GOAP habit branch

The same explicit catalog-derived G16d weights change the complete
valid planner model's operator costs while keeping symbolically
valid plans, finite positive costs and stable search ordering. A GOAP
choice and its original request ID are durably recorded **before**
creating the handler ActionRequest. Replays return the recorded
operator and request rather than repricing from newly changed inputs.
Unsafe/untagged planner domains refuse; the existing multi-step ship
navigation model is not yet fully tagged and therefore is **not**
silently declared personality-enabled.

## Limits and tests

[Dedicated G16c CI](../../.github/workflows/ox-g16c-durable-choice.yml)
uses the real pinned Concordia actor/scheduler with a deliberately
fake, deterministic three-pass System One engine to verify **integration,
not model behavioural quality**: semantic permutation invariance,
separated psychological profiles, immutable original menu, replay,
stale evidence and checkpoint rollback, budget accounting and safety
locks. It also runs the existing routing, scheduler and GOAP suites.
No actual Decider GGUF is downloaded by this structural CI.

**Not adoption evidence:** this is not G16e's six native G9 actor study,
not a 6/20/40 throughput measurement, not real-world equipment work and
not a supervisor soak. Those gates remain mandatory before setting the
flag in an authenticated live service.
