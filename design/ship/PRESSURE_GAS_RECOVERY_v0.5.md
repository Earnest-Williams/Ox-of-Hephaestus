**CURRENT 23 OCTOBER 2026 v0.5 CANDIDATE:** 133/133 physically bounded nominal pressure cells, 339 rated isolation boundaries (208 previously rated plus 131 unknown-environment thresholds), 100,772.940 m³ gross / 65,832.797–88,021.802 m³ planned free-air reference; **808 maintained equipment objects, 15 inventory accounts, 42 maintenance groups**. The six cargo-drums now have individual passenger indexers and freight docking collars; the four separate, finite industrial/hazardous bins begin empty. Read [machinery/industrial disposal closure](MACHINERY_AND_FINITE_DISPOSAL_CLOSURE_v0.5.md) and [physical closure](PHYSICAL_CLOSURE_v0.5.md). Earlier dates/counts later in these files refer to earlier v0.5 milestones only. All source volumes are design geometry, not as-installed measurements or certified safe access.

# Ox of Hephaestus — atmosphere volume, refill reserve and casualty delivery v0.5

> **Earlier v0.5 increment — 22 October 2026:** 101 of 133 pressure cells
> have selected nominal gross dimensions; 32 remain unsized. All ten
> previously unprotected intercell doors now have rated boundary status,
> bringing the count to 208. Six freight locks have 12 m clear
> length around the unchanged 8 m full sled. HAB-04 medical isolation and
> two final-lift volumes are carved out of the respective existing arc
> shell gross, not added to it. Reference free air 54,021–62,390 m³
> (65.047–75.125 tonnes). See
> [pressure-access closure](PRESSURE_ACCESS_CLOSURE_v0.5.md).
> Earlier volume/count figures below are retained as design history.


**23 October 2026 · B′ 38° working ship · Engineering design candidate, not runtime**

**Source files:** `pressure_zone_topology_v0.5.json` (133 independent
pressure cells), `ox_full_ship_v0.5_candidate.json` (physical machinery,
valves and stock), and `pressure_gas_recovery_v0.5.json` (explicit
planning ranges and operating topology).

This closes a real gap: a pressure hull and ECLSS scrubber do not provide a
source of replacement *air mass* after a breach. Breathing oxygen production
does not manufacture the nitrogen/buffer mass that escaped. The Ox now has
physically separated gas stock and delivery paths. This is a functional
simulation-level engineering arrangement; the crew still needs to investigate
and act, not simply click “repressurise.”

## 1. Current pressure-cell reference — all 133 dimensioned, none assumed measured

The completed B′ cell geometry assigns defensible nominal gross bounds to **all 133 isolatable pressure cells**: the original 46 sectional personnel bores, 23 heavy-logistics bores, eight full habitation arcs, eight bridges and 48 additional individual workplaces, transfer rooms and specialist cells. **339 pressure-rated boundaries** include 131 guarded cargo, industrial and shielding thresholds. These are different from the **83 unclassified rooms** whose normal gas and safe unsuited access remain unproven.

| Present selected reference | Current v0.5 |
| --- | ---: |
| Independently bounded pressure cells | **133 / 133** |
| Gross geometric envelopes | **100,772.940 m³** |
| Screened fitted free gas (planning only) | **65,832.797–88,021.802 m³** |
| Dry air at 101.325 kPa and 20°C | **79.270–105.989 t** |
| One HAB arc full post-breach replacement | **approximately 3.02–3.71 t** |
| Rated door/threshold boundaries | **339** |
| Cargo/industrial/shield rooms not proved breathable | **83** |

The planning void fractions bound corridors, freight displacement, arc fit-out, sealed subrooms and specialist volumes; each cell's selected fraction and separate `verified_as_installed_free_gas_m3: null` are retained in `pressure_gas_recovery_v0.5.json`. Nominal geometry is not a pressure reading. This section supersedes the earlier **85 sized / 48 unsized** discussion below, retained solely as a documented design-history checkpoint.

**Routine vs casualty mass are different supplies.** The **7.0 t** `INV-INERT-MAKEUP-A/B` stock covers 0.01%/day **inert** atmosphere leakage under ECLSS oxygen-balanced mixing, while the **5.5 t** separated compressed mixed-air reserves below remain protected for actual pressure breaches. The routine 730-day estimate is **4.456–5.958 t inert** (part of **5.787–7.737 t complete leaked air**) at the currently larger pressure inventory. See [B′ Issue 1.3 endurance reconciliation](BPRIME_ISSUE13_MISSION_RECONCILIATION.md).


## 2. Two real, independent refill-gas banks

The existing **5.5 t single-arc refill allowance** is now accounted as
two 2.75 t compressed **dry breathable-air** banks. They are part of
the existing **1,500 t voyage/mission provisioning envelope**; the
departure mass is not increased.

