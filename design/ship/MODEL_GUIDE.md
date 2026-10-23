# Ox of Hephaestus - full ship JSON model guide

**Schema:** `ox.ship-world/0.1`, preparation baseline **v0.4**  
**Date:** 22 October 2026  
**Purpose:** playable world state and simulation authoring, not spacecraft certification.

v0.4 is the current repository preparation baseline. It retains the complete habitation/cargo/service model, the compartmentalised fixed spine, the adjustable-gravity Engineering work rotor, and the survivability/maintenance layer.

## Governing engineering scope

**[Ship Engineering Design Standard](SHIP_ENGINEERING_DESIGN_STANDARD.md) governs all ship engineering review.** Verisimilitude for a playable, aging, repaired freighter—not NASA, ESA, or fabrication certification—is the objective. The design is adopted when spatial relationships, failure dependencies, work/access costs, limited resources and observational uncertainty are convincing and internally consistent; missing aerospace qualification is not a blocker.

## What changed in v0.2

- Every major fixed-spine workplace now has a real axial compartment extent plus schematic cross-section position.
- The original twin 3 m personnel/service trunks are retained and now carry guided personnel carts.
- A separate 5.5 m heavy-logistics trunk runs the length of the fixed spine.
- Six large stopped-drum freight locks allow bounded inter-drum transfers without pretending the spine replaces port cargo handling.
- The bow is a real command/docking/EVA/rescue/service complex rather than a cluster at x=45 m.
- Main Engineering is resolved into Engineering Control, machine shop, electronics, welding, NDT, tool crib, parts wash, spares and material stock.
- Aft generation, stores, emergency control and propulsion are compartmentalised.
- Fixed-spine atmosphere and sanitary services now have explicit distribution and isolation.
- Debris protection is layered: passive shields, navigation/avoidance, charged-dust active adjuncts, forward water mass, and an explicit FTL dust-exclusion setting rule.

See `FIXED_SPINE_LAYOUT.md` for the human-readable arrangement and operating doctrine.

## Three truth layers

1. Original design intent.
2. Current physical installation (authoritative to the world).
3. Available documentation (evidence that can be stale).

Character knowledge remains separate.

## Granularity rule

Create objects where they affect movement, maintenance, resources, isolation, diagnosis, cargo handling, or meaningful choices. Do not instantiate every fastener or metre of pipe.

The fixed-spine positions are intended to answer questions such as "where is the machine shop?", "what route moves this pump aft?", and "what compartment loses air if this damper closes?" They are not fabrication coordinates.

## Integration status

The **published v0.4 spatial topology is now materialised** as 421 persistent Evennia rooms and 1,034 Developer-only directional access objects representing 517 undirected physical links. Current condition is owned by those Evennia objects and never overwritten on rebootstrap. The original seven-compartment proving ground remains the separately exercised operational runtime until equipment, pressure, crew safety and interlocks migrate. The **v0.5 candidate** contains further engineering source designs but is not yet the canonical bootstrap model or a verified matching live wire render. See `EVENNIA_INTEGRATION.md`.

## Main files

- `ox_full_ship.json` - canonical linked model.
- `FIXED_SPINE_LAYOUT.md` - layout/transit/debris doctrine.
- `Ox_Ship_Wire_Render_v0.4.html` - standalone interactive wire render.
- `EVENNIA_INTEGRATION.md` - tested stage-one integration and safety boundary.
- `LIVE_TERMINAL.md` - authenticated, version-gated Developer-only spatial monitoring.

## v0.3 adjustable-gravity Engineering work rotor

The heavy machine/mechanical shop is not a fixed zero-g room in the current Ox. `WR-01` is an independently rotating, variable-radius Engineering work assembly at the central spine.

Treat `SHOP-MECH`, `SHOP-WELD`, `PARTS-WASH`, `SPARES-CENTRAL`, `TOOL-CRIB` and `MATERIAL-STOCK` as persistent spaces riding WR-01. Their `location.radius_m` is the current nominal deployment; `radial_range_m` is the permitted authored range. The world may change the current radius through an actual rotor-reconfiguration action.

The simulation should derive centrifugal gravity from rotor speed and current radius rather than storing an immutable room gravity. Changing radius changes inertia and requires elapsed time, coordinated counter-carriage movement and balance control.

The nominal mass relationship is 160 t shop carriage to 480 t stores carriage. This is a play-facing mass model, not fabrication qualification. Fine balance comes from trim water/weights and current stock placement. Do not assume all spares are point mass at the carriage centroid when a scenario specifically concerns balance.

Heavy freight transfer to WR-01 requires a stopped/indexed/hard-locked state. Personnel transfer through `WR-IX-CAPSULE` is separate and may operate while WR-01 is rotating normally.

## v0.4 survivability additions

The current model adds four new play-facing layers:

- `damage_control_contract` and the `fire_main` service network;
- `external_maintenance_contract` and explicit exterior EVA work routes;
- `local_control_contract` and `local_control_station` equipment;
- `backup_life_support_contract` and the local `emergency_oxygen` network.

Every space now carries a `damage_control_sector` field. Treat this as an operational grouping, not a new pressure boundary by itself.

Exterior work zones are locations for access/state logic. They are not pressurised rooms and do not imply that a human can cross moving machinery without the restrictions on the access link.

Backup life-support objects buy time. They do not make a leaking space safe, supply indefinite heat rejection, or cause unreachable occupants to teleport into a refuge.