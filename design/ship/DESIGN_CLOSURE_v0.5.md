# Ox of Hephaestus — full-ship design reconciliation v0.5 (candidate)

**22 October 2026 · Design-only branch · Simulation-level engineering**

This is the first constructive ship-completion increment after putting Evennia/UI
integration on hold. It is not a rewrite of the Ox into an unrecognisable ship,
and it does not require real-world pressure-vessel certification to settle
the playable arrangement. The candidate artifact is
**ox_full_ship_v0.5_candidate.json**. The currently published
**ox_full_ship.json v0.4** remains canonical until the full-ship design
candidate is explicitly promoted. The v0.4 standalone wire render remains a
historical geometry snapshot, not a claim that the v0.5 candidate has already
been visualised.

## Status: what is established, what remains a choice

The ship itself is a 950 m industrial bulk freighter with a 16 m fixed spine,
six independently rotating cargo drums, two flywheel installations,
substantial fixed power/thermal plant, and central rotating habitation.
**Independent pressure-rated habitation arcs and design provision for 40
people are established constraints.** The 40-person figure is neither the
minimum safe operating crew nor the ordinary working complement.

The v0.4 model gives a reference implementation of eight habitation arcs and
a 38-degree tangent-ring/pressure-section schematic, with four ten-cabin
residential arcs (HAB-01, 03, 05 and 07), four specialist arcs, two indexed
spine–habitation interfaces, and eight inter-arc pressure bridges. The
recovered v0.5 pressure-head/frame study used a **different, provisional
41-degree arc**, and its 3D CAD is not a direct geometric authority for the
38-degree world model. Neither study proves a fabricated hull; the operator
model may nevertheless select credible mechanisms and failure consequences.

The Ox originally had comparatively standardised, orderly utility systems.
Its *current installation* has mixed-generation panels, revised cable
routes, local retrofit gateways, patched machinery and inherited practices.
Neither the source-era blueprint nor the crew's remembered version replaces
the measured present-day physical ship.

## What this increment actually changes

| Subject | v0.4 issue | v0.5 candidate correction |
| --- | --- | --- |
| Heavy logistics | Rectangular 4.2 x 4.2 m sled claimed inside 5.5 m diameter tube | 3.8 x 3.4 x 8.0 m complete load bounding box; 50 t ordinary / 100 t restricted ratings unchanged |
| Service route identity | 56 power/air/water/cooling/effluent links passed through arc-group identifiers, not rooms | 112 group occurrences in those 56 links replaced with real HAB-nn-SERVICE-GALLERY spaces |
| Bridge maintenance | Eight BR-nn **rooms** misidentified as equipment IDs | Eight new BR-nn-UTILITY-SLEEVE equipment assemblies and corrected maintenance targets |
| Arc-end closures | Sixteen bridge-facing pressure hatches were only graph edges | Sixteen individually identified end-hatch equipment assemblies linked to those graph edges |
| Modification provenance | Three modification records used undefined ERA-LIFE-EXTENSION | Remapped to existing ERA-LIFE, retaining the modification histories |
| Maintenance coverage | No grouped maintenance procedures for much of the principal plant | 36 grouped procedures cover every one of the candidate's 720 installed equipment IDs |

The next incremental addition also gives the ship two oxygen-production
subassemblies and two regenerable CO2-removal subassemblies, plus an
explicit 32 t long-voyage food inventory. These serve the existing
A/B ECLSS trains rather than fabricating a third full-capacity train.
There are now 720 installed modeled equipment objects, 36 maintenance
groups and eight explicit inventory accounts. See ENDURANCE_LEDGER_v0.5.md.

No physical compartment or access-link identities were renamed, and no
current equipment condition, inventory amount, dry-mass planning envelope or
fictional propulsion coefficient was silently revised. Equipment identities
were added; the 421-room / 517-link spatial model was preserved.

## Cargo and fixed-spine geometric fit

The logistic passage is a circular, **5.5 m clear-diameter** freight tube.
A 4.2 x 4.2 m square has a 5.940 m diagonal and cannot fit inside it.
The revised *complete* load envelope has a corner radius from the tube axis of

    sqrt(1.9² + 1.7²) = 2.550 m

versus the 2.750 m available radius. There is approximately **0.200 m
radial geometrical clearance at the most distant corner**, before any chosen
operational stand-off beyond the stated clear envelope. The sled body,
restraints, load, manipulators and any protruding wheels must all remain
inside the 3.8 x 3.4 x 8 m bounding box: 3.8 x 3.4 is not merely the crate
dimensions. A verified freight lock must admit this box without touching its
stopped/indexed/hard-locked drum portal.

The usual 50 t and exceptional 100 t sled mass allowances are permissions
subject to restraints, acceleration, route load limits and available
braking, not a claim that every shape or material with that mass fits. Port
bulk handling remains the only normal way to redistribute hundreds of
thousands of tonnes of commercial loose bulk.

Two separate 3 m personnel trunks retain manual passage even when battery
carts are unavailable; neither trunk is the commercial freight conveyor.

## Habitation geometry and volume reconciliation

At reference radius 73.15 m, a 38-degree arc is approximately 48.52 m
along its centreline. Eight ideal 9.5 m-diameter circular sections at this
length enclose approximately **27,511 m³ of gross tube envelope** before
subtracting fit-out and accounting separately for the curved heads.

The three nominal full-length fixed-spine movement tubes (two 3 m round
personnel trunks and a 5.5 m round freight trunk) add approximately
**36,001 m³ of gross cylindrical envelope** over 950 m. The combined
geometric reference is thus about **63,511 m³**, *before* adjusting for
structural displacement, bulkheads, sealed/vacuum zones, pressure heads and
other occupied work spaces.

