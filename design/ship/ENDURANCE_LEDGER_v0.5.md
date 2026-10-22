# Ox of Hephaestus — 40-person, 730-day endurance and consumables v0.5

**Design-only normal-voyage ledger.** The accepted population limit is
40 people, not a requirement that 40 people be aboard every leg.
The figures below are usable operating assumptions for a long-haul
fictional industrial freighter; they are **not** a claim that every
plant, transfer valve and pressure-volume measurement is finished.

The source contract already supplies main ECLSS trains A/B, serviceable
protected oxygen banks, 162 t normal water makeup, 70 t separate water
recovery reserve, 39 t working water, and large long-voyage stores
locations. This increment supplies the missing consumables and normal
oxygen/CO2 replacement path without changing the dry/departure mass
envelope.

## 1. Forty-person daily material throughput

| Flow | Rate for 40 | 730-day reference |
| --- | ---: | ---: |
| Respiratory oxygen use | 35.6 kg/day | 25.988 t |
| Respiratory CO2 produced | 43.2 kg/day | 31.536 t |
| Domestic water circulated | 1,000 L/day | 730,000 L gross |
| Domestic unrecovered at 90% | 100 L/day | 73 t |
| Shelf-stable edible provision | 34 kg/day | 24.82 t |

Oxygen and CO2 figures are the ship's adopted biological accounting rates,
not assumptions that occupants live only on bottled oxygen. A normal
atmosphere circulation train must supply the required oxygen and
remove the CO2 while rejecting heat and conditioning moisture.

## 2. Normal oxygen replacement has an actual source

The candidate adds serviceable equipment
**ECLSS-A-O2-GEN** and **ECLSS-B-O2-GEN** in the already existing
ECLSS train rooms. Each is rated at a nominal 40 kg O2/day. A single
available train can meet the 35.6 kg/day forty-person reference
when water quality, power, heat rejection, and gas distribution are
intact. Running both simultaneously does not double demand.

Reference process: treated-water electrolysis, followed by oxygen
purity conditioning and verified discharge into the correct
atmosphere distribution circuit. For every 1 kg O2 produced,
approximately 1.125 kg water is split. At 25.988 t O2 over
730 days, the conservative **gross** electrolyser feed is
approximately **29.237 t water**. The hydrogen counterpart
is approximately **3.249 t over the leg**.

Hydrogen cannot accumulate in an unbounded imaginary receiver.
The operating plant must recover it to an identified process,
or use a controlled, isolated exterior discharge point with
positive routing checks. If neither route is available,
oxygen production must be limited or halted. This is a distinct
possible casualty and repair task.

A provisional 6 kWh electrical/kg O2 implies about **8.9 kW**
continuous average electrolysis demand at reference consumption,
and 10 kW at a 40 kg/day skid output. This is an explicit
environmental-process load inside the wider 1.55 MW normal ship
demand, not a newly claimed electric plant.

**Protected bottled oxygen** is still 249.2 kg total across the
two 40-person refuges and eight local packages. It is separate
from normal electrolysis feed and is located where it is needed;
the sum cannot be treated as a single universally accessible tank.

## 3. Regenerable CO2 scrubbing has a real waste path

The candidate adds **ECLSS-A-CO2-REGEN** and
**ECLSS-B-CO2-REGEN**, each sized for nominal 45 kg CO2/day
removal, above the 43.2 kg/day forty-person reference.

A regenerable sorbent bed traps CO2 and then needs an isolated
regeneration/desorption route. Capturing CO2 is not destroying
its carbon mass. Over 730 days the ship must either discard,
store or chemically process roughly **31.536 t gross captured CO2**,
less any explicitly credited on-board recovery.

A poisoned sorbent, failed regeneration heater, closed disposal
line, leaking selector valve or inaccurate CO2 sensor can each
leave a fan audibly running while life support is **not**
performing adequate CO2 removal. Local chemistry samples and
actual discharge measurements are part of the repair proof.

The source model already has atmosphere service networks and
ECLSS train rooms. Specific hydrogen/CO2 overboard discharge
routes are still future equipment/service-topology authoring,
not a reason to invent a third full-capacity ECLSS train.

## 4. Reconcile the 162 t normal makeup-water allowance

The previous 162 t allowance could not be derived simply from
the 90% recovered domestic supply: that alone is 73 t for
730 days. The v0.5 candidate adopts a conservative planning
allocation:

| Normal make-up demand (730 days) | Tonnes |
| --- | ---: |
| Domestic unrecovered (40 x 25 L/day x 10%) | 73.000 |
| Gross oxygen electrolysis feed | 29.236 |
| Cultivation and food-process net water | 35.000 |
| Routine servicing, quality rejection, leakage allowance | 24.764 |
| **Total normal planning makeup** | **162.000** |

Rounding the electrolysis term to three decimals does not
alter the intended 29.2365 t stoichiometric estimate. Some
respired water or processed byproducts may later be returned
to the feed cycle, but the proposed ledger takes **no** credit
until actual recovery equipment and routing are demonstrated.

