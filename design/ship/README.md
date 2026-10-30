**CURRENT 23 OCTOBER 2026 v0.5 CANDIDATE:** 133/133 physically bounded nominal pressure cells, 339 rated isolation boundaries (208 previously rated plus 131 unknown-environment thresholds), 100,772.940 m³ gross / 65,832.797–88,021.802 m³ planned free-air reference; **808 maintained equipment objects, 15 inventory accounts, 42 maintenance groups**. The six cargo-drums now have individual passenger indexers and freight docking collars; the four separate, finite industrial/hazardous bins begin empty. Read [machinery/industrial disposal closure](MACHINERY_AND_FINITE_DISPOSAL_CLOSURE_v0.5.md) and [physical closure](PHYSICAL_CLOSURE_v0.5.md). Earlier dates/counts later in these files refer to earlier v0.5 milestones only. All source volumes are design geometry, not as-installed measurements or certified safe access.

> **Ship design standard — VERISIMILITUDE, NOT NASA APPROVAL.**
> [Read the binding ship engineering design philosophy](SHIP_ENGINEERING_DESIGN_STANDARD.md).
> The Ox is a fictional, repeatedly repaired working freighter. We require
> believable layout, causal systems, imperfect evidence, operational tradeoffs
> and meaningful damage/repair consequences, **not** construction-ready plans,
> fabrication qualification, agency approval or certification-level analysis.
> Finish the playable design when these criteria are met.

# Full ship spatial integration and v0.5 engineering candidate

This directory contains the current **Ox of Hephaestus full-ship physical world model, v0.4**.

The published `ox_full_ship.json` **v0.4 source is materialised in Evennia** as 421 persistent canonical rooms and 1,034 exits for the 517 authored physical connections. Since G19 the exits are open to ordinary characters behind world-owned access gates. The Developer-only authenticated read-only wire terminal presents separately persisted world spatial conditions over the *matching v0.4 drawing*. The autonomous crew still runs on the seven-compartment proving ground.

The separately validated **v0.5 engineering candidate** (topology-identical to v0.4) supplies the operational register: finite resource budgets, all 133 dimensioned pressure cells, gas stores and 808 equipment units, which G19 simulates under the installed physics clock. It has **not** been promoted to `ox_full_ship.json` or a regenerated v0.5 renderer. Per-family evidence tiers are in the [G19 equipment-family audit](G19_EQUIPMENT_FAMILY_CLOSURE_AUDIT.md); verified scope and open items are in the [G19 acceptance record](G19_ACCEPTANCE_RECORD_2026-10-29.md).

## Current files

- [`ox_full_ship.json`](ox_full_ship.json) — canonical current-installation world data. It is stored minified in Git to keep the prepared source compact; whitespace is not semantically significant.
- [`ox_ship_world.schema.json`](ox_ship_world.schema.json) — structural schema for the prepared model.
- [`Ox_Ship_Wire_Render_v0.4.html`](Ox_Ship_Wire_Render_v0.4.html) — standalone interactive inspection render.
- [`MODEL_GUIDE.md`](MODEL_GUIDE.md) — modelling boundaries and future integration rules.
- [`FIXED_SPINE_LAYOUT.md`](FIXED_SPINE_LAYOUT.md) — bridge, fixed-spine compartments, transit/logistics, adjustable-gravity Engineering shop and debris protection.
- [`SURVIVABILITY_AND_MAINTENANCE.md`](SURVIVABILITY_AND_MAINTENANCE.md) — damage control, EVA maintenance, local machinery control and backup life support.
- [`EVENNIA_INTEGRATION.md`](EVENNIA_INTEGRATION.md) — installed v0.4 topology, G19 crew traversal gates and migration sequence.
- [`G19_ACCEPTANCE_RECORD_2026-10-29.md`](G19_ACCEPTANCE_RECORD_2026-10-29.md) — G19 requirement matrix, exact-head test results, open blockers and deferred items.
- [`G19_FUZZ_CAMPAIGN_2026-10-30.md`](G19_FUZZ_CAMPAIGN_2026-10-30.md) — post-merge targeted fuzzing: method, results, the fixed heat-capacity finding and open hardening items.
- [`LIVE_TERMINAL.md`](LIVE_TERMINAL.md) — privileged read-only spatial console and fail-closed drawing version policy.

