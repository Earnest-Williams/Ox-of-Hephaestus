# Workshop and exterior

Making parts, and working outside the hull. Sources:
[workshop fabrication](../ship/G19_WORKSHOP_FABRICATION.md),
[workshop welding](../ship/G19_WORKSHOP_WELDING.md),
[exterior mobile rail and inspection](../ship/G19_EXTERIOR_MOBILE_RAIL_AND_INSPECTION.md),
[exterior radiator service](../ship/G19_EXTERIOR_RADIATOR_SERVICE.md),
[operating doctrine §H](../ship/SYSTEM_OPERATING_STATES_v0.5.md) and the
installed design data.

## The plant

| Part | What it is | Status |
|---|---|---|
| `SHOP-MECH` | `SHOP-CNC-MILL`, `SHOP-CNC-LATHE`, `SHOP-MANUAL-LATHE`, each on its own refit breaker | Runtime |
| `SHOP-WELD` | Welding cells | Runtime (separate chain) |
| Stock | Generic metal blanks in `INV-SPARES`, classified before use | Runtime |
| `WR-01` workshop rotor | Independent rotor with its own carriage (24–75 m) and indexed transfer; `LCS-WR` | Runtime (rotor); Data (station) |
| EVA rail | Handholds, tethers and rail from bow to aft, through the drum bores | Data (doctrine); Runtime (rail links) |
| `EVA-CRAWLER-1`, `-2` | Rail crawlers at `EVA-FWD` and `EVA-AFT` | Runtime |
| `DRUM-INSPECT-ROBOT-1`, `-2` | Inspection robots for selected rotating surfaces; no heavy repair | Runtime |
| EVA suits | Finite oxygen, issued from the airlocks | Runtime |

## Normal

| | Value | Status |
|---|---|---|
| Shop tool service | First inspection at 30 operating days; faulted at 37.5 | Runtime |
| Machining | Needs measured shaft output, a qualified worker present and safe shop air on every interval | Runtime |
| Radiator and propulsion exterior work | Only under thermal isolation or positive drive inhibit | Runtime |

## What the lead mind runs

**New:**

- **Shop power and scheduling:** feeds tools when jobs are planned, and holds
  the demanding power schedule while they run ([power](power.md)).
- **Stock and wear:** blanks in stock, tool hours against service intervals.
- **Inspection robots**, where reachable, for routine looks at rotating
  surfaces.
- **EVA support:** tracks suits, oxygen and who is outside; stops and locks a
  drum before anyone crosses onto its skin.

## What needs hands

All **Runtime**:

- **All machining and welding:** a qualified engineer fetches stock, starts
  the tool and stays with the job.
- **All EVA work:** a suited, fit worker, through the real airlocks and
  platform transfers, with finite oxygen.
- **Crawler operation** and anything heavier than an inspection.

Doctrine §H: losing remote actuator control does not transfer authority to an
AI character or the interface; actual maintenance is local, permissioned and
logged.

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| Tool past interval | Degraded; at 125 % it faults and stops | Runtime |
| No stock | Nothing can be made; stock is never created | Runtime |
| Drum not locked | No crossing onto its moving skin | Data (doctrine) |
| Suit oxygen low | The worker must return | Runtime |

## What it leaves behind

- **Receipts (Runtime):** stock issued, tools started, parts made, welds, EVA
  entries and exits, crawler and robot use.
- **Wear (Runtime):** tool hours and repairs.
- **Suit custody and oxygen (Runtime).**

## Open questions

1. Can the inspection robots be driven by the lead mind, and where can they
   reach?
2. Should drones (much later) be a new kind of fitted equipment here?
