# Build plan

The order in which the operations specification becomes game code. Each work
package is one or two focused pull requests with its own tests and a focused Ox
CI check, following the repository's rules: Ox code stays in `game/`,
`services/`, `contracts/`, `design/` and `scenarios/`; Evennia owns every world
change; no handler or interface acts as a second physics authority.

**Status:** plan, 3 November 2026. Nothing below is implemented.

## What already exists to build on

- **Traversal records.** Every move through a canonical exit creates a
  `crew_traverse` world event (who, from, to, game time) and a work receipt
  (`game/world/ship_crew_access.py`).
- **The read model's scopes.** `developer_actual` and `actor_observed`, with
  versioning and cursors ([contract](../../contracts/WORLD_READ_MODEL.md)).
- **Receipts and request IDs** for every consequential action, with
  reconciliation under the original ID ([ADR 0009](../decisions/0009-durable-events-and-work.md)).
- **The ship model** in `design/ship/ox_full_ship.json`, loaded by
  `game/world/ship_model.py`, checked by `design/ship/check_v05_candidate.py`;
  the prebuilt ship template rebuilds automatically when the design changes.
- **Remote-operable flags** on 559 isolation points, and 33 local control
  stations, as data with no runtime behaviour yet.

## Work packages

| # | Package | Delivers | Acceptance | Depends on |
|---|---|---|---|---|
| 0 | **Design data for operations** | Optional, validated fields: per access link `motorised` and `vacuum_seal`; per room `controlled_access`; the nine core machine rooms and machines; the navigation computer on the bridge; gateway hosts on local control stations; backbone routes | Model loader and candidate checker accept them; existing installed-ship tests unchanged | — |
| 1 | **The lead mind as a principal** | An authenticated player with no body; a new network-scoped read view (not `developer_actual`, not any character's beliefs) | S04, S09 | 0 |
| 2 | **Access log** | The lead mind's scoped view of `crew_traverse` events and door state changes: door, direction, time everywhere it reaches; identity only at controlled-access points | Identity appears only at controlled points; nothing from doors it can't reach; paged replay without gaps or duplicates | 0, 1 |
| 3 | **Backbone, segments and gateways** | World-owned link state, segment membership, gateway mappings with revisions, raw and translated readings; drum 3's gateway at `LCS-DR-03` first | S01, S02, S03, S12 | 0 |
| 4 | **Remote actuation** | Commands over the network to remote-operable devices, starting with `ISO-DR-03-LT-IF`; request IDs, receipts, interlocks, arbitration | S04, S05, S06 | 1, 3 |
| 5 | **Local takeover** | `LCS-DR-03` as a crew console: local reads, local operation, takeover and hand-back, receipted | S14 | 3, 4 |
| 6 | **Motorised doors** | The lead mind opens, closes and seals motorised doors; every movement in the access log | Door commands obey pressure interlocks; access log matches | 2, 4 |
| 7 | **The core** | Nine machines as fitted equipment, parity and rebuild, capacity steps, handover to subsystems, the core log | S10, S15 | 0, 3 |
| 8 | **Navigation computer** | Equipment on the bridge; a specialist agent with no personality by default; installs only at the machine, recorded | S07 | 0, 7 |
| 9 | **Watch routine** | 36-hour day, shifts and rota, calls and responses as records | Rota and calls replay exactly | 1 |
| 10 | **Time and communications** | Watch mode on reachable triggers; message routes and delivery | S11, S13 | 1, 3 |

## First pull request

Packages **0 and 2**, with the smallest slice of package 1 they need:

1. Add the optional `motorised`, `vacuum_seal` and `controlled_access` fields
   to the model, defaulting so that existing data is unchanged; mark the
   entrances, the bridge and the nine machine rooms as controlled access.
2. Extend the loader and candidate checker to validate them.
3. Build the access-log projection over existing `crew_traverse` events: door,
   direction and time for motorised doors; identity only at controlled-access
   points.
4. Tests: a pure projection test (identity filtering, unreachable doors,
   pagination), and an installed-ship test that walks a character through a
   controlled and an uncontrolled door and checks both views.
5. A focused CI workflow for the new tests, following the repository's
   draft-guard and path-filter rules.

This builds on records the world already keeps, changes no physics, and gives
every later package — and the lead mind's view of who went where — its
foundation.

## Open questions

1. Should the design-data fields go into the v0.5 candidate directly, or into
   an operations overlay file loaded beside it?
2. Is the lead mind's network-scoped view a third read-model scope, or a
   specialised `actor_observed` for a principal with no body?
