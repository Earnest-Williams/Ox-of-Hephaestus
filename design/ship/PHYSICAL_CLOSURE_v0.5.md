# Ox of Hephaestus — physical-volume and access-envelope closure, v0.5

**CURRENT 23 OCTOBER 2026 v0.5 CANDIDATE:** 133/133 physically bounded nominal pressure cells, 208 rated access boundaries, 100,772.940 m³ gross / 65,832.797–88,021.802 m³ planned free-air reference; **802 maintained equipment objects, 13 inventory accounts, 42 maintenance groups**. The six cargo-drums now have individual passenger indexers and freight docking collars; the four separate, finite industrial/hazardous bins begin empty. Read [machinery/industrial disposal closure](MACHINERY_AND_FINITE_DISPOSAL_CLOSURE_v0.5.md) and [physical closure](PHYSICAL_CLOSURE_v0.5.md). Earlier dates/counts later in these files refer to earlier v0.5 milestones only. All source volumes are design geometry, not as-installed measurements or certified safe access.


**23 October 2026 · candidate only · no canonical v0.4 promotion, Evennia integration or manufacturing qualification.**

## Selected whole-ship reference

The actual Ox remains a **950 m** working bulk freighter with an uninterrupted **16 m diameter fixed spine**, two **3.0 m** clear personnel bores, one **5.5 m** clear axial heavy-logistics bore, six separately rotating cargo drums, eight **38° B′** habitation arcs and an independent WR-01 rotor.

This revision dimensionally accounts for **all 133 independently isolatable nominal pressure cells**. The gross reference is **100,772.940 m³**, with a deliberately broad **65,832.797–88,021.802 m³ planning free-air envelope** (approximately **79.270–105.989 tonnes** nominal dry gas at 20°C, 101.325 kPa). **Not one** installed usable-free-air measurement is claimed. The existing two separate **2.75 t** refill-air banks and **249.2 kg** protected oxygen supply are unchanged, and cannot restore an arbitrarily large portion of that initial atmosphere. There remain **208 individually rated pressure-boundary access links**, **26 registered vacuum spaces**, and **83 cargo/machinery spaces not presumed breathable**. The forty-person figure is design maximum, not standing crew.

The old 101/32 and 107/26 counts in detailed historical sections are earlier v0.5 development checkpoints, not the selected reference.

## Fixed 16 m spine and external refit pods

The checked physical model relocates **74 reference geometry records** to eliminate the former pressure-room/crew-trunk, crew-room/industrial-plant and room/room clashes. A global circle/box/axial-interval sweep now checks every dimensioned static box or cylindrical tube against the others, *including* originally unsized rooms and dimensioned industrial service spaces; it does not merely reject selected admission samples.

The aft long-life stores, food, fluid and critical-spares holdings are allocated to separately enclosed outboard **stern sidecar pressure pods**, extending approximately 7.1–14.6 m to starboard where needed. The emergency command, aft communications and rescue spaces use a distinct short outboard run. This is a limited, already-refitted ship extension: it does not widen or obstruct the standard fixed crew/logistics bores and remains within the present planned dry-mass allowance. Short **independently pressure-rated access necks**, mounted outside the cart sweep, remain part of the selected assembly; no fictional shared gas volume is credited for their unmeasured interiors.

Axial logistics stop labels are functional **sled/layby activity stations within the existing 5.5 m tube**, *not separate gross boxes occupying the same bore twice*. The forward shield is a **penetrated multilayer collar** with three protected tube openings, not a solid plate across active transport.

Three former interior cross-connectors become independently pressure-rated **external over-spine arch bypasses**, nominally **2.5 m** clear bore around radius 9.6 m with two short necks. Their approximately 182.405 m³ gross reference is counted **once per connector**. The central bypass is axially between the IX-A and IX-B passenger carriers, not inside either swept annulus. These independent pressure cells allow a crew bypass without crossing the 5.5 m freight tube or assuming the two personnel bores become one pressure compartment.

## Six drum service rings and fixed freight locks

The six original **12 × 4.6 × 4.6 m** fixed freight locks retain a 2 m nominal end allowance around the full eight-metre load box. Their farthest nominal moving-sweep radial extent is approximately 11.336 m.