## Scope

The v0.4 model contains 421 spaces, 517 traversable access links, 692 equipment objects, 1,041 service nodes, 1,036 service edges and 1,092 isolation points. It includes the six cargo drums, eight habitation arcs, compartmentalised fixed spine, axial personnel and heavy-logistics transport, WR-01 variable-gravity Engineering workshop/stores rotor, layered debris protection, sectionalised fire mains, external maintenance routes, 33 local machinery-control stations and distributed backup life support.

The model distinguishes original design intent, current physical installation and available documentation. **Once materialised into Evennia, current physical condition is world-authoritative there; the JSON is source identity and design metadata, while character beliefs remain private to cognition.**

## Verification of the prepared artifact

The source artifact was checked before import with 132/132 core reference/topology checks and 2,353/2,353 deeper casualty/topology checks. Those checks verify the design data as an internally connected model. They establish source topology and design consistency, not that every physical mechanic is simulated in Evennia. Stage-one database-backed materialisation, idempotence, access authorization, static spatial metadata and read-only terminal checks are separate CI evidence; pressure, equipment, EVA and rotary interlocks remain future runtime work.

## Live world physics status

The v0.5 candidate has a separately **opt-in** installed G17 operational
register, and G18 introduced world-owned bounded physics ticks and local
machinery commands without replacing the v0.4 source map. The next G18b
increment is documented in
[G18b coupled casualty and local recovery](G18B_COUPLED_CASUALTY_RECOVERY.md).
Its ordinary HAB hatch actuation remains distinct from NPC traversal,
which is not yet enabled.

## Integration boundary

The importer validates the v0.4 source then idempotently creates persistent spaces and exits without resetting existing room condition or descriptions; on an existing world it re-applies the G19 exit lock and rebuilds if the first exit is not yet `live_world_gated`. Doors marked `closed`, `closed_or_auto` or otherwise mechanically/pressure restricted are enforced at traversal by `world/ship_crew_access.py`, not by static metadata. Evennia remains the sole world authority; the handler maintains private cognition and receives only observations it is entitled to receive. Promoting v0.5 later must preserve room identities, deliberately migrate operational state and generate a matched visualization before the console will serve it.

### Latest design candidate engineering totals

**Earlier 23 October 2026 checkpoint — indexed drum locks:** Six separately pressurised DR-01–DR-06 fixed service-lock cylinders have been moved off the personnel-trunk bores. There are now **107/133 sized pressure cells**, **26 held**, **208 rated boundaries**, **68,310.657 m³ nominal gross** and **54,101.591–62,502.553 m³ design free-air screen**. The short station connectors and moving indexed collars remain survey items; measured free air and actual safe access remain unknown. The two independent 2.75 t air reserves remain unchanged.

## v0.5 ship-completion candidate (design-only)

> **Latest v0.5 increment — 22 October 2026:** 101 of 133 pressure cells
> have selected nominal gross dimensions; 32 remain unsized. All ten
> previously unprotected intercell doors now have rated boundary status,
> bringing the count to 208. Six freight locks have 12 m clear
> length around the unchanged 8 m full sled. HAB-04 medical isolation and
> two final-lift volumes are carved out of the respective existing arc
> shell gross, not added to it. Reference free air 54,021–62,390 m³
> (65.047–75.125 tonnes). See
> [pressure-access closure](PRESSURE_ACCESS_CLOSURE_v0.5.md).
> Earlier volume/count figures below are retained as design history.



The next ship-design increment is tracked on branch **ship-design-closure-v05**.
It does **not** overwrite or silently promote v0.4. Until the physical
configuration is reconciled, `ox_full_ship.json` remains the current
published canonical source; the existing v0.4 standalone wire renderer is
unchanged.

- [v0.5 candidate JSON](ox_full_ship_v0.5_candidate.json): a full copy
  of the linked ship world with corrected freight geometry, physical
  bridge/hatch equipment, repaired references and 42 maintenance groups.
