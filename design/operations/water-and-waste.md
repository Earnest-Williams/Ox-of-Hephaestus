# Water and waste

Potable, grey and black water, recycling and sealed waste. Sources:
[G19 water, wastewater and waste](../ship/G19_WATER_WASTE_RECYCLING.md),
[operating doctrine §E](../ship/SYSTEM_OPERATING_STATES_v0.5.md),
[endurance ledger](../ship/ENDURANCE_LEDGER_v0.5.md) and the installed design
data.

## The plant

| Part | What it is | Status |
|---|---|---|
| `WATER-PROC-A`, `-B` | Water processors in the HAB-06 and HAB-08 ECLSS rooms | Runtime |
| `WASTE-PROC-A`, `-B` | Sanitation processors, same rooms | Runtime |
| Working potable water | 39,000 kg at the reference start | Runtime |
| Makeup and reserve | 162 t normal makeup; 70 t protected reserve, counted separately | Runtime |
| Separate networks | Storage, potable processing, grey water, black water, dehumidifier condensate and cultivation are distinct | Data (doctrine) |
| Rotary interfaces | Potable, grey and black water into the habitat ring through `ROTARY-UTIL-A` and `-B` | Data |
| Isolators | Potable: 20 remote, 32 manual. Grey: 18 remote, 32 manual. Black: 18 remote, 14 manual | Data |
| Local control | None: no local control station covers water | Data (gap) |

## Normal

| | Value | Status |
|---|---|---|
| Domestic use | Reference 1,000 L a day for 40 people, 90 % recovered | Data (doctrine) |
| Cultivation | Up to 35 t over 730 days from the working potable tank | Runtime |
| Quality | Commissioned water quality; a processor fault can quarantine a train even with its pump running | Runtime |
| Reserve | Never drained automatically for normal use or crop irrigation | Data (doctrine) |

## What the lead mind runs

**New**, through a water segment gateway still to be placed:

- **Treatment trains.** Runs processors, swaps trains for service, and holds a
  quarantined train out of the potable loop.
- **Routing.** Keeps grey, black and potable water in their own circuits;
  reroutes compatible grey water only within valid valve boundaries.
- **Accounting.** Tracks working potable stock, makeup and the protected
  reserve, and forecasts them to the end of the voyage.

## What needs hands

- **Water-quality checks and sampling** before a quarantined train returns
  (**Runtime**).
- **Releasing the protected reserve**, deliberately (**Data**, doctrine).
- **The 78 manual-only water isolators.**
- **Carrying and depositing sealed waste** and refuse at the ECLSS rooms
  (**Runtime**).
- **Filter and processor service.**

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| Processor fault | The train is quarantined; water does not become potable by retagging | Runtime |
| Potable supply fails | Crops stop growing; galley cooking needs verified safe water | Runtime |
| Leak | Water is lost from its network; the reserve is not tapped automatically | Data |

## What it leaves behind

- **Water state (Runtime):** stock per account, treatment cycles, quarantine,
  quality, valve settings, receipts for each local operation.
- **Waste custody (Runtime):** sealed waste and refuse masses carried and
  deposited.
- **Routing changes and train swaps** in the remote command log (**New**).

## Open questions

1. Where does the water segment's gateway sit, given no local control station
   covers water?
2. What is the small crew's daily domestic use, rather than the 40-person
   reference?
