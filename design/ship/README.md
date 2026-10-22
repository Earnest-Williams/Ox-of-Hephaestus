# Full ship preparation baseline

This directory contains the current **Ox of Hephaestus full-ship physical world model, v0.4**.

It is deliberately **not integrated into the runnable Evennia world in this change**. The existing seven-compartment proving ground remains the implemented runtime. These files prepare the later integration by giving it a stable spatial, equipment, access, utility, maintenance and survivability source model.

## Current files

- [`ox_full_ship.json`](ox_full_ship.json) — canonical current-installation world data. It is stored minified in Git to keep the prepared source compact; whitespace is not semantically significant.
- [`ox_ship_world.schema.json`](ox_ship_world.schema.json) — structural schema for the prepared model.
- [`Ox_Ship_Wire_Render_v0.4.html`](Ox_Ship_Wire_Render_v0.4.html) — standalone interactive inspection render.
- [`MODEL_GUIDE.md`](MODEL_GUIDE.md) — modelling boundaries and future integration rules.
- [`FIXED_SPINE_LAYOUT.md`](FIXED_SPINE_LAYOUT.md) — bridge, fixed-spine compartments, transit/logistics, adjustable-gravity Engineering shop and debris protection.
- [`SURVIVABILITY_AND_MAINTENANCE.md`](SURVIVABILITY_AND_MAINTENANCE.md) — damage control, EVA maintenance, local machinery control and backup life support.

## Scope

The v0.4 model contains 421 spaces, 517 traversable access links, 692 equipment objects, 1,041 service nodes, 1,036 service edges and 1,092 isolation points. It includes the six cargo drums, eight habitation arcs, compartmentalised fixed spine, axial personnel and heavy-logistics transport, WR-01 variable-gravity Engineering workshop/stores rotor, layered debris protection, sectionalised fire mains, external maintenance routes, 33 local machinery-control stations and distributed backup life support.

The model distinguishes original design intent, current physical installation and available documentation. **Current physical installation is the future world-authoritative layer; character beliefs remain private to the cognition system.**

## Verification of the prepared artifact

The source artifact was checked before import with 132/132 core reference/topology checks and 2,353/2,353 deeper casualty/topology checks. Those checks verify the design data as an internally connected model. They do **not** prove that the current Evennia runtime implements any of it.

## Integration boundary

A later implementation PR should add a loader/adapter and migrate gameplay incrementally. Do not replace the existing world bootstrap merely by deserialising this file. Runtime integration must preserve the established Ox authority rules: Evennia owns physical state, access, inventory, time and action consequences; the external handler owns private cognition and never receives hidden world truth merely because it exists in this JSON.

## v0.5 ship-completion candidate (design-only)

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
- [730-day, 40-person endurance ledger](ENDURANCE_LEDGER_v0.5.md):
  explicit 32 t stored food, oxygen electrolysis, CO2 regeneration,
  water-makeup balance and actual chemical byproducts.
- [Pressure-cell separation and gas envelope](PRESSURE_CELL_CLOSURE_v0.5.md):
  46 sectional personnel-trunk cells, 8 independently isolatable HAB bridges,
  40-person whole-arc refuge interpretation, rated hatches, vacuum flywheel bays
  and material/gas volume limitations.
- [Pressure-cell machine-readable register](pressure_zone_topology_v0.5.json):
  133 elementary pressurised cells with 198 pressure-rated boundaries; includes
  gross reference envelopes where dimensions are defined.
- [Atmosphere reserve / bounded free-volume and gas-recovery design](PRESSURE_GAS_RECOVERY_v0.5.md):
  the 5.5 t two-bank gas reserve, sectional refill plumbing, 69 fixed-spine
  taps, 8 bridge crossings and honest 85/48 cell volume uncertainty.
- [Atmosphere gas reference and room-safety roles](pressure_gas_recovery_v0.5.json):
  engineering free-volume ranges, all 83 unresolved-space roles and the
  independent refill-gas topology linked to installed objects.
- [Pressure-gas casualty validator](check_pressure_gas.py):
  independent stock, pressure, valve, two-bridge outage and eight
  negative-mutation tests.
- [Pressure-cell validation](check_pressure_cells.py): independent geometric
  and pressure-boundary verification with six deliberate negative cases.
- [B′ mechanical and casualty validator](check_bprime_mechanics.py):
  independent port geometry, equipment, load-path, movement/reachability and
  eight deliberate mutation checks.
- [Focused design validator](check_v05_candidate.py): stdlib model-reference,
  geometry, mass/O2 and negative-regression checks; runnable without Evennia.

Run `python design/ship/check_v05_candidate.py` and `python design/ship/check_bprime_mechanics.py`, plus
`python design/ship/check_pressure_cells.py` and `python design/ship/check_pressure_gas.py`, from the repository root.
The v0.5 candidate is a *simulation-operational* engineering proposal,
not real-world construction or certification data. No Evennia or dashboard
code is changed in this branch. The earlier full-ship integration
PR #101 remains separate and unmerged pending design completion.
