# Full ship preparation baseline

This directory contains the current **Ox of Hephaestus full-ship physical world model, v0.4**.

It is deliberately **not integrated into the runnable Evennia world in this change**. The existing seven-compartment proving ground remains the implemented runtime. These files prepare the later integration by giving it a stable spatial, equipment, access, utility, maintenance and survivability source model.

## Current files

- [`ox_full_ship.json`](ox_full_ship.json) — canonical current-installation world data.
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
