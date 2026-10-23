**CURRENT 23 OCTOBER 2026 v0.5 CANDIDATE:** 133/133 physically bounded nominal pressure cells, 339 rated isolation boundaries (208 previous plus 131 cargo/industrial/unknown-environment thresholds), 100,772.940 m³ gross / 65,832.797–88,021.802 m³ planned free-air reference; **808 maintained equipment objects, 15 inventory accounts, 42 maintenance groups**. The six cargo-drums now have individual passenger indexers and freight docking collars; the four separate, finite industrial/hazardous bins begin empty. Read [machinery/industrial disposal closure](MACHINERY_AND_FINITE_DISPOSAL_CLOSURE_v0.5.md) and [physical closure](PHYSICAL_CLOSURE_v0.5.md). Earlier dates/counts later in these files refer to earlier v0.5 milestones only. All source volumes are design geometry, not as-installed measurements or certified safe access.

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
| Normal mixed-diet food mass (includes freshly grown crops) | 77.795 kg/day | 56.790 t |
| Nominal consumed dehydrated food | 8.5 kg/day | 6.205 t |
| Nominal consumed on-board staple crop | 25.5 kg/day | 18.615 t |

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
environmental-process load inside the adopted 1.35 MW normal ship
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

## 4. Reconciled 162 t normal makeup-water allowance

Forty people at 25 L/day each circulate 730 t over a 730-day leg; at 90% recovery the net domestic loss is **73.000 t**. That loss alone never explained the separate 162 t normal voyage make-up account. The adopted B′ Issue 1.3 policy allocates **all** of it:

| Normal make-up demand (730 days) | Tonnes |
| --- | ---: |
| Domestic unrecovered (40 × 25 L/day × 10%) | 73.000 |
| Ordinary metabolism O2 electrolysis water feed | 29.236 |
| Cultivation and conventional-food process | 35.000 |
| O2 electrolysis feed replacing oxygen lost in daily cabin leakage | 2.100 |
| Dehydrated food rehydration/handling | 0.740 |
| Ordinary servicing and water-quality rejection | 21.924 |
| **Normal stock consumed (reference maximum)** | **162.000** |

Respiratory O2 electrolysis uses 35.6 kg/day × 730 × 18/16 = approximately 29.2365 t gross treated-water feed. The additional **2.100 t** allocation covers lost O2 at the **current larger 133-cell atmosphere inventory**, not the ~1.1 t derived for Issue 1.3's older, smaller atmospheric mass. This is conservative gross process water; no unmodeled reclaim is assumed. The separate **70 t protected water-recovery reserve** is not automatically available for crop watering or ordinary washdown. The **39 t working water** account is circulating/process stock, not a second 39 t of makeup. At 80% domestic recovery, extra loss alone is 73 t over the leg: a tangible repair/rationing emergency.

## 5. Stored food, working 450 m² cultivation and failure fallback

The single `INV-FOOD-LONG-LEG` holds **56.790 t at departure**, in `STORE-FOOD-AFT` and the four named HAB-01/03/05/07 stores. The physically allocated split is **24.820 t high-energy dehydrated fallback** and **31.970 t conventional foods**—not 56.79 t dry *plus* 56.79 t conventional. This corrects the old 32 t / 0.85 kg-per-person-day provisioning concept.

The reference diet is 40 × 2,550 kcal/day × 730 days = **74.46 million kcal**, divided **25% hydroponic, 25% dehydrated and 50% conventional**. At the selected reference energy densities, normal dietary mass consumption is **18.615 t fresh crops + 6.205 t dehydrated + 31.970 t conventional = 56.790 t**. Crop mass is produced in flight, not stored on departure. The same total as 56.79 t departure stock is coincidental: dehydrated safety margin offsets fresh crop production.

Three existing rooms, `HAB-02-GROW`, `HAB-06-GROW`, `HAB-08-GROW`, each hold **150 m² productive growing beds**, serviced by existing controls/nutrient skids. Their **90 kW** combined reference power is ordinary operating load. The 450 m² staple output target is a bounded, plausible fictional yield to verify during operation, **not** a free default material credit: production depends on lighting, nutrients, water, temperature, heat rejection and maintenance.

The **24.82 t** dehydrated departure subset alone provides the entire 74.46 million kcal at ~3,000 kcal/kg. During a normal voyage, dry food is consumed at only one-quarter of calories, so the *remaining* dry stock can still support the *remaining leg* if the crop and conventional foods are lost late. It does not restore an already contaminated food store, guarantee water/power, or make fresh production instantaneous.

Stored food and the two independent gas stores remain inside the existing **1,500 t mission allowance**, so the selected departure mass remains **1,187,500 t**. Complete contract/validator: [B′ reconciliation](BPRIME_ISSUE13_MISSION_RECONCILIATION.md).

## 6. Everyday atmospheric leakage is not a pressure-breach casualty

The candidate has **133 physically dimensioned pressure cells**, a **79.270–105.989 t** dry-air planning charge, and **83 cargo/industrial/shield rooms** whose breathability is *unknown by default*. At the selected **0.01%/day** nominal leak assumption, **5.787–7.737 t full air** exits the ship over 730 days. The **inert component is 4.456–5.958 t** (~77% dry-air mass), and O2 loss is **1.331–1.780 t** (~23%). These are respectively full-air, inert and oxygen terms; do not use them as interchangeable numbers.

