**CURRENT 23 OCTOBER 2026 v0.5 CANDIDATE:** 133/133 physically bounded nominal pressure cells, 339 rated access boundaries, 100,772.940 m³ gross / 65,832.797–88,021.802 m³ planned free-air reference; **808 maintained equipment objects, 15 inventory accounts, 42 maintenance groups**. The six cargo-drums now have individual passenger indexers and freight docking collars; the four separate, finite industrial/hazardous bins begin empty. Read [machinery/industrial disposal closure](MACHINERY_AND_FINITE_DISPOSAL_CLOSURE_v0.5.md) and [physical closure](PHYSICAL_CLOSURE_v0.5.md). Earlier dates/counts later in these files refer to earlier v0.5 milestones only. All source volumes are design geometry, not as-installed measurements or certified safe access.

# Ox of Hephaestus — 40-person waste and byproduct disposition, v0.5

**22 October 2026 · Ship-design candidate only.** This is installed-system
identity, bounded capacities, and failure logic for the long-serving Ox.
It is not an Evennia runtime implementation, a fabrication drawing, or a
claim that the installed machinery is currently fully serviceable.

## Physical installation

Each independent full-capacity ECLSS train remains aboard its existing
habitation arc: **A in HAB-06**, **B in HAB-08**. No new ECLSS train was
invented. Existing WASTE-PROC-A/B and water/waste rotary interfaces have
new explicit operating limits; six additional maintainable pieces of
equipment were admitted:

| Installed item | Position | Function |
| --- | --- | --- |
| ECLSS-A-H2-VENT / ECLSS-B-H2-VENT | HAB-06 / HAB-08 service gallery | Segregated electrolysis hydrogen exterior discharge and 0.25 kg temporary buffer each |
| ECLSS-A-CO2-VENT / ECLSS-B-CO2-VENT | HAB-06 / HAB-08 service gallery | Separate regenerated CO2 exterior discharge and 50 kg temporary receiver each |
| WASTE-RESIDUE-HOLD-A/B | STORE-FLUID-AFT | Sealed cassette receivers, 8 t nominal holding each |

The four process-vent lines are a new **byproduct_exhaust** service network:
eight process/outlet nodes, four pipe edges, and eight independently
accessible, normally closed source/hull isolators. Each source is
associated with exactly one medium and one ECLSS train; there is no common
hydrogen/CO2 line, no intentional exhaust into occupied air, and no
connection to the vessel's 5.5 t breathing-gas refill network.

The exterior hull outlet is on the *rotating* section, not a fictional
uninterrupted pipe through the stationary spine. Pressure-hull penetration
and outlet jet clearance relative to EVA access, bridge mechanisms and
indexer swept hardware remain **as-installed survey items**; inability to
verify that clearance prevents opening the discharge. A closed isolator
is not a source of infinite waste-processing capacity.

## Chemistry and 730-day voyage mass transfer

At **40 people**, O2 consumption is **35.6 kg/day** and the design
water electrolyser requires approximately **40.05 kg/day** of treated
water at the prescribed 1.125 kg water/kg O2 stoichiometry. The
counterpart hydrogen is **4.45 kg/day**, or **3,248.5 kg across 730
days** if all O2 is produced by this process and the hydrogen is
discharged. Each ECLSS H2 vent has a nominal 6 kg/day capacity; the
0.25 kg local buffer affords about 1.35 hours at design consumption
rate, not days. If its pathway closes, the affected electrolyser must
throttle or shut down before buffer overpressure. The unrelated local
and refuge breathing oxygen remains available subject to its own
independent duration and pressure constraints.

The two regenerable CO2 units each have 45 kg/day removal capacity.
Forty people produce **43.2 kg/day**, or **31,536 kg over 730 days**.
Each isolated vent is rated at 50 kg/day with a distinct 50 kg
temporary receiver. A healthy sorbent bed can continue only as long
as desorption, storage, energy and heat rejection remain supportable.
A CO2 receiver approaching full disables further regeneration;
ongoing respiration then increases cabin CO2 as active sorbent
capacity is consumed. CO2 has not been chemically destroyed.
Hydroponic gas-processing credit is not required for survival.

Released hydrogen and CO2 are real departures from the vessel's
internal mass ledger: their elemental mass originated in the
voyage's water/oxygen/respiration/food streams. A simulation must
not debit a source and simultaneously mint the gas in an unrelated
inventory. External dump decisions have observable line flow,
temperature/pressure evidence and loggable valve operations.

## Greywater and blackwater collection

Existing separate eight-arc **greywater and blackwater** rings feed
the independent WASTE-PROC-A/B units. Each unit is assigned
40-person operation, nominally **1,100 L/day greywater** and
**120 L/day blackwater** processing, with **500 L local grey** and
**250 L local black** finite upset buffering. Gross domestic water
circulation remains 1,000 L/day at the 40-person reference, with
90% water recovery *only after proven treatment*. These capacities
are screens, not a claim that daily grey plus black flows add to
1,220 L/day or that every stream is new makeup-water consumption.

