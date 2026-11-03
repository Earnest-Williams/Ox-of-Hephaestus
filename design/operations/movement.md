# Movement

How people and freight move around the ship, and what that leaves behind.
Sources: [operating doctrine §C](../ship/SYSTEM_OPERATING_STATES_v0.5.md),
[indexed personnel transfer](../ship/G19_INDEXED_PERSONNEL_TRANSFER.md),
[access coverage](../ship/G19_ACCESS_COVERAGE.md),
[movement and rotary operations](../ship/G19_MOVEMENT_AND_ROTARY_OPERATIONS.md)
and the installed design data.

## The plant

| Part | What it is | Status |
|---|---|---|
| 517 access links | 131 pressure doors, 70 doors, 40 cabin doors, 18 pressure hatches, 48 cargo service doors, freight routes, shutters, gates, EVA transfers and more; each with its own traverse time | Runtime |
| Pressure boundaries | 198 links are pressure boundaries | Runtime |
| Normal states | 407 closed, 66 open, 44 "closed or auto" | Data |
| Personnel trunks A and B | Two 3 m trunks along the spine; eight personnel carts, about six people each, cruising at 4 m/s | Data (carts) |
| Heavy logistics tube | 5.5 m clear; four freight sleds, 50 t normal and 100 t restricted | Runtime (transfers) |
| Indexed transfers | Nine rated connections into rotating sections: six cargo drums, two habitat stations, the workshop rotor; 20, 180 or 300 seconds depending on the connection | Runtime |
| Gates on movement | Pressure and gas checks, suits for exterior and some rated doors, incapacity blocks travel | Runtime |

## Normal

- Ordinary doors open on demand and close behind; pressure doors preserve
  sectional isolation (**Data**).
- Travel time is the sum of authored link times; drum 3's gallery is 300
  seconds from the bridge, mostly the indexed transfer
  ([drum 3 survey](../interface/drum3-fitout-survey.md)) (**Runtime**).
- Only one habitat indexed transfer runs at a time (**Runtime**).

## What the lead mind runs

**New:**

- **Doors and hatches.** **Decided:** most doors are motorised and can seal
  against vacuum. The lead mind opens them on request, closes them behind,
  holds pressure boundaries and seals sections in a breach.
- **Controlled access.** **Decided:** the ship's entrances, the bridge and the
  lead mind's machine rooms are monitored and have controlled access. There the
  lead mind knows who passed; elsewhere it knows only that a door moved.
- **Carts and sleds:** dispatching carts, sequencing sled movements with drum
  stops and freight collars ([cargo](cargo.md)).
- **Indexed transfers:** preparing the rotor (stop, index, hardlock) so a
  transfer can start when someone arrives.
- **Knowing where people are**, from the access log, cameras, suits and
  panels, with the age of each sighting.

## What needs hands

**Runtime:**

- **Walking.** Every person moves only by real exits, in real time.
- **Indexed transfers:** a qualified engineer operates the fixed-side hatch;
  the traveller waits the full transfer time.
- **Freight transfers:** a cargo worker at the drum with the handler and
  collar.
- **Manual doors and hatches**, and any boundary the lead mind cannot reach.

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| Guideway fault | A cart strands; the trunk can still be walked | Data (doctrine) |
| Pressure shutter locked | A sled cannot change compartments | Data (doctrine) |
| Bad pressure or gas | Transfer refused; more than 2 kPa difference stops an indexed transfer | Runtime |
| Power lost mid-transfer | The job pauses; the person or cargo stays at the last committed point | Runtime |
| Incapacity | The person cannot travel | Runtime |

## What it leaves behind

- **Indexed transfers (Runtime):** request, start, completion and who moved.
- **Freight transfers (Runtime):** receipts and manifest changes.
- **Every traversal (Runtime):** each move through a canonical exit already
  creates a world event (`crew_traverse`: who, from, to, game time) and a work
  receipt. That is the world's truth, with identity, and no character or the
  lead mind can read it whole.
- **The lead mind's access log (New)** is a scoped view of those events: that a
  motorised door moved, when, and in which direction, everywhere it reaches;
  **who** only at controlled-access points (entrances, the bridge, the lead
  mind's machine rooms). A **location history** is built from it, never
  complete. See [records](records.md).

## Open questions

1. Which doors are *not* motorised? The design data needs a flag per access
   link.
2. What does monitoring mean at a controlled point: identity reader, camera,
   or both?
3. Are carts modelled as vehicles, or only as faster walking?
