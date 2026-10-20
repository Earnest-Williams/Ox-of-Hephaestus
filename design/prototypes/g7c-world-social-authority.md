# G7b closure — Persistent social authority

The previous G7b GOAP domain exercised social actions against an **offline**
`ContractBoard`. This change gives ordinary, authenticated Evennia characters
an authoritative agreement and obligation ledger. The ship's engineering
architecture remains entirely outside the experiment.

## Source of truth

- `SocialAgreement` stores both verified character dbrefs, the **current
  versioned terms**, counteroffer direction, original promisor, deadline,
  state, and independent consideration/performance receipt references.
- `SocialAgreementEvent` preserves every public revision and lifecycle
  transition. Both parties receive separate durable addressed `CrewEvent`s,
  accessible after lost ACKs through the existing `oxinbox` cursor.
- `SocialEvidence` consumes a successful existing `WorkReceipt` at most once
  and binds it to one specific agreement and obligation side.
- Every social mutation travels through `oxwork <32hex> social_<verb> social
  <base64url-json>` with typed, bounded arguments. Its receipt is an ordinary
  globally idempotent `WorkReceipt`, not a handler-side assertion. The world
  locks actors/agreement rows and checks every transition transactionally.
- `oxsocialstatus <32hex>` is a party-only read via the ordinary Evennia
  character command; nonparticipants cannot distinguish nonexistent from
  inaccessible agreements.

### States, not merely dialogue

A proposal is *pending*; a counter increments the revision and requires fresh
acceptance; rejection/deferral/expiration terminate a pending version.
Acceptance does not mark either obligation completed. Either party can
withdraw before physical performance. A withdrawal **after payment but before
performance** retains the paid consideration and marks a breach rather than
retroactively pretending no promise or payment existed.

Physical `social_perform` actions are real authenticated, co-located game
transitions with atomic world events, not chat `pose` text being interpreted
as physical truth. No later touch or different activity is inferred from a
past accepted offer. Already-performed acts cannot be undone by a withdrawal.

An `information` consideration can be marked delivered only by an addressed,
world-recorded disclosure from the party who promised it. This certifies the
*delivery of words*, **not** their truth. Material help or a work activity
requires terms naming the exact admissible world `target`/`operation`, a
successful receipt by the responsible actor **after agreement**, and a
one-time evidence link. A promise of a shift swap, future favor, information,
or supplies without a receipt remains **outstanding**. Other forms of material
consideration are rejected for now if the world cannot actually verify the
transfer—no phantom currency or inventory is manufactured.

At the present stage `performance_id` records one witnessed act or one
receipt-backed job. Ongoing, repeated and open-ended obligations require
future instanced milestones before individual installments can be marked
fulfilled. Their promise remains visible, not auto-completed.

## Integration with GOAP

The new `authoritative_live_trial.py` obtains independently chosen GOAP
social actions from the existing `ApartmentExpanded` minds. For all proposal,
reply, withdrawal, and physical performance actions it sends a typed `oxwork`
command through each character's ordinary authenticated client. It waits for
**both** the actor's canonical work receipt and the counterparty's addressed
observation, and only then updates an offline comparison shadow. The shadow
is checked against both a world-owned `oxsocialstatus` projection and
per-revision facts. It has no power to authorize an event.

Other speech is still transmitted through normal Evennia `say` with
confirmation on both clients. There are no hosted model calls.

## Verification and recovery

Focused G7b checks cover:

1. Unknown, unauthenticated, third-party and cross-character claims;
2. versioned counteroffers, stale revisions and bilateral acceptance;
3. exact activity, actual co-location and double-performance prevention;
4. due expiration and re-proposal for an expired pair;
5. receipt replay and request-ID collision refusal;
6. failed event writes rolling back agreement transitions;
7. information transmission order, paid-then-withdrawn breach;
8. real external work receipt provenance, post-acceptance timing and reuse;
9. game command parsing and party-scoped world status queries;
10. three GOAP-led real Evennia conversations (mutual / mismatch /
    reconsideration) using authoritative social receipts;
11. a real two-client agreement accepted before server restart and
    performed **after** restart by newly authenticated sessions.

Run the dedicated `Ox G7b social negotiation GOAP` workflow and the focused
Django suite `python -m world.test_runner world.tests.test_social_authority`
under `game/`. Do not rerun the inherited full CI matrix because of a focused
social-model fix.

The GOAP handler's original in-memory `ContractBoard` remains useful for
isolated planning comparison, but in a live world it is now a read-only
**shadow**, never the contract authority or a proof of actual work.