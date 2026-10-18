# G3 epistemics: what each crew member knows, believes, and has not asked

**Design invariant:** an actor's knowledge is not the world's complete truth.
Evennia alone owns current physical state. An agent has *observations*
from its own verified local instruments, *reports/events* addressed to it,
*beliefs* it infers, and *questions* it knows remain unanswered. None can
create permission or a physical item.

## Formal distinctions

| Classification | What the character may assert | Not allowed |
| --- | --- | --- |
| Observed (known known in a bounded sense) | At game time T, source S gave value V to this authenticated body; use as current only within its declared freshness horizon | Assume the value remains true forever or that another room has the same state |
| Believed | Actor hypothesizes V on stated basis B with confidence C, possibly wrong, even C=1 | Upgrade belief to observed without fresh world evidence |
| Known unknown | Character has explicitly recorded a question, with rationale, whose answer is not verified now | Treat missing value as false, zero, or necessarily absent |
| Unmodeled | The proposition or even the domain has not been considered | Pretend to enumerate what the actor does not know it does not know |
| Retrospective surprise | After a new world-observed fact, recognize that this category was absent from the prior model and no question predicted it | Claim the unknown unknown was known before discovery |

A stale observation becomes **historically observed**, not a reliable
present condition. Earlier conflicting observations remain in bounded
provenance history. An authenticated contrary observation may refute an
earlier belief; the belief remains inspectable as *refuted*, never magically
becomes an observation.

The operative Rumsfeld distinction is epistemic, not an invented finite
list of all possible uncertainties. **Unknown unknowns cannot be enumerated
in advance**. We represent model incompleteness by an open-world policy
and recognize certain surprises **only after** a verified unpredicted fact
is encountered. Ordinary unfamiliar observations are not necessarily
surprises.

## World trust and privacy

Each persistent AgentEpistemics ledger is bound to an Ox crew role AND
character DBref, stored independently in the handler's supervisor state.
All five character minds receive only their own addressed event identities;
the event's receipt is verified, but another person's text is at most
testimony, **not** automatically true physical telemetry.

Only a trusted local sensor or world receipt may call observe_verified;
model output, testimony and non-authoritative reasoning use believe or ask.
Entries have source kind, evidence ID, game time and explicit freshness
duration. Evidence is not shared from another crew member's checkpoint.
Records are bounded, versioned, replay-idempotent and reject foreign
identities or colliding evidence IDs.

For the first integration, Teo asks about local A-01 cartridges when an
alarm creates work. The existing real local equipment readout supplies an
observed count. If that count is zero, Teo records the further *known
unknown* of when any resupply may actually occur. Mere cargo rumors or
an anticipated handoff cannot upgrade this to known available stock.
The existing world-owned work receipts still decide whether work happened.

## Next world systems

This ledger is the **first slice** of G3, not a complete inventory or
interdepartmental work-order system. The next PRs implement game-owned
item lots, actual location/carrier transfers with global idempotent
receipts, and world-assigned cross-department work orders whose
notifications are recipient-specific evidence rather than psychic shared
state. Later skill-by-use observations belong to actors with verifiable
participation, not job-template magic.

[Tests](../../services/ai-handler/tests/test_epistemics.py) cover open-world
absence, belief independence, known unknowns, expiring observations,
contradiction/refutation, cross-character checkpoint refusal, replay and
retrospective surprise.