Routine maintenance uses a distinct **7 t inert-gas inventory**, two 3.5 t banks with metered A/B delivery to *ECLSS-controlled atmosphere mixers*. Pure inert gas cannot feed habitable rooms directly. A dedicated manual cross-tie is normally shut and usable only after isolation/purity checks. Existing oxygen electrolysers must make up the missing oxygen along with ordinary metabolism. Each A/B 40 kg O2/day train is sufficient for 35.6 kg metabolism plus at most ~2.44 kg/day leak-O2 under this plan, subject to power/water/heat/disposal and purity proof.

The **two 2.75 t mixed-air emergency banks** remain fully reserved for deliberate post-breach pressure-cell recovery, separately from the protected **249.2 kg local/refuge oxygen**. A normal 730-day voyage must never silently debit emergency banks for steady leakage. If the 7 t inert stock runs out, the crew faces an actual pressurisation/operating limitation; the ship does not manufacture nitrogen by electrolysis. See [gas recovery](PRESSURE_GAS_RECOVERY_v0.5.md) and [mission reconciliation](BPRIME_ISSUE13_MISSION_RECONCILIATION.md).

Waste streams and industrial receivers remain finite. Biological solids, spoiled crops/packaging, used filters, contaminated water, generated hydrogen and captured CO2 require compatible actual processing, isolation or identified exterior discharge. They never disappear merely because an inventory entry decreases.

## 7. Consequential operating casualties at the selected mission loads

- A water processor can interrupt normal crew drinking water, electrolyser oxygen feed and the productive 450 m² crop system simultaneously; the separate emergency water stock is not automatic crop irrigation.
- One ECLSS train may fail and the other still replaces **38.04 kg/day** reference oxygen if powered and connected, but the oxygen-capacity margin is small.
- A stuck inert metering valve can waste the **separate 3.5 t** routine bank; a contaminated or blocked mixer cannot be bypassed straight into occupied cabins. A manual cross-feed may restore one path, but introduces a testable shared-contamination risk.
- Loss of a whole hab arc needs the **separate** 5.5 t casualty mixed-air banks; spending them for everyday leakage would make the later breach unrecoverable.
- Crop or conventional-food loss increases **measured depletion** of remaining dehydrated stores. A contaminated dry-food bay removes the very fallback that otherwise preserves calories.
- Loss of the main generator forces a verified **0.65 MW or smaller** essential power schedule. The entire **90 kW** hydroponic load is shed; a claimed 0.75 MW protected-service demand is not automatically attainable.
- Domestic water recovery degraded from 90% to 80% adds **73 t** gross loss over the leg and threatens the protected reserve unless repaired or rationed.
- ECLSS captured gases and sanitary/industrial waste must have physically identified, compatible bounded disposal routes; an exhausted receiver halts further generating work.

## 8. Updated B′ gross and fitted-free geometry reference

The historical 38° HAB tube/head/bridge and three fixed-spine movement-tube subtotal of ~**65,549 m³** is only a partial geometry screen. It omits numerous fixed specialist compartments, transfer locks, connectors and work volumes; it is **not the current whole-ship pressure-volume inventory**.

The completed cell-by-cell B′ physical reconciliation now gives **133/133 nominal pressure cells dimensioned**, **339 rated access/pressure boundaries**, **100,772.940 m³ screened gross pressure envelope**, and **65,832.797–88,021.802 m³ planning free-gas range**. That implies approximately **79.270–105.989 t dry gas** at the reference temperature and pressure. Occupied arc refill mass is roughly 3.02–3.71 t depending on arc/source-specific displacement. The 83 additional industrial/cargo/shield rooms are not made breathable by a convenient JSON default.

As-installed actual free-air volume, gas composition, seal conditions, manifold failures and incident pressure histories remain unknown until observed. The data deliberately records **planning fractions and null measured free air**, not fabricated world truth.

## 9. Independent pressure boundaries and routine inert gas replenishment

There are 46 true personnel trunk pressure sections, 23 heavy-logistics cells, eight independently isolatable HAB bridges, eight full habitation arcs and other sized specialist cells. **All 133** have defensible nominal gross bounds; the 339 rated connections include 131 explicitly guarded cargo/industrial/shield thresholds. Equalisation and refill require a safe physical path, valve/pressure evidence and nonhazardous destination, not just a graphical doorway.

Routine **inert** loss over 730 days draws only `INV-INERT-MAKEUP-A/B` (two distinct **3.5 t** sources), through verified ECLSS mixing skids—not the pressure-refill ring. Individual metering paths run alongside selected A/B segmented trunk raceways and independent rotary service interfaces. Their normally shut local controls and cross-tie have physical access and failure consequences.

## 10. After-loss emergency refilling remains separate

Two **2.75 t mixed breathable-air reserve banks** in the original forward shielding and aft fluid stores feed regulated, isolated A/B fixed-spine headers, 69 trunk pressure taps, two independent rotary crossings and the HAB gas ring. These 5.5 t are intended for a **single, repaired and verified** severely depressurised hab arc (roughly 3.02–3.71 t), never two whole arcs. The 100 kg/h per-bank regulator reference makes recovery a many-hour operation.

They do **not** count as normal leak supply; the independent 7 t inert inventory is neither a substitute for a full mixed-air refill nor a rescue O2 reserve. All **15** inventory accounts, **808** installed maintained equipment units and routine water/food/power/endurance assumptions are crosschecked by the 14-validator ship design CI including `check_mission_endurance.py`. Fictional verisimilitude and meaningful operating constraints are the acceptance standard, not NASA approval.
