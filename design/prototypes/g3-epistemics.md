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
| Unknown unknown (world-relative, **operator only**) | **Nothing.** The fact already exists in authoritative world state, but this particular actor has neither evidence nor a concrete suspicion or question identifying it | Leak the fact's identity, location, value, existence, or a suggestive question to the actor merely because the world knows it |
| Unmodeled (actor-side representation) | No proposition is recorded; this is the actor's absence of a record, not a character-facing inventory of hidden facts | Infer that the fact is false or that the actor should be prompted about it |
| Retrospective surprise (separate concept) | After encountering unexpected evidence, the actor may recognize a former gap in their model | Treat surprise/discovery as a prerequisite for the hidden world's fact to have been an unknown unknown earlier |

A stale observation becomes **historically observed**, not a reliable
present condition. Earlier conflicting observations remain in bounded
provenance history. An authenticated contrary observation may refute an
earlier belief; the belief remains inspectable as *refuted*, never magically
becomes an observation.

### Actor-relative versus world-relative epistemics

**Unknown unknowns already exist before discovery.** They are hidden *from
the character*, not necessarily hidden from the **simulation**. Evennia
may authoritatively know that a pirate is waiting behind a moon while Lin
has no reason to suspect that specific ship. That pirate is an **unknown
unknown to Lin right now**. It might remain undiscovered indefinitely;
the classification does not depend on future revelation.

An ordinary character's own private ledger can distinguish what it
observed, what it believes, and what specific questions it has posed.
It **cannot** list the particular facts it has not conceived of.
The world/operator can instead classify any bounded **actual world fact**
relative to a given actor, by comparing authoritative world state with
that character's private knowledge and the evidence disclosed to that
character. In our mostly closed ship simulation this relationship is
often systemically identifiable.

Scope is proposition-specific: knowing that the far side of the moon
is unexplored is a **known unknown** concerning geography, but it does
**not** magically make the pirate's particular existence, location, or
intentions a known unknown. Those remain unknown unknowns unless some
concrete evidence, relevant hypothesis, or question gives the character
reason to represent them.

The game is under no obligation to reveal such a fact on a schedule. The
pirate can act in the world without entering Lin's mind. Only an
actor-authorized observation, genuinely addressed message, or other
in-world discovery channel may create knowledge, questions or beliefs
about it. Hidden world facts must not appear in character prompts,
memory summaries, GOAP affordances, event feeds, action menus, or
unsanctioned debug output.

A **retrospective surprise** is different: it is an optional later
record that the character encountered something outside their prior
model. It is *not* the definition of an unknown unknown. Not every
unknown unknown is discovered, and not every discovery is surprising.

### Operator-side classifier (not an actor tool)

`game/world/epistemic_audit.py` implements a pure diagnostic comparison.
The operator supplies one **existing authoritative world proposition**,
one correctly identified character-private epistemic snapshot, the
world time and whether the world actually disclosed that fact's evidence
to the character. The result can distinguish `known_known`,
`known_unknown`, `unknown_unknown`, `modeled_belief`,
`mistaken_observation` and `exposed_unassimilated`. This does **not**
build a global secret-fact index or provide a world-state interface
to the handler. It is not registered with any character command or
agent cognition tool.

A correct guess remains a belief until verified. A false current
observation is flagged as a discrepancy, not a known known. A stale
observation means the actor once knew something about the topic but
its current answer is a known unknown. If world evidence was exposed
but not ingested into the actor's ledger, the classifier flags that
inconsistency; it does not assume that an unprocessed observation was
never delivered.

The diagnostic classification is **operator privilege**, never an
observation sent to the character.

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

This initial ledger has since been combined with real serialised cargo
items and world-authenticated interdepartmental supply operations in
G3b/c (PRs #39–40). Their recipient-private messages remain evidence of
*what was communicated*, not omniscient proof of hidden inventory or
remote dangers. Later skill-by-use observations belong to actors with
verifiable participation, not job-template magic.

[Actor-side tests](../../services/ai-handler/tests/test_epistemics.py)
cover open-world absence, belief independence, known unknowns, expiring
observations, cross-character checkpoint isolation, and retrospective
surprise. [World-side operator tests](../../game/world/tests/test_epistemic_audit.py)
use an already-existing hidden pirate behind a moon to verify that the
simulation classifies an unknown unknown **before discovery**, without
writing, returning, or hinting that fact into the actor's memory.
