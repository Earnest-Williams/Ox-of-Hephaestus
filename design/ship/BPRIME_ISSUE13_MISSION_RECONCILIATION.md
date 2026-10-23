# B′ Issue 1.3 — 40-person / 730-day mission reconciliation

**Design decision, 23 October 2026:** adopt the Issue 1.3 food, cultivation and normal-power basis in the physical Ox v0.5 candidate. Preserve the subsequently designed larger 133-cell atmosphere envelope, protected casualty gas and existing vessel/departure mass. This is a verisimilitude-level working ship with finite failure consequences, **not a real spacecraft qualification**. The candidate is not yet promoted into `ox_full_ship.json` or the Evennia simulation.

**Machine-readable authority:** `ox_full_ship_v0.5_candidate.json` (`mass`, `life_support_contract`, `power_contract`, installed equipment, inventories, utilities). **Fail-closed regression:** `check_mission_endurance.py`, invoked in `ox-ship-design.yml`. Data refers to planned charge/nominal capacities, not actual pressure gauges or a guaranteed present-day ship condition.

## Selected 730-day dietary contract

- 40 people, **2,550 kcal/person/day**: **74.46 million kcal** over 730 days.
- Issue 1.3 mass reference: **56.79 tonnes total food mass consumed under a normal diet** over 730 days (28.395 t per 365 days, customarily rounded to 28.40 t/yr).
- **56.79 tonnes physically stored at departure** in the existing aft and four habitat food stores: **24.82 t high-energy dehydrated** and **31.97 t conventional foods**. The 24.82 t subset is enough for all 74.46 million kcal at 3,000 kcal/kg; it is *not an additional 24.82 t beyond the 56.79 t inventory*. Conventional food is separately part of the same inventory, not a second secret store.
- Normal calorie split **25% hydroponic / 25% dehydrated / 50% conventional**. At the stated energy density assumptions, nominal consumption is **18.615 t edible hydroponic crop**, **6.205 t dehydrated**, and **31.97 t conventional**. The crop starts unharvested and requires real production; only the two stored categories are physically aboard as the departure provision.
- Hydroponic yield is a **design goal**, not an independently verified agricultural output: 450 m² productive bed area, 150 m² each at existing `HAB-02-GROW`, `HAB-06-GROW`, `HAB-08-GROW`; 90 kW normal lighting/process/controls (30 kW per room); 18.615 t edible at ~1,000 kcal/kg per leg. Reference conventional energy density is ~1,164.529 kcal/kg, explicitly a mixed wet-food equivalent rather than a dried staple.
- If a crop train loses water, light, nutrient regulation or heat removal, that food is **not** created. The crew must draw additional stored dehydrated provisions, ration, repair or trade. At any point in an otherwise nominal leg, the remaining dehydrated supply is sufficient to cover the remaining *whole-leg calories*, provided the stock is itself intact. A food-store casualty can invalidate that fallback.

The equal values **56.79 t stored on departure** and **56.79 t wet mass eaten under the normal diet** have different compositions. Normal crops replace precisely the extra high-energy dry stores that remain in reserve. Do not turn that coincidence into duplicate mass.

## Atmosphere: total gas lost versus inert gas make-up

At **0.01% of charged dry-gas mass lost per day**, the new 133-cell v0.5 planning reference contains **79.270–105.989 t** dry air. The constant-mass reference screen therefore loses **5.787–7.737 t mixed air** over 730 days.

With approximate dry-air mass fractions **77% inert / 23% oxygen**, this is **4.456–5.958 t inert** and **1.331–1.780 t oxygen**. These are not contradictory leak totals: the smaller figure is the **inert component** of the larger mixed-air loss (the original Issue 1.3 estimate was correctly expressed as *inert make-up*). The upper bound makes a separate gas store necessary.

