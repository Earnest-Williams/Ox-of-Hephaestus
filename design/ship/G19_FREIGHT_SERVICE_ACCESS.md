# G19 — attended freight-machinery service access

**Implementation:** `game/world/ship_freight_service.py`,
`game/world/continuous_ship_physics.py`,
`game/world/ship_crew_access.py`. This is a **live crew movement
mechanism**, not just a route graph, and it preserves the original Ox v0.5
inventory, compartments, and freight hardware without introducing a new
pressurised tunnel or free equipment teleport.

## Nine existing maintenance wickets, thirteen installed machines

| Existing physical service opening | Original upstream crew station | Downstream worksite | Serviced equipment |
| --- | --- | --- | --- |
| `ACC-DR-01-FREIGHT-LOCK-LOGI` through `ACC-DR-06-FREIGHT-LOCK-LOGI` | Each matching `LOGI-STOP-DR-xx` | Each `DR-xx-FREIGHT-LOCK` | The six `DR-xx-FREIGHT-COLLAR` units |
| `ACC-WR-SPARES-MATERIAL` | `SPARES-CENTRAL` | `MATERIAL-STOCK` | `IND-SCRAP-HOLD-B`, `LP-MATERIAL-STOCK` |
| `ACC-LOGI-STOP-HAB-HUB-SERVICES-MAIN` | `LOGI-STOP-HAB-HUB-SERVICES` | `LOGI-HAB-HUB-SERVICES` | `LOGI-SLED-01` through `LOGI-SLED-04` |
| `ACC-WR-FREIGHT-STAGING` | `LOGI-STOP-HAB-HUB-SERVICES` | `WR-FREIGHT-STAGING` | `WR-HEAVY-LOCK` |

The original `freight_branch_tunnel`, `freight_door`, and
`freight_gate` entries **remain freight hardware** in the source model.
A qualified cargo officer or engineer can use an existing opening as a
*secured worksite entry* only while its freight function is inhibited.
The remaining freight transfer, heavy rotor docking and cargo portal
hardware never becomes a generic crew doorway.

## Operational sequence

1. An authorised world operator explicitly runs
   `commission_g19_freight_service(operator_approved=True)` after
   installing and arming the ship. Recommissioning preserves prior
   maintenance state; it never closes an occupied hatch or resets a casualty.
2. An engineer or cargo officer stands at the listed **upstream**
   compartment. `oxplantread freight_service` shows only the physically
   adjacent gates and their current state.
3. Ensure the corresponding drum or workshop rotor is stopped, braked,
   stationary, hard-locked, with transfer collars retracted; the original
   freight capture behind it is closed. All cargo moves, moored port jobs,
   sealed-waste freight and propulsion/attitude/FTL commands must be idle.
   Both already-fitted compartments must have breathable, matched
   pressure cells. These conditions are rechecked against world state.
4. Issue an ordinary durable crew operation:
   `oxplant <32hex-id> freight_service <ACC-...> open`.
   This obtains **exclusive** shipwide freight service custody and
   positively opens the existing rated service hatch. A damaged or
   already-open, unregistered door cannot be grandfathered into a permit.
5. Cross the **real authored forward exit** using normal Evennia traversal,
   work beside the actual installed equipment, and return through the
   reverse exit. Existing `repair` operations require a real toolkit,
   locally surveyed and carried spare parts, real condition, isolation and
   finite elapsed time. Actual service access is required both when repair
   begins **and on each subsequent repair tick**.
6. Return all personnel to the accessible control side. A qualified
   operator at that control then sends
   `oxplant <32hex-id> freight_service <ACC-...> close`.
   Closure is rejected if crew remain inside or an on-site repair job
   is unfinished. Closing records a cumulative completed release and
   relinquishes the global freight lockout.

`crew_physical_action` assigns globally idempotent work receipts,
`CanonicalShipEvent` records both lockout and real hatch transitions,
and `traverse_canonical_exit` records every physical crossing.
Replaying an old command cannot re-open a gate or restore cargo movement.
A roleless/unauthorised person, an uncommissioned service hatch, an
operator-position shortcut or a stale "open" access setting cannot
grant crew clearance.

## Protection and emergency behaviour

While **any** one of the nine openings is in attended-maintenance
custody, normal cargo transfer, port handling, waste offload, ship
acceleration/attitude, translation and hazardous rotor actions are
inhibited. Stopping machinery remains possible. Only **one** such gate
can be serviced concurrently: this models the Ox's inherited master
freight-LOTO arrangement rather than unqualified modern redundancy.

If an actual pressure, door or machinery casualty occurs, further
crossing and repair progress fail closed until the real condition is
restored. The maintenance ledger remains durable across server restarts,
and a failed operation does not consume its request ID. No operator
teleport, magic service hatch or new air/stock/mass is used.

Crew **access** does not imply that a damaged or loaded scrap cassette is
safe to repair: existing `safe_repair_target` requirements remain in force.
In particular, the industrial scrap cassette must be empty before
replacement, and moving rotor collars remain isolated.

## Regression and acceptance

- Pure: `world.tests.test_ship_freight_service`
  checks nine source-model gate identities, all 13 real machine sites,
  permitted upstream routes, ledger integrity and machinery interlocks.
- Pure: `world.tests.test_ship_worksite_audit` requires 13/13
  to have attended access, with **zero** unexplained personnel worksite
  locations and no freight shortcut in general-purpose crew routing.
- Installed: `world.tests.test_installed_ship_freight_service`
  physically boards and returns through all nine original freight
  entries, rejects uncommissioned/unsafe entry, stops new freight
  operations during personnel maintenance, prevents closure on an
  occupied worksite, and conducts a measured 0.5-kg spare-parts
  replacement of `LOGI-SLED-01` at its actual freight enclosure.

The isolated, unoccupied `WR-TRIM-TANK-BAY` remains a sealed equipment
void. This slice does not declare the other 103 unsurveyed-atmosphere
equipment sites breathable, nor does it authorise hot-radiator,
propulsion-plume or unparked drum-skin EVA work.

**No 40-crew voyage**; PR #138 remains draft until wider G19 acceptance.
