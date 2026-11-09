# Power

Generation, storage, distribution and protection. Sources:
[G19 electrical power](../ship/G19_ELECTRICAL_POWER_AND_RECOVERY.md),
[operating doctrine §A](../ship/SYSTEM_OPERATING_STATES_v0.5.md) and the
installed design data.

## The plant

| Part | What it is | Status |
|---|---|---|
| `GEN-M`, `GEN-A`, `GEN-B` | Main and two auxiliary generators; deliverable 3.0, 0.65 and 0.65 MW; combined output capped at **3.3 MW** | Runtime |
| `GEN-B` | Life-extension replacement; reaches the plant-control network through a gateway | Data |
| Cartridge magazine `INV-GEN-CART` | 125 t of generator cartridges at departure; **2 kg per MWh** generated; spent housings stay aboard | Runtime |
| `BAT-COMMON-OPS`, `BAT-COMMON-PROT` | Grid batteries: 8 MWh to main board B; 12 MWh to the protected bus only | Runtime (start uncommissioned) |
| 16 local batteries | Bearing stations, transfer stations, refuges; not on the grid | Data |
| `F1-FW-01` … `F2-FW-32` | 64 flywheel modules, 3.90625 MWh nominal each (250 MWh nominal) | Runtime (each surveyed before use) |
| Shore power `SHORE-PWR` | Only at a commissioned berth, generators isolated | Runtime |
| Distribution | 438 power nodes, 450 edges, 466 breakers and isolators; main boards A and B, a bus tie, a protected bus | Runtime |
| Local control | `LCS-GEN-M`, `LCS-GEN-A`, `LCS-GEN-B`, `LCS-PWR-AFT`, `LCS-F1`, `LCS-F2` | Data |

## Normal

| | Value | Status |
|---|---|---|
| Normal schedule | 1.35 MW (includes 90 kW hydroponics and 97 kW margin) | Runtime |
| Other schedules | Essential 0.65 MW; protected 0.75 MW; demanding 2.60 MW | Runtime |
| Cartridge use at normal | About 65 kg a day (1.35 MW × 24 h × 2 kg/MWh) | Derived |
| Magazine endurance at normal | About 1,900 days from 125 t | Derived |
| Generator states | Off/cold, preparing, available, on load, tripped, isolated for work | Data (doctrine) |
| Generator readings | Cartridge feed, coolant flow, output, winding and bearing temperature, breaker position, protection state | Data (doctrine) |

## What the lead mind runs

**New**, using remote-operable breakers (236 of 466) through the generation,
distribution and storage gateways:

- **Dispatch.** Chooses the schedule that matches demand: normal under way,
  demanding for heavy cargo or workshop work, essential or protected in a
  shortfall. Brings generators to *available* and *on load* in step with it.
- **Load shedding.** When a generator trips, sheds discretionary loads at once
  to keep within what remains. The runtime today has **no automatic load
  shed**; crew must select a smaller schedule by hand.
- **Storage.** Places batteries and flywheels in standby, charge or discharge
  to bridge changeovers and absorb spare generation, within each unit's
  surveyed limits.
- **Energy balance.** Watches generation against delivered load, storage
  state of charge and cartridge use, and predicts magazine endurance.
- **Coordination.** Prepares bus-tie and protected-feeder changes for the
  crew members who must witness them.

## What needs hands

**Runtime**, unless marked:

- **Resetting a tripped breaker.** A protective trip is reset physically at the
  breaker, after the fault is found; acknowledging the alarm resets nothing.
- **Generator thermal-trip reset**, separately from bringing it back on load.
- **Main bus synchronisation.** `EDGE-MSB-XTIE sync` needs a person on site for
  a 15-second witness, which expires after 90 seconds; only then can the tie
  close.
- **Protected-feeder transfers** where the two feeder switches are in
  different rooms: each needs its own attendance, break-before-make.
- **Surveys** of batteries and flywheels before they can be used.
- **Shore connection** at a berth.
- **The 230 manual-only breakers and isolators.**
- **Repairs**, and finding the things a screen can't show: "a welded contact or
  a relabelled cable" (doctrine §A).

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| `GEN-M` trips | One auxiliary carries at most the 0.65 MW essential schedule; the 0.75 MW protected schedule loses at least 0.1 MW of discretionary load | Runtime (0.65 MW limit); Data (doctrine expects re-dispatch) |
| Sustained overcurrent | After 10 seconds over rating, the breaker trips and latches; reset only locally after isolating the fault | Runtime |
| Bus tie fails | One district goes dark while neighbours stay lit | Data (doctrine) |
| Dark panel | Loss of telemetry, not proof the room is safe | Runtime |
| Generator healthy but output nothing | Board or outgoing breaker isolated; a healthy machine can deliver nothing | Runtime |
| `GEN-B` gateway fault | The generator keeps running under its own local control; the lead mind loses its readings and commands until the gateway is restored | New |
| Storage not surveyed | It cannot bridge a changeover, whatever its nameplate | Runtime |

Restoring power needs verified voltage and downstream load and temperature,
not a switch set back to *on* (doctrine §A).

## What it leaves behind

- **Meters (Runtime):** generated kWh, shore imports, battery and flywheel
  charge and discharge, load delivered, load not served, trip meters,
  cartridge magazine and spent-housing custody. A repeated tick changes none
  of them.
- **Receipts (Runtime):** every local power operation, sync witness, feeder
  transfer, survey and reset.
- **Alarms (Runtime):** at panels in the affected rooms.
- **Gateway traffic and remote command log (New):** every dispatch change,
  shed and storage command the lead mind makes.
- **Local control log (New):** takeovers at the generator and distribution
  stations.

## Open questions

1. Which loads are discretionary, in what shed order? The runtime uses
   ship-wide schedules, not per-device loads.
2. Can the lead mind bring a generator from cold to *on load* remotely, or does
   a start need a person?
3. How much storage is surveyed and charged at the start of play?