- Two **3.5 t routine inert-gas banks**, `INV-INERT-MAKEUP-A/B` and `GAS-INERT-BANK-A/B`, installed in the separated forward/aft environmental control rooms, provide **7.0 t total**. Their lines have metered regulators, normally closed source and injection valves, separate A/B routed trunk/rotary paths, and a normally closed **manual** cross-tie. Loss of a bank is therefore not automatically repaired by selecting another alarm icon.
- **Inert gas is not breathable air.** Neither source may feed cabin pressure taps directly. `ECLSS-A/B-INERT-MIX` only admits it into a healthy, tested ECLSS atmospheric return after local oxygen partial-pressure, purity, pressure, power and flow verification. A failed train or contaminated common cross-tie can block flow even with adequate stock.
- The **5.5 t mixed-air casualty/refill stock** remains two physically separate, **protected 2.75 t** banks with their original pressure-cell recovery routes. It is never automatically spent on routine leakage. The **249.2 kg refuge/local emergency oxygen** is also a different inventory and cannot finance normal makeup.
- The normal `ECLSS-A-O2-GEN` or `ECLSS-B-O2-GEN` train electrolyses the missing oxygen along with respiration demand. Worst-reference daily oxygen burden is ~**38.04 kg/day** (35.6 kg metabolism plus ~2.44 kg leakage), beneath the **40 kg/day single-train** capacity, with little nominal margin. All replenishment requires usable potable/process feed, power, heat rejection and safe hydrogen discharge.
- The loss-oxygen electrolysis allocation is **2.100 t additional gross water** over the leg, which covers the 133-cell upper-bound oxygen-leak requirement (~2.003 t water). Issue 1.3's older ~1.1 t water figure was based on the smaller atmosphere; the adjusted 2.1 t is deliberate.
- Without access to a qualified port or a successful gas-recovery process, depleted inert stock cannot be regenerated from nothing. A serious unarrested leak, failed pressure measurement or lost metered mixer can force shutdown of compartments, vent-path repair, isolation, or changed mission duration.

The calculation uses a **constant nominal charged-mass planning screen**. Actual pressure/temperature, varying volume, isolations, leak rate and reserves will vary in play; `verified_as_installed_free_gas_m3` remains unknown, and 83 industrial/cargo rooms are not presumed breathable.

## Water, power, mass and operating constraints

| 730-day normal water demand | Tonnes |
| --- | ---: |
| Domestic unrecovered (90% recovery) | 73.000 |
| Respiratory oxygen electrolysis (normal metabolism) | 29.236 |
| 450 m² cultivation and food-processing budget | 35.000 |
| Additional oxygen electrolysis for nominal atmosphere leak | 2.100 |
| Dehydrated-food rehydration/handling | 0.740 |
| Service, quality rejects and other ordinary losses | 21.924 |
| **Normal make-up water** | **162.000** |

The existing **70 t protected water recovery reserve** and **39 t working/process water** are separate and have different operating roles. Gross electrolysis input is conservatively charged without inventing returned hydrogen/CO2 water. Stored water, hydroponic yield and normal oxygen manufacture remain coupled through the actual ECLSS services.

**Normal electrical demand selected: 1.35 MW**, comprising **1.163 MW assigned non-cultivation ordinary service**, **90 kW crop production**, and **97 kW within-schedule operating margin**. The demanding mode remains **2.60 MW**; protected reference mode **0.75 MW**; a lone surviving auxiliary can support only a separately shed **0.65 MW** schedule. On emergency power, crops lose their 90 kW first and dehydrated stores compensate. The 125 t generator-cartridge account covers the full reference 1.35 MW × 730 d × 24 h/day × 4.5 kg/MWh = **106.434 t** without exceeding capacity; this is a uniform-load baseline, not guaranteed after breakdowns.

New 56.79 t food and 7.0 t inert make-up are allocated *within the unchanged 1,500 t mission allowance*, alongside the pre-existing 5.5 t casualty gas and water stocks. The total departure mass remains **1,187,500 t**. Avoid treating newly enumerated line items as extra ship mass.

## Recorded B′ decisions and technical status

The ship keeps **eight independently pressurised 38° habitation arcs at 45° pitch**. The earlier 41° trial is superseded; 38° is the selected functional geometry. All **133 nominal pressure cells are dimensioned**, but the estimated **65,832.797–88,021.802 m³ free-gas** range is a planning displacement interval, not a physical pressure survey. The machinery and service paths are authored for gameplay; no real-world NASA, ESA, fabrication or insurance approval is sought.

The source ship's **40-person ECLSS A/B**, **two protected refuges**, **two survival craft**, separate waste receivers and the old Ship-of-Theseus refit status are unchanged. Inventories deplete in simulated operation; the static candidate records starting stocks and credible routes, not omniscient current gauges. Introduced equipment has accountable maintenance through the existing `MT-GAS-RESERVES` and `MT-GAS-DELIVERY` groups.

**Runtime promotion remains a separate step:** regenerate the wire visualization for the v0.5 source, update its model-version binding and rebase the stage-one Evennia importer only after the checks pass. Do not silently substitute the candidate for published v0.4.
