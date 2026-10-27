# G19 — full-ship crew access inventory and verification

Status: implementation committed on draft PR #138. The static topology audit
is not a claim that all 421 spaces are immediately accessible during casualty.

## Authored topology gate

The canonical source model has 421 rooms and 517 undirected physical links,
materialised as 1,034 separate Evennia exit objects. Each direction has its
own persistent exit identity, real room origin/destination, original link ID
and kind. `ship_access_audit.audit_access_topology` detects duplicate,
dangling and self-links, counts frame changes and boundary labels, and
enumerates reachable/isolated rooms from `CMD-PRIMARY`. It does not
silently recast a disconnected worksite as physically reachable.

`authored_route` returns only a shortest **static** link itinerary. Its
result never overrides pressure, EVA, damaged doors, moving frames, damaged
equipment, power or individual crew health.

A new isolated-compartment report can therefore distinguish:

- missing/incorrect authored ship geometry;
- complete, mounted exit objects pointing into wrong rooms;
- physically connected spaces presently barred by a real interlock;
- ordinary rooms that are reachable but unsafe to enter.

## Verification

Pure test: `world.tests.test_ship_access_audit`.
Installed two-test suite:
`world.tests.test_installed_ship_access_audit`.
Push gate: `.github/workflows/ox-g19-access-audit.yml`.

The installed run creates the real 421-room hull, verifies every bidirectional
exit, and checks that rebuilding the current installation retains physical
identity and damage. It does not run an autonomous crew voyage.

## Remaining operational closure

1. Run and archive same-head installed CI for the new audit.
2. Record any disconnected components as specifically authorised vacuum-only,
   separated structure, or a genuine design defect; do not blindly install
   invented crew passages.
3. Add a physically permissioned *runtime* sampled-route campaign across
   each actual access kind, including at least one ordinary route, each
   rotary transfer family, the moving HAB and both EVA locks.
4. Inventory all exterior workplaces and the remaining inaccessible
   maintenance stations; compare with actual safe physical access.
5. Keep PR #138 draft until the wider G19 casualty, physiology, equipment
   and conservation contracts pass. No 40-crew voyage this round.

## Important boundary

A passing static room/exit inventory is *not* complete traversability:
e.g. an EVA rail may be geometrically connected but require a charged suit,
functional airlock and acceptable exterior exposure. All of those decisions
remain with the existing authoritative `ship_crew_access` preflight.
