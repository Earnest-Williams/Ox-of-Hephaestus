# Build plan

The order in which the operations specification becomes game code. Each work
package is one or two focused pull requests with its own tests and a focused Ox
CI check, following the repository's rules: Ox code stays in `game/`,
`services/`, `contracts/`, `design/` and `scenarios/`; Evennia owns every world
change; no handler or interface acts as a second physics authority.

**Status:** first access-evidence package in review, 11 November 2026. [PR #151](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/151) merged and implements physical power islands, surveyed A/B connectivity, finite cooling with original-LT rejection and the first verified read-only drum-3 gateway vocabulary. Remote actuation, a lead-mind principal and player access remain subsequent packages. The original v0.5 ship model remains intact.

## What already exists to build on

- **Ordinary traversal records.** Completed passage through a canonical
  exit emits `crew_traverse` (who, from, to, game time) and a work receipt
  (`game/world/ship_crew_access.py`). This is not a door-state event.
- **Attended hatch actions.** `crew_physical_action(..., "hatch", ...)`
  emits `crew_hatch` with an access-link target and before/after state even
  when nobody passes through. Only a changed state proves an open/close.
- **Indexed transfers.** A finished timed passage emits
  `crew_indexed_transfer_complete` with origin, destination and actor;
  `crew_indexed_transfer_queued` and aborted events are not arrivals.
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
| 0 | **Design data for operations** (support overlays underway in PR #151) | Optional, validated fields: per access link `motorised` and `vacuum_seal`; per room `controlled_access`; the nine core machine rooms and machines; the navigation computer on the bridge; gateway hosts on local control stations; backbone routes | Model loader and candidate checker accept them; existing installed-ship tests unchanged | — |
| 1 | **The lead mind as a principal** | An authenticated player with no body; a new network-scoped read view (not `developer_actual`, not any character's beliefs) | S04, S09 | 0 |
| 2 | **Access log** | Network-scoped projection of completed `crew_traverse`, state-changing `crew_hatch`, and `crew_indexed_transfer_complete` events, with source ID/time and identity only at controlled-access points | Standalone hatch transitions and indexed arrivals appear; no-op hatch requests and queued/aborted transfers do not imply movement; unreachable records stay hidden; replay has no gaps or duplicates | 0, 1 |
| 3 | **Backbone, segments and gateways** (dual-rail physical paths underway; segments/gateways pending) | World-owned link state, segment membership, gateway mappings with revisions, raw and translated readings; drum 3's gateway at `LCS-DR-03` first | S01, S02, S03, S12 | 0 |
| 4 | **Remote actuation** | Commands over the network to remote-operable devices, starting with `ISO-DR-03-LT-IF`; request IDs, receipts, interlocks, arbitration | S04, S05, S06 | 1, 3 |
| 5 | **Local takeover** | `LCS-DR-03` as a crew console: local reads, local operation, takeover and hand-back, receipted | S14 | 3, 4 |
| 6 | **Motorised doors** | The lead mind opens, closes and seals motorised doors; new world-owned actuation and seal-state events extend the existing access-log projection | Door commands obey pressure interlocks; standalone open/close/seal transitions appear only when world-confirmed | 2, 4 |
| 7 | **The core** (physical machinery support underway; parity/principal pending) | Nine machines as fitted equipment, parity and rebuild, capacity steps, handover to subsystems, the core log | S10, S15 | 0, 3 |
| 8 | **Navigation computer** | Equipment on the bridge; a specialist agent with no personality by default; installs only at the machine, recorded | S07 | 0, 7 |
| 9 | **Watch routine** | 36-hour day, shifts and rota, calls and responses as records | Rota and calls replay exactly | 1 |
| 10 | **Time and communications** | Watch mode on reachable triggers; message routes and delivery | S11, S13 | 1, 3 |

## First access-evidence pull request

Packages **0 and 2**, with the smallest slice of package 1 they need:

1. Add the optional `motorised`, `vacuum_seal` and `controlled_access` fields
   to the model, defaulting so that existing data is unchanged; mark the
   entrances, the bridge and the nine machine rooms as controlled access.
2. Extend the loader and candidate checker to validate them.
3. Build the access-log projection from `crew_traverse` (completed ordinary
   passage), `crew_hatch` (only actual open/close transitions in before/after
   state), and `crew_indexed_transfer_complete` (finished indexed passage).
   Preserve the event ID, access link, source type and game time; show
   direction only for passage and identity only at controlled-access
   points. Do not infer door actuation from a traversal, or a completed
   transfer from a queued/aborted event. Remote door and seal actuation
   require new world-owned events in package 6, not fabricated records.
4. Tests: pure projection cases for a hatch opened and closed without
   traversal, an unchanged hatch request, ordinary crossings, indexed
   transfer completion versus queued/aborted states, identity filtering,
   unreachable doors, event-ID deduplication and paged replay. Installed
   tests should exercise an attended hatch action, controlled and
   uncontrolled crossings, and a completed real indexed transfer.
5. A focused CI workflow for the new tests, following the repository's
   draft-guard and path-filter rules.

This first access-evidence slice validates optional room/door flags and adds
a versioned design-only monitoring overlay, without rewriting the original
v0.4 topology. The gap-23 MIND-03 rack has its own reader candidate; its
public cross-trunk room is not labelled controlled. The internal projection
reads only committed `CanonicalShipEvent` sources and filters by the set of
already verified reader deliveries, with identity separately gated by an
installed identity reader. A numeric internal scan cursor is **not** a player
API. Fitted access readers, authenticated principal, physical reader paths
and durable per-principal delivery/cursor binding remain follow-up work.

The first integration campaign checks live hatch and indexer events through
that internal projector. No remote door actuation or network read access
is being silently activated.

## Open questions

1. **Decided for physical infrastructure in draft PR #151:** use versioned
   operations overlays loaded beside the existing v0.5 candidate, with
   cross-reference checks and separate world-owned installed rows. Preserve
   the historical ship model and avoid silently interpreting proposals as
   already fitted. See [ADR 0011](../decisions/0011-ship-control-support-overlays.md).
2. Is the lead mind's network-scoped view a third read-model scope, or a
   specialised `actor_observed` for a principal with no body?

## Infrastructure work underway in PR #151

- Separate power and ship-control support overlays. They reference real
  power boards, trunk rooms and access links rather than altering the v0.5
  candidate in place.
- Dual 23-compartment fibre rails and 18 individual computer drops. Two
  additional, independently rated HAB rotary data couplers are **new
  hardware**; neither indexed personnel transfer is treated as a cable.
- Five locally buffered and individually monitored thermal groups, with
  finite surveyed headroom, 15 separately fitted LT circuit records,
  measured rejection, headroom recovery and on-clock thermal trip handling.
- [Attended computer cooldown and restart](cooling.md#attended-computer-recovery),
  with metered auxiliary power, observed heat rejection, recovered headroom
  and a separate local restart command that preserves physical damage.
- Recorded continuity and pressure-penetration surveys, plus continuous
  rotary-joint environmental/EMI qualifications before connectivity counts.
- A separately fused, metered local supply and a three-register read-only
  vocabulary for the drum-3 gateway, with source provenance and revisions.
- A monitored rack at `XCON-GAP-23`, preserving the original crew shortcut.

**Still pending:** remaining gateway protocol coverage, local takeover,
network read-model scopes, access-reader events, remote commands and the
lead-mind principal.


## Follow-on: first actual access contact (dependent PR)

A drum-3 passive contact mounted on `ACC-DR-03-LOCK-FIX` and wired to the
already metered `GW-LCS-DR-03` sense input is fitted as separately
faultable Evennia hardware. Physical continuity/penetration surveys bind
the sensor and cable revisions. A local world event is recorded **only**
when the physical hatch changes state while the fitted, surveyed gateway input
is powered; there is no retroactive catch-up and no inferred identity. This is
a local instrument, not the network delivery service or lead-mind principal.
See [the fitted drum-3 contact](../ship/G19_DRUM3_ACCESS_CONTACT.md).
