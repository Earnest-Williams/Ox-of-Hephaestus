# G10b — world-authoritative time read on each cognition decision

The G10 memory clock bridge persists simulated time but cannot advance in a
quiet live ship when no addressed event arrives. This follow-up completes the
live read path without creating a handler-controlled timer.

An ordinary authenticated Evennia character may issue
`oxclock <32-lowercase-hex-nonce>`. The command uses
`evennia.utils.gametime.gametime(absolute=True)` *inside the live game
server* and replies with one bounded `ox_clock` OOB packet containing
`version`, the echoed nonce, caller dbref and authoritative game seconds.
It never grants authority, edits state, or reads other characters' memories.

`WorldClockPort` verifies authentication, nonce, identity and finite
nonnegative game seconds through the same bounded packet-preserving WebSocket
matcher already used for capability reads. The supervisor samples the clock
just before scheduling each model decision and advances **only that actor's**
G10 memory cursor. Thus elapsed game time is accounted for even if no new
memory was admitted since the last decision.

Failure to read the clock fails closed before inference; handler wall time is
never used as a substitute. A sample is not a world event, equipment receipt,
or authority to mutate Evennia. A G8 virtual turn remains its own domain.

Cost: one additional authenticated read-only Evennia command per live model
decision. The G12 local scale profile did *not* measure this transport cost;
a separately observed integration trace is needed before optimising its
cadence or caching authoritative samples.