Each drum's rotating receiving ring begins at radius **11.85 m**, giving a **0.514 m** minimum nominal radial exclusion from the stationary full-freight-lock rectangular envelope. It is **not** a false continuous full-pressure ring extending thirty metres axially.

Each drum uses:
- One six-metre axial freight receiving pressure annulus, radii 11.85–13.65 m.
- A separate five-metre two-person indexed-receiver pressure annulus **18 m aft of the freight station**.
- A **12.5 m × 1.6 m** rotating pressure-rated axial connector between those two independent work stations.
- A four-metre axial outer gallery, radii **13.65–16.5 m**, leading to sector-specific cargo access. Its freight-berth room label is a **nested receiving alcove**, not a newly duplicated atmosphere volume.

Thus each `PZ-DR-xx-SVC` gets **2,691.119683 m³ nominal gross**. Each separate fixed indexed service lock retains the previously established **5 m × Ø2.3 m** gross geometry but is relocated **18 m axially** clear of the freight lock, while remaining inside its corresponding 75 m drum station section. The passenger-indexed carrier has a radial guard [8.05, 11.65] m, stays in that second axial station and cannot operate with the fixed freight adapter extended. A jammed collar can strand people or disable that station without magically defeating the other five drums.

## Workshop rotor, pressure passages and stores

WR-01's once-erroneous near-axis solid hub becomes a separate rotating **annulus radii 8.8–12.8 m, 10 m axial length**, preserving at least 0.8 m nominal fixed-spine radial clearance. The four-metre independently captured WR-IX cabin occupies its own x=480 m station and nominal 10.5 m radial orbit; it does not share gas with the fixed spine or hub.

At approximately **60 m radial operating station** the actual shop spaces are separated axially: parts wash [472–480] m, mechanics [480–498] m, welding [498–508] m. The immediate stock locker is nested inside mechanics rather than added again. The opposite **20 m radial store carriage** likewise has non-overlapping material, spares and tool-crib bays. Installed load/mass and variable balancing requirements are preserved.

The seal-monitored **3 m clear pressure passages** terminate at the respective pod boundaries. The shop passage is **41.2 m** deployed at the selected station, with bounded length variation **5.2–56.2 m** as the carriage moves; the stores passage is **2.2 m** nominal with bounded extension **2.2–19.2 m**. The nominal gross is counted at the selected operating position, **not asserted as constant gas volume** under telescoping. Physical pressure equalisation, sliding-seal integrity, replenishment and power/thermal access constrain each movement.

## Testable failures and authority

`check_pressure_geometry.py` now independently recomputes every newly admitted pressure envelope, checks the entire fixed-spine dimensioned static geometry, verifies six separate drum indexed/freight stations and nested receiving volumes, distinguishes movable workshop volume from actual installed gas, checks pressure boundaries and preserves HAB-04/HAB-08 daughter-volume subtraction. Fifteen deliberate invalid mutations are rejected, including restored overlaps, false gas measurements, failed rotary-door closure, oversized swept equipment, an obstructed forepeak and telescoping volume claims. The ordinary ship geometry, gas, waste and B′ mechanics suites remain separate checks.

The `approved_geometry_changes_v0.5.json` witness and `fixed_spine_relayout_v0.5.json` identify the intended reference changes independently from the as-published v0.4 file. Data values are *design constraints*, not measured installation; crew may discover seized seals, misleading labels, locally welded-up service corridors and obsolete drawings. Such physical variation requires actual world-owned inspection, isolation, repair and pressure retest. **Do not assume all 133 cells are presently serviceable, simultaneously pressurised, or safe for unsuited entry.**

## Design scope boundaries

The design closes pressure-volume bookkeeping and proposed nonintersecting station reference envelopes at *simulation-operation fidelity*. It does **not** claim a construction-quality moving-contact/FEA model, fit-to-survey pressure vessel drawings, completed atmosphere commissioning, or current crew access permission. All nominal volumes can be recomputed without inventing additional crew, stored air or voyage mass. The canonical `ox_full_ship.json` v0.4, old standalone renderer and PR #101 remain untouched.