- [Design reconciliation](DESIGN_CLOSURE_v0.5.md): the findings, changed
  assumptions, balances, preserved decisions and remaining design work.
- [B′ 38° installed mechanical interfaces](BPRIME_HAB38_MECHANICAL_CLOSURE.md):
  8 keyed centres, 16 thermally sliding outer saddles, 48 separated outer branches,
  8 isolatable flexible bridge spools, 2 main rotor bearing/drive/brake stations,
  and 2 independently indexed 30 t reference carriers.
- [Machine-readable B′ interfaces](hab_bprime_mechanical_interfaces_v0.5.json):
  stable coordinates and individual assembly identities for the selected ship.
- [Pressure ends, cradles and rotary access](HAB_PRESSURE_ACCESS_v0.5.md):
  the functional hatch/seal/indexer arrangement, failure/recovery and the
  adopted B′ 38° geometry, with earlier 41° CAD treated as a superseded trial requiring dimensional adaptation.
- [Major-system operating states](SYSTEM_OPERATING_STATES_v0.5.md):
  power, atmosphere, water, thermal, cargo, damage control and repair
  doctrine for a 40-person ship.
- [Selected B′ Issue 1.3 operating-basis reconciliation](BPRIME_ISSUE13_MISSION_RECONCILIATION.md):
  physically funded 40-person diet/crops, normal and casualty gas, water balance, 1.35 MW/730-day cartridge contract and recoverable failure paths.
- [730-day, 40-person endurance ledger](ENDURANCE_LEDGER_v0.5.md):
  explicit 56.79 t stored food with 24.82 t full-leg dehydrated fallback, 450 m² staple cultivation, oxygen electrolysis, CO2 regeneration,
  water-makeup balance and actual chemical byproducts.
- [Pressure-cell separation and gas envelope](PRESSURE_CELL_CLOSURE_v0.5.md):
  46 sectional personnel-trunk cells, 8 independently isolatable HAB bridges,
  40-person whole-arc refuge interpretation, rated hatches, vacuum flywheel bays
  and material/gas volume limitations.
- [Pressure-cell machine-readable register](pressure_zone_topology_v0.5.json):
  133 nominal pressurised cells with 339 rated isolation boundaries (including 131 unclassified-environment interfaces); includes
  gross reference envelopes where dimensions are defined.
- [Atmosphere reserve / bounded free-volume and gas-recovery design](PRESSURE_GAS_RECOVERY_v0.5.md):
  the 5.5 t two-bank gas reserve, sectional refill plumbing, 69 fixed-spine
  taps, 8 bridge crossings and all **133/133 dimensioned** pressure cells (actual free gas remains unmeasured); separate routine 7 t inert makeup is not a pressure-casualty refill.
- [Atmosphere gas reference and room-safety roles](pressure_gas_recovery_v0.5.json):
  engineering free-volume ranges, all 83 unresolved-space roles and the
  independent refill-gas topology linked to installed objects.
- [Pressure access and freight-lock closure](PRESSURE_ACCESS_CLOSURE_v0.5.md):
  12 m six-drum locks, 4-seat indexer/medical/final-lift volumes, 10 newly rated intercell doors and no double-counted parent gas.
- [Mass-balanced byproducts and finite waste](BYPRODUCT_AND_WASTE_CLOSURE_v0.5.md):
  dedicated H2/CO2 vents, finite sanitation receivers, four dual-isolated wet rotary links and consequences of single/double valve loss.
- [Waste / byproduct casualty validator](check_waste_byproducts.py):
  physical route, generated-mass, stored-residue and eight negative regression cases.
- [Geometry audit](PRESSURE_GEOMETRY_RECONCILIATION_v0.5.md):
  the admitted/held compartments and recorded spatial intersections.
- [Geometry admission validator](check_pressure_geometry.py):
  sourced volume, host-arc conservation, indexer swept guard, door and freight-lock regressions.
- [Pressure-gas casualty validator](check_pressure_gas.py):
  independent stock, pressure, valve, two-bridge outage and eight
  negative-mutation tests.
- [Pressure-cell validation](check_pressure_cells.py): independent geometric
  and pressure-boundary verification with six deliberate negative cases.
