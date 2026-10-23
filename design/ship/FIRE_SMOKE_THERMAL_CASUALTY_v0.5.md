# Fire, smoke, ventilation and thermal casualty engineering — Ox v0.5

**23 October 2026 · selected design-only pressure-casualty increment on PR #102.**
The module `fire_smoke_thermal_v05.py` extends
`pressure_damage_sim_v05.py`. Run
`python design/ship/check_fire_smoke_thermal.py` from the repository root.
This produces inspectable deterministic references, **not live Evennia physical
state, an actuator/controller implementation, automatic authorization, a
certified flow/fire model, or measurements of the surviving working ship**.

## Canonical topology reused, not duplicated

- **133 existing** individually bounded nominal gas pressure cells;
  **339 existing** rated physical access gates, including **131** to
  unknown environmental receivers. No pressure volumes or space/access
  identities were changed. The 83 cargo/industrial spaces with no verified
  breathable atmosphere do **not** become fictitious vacuum sinks.
- The actual **212-node, 213-edge, 221-isolator atmospheric duct network**
  is loaded from the candidate ship. Each connection is resolved through
  its equipment/space owner to the source pressure-zone ID. A closed
  HAB bulkhead does *not* close a separate open HVAC duct.
- The actual **68-node, 73-edge, 73-isolator fire main** is used, including
  forward/aft physical pumps, segregated trunk A/B mains, the two rotary
  HAB inlets, eight ring sections, and HAB-01..08 mist manifolds. Suppression
  can flow only if a real reachable service path survives.
- The existing **78-node, 79-edge, 87-isolator LT cooling network**
  controls physical connectivity from LT-PLANT through two rotary
  interfaces, the eight HAB manifolds and bridge links. The plant's
  nominal **3.75 MW** is bounded by four separately disableable
  **0.9375 MW** radiator-wing shares from the actual equipment objects.

The existing v0.4 published world, v0.4 standalone HTML wire rendering,
Evennia, AI handler, personality routing and UI stay untouched.

## Modeled consequences and deliberate approximations

The fire trial maintains finite preassigned carbon-equivalent combustible
fuel, cell oxygen, species-tagged visible/harmful smoke, source temperature,
and compartment pressure simultaneously. Combusting one kg of a selected
carbon-equivalent fuel debits about 2.667 kg oxygen and adds its own 1 kg
carbon mass to the existing gas ledger; consumed oxygen becomes other
gas products instead of disappearing. Finite fuel and captured
particulates remain in the closed-system mass reconciliation.
Oxygen deficiency and smoke accumulation can block unsuited crew access
even when a room remains near nominal total pressure.

**The chemistry is an intentionally crude carbon-combustion reference**,
not a universal combustion equation, experimentally measured smoke yield,
CO/CO2 toxicity model, or structure-burning forecast. The tagged smoke
fraction is a mobile hazardous tracer rather than a complete list of
real combustion products. Baseline parameters are 20 MJ/kg fuel, a
scenario-specified burn rate and smoke fraction, and oxygen-starvation
throttling. These are adjustable trial controls, not hidden knowledge
given to characters.

Gas pressure includes temperature through the lumped ideal-gas law.
Gas parcels carry temperature into adjacent pressure cells; their
combined oxygen, tracer, gas mass and reference enthalpy follow each
flow. Structural fit-out supplies a finite *effective* thermal inertia
to each compartment; fire heat and ordinary work heat share the available
LT radiator budget and actual valved distribution. The chosen screening
thermal capacitances, **2.0 MW maximum per terminal**, and a 600-second
nominal cooldown objective are not surveyed thermal specifications.
The model does not solve radiation from burning surfaces, nonlinear
heat transfer, real fan control, plume stratification or manufacturing
thermal qualification.

Through a separate open *real* ventilation duct, the model transmits
finite composition and smoke exchange (default **2 kg/s** per active
cross-pressure-zone connection) and small differential-pressure flows
(screened **0.12 kg/s** reference conductance). Fan shutdown stops powered
mixing, **not** possible passive airflow through an unisolated duct.
HVAC changes do not themselves open or close pressure doors. Closing
one of a dual-ended BR-03 duct's two dampers blocks that duct; if both
mechanical damper seats jam open, smoke can still reach HAB-04 while the
BR-03 pressure hatches are closed. Unlike cargo-gate failures, duct
bypass uses real known-to-known pressure-cell endpoints and finite gas
inventory.

