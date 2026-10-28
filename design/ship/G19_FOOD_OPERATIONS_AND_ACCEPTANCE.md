# G19 — complete original-food operating chain and cultivation provisioning

**Branch:** `g19-complete-ship-systems`; [PR #138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138) remains draft. This is game-world verisimilitude, with actual equipment, compartments, finite material and authenticated work, **not** NASA qualification. The excluded 40-crew voyage is NOT part of this phase.

## As-installed food spaces and baseline

- Five exactly authored original food stock compartments: `STORE-FOOD-AFT` 33.790 t; `HAB-01/03/05/07-FOOD-STORES` 5.750 t each.
- One authoritative `INV-FOOD-LONG-LEG` inventory: **56.790 t** departure mass consisting of **24.820 t dehydrated high-energy fallback** and **31.970 t conventional provisions**. Distribution follows original room allocations, not added stock.
- The original `HAB-02-GALLEY` and `HAB-02-MESS` are distinct rooms. The galley is actually connected to the **B** electrical distribution bus and its existing `NODE-HAB-02-GALLEY-LP` and `ISO-HAB-02-GALLEY-LP`. An ordinary engineer cannot substitute A-bus power through the standby main-board cross-tie.
- Three `HAB-02/06/08-GROW` bays retain their individual 150 m² gardens with both fitted `GROW-n-CTRL` and `GROW-n-NUTRIENT` powered appliances.
- Nutrient-compatible spares must be classified by an explicit one-time operator attestation against **already located** original `INV-SPARES` stock; issuing 1 kg removes 1 kg from both the authoritative spare inventory and the original local source survey. A crew member carries the same finite material to the destination plant. A locally installed dose cannot exceed the fitted 10-kg machine limit.

The source model remains unchanged: 421 spaces, 517 access links, 808 originally authored equipment identities and 15 permanent inventory accounts. These operational ledgers are written into the **same authoritative installed-world clock** as water, power, crew health and cultivation, not a second simulation.

## Production and environmental dependencies

- The operator commissions actual electricity, water, cultivation and food independently. Previous cultivation records are migrated **without resetting surveys, crop biomass, charge or elapsed history**.
- Each grow pair must actually be powered, nonfailed, correctly room-sited and metered running, with safe local gas, temperature and no smoke/fire/active leak.
- Each production tick consumes genuine available cultivation water from the existing working potable tank, limited to the previously voted 35 t/730-day budget; no growth when the supply fails or the protected reserve is released.
- Productive crop has a reference limit of **8.5 kg per bay/day**, consuming **1.8 kg irrigation water** and **0.012 kg previously issued nutrient** per kg wet edible yield. Rates and elapsed time are bounded; measured mass histories persist across ticks.
- Crop biomass is grown and held in the original bed; only an attended harvest can move crop to its bounded local 80-kg rack, and a separate local pickup issues it to an actual worker.
- Raw fresh food on the galley counter and in people's hands is perishable. Prepared meals have strictly finite rack space and shelf life; chronologically expired meals and overtemperature losses become *actual local food refuse*.

This is a coarse biological production model: crop strain, seeding, a detailed crop-disease model and nutrient chemistry are not yet independently authored production systems. They are not substituted with fictional stock or assumed full performance.

## Authentic crew operations

All `oxplant` operations require a unique 32-character lowercase hex request ID, a real authenticated person in the exact source/destination compartment, live breathable local atmosphere and actual world-authoritative custody. Work receipts are persistent and replay-safe. Supplied values are examples; kilogram quantities are finite.

1. A worker at `HAB-01-FOOD-STORES` issues `oxplant <uuid> food HAB-01-FOOD-STORES take:dry:1` or `take:conventional:1`. Personal hand-carry is capped at 5 kg.
2. A worker physically traverses the existing exits to `HAB-02-GALLEY` and issues `oxplant <uuid> food HAB-02-GALLEY deliver`.
3. A worker may `cook:vegetable`, `cook:mixed`, `cook:stored` or `cook:emergency`. The ingredients must be physically staged, local B-side galley panel must be truly energized, the live water plant must provide verified safe potable service, and the selected recipe debits measured water. Exactly one meal appears in the bounded galley rack. The old automatic daily rehydration allowance is suppressed after food commissioning, avoiding duplicate water charges.
4. `meal_take` puts a real prepared meal in the worker's hands; the worker physically travels to `HAB-02-MESS`, then `meal_serve` moves it into that room's bounded rack. An enrolled real crew member may `eat` an actual meal, consuming its original inventory contribution exactly once and receiving individually measured calories. Crew may also eat a personally carried meal while in a suitable eating area.
5. `waste_take:<kg>` at the local galley, mess, food store or grow room collects generated food refuse. A genuine transported `waste_deposit:<kg>` at original `HAB-06-ECLSS-A` or `HAB-08-ECLSS-B` transfers that carried mass to the **same capped, sealed sanitary cassette** already used by the ship's wastewater and waste systems. No infinite disposal.
6. The operator may `survey_g19_food_nutrient_stock(...)` only against previous `survey_g19_water_material(source="INV-SPARES", ...)` records; a worker `nutrient_take:<kg>` at the actual spare room, transports the issued pack and `nutrient_install:<kg>` at the real grow room. The first stage debits installed source inventory, the second credits only the installed nutrient skid.
7. `oxplantread food`, `oxplantread nutrition` and `oxplantread GROW-1` expose an attended **local** food station, the individual's own held materials and nutrition, or one actual grow room. They are not global stores or crew status oracles.

## Resource conservation and deprivation

- The sum of all original dry/conventional goods, including packages in hand, raw ingredients and unconsumed cooked portions, plus edible quantities already eaten or spoiled, always equals the original 56,790 kg. **`INV-FOOD-LONG-LEG` is decremented only when existing food is eaten or classified as spoilage.**
- Newly grown fresh crops are accounted separately through the cultivation history and cannot be mistaken for the original dry/standard stores. The bed's harvested/staged/released quantities exactly reconcile with its previous productive biomass.
- Food thrown away is held as physical refuse at the same worksite (or carried by a worker). Its generated mass equals refuse pending plus waste actually deposited to existing sanitation custody.
- Cooking water is held in actual prepared meals and then recorded as ingested moisture or spoiled moisture. No second full water tank is created.
- Nutrient spares remain conserved across source-certified inventory, carried packs, fitted plant charge and metered consumption.
- Physically enrolled living crew use **2,550 kcal/person/day** as a reference. Without food they accumulate measured caloric deficit. Sustained depletion limits their ability to operate machinery or travel; meals replenish individual energy. Unenrolled/dead characters are not silently simulated as 40 hypothetical eaters.

## Test matrix and acceptance boundary

The new `.github/workflows/ox-g19-food.yml` includes three **unconditionally executed** jobs, including on the draft integration PR:

1. Pure mass, calorie, crop, spoilage, nutrient, 730-day water and seeded food-operation fuzz regressions, using no fabricated ship crew or route.
2. Full installed Evennia original-room commissioning, pantry transport, B-bus galley, recipe water, mess eating, receipts, spoilage and spares-to-cultivation transport.
3. Prior installed G19 electrical, water/waste and crew-physiology regressions, to ensure the new resource account cannot silently break already accepted ships.

**Acceptance requires all three jobs green on the exact final runtime commit.** Older green runs demonstrate their own code only. A failed or skipped gate does not count. The original whole-ship acceptance and prohibited 40-crew voyage remain separate. Merge only after wider G19 completion.


### Casualty nutrition and test partition

A physically present helper may use \`oxplant <uuid> food <patient-room> feed:#patient\` to feed an **already prepared, actually carried** serving to an **enrolled, living character in the same real pressurised room**, including a patient who is too weak to traverse the ship to the mess. A depleted person cannot operate logistics or machinery until fed; rescue therefore does not require teleporting a starving character to the galley. The receipt is once-only and nutrition is credited to the patient, never the helper.

The phase's historical compatibility acceptance executes the same original 42 electrical, 12 water/waste and 4 physiology tests in six separately provisioned, parallel shards (four electrical, one water, one physiology). This cuts wall time without deleting coverage or allowing failures to be hidden by a successful subset. Final phase acceptance requires **all eight jobs** (pure, installed food and six compatibility shards) to succeed on the exact commit.
