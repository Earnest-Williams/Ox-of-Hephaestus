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
no status is inferred from a cached gateway tick. An action made locally
during an outage remains independent of any earlier accepted request.
The surveyed contact still reports actual transitions separately.

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
