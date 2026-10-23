# Electrical, fallible local control and crew evacuation — Ox v0.5

**23 October 2026 · Design-candidate casualty evaluation on PR #102.**
This is a pure-Python physical-reference extension of
`fire_smoke_thermal_v05.py`, **not** an Evennia data import,
automatic crew AI, sensor oracle, or permission to operate the current vessel.
Run `python design/ship/check_electrical_evacuation.py` to
exercise all coupled tests against the actual selected ship v0.5 JSON.

## Canonical topology and authority

- **438 electrical nodes, 450 power edges, 466 breaker/isolation points**
  resolved by their real equipment IDs, including main and auxiliary
  generators, A/B MSBs, protected bus, two independently fed rotary power
  interfaces, eight HAB protected panels and sectionalised ring supplies.
- **421 real rooms and 517 access links** retained without added room
  identifiers, dungeon conversions, imaginary bridges or teleportation.
  Access graph carries each authored traversal time, restricted activity,
  pressure-boundary ID and cargo/environment classification.
- The previously verified **133 gas pressure cells, 339 physical pressure
  boundaries**, independent 131 unknown cargo/process thresholds, 213
  atmosphere service edges, 73 fire-main edges and 79 LT edges remain
  unchanged. This increment composes those existing relations; it does
  **not** replace design JSON, measured-world state or the earlier validators.

### Source dispatch and source-to-load proof

Authorial equipment references specify GEN-M **3.0 MW**, GEN-A and
GEN-B **0.75 MW nameplate**, an overall installed **3.3 MW continuous
delivered envelope**, **1.55 MW** normal service load, **2.6 MW**
demanding schedule and **0.75 MW** nominal protected schedule.

The test uses **0.65 MW of selected essential load per surviving auxiliary**
as the conservative single-auxiliary operating point. It does not
credit the difference between the selected essential schedule and
generator nameplate as magically delivered safety power.
Both auxiliaries together are conservatively screened as at most
1.30 MW for the selected essential scenario. The independently
existing normal-service and protected budgets **must not** be
summed indiscriminately as independent plants.

The cold reference dispatch explicitly starts GEN-M and GEN-B
ON_LOAD, GEN-A OFF, no shore power, and no credited backup
battery/flywheel endurance. Batteries **exist** but their usable
charge, switching state and time under load must be proved before
quantitative bridging can be counted. **Zero credited battery
endurance is not a claim that the batteries are absent or empty.**

An electrical path requires every real selected breaker and source
feed, plus enough dispatched capacity for the selected load schedule.
Only actual ring feeders and the verified main cross-tie permit
bidirectional backfeed. Directed protected-load and source feeds
cannot run backward to energise an otherwise isolated main bus.
Breakers do not automatically change state because GEN-M tripped;
explicit load shedding, source selection and protection transfer are
separate operator actions. Synchronisation evidence is required to
close the central MSB A/B tie. A reported breaker state is not the
installed breaker contact position.

### Mixed-generation inherited wiring

The published v0.5 refit exception for **HAB-03 cabin 07** is
deliberately retained: the fan-coil's power branch is physically
tapped from **HAB-03 SG2 corridor distribution**, not cabin 07's
own panel. Its cabin-panel breaker is **manual-only** (refit
generation 3); the fan-coil is separately controlled through a
replacement generation 2 breaker. Switching the cabin panel off
cannot silently disconnect the fan-coil. Switching the SG2 feeder
also loses the fan-coil regardless of cabin-panel indication.
The test places a real scenario technician at each actual breaker
location before claiming manual operation.

### Control and telemetry failure

The experiment distinguishes five phases: command accepted into a
queue, simulated control propagation delay, physical actuator
attempt, actual valve/breaker state, and the displayed readback.
A fault can intervene between command issue and the due actuator
time. Loss of the real protected control bus or communication link
makes a pending remote order fail instead of teleporting the valve
to the requested state. A jammed valve remains jammed.

A **manual** operation requires a staged worker in the isolator's
real authored room, recent compatible atmosphere evidence and a
manual-operable mechanism. **Remote** operation needs a supported
remote actuator, an energized protected bus and working transport.
The BR-06 repaired coolant sleeve remains a manual-only exception:
a remote bridge-room indication is not an actuator.

Normal telemetry may be missing, stale or stuck at OPEN/CLOSED.
Readbacks intentionally carry **no `verified_physical_state`**
authority; engineers require separate field verification. Similarly,
a detector with no verified power reports unavailable rather than
"all safe." Stuck-silent and false-alarm sensor faults alter the
indication, not a fire's fuel/oxygen/smoke state. No AI character
can inspect the simulator's private fire object as an observation.

### Power-dependent real equipment

- A failed feed can interrupt powered ventilation mixing; physically
  OPEN dampers remain open, so differential-pressure passive leakage
  remains possible. This is not the fiction of power-fail-shut valves
  where no such actuator is installed.