| Bank | Physical store | Local regulation | Nominal stored air |
| --- | --- | --- | ---: |
| A — forward | `WATER-SHIELD-FWD`, unoccupied shielding/tank bay | `GAS-REFILL-REG-A` at `ENV-FWD` | 2.75 t |
| B — aft | `STORE-FLUID-AFT` | `GAS-REFILL-REG-B` at `ENV-AFT` | 2.75 t |

Each bank is identifiable installed equipment, a separate inventory
account and a *normally closed* outlet valve. Gas is a verified
breathable 21%-oxygen (molar) air mix in rated storage; it is
not the same as the **249.2 kg protected, local/refuge pure oxygen**
stock. Do not double count that oxygen or reassign it automatically
to a distant casualty.

No arbitrary permanent cylinder working pressure is asserted yet:
the real equipment has safe regulators, expansion thermal control,
leak test, purity test and pressure/flow monitoring as separate
failure modes. The current reference regulator rate is **100 kg/h
per bank**, contingent on source pressure, thermal conditions and
sound downstream valves. Both healthy banks together can
deliver *up to* 200 kg/h, not instant atmospheric replacement.

A full isolated arc refill therefore takes **no less than roughly
15.4–18.5 hours** at this reference flow, ignoring pressure ramp
and field delays; actual work is slower if a regulator derates,
heat rejection is constrained or the pressure hull still leaks.

**One bank alone (2.75 t) does not replenish an entire evacuated
arc** at the modeled lower-bound free gas (3.09 t). The intact
5.5 t supply can refill one arc with a plausible margin, but
cannot refill two completely depleted arcs (minimum combined
approximately 6.18 t). Emergency decisions become meaningful.
Port replenishment and post-loss mass-bookkeeping are necessary.

## 3. Fixed-spine gas mains are separate from breathing-air circulation

`repressurization_gas` is a new explicitly identifiable network,
not a third ECLSS train and not an imaginary fluid inside existing
`atmosphere` duct paths.

Each bank feeds a tested regulator, a separately sectionalised
annular-raceway supply header and a line of **23 axial header
sections** along the 950 m spine. The heads run from opposite ends:

- A feeds forward-to-aft beside personnel trunk A.
- B feeds aft-to-forward beside personnel trunk B.
- A central A/B cross-tie is **normally shut**, and requires
  deliberate isolation checks to open.
- All **46 sectional personnel cells** and **23 sectional
  5.5 m logistics cells** now have local, normally closed,
  pressure-rated makeup taps with separate valve identities.

A 69-tap system is not a promise that all trunk cells are one
pressure compartment or that the gas bank has enough reserve
to refill all 69. A nearby section can be isolated at its
own tap. A damaged axial header segment may cut supply to
additional downstream sections until the fault is found,
isolated and alternate route selected. Local branch valves
alone cannot restore a broken main.

The new service nodes and edges refer to real compartment IDs,
even though the physical distribution tubing is in adjacent
service raceways rather than inside the walking clearance.
The bridge between A/B trunk headers is separate from the
trunk walkable cross-connections.

## 4. Habitation pressure makeup is a separate rotating service

Two separate stationary-to-rotating makeup-gas unions are
located at `ROTARY-UTIL-A` and `ROTARY-UTIL-B`.
Each has a local fixed-side and rotating-side isolation valve,
leak measurement and independent shutdown. These interfaces
are not the passenger indexers and are not general ventilation
duct dampers.

The A inlet feeds `HAB-06`; B feeds `HAB-08`. An
eight-manifold makeup ring follows the actual eight pressure
arcs and crosses each `BR-nn` using a new, **separately
isolatable tube within `BR-nn-UTILITY-SLEEVE`**. Both ends
of every bridge gas crossing have normally closed valves.
A failed spool can be isolated from the refill line without
requiring the remaining seven spools to fail.

The ring describes *potential physical delivery* when
deliberately opened, not permanently connected gas spaces.
Normal room air does not continuously mix through these
high-pressure lines. A manifold can pressurise its own
`PZ-HAB-nn` after the compartment is repaired,
isolated, evacuated of contaminants as necessary, and
correctly sized for the refill. Ordinary bridge pressure
equalisation is handled by its pressure-head hatch fittings,
not by simply opening a high-pressure makeup valve.

This also defines a real failure consequence:

- One isolated BR-06 sleeve does **not** destroy all
  eight-arc makeup access: the long way around the ring remains.
- Both BR-06 and BR-07 unavailable isolate HAB-07 from
  **both** A and B gas inlets, regardless of how much gas remains
  in the stores; manual exterior or local alternative becomes
  a real repair job.

## 5. The 83 cargo/industrial spaces not assigned breathable gas

