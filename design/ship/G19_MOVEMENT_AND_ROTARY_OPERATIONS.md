# G19 — Ship movement and rotating plant implementation

**Status:** implementation on draft PR #138; not yet integrated acceptance-verified. This describes a fictional, worn working freighter and an intentionally coarse causal game simulation, **not NASA certification**.

## Canonical mass, not a light-spacecraft placeholder

The ship's selected candidate contract is the only source for commissioned dry mass, commercial freight, FTL fuel, sublight reaction mass and mission/process fluids. The reference departure mass is **1,187,500 tonnes**. A former temporary 9,000-tonne dry hull / 8,000-tonne cargo cap / 240-tonne reaction-mass model is superseded. The motion ledger stores these categories separately; spent sublight propellant leaves the ship and reduces its instantaneous inertial mass.

Full commercial cargo is assumed aboard at reference departure, **not** an empty hold. This is a reference initial condition, not a verified container-by-container manifest. There must be no assertion that commercial freight is currently distributed evenly over six drums. Internal and external freight transfers now use receipted, bounded machinery jobs and explicit manifest mass accounting. Fully surveyed cargo placement, measured center of gravity and automated commercial port logistics remain unfinished.

An already armed G18 world needs explicit operator-only `commission_g19_movement`; it does not silently reset the ship or overwrite existing velocity/position. Existing expended reaction mass is carried across and subtracted from the reconciled bunker. Existing nonzero cargo quantities that cannot be reconciled fail closed.

## Translational and attitude dynamics

- Independent inertial three-vector position and velocity; thrust commands expressed in body coordinates and rotated into the world frame by pitch/yaw/roll.
- Finite propellant, inertia including actual cargo, two separately operated main-drive and RCS fault gates, independent attitude state and angular velocities.
- Bounded 10-second substeps with power checked on each step. Main thrust is a **fictional gameplay-calibrated force**; it must draw spare power above the live distribution profile. RCS can use essential assured supply without powering the main drive.
- Only **engine controls, valves, pumps and auxiliary electricity** draw from the 3.3 MW shipboard plant. Thrust energy is sourced from Ox’s explicitly fictional reaction-drive plant and finite reaction mass; the shipboard generators are not claimed to power a megatonne vessel’s plume.
- Firing deposits heat in a finite propulsion thermal store. Healthy low-temperature cooling and a usable radiator reject heat; without cooling the engine reaches a thermal trip. A crew engineer must attend PROP-CTRL, wait for cooldown, reset the trip and explicitly release the inhibit. Receipts do not conjure lost energy or reset damaged machinery.
- `crew_physical_action(...,"helm","HELM","x+")` and `(...,"attitude","HELM","yaw+")` are authorized only at the real primary bridge or aft propulsion control. These are receipted world operations, not model-authored intentions.
- `local_physics_readout(actor,"helm")` reads the physical movement state from an eligible station; it does not provide an external navigation oracle.

**Limitations:** Drive and RCS fault gates are world state pending binding to individually identified installed drive/reactor hardware. Exhaust velocity, thrust, torque and inertia are explicit scenario parameters, not empirical qualifications. A bounded fictional FTL route and fuel ledger exists, as does a commercial-berth contact and finite cargo handling contract. Neither is an orbital ephemeris, external collision solver, dynamic rendezvous or general docking navigator.

## Independent rotating equipment

`game/world/ship_motion_machinery.py` owns pure transitions for all eight separate mechanisms: DR-01–DR-06, the HAB ring and the independent WR-01 work rotor. Each has its own persistent angle, angular speed, speed target, brake, hardlock, freight collar, indexed passenger mechanism, bearing temperature, balance warning and bearing-hour count.

- Ramps are finite; stopping and power loss do not teleport spin to zero.
- Operating spin demands electrical power; bearing heat builds and rejects against its compartment reference model. Severe overheating trips the unit.
- Heavy freight requires zero target/speed, index to a known datum, structural brake/hardlock and an exclusive freight collar. Indexing itself needs power and takes time; no magic instantaneous alignment. Indexed personnel transfer and freight capture cannot overlap.
- WR-01 is independent of the habitation ring and six drums. The engineering shop carriage moves at a finite rate across the authored **24–75 m** range, with its opposed stores carriage at one-third radius. Heavy freight capture requires the carriage physically retracted to 24 m; workshop gravity is computed from its actual radius and speed.
- Breakdowns of a cargo-drums' **personnel indexer** or **freight collar** disable those interfaces without physically seizing its independently driven drum. The two HAB bearings can inhibit the habitat mechanism.
- A loaded/drifting unbalanced drum cannot simply restart. The permitted provisional mass-imbalance threshold is a gameplay limit until the full individual drum mass manifests are implemented.
- Authorized engineers can command `rotor <DR-01|...|HAB|WR-01> <start|stop|release|index|hardlock|freight_extend|freight_retract|passenger_extend|passenger_retract>` through the receipted `oxplant` action at designated machinery stations. Local readouts expose mechanical state and centrifugal gravity.