- The two ECLSS processing stations must be reachable through their
  actual electrical load panels (HAB-06/ECLSS-A and HAB-08/ECLSS-B)
  **and** their previously checked ventilation return paths. A working
  scrubber does not create grid power, gas, oxygen or air flow.
- Fire-main delivery and LT service now require a separately
  confirmed plant-power witness and protected distribution.
  The candidate source does **not** contain unique electrical feeder
  nodes for FIRE-PUMP-FWD/AFT or LT-PLANT; these remain explicitly
  *conditional*, not invented as verified electrical routes.
  The full fire-water/thermal coolant paths remain tied to the
  existing real-service networks.
- HAB emergency luminaires and fire detectors use their *actual*
  separately breaker-fed protected-load nodes. One can go dark
  without magically disabling the other.

### Evacuation, gear, occupancy and observations

Route planning uses the real **517-link** space graph. A rated hatch is
not traversable until *physically open*, however close it appears on
the wire drawing. Unknown cargo, vacuum exterior, freight-only
passages and restricted maintenance routes are never promoted into
habitable shortcuts. Crew and engineer access classifications remain
distinct. Closing/impassably damaging a link removes it from the
available route graph.

A planned path requires recent local pressure and atmosphere samples.
A healthy route is not a guarantee that all segments will stay safe:
the execution helper advances actual casualty simulation time for
every segment and rechecks the destination at each threshold.
Participants move physically from their recorded originating room;
the total cannot exceed **40 crew**. A delayed or blocked leg retains
them at the last verified room, not at a hypothetical refuge.
A moving group has a deliberately chosen *screening* walking
concurrency of four people per authored link traversal period; it is
**not** a physical hatch certification or measured throughput.
Movement incurs smoke/oxygen/heat/pressure exposure through the
existing casualty model.

The optional smoke-breathing sets protect against smoke while
retaining a **70 kPa minimum pressure / 50 °C maximum** trial
constraint. These sets are **not vacuum spacesuits**. Portable
lighting may enable passage when a circuit fails or a bridge has
no independently confirmed illumination; it incurs a journey-time
penalty. Test-available sets and lights are explicitly bounded
scenario allocations from existing DC locker assumptions, **not**
new global ship inventories or an infinite gear generator. Personnel
must hold those allocations before using them.

## Acceptance matrix

The adversarial test suite verifies:

| Damage-control conflict | Required evidence and consequence |
| --- | --- |
| GEN-M trip during 1.55 MW normal schedule | Remaining GEN-B supplies at most 0.65 MW selected essential schedule; normal schedule not "still fine" |
| Explicit 0.60 MW load shed | Surviving B distribution can support selected essential loads |
| Protected A-to-B transfer | HAB detector/lighting and main PROT selection require distinct real transfer action |
| Main tie closure without synchronisation | Rejected; protected bus and batteries cannot reverse-backfeed the main board |
| Manual-only CAB-07 panel and separate fan-coil | Panel can darken while refit fan-coil survives on SG2; SG2 shutdown disables it |
| Generator blackout with ventilation ducts open | Powered smoke mixing stops, but valve positions remain physical |
| Pending remote damper close after control-power trip | Order fails; worksite crew can shut manually if actual safe access remains |
| Sensor stuck OPEN despite real CLOSED contact | Readback can lie and never supplies private world truth |
| Stuck-silent/false-alarm/dark fire detector | Readings diverge from actual fire state without mutating hidden combustion |
| HAB03 cabin through BR03 into HAB04 | Real rated hatch IDs, proof/gear/lighting constraints; two crew move without teleporting |
| Closed/impassable bridge or unknown cargo | No unsafe alternate route invented |
| Power blackout with portable lighting | Selected route can still function with allocated finite equipment |
| 40-person corridor traversal | Group travel is longer than one person's; all forty remain accounted for |
| Deliberately corrupted graphs and invalid controls | Missing breakers, non-existent rooms, invented buses, false boundary tags, authority bypass and excess gear rejected |

## Scope limits

This stage is for fictional engineering and gameplay verisimilitude:
a realistic network of causal dependencies, local maintenance,
imperfect evidence, finite resources and consequences, **not**
fabrication or spacecraft certification. It does not certify cable
capacity, fault-current protection, generator synchronization,
battery kWh, detector coverage, group evacuation crowd flow,
per-door latch power, suits or a legally enforceable remote
permission rule. The one-hertz trial timestep and nominal
door walk times are separate from real time in Evennia.

Most importantly, the current Ox is an inherited and multiply
repaired working freighter: live faults and as-installed revisions
must eventually be owned by the world, not treated as pristine
catalogue conditions. No runtime Evennia stores, model decision
routing, or published v0.4 ship are modified. PR #102 remains
a **design candidate**, not a canonical integration release.
