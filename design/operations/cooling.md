# Cooling

The low-temperature (LT) and high-temperature (HT) heat-rejection loops and
their radiators. Every other system's heat ends up here. Sources:
[operating doctrine §F](../ship/SYSTEM_OPERATING_STATES_v0.5.md),
[exterior radiator service](../ship/G19_EXTERIOR_RADIATOR_SERVICE.md),
`allocate_lt_cooling` in `game/world/ship_auxiliary_electrical.py` and the
installed design data.

## The plant

| Part | What it is | Status |
|---|---|---|
| `LT-PLANT` | LT thermal plant in `ROTARY-UTIL-A` (life-extension refit) | Runtime |
| Four LT radiator wings | 937.5 kW each when the plant runs; service faces `EXT-RAD-LT-1` … `-4` | Runtime |
| Eight LT rotary interfaces | Two into the habitat ring (`ROT-LT-COOLING-A`, `-B`) and one into each cargo drum (`DR-xx-LT-IF`); the workshop rotor has its own | Runtime (drums) |
| Eight habitat manifolds | `HAB-01-LT-COOLING-MAN` … `HAB-08-…` | Data |
| 40 cabin fan-coils | One per cabin; `HAB-03-CAB-07` is a gen-2 replacement on a different branch from its labelled panel | Data |
| Two HT radiators | `RAD-HT-1`, `RAD-HT-2` in `THERM-HT`; generator heat rejection | Runtime |
| Local control | `LCS-LT`, `LCS-HT` | Data |
| Isolators | LT: 25 remote, 62 manual only. HT: 5 remote | Data |

## Normal

| | Value | Status |
|---|---|---|
| LT capacity | 937.5 kW × working radiators (3,750 kW with all four), only with coolant connected, plant running, motor ready and service assured | Runtime |
| Priority | The drive's heat is cooled first; the rest is the environment budget | Runtime |
| Cargo share | min(120 kW, 10 % of the environment budget) | Runtime |
| Radiator skin | Entry for service only below 315.15 K (42 °C); a wing settles over about 1,500 s | Runtime |
| Manifold inspection | A scheduled habitation manifold inspection | Data |

## What the lead mind runs

**New**, through the `LCS-LT` and `LCS-HT` gateways:

- **The heat budget.** Plans drive, habitat and cargo heat against working
  radiators; warns before a burn or a radiator outage will squeeze habitat or
  cargo cooling.
- **Radiator branches.** Brings wings in and out of service, and isolates a
  wing for repair — the two HT radiator isolators are already operable from
  `ENG-CONTROL` (**Runtime**).
- **Derating.** When rejection can't keep up, sheds non-essential generation
  and industrial heat first (doctrine §F), through [power](power.md).
- **Distribution.** Keeps habitat manifolds and fan-coils in their normal
  state.

## What needs hands

- **Radiator repair** is EVA work from the wing's service pad, through a
  150-second platform transfer, only once the skin is cool (**Runtime**).
- **The 62 manual-only LT isolators.**
- **Manifold inspection** and fan-coil service.

## When things go wrong

| Event | What happens | Status |
|---|---|---|
| A radiator wing lost | LT capacity falls by 937.5 kW | Runtime |
| LT plant stopped or coolant disconnected | No LT rejection at all | Runtime |
| Hard burn | The drive takes its heat first; habitat and cargo get what remains | Runtime |
| HT rejection short | Generators must derate; ship is not abandoned (doctrine §F) | Data |
| `LCS-LT` gateway fails | The plant keeps running locally; the lead mind loses its view of the heat budget | New |

## What it leaves behind

- Cargo heat rejected, in joules, per drum (**Runtime**).
- Radiator skin surveys and service receipts (**Runtime**).
- The per-tick LT allocation — capacity, drive, environment, cargo — is
  computed but kept only as a sensor history in the [records](records.md)
  proposal (**New**).

## Open questions

1. Are habitat fan-coils remotely controllable, or only their manifolds?
2. Which loads count as "industrial heat" to shed first?

## Independent compute cooling — new support design

The original `LT-PLANT` is a shared heat-rejection source; nine computers
depending solely on that plant would violate the core's single-fault
containment rule. Draft [PR #151](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/151)
therefore adds five *separate* finite local thermal buffers and rejectors,
with no more than two computers and no common buffer per island.

At 2 kW per computer, the worst two-machine group creates 4 kW of heat:
120 seconds requires 480 kJ of locally available heat capacity. The
candidate nameplate is 720 kJ per group. **Surveyed free thermal capacity
starts at zero**, and only a genuine measured rejection rate may prevent
buffer use. The physics clock records generated, buffered, rejected and
uncontained heat. Uncontained heat is applied to the installed room gas
cell and drives a latched computer thermal protection fault.

This protects the short transfer interval, **not** unlimited operation without
LT, and does not substitute for an as-fitted steady-state LT/room-air heat
rejection survey. Cooling is part of the new infrastructure, not a new
lead-mind cognitive feature. See [ADR 0011](../decisions/0011-ship-control-support-overlays.md).