The earlier pressure-cell register left 83 spaces without
pressurisation classification. We now provide an explicit
*access safety role* for each, without inventing an extra
pressure zone or air volume:

| Space role | Number | Normal assumption |
| --- | ---: | --- |
| Manifest-dependent rotating cargo sectors | 48 | cargo-conditioned or vacuum; never crew breathable by default |
| External commercial cargo portals | 12 | pressure depends on docking/portal configuration |
| Bearing service enclosures | 12 | mechanical hazard; pressure unknown until proven |
| High-energy fixed machinery rooms | 8 | “serviceable” does not imply safe air |
| Shield, tank and trim bays | 3 | unoccupied and not treated as breathable |

These are not all declared permanently vacuum. A cargo sector
may contain a manifest-specific pressurised gas; a service bay
may be safely entered after deliberate checks. Nevertheless,
**no generic MUD room or crew AI may infer unsuited access from
a null pressure-zone ID.** The individual room, entry doctrine,
pressure evidence and cargo conditions have to justify entry.

## 6. Reference casualty sequences

**Refill one evacuated HAB-03 arc:** verify hatches on both
BR-02/BR-03, prove the arc pressure shell and repair,
test each local valve/pressure gauge, isolate affected bridge
makeup branches, open a proven A/B path from both banks
via opposite rotary unions, purge/verify receiving air,
meter 3.09–3.71 t at correct pressure and composition over
many hours, close outlets and certify pressure retention
before normal crew access. A repair receipt alone does
not certify a sound seal.

**Forward bank fails:** the aft bank can reach all intact
trunk-B feed sections and the hab-ring if its rotating
route works, but its remaining 2.75 t cannot guarantee
a whole-arc refill. The cross-tie may reach trunk-A
sections if local isolation permits.

**Two bridge sleeves fail around HAB-07:** the gas graph
cannot reach that arc from either rotating inlet, even
though both stores may still read full. The crew must
restore one sleeve, establish a separate rated route,
or defer the refill. A normal pressure-head hatch can
remain closed while a utility sleeve is isolated.

**Pressure loss in a sectional trunk:** the failed section
isolates via its two rated trunk doors. Other trunk
sections do not automatically become vacuum. The
surviving A/B gas main can reach a specifically
identified section through its local tap, but an open
tap is not permission to open a person-size pressure door.

## 7. What is closed and what remains uncertain

Pressure-cell **gross geometry** is dimensioned for all 133 authored pressure cells, and the ship has both a physically differentiated **5.5 t protected casualty-air reserve** and a separately metered **7.0 t routine inert-gas supply**. Each has finite mass, distinguishable source IDs, local valves and operating conditions. A single full HAB arc may be refillable after leak repair; two full losses still exceed available casualty air. Routine inert stock is never implicitly usable as breathable full-arc refill.

Fitted displacement, actual partial pressures, corrosion/purity, as-found legacy connections and damage histories remain unmeasured or potentially wrong. Neither the source dimensions nor the 83 unclassified hazardous rooms grant unsuited entry or bypass a failed sensor. The separate 40-person ECLSS oxygen electrolysers replace metabolic and nominal leak O2 but cannot create nitrogen.

Operations require tested pressure/gas composition, proven source-to-destination routing, isolation, local authority, power and real inventory depletion. Exact fabrication certification is not an approval gate. Design history below explains why some older v0.5 checkpoint numbers are smaller than today's complete model.


## 8. Historical survey of the 48 then-unsized pressure cells

The next room-by-room audit of the source model found that **37 of these 48
cells already contain a `geometry` entry for every constituent room**;
only eleven cells lack geometry on one or more rooms (six cargo-drum
freight/service galleries, the isolated medical room and four habitation
indexer/capsule/final-lift cells).

That does **not** make all 37 reliable gross-volume sums. Two variable-length
WR telescoping passages have a known 3 m clear bore but no fixed deployed
length. Multi-room `box` groups can overlap: in
`PZ-AFT-STORES`, the `STORES-LONGLIFE` extent contains 162 m³ of each
of the `STORE-FLUID-AFT` and `STORE-FOOD-AFT` rectangles. Summing
the three as separate empty rooms would double-count their common geometry.
`PZ-AFT-CTRL` also has two smaller box intersections (~2.73 m³ and
27.04 m³), which require surveying whether nominal envelopes are shared
or improperly placed. Some workshop pods may similarly share clearance
zones.

**Next closure rule:** derive free volumes from a non-overlapping union of
occupied-pressure envelopes, after confirming which rooms are subspaces,
which are genuinely separate bounded compartments, and which service
passages vary with radius. Do not promote a bare sum of nominal room boxes
to verified compartment air. The present 48-cell `null` accounting
remains deliberate until that geometry review is complete.
