# Ox of Hephaestus — atmosphere volume, refill reserve and casualty delivery v0.5

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


**22 October 2026 · B′ 38° working ship · Engineering design candidate, not runtime**

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

## 1. What the gas-volume figures actually establish

The existing pressure-cell survey has **133 separately isolatable
pressurised cells**, of which **85** have geometric dimensions:
46 personnel-trunk sections, 23 heavy-logistics sections, eight
habitation arcs and eight bridges. The remaining **48** known
pressurised cells (fixed specialist workplaces, cross-connections,
indexer capsules and the like) still have **no measured/defended
gross volume**. We must not silently assume zero gas in them or
fabricate room measurements.

The v0.5 working model assigns conservative *planning ranges*
for the fraction of known gross enclosed volume that is actual
free gas. These are not surveyed displacement figures:

| Geometrically sized volume | Gross-to-free fraction, planning only | Why |
| --- | ---: | --- |
| 46 personnel trunk cells | 0.93–0.98 | clear 3 m bores with guides/carts and local fittings |
| 23 heavy-freight trunk cells | 0.86–0.97 | 5.5 m bores with variable sled occupancy/restraints |
| Eight 38° B′ habitation arcs | 0.70–0.84 | floors, cabins, furnishings, galleries, mounted equipment |
| Eight independent pressure bridges | 0.80–0.93 | 3 m bore, collar, conduit and penetration volume |

At **101.325 kPa**, **20°C**, dry-air density **1.204118 kg/m³**:

| Sizing result for the 85 known-envelope cells | Range |
| --- | ---: |
| Geometric gross space (not net) | 65,549 m³ |
| Screened free air volume | **52,609–59,898 m³** |
| Contained air mass | **63.35–72.12 tonnes** |
| One intact pressurised habitation arc | **3.09–3.71 tonnes** |
| Two intact habitation arcs | **at least 6.18 tonnes** |

These numbers exclude the 48 unsized gas cells. They are useful
order-of-magnitude reservoir requirements for **operating and casualty
simulation**, not a claim that the installed ship has been measured or
is always at this temperature or pressure. Each ledger row retains a
separate `verified_as_installed_free_gas_m3: null`. Pressure,
composition, humidity and compartment temperature change actual gas mass.

The underlying source `pressure_zone_topology_v0.5.json` deliberately
continues to distinguish `gross_reference_envelope_m3` from
`actual_usable_free_air_m3`; this increment does not overwrite that
distinction.

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

## 7. Remaining closure without false precision

This increment closes gas source and route *identity* at the
full-ships's simulation granularity, not the dimensions of
48 presently unsized breathable pressure cells or exact
surveyed free air. It does not claim finite-element
validation for pressure bottles, rotating seals or hatch seats.

Next: size the 48 unsized pressurised zones from their
actual structural geometry/operational requirement;
resolve existing byproduct discharge and waste receivers;
record as-found sensor fidelity and condition for the
old, mixed-generation plumbing. Then the candidate can
be promoted on its merits before revisiting Evennia/UI.

## 8. Survey of the 48 still-unsized pressure cells

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
