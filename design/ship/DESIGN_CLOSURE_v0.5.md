**CURRENT 23 OCTOBER 2026 v0.5 CANDIDATE:** 133/133 physically bounded nominal pressure cells, 339 rated isolation boundaries (208 previous plus 131 cargo/industrial/unknown-environment thresholds), 100,772.940 m³ gross / 65,832.797–88,021.802 m³ planned free-air reference; **802 maintained equipment objects, 13 inventory accounts, 42 maintenance groups**. The six cargo-drums now have individual passenger indexers and freight docking collars; the four separate, finite industrial/hazardous bins begin empty. Read [machinery/industrial disposal closure](MACHINERY_AND_FINITE_DISPOSAL_CLOSURE_v0.5.md) and [physical closure](PHYSICAL_CLOSURE_v0.5.md). Earlier dates/counts later in these files refer to earlier v0.5 milestones only. All source volumes are design geometry, not as-installed measurements or certified safe access.

# Ox of Hephaestus — full-ship design reconciliation v0.5 (candidate)

**Earlier 23 October 2026 checkpoint — indexed drum locks:** Six separately pressurised DR-01–DR-06 fixed service-lock cylinders have been moved off the personnel-trunk bores. There are now **107/133 sized pressure cells**, **26 held**, **208 rated boundaries**, **68,310.657 m³ nominal gross** and **54,101.591–62,502.553 m³ design free-air screen**. The short station connectors and moving indexed collars remain survey items; measured free air and actual safe access remain unknown. The two independent 2.75 t air reserves remain unchanged.


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

The adopted **B′ (B-prime)** arrangement is eight independent **38-degree**
pressure-rated habitation arcs at 45-degree pitch: four ten-cabin
residential arcs (HAB-01, 03, 05 and 07), four specialist arcs, two indexed
spine–habitation interfaces, and eight inter-arc pressure bridges. Each arc
has three principal cradle saddles, a keyed diaphragm-supported centre,
and sliding outer supports with three distinct load-path branches each.
The earlier provisional **41-degree** pressure-head/frame trial is
**superseded** as layout geometry; its component ideas require adaptation to
the actual 38-degree B′ ship. This is an operational engineering selection
for the fictional vessel, not fabrication certification.

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
| Maintenance coverage | No grouped maintenance procedures for much of the principal plant | 42 grouped procedures cover every one of the candidate's 780 installed equipment IDs |

An additional B′ mechanical increment now materialises eight isolatable pressure-bridge spool assemblies; the eight centre keyed and sixteen outer sliding saddles, with 48 physically separate outer branch identifiers; six main habitation rotor bearing/drive/brake machines; and two independent 30 t reference indexer carriers with four retracting pressure collars. The mechanical reference is `hab_bprime_mechanical_interfaces_v0.5.json`; details and failure consequences are in `BPRIME_HAB38_MECHANICAL_CLOSURE.md`.

The earlier endurance increment also gives the ship two oxygen-production
subassemblies and two regenerable CO2-removal subassemblies, plus an
explicit 56.79 t long-voyage food inventory. These serve the existing
A/B ECLSS trains rather than fabricating a third full-capacity train.
There are now 780 installed modeled equipment objects, 42 maintenance
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

At 45-degree pitch, the selected 38-degree B′ modules leave 7-degree
gaps, or approximately **8.93 m** between nominal arc-end centreline
positions at 73.15 m radius. The superseded 41-degree trial would
have left 4 degrees and about **5.10 m**. Bridge design therefore uses
the adopted 38-degree span; component and frame CAD is adapted to
that span, not the other way around.

The fitted B′ 38° ellipsoidal head port datum separation is approximately **4.281834 m**, leaving approximately **3.581834 m** for a replaceable centre bridge spool with two 0.35 m end interfaces. These port-to-port figures do not replace a net pressure-volume or gasket-contact survey. See `BPRIME_HAB38_MECHANICAL_CLOSURE.md` and `HAB_PRESSURE_ACCESS_v0.5.md` for details.

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

Normal hydroponics supplies **25% of energy** through 450 m² of productive
beds in HAB-02/06/08 under **90 kW** of normal electrical demand. The
departure food inventory holds **56.79 t** including a full-leg **24.82 t
dehydrated fallback** and **31.97 t conventional provision**, without
double-counting. The assumed crop yield depends on real water, power,
nutrient and thermal systems; it is not guaranteed on a damaged ship.

## Power and thermal operation

The adopted normal schedule is 1.35 MW (including 90 kW hydroponics and 97 kW operating margin); demanding operation remains 2.6 MW; the
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
some named the wrong object class. The candidate now has 42 procedures
whose combined target sets cover all **780 modeled equipment IDs**.
These are grouped schedules, not 780 individually hand-authored manuals.
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

1. **Finish B′ solid interfaces**: keep the selected 38-degree arc sweep and
   three-saddle architecture; develop finished curved-shell heads,
   current pressure bridge datums, net zone volume, indexed
   carrier swept envelopes, and access/maintenance reach. The old
   41-degree trial must not silently change this decision.
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

## B′ Issue 1.3 mission decision — adopted on v0.5 candidate, 23 October 2026

The earlier endurance draft contradicted B′ Issue 1.3 in stored food, calorie sourcing, electric service load and routine atmosphere make-up. We have now selected **Issue 1.3** as the preferred **40-person, 730-day** operation baseline, while retaining the later 133-cell B′ atmosphere geometry. The concrete [mass/flow reconciliation](BPRIME_ISSUE13_MISSION_RECONCILIATION.md), revised candidate JSON and the new `check_mission_endurance.py` make this testable rather than an unresolved document-only promise.