**Important boundaries:** indexer motion currently tracks interlocks and extension state, not yet the precise moving-carriage path or person traversal. Freight release/air equalisation has to integrate the separate pressure/access boundary checks; a hardlocked collar does **not** alone authorize opening a pressure hatch. The six drum rates and working radii remain provisional game parameters until each installed drum contract is mapped, and as-installed moving-carriage details beyond the modelled finite WR-01 24–75 m extension remain unverified.

## Reference commercial cargo and finite shipboard movement

The 900,000-tonne commercial cargo reference is preserved *on board*, but no
six-drum mass split is invented. The G19 cargo ledger starts with a single
unlocated onboard amount. An explicitly approved physical stowage survey moves
existing mass from that unlocated holding into named package or bulk lot
positions (drum, radial arm, azimuth, restraint). The operator can split known
restrained bulk into individual rated sled lots; such subdivision conserves
mass and cannot import or fabricate freight. Only independently surveyed
drums produce trusted moment/imbalance calculations.

Real 50-tonne normal / 100-tonne restricted sled transfers require an actual
local cargo worker, real `DR-xx-RADIAL-FREIGHT-HANDLER` and
`DR-xx-FREIGHT-COLLAR` hardware, a stopped indexed structural lock, retracted
personnel interface, real pressure-readiness for the occupied control room
and an independently rated capture boundary to enter the spine. Work moves
only after finite simulated handling time. Failures, isolated doors and loss of
power pause the actual job; cargo remains at the last committed location.
Unbalanced drums can unload under a hardlock to *correct* the imbalance, but
are barred from spinning up when above the selected balance limit. There is
no arbitrary off-ship disposal of material.

World-clock snapshot events retain cargo manifest hash, summary, current
transfer jobs and actual mass; operator survey events additionally preserve
the exact surveyed identifiers, masses, angular positions and source lot.
These are intentionally bounded rather than dumping 2,048 lot records into
every ten-second tick event.

## Installed drive, bearing, lubrication and handler faults

All six drum rotors now consult their two physically separate bearing
lubrication stations (`BE-01..12-LUBE-N/S`) and each drum's
`DR-xx-ROT-PWR` electrical interface. The habitation ring requires both
`HAB-BEARING-FORE/AFT`, while either sound
`HAB-DRIVE-FORE/AFT` can provide motor effort. The workshop requires
both `WR-BEARING-A/B`, one sound `WR-DRIVE-A/B`, the actual
`WR-01` mechanism and `WR-ROT-PWR-IF`. Failed
`WR-EXTEND-SHOP/STORES` prevent telescope motion independently of
workshop rotation. A failed indexer, freight collar, handler or bearing skid
has its own local consequence rather than globally destroying every drum.

## FTL movement and navigation

A separate, explicitly fictional FTL field is installed as
`FTL-TRANSLATION-FIELD`, with `LCS-FTL` local control. The selected v0.5
contract is **5–100c** and a reference economy cost of **400 tonnes per
light-year**, scaled by frozen leg departure mass and
`1 + 4 ln(speed_c / 5)`. Each leg is independently commissioned against a
destination and distance by the world operator, then engaged or aborted by
an authorised crew navigator at `CMD-PRIMARY` or `NAV-PLANNING`.
The **1,200-tonne FTL bunker reserve** is protected against routine
dispatch. The field consumes finite fuel progressively during simulated
voyage time, requires 0.20 MW electrical auxiliaries and thermal rejection,
and aborts safely if the actual field/control equipment, power or cooling
cease to be usable. Attitude and sublight commands are locked during
translation. Arrival changes a named navigation reference only after the
full timed passage; no fictional sky coordinates are minted by the solver.

The sublight drive uses effective **960 km/s** reaction exhaust velocity
and **11.645 MN** reference thrust in order to reproduce the selected
**~4 km/s total delta-v / <=0.001 g loaded** setting from its finite
5,000-tonne reaction mass. Those are *fictional* drive parameters, not a
claim about real exhaust technology. The 3.3 MW hotel plant supplies
control auxiliaries, not energy that creates the reaction plume.

**Still outside implemented operational closure:** measured per-package
hull/rotor center of gravity, dynamic cargo-port rendezvous and autonomous
dock service, high-fidelity trajectory targeting, traffic/collision
avoidance, full character movements and EVA, autonomous condition-based
repair of every unit, and long-duration 40-crew integrated casualty acceptance.
The route's named destination is an operator-supplied reference rather than
an inferred astronomical location.

## Cargo manifest and inter-drum freight (G19)

