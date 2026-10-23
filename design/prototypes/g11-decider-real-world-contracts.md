# G11 — Decider personality creates real, receipted social consequences

## Motivation and outcome definition

The previous G9 trial showed meaningful personality-weighted GOAP consultation
and character-specific sensitivity to memories accumulated over 205 actual
Evennia turns. Its selected Decider *dialogue intentions* were genuinely heard,
but it did not itself choose whether an in-world relationship commitment was
accepted or declined.

G11 makes that next transition deliberately narrow and reversible:
**only an actual, actor-addressed, pending world relationship offer** may be
accepted, deferred or declined by the next selected decision. The model never
creates its own world permissions or changes Evennia state without an
authenticated request and validated receipt.

This is NOT a romance chatbot and it does not generate conversational text.
Decider 4B Q4_K_M remains the sole selected local finite-action model.
The existing multi-turn social situation (and its tension, jealousy and
misunderstandings) has been inherited from G8/G9.

## Precisely what changes

The original G8 deterministic social-reply heuristic remains the symbolic
GOAP baseline. A real, validated pending agreement becomes a new explicit,
actor-bound routing boundary. The existing personality-based router freezes
the GOAP-vs-Decider draw in the persistent per-character checkpoint before
any model inference. GOAP returns its one real symbolic planned response;
Decider, if chosen, scores only these options:

- Accept the existing pending commitment
- Defer the commitment
- Decline the commitment

The model's proposal remains nonauthoritative. It is submitted through
the existing authenticated Evennia social_reply operation and its durable
request ID. **Only a successful world work receipt and a matching
recipient-addressed social event** authorize recording a successful
decision or changing the experiment's relationship state. For a
Decider-sourced proposal the agent's pending request is acknowledged only
after those world verifications. A missing confirmation is not silently
converted to a success; checkpoint recovery from an in-flight unverified
decision fails closed.

The G8 500-turn symbolic and G9 205-turn dialogue experiments remain
unchanged by default. A separate opt-in contract-routing flag, saved in
the trial checkpoint, prevents accidentally changing actor authority
when recovering from a different mode.

## Three-world breadth

CI runs **three independent 205-turn Evennia trials** using seeds
241, 619 and 1009, with new six-character worlds per job. That is
**615 authenticated character decisions**, three opportunities for
different relationships and model-vs-GOAP routing histories,
six operator-injected real equipment faults, and 15 separately
authenticated physical maintenance work receipts (five per world).

Each world independently verifies all six authenticated characters,
observed speech deliveries, cross-actor memory provenance and
authentic physical recovery, using the existing G9 verifier.
G11 adds agreement ownership, the pending offer, per-decision route
choice, selected response, model-call accounting, individual world
operation receipt IDs and matching recipient event IDs. G11's separate
cross-seed aggregator rejects incomplete or selectively reported runs.

**No expected social answer is programmed as a pass condition.** The
outcome may be a change or no change from GOAP, and acceptance,
deferral and rejection are all legally available world actions. Actual
story-relevant significance must be assessed in the evolving
relationships, not equated with an arbitrary count of deviations.

## Limitations

G11 is still an experimental six-crew scenario with authored initial
histories and a finite relationship domain; its resulting world replies,
belief changes and memories are authentic *within that simulation*.
The model cannot directly improvise an unapproved world operation,
rewrite a physical fault, or issue out-of-schema text. This experiment
does not enable the production supervisor. The existing 500-turn G8
baseline and full project CI are separately required before merging.
