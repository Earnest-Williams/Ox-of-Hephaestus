# Cargo

The six rotating cargo drums: their climate, rotation and freight handling.
Sources: [G19 cargo environment](../ship/G19_CARGO_ENVIRONMENT.md),
[movement and rotary operations](../ship/G19_MOVEMENT_AND_ROTARY_OPERATIONS.md),
[indexed personnel transfer](../ship/G19_INDEXED_PERSONNEL_TRANSFER.md),
[wear and maintenance](../ship/G19_EQUIPMENT_WEAR_AND_MAINTENANCE.md),
[operating doctrine §B–C](../ship/SYSTEM_OPERATING_STATES_v0.5.md) and the
[drum 3 fit-out survey](../interface/drum3-fitout-survey.md).

## The plant, per drum

Each of `DR-01` … `DR-06` has, **Runtime** unless marked:

| Part | What it does |
|---|---|
| `DR-xx-CARGO-HX` | Thermal skid: proportional local controller, up to 20 kW of heat rejection |
| `DR-xx-CARGO-GAS` | Cargo-atmosphere circulation pack; must run for the skid to cool |
| `DR-xx-LT-IF` and valve `ISO-DR-xx-LT-IF` | Rotary interface to the LT plant, on the fixed side |
| `DR-xx-SVC-DB` | Rotating service board feeding both cargo devices |
| `DR-xx-ROT-PWR` | Rotary power interface into the drum |
| Eight sectors | Each with its own power breaker, cooling valve and cargo-atmosphere valve (Data: all remote-operable) |
| Personnel indexer | 180-second indexed transfer between the fixed service lock and the drum hub |
| Freight collar and `DR-xx-RADIAL-FREIGHT-HANDLER` | Heavy freight capture and radial handling; 50 t normal, 100 t restricted |
| Rotor | Its own angle, speed, target, brake, hardlock and bearing state |
| `LCS-DR-xx` | Local control station: rotation, locks, service interfaces, cargo machinery (Data: no runtime role yet) |

The commercial cargo is 900,000 t at the reference departure. It starts as
one unlocated amount; stowage surveys place it into named lots by drum, arm,
azimuth and restraint.

## Normal

| | Value | Status |
|---|---|---|
| Drum states | Parked, braked, releasing, rotating, spindown, isolated, unbalanced, bearing caution, tripped | Data (doctrine) |
| Cold-chain cooling | Each skid ≤ 20 kW; all six together ≤ min(120 kW, 10 % of LT capacity left after the drive) | Runtime |
| Temperature bands | Per lot profile: cold chain, cool-sensitive, heat-sensitive; targets 265–315 K | Runtime |
| Skid and pack service | First inspection due at 90 operating days; faulted at 112.5 | Runtime |
| Bearing lube and filter | Condition-based: filter differential, debris or flow trend | Data |
| Local control test | Takeover and indication test at each station | Data |

## What the lead mind runs

**New**, through each drum's gateway at `LCS-DR-xx`:

- **Cargo climate.** Sets each drum's target from its surveyed lots' bands;
  keeps the LT valve and sector cooling and atmosphere valves in their normal
  state (96 remote-operable cargo valves, no manual-only ones).
- **The heat budget.** Plans cargo cooling against the drive: the drive's heat
  is cooled first, so burns and radiator outages shrink the cargo share. It
  pre-cools drums before a planned burn and warns the captain when a burn will
  push lots out of band.
- **Rotation.** Spins drums up and down and holds speed within interlocks;
  refuses to spin an unbalanced drum.
- **Freight scheduling.** Sequences stops, indexing and hardlocks for planned
  transfers, so a drum is ready when the cargo crew arrive.
- **Watching.** Lot quality and time out of band; skid and pack wear against
  the 90-day interval; balance from surveyed lots.

## What needs hands

**Runtime**, unless marked:

- **Every freight transfer:** a cargo worker at the drum, the real radial
  handler and freight collar, a stopped, indexed, hardlocked drum and a
  retracted personnel interface.
- **Restraint checks** after a stop, before restart (Data, doctrine §C).
- **Entering a drum:** the 180-second indexed transfer, with a fixed-side hatch
  operated by a qualified engineer.
- **Surveys:** stowage positions, sensitive lots and drum thermal properties.
  Operator-only today.
- **Changing a drum's target by hand** in its gallery (the only way today), or
  at its local control station (New).
- **Service and repair** of skids, packs, bearings and handlers.

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| LT valve shut, LT interface broken, or pack stopped | The skid runs but delivers no cooling | Runtime |
| Heavy drive heat or fewer radiators | Cargo's share of LT capacity falls, possibly to nothing | Runtime |
| Skid passes 90 operating days | Degraded; at 112.5 days it faults and stops | Runtime |
| Lot out of band | Permanent quality loss accumulates; the lot's mass is unchanged | Runtime |
| Indexer or freight collar breaks | That interface is disabled; the drum still turns | Runtime |
| Drum out of balance | Cannot spin up; can be unloaded under hardlock to correct it | Runtime |
| Power lost mid-transfer | The job pauses; cargo stays at its last committed position | Runtime |
| Drum's gateway fails | The skid keeps regulating to its last target; the lead mind loses the drum's readings and commands | New |
| Drum taken into local control | The lead mind's commands to that drum are refused until it is handed back | New |

## What it leaves behind

- **Cargo climate (Runtime):** temperature, target and cooling output per drum;
  quality, time out of band and last temperature per sensitive lot.
- **Manifest (Runtime):** lot positions, splits, transfers and unmeasured
  transfer time; manifest hash in clock snapshots.
- **Wear (Runtime):** operating hours, stage and repairs for each skid and pack.
- **Receipts (Runtime):** setpoint changes, rotor commands, transfers, surveys.
- **Indexed transfers (Runtime):** every entry to and exit from a drum.
- **Gateway traffic, remote commands and local control log (New).**

## Worked example: drum 3

Drum 3's skid is in the rotating gallery; its LT valve and local panel are in
the fixed service lock; its local control station is in the `BE-05` bearing
service room, off trunk B. Counting authored door and transfer times, the
service lock is 140 seconds from the bridge, the control station 160, and the
gallery 300, because entering the drum adds the three-minute indexed transfer. In normal operation the lead mind holds drum 3's target
and valves through `LCS-DR-03`; nobody needs to go there. When something
departs from normal, the records above show what changed, and the travel times
show what it costs to send someone. The
[fit-out survey](../interface/drum3-fitout-survey.md) has the details.

## Open questions

1. May the lead mind spin drums up and down remotely, or only hold speed?
2. Who surveys cargo in play, now that surveys are operator-only?
3. What cargo profiles does a typical voyage carry, and how much is
   temperature-sensitive?