The selected **900,000 tonne** commercial payload is initially an accountable *unlocated mass aboard ship*. It is not silently split into six equal drum masses. An explicit operator-only `survey_cargo_lot` operation binds a reported lot to one installed drum and physical radius/azimuth; splitting a bulk lot creates an individually restrained, at most 100-tonne sled package **without increasing cargo mass**. Surveyed stowage positions compute the signed drum balance moment. A drum may be individually marked surveyed only upon physical operator verification; this is not inferred from the remaining unlocated shipwide mass.

The `oxplant ... freight <lot> <direction>` command is receipted, local to the handling collar, and advances over multiple timed physics ticks. A failed/isolated actuator, power loss, lost hardlock, open-personnel indexer, or closed/unsafe rated freight boundary suspends rather than completes the job. At the common fixed spine station, only one load/transfer may occupy its receiving position. The `from_spine:DR-04` form means that **the receiving drum** must stop, index, hard-lock and operate its own real collar and crew station; the original drum does not remotely transfer it.

After delivery into a new drum, a package is explicitly **unstowed/unrestrained** until a physical operator survey uses `restow` to certify its actual new berth. Such loose freight prevents drum spin-up. A locked drum may still remove mass to correct an imbalance: balance interlocks prevent acceleration, not recovery with the drum parked. Internal transfers preserve ship mass. External bulk portal operations now change ship mass over time while maintaining an explicit offship mass ledger. The ledger is not a real measured inventory until the operator actually surveys it.

The focused `ox-g19-movement.yml` GitHub Actions workflow runs on the **draft PR**, compiles the modules and runs actual Evennia movement, cargo, FTL and installed-world regressions. A draft PR is not automatically an acceptance pass: the workflow result and cross-system tests must be checked explicitly.

## Twelve commercial cargo portals and finite external transfers

Each authored DR-01–DR-06 P1/P2 commercial portal now has external port
handling, distinct from the internal 50/100 t freight spine. The world
operator must positively commission an external berth and a finite
consignment; these are external observations, not invented stored freight
or inferred celestial locations.

Crew at the actual cargo-control room or drum gallery may start a
receipted, time-bounded job using the real radial freight handler and
closed, sound gallery portal. A port needs a stopped, indexed,
hardlocked drum, a sound handling rail and spare electrical power.
Power failures, damage or a lost lock pause work; no teleportation.
The selected gameplay rate is **1,500 kg/s after 60 seconds startup**,
per available radial handler. Two portals on one drum share its
handler; operations in other drums remain independent.

Every partial tick debits or credits the ship's **actual inertial cargo
mass** and records matching external custody. Unloading associates
the cargo with the commissioned external berth. Re-loading it from a
different berth is prohibited; a new legitimate external consignment
must be explicitly registered. A newly loaded lot remains unsecured
until physically restowed, and an unverified cargo drum may not
spin up. A commercial mooring prevents thrust, attitude-control
manoeuvres, drum rotation and uncommanded undocking.

This is an operational game port interface, not an orbital docking or
collision-avoidance solver. It does not invent the detailed movement
of unseen port-side cranes or a construction-grade supply terminal.
The port tests run alongside previously passing ship movement and
G18/G17 coupled-physics regression jobs in the draft G19 PR.

## Commercial port interruption and recovery

A crew member at an installed cargo-control station can now send receipted
`oxplant <request-id> port DR-01-P1 pause:<lot>`,
`resume:<lot>`, or `abort:<lot>` operations. A paused or disabled handler
draws no active motor load and transfers no mass, but its occupied handling
rail remains unavailable to other consignments. **Abort is a commanded
physical reversal**, not a reset: the rig spends another startup interval
and pumps the partially transferred consignment back to the original berth
or hold at the same finite rate. Lost electrical service or damaged handling
equipment stalls recovery rather than silently completing it. Only after
the reverse cycle finishes can the berth be released.

Actual ship mass and external custody are reconciled at every intermediate
step, including reversals. A deterministic, seeded interruption test checks
that repeated blackouts and recoveries never create cargo. This remains a
fictional gameplay model of commercial facilities rather than a port-side
crane construction specification.

## Acceptance gates before merge

1. Run pure `test_ship_movement.py` regressions: mass-dependent thrust, fuel conservation under dual-drive operation, orientation vector rotation, blackout, rotor independence and index/hardlock sequencing.
2. Run installed `test_installed_ship_movement.py` against real installed 421 spaces, 133 cells and 808 equipment; verify authorization, receipt deduplication, mass sum, epoch migration and local readouts.
3. Run the existing coupled casualty suite unchanged; a new rotor or helm command cannot bypass fire, gas, damaged access, disabled power, manual isolators or world event receipts.
4. Model true loader, restraint and cargo transfer as separate receipted work using physical manifest rows, not whole-ship cargo mass edits. Bind the independent motor drives, bearing lubrication and temperature to actual ship equipment before claiming mechanical completion.
5. Validate late-game and damaged conditions. No claim of final G19 completion or merge until integrated acceptance.

