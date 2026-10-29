# G19 — full-ship systems completion (single integration PR)

**Status: implementation in progress; NOT ready for acceptance or merge.**

## Attended service access into existing freight enclosures

The **13 previously freight-only machines** now have dedicated attended
service entry using **nine original, bidirectional, stationary freight
hatches**. The implementation introduces strict location, crew role,
air-pressure, rotor, cargo/waste/port and moving-worksite interlocks, an
exclusive durable lockout, occupied-room release refusal, signed work
receipts, and live repair-tick gating. Original 421-space / 517-passage
geometry and 808 equipment identities remain unchanged.
[Operating service contract](G19_FREIGHT_SERVICE_ACCESS.md).
**Accepted at subsystem level, 27 October 2026**:
[run #40580738273](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40580738273)
passed **12 pure and 11 installed Evennia tests (23/23 in two jobs)**
at tested runtime `fa692fea`. This verifies all nine actual service
gate entry/return operations, personnel lockout, stalled freight during
maintenance, damaged hardware refusal, retained globally receipted
state, and one genuine finite-spares machinery repair. The remaining
G19 full-ship integration and unsurveyed/vacuum worksite gates remain open.

## Verified access/worksite continuation (27 October 2026)

At tested runtime `a2f6ee9e`,
[run #40556713652](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40556713652)
passed **8 pure and 7 installed Evennia tests** across both jobs. This
covers all 421 original spaces, 517 links / 1,034 directional installed
exits, seven local ordinary-door families, physically timed drum and
moving-HAB return routes, independent aft EVA airlock recovery, and
808 mapped equipment worksite records. Exactly one unpressurised,
unoccupied `WR-TRIM-TANK-BAY` void has no personnel entry; all other
geometric rooms are connected. Machinery-site gas classification records
602 in authored pressure cells, 103 in vacuum, and 103 with unsurveyed
atmosphere; 13 freight-only hardware sites require distinct service access.
See `G19_ACCESS_COVERAGE.md`. This is bounded access acceptance,
not permission to merge or run the excluded 40-person voyage.

## Accepted bounded G19 radiator exterior access and maintenance (28 October 2026)

The **six existing** external radiator faces now have real suited entry,
return and maintenance through their original timebound EVA platform
passages. F1/F2 flywheel work is separately accepted, and neither
subsystem constructs extra ship space or air. Distinct LT/HT cooling
isolation respects the v0.5 installed hardware: four LT radiator wings
share the two original rotary LT manifold valves and disabled LT plant;
the two HT radiator wings have their original individually rated valves
which can be operated from the fitted `ENG-CONTROL` remote station,
without falsely declaring `THERM-HT` breathable. The original
coolant/heat budget remains authoritative.

Operator-surveyed radiator-skin temperatures, bounded thermal cooldown,
EVA gear custody, ship attitude/coast and braked neighbouring drums
govern permits, platform deployment, active transit and ongoing
600-second finite-spares repairs. Unsafe isolation suspends work
and transit rather than resetting machinery or teleporting crew.
Occupied platforms and active work prevent release. Helm, attitude,
FTL and rotor start commands respect installed maintenance lockouts.

[Focused acceptance run #40662087586](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40662087586)
passed **24/24 tests (17 pure, 7 installed Evennia) at `58315d7c`**.
See [G19 radiator access/repair contract](G19_EXTERIOR_RADIATOR_SERVICE.md).
The independent aft propulsion maintenance/plume face, unsurveyed
internal industrial compartments and full integrated acceptance
remain open. No 40-crew voyage was run.

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

### Accepted bounded G19 implementation slice — electrical distribution, storage and protective recovery

**Accepted at subsystem level on 27 October 2026.** The fitted power graph is **438 service nodes, 450 existing live/standby edges and 466 actual breaker/isolation points**, with no added fictional buses. The authoritative Evennia clock now uses directional generation/feeder reachability, both main boards and protected source selection, timed 15-second main-tie synchronisation, damaged-bus and open-breaker isolation, per-circuit latched overcurrent with real local reset, explicit load schedules and limited output under shortfall. It does not substitute online generator command flags for a physically available load connection.

The three original generators draw from the **existing finite 125-tonne cartridge magazine** at an explicitly fictional 2 kg/MWh energy conversion; spent material remains on board. Accurate **3.6 MW·seconds per kWh** energy arithmetic governs separately measured 8 MWh common operational and 12 MWh protected batteries, plus all **64 fitted F1/F2 flywheel modules (250 MWh combined nominal, not precharged)**. Actual installed feeder contact, real module condition and measured charge are prerequisites. Battery/protected paths cannot silently energise the wrong switchboard. Fire/atmosphere/cooling, water/waste, rotary HAB/EVA and cargo/propulsion retain their shared power state and physical operating constraints. Signed local work receipts are persistent and replay-safe, and suited work in unpressurised generator/flywheel spaces requires an operator-attested worksite.

**CI acceptance:** [run #40435001116](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40435001116), **77/77 tests in four successful jobs** at tested code `c586378e897fe284418456331e860ead50211596`: 22 pure electricity/energy tests, 16 installed Evennia switching/storage/cartridge tests, 14 inherited G18 fire/gas/thermal casualties and 25 installed G19 water/cargo/movement compatibility tests. The [electrical operating contract](G19_ELECTRICAL_POWER_AND_RECOVERY.md) and [machine-readable acceptance](G19_ELECTRICAL_ACCEPTANCE_2026-10-27.json) distinguish accepted graph-level operation from unresolved component identity coverage.

**Acceptance boundary:** The as-authored graph does not individually wire the 16 other local batteries or name dedicated electric motor feeders for the LT plant and two fire pumps; these are not credited as fabricated global electrical sources. The selected schedule is a coarse but causal game-world MW budget, not per-circuit voltage, instantaneous fault-current or physical-switchgear certification. Docked external shore-power connection has pure-kernel evidence but not a complete real-berth installed acceptance campaign. These limitations do not reopen the bounded installed distribution and finite-energy subsystem tests, but mean **whole-ship Equipment and full G19 closure remain open**. The 40-crew voyage was not run; **PR #138 remains draft and unmerged**.

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

### Accepted bounded G19 implementation slice — indexed passenger stations

The ship now has time-bounded working connections for the **six installed drum personnel locks** (180-second captured transfer), **both HAB indexer stations** (300-second captured transfer), and the **independent WR-01 workshop-rotor indexer** (20-second captured transfer). The existing 421 spaces, 517 authored access links, 133 pressure cells, rotor motion state and equipment identities remain authoritative. Fixed-end pressure hatches are separately actuated, checked for real gas safety, and barred from opening when the corresponding rotary collar is captured. Indexed transfers use shared clock jobs, authenticated character positions, real component conditions, physical power and one-time request receipts. Failure holds the person aboard without teleportation; gas and cargo inventories are not reset or minted.

CI acceptance: [run #40309694557](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40309694557), **40/40 tests across three jobs** (five pure, six installed and 29 movement/cargo compatibility), tested runtime `7c210fd0`. See [G19 indexed personnel transfer contract](G19_INDEXED_PERSONNEL_TRANSFER.md) and `.github/workflows/ox-g19-indexed-personnel.yml`. **The parked-indexer slice is accepted.** Its narrower statement that normal HAB rotating carriage and EVA are still unimplemented has been superseded by the bounded acceptance below. Full reachability across all authored spaces remains unverified.

### Accepted bounded G19 implementation — rotating HAB boarding, suited EVA and major breaches

At tested runtime `4e3f333a` on 26 October 2026, [EVA/large-damage CI #40344783606](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40344783606) passed **15/15 pure and 5/5 installed tests**, while [indexed motion CI #40344783647](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40344783647) passed **9/9 pure, 7/7 installed and 29/29 existing movement/cargo compatibility tests**. These are 65/65 tests in five green jobs for the two targeted workflows.

The HAB's *existing* A/B carrier hardware now accelerates and phase-synchronises to a running ring. A finite 300-second crew passage may finish while HAB keeps turning; loss of capture, power or healthy atmospheres pauses rather than teleports. The forward/aft existing EVA airlocks have individual interlocked hatches and isolated air-branch dampers, finite 90-second gas recovery/repressurisation, stocked breathing suits with CO2 accumulation, and rated exterior crawlers, rails and worksite platforms. Unsafe spinning drum surfaces and active propulsion/radiator sites refuse ordinary EVA.

A measured high-rate pressure-shell breach may be surveyed to its authentic exterior face. Powered isolation commands close **all installed rated bulkheads** on a 120-second work cycle; a failed/reopened boundary revokes containment. Suited engineers then perform genuine 2 kg temporary / 4 kg permanent hull work using shared spare-part custody and durable crew work receipts. No lost gas or spent suit supply is regenerated by repair.

**Acceptance is bounded**, not a claim of 421-room accessibility, operationally complete environmental medicine, universally safe exterior sites, every equipment family's behaviour, or readiness for a ship-wide voyage.

### Current G19 follow-on — individually persistent crew physiology

The separate [crew physiology integration](G19_CREW_PHYSIOLOGY.md) registers **named real Evennia crew objects**, samples measured compartment oxygen/CO2/smoke/temperature/pressure during bounded physics ticks, consumes finite room O2 with equal accounted CO2 mass, and persists injury and incapacity. Worn suits remain one distinct source of finite breathing gas, not a second addition to the room's oxygen demand. [Focused crew-physiology CI #40422476968](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40422476968) passed **20 pure and four installed tests** at tested runtime `32761e716`. This is bounded subsystem evidence, not completed medical assistance, not proven all-crew endurance, and not completion of the broader G19 integration regression matrix. **The 40-crew voyage remains expressly excluded.**

Every row requires a real integrated implementation, not merely documentation,
static JSON entries, an isolated demonstration or operator-injected outcomes.
Keep the existing G18 mechanisms where valid and extend them; do not create
a parallel simulator.

### Equipment-family continuation — 26 powered cargo, cultivation and workshop services

G19 now fits an additional **26 individually isolatable secondary equipment
feeds** to the actual co-located v0.5 room panels: six crop growing control/
nutrient machines, twelve drum-cargo thermal/gas packs, and eight workshop
tools/welding cells. The 78 added terminal/conductor/breaker objects are
segregated from the original 438/450/466 power network and the earlier
72 separately fused priority-motor circuits.

The original machine state is registered into an authoritative, persisted
per-unit duty ledger with real generator/shore/storage availability,
local isolation, cumulative operating/unserved time, and operator-visible
working cargo-environment and cultivation *pairs*. The machine shop's
high-energy tools retain a **manual restart latch** following interrupted
power: authorised engineers restore the actual feeder and explicitly restart
the affected machine at its physical location. Pre-existing control and
damage history is preserved when an older armed ship is upgraded.

Coverage audits and tests: `design/ship/check_g19_service_equipment_inventory.py`,
`game/world/tests/test_ship_equipment_services.py` and the real-world
installed electrical test class. The electrical four-job workflow covers
the new code and previous G18/G19 compatibility; complete same-head
acceptance is the next closure gate. This establishes powered machinery
availability rather than inferring fabrication output, crop yield or cargo
climate changes without actual materials, process state and operating
contracts.

Full implementation and per-room circuit mapping are in
[G19 electrical power and recovery](G19_ELECTRICAL_POWER_AND_RECOVERY.md).

### Continuing equipment implementation — cargo thermal custody and deterministic wear

The original six cargo drums now have explicitly **surveyed packaged-freight
thermal stores** with measured finite capacity, target setpoint and gallery
wall conductance. Cooling requires the existing independently fused
`DR-xx-CARGO-HX` plus `DR-xx-CARGO-GAS` operating pair, its
`DR-xx-LT-IF` original rotary coolant valve, the LT plant and live
shared radiator capacity. Six individual cargo skids are capped at
**20 kW equivalent each**, and the entire cargo cooling allowance is
limited to 10% of the LT thermal budget after propulsion, leaving occupied
spaces priority. Heat transferred between a cargo store and the original
`PZ-DR-xx-SVC` gallery is explicitly reconciled in that pressure cell.

Commercial freight stays in the existing authoritative cargo manifest.
Operator-confirmed temperature-sensitive lots have persistent temperature
excursions and **irreversible quality deterioration** when their actual
drum environment departs from the surveyed cargo band; split daughter
lots inherit an already spoiled parent condition. Freight mass, balance
and legal transfer custody remain unchanged. Local engineer setpoints
are attended, receipted and require a sound feeder and safe gallery.
[Cargo cooling contract](G19_CARGO_ENVIRONMENT.md) defines the bounded
thermal simulation, original valve/geometry audit and CI.

The 26 auxiliary crop, cargo and workshop machines now also have an
individual *running-hours-derived* wear history and service-clock state.
Fitted equipment becomes **degraded** after a calibrated service interval
and **faulted** after a larger interval. Only real operational time
accrues; an isolated breaker does not wear an idle bearing. A recorded
actual completed crew repair with finite material and worksite custody
can clear worn-out part history; an electrical reset cannot.
Original run-hour and repair provenance are imported without crediting
an inherited freighter as freshly overhauled. A one-time operator
attestation may record pre-existing fatigue.
[Machinery wear and service contract](G19_EQUIPMENT_WEAR_AND_MAINTENANCE.md)
documents operating classes and test cases.

The current four-job electrical workflow includes **pure and installed
cross-system tests** for cargo heat/mass custody, physical LT valve
isolation, cold-freight quality and split inheritance, machine
degradation and faulted attended restart, plus the inherited G18/G19
atmosphere, water, movement and full power compatibility suites.
The formal completion gate is the **same revision's final run**, not an
earlier pure-only pass.

## Accepted original aft nozzle workface (28 October 2026)

The installed `EXT-PROP-AFT` exterior work pad now has positive exhaust
and temperature observation, a fuel-consumption signature, an exclusive
plume permit, physically disabled MAIN/RCS, and a 120-second original
EVA passage with real suited crew. Normal ship thrust, attitude
changes, FTL engagement and drive re-arming remain inhibited until the
workface is vacated and the permit released. The return EVA path is
retained after a controller casualty. This is an inspection
station; the ship's pressure-unknown `PROP-SVC` room and any fictional
external nozzle replacement remain outside this gate.

[Acceptance run #40665213567](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40665213567)
passed 17 pure + 4 installed tests (21/21) at `2e474b3f`.
Details: [Aft propulsion EVA inspection](G19_AFT_PROPULSION_EVA_INSPECTION.md).

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


## Late G19 subsystem continuation — food, medical, workshop and propulsion (28 October 2026)

The living ship now has real finite installed provisioning and hydroponics,
attended medical stabilization and convalescence, separately isolatable
workshop machinery, original-part fabrication and local measured propulsion
output. All these use the **same G19 Evennia physics clock, original rooms,
source-material ledgers and authenticated replay-safe worker receipts**.

- **Medical:** bounded first aid and slow convalescence passed its earlier
  two-job installed medical gate
  [run #40771595898](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40771595898).
  The subsequent physical `HAB-04-MED-OBS` revision now gives the original
  observation bay its own personally delivered stock, independently
  fed original panel/isolator and actual attended continuing care.
  Unlike the treatment room, the original observation room has separate
  `ISO-HAB-04-MED-OBS-LP` and `NODE-HAB-04-MED-OBS-LP` under the shared
  real `PZ-HAB-04` atmosphere; the separate independent pressure cell
  of medical isolation `HAB-04-MED-ISO` is not confused with it.
  The observation-bay extension has its own new pure/installed CI and
  must not be counted accepted until the final code-head jobs pass.
  See [HAB-04 medical care](G19_MEDICAL_CARE.md).
- **CNC original part production:** positive surveyed existing `INV-SPARES`
  workpiece source; actual local CNC/lathe service, delivered electrical
  power and measured live spindle; 90 s per kg of attended machining,
  75% finished mass / 25% physically retained offcuts. A four-kilogram
  blank produces a three-kilogram repair part (with actual authenticated
  failed-machine repair) and one kilogram of carried industrial waste.
  [Full CNC pure/installed green #40772270736](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40772270736).
  See [workshop fabrication contract](G19_WORKSHOP_FABRICATION.md).
- **Original twin welding cells:** locally staffed `WELD-CELL-A/B` use
  individually surveyed and transported finite filler plus a real base
  replacement part. Powered arc work generates measurable and thermally
  accounted kJ inside the original `SHOP-WELD` gas cell. A representative
  3 kg base and 1 kg electrode produces 3.85 kg welded output and 0.15 kg
  of retrievable industrial slag. Two-job pure/installed **combined
  CNC + welding** baseline
  [#40773822827 passed](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40773822827);
  the later source-specific `fault` positive-arc restart verifier requires
  the expanded test workflow on the exact runtime. See
  [welding and spent-material contract](G19_WORKSHOP_WELDING.md).
- **Main propulsion:** a staffed `PROP-CTRL` work receipt now
  establishes a before/after **real consumed propellant and measured
  three-axis velocity change**, not an ON flag. The main-drive
  proof plus original aft nozzle inspection passed the two-job
  [installed propulsion gate #40772191972](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40772191972).
  Critically, original `LCS-PROP` is physically at `PROP-SVC`,
  **not** `PROP-CTRL`. A subsequent G19 build now models its existing,
  separately rated `ACC-PROP-SVC` from `PZ-TRUNK-B-AFT` with **one-time
  physically measured isolated bay gas**, a finite bounded trunk-to-bay
  equalization bleed, mutually closed original freight hatch,
  real individually held EVA suit/oxygen, owner-specific lockout and
  attended access. The original unclassified bay remains outside the
  133 previously sized pressure cells: it is **not** silently renamed
  breathable or vacuum. A genuinely present engineer must traverse the
  original exit, close the rated hatch, isolate the original room power
  and consume physically issued repair parts over actual elapsed time
  before returning through the same hatch to resume a measured
  propellant-and-delta-v proof. Pure gas/pressure/conservation and permit
  tests have passed; the installed multi-phase Evennia repair/drive
  acceptance is being verified in dedicated CI. See
  [original propulsion bay maintenance contract](G19_PROPULSION_BAY_SERVICE.md)
  and [aft nozzle inspection and drive witness](G19_AFT_PROPULSION_EVA_INSPECTION.md).

**Integration boundary:** G19 still requires wider equipment-family and
worksite characterization, remaining unsurveyed machinery zones, full
multi-system casualty/replay testing and original whole-vessel closure.
The deferred 40-crew voyage has not been run; PR #138 remains draft
and unmerged.


## G19 as-fitted industrial service continuation (29 October 2026)

A 16-room industrial extension on this same draft branch operationally models
the four previously unclassified aft machinery galleries (THERM-HT, FTL-SVC,
FUEL-SVC and REACTION-SVC) plus BE-01..12 bearing rooms, two for each of
the six original DR-01..06 cargo drums. It preserves all 421 source rooms,
517 original links and 808 original equipment identities; it does not turn
these into new pressure cells or assume their original gas is breathable.

The source-frozen worksite register in
[G19 industrial service and casualty contract](G19_INDUSTRIAL_SERVICE_AND_CASUALTY.md)
and the world-authoritative runtime provide:
positive one-time real-gas survey, 20 kg maximum physically sourced clean
trunk-to-bay equalisation, 2 kPa differential gate, original rated hatch,
per-person issued finite-oxygen suit, individually signed permit and
authenticated movement/inspection receipts. Aft machinery and original HT
valve, FTL, main/RCS drive, and braked cargo-drum isolation are tied directly
to real plant state. Failed machines require their original local breaker
OPEN during finite-spares repair; independently fitted motor feeders must
also be genuinely open. A live work order padlocks re-energisation.
Small shell leaks draw down the previously enclosed gas and add exactly
that gas to loss-to-space; a present, suited worker needs an authentic
assigned toolkit, 2 kg of already issued original spare material and
180 seconds to seal a bounded leak, with all worksite/isolation checks
repeated each tick. Larger unsafe leaks have no imagined internal bypass.

A physical breach at FTL/FUEL inhibits translation; THERM/REACTION
casualties inhibit propulsion; a bearing annulus leak orders the associated
rotor to coast down under existing continuous dynamics. An active
high-energy-room permit separately blocks conflicting restart commands.
These are game-world causal checks, not certification.

**Acceptance accounting:** The initial pure industrial and inherited
installed generator/PROP-SVC regression jobs passed at
[run #40793435817](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40793435817),
while that run's first new industrial installed fixture was corrected after
it tried to enrol an engineer before physically boarding the real ship.
The corrected and expanded pure, installed and compatibility suite is
[run #40794343776](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40794343776).
The full 3-job gate must be green at the relevant code head before declaring
the 16-room integration **accepted**. Do not infer acceptance from prior
green code or this documentation revision.

The other 63 original unclassified spaces are not all similar enclosed
machine bays: 48 manifest-dependent drum cargo sectors, 12 cargo portals
and 3 shield/trim geometric spaces require separately tailored access and
material/thermal safety rules. Original WR-TRIM-TANK-BAY remains a reviewed
noncrew void. Do not invent an ordinary personnel hatch into it.

PR #138 remains draft and not merged. The excluded 40-crew voyage has
not been run. The full G19 whole-vessel cross-system closure remains open.


## G19 original 63 unclassified cargo/port/shield closure (29 October 2026)

The previous 16 industrial rooms and original generator/PROP-SVC bay work
retain their exact-head positive installed acceptance. The remaining
**63 unclassified spaces** now have source-fitted, class-specific authority
and physics in the G19 branch, not a fictitious fourth generic machinery
room type:

- **48 manifest sectors** with 48 original rated personnel doors and
  48 original cargo-only freight rail connections; finite as-found gas,
  per-sector manifest allocation, independent pressure chemistry, time-
  and receipt-bound actual cargo worker access, real oxygen/CO2 and heat
  accounting for unsuited people in genuinely approved compartments,
  held crew permits, and leak-to-space plus finite issued-spares sealing.
- **12 commercial portal sleeves**, non-personnel, with exact physical
  berth, original closed rated seal and its actual revision, actual
  handler and hardlocked drum; these same controls gate the original
  commercial and sealed-waste transfer systems. Docking alone is not
  proof of safe sleeve operation. Original mass continues to move on
  time-bounded loading/abort equipment.
- **3 shield/trim spaces**: penetrated nonbreathable bow shield and
  original field hardware, forward annular water/radiation tank with
  real remotely operable gas-bank isolator, and original WR-01 trim
  reservoir with *no* personnel hatch. Authenticated inspection from
  actual controls does not conjure breathing gas, water, a new exit,
  or instant remote structural repair.

Original **110 rated interfaces** (96 sector person/handling, 12
commercial sleeve, two shield/tank service) are retained; the 133
commissioned ordinary pressure cells are not expanded by inventing
another 63 safe atmospheres. The original manifest remains
authoritative for cargo and motor imbalance.

The implementation is in
[G19 cargo, port and shield closure](G19_UNCLASSIFIED_CARGO_PORTAL_SHIELD_CLOSURE.md).
The three-job focused CI is
[Ox G19 63-space acceptance workflow](../../.github/workflows/ox-g19-unclassified.yml).
Until the actual latest runtime head has all three *pure, installed and
compatibility* jobs green, this extension is **implemented but not
accepted**. Draft PR #138 is not merged. No 40-crew voyage has been run.


## Coupled cargo decompression and human casualty transport (29 October 2026)

Runtime `f0221bbd` passed the existing three-job G19 original-space
acceptance on [run #40876903140](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40876903140).
This revision adds real open-hatch gallery/sector gas mixing with 10-second
concurrent shell leakage, bounded empty-sector behavior, damaged-open door
physics and authenticated real survivor return. The installed campaign also
carries a separately injured patient, with two enrolled crew, from the
isolated DR-01 rotating service gallery to its original co-rotating hub
using the actual timed entrance. The cargo drum's coast and restart
interlocks remain sourced from the same real damage/manifest ledger.

See [G19 unclassified cargo/portal/shield closure]
(G19_UNCLASSIFIED_CARGO_PORTAL_SHIELD_CLOSURE.md) for accounting invariants,
roles, casualty and isolation cases, and original 48/12/3 space inventory.

The expanded G19 workflow adds an independent adjacent systems acceptance
job for existing EVA, major hull damage, casualty transport, hull restoration,
cargo movement and medical procedures. The earlier three-job runtime
acceptance is green; the expanded cross-system gate is newly requested.
No 40-crew voyage has been performed. PR #138 remains a draft.

## Final G19 multi-system process recovery (29 October 2026)

The bounded whole-ship casualty, clock replay, atomic rollback and independent
Python-process persistence campaign is documented in
[G19 integrated casualty/restart acceptance](G19_INTEGRATED_CASUALTY_RESTART_ACCEPTANCE.md).
The three-job initial campaign was accepted on runtime `18d42358` at
[run #40888000855](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40888000855).
A fourth, independently isolated CI job verifies that two distinct Python
interpreters survive the same original physically damaged Evennia database.
It passed on runtime `0ed5f0d3` at
[run #40889821371](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40889821371),
with **4/4 jobs green**. The test recorded 18 kg lost before process exit
and 87 kg cumulative loss after durable restart/catch-up (no material refill).
The acceptance probe's exception-precision correction was retested on
runtime `32cb309d` at
[run #40890643600](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40890643600),
with all four jobs green.

This is a bounded integration acceptance, not a full game release or
NASA-style physical qualification. PR #138 remains draft/unmerged; the
40-person voyage is not part of this development round.

## Complete as-fitted equipment-family closure review (29 October 2026)

The 808 original equipment identities across 91 families are now subject to a
strict installed Evennia audit. Evidence tiers and the remaining named
portable/exterior machinery obligations are recorded in
[G19 equipment-family closure audit](G19_EQUIPMENT_FAMILY_CLOSURE_AUDIT.md).
The forty individual cabin terminal cooling contracts passed three-job
acceptance [#40894829437](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40894829437);
the full equipment identity/family audit passed both jobs at
[#40895961792](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40895961792).
The two independently fitted rescue-bay scrubbers have now been integrated
with as-found finite media and operating time; the dedicated installed
acceptance remains the authority for final confirmation of that slice.
