# G19 — casualty repressurisation from the fitted refill banks

**Status:** implemented on the G19 integration branch (PR #138). Acceptance is recorded in the [G19 acceptance record](G19_ACCEPTANCE_RECORD_2026-10-29.md).
**Design source:** [`PRESSURE_GAS_RECOVERY_v0.5.md`](PRESSURE_GAS_RECOVERY_v0.5.md) §2 and §6. No geometry, equipment or stock is added.

## Why it exists

Before this slice a breached cell could be patched and restored, but the gas it lost was gone for good. Oxygen generation makes oxygen only; it cannot replace the escaped nitrogen and buffer mass. The v0.5 ship already carries the hardware for this, which until now was classified but not simulated:

| Item | Identity | Location |
| --- | --- | --- |
| Bank A, 2.75 t dry breathable air | `GAS-REFILL-BANK-A` / `INV-GAS-REFILL-A` | `WATER-SHIELD-FWD` (non-breathable tank bay) |
| Bank B, 2.75 t dry breathable air | `GAS-REFILL-BANK-B` / `INV-GAS-REFILL-B` | `STORE-FLUID-AFT` |
| Regulators, 100 kg/h each | `GAS-REFILL-REG-A` / `-B` | `ENV-FWD` / `ENV-AFT` |
| Rotary unions to the HAB ring | `GAS-ROTARY-A` / `-B` | `ROTARY-UTIL-A` / `-B` |
| Network | `repressurization_gas`: 131 nodes, 132 edges, 143 valves | Headers, trunk sections, 69 cell taps, 8 HAB manifolds |

## Operating procedure

1. **Restore the shell first.** A cell with any registered leak, or a hull breach that is open or only patched, is refused.
2. **Line up the valves** with the ordinary `switch` action at each valve's station. As found, 99 of the 143 valves are closed and nothing reaches any cell. `ISO-GAS-BANK-A` is worked remotely from the `WATER-FWD` panel, so nobody enters the tank bay. A HAB arc is fed through its rotary union, the ring inlet, and the bridge make-up lines around the ring; a failed bridge line or manifold cuts off the arcs beyond it.
3. **Start metering at the regulator station:** `oxplant <id> gas_refill <PZ-cell> start:A` (or `start:B`) from `ENV-FWD` / `ENV-AFT`, with an engineering role. The setpoint is the cell's commissioned pressure.
4. **Watch the gauges:** `oxplantread gas_refill` at the station shows that bank's remaining stock, the active job, the downstream cell's pressure and oxygen fraction, and the last stop reason. It is not a ship-wide pressure oracle.
5. **Stop:** `gas_refill <PZ-cell> stop:A`. Delivered gas stays delivered.

A full HAB arc (about 3.1 t) takes more than 30 hours from one regulator, so the procedure is set up attended and then runs under the regulator's own pressure control.

## Physics and accounting

- Each physics substep meters at most 100 kg/h, never more than the bank's remaining stock or the mass that brings the cell to its setpoint.
- Delivered air adds mass, 23.2 % oxygen by mass, and enthalpy at 293.15 K to the cell. It is debited from the bank inventory by exactly the same mass and enters the tick's gas balance as a source term, like electrolysis oxygen.
- The ledger records commissioned stock and cumulative delivery per bank. Every tick checks that the inventory equals commissioned stock minus delivery, and that this tick's debit equals this tick's delivery.
- A job halts, with no refund, when its route is lost (a valve closed or a route node failed), the cell starts leaking again, the regulator or bank becomes unserviceable, the bank empties, or the setpoint is reached. Each halt is a ship event with the delivered mass and the original request ID.
- Requests are receipted and replay-safe; replaying a request or an equal-time tick changes nothing.

## Coverage boundary

77 of the 133 pressure cells have a tap or manifold: 46 personnel-trunk sections, 23 heavy-logistics bores and all 8 HAB arcs. The other 56 (bridges, drum service galleries and locks, hubs, indexers and the workshop rotor cells) have no tap in the design. They are refilled by filling a served neighbour and equalising through a rated hatch, which the G18b hatch exchange already models.

A job delivers only into its named cell. HAB manifolds passed on the way have local pressure feedback, so arcs already at setpoint draw nothing.

Routine inert make-up (`INV-INERT-MAKEUP-A/B`, mixers, inert regulators) is not part of this slice: no routine leakage is simulated yet, so it has nothing to replace.

## Code and tests

- `game/world/ship_gas_refill.py`: pure, typed ledger, metering and route evaluation.
- `game/world/continuous_ship_physics.py`: `gas_refill` crew action, regulator readout, tick metering and balance.
- `game/world/tests/test_ship_gas_refill.py`: 16 pure tests, including routes over the real v0.5 graph.
- `game/world/tests/test_installed_ship_gas_refill.py`: 4 installed tests. They cover the full breach, patch, restore, lineup and refill sequence on `PZ-HAB-03`; refusal of an unrestored breach; halts on a closed valve and a new leak; and an operator stop.
- Both run in `.github/workflows/ox-g19-final-campaign.yml`.
