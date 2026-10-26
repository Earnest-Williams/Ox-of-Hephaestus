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

### Accepted G19 implementation slice — water, waste and recycling

**Closed at subsystem level on 25 October 2026.** The same G19 branch now has verified finite potable/grey/black water processing, 39 t working / 162 t normal / separately guarded 70 t protected water, two independent treatment trains, verified local and fixed receivers and redundant valved wet rotary crossings, honest 90%/80% recovery, bounded sealed sanitary/industrial/hazardous waste, carried filter supplies, local permissions/receipts and a causally coupled power/fire/hydrogen relationship. [Evidence run 40245103836](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40245103836) passed **17 pure tests, 12 installed Evennia tests and 14 inherited G18 compatibility tests**, plus physical-design validators, on tested code revision `d3d2f9c537a7e03dbe9366821c5af241376f30a6`. Read [G19 water/waste system contract](G19_WATER_WASTE_RECYCLING.md) for operating controls, conservation, degraded modes and remaining cross-system dependencies.

**This acceptance closes the core Water and waste implementation slice.** Its port-side solid-waste transfer and shared material/tool-based repair dependencies are now separately accepted below. Crew exposure/physiology, whole-ship access and casualty recovery, full equipment-family coverage, hull restoration and the final autonomous voyage remain open. No partial subsystem pass authorises merging PR #138.

### Accepted G19 implementation slice — port-side waste offloading and shared repairs

**Closed at subsystem level on 26 October 2026.** The same branch now has separately authorised finite waste acceptance at actual external berths, operator-surveyed paths from the six installed sealed sanitary/industrial/hazardous receivers, time-bound freight capture/port transfer/empty-cassette return, real external custody and correct loss of ship mass by original material family. The same canonical world provides per-worker, locally carried finite spare parts; six reusable toolkits initially held at the fitted tool crib; safety/condition checks for installed equipment, access and isolators; persistent multi-crew repair work orders and timed completion; incapacity interruption, and explicit local restart. There is no universal repair button or offship disappearance of full cassettes.

[Dedicated 26 October evidence run #40250285584](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40250285584) passed **74/74 tests across five jobs**, including 29 pure material/fuzz checks, 6 actual installed Evennia repair/offload tests, 12 water regressions, 13 cargo/movement regressions and 14 inherited G18 fire/atmosphere/damage regressions. Tested runtime revision: `5eb76e257f30ac8a3b6aa6b8109c980eb304306d`. Detailed operational contract and known boundaries: [G19 waste-offload and shared repairs](G19_PORT_WASTE_AND_SHARED_REPAIRS.md).

**Remaining:** This closes the selected port-offload and shared-repair systems, **not** the full Equipment, Hull, Crew exposure, Navigation/access or whole-ship Recovery and voyage gates. PR #138 stays draft and unmerged until all G19 closure criteria are met.

### Accepted bounded G19 implementation slice — inner hull patching and restoration

A bounded **as-installed hull-breach restoration** path is now implemented on the G19 branch. It uses the existing 133 real pressure cells, mass-conserving vent physics, operator-attested repair room, shared individually carried spare parts and reusable toolkits. Qualified local engineers can perform a 600-second 2 kg temporary patch (leak reduced to 10%), then a 900-second 4 kg permanent restoration (residual leak closed). Work pauses if the worker leaves, loses qualification, or the compartment becomes unsafe. Atmospheric gas already lost is never recreated; major unpressurised ruptures cannot be patched from an ordinary unsuited worksite.

[Hull restoration operational contract](G19_HULL_BREACH_AND_RESTORATION.md) and dedicated `ox-g19-hull.yml` pure/installed-world tests document the limited feature. **Subsystem CI accepted on 26 October 2026:** [run #40261981436](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40261981436) passed **7 pure and 5 installed-world tests**, including fire interruption and correct material custody, at tested runtime `c22ff2eb`. This does **not** close the overall Hull gate. External suit access, comprehensive breach isolation, major hull replacement and all installed equipment family coverage remain outstanding. **The 40-crew voyage is explicitly excluded from the current work at the user's request.**

### G19 indexed passenger stations — implemented, CI verification pending

The ship now has time-bounded working connections for the **six installed drum personnel locks** (180-second captured transfer), **both HAB indexer stations** (300-second captured transfer), and the **independent WR-01 workshop-rotor indexer** (20-second captured transfer). The existing 421 spaces, 517 authored access links, 133 pressure cells, rotor motion state and equipment identities remain authoritative. Fixed-end pressure hatches are separately actuated, checked for real gas safety, and barred from opening when the corresponding rotary collar is captured. Indexed transfers use shared clock jobs, authenticated character positions, real component conditions, physical power and one-time request receipts. Failure holds the person aboard without teleportation; gas and cargo inventories are not reset or minted.

See [G19 indexed personnel transfer contract](G19_INDEXED_PERSONNEL_TRANSFER.md) and `.github/workflows/ox-g19-indexed-personnel.yml`. **Do not mark the overall Navigation/access gate closed**: current travel requires the rotor parked and hardlocked, and full moving-frame docking, decompression/EVA and end-to-end all-compartment route reachability remain separate. The user's instruction to omit the 40-crew voyage remains in force.

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
