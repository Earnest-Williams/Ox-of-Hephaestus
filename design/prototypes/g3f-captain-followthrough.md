# G3f — Sixth crew: captain, competencies and unresolved command obligations

**Implementation PR:** [#54](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/54).
**Status:** experimental until a final-head six-client CI run and world gate succeed.

## Why add a captain?

Lin remains the bridge *watch officer*: receiving reports, drawing tentative
diagnostic conclusions, and relaying operations telemetry. The new captain
is a separate, independently authenticated person in the existing Bridge
compartment. Their obligation is not to be the cleverest diagnostician. It is
to keep the ship working an **unresolved problem** even when technicians disagree,
have no confident explanation, refuse an assignment, or cannot proceed.

A captain's authority is about **accountability and prioritisation**, not
forcing a medical/scientific conclusion, impersonating an engineer, or
magically changing equipment state. Crew still control their own observations
and may legitimately decline dangerous work.

## First command loop

1. **Authoritative ticket.** Evennia opens `CaptainObligation` for an
   atmospheric scrubber A-01 alarm (priority 100) or for the genuinely uncertain
   analyzer case (priority 70). The private case cause never appears in the
   captain's notification. Tickets are kept in the world DB, not model memory.
2. **Claim.** Only the world-designated Captain character may acknowledge
   responsibility. An acknowledgement does **not** mark the ticket resolved.
3. **Delegate.** The captain chooses a specialist from a bounded, qualified
   list. The ordinary global durable work ledger verifies the command,
   records an order ID, and delivers a recipient-specific assignment to
   the actual crew character. Competing theories do not veto further work.
4. **Respond.** The specialist independently chooses to accept, decline or
   report themselves blocked. This is a legitimate independent decision;
   no captain instruction overrides location, equipment interlocks or
   safety/role restrictions.
5. **Obtain verified work.** If assigned to the analyzer question, a specialist
   must *actually* sample at their station, file a firsthand report,
   register a local follow-up question, sample again and file a second
   world-receipted measurement. The captain learns that a verified report
   exists without receiving the specialist's private deliberations. A
   previously completed test cannot be recycled as evidence of new work.
   For an A-01 alarm, the existing Teo maintenance pipeline retains
   responsibility for physically safe servicing and scarce materials.
6. **Review and continue.** The captain reviews the real world state. An
   unanswered or blocked job stays open. A recorded, fresh report permits
   assignment of another eligible expert; with all available tests exhausted
   the captain explicitly escalates. The world duty clock periodically
   reawakens unresolved obligations without polling LLMs while idle.
7. **World-only closure.** The atmosphere-alarm ticket closes only after
   A-01 has actually returned to nominal through a world-recorded restart.
   A captain's vote, a specialist's consent, the favored diagnosis or
   the existence of a report **never** closes an unresolved anomaly.

This is the **first bounded command-follow-through capability**. It is not
an indefinite science planner: an analyzer case presently permits one distinct
second diagnostic per specialist, followed by an explicit open escalation
if the cause remains unverified. Further rounds, alternate experiments,
real controlled interventions and scheduling beyond the current apparatus
are future G3/G4 work. The world reminder loop prevents silent disappearance,
but does not itself generate new scientific methods.

## Skills separate from ranks and authority

The role's initial competency vector ranges from 0 to 4 in command,
coordination, engineering, environment, cargo and diagnostics. It is seeded
on first ship creation for each of the original five plus the captain, and
never overwritten on idempotent reboots. Neither rank nor this vector
bypasses physical permission checks. The captain's starting diagnostics
score is **1**: command responsibility does not imply diagnostic competence.
The optional, personally performed bridge check requires **diagnostics >= 2**
AND presence on the Bridge, and still reveals only available telemetry, not
a root cause. The captain's Concordia action menu includes this personal
inspection choice only when the world-issued problem notice establishes
the necessary qualification; otherwise the captain must delegate. A
world-verified `captain_inspect` receipt binds the observation to the
captain's own session and prevents invented expertise. This defines an initial qualification boundary, **not** a
use-based progression/experience system; progression must later use verified
consequential work rather than mere button presses.

The captain deliberately has no invented backstory, name or personality
trait profile beyond their factual command duties. We can develop individual
characters after the systemic responsibilities have been tested.

## Isolation, authentication and crash behavior

- The captain is a sixth native Evennia character and a distinct Concordia
  entity, puppet account and checkpoint, enabled with
  `OX_CAPTAIN_OVERSIGHT=1` and a separate operator-provisioned
  `p4f-captain-id.json`. Old `p4e-ids.json` stays exactly five identities,
  preserving existing five-crew trial behavior.
- The same existing supervisor lease prevents simultaneous competing handlers
  for one ship. The captain's individual messages reach only that account;
  independent engineers' unaddressed observations are never copied.
- Work assignments, answers, claim, review and escalation use actor-bound
  `WorkReceipt` IDs and source-addressed journal events. Replayed
  acknowledgements do not duplicate physical actions or historical reports.
- The existing world clock emits a bounded review-due notification from the
  persisted due time. Operator/test code may advance game time; the handler
  only wakes on actual world events and never consults the DB cause.

## Tests and limitations

The new `world.tests.test_captain_followthrough` covers role and skill
permissions, open-ticket ownership, qualified assignments, explicit refusals,
fresh-source evidence, no duplicate assignments, journaling rollback, review
reminders, and the actual A-01 isolation/replacement/restart resolution.
Existing uncertainty tests and six separately authenticated WebSocket
sessions run in `ox-g3f-captain.yml`: five crew first gather evidence,
the captain then directs further work, receives actual reports, and
escalates when the bounded diagnostic possibilities are exhausted.
Restart/replay must perform **no duplicate assignments**.

The old deterministic MockModel is a protocol test. It does not show that
a real captain consistently prioritizes wisely, or that a specialist always
accepts and completes the assigned work. Future targeted trial batteries
should include captain-versus-crew disagreement, refusal, bad hypotheses,
scarce parts and competing shipwide emergencies, with hosted-model
decision-making, measured deadlines and different skill distributions.
