# G2c — learned-world GOAP navigation

**Delivery:** world-side capability advertisements merged in
[PR #35](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/35).
Authenticated handler planning, world travel and station recovery are in
[PR #36](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/36).

## Authority and privacy

Evennia's `oxcapabilities <nonce>` command reports only the caller's
current ship compartment, exits whose actual traverse locks currently allow
the caller to pass, and installed **local** equipment with candidate
operations currently eligible under state, role, inspection and inventory.
The handler's `CapabilityPort` requires an ordinary authenticated character
WebSocket, fresh 128-bit matching nonce, exact actor DB ref, protocol version
and strict bounded JSON structure. This is an observation, not a permit.

Each character has a separate `NavigationKnowledge` JSON record, bound
to their world character DB ref; it cannot be restored onto another crew
member. This is an *imperfect learned graph*, not a global map: only the
exits visible at places personally visited are stored. Current location is
NEVER trusted from saved data.

## Planning, execution and failure

`CrewNavigator` builds `GoapAction` operators from learned exit
advertisements: moving from origin room to adjacent room changes the
hypothetical at-room fact. Existing `GoapPlanner` searches these predicted
transitions by cost; when the target is not yet known, the navigator
heads toward the nearest reachable **unexplored** compartment. It never
queries the server's complete ship topology.

Before an attempted step, `CapabilityPort.traverse` asks the world
again for the actor's current room and exits. If the exit is no longer
advertised, the navigator rejects that step. Otherwise it sends the normal
world exit command (e.g. `out` or `engineering`) through its own authenticated
session. It then asks again and confirms the actual room; the predicted
GOAP effect alone NEVER marks an arrival. A denied/stale exit is excluded
for that run and other discovered routes are considered. Without a route,
the navigator reports `blocked`, bounded by at most 24 moves in the live
trial. All equipment transitions still require independent world receipts.

This is a deterministic, **zero-LLM** navigation policy: it does not
demonstrate general abstract wayfinding intelligence. The route policy
and a character's long-term knowledge can become additional inputs to
cognition later, but world access remains authoritative.

## Live crew integration

The three-crew supervisor now confirms that the active engineer and safety
reviewer can reach Engineering through ordinary exits before local work.
The five-crew supervisor confirms Mara's Cargo Hold and Teo's Environmental
Plant locations before departmental actions. Private maps are persisted
under `navigation_knowledge` in the existing supervisor state, with the
same character-bound schema across restarts. An unreachable duty station
fails without sending physical work. No database is read from the handler.

## CI acceptance

- Offline bounded typed-payload tests: actor/nonce/schema/cmd injection
  rejection, private map identity binding, unknown destination discovery,
  closed-route blocking, alternative path exploration, mid-travel hatch
  closure, route memory restoring against the **new actual location**.
- Real Evennia world-backed capability tests: role/location/inspect eligibility,
  denied exits, no remote equipment or omniscient map, command OOB payload.
- Authenticated independent client walks **Crew Mess -> Connecting Passage
  -> Engineering** using only real exit commands; reroutes through an
  operator-installed Machine Shop hatch when the direct engineering hatch
  is locked, or stops when no route remains.
- Five-crew recovery trial puts Teo in the mess while A-01 is faulted; the
  live supervisor must navigate him to Environmental Plant and successfully
  service A-01 using existing durable world receipts.
- All earlier Evennia, Concordia, PostgreSQL and recovery workflows run
  against the final code commit before merge.

## Explicit limits

No omniscient long-distance map, autonomous mission selection, item handling,
shipwide inventory, arbitrary multi-room repair permissions or teleport APIs
exist in this slice. Exit advertisements can become stale; validated moves
still pass through Evennia. Cross-process distributed fencing and full G3
cooperative work orders remain future work.
