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

## Attended freight machinery entry (new G19 slice)

The original freight-only **13-machine worksite gap is now implemented**
using **nine already-authorised ship freight passages**, rather than
fabricating new crew corridors. `ship_freight_service.py` matches each
original gate and machine room exactly. A qualified cargo officer or
engineer at an actual upstream LOGI/WR station must secure an exclusive
shipwide freight lockout and verify stopped rotors, sealed freight capture,
idle cargo/ports and safe matched pressure. Only then may crew enter and
return through the original Evennia exit under the signed service permit.
The permit is durable; occupied workrooms and unfinished actual repair
orders prevent release. The `freight_service` crew operation is receipted,
and local `oxplantread freight_service` reports the accessible machinery.
Machine repair also checks the permit every work tick.

[CI run #40580738273](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40580738273)
passed **12/12 pure and 11/11 installed Evennia tests, 23/23 total**
at tested runtime `fa692fea`. The installed campaign physically
crosses and returns from all nine service gates, holds machinery locked
out while crew and unfinished jobs remain in the space, rejects unsafe
bypasses, and performs a 0.5-kg finite-spares repair of a genuine
`LOGI-SLED-01` inside the logistics trunk. The former 13-case
freight-only equipment access gap is **accepted at subsystem level**.
Vacuum/unsurveyed workspaces and exterior hazards remain separate scopes. Operating contract:
[G19 freight service access](G19_FREIGHT_SERVICE_ACCESS.md).

## Accepted original six exterior radiator work faces (28 October 2026)

All four `EXT-RAD-LT-1..4` and both `EXT-RAD-HT-1..2`
are now physically traversable through their **original** EVA
platform passages, under real individually issued suits, finite oxygen,
active 150-second carriage time and qualified crew permissions.

The existing LT plant must be stopped and both fitted LT rotary
manifold valves closed because the ship has no individual LT wing valves.
The two HT wings use their real independent valves operated from the
remote-capable `ENG-CONTROL` station, not imagined breathable air
inside `THERM-HT`. Surveyed skin temperature, thermal cooldown,
actual coolant valve positions, hardlocked nearby drums and ship
coast/attitude hold are live prerequisites for an individually
issued service permit. Reopening valves, restarting LT plant, thrust,
attitude changes and neighbouring drum motion are inhibited while
the permit is held. Failed isolation pauses both exterior approach
and genuine finite-spares repair, and actual personnel occupancy prevents
premature service release.

[Accepted CI run #40662087586](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40662087586)
passed **17 pure + 7 installed Evennia tests (24/24)** at
`58315d7c`. The physically walked LT and HT access and return paths,
HT part replacement, fault-paused repair and EVA transit, 6-face
independent permit coverage and ship-motion inhibition were tested.
See [exterior radiator service contract](G19_EXTERIOR_RADIATOR_SERVICE.md).

The separate original `EXT-PROP-AFT` plume inspection workface
now also has a dedicated safe EVA and propulsion shutdown sequence.
The original 120-second `EXT-AFT` platform permits an actual issued-suit
worker to enter only after positive exhaust skin/plume survey, both MAIN
and RCS inhibition, coasting/attitude hold, sound fitted controls and
an individually held workface permit. Actual crew can inspect and
retreat even after an unsafe control casualty. No separately fitted
external engine replacement component is invented.

[Nozzle inspection CI #40665213567](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40665213567)
passed **17 pure and 4 installed Evennia tests, 21/21 total**, at
`2e474b3f`. The suite covers the true EVA approach, returned crew,
nonrepeatable inspection, expired plume safety, occupied-workface
release refusal, propulsion/attitude/FTL inhibition and fault-paused
arrival. [Nozzle access contract](G19_AFT_PROPULSION_EVA_INSPECTION.md).

Whole-ship acceptance and the prohibited 40-crew voyage are not part
of either exterior subsystem gate.

## Remaining G19 closure

1. Run the current-code access audit, installed door/EVA route tests,
   indexed movement and G18 environment compatibility to green.
2. Classify the **83 unmapped-gas rooms** and their 103 equipment items
   without inventing pressure or personnel shortcuts. Map physical service
   from adjacent compartments where applicable.
3. Complete deliberately rated suited access into the two flywheel bays,
   unpressurised machinery sites and cargo section maintenance stations,
   including gas custody, cycling, finite gear and damage isolation.
4. The six radiator exterior pads and independently surveyed aft
   nozzle inspection platform now have measured hazards, finite suited
   access, work permits and propulsion/thermal inhibits. Unknown-atmosphere
   interior maintenance rooms, actual engine-component repair and other
   unsurveyed sites remain separate closure obligations.
5. Continue the full G19 damage, physiology, electrical, materials and
   operating closure gates. Keep the 40-crew voyage excluded this round.
