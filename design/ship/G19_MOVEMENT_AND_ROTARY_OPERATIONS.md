# G19 — Ship movement and rotating plant implementation

**Status:** implementation on draft PR #138; not yet integrated acceptance-verified. This describes a fictional, worn working freighter and an intentionally coarse causal game simulation, **not NASA certification**.

## Canonical mass, not a light-spacecraft placeholder

The ship's selected candidate contract is the only source for commissioned dry mass, commercial freight, FTL fuel, sublight reaction mass and mission/process fluids. The reference departure mass is **1,187,500 tonnes**. A former temporary 9,000-tonne dry hull / 8,000-tonne cargo cap / 240-tonne reaction-mass model is superseded. The motion ledger stores these categories separately; spent sublight propellant leaves the ship and reduces its instantaneous inertial mass.

Full commercial cargo is assumed aboard at reference departure, **not** an empty hold. This is a reference initial condition, not a verified container-by-container manifest. There must be no assertion that commercial freight is currently distributed evenly over six drums. Loading, offloading, freight restraint, transfer timing, drum balance and center of mass require real manifest transactions and remain unimplemented.

An already armed G18 world needs explicit operator-only `commission_g19_movement`; it does not silently reset the ship or overwrite existing velocity/position. Existing expended reaction mass is carried across and subtracted from the reconciled bunker. Existing nonzero cargo quantities that cannot be reconciled fail closed.

## Translational and attitude dynamics

- Independent inertial three-vector position and velocity; thrust commands expressed in body coordinates and rotated into the world frame by pitch/yaw/roll.
- Finite propellant, inertia including actual cargo, two separately operated main-drive and RCS fault gates, independent attitude state and angular velocities.
- Bounded 10-second substeps with power checked on each step. Main thrust is a **fictional gameplay-calibrated force**; it must draw spare power above the live distribution profile. RCS can use essential assured supply without powering the main drive.
- Active propulsion load is reflected in generator dispatch and hence generator waste heat. The movement clock records acceleration indirectly through before/after velocity and persistent current mass.
- `crew_physical_action(...,"helm","HELM","x+")` and `(...,"attitude","HELM","yaw+")` are authorized only at the real primary bridge or aft propulsion control. These are receipted world operations, not model-authored intentions.
- `local_physics_readout(actor,"helm")` reads the physical movement state from an eligible station; it does not provide an external navigation oracle.

**Limitations:** Drive and RCS fault gates are world state pending binding to individually identified installed drive/reactor hardware. Exhaust velocity, thrust, torque and inertia are explicit scenario parameters, not empirical qualifications. There is no FTL jump/navigation solver, docking dynamics, external object collision model or orbital ephemeris yet.

## Independent rotating equipment

`game/world/ship_motion_machinery.py` owns pure transitions for all eight separate mechanisms: DR-01–DR-06, the HAB ring and the independent WR-01 work rotor. Each has its own persistent angle, angular speed, speed target, brake, hardlock, freight collar, indexed passenger mechanism, bearing temperature, balance warning and bearing-hour count.

- Ramps are finite; stopping and power loss do not teleport spin to zero.
- Operating spin demands electrical power; bearing heat builds and rejects against its compartment reference model. Severe overheating trips the unit.
- Heavy freight requires zero target/speed, index to a known datum, structural brake/hardlock and an exclusive freight collar. Indexing itself needs power and takes time; no magic instantaneous alignment. Indexed personnel transfer and freight capture cannot overlap.
- WR-01 is independent of the habitation ring and six drums. At 60 m nominal carriage radius, the computed centripetal acceleration is available at the local gauge.
- Breakdowns of a cargo-drums' **personnel indexer** or **freight collar** disable those interfaces without physically seizing its independently driven drum. The two HAB bearings can inhibit the habitat mechanism.
- A loaded/drifting unbalanced drum cannot simply restart. The permitted provisional mass-imbalance threshold is a gameplay limit until the full individual drum mass manifests are implemented.
- Authorized engineers can command `rotor <DR-01|...|HAB|WR-01> <start|stop|release|index|hardlock|freight_extend|freight_retract|passenger_extend|passenger_retract>` through the receipted `oxplant` action at designated machinery stations. Local readouts expose mechanical state and centrifugal gravity.

**Important boundaries:** indexer motion currently tracks interlocks and extension state, not yet the precise moving-carriage path or person traversal. Freight release/air equalisation has to integrate the separate pressure/access boundary checks; a hardlocked collar does **not** alone authorize opening a pressure hatch. The six drum rates and working radii remain provisional game parameters until each installed drum contract is mapped, and WR-01's telescoping carriage radius is currently fixed at 60 m.

## Acceptance gates before merge

1. Run pure `test_ship_movement.py` regressions: mass-dependent thrust, fuel conservation under dual-drive operation, orientation vector rotation, blackout, rotor independence and index/hardlock sequencing.
2. Run installed `test_installed_ship_movement.py` against real installed 421 spaces, 133 cells and 808 equipment; verify authorization, receipt deduplication, mass sum, epoch migration and local readouts.
3. Run the existing coupled casualty suite unchanged; a new rotor or helm command cannot bypass fire, gas, damaged access, disabled power, manual isolators or world event receipts.
4. Model true loader, restraint and cargo transfer as separate receipted work using physical manifest rows, not whole-ship cargo mass edits. Bind the independent motor drives, bearing lubrication and temperature to actual ship equipment before claiming mechanical completion.
5. Validate late-game and damaged conditions. No claim of final G19 completion or merge until integrated acceptance.