These numbers are **not** the ship's exact free-gas volume. Nevertheless,
they make an older 30,000 m³ whole-vessel pressure-volume assumption
unusable. Future atmosphere ledgers must enumerate pressure zones, actual
free volume, stored gas, leakage and repressurisation costs. The current
5.5 t arc-refill-gas allowance is not permission to fill the entire ship.

At a 45-degree module pitch, the 38-degree schematic leaves a 7-degree
angular gap. The 73.15 m centreline chord is approximately **8.93 m**;
the 41-degree trial gap would be only 4 degrees and approximately **5.10 m**.
The inter-arc bridge must therefore be sized against its actual adopted
configuration. The v0.5 framework/hatch trial must not be dropped into the
current model without this geometry reconciliation.

See HAB_PRESSURE_ACCESS_v0.5.md for the mechanical and operating interfaces.

## Life support and food: 40 people, no fictitious third train

Two main ECLSS trains remain independent physical units. Each has a
protected-duty capacity for **40 people**, provided distribution and heat
rejection are serviceable. At the current reference rates, forty occupants
consume approximately **35.6 kg O2/day**, generate **43.2 kg CO2/day**,
and demand **1,000 L/day domestic water**. At 90% domestic recovery, the
domestic unrecovered share is **100 L/day**, before cultivation,
processing, reserve degradation and extra losses. The published 162 t
730-day makeup budget is *not* simply 100 L x 730 days: its other uses
now have a provisional 162 t breakdown including domestic unrecovered water, normal oxygen electrolysis feed, crop/food processing and technical rejects; see ENDURANCE_LEDGER_v0.5.md. The split is a planning contract, not a measured hydroponic yield or exact closed-loop balance.

The two independent HAB-04/HAB-08 refuge packages retain
40 people x 72 h each; each refuge oxygen allocation is 106.8 kg.
Eight arc-local isolation packages retain ten people x 12 h each;
each local oxygen bank is 4.45 kg. Protected stock is therefore
2 x 106.8 + 8 x 4.45 = **249.2 kg O2**, with no double counting.
The two survival craft each provide 40 people x 30 days as a
separate, deepest local protection layer. No small refuge equipment
cupboard is mistaken for the living volume of forty people.

Hydroponics is fresh-food supplementation, not the primary calorie
supply. A stated 80 m² / 20 kW cultivation plan remains a provisional
load and yield assumption, not evidence of complete food independence.

## Power and thermal operation

The nominal demand is 1.55 MW; demanding operation is 2.6 MW; the
wider protected-service budget is 0.75 MW. A single auxiliary generator
supplies 0.65 MW in the deliberately shed operating schedule.
**These two protected/emergency figures are not interchangeable.**
When limited to a single auxiliary, the ship must shed at least the
100 kW difference and any additional heat-rejection burden, while
prioritising pressure management, life support, protected circuits,
communications, medical needs and essential bearing/thermal support.

Power can be lost locally even if generation is healthy. Distribution
faults, rotary interfaces and heat-rejection limits are separate
operating problems. The 3.3 MW combined continuous generation contract
remains below the 4.5 MW combined nameplate total for existing reasons.
The FTL and sublight drives retain their explicitly fictional independent
propulsion-energy contracts; hotel-load generator figures must not be
misapplied as propulsion power.

## What the maintenance expansion actually means

The original fourteen group definitions were useful but incomplete, and
some named the wrong object class. The candidate now has 36 procedures
whose combined target sets cover all **720 modeled equipment IDs**.
These are grouped schedules, not 720 individually hand-authored manuals.
Each carries representative intervention time, skills, parts and a
verification predicate. A passed checklist is not automatically
a repaired machine. Actual spares, access, isolation, elapsed work time,
condition history and sensor agreement remain needed for gameplay.

Major new coverage includes generators, primary power buses, batteries,
rotary utility interfaces, heavy transit and passenger carts, radiators,
water treatment, propulsion, indexed transfers, cultivation, protected
lighting/comms, machine/fabrication equipment, and the bridge hatch
assemblies themselves. Eight forgotten habitation DC lockers and the
non-service-side bearing lubrication skids are brought into existing
tasks.

## Remaining engineering work, in useful order

1. **Resolve HAB physical envelope**: one arc sweep, true curved-shell
   end/head geometry, bridge span, pressure-zone/free volume and the
   two independent indexer swept envelopes. Select simulation geometry
   without requiring fabrication certification.
2. **Complete coupled physical access**: cradle-to-frame redundant
   attachments, paired pressure-head seals/dogs, rotary carrier movement,
   local emergency stops and recovery manoeuvres. Report what becomes
   inaccessible after particular failures.
3. **Close pressure-gas, water and long-voyage inventory ledgers**:
   zone volumes, refuge/use inventories, consumption, refill constraints,
   by-products and losses at 40-person design load.
4. **Close system dependencies and plant state machines**:
   electrical switching, thermal rejection, ECLSS, waste, cargo, fire
   mains and exterior maintenance; test actual isolations, backfeeds and
   repair routes instead of declaring everything healthy.
5. **Build the current vessel's as-found condition ledger**:
   mixed-generation panels, unstandardised spares, equipment-specific
   degraded modes, documentation reliability and normal watch practice.

After the remaining physical interfaces and ledgers agree, we should promote the v0.5 candidate into ox_full_ship.json,
regenerate the wire-render snapshot and rebase the presently unmerged
Evennia integration PR. **Do not turn unfinished design into game rules
by accident.**
