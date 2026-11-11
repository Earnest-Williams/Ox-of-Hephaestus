# Network-delivered access observations

**G19 package:** first authenticated, bodiless account read channel on the
fitted lead-mind-support network. A network event is different from a local
instrument reading; the world owns both and records why an event qualifies.

## Operator enrolment and scope

The operator invokes `enroll_access_account(account, operator_approved=True)`
with an existing Evennia **AccountDB** object after physical control hardware
has been fitted. Enrolment is permanent/idempotent for this initial one-account
principal; attempting to reassign the account is refused. No normal character
can enrol itself, select a reader, select a scan cursor, or claim a region.

Only an authenticated OOC account gets these commands:

- `oxnet` — one page (16) of previously delivered events, in an
  `ox_network_access` OOB packet; each includes an opaque acknowledgement
  token rather than a client-chosen numeric world cursor
- `oxack <token>` — acknowledge a previously issued page in a
  `ox_network_ack` OOB packet; acknowledgement persists across restarts

The account is a player-network principal, not a crew character or an
omniscient developer. These commands do not belong to `CharacterCmdSet`.
An unsuccessful authentication, missing enrolment, or network isolation
returns no world records or information about another account.

## Admission rules

The world's passive drum-3 hatch contact is the **only** currently admitted
source. For an actual changed-hatch event, the local contact first emits
`g19_access_contact_observed` if its own surveyed circuit is live.
During that same transaction, the network delivery receiver checks:

1. The original fixed door event exists and matches the contact's change.
2. The contact's current physical identity, sensor/cable revisions and
   continuity/penetration certificate remain valid.
3. The local gateway has its real energised 50 W supply and intact thermal
   mount; power is evaluated *now*, not from a stale prior tick.
4. The independent ship power model can presently supply a working compute
   endpoint. The existing thermal proof and full A/B surveyed backbone must
   connect that endpoint to the drum-3 gateway. A broken segment, feeder or
   cold-plate instrument fails closed even if the cached telemetry says online.

When all checks pass, an append-only `g19_access_network_delivered`
world event is recorded against the account principal. Its capsule includes
the original hatch event, source observation ID, reader and gateway, game time,
and open/closed transition. It has **no operator identity** because the fitted
contact cannot identify people.

There is **no offline message queue** for this first source: a local contact
event during a network outage remains local and is not backfilled on reconnect.
Previously *delivered* events are replayable by the same account after
reconnection, until acknowledged.

## Durable replay and authority boundaries

Each account-scoped delivery page is bounded to 32 rows. A signed opaque
acknowledgement token binds the delivered event ID, physical enrolment epoch and
actual account database identity. The server stores issued/acknowledged
prefixes in the world-owned principal record under PostgreSQL row locks.
Unacknowledged pages can be replayed after restart; a forged or cross-account
token cannot advance the cursor.

This is *read-only*: no remote isolator action, door motors, local takeover,
cognition or subsystem arbitration is activated. The next control slice
will attach actuation authority to a separately receipted world operation.
