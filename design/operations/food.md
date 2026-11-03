# Food

Stores, cultivation and the galley. Sources:
[G19 food operations](../ship/G19_FOOD_OPERATIONS_AND_ACCEPTANCE.md),
[cultivation and food](../ship/G19_CULTIVATION_AND_FOOD.md) and
[operating doctrine §E](../ship/SYSTEM_OPERATING_STATES_v0.5.md).

## The plant

| Part | What it is | Status |
|---|---|---|
| Food stores | `STORE-FOOD-AFT` 33.79 t; `HAB-01/03/05/07-FOOD-STORES` 5.75 t each | Runtime |
| Stock | 56.79 t at departure: 24.82 t dehydrated fallback, 31.97 t conventional | Runtime |
| Grow bays | `HAB-02/06/08-GROW`, 150 m² each, with `GROW-n-CTRL` and `GROW-n-NUTRIENT`; 90 kW together | Runtime |
| Galley and mess | `HAB-02-GALLEY` (on electrical bus B) and `HAB-02-MESS` | Runtime |
| Nutrients | Issued from located spare stock | Runtime |

## Normal

| | Value | Status |
|---|---|---|
| Diet | 25 % hydroponic, 25 % dehydrated, 50 % conventional by energy | Data (doctrine) |
| Crop yield | Up to 8.5 kg per bay per day, using 1.8 kg water and 0.012 kg nutrient per kg | Runtime |
| Fallback | Dehydrated stock alone covers full calories for the remaining leg at 3,000 kcal/kg | Data (doctrine) |
| Perishables | Fresh food and prepared meals have finite rack space and shelf life; expired meals become refuse | Runtime |
| Grow service | Cultivation controllers first inspected at 60 operating days; faulted at 75 | Runtime |

## What the lead mind runs

**New:**

- **Grow bays.** Keeps controllers and nutrient skids powered and within their
  gas, temperature and water conditions; schedules harvests.
- **Stock.** Tracks every store, meals cooked, served and eaten, refuse, and
  crop biomass; forecasts food to the end of the voyage.
- **Power.** Hydroponics is the first thing shed on an auxiliary-only
  essential schedule ([power](power.md)).

## What needs hands

All **Runtime**:

- Taking stock from a store (hand-carry up to 5 kg) and delivering it to the
  galley.
- Cooking, which needs staged ingredients, a powered galley panel and verified
  safe water.
- Carrying meals to the mess, serving, and eating.
- Harvesting to the bay's 80 kg rack, and issuing it to a worker.
- Collecting refuse and depositing it at an ECLSS room.
- Issuing and carrying nutrients.

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| Bay unpowered, unsafe air or no water | No growth | Runtime |
| Essential power schedule | Hydroponics shed | Data (doctrine) |
| Crops lost | Dehydrated stock replaces fresh calories if the reserve is intact | Data (doctrine) |
| Meals expire or overheat | They become refuse | Runtime |

## What it leaves behind

- **Food chain (Runtime):** stock per store; each take, delivery, cook, serve,
  eat and refuse movement as a receipt; crop biomass histories.
- **Forecasts and harvest schedules** in the lead mind's model (**New**).

## Open questions

1. Who cooks and when? A watch routine needs mealtimes.
2. How closely does the lead mind track who ate what? The receipts already
   record it.
