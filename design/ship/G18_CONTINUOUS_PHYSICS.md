# G18 — continuously evolving physical ship state (first opt-in slice)

This increment operates **on the installed G17 v0.5 candidate** and its authoritative
Django/Evennia records, not a competing source-of-truth and not the design-only
reference trial. The 421 rooms, 517 access connections, 133 bounded gas cells,
808 equipment units and service/isolator identities remain unchanged.

**Deliberate arming:** after \`install_candidate\`, \`install_pressure_cells\`
and \`initialize_nominal_atmosphere\`, call
\`arm_continuous_physics(operator_approved=True)\` once in the server's game-time
epoch. A second call never resets a casualty. Restarted worlds can call
\`ensure_continuous_physics_clock()\`; the server start hook only starts a
persistent timer when the operator has armed a scenario. No player or AI can arm
one or inject a breach/fire.

## Physics and causality

- Each pressure cell persists actual finite gas mass, oxygen, CO2, smoke tracer,
  temperature, stored combustible fuel, heat exposure and local thermal damage.
  Initialise as a labelled **fictional baseline**, not measured oxygen or
  installation condition. Vents discard gas and its species; no infinite refill.
- Open/unfaulted installed **atmosphere ducts** permit finite recirculation,
  including smoke/heat into adjacent cells; closed pressure hatches remain
  separate boundaries. Each tick uses the installed switch states, not
  immutable reference switch states.
- An installed generator must be online, have its real feeder conducting,
  and satisfy the selected load profile for assured bus service. The combined
  generation cap is 3.3 MW and the auxiliary-only budget cannot silently run
  the normal 1.35 MW schedule. Batteries/flywheels have no credited infinite
  dispatch.
- LT cooling requires actual coolant connectivity, active LT plant, nonfaulted
  radiator wings and **assured** bus power. Modeled wall/cabin thermal inertia
  prevents immediate temperature jumps. Unrejected heat produces cumulative
  equipment damage at authored locations.
- Operator-seeded finite fires consume oxygen, make accounted combustion
  products and smoke, and heat surrounding gas and structural inertia. Mist
  requires an active installed fire-main supply, fire pump, power, finite water
  from \`INV-WATER-NORMAL\` and a verified **local** technician with breathing
  protection. It is not a universal extinguishing wand.
- Bounded 10-game-second integration steps; each transaction advances at most
  60 game seconds, with a **persisted** last processed game timestamp. Longer
  outages are caught up in subsequent transactions rather than inventing a
  massive unintegrated jump. The world ticker never calls Concordia or GOAP.

## Crew contracts

\`oxplantread air\` and \`oxplantread <local-equipment-id>\` report local
*scenario* readouts, not an oracle about unvisited damage or historical
drawings. \`oxplant <32-hex-id> switch <isolator-id> <open|closed>\`,
\`oxplant <id> plant <unit-id> <on|off>\`,
\`oxplant <id> schedule GEN-M <essential|protected|normal|demanding>\`,
and \`oxplant <id> mist PZ-HAB-XX <start|stop>\`
go through one world-owned transaction. Permissions, literal equipment
presence, damage and realistic physical actuator delays are enforced
server-side. Each successful local intervention commits its physical event and a row in the
existing global `WorkReceipt` ledger in the same transaction. An identical
request replays the original outcome; a request ID already used for legacy
ship or social work is rejected. Dead characters cannot operate equipment.
G17 operator-only gas vent/equalisation helpers are forbidden once the new
oxygen/smoke ledger is armed, avoiding silent constituent desynchronisation. Failed authorization cannot
grant a receipt or modify physics.

**No unrestricted repair, traversal, refuelling or force-open commands.**
Both human and synthetic characters use the same allowlisted command
surface. The world still requires the next maintenance-task and suit/
seal-integration milestones before crew can freely access all compartments.

## Limits, acceptance and next gate

This is explicitly **game engineering, not NASA certification**.
The first slice is lumped thermal inertia and ideal-gas mixing, **not CFD**,
measured leakage, validated oxygen chemistry, local smoke-layer CFD, liquid
hydraulics, truthful sensor faults, or precise rotating-joint physics.
Combustible fuel and incident rates are operator-established scenarios.
It does not imply inhabited 40-crew operation is safe or automatic.

Acceptance must establish: finite gas/combustible/water accounts;
damper-specific smoke spread; open-circuit/overloaded dispatch; cooled
versus thermally exposed rooms; breached equipment degradation;
unauthorised and replay-safe crew actions; transactional rollback;
cold/restart continuity; and no effect on the unarmed legacy world.
The next milestone is physically verified local maintenance, pressure
hatch/suit interlocks and actual 40-character concurrent work routes.
