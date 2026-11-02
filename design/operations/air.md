# Air

Atmosphere, pressure and the fallbacks behind them. Sources:
[operating doctrine §D](../ship/SYSTEM_OPERATING_STATES_v0.5.md),
[instrumentation](../ship/G19_INSTRUMENTATION_AND_RECOVERY.md),
[crew physiology](../ship/G19_CREW_PHYSIOLOGY.md),
[atmosphere refill](../ship/G19_ATMOSPHERE_REFILL.md) and the installed
design data.

## The plant

| Part | What it is | Status |
|---|---|---|
| `ECLSS-A` (`HAB-06-ECLSS-A`) | Environmental train; life-extension refit | Runtime |
| `ECLSS-B` (`HAB-08-ECLSS-B`) | Environmental train; original with gen-3 controls behind a mixed-generation gateway | Runtime (gateway quirk: Data) |
| Oxygen generation and CO₂ removal | Each train: 40 kg/day oxygen by electrolysis, 45 kg/day CO₂ removal; one train is sized for 40 people | Data (doctrine); oxygen generation and hydrogen venting are Runtime |
| Air handlers | Eight habitat AHUs (mixed rebuilds and gen-2 replacements) and two spine air handlers | Data |
| Dehumidifiers | Four, from the cultivation refit | Data |
| 133 pressure cells | The authoritative gas ledger: masses, temperature, damage, leaks, smoke | Runtime |
| Refill banks | A and B, 2.75 t dry breathable air each; 100 kg/h regulators | Runtime |
| Fallbacks | Eight arc emergency scrubbers and oxygen banks; two 72-hour refuges; two 30-day survival craft; four portable scrubbers | Data (refuges and portable air partly Runtime) |
| Local control | `LCS-ECLSS-A`, `LCS-ECLSS-B` | Data |
| Isolators | Atmosphere: 68 remote, 153 manual only. Emergency oxygen: 10, all manual only | Data |

## Normal

| | Value | Status |
|---|---|---|
| Alarm limits | Pressure 80–125 kPa; oxygen 16–26 kPa; CO₂ above 0.008 mass fraction; any smoke; temperature 278–313 K; cell damage ≥ 0.2 | Runtime |
| One person's breathing | 0.00001 kg/s of oxygen, about 0.86 kg a day, returned to the cell as CO₂ | Runtime |
| Margin | A small crew uses a tiny fraction of either train's capacity | Derived |
| Train states | Available, online, standby, limited, isolated, faulted, under local control | Data (doctrine) |
| Service | Arc AHU filter and drain service; environmental train rolling service | Data |

## What the lead mind runs

**New**, through the ECLSS gateways and the 68 remote atmosphere valves:

- **Trains.** Keeps one train online and one in standby, swaps them for
  service, and sets oxygen generation and CO₂ removal to match the people
  aboard.
- **Circulation.** Runs air handlers and dampers so every occupied cell is
  inside its limits.
- **Breach response, first steps.** Detect and verify; close the smallest
  viable boundary it can reach; account for who is in the affected cells
  (doctrine §D).
- **Refill planning.** Tracks refill bank stock against possible losses.
  Bank A's valve is already operable from `WATER-FWD` (**Runtime**).

## What needs hands

- **The 153 manual-only atmosphere isolators and all 10 emergency oxygen
  banks.**
- **Patching, repair and leak testing**, then deliberate repressurisation from
  stock, then reopening only when conditions are met (doctrine §D).
- **Filter, drain and rolling train service.**
- **Portable scrubbers and air**, carried to where they're needed.

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| A cell leaks | Its gas mass falls; its panel alarms if powered; the leak's location stays world-owned until found | Runtime |
| A train faults | The other carries the ship alone | Data |
| A good train, an isolated zone | It cannot clean air it has no route to (doctrine §D) | Data |
| Lost gas | Oxygen generation replaces oxygen only; nitrogen and buffer gas come from the refill banks | Runtime |
| ECLSS-B gateway quirk | Readings or commands for train B may be mistranslated or lag | New |
| A dark panel | No reading for that cell; not evidence the cell is safe | Runtime |

## What it leaves behind

- **Gas per cell (Runtime):** oxygen, CO₂ and buffer masses, temperature,
  smoke, leak rate, damage — including each person's breathing.
- **Alarms (Runtime)** at panels in affected rooms.
- **Refill bank custody (Runtime).**
- **Crew exposure (Runtime)** per enrolled person.
- **Train modes, setpoints and boundary closures** in the gateway traffic and
  remote command log (**New**).

## Open questions

1. Which doors and hatches can the lead mind close remotely in a breach? The
   access data has no remote flag for doors.
2. How many people are aboard at the start, and does the ECLSS run at a
   small-crew setting?
