# G19 — full-ship access, crew movement and worksite coverage

**Branch:** `g19-complete-ship-systems`; PR #138 stays draft. Verisimilitude
and authoritative Evennia state are the contract. No 40-crew voyage in this
development round.

## Verified topology baseline

Original ship geometry: **421 physical space objects, 517 physical links,
1,034 materialised directional Evennia exits**. The original G19 access audit
passed its two-job pure/installed gate on 27 October 2026:
[run #40554343721](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40554343721).

The full installed index tests every room, both exits per connection,
actual destinations and durable identities. Rebuilding the world preserves
existing smoke damage and previously materialised objects.

**420 of 421 rooms** belong to the connected authored graph. The one
disconnected space, `WR-TRIM-TANK-BAY`, is a specifically surveyed
**unoccupied trim-water tank void**, without a breathing-pressure cell,
inside the independently rotating workshop assembly. There is no physical
personnel hatch and no installed equipment located *inside* that cavity.
Both `WR-TRIM-A` and `WR-TRIM-B` are at the separate fixed
`WR-ROTOR-MACHINERY` station. The audit makes this **one exact,
metadata-checked exception**. Any other disconnected room remains a
strict topology failure, and a remodel that changes the void to a
habitable compartment cannot silently reuse this exception.

## Equipment and gas-site inventory

All **808** original v0.5 candidate equipment records have valid installed
room IDs. The authored gas-location survey is:

| Atmospheric location | Equipment | Implication |
| --- | ---: | --- |
| Named pressure cell `PZ-*` | 602 | Check real gas inventory, pressure and temperature before local entry |
| Declared `VACUUM` | 103 | Suited maintenance/access and specific rated controls required |
| No assigned pressure cell (`null`) | 103 | **Unknown** is not air: no unsuited personnel admission or pressure credit |

The 103 unknown-pressure equipment sites are not automatically declared
vacuum; their installation and intended service method require a further
room-by-room classification. The 83 compartments without pressure-zone
metadata and 26 explicit vacuum compartments are a separate inventory
finding from the 420-connected spatial graph.

`ship_worksite_audit` inventories equipment families, physical rooms,
static path obligations, exterior worksites, cases with only freight
geometry, and the actual atmosphere class. Equipment is never placed
in a guessed space. No source inventory or ship mass is fabricated.

## Personnel routing versus physical geometry

The original unconstrained shortest-path audit could select a *freight
handling route* or an unnecessary exterior rail when looking for a
maintenance site. The new `candidate_personnel_routes` uses only known
personnel-capable link families and heavily penalises rotary/EVA/airlock
segments. It **never converts freight gates, cargo portals or heavy
freight capture into instant human passages**.

This remains a *geometry-only worksite itinerary*. A candidate route
does not itself open a hatch, equalise gas, move a carriage, issue a suit
or defeat a locked equipment work order. Real movement still calls
`traverse_canonical_exit` and must satisfy the live physical preflight.

## Powered and ordinary crew doors

The existing pressure-bridge, fixed-indexer and EVA controllers retain
their separate interlocks. The new G19 local ordinary door operation
extends the same durable `hatch` receipt to real doors of these classes:
pressure, service, cabin, cargo-section, store, service-panel and fire,
**only where two fitted pressure cells are known, breathable and matched**.
Cross-frame, damaged, unrated or vacuum/unknown openings are refused.
An ordinary hatch command cannot operate a freight capture, dedicated
F1/F2 vacuum service airlock or EVA exterior hatch.

An unsurveyed generator room or cargo-sector atmosphere is therefore
not made safe by a generic door-opening command. Some worksite and
pressure-zone commissioning still remains, and generic pressure hatch
control is not a substitute for a complete suited work procedure.

## Physically executed regression

The first end-to-end installed route campaign passed on
[run #40555828118](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40555828118):
fixed spine → drum lock → 180-second rated indexer → drum hub → return,
and fixed HAB dock → moving phase-matched HAB → 300-second carriage →
return through the same rated interfaces. Every passage is a real exit,
with work receipts and no mid-route operator teleport.

Follow-on installed tests verify locally operated ordinary doors,
blocked unsurveyed cargo/generator access, and an independent aft EVA-lock
round trip with finite suit, pressure recovery and its actual electrical
feeder. [Run #40556713652](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40556713652)
passed **both jobs: 8 pure and 7 installed Evennia tests**, at
tested runtime `a2f6ee9e`. Its two-job evidence is limited to this
access/worksite slice; larger G19 whole-ship closure remains open.

## Remaining G19 closure

1. Run the current-code access audit, installed door/EVA route tests,
   indexed movement and G18 environment compatibility to green.
2. Classify the **83 unmapped-gas rooms** and their 103 equipment items
   without inventing pressure or personnel shortcuts. Map physical service
   from adjacent compartments where applicable.
3. Complete deliberately rated suited access into the two flywheel bays,
   unpressurised machinery sites and cargo section maintenance stations,
   including gas custody, cycling, finite gear and damage isolation.
4. Verify the remaining exterior platform sites under radiator/plume and
   rotating drum restrictions; no false pass from static graph reachability.
5. Continue the full G19 damage, physiology, electrical, materials and
   operating closure gates. Keep the 40-crew voyage excluded this round.
