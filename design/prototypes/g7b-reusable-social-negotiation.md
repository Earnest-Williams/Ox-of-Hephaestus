# G7b — General-purpose social GOAP and bargaining

## Objective

Expand the existing G7 apartment experiment rather than extending the ship.
GOAP chooses actions, not just dialogue. New reusable packages:
- services/ai-handler/src/ox_ai/social/domain.py — 75 typed actions covering contact, emotion, limits, reciprocity, bargaining, cooperation and non-explicit physical proximity.
- services/ai-handler/src/ox_ai/social/contracts.py — 36 negotiable activities with typed scope, consideration, ordering, counteroffer revisions, independent assent, revocation, and separately verified performance.
- services/ai-handler/src/ox_ai/scenarios/apartment_extended.py — scenario adapter with independent GOAP minds, private motives, emotional updates, and an explicitly disposable simulated world.

The same bargaining vocabulary accommodates hand-holding, a kiss, staying
overnight, assistance, information, resources, a shift swap or confidentiality.
A contract is *not* a statement of attraction and an accepted promise is
*not* world-verified work. The world never sees an actor's private utility.

## Planning and authority

Each actor privately evaluates competing goals and lets the EXISTING
GoapPlanner find feasible multi-step actions from its own beliefs. A
planner's predicted effect cannot replace an authoritative observation.
Only the next action is attempted, and each observed response may change
subsequent priorities.

Negotiation is typed: propose exact terms, ask, counter, accept, defer,
decline, withdraw, or fulfill. Countering changes the revision and next
addressee but **not who owes consideration**. Both sides must assent to
one exact current revision. A promise to exchange something first must
be *fulfilled first*, with a separate world receipt, before the requested
activity is permitted. Parties may later change their minds before a
physical act without retroactively rewriting earlier events.

Internal drives distinguish affection, curiosity, companionship,
pragmatism, reciprocity, duty, social expectation, anxiety, patience
and caution. Trust, hope, comfort, uncertainty, resentment, and fatigue
change through observed interactions and recipient-private new evidence.
A person can agree for instrumental or obligation reasons despite weak
affection; agreements never create an affection fact by themselves.

## Reproducible comparison

Local deterministic zero-model experiments (all tests passed before PR):

| Initial case | Turns | Counters | Agreements | Act performed | Main observation |
| --- | ---: | ---: | ---: | ---: | --- |
| Mutual | 13 | 0 | 3 | 1 | Agreed closeness performed |
| Cautious | 19 | 2 | 3 | 1 | Hesitation, negotiated scope and acknowledged pace |
| Instrumental | 18 | 3 | 2 | 1 | Low desire; information delivered before agreed hand-holding |
| Mismatch | 10 | 0 | 0 | 0 | Refusal without repeated solicitation |
| Obligation | 12 | 0 | 2 | 0 | Positive decisions with duty/social pressure distinct from attraction |
| Work trade | 12 | 0 | 3 | 0 | Shift, investigation, help promised without inventing completion |
| Reconsider | 12 | 0 | 1 | 0 | New private evidence leads to withdrawal before touch |

Use:

    python -m unittest discover -s services/ai-handler/tests -p test_social_expanded.py -v
    python -m ox_ai.scenarios.apartment_extended --variant instrumental --turn-cap 64

A focused G7b workflow compares all seven variants and starts a disposable
Evennia apartment with TWO independent ordinary authenticated clients.
It performs three live zero-consideration cases (mutual, mismatch,
reconsider) via normal say/pose commands, confirming that both actual
characters saw each utterance before updating GOAP.

## Persistent Evennia integration

The original in-memory ContractBoard remains a GOAP comparison model. The
actual game now owns persistent, authenticated, versioned social agreements
and separate consideration and performance receipts in its world database.

The new G7b authoritative runner sends GOAP-selected proposals, replies,
withdrawals and agreed physical interactions as typed ordinary world work.
Only after the world returns its durable receipt AND delivers the counterpart's
private observation may the local planning shadow advance. It verifies each
subsequent world snapshot against that comparison shadow.

See [World-owned social authority](g7c-world-social-authority.md) for exact
terms, provenance, work evidence, transaction boundaries, accepted-but-unfilled
obligations, and recovery across a real game-server restart.

## Still beyond this milestone

- Ongoing and repeated payment/performance installments, verified cash or
  inventory transfer without a corresponding real game operation.
- Free-text dialogue understanding and long-term emotional memory.
- Physics-backed contact: performed interactions are world-owned witnessed
  social events, not literal anatomical/positional simulations.
- A promise never proves desire and an accepted obligation never proves
  it has been fulfilled.