| Account | Adopted physical/operational choice |
| --- | --- |
| Food storage | **56.79 t** departure: **24.82 t dehydrated** capable of feeding the full 730 days if other food is lost; **31.97 t conventional**. Both parts counted once in the same inventory |
| Normal diet | **25% hydroponic / 25% dehydrated / 50% conventional calories**; 450 m² of existing HAB-02/06/08 growing beds, 90 kW nominal |
| Normal voyage power | **1.35 MW** including the 90 kW crops and 97 kW internal ordinary-service margin. The protected 0.75 MW and single-auxiliary 0.65 MW shed schedules remain different |
| Routine atmospheric gas | 0.01%/day reference loss from **79.270–105.989 t** initial dry gas: **5.787–7.737 t total mixed-air lost**, of which **4.456–5.958 t inert**. Normal refill comes from **two 3.5 t dedicated inert stores** via oxygen-verified ECLSS A/B mixers |
| Breach and refuge gas | Separate protected **5.5 t mixed-air casualty stock** (two 2.75 t banks); **249.2 kg local/refuge oxygen** also separate. Neither is routine leak stock |
| Water | Exactly **162 t** regular makeup: 73 domestic + 29.236 metabolic electrolysis + 35 cultivation/food + 2.100 extra O2 electrolysis for leakage + 0.740 dry-food processing + 21.924 ordinary rejects |
| B′ arc geometry | **38° selected**; previous 41° trial superseded. 133/133 dimensioned pressure cells and 339 rated boundaries, but no invented as-installed free-air measurements |

The earlier review's 4.45–5.95 t *inert loss* and our 5.79–7.74 t *total dry-air loss* describe different parts of the **same leakage**. No arithmetic dispute remains once inert (77%) and O2 (23%) are accounted separately. The older Issue 1.3 ~1.1 t extra oxygen-water term derived from a smaller pressure inventory; **2.1 t** is deliberately budgeted for the current larger v0.5 atmosphere.

The added makeup banks and metering routes are physically installed in separate forward/aft environmental control rooms; their A/B lines travel through segmented service raceways to ECLSS A/B, with a normally closed manual cross-tie. Unmixed inert gas never enters occupied rooms directly. The existing 1,500 t mission allowance and 1,187,500 t reference departure mass are unchanged; the added inventories are enumerated portions of this allowance, not new mass bolted onto the ship.

This closes the specific Issue 1.3 **source-model** contradiction. It does **not** claim that actual depletion, crop yield, gas purity, thermal load or damaged valves are automatically healthy. Nor does it automatically promote candidate v0.5 into the published v0.4 wire/Evennia model. That remains a deliberate separate release/integration operation.

## Additional pressure-cell closure

The full B′ candidate now separates the 23 sections in **each** of the two 950 m, 3 m-clear personnel trunks into **46 genuine elementary pressure cells** rather than two all-ship gas identities. The original 44 inter-section pressure doors can therefore actually isolate atmosphere when shut, without changing any room/exits. The HAB-04 medical isolation space and the A/B final indexer lifts each gain independent pressure-zone IDs, while F1/F2 flywheel service bays are classified as vacuum machinery beyond pressure airlocks. HAB-04 and HAB-08 **entire arc pressure volumes** serve as the two 40-person/72 h refuge spaces; their 40 m² REFUGE rooms contain equipment only.

The new `pressure_zone_topology_v0.5.json` identifies **133 independently sealable pressurised cells**, 339 rated access/isolation boundaries, 26 known vacuum spaces and 83 still-unclassified machinery/cargo spaces. Current reconciled geometry dimensions all **133/133 cells** with screened gross envelopes totalling approximately **100,772.94 m³**, but there is no claim that these are net breathable/free-gas volumes. See `PRESSURE_CELL_CLOSURE_v0.5.md` and the pressure validation suite; net displacement/pressure-gas inventory is the next physical closure target.

## B′ pressure-gas reserve and refill-availability closure

The next increment puts the 5.5 t single-arc breathing-air refill allowance into **two real 2.75 t banks** in separated forward/aft stores, including source/regulator, two axial fixed-spine supply headers, 69 normally shut local trunk taps, independent A/B rotary unions and an eight-arc gas makeup ring crossing all eight isolatable BR utility sleeves. The reconciled candidate now has **808 installed equipment items, 42 maintenance groups, 1,186 service nodes, 1,181 service edges and 1,256 isolation points**; all old room/link identities survive.

For the 133/133 geometrically sized pressure cells, the bounded planning free-air reference is **65,832.797–88,021.802 m³**, containing approximately **79.270–105.989 t dry air** at the chosen nominal reference state; **none of the 133 cells remains unsized**. All 83 spaces with unassigned normal pressure have a conservative hazard/access role, not a magically breathable default. A single inhabited arc requires about **3.02–3.71 t** of gas after complete evacuation under these assumptions. Both banks can refill one intact arc if the real gas path and pressure integrity are available, but two fully depressurised arcs cannot be restored from 5.5 t.

The compressed stock is separate from the existing **249.2 kg** protected refuge/local oxygen and the ship's initial charged atmosphere; it is included within the established **1,500 t mission allowance**, not added to departure mass. Reference regulators supply at most 100 kg/h each, with slower real recovery as conditions require. The independent gas-line valve graph has explicit failure consequences; two adjacent bridge-sleeve losses can deny HAB-07 refill even with both gas banks intact. See `PRESSURE_GAS_RECOVERY_v0.5.md` and `pressure_gas_recovery_v0.5.json`; unlike the gross geometry survey, these are **planning displacement intervals**, not accepted measurements of net gas volume. The remaining work is verifying fitted free-gas displacement, refill accessibility and operational resource budgets; the geometry dimensions themselves have been closed.