The protected **70 t** reserve is separate from routine
162 t, and must be protected against automatic watering or
ordinary washdown during low-inventory operation. If domestic
recovery slips from 90% to 80%, that alone increases
unrecovered domestic demand by 100 L/day—approximately
73 t over a 730-day leg. The 70 t reserve can bridge
substantial degraded operation but is not magic indefinite
support.

The additional 39 t working/process/refuge water account
exists for circulation and local operation. It is not a
second copy of either the 162 t or 70 t makeup stocks.

## 5. Food is a real stored material

The four HAB-01/03/05/07 FOOD-STORES rooms and aft
STORE-FOOD-AFT existed in v0.4, but no explicit voyage-food
inventory was tied to them. The candidate adds
**INV-FOOD-LONG-LEG** with **32 t departure stock**.

At the proposed reference 0.85 kg/day/person of edible shelf-stable
provisions, 40 people require **24.82 t edible mass** over 730 days.
The remaining mass allowance covers packaging, diet/menu variety,
handling loss and contingency. Approximate planning energy is
0.85 kg x 3,000 kcal/kg = **2,550 kcal/person/day**,
sufficiently useful as a scenario reference without claiming
that every body or duty has identical needs.

The 32 t inventory is **inside the existing 1,500 t
mission/non-propulsive allowance**—the voyage departure
mass remains 1,187,500 t. It is not 32 t new mass secretly
added to the vessel. Cultivation supplies fresh produce and
crew morale, not the calorie balance; a crop failure should
not immediately starve a provisioned ship.

## 6. Gas refill and waste are distinct from normal circulation

The v0.4 5.5 t *single arc refill gas* allowance is not
an entire-vessel atmospheric reserve. Approximate gross
geometric envelopes of the two 3 m personnel trunks, the
5.5 m logistics trunk and eight candidate 38° pressure sections
already total around 63,511 m³ before adjustment for
equipment, bulkheads, heads and occupied fixed compartments.
Exact free gas volume and usable storage positions still
require a **pressure-zone ledger**.

Solid biological waste, packaging, used filters, spent
cartridges, contaminated water and captured atmospheric
byproducts do not vanish when an inventory goes down.
Existing waste-processing plant can transform or dispose of
material only through verified process modes and receiving
volume. Exact receiver capacities, disposal permits and
long-leg accumulation are the next endurance-model closure.

## 7. Failure cases available with these choices

- A water-processor contamination alarm can interrupt both
  ordinary potable distribution and oxygen-electrolyser feed;
  splitting A/B ECLSS equipment does not make a shared feed
  magically independent.
- Electrolyser A can fail while B continues the forty-person
  oxygen replacement, subject to distribution and heat budget.
- CO2 regeneration isolation can cause a delayed atmosphere
  problem even when fans and oxygen production remain normal.
- A decrease to 80% domestic water recovery consumes the
  protected water reserve over the course of the voyage rather
  than requiring an immediate evacuation.
- A cultivation fault reduces dietary variety, not the
  basic 730-day calorie stock.
- A food-storage leak or contamination event forces a
  real inventory survey, ration plan or lost-cargo decision.

The design can now support meaningful causality and
work with actual consumables. It is not yet a completed
physical utility-graph implementation.

## 8. Updated B′ gross geometric volume reference

A 38°/73.15 m-centreline/9.5 m pressure tube has approximately 27,511 m³ eight-arc tube envelope. Adding a schematic pair of 2:1 ellipsoidal half-head volumes per arc gives approximately **29,306 m³** gross habitation module envelope. Eight pressure bridges add approximately **242 m³** gross bore envelope at the selected port spacings. The fixed spine's three nominal full-length tubes add approximately 36,001 m³, yielding roughly **65,549 m³ gross geometric envelopes before fixed rooms, partial pressurisation and displaced fit-out**. This does **not** mean all this gas is carried at once or that it belongs in one pressure zone. Inventory/refill planning still requires actual net volumes and pressure boundaries; see `BPRIME_HAB38_MECHANICAL_CLOSURE.md`.

## 9. Independent pressure boundaries and refill-gas distribution

The gross 65,549 m³ schematic envelope now belongs to **multiple separate pressure cells**, not a single shipwide air tank. The two 950 m personnel trunks alone form 46 isolatable sections, with 23 heavy-freight tube cells and eight independently sealable habitation bridge volumes. Any simulated repressurisation must account for doors, equalisation and gas supply/consumption within *reachable* cells. The two 40-person refuges occupy intact HAB-04 and HAB-08 whole-arc pressure zones; 40 m² REFUGE identifiers remain equipment stores. `pressure_zone_topology_v0.5.json` records 85 geometric envelopes and 48 additional pressurised cells whose dimensions remain unresolved; this ledger retains the original 5.5 t per-arc refill-gas planning allowance without pretending to know total free-gas volume.
