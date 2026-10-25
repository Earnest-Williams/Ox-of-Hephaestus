# G19 — full-ship systems completion (single integration PR)

**Status: implementation in progress; NOT ready for acceptance or merge.**

## Decision

G19 is one integration branch and one pull request for completing the ship's
physical and operational systems. Do not split the work into feature PRs.
Do not represent passing component checks as ship completion. The final
acceptance voyage is run only after the implementation and cross-system
integration are complete. Existing automatic CI may run on intermediate
commits; those runs are not the final acceptance gate.

This is a game-world engineering contract: believable causal consequences,
finite resources, operationally meaningful local controls and persistent
damage on an old, repeatedly refitted working freighter. No NASA certification,
CFD, structural FEA or fabrication-grade qualification is required.

## Source of truth and boundaries

- Evennia canonical installed world and its persisted state remain authoritative.
- Read-only ship design geometry is a reference, not a second mutable world.
- All game-time integration uses one monotonic, bounded, replay-safe clock.
- Each resource flow has a source, destination, finite stock or capacity,
  explicit rate and conservation/ledger treatment.
- Crew operations require a real character at a reachable local station,
  adequate access and equipment, and a durable idempotent work receipt.
- An AI may propose actions but never directly rewrite physical state.
- Unknown spaces or unverified mechanisms must fail closed, not become
  magically breathable, accessible or powered.
- Ship repairs consume time, labour and finite material; restarting or
  resetting equipment is not the same as repairing damage.

## Implementation scope and closure gates

| Area | Required G19 behaviour |
| --- | --- |
| Electrical | Source dispatch, finite reserves where installed, feeder and bus topology, load priorities, protective trips, brownout/blackout and controlled restoration |
| Atmosphere | Bounded compartment gas inventories, breathing and CO2, circulation and treatment, finite replenishment, venting/leaks, pressure equalisation, smoke and contamination |
| Thermal | Equipment and crew heat loads, finite heat sinks and coolant circuits, radiator rejection, thermal storage, overtemperature trips and lasting damage |
| Fire | Fuel/oxygen consumption, heat/smoke production, ignition conditions, detection, local and distributed suppression, finite extinguishing media, secondary faults |
| Equipment | Per-family operational state machines for installed machinery, startup/shutdown, work cycles, wear, maintenance, faults and repair |
| Hull | Bounded breaches, isolation, depressurisation, temporary patching, repair and secondary equipment/crew consequences |
| Water and waste | Finite tanks, pumps, processing throughput, contamination, recovery, disposal and inventories |
| Cargo and mechanics | Cargo handling, rotary interfaces, interlocks, transfer cycles, mechanical wear and fault propagation |
| Propulsion and dynamics | Finite propellant/energy, commanded thrust and manoeuvres, mass and motion state, operating constraints and credible failures |
| Crew exposure | Local breathable-air/temperature/smoke/pressure effects, cumulative exposure, real protective equipment, incapacity and recovery |
| Navigation and access | Crew traversal of authored exits only, pressure-boundary/interlock checks, suit and transfer constraints, access to actual workstations |
| Recovery | Fault detection by available instruments, investigation, isolation, maintenance, spare parts, delayed restart and audit receipts |

Every row requires a real integrated implementation, not merely documentation,
static JSON entries, an isolated demonstration or operator-injected outcomes.
Keep the existing G18 mechanisms where valid and extend them; do not create
a parallel simulator.

## Completion criteria

1. All installed equipment families and resource networks are inventoried.
   Each is either simulated with defined causal behaviour or explicitly
   identified as passive infrastructure with a justified no-op role.
2. Normal operations and casualty operations use the same persistent state.
   No special-case test physics that the live world cannot execute.
3. Cross-system interactions work in both directions where physically
   appropriate: power/cooling, power/air, heat/fire, water/fire, damage/power,
   access/pressure, crew/environment, propulsion/power and cargo/mechanics.
4. A crew member can perceive a fault, travel legally to its station, operate
   machinery, consume materials, complete work and observe the consequence.
5. Long downtime, duplicate commands, restart, concurrent actions and
   out-of-order events do not create or erase resources or work receipts.
6. No unresolved high-severity physical-state inconsistency or bypass remains.
7. Only after implementation closure: execute unit/property/fuzz tests,
   independent process restart, multi-crew autonomous voyages and extended
   casualty campaigns. Archive machine-readable results and known limits.
8. Merge this PR only after those acceptance gates pass.

## Known G18 baseline, not G19 completion

The merged G18b world already couples rated open hatches, selected ducts,
power generation, cooling, fires, leaks, mist suppression, protection trips
and some local controls over 133 pressure cells. Its documented limits
include Developer-only ordinary traversal, limited hatch actuation, scenario
fault injection and incomplete maintenance/suit/rotary mechanisms.

## Implementation sequence within this ONE PR

1. Inventory existing canonical equipment/network families and current
   simulation coverage; establish conservation and state contracts.
2. Integrate resource flows and equipment operations in the existing clock.
3. Add fault, degradation, repair and environmental exposure semantics.
4. Enable verified access, traversal and crew action integration.
5. Close remaining mechanical, cargo and propulsion dependencies.
6. Audit complete system interactions; then run the final test campaign.

**No production activation and no merge while this document says
implementation in progress.**