The existing fixed receiver equipment at WATER-FWD now has a
**10 m³ greywater** tank and **2 m³ blackwater** tank. The previous
network had fixed tank-to-rotary-side links but lacked the final
rotary-side-to-hab-manifold connection. Four new double-isolated
wet branches resolve that actual topological defect:

- EDGE-WET-GREYWATER-A-ROTARY / -B-ROTARY
- EDGE-WET-BLACKWATER-A-ROTARY / -B-ROTARY

Each crossing uses *two separately controlled local valves*:
one in ROTARY-UTIL-A/B and one in the HAB-06/08 service gallery.
Both are normally closed. They are independent of passenger
indexers, emergency gas replenishment and their neighbouring
electrical/cooling sleeves. The eight-bridge utility-ring
topology offers an alternate manifold path.

The four pre-existing fixed-receiver feed edges also now carry explicit
room-by-room **A/B fixed-spine service-raceway paths**, from WATER-FWD
through the twelve applicable sectional personnel-trunk locations to
ROTARY-UTIL-A/B. Lines run **beside**, not in the stated 3 m clear
personnel-cart bore, so a closed crew pressure shutter does not
automatically close the adjacent wet plumbing. The source and
rotary-side isolation devices remain real and separate.
A lost middle section of the wet line still requires physical
isolation and repair; a nominal edge in the network graph is not a
magically surviving tube. The checker rejects a missing or
misordered route station.

A single disabled rotary wet crossing leaves potential access
through the other correctly isolated crossing. Losing *both*
disconnects the fixed receiver despite the tank still existing:
the crew must isolate the problem, use bounded local receivers,
reroute only along approved compatible plumbing, stop affected
water use, or restore a union. No tank is automatically
reachable because its symbol appears in the ship schematic.

## Sealed nonaqueous residues

WASTE-PROC-A/B dewater and stabilise received solids rather than
making them disappear. The reference **10 kg/day** of dried
sanitary residual across 40 people is **7.3 t over 730 days**;
two separate sealed receivers provide **16 t nominal total**,
leaving contingency for filters and other *compatible* dried
residue, not an assurance of unlimited industrial-waste capacity.
Medical/isolation contamination and flammable or incompatible
materials demand segregated containment/handling. Liquid
unprocessed blackwater is not poured into a dry-solids bin.

The `INV-WASTE-RESIDUE` ledger is **zero tonnes at departure**
with 16 t installed capacity. Subsequent accumulation transforms
already carried food, cartridges and other mission inputs. This
generated stock does **not** add 16 t to departure mass or
create new net matter. Emptying at port remains an operational
task, as does any extra voyage refuse assessment.

## Degraded modes and physical consequences

- **A H2 vent cannot verify its outside path:** isolate both
  valves, use only 0.25 kg permitted local buffer and inhibit that
  train's electrolysis before capacity is exhausted. Main
  oxygen output is not magically restored by CO2 vent equipment.
- **Both H2 vents unavailable:** oxygen generation from
  electrolysis ceases when local buffers fill. Protected oxygen
  and the other ECLSS functions have independent limits and
  cannot replace indefinite normal oxygen production.
- **A CO2 outlet blocked:** keep intake scrubber available only
  while sorbent state and its 50 kg receiver allow. Continuing
  full crew load indefinitely without desorption is invalid.
- **One rotary wastewater union fails:** close that wet service
  at both ends, backfeed through the other union where the
  bridge ring and isolation are healthy; do not assume
  contiguous physical access across a closed pressure door.
- **Both wet unions fail:** fixed grey/black tanks are
  unreachable from the HAB arcs even if electrically healthy
  and empty. Local process/buffer and waste-use restrictions
  dictate actual endurance.
- **Dry waste bin fills:** switch to a verified independent
  cassette where available or stop generating incompatible
  residue. The inventory is a finite physical stock.

All intervention proceeds under local permits, sensor/hand
gauge verification, isolated valve states, spare availability,
and world-owned repair confirmation. A completed work receipt
or unchanged JSON nominal condition alone proves nothing.

## Model preservation / check status

The candidate retains **421 spaces, 517 access links, 133
independently isolatable pressure cells and 208 rated
pressure boundaries**. The current machinery data has **786
equipment objects, 1,180 service nodes, 1,176 service edges,
1,251 isolation points and 11 inventory accounts**.
Forty-two maintenance groups cover the six new installed
units without adding an extra maintenance cohort.

The `check_waste_byproducts.py` regression proves no
hydrogen/CO2 cross-connection, properly paired hull isolators,
finite buffers and departure inventory, dual A/B alternate
wastewater delivery, and failure of both rotary routes.
It includes nine deliberate failure mutations. This is
network and accounting integrity, not a pressure-vessel
qualification or actual live-world test.

**Remaining physical closure:** correct overlapping
fixed-spine room/trunk envelopes in the 32 unsized pressure
cells and finish the selected 38° habitation pressure-head
solid interference survey. Preserve old/current/refit
configuration differences. Do not promote v0.5 or change
the Evennia/UI integration branch in this PR.
