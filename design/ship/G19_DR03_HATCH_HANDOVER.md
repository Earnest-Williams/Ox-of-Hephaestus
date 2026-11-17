# Drum-3 hatch access: requests and attended local decisions

**G19 scope:** the existing pressure-rated `ACC-DR-03-LOCK-FIX` hatch,
its surveyed passive `ACSR-DR-03-FIX` contact, and the original
`LCS-DR-03` console in `BE-05-SVC`.

The fitted hatch contact is **a dry switch, not an actuator**. An
authenticated, enrolled lead-mind account may issue
`oxhatchreq <32-hex-id> <open|closed>` when the actual surveyed contact,
powered gateway, finite compute, and ship A/B network are available.
The request changes **no hatch state** and grants no remote motor authority.
At most one request is outstanding; each request is durably receipted.

Crew can inspect the pending request ID and desired position with
`oxhatchpending` at `LCS-DR-03`, even if the ship-wide A/B network is down.
This local display contains no account identity and never moves the hatch.

A crew member physically present at the existing locally powered
`LCS-DR-03` console may issue
`oxhatchreply <32-hex-decision-id> <original-request-id> <accept|decline>`.
The console uses its real local electrical supply and remains operable
when the ship-wide fibre drops. The decision becomes a world-owned event
linked to the original request and has its own globally unique work
receipt. Accepting means **accepted for manual action**, not that the
door has moved. Only the standard physically present crew hatch
operation, with its existing pressure, movement, damage and worksite
interlocks, may subsequently change `access:ACC-DR-03-LOCK-FIX`.

The original account can call `oxhatchstatus <request-id>` across a
currently live network. It sees its own pending/accepted/declined state
from immutable events. No other account can read or claim its request;
no status is inferred from a cached gateway tick.

## World-confirmed, not merely accepted

A previously accepted request becomes `world_confirmed_at_source_time`
only when the **same accepting engineer** subsequently performs an actual,
state-changing `crew_hatch` action to the requested position, the surveyed
local dry contact emits a matching observation of that exact physical event,
and the account's existing access-delivery channel actually delivers this
observation **while the network is live at event time**. The reconciled
status includes bounded physical, sensor and network-delivery event IDs and
the source time, but **not** the engineer's identity or private state.

A no-op, an action by another worker, an action before acceptance, a
declined request, a later superseding request, a failed/unsurveyed reader,
or a contact event that remained local during a network outage cannot
advance the status. Reconnection never backfills a missing network
observation. `physical_actuation: false` continues to mean the *remote
request* moved no hardware; the physical confirmation is independent
crew work. The confirmed status means the hatch **was measured in that
position at the cited time**; it is not a claim about its current position
or proof of the engineer's intent. A later reopening does not erase
the earlier world-confirmed transition.

The original local contact and the existing event-time-delivered access
stream retain sole authority for observations. No new sensor, network
permission, actuation route or world-owned physical state is invented.

**Acceptance:** pure policy checks reject spoofed control records,
made-up door motors and concurrent requests. Installed tests exercise
authentication, current surveyed contact, idempotent global receipt IDs,
manual hatch movement only after real crew action, and a local response
after the A/B fibre is severed.

**Excluded:** remote hatch movement; arbitrary access-link commands;
invented motor power or cable routes; automatic action after acceptance;
door-identity recognition; queues beyond one request; bypasses of
physical crew hatch interlocks. A later motorised hatch feature would
need separate fitted hardware, isolation, pressure testing, commissioning,
and an independent acceptance review.