The two installed ECLSS trains have separate flags and an optional
scenario smoke-filtration action. Filtration needs actual duct reachability
and powered fans; its finite filter budget is explicitly an allocation
inside existing **INV-DC-CONSUMABLES**, not new ship mass. Capture removes
aerosol mass from cabin gas into an accounted recovered residue.
A blocked or isolated duct cannot make a remote filter clean that
compartment. ECLSS scrubbers do not restore oxygen or replace air
lost overboard merely because they process smoke.

For ordinary combustibles, mist suppression requires operator authority,
a compatible agent, actual forward/aft fire-main delivery and a finite
selected allocation inside the existing **INV-WATER-NORMAL 162 t** account.
A fire-main shut valve or loss of both fire pumps blocks delivery, regardless
of healthy atmosphere ducts. Live electrical fires also require explicitly
verified energy isolation before mist is permitted. Spray consumes water
from a **scenario allocation**, temporarily reduces the nominal burn rate,
and rejects thermal energy to the water. Spraying is not an automatic
extinguishment/repair receipt; consumed water is not credited as new
drinking or atmosphere water. The source mass ledger of the ship itself
is unchanged.

A deliberate exterior atmospheric dump requires an existing verified
pressure-to-*known-vacuum* hatch (for example the bow EVA airlock),
positive local permission, proof of single-cell isolation and removal of
unprotected occupants. **HAB-03 has no magical direct vacuum vent.**
Venting is not the normal response to a fire and always loses valuable
breathing mass. A cargo receiver whose pressure is unknown receives no
fabricated quantitative flow or safe access designation.

## Adversarial acceptance

`check_fire_smoke_thermal.py` exercises both the old pressure
model and these additional fire/system interdependencies:

| Decision or casualty | Expected operational consequence |
| --- | --- |
| Fire starts in HAB-03 | Fuel and oxygen debited, smoke/carbon accounted; temperature, pressure and crew exposure change |
| Pressure hatches shut, HAB ring ducts open | HAB-04 acquires smoke through intact ventilation *without* a traversable passage |
| HVAC isolated at 0 seconds versus 140 seconds | HAB-04 smoke is reduced by early isolation, while more smoke stays in HAB-03 |
| One BR-03 damper jammed open | Independent other-end valve still contains flow |
| Both BR-03 end dampers jammed open | Local isolation reports failures and smoke propagates |
| Hull breach with hatch shut, duct open | Small but finite intercell air loss through unisolated duct |
| ECLSS cleanup, isolated ducts, stopped fans and finite filters | Cleanup follows physical reachable routes and consumes finite capacity |
| HAB-03 water mist during fire | Real A/B pump/rotary/ring route must exist, water is consumed, combustion slowed |
| Mist station valve shut, both pumps off, energized electrical fire | Unsafe or unsupported suppression is refused |
| One vs several lost radiator wings under load | Reduced heat rejection causes rising temperature/pressure risk |
| Nonessential work shed after radiator casualty | Remaining radiator capacity can cool warm compartments |
| Vacuum vent requested at nonexistent HAB hatch or with people present | Refused; permitted rated isolated airlock loses real gas |
| Unknown cargo threshold fails open | No cargo air state invented; affected zone truth/crew access withheld |
| Lower/midpoint/upper free-volume assumptions | Different test pressure/thermal outcomes, all gas/particulate/fuel mass conserved |
| Eighteen deliberately damaging inputs | False identities, valves, ratings, stock/rates and authority rejected |

**Preserved authority boundary:** design scripts may emit evidence and
physical counterfactuals. Later Evennia code will own actual gas,
temperature, damper/valve positions, equipment damage, water/fuel stocks,
crew location, action timing and server-verified outcomes. Private AI
cognition must not receive a perfect sensor or a truth-only casualty map.
A selected equipment name or expected route in this file is **not** proof
that the present Ship of Theseus still has that component installed or
working.

## What remains beyond this stage

This closes the first *coupled design-level* fire/smoke/thermal response,
not an entire shipwide CFD/fire certification or gameplay system.
Appropriate later refinements are measured/surveyed HVAC conductance,
individual AHU power and filter conditions, several distinct smoke/toxic
species, evacuation passage occupancy, explicit heat capacity/material
damage, localized fire extinguishing agents, finite water returns, and
live crew procedural decisions with delayed imperfect evidence.
