# Coupled atmosphere and damage-control trials — Ox v0.5

**23 October 2026 · simulation-operational reference only · PR #102.**
This is a bounded design experiment, not a connected Evennia atmosphere
model, an as-installed survey, a real pressure-vessel qualification, or a
crew/AI permission service.

## Physical basis and authority

The pure stdlib module `pressure_damage_sim_v05.py` loads the
existing **133** identified nominal pressure cells, **339** registered
pressure-rated access connections and **131** explicitly unclassified
receivers. It uses the original geometry and identities without inserting
extra rooms, pressure volumes or the convenient fiction that unclassified
cargo holds are vacuum or breathable. **83** cargo, process and service
rooms remain classified as unknown environment. There is no source data
change to the 421-space/517-access world; the baseline 5.5 t independent
air stores, 249.2 kg protected oxygen and 40-person maximum also stay intact.

A new trial starts with every pressure gate *closed* and nominally filled
reference cells. This is a deliberately cold-isolated experiment, **not**
a claim that every gate is normally shut, that the derelict ship is full,
or that any installed pressure sensor has recently been read. The simulator
runs with lower, midpoint or upper free-volume estimates from the existing
reference ledger. All three remain geometric fit-out screens, not measured
usable volumes. The 133 compartments have separate gas mass and oxygen
fraction; a surviving pressure shell does not automatically imply breathable
or sampled air.

## Coupled physical consequences

For each simulated time step (at most one second), flow is computed from
the existing rated **open** connections and registered hull breaches.
The model uses fixed-temperature ideal-gas scaling from 101.325 kPa,
20 °C and 1.204118 kg/m³ reference air. Its chosen **35 kg/s reference
open-hatch flow**, **0.25 kg/s symmetric composition mixing** and
scenario-defined nominal breach flow (18 kg/s in the HAB-03 trial)
are deliberately *lumped casualty parameters*, not measured hatch
conductances, high-fidelity compressible CFD, or hardware specifications.
Flow scales with upstream pressure and pressure ratio. Each open-door
transfer is capped at the mass required for the donor and receiver to
reach equal pressure, and all vacuum losses are bounded by physically
remaining mass. In a leak-only trial, no adjacent intact compartment
can rise above the original equilibrium pressure just because a small
bridge chamber was integrated with a finite timestep.

Open pressure-cell connections exchange total mass, oxygen and the
contaminant tracer. A breach or a failed-open gate to a space **known
to be vacuum** debits atmosphere as a finite exterior loss. Bank air
delivery debits the source inventory; the gas ledger tracks contained,
reserved and lost gas and must conserve their combined mass. The
contaminant tracer is a portion of previously existing carrier gas, not
material conjured by an AI.

A failed-open boundary to a cargo compartment whose atmosphere is
**unknown** does *not* turn it into an imaginary vacuum sink. It instead
flags all connected open pressure cells as **quantitatively uncertain**:
their reported pressure/O2 figures are withheld, sample-based unsuited
access is blocked, and they cannot be refilled on this stale model.
Physical restoration requires new external/in-world measurements; merely
shutting a gate cannot prove that a contaminated cell is safe.

## Operator work and crew access

Physical gate state and *permission to operate or traverse* are distinct.
An intact known-to-known rated gate can be opened only with explicitly
modelled local authority and recent readings (maximum ten simulated
seconds, with limited pressure change) on both sides. The selected
reference open threshold is at most **2 kPa differential**; the supported
unsuited-air screening band is **80–120 kPa** total pressure,
**16–26 kPa** O2 partial pressure, and a limited contaminant fraction.
These are conservative trial policy settings, not current ship observations.
Known vacuum and unclassified cargo thresholds do not gain a shortcut
because an operator has PPE or a generic transfer approval. They require
their separately engineered airlock/transfer sequence.

A mechanical fault can force a hatch **jammed open** regardless of
permission. Commanding closure then fails and the leak or unwanted
atmosphere connection persists. `isolate_zone` closes all
available boundaries around the named pressure cell but reports each
failed closure separately. Delaying that command permits losses to
propagate into neighboring intact compartments. The simulator also
screens crew-access reachability through gates that are both physically
open and locally verified safe. Crew occupancy can be seeded up to the
40-person vessel design limit, with unsafe person-seconds recorded.
These are exposure indicators, **not** deaths or autonomous crew actions.
No traversal happens merely because a path is graph-reachable.

The physically separate 2.75 t refill bank outlets begin shut. A metered
replacement-air credit is permitted only after isolation/repair,
locally checked bank valve and route, and fresh receiving chemistry
evidence. Refill is bounded by available bank gas, the selected pressure
target and the existing 200 kg/h *combined* nominal reference
throughput. Delivery is ledger-averaged over declared elapsed time;
it does not pretend to resolve moving valves, thermal ramp, or actuator
transients. A runtime implementation must resolve live gas service
network routes and world-authoritative permissions separately.

## Acceptance matrix

Run `python design/ship/check_pressure_damage_sim.py`.
The test uses actual v0.5 registers, and contains these independent
adversarial comparisons:

| Physical case | Required observable consequence |
| --- | --- |
| Cold isolated HAB-03 shell breach | HAB-03 vents; intact bridge and HAB-04 retain their reference gas |
| HAB-03 → BR-03 → HAB-04 hatches opened | Mass and partial pressure propagate across real graph boundaries |
| Isolate after 3 s versus 50 s versus not at all | HAB-04 loss increases with delay; isolated passage no longer available |
| HAB-03 end gate mechanically jammed open | Isolation reports the failed gate, continued propagation; second gate can still close |
| Open segmented Trunk-A forward hatch | Adjacent 950 m trunk segment loses gas; independent closure arrests transfer |
| Flywheel F1 service hatch failed open | Known vacuum receives lost gas; source segment depressurises |
| Cargo sector hatch failed open | Unknown receiver is NOT treated as vacuum; affected pressure/crew permissions become uncertain |
| Dirty-air HAB-03 to bridge | Even at equal pressure, material tracer mixes through an open hatch and blocks unsuited access |
| Lower vs upper air-volume assumptions | Equal breach parameters produce different pressure histories |
| Puncture sealed, bank locally opened, route proved | Real bank stock decreases; compartment gas increases; refill rate/ceiling enforced |
| Eleven damaging input variations | Wrong topology, false installed measurements, invented crew/rates/authority are rejected |

The test is part of the standalone Ox ship-design GitHub workflow. The
other nine design validators retain their original duties. This is
separate from PR #101 and does not touch the published v0.4 wire renderer,
the Evennia room database, crew decision maker, inventories or UI.

## Still deliberately outside this increment

The reference calculation assumes isothermal compartments; it does not
solve thermal expansion, sonic nozzle details, flexible pressure-shell
deformation, measured pipe conductance, airlock cycle machinery,
automatic sensing faults, metered crew breathing, fire heat/smoke
chemistry, detailed pumping transients or real-time world event ordering.
Those are candidate runtime physics/operations refinements, **not**
reasons to reopen the selected fictional ship layout. World authority
must eventually consume the *physical IDs and intended failure
consequences* here rather than treat this script as a second source
of truth.
