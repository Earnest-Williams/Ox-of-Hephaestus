# Fire and damage control

Detection, suppression, breaches and the equipment that answers them.
Sources: [operating doctrine §G](../ship/SYSTEM_OPERATING_STATES_v0.5.md),
[instrumentation](../ship/G19_INSTRUMENTATION_AND_RECOVERY.md),
[attended fire and water recovery](../ship/G19_ATTENDED_FIRE_WATER_RECOVERY_2026-10-29.md),
[portable pump and smoke control](../ship/G19_PORTABLE_PUMP_AND_SMOKE_CONTROL.md),
[hull breach and restoration](../ship/G19_HULL_BREACH_AND_RESTORATION.md) and the
installed design data.

## The plant

| Part | What it is | Status |
|---|---|---|
| Fire mains A and B | Segregated, forward and aft pumps, sectional isolation, normally shut cross-ties, two habitat inlets; water mist | Runtime (forward chain proven) |
| Fire detection | Local detection loops; a protected detector and comms node in each habitat section | Runtime |
| Bridge fire relay | Serious habitat alarms to `ENG-CONTROL`, `CMD-PRIMARY`, `CMD-EMERG`; a failed pair reports lost links, not all-clear | Runtime |
| Damage-control lockers | 20 lockers with portable pumps, smoke fans and breathing hardware | Runtime (portable kit) |
| Local control | `LCS-FIRE-FWD` (`WATER-FWD`), `LCS-FIRE-AFT` (`ENV-AFT`) | Data |
| Isolators | Fire main: 73, all remote-operable | Data |

## Normal

- Mains pressurised, cross-ties shut, lockers stocked and inspected
  (damage-control locker and fire-main inspection is a scheduled task)
  (**Data**).
- Every portable item has a current location; one in use elsewhere is not in
  its locker (**Data**, doctrine).

## What the lead mind runs

**New**, through the fire segment gateways and all 73 fire-main valves:

- **Mains:** keeps them pressurised and configured; backfeeds a lost section
  from the opposite main by opening the right cross-tie.
- **First response:** on an alarm, verifies from readings; isolates threatened
  utilities and ventilation; contains smoke within intact pressure zones;
  tells people where to go and not to go.
- **Equipment tracking:** knows where every portable pump, fan and set of
  breathing gear is, from the records of who took it.

Venting to vacuum is a deliberate last resort with crew consequences, and the
lead mind does not do it on its own authority.

## What needs hands

**Runtime:**

- **Starting water mist** in a habitat section needs a crew member in an issued
  suit with breathing oxygen, intact and fit.
- **Portable pumps and smoke fans** are carried and set up by people.
- **Hull breach repair:** isolate, patch with finite spares, test, then
  repressurise ([air](air.md)).
- **Clearing and testing** before routes reopen.

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| A detector or comms node fails | The relay reports lost links, not an all-clear | Runtime |
| A fire-main section lost | Recoverable by opposite-main backfeed; a shut cross-tie supplies nothing | Data (doctrine) |
| Smoke | Contained and scrubbed within intact zones | Data (doctrine) |
| A fire segment gateway fails | Local pumps and cross-ties still work by hand; the lead mind can't configure the mains | New |

Doctrine is explicit: losing remote actuator control does not transfer
authority to an AI character or the interface; actual maintenance is local,
permissioned and logged.

## What it leaves behind

- **Alarms and the relay (Runtime).**
- **Receipts (Runtime)** for mist, portable equipment, breach work and tests.
- **Main configurations and isolations** in the remote command log (**New**).

## Open questions

1. Who in the crew is trained for fire response?
2. May the lead mind start mist in an unoccupied section without a person?