- [B′ mechanical and casualty validator](check_bprime_mechanics.py):
  independent port geometry, equipment, load-path, movement/reachability and
  eight deliberate mutation checks.
- [B′ 730-day coupled-endurance validator](check_mission_endurance.py): finite food/crop/yield substitution, dedicated inert makeup/oxygen/water supplies, 40-person power and negative fault controls.
- [Focused design validator](check_v05_candidate.py): stdlib model-reference,
  geometry, mass/O2 and negative-regression checks; runnable without Evennia.

Run `python design/ship/check_mission_endurance.py`, `python design/ship/check_v05_candidate.py` and `python design/ship/check_bprime_mechanics.py`, plus
`python design/ship/check_pressure_cells.py` and `python design/ship/check_pressure_gas.py` and `python design/ship/check_pressure_geometry.py` and `python design/ship/check_waste_byproducts.py`, from the repository root.
The v0.5 candidate is a *simulation-operational* engineering proposal,
not real-world construction or certification data. No Evennia or dashboard
code is changed in this branch. Runtime promotion and terminal/loader version
alignment are distinct release tasks; see the separate stage-one integration
PR #101 without depending on its temporary merge state.

- [Complete selected pressure reference and full fixed/rotary layout](PHYSICAL_CLOSURE_v0.5.md): 133 pressure cells, nonintersecting fixed envelopes, drum station separation and telescoping WR-01 references.

- [Unknown-environment containment closure](UNKNOWN_ENVIRONMENT_ACCESS_CLOSURE_v0.5.md): rated protection at 131 cargo/industrial/shield thresholds, local interlocks and service ownership.
- [Unknown-environment door schedule](environmental_access_boundaries_v0.5.json): physical records and handling rules for all 131 rated receivers.
- [Environmental access regression](check_environmental_boundaries.py): pressure/chemistry and dual cargo-sector gate checks.

- [Coupled pressure-and-damage-control trials](COUPLED_PRESSURE_DAMAGE_TRIALS_v0.5.md): deterministic gas mass, timed isolation, jammed hatch, crew access, cargo unknowns, finite reserve tests without Evennia.
- [Pressure damage simulator](pressure_damage_sim_v05.py) and [adversarial scenario runner](check_pressure_damage_sim.py): run `python design/ship/check_pressure_damage_sim.py` for the design-only physical/casualty trial suite.

- [Fire, smoke and thermal casualty closure](FIRE_SMOKE_THERMAL_CASUALTY_v0.5.md): coupled oxygen/fuel, HVAC dampers, smoke filtration, source-pump-and-fire-main water delivery, cooling heat rejection, failed radiator and loss-of-ventilation cases.
- [Coupled fire/thermal module](fire_smoke_thermal_v05.py) and [adversarial fire/smoke runner](check_fire_smoke_thermal.py): execute `python design/ship/check_fire_smoke_thermal.py`; existing v0.4 and Evennia remain unaffected.

- [Electrical distribution, fallible control and crew-access casualty trials](ELECTRICAL_CONTROL_EVACUATION_CASUALTY_v0.5.md): 438 electrical nodes / 450 connections / 466 isolators, delayed actuator failure, protected-feed switching, refit wiring, and 517 actual room access links.
- [Electrical/evacuation simulator](electrical_evacuation_v05.py) and [adversarial acceptance runner](check_electrical_evacuation.py): `python design/ship/check_electrical_evacuation.py`. Design-only: no Evennia, new spaces, or canon promotion.

- [Forty distinct crew across the real ship](WHOLE_SHIP_40_CREW_CASUALTY_v0.5.md): fixed 40-person, 40-space manifest, false detector evidence, containment-versus-rescue choices, route-by-route movement, finite PPE, individual hazard exposure and jammed pressure-hatch consequences.
- [Whole-ship 40-person reference simulator](whole_ship_crew_casualty_v05.py) and [adversarial matched-policy runner](check_whole_ship_crew_casualty.py): run `python design/ship/check_whole_ship_crew_casualty.py` for the design-only exercise; not 40 live Evennia agents.
