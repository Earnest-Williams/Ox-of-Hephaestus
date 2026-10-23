# Habitation pressure interfaces and mechanical recovery — v0.5 design continuation

**Status: adopted B′ functional architecture, proposed component details.**
This is a play-facing hardware/operations specification rather than a
construction drawing or finite-element signoff. The adopted arrangement
is **eight independent 38° pressure-rated habitation arcs**, at 45°
pitch, supporting **40 people** with three saddles per arc. B′ has a
keyed structural centre and independently sliding outer supports. Precise
member sizes are still engineering candidates; the 41° preliminary CAD is
not an alternative arrangement still awaiting selection.

## 1. Layout and pressure boundaries

The eight reference arcs form eight separate primary pressure zones,
PZ-HAB-01 to PZ-HAB-08. A bridge BR-nn is another *separately isolatable*
pressure zone. The relevant physical chain is:

    HAB-nn corridor -> arc-end vestibule
    -> pressure hatch A -> BR-nn -> pressure hatch B
    -> next arc's vestibule -> next arc corridor

Neither an open hatch nor a healthy service cable should make two
neighbouring arc pressure shells into one continuous pressure vessel. The
pressure-head openings are genuine rated closures, not decorative door
meshes. Bridge loss can be contained by both end closures. People then
must use the other direction around the arc ring, or an independently
safe spine transfer path; a sealed bridge is not traversable simply
because a route exists in the graph.

B′ uses **38° modules at 45° pitch**, leaving 7° between arc ends.
At 73.15 m centreline radius, the nominal separation chord is about
**8.93 m**. The earlier 41° curved-shell/frame trial would leave 4°
and about 5.10 m, so it is unsuitable as a direct installed-geometry
reference. **Remodel that trial's head, cradle and indexer interfaces
to the chosen B′ 38° layout.** The standalone v0.4 wireframe correctly
displays the currently selected schematic; it does not qualify the
manufactured pressure closures.

## 2. Pressure-end closure at every bridge interface

Sixteen pressure-head hatch assembly equipment IDs are present in the v0.5 design candidate:
HAB-nn-END-HATCH-CW and HAB-nn-END-HATCH-CCW.
Each belongs to the corresponding HAB-nn-VEST-CW/CCW compartment,
and refers to the existing access-link ID so the closure and passage
are not two unrelated inventions.

The recovered v0.5 STEP trial established a *local geometric precursor*:
9.5 m inner pressure section; trial 2:1 ellipsoidal end; a
1.40 m axial-width x 2.20 m radial-height rounded aperture with
R0.20 m corners; 16 proposed dog centres. At a hypothetical
150 kPa pressure differential, the approximately 3.04566 m²
rounded opening carries about **456.85 kN of pressure load**.
Division by 16 gives 28.55 kN per dog *only as a mean load*,
not a load rating or evidence that the dogs share force equally.

The trial assembly's hatch leaf sat **32 mm from its nearest metal
pressure seat**. Therefore its CAD was not a functioning seal.
The current-installation candidate must instead include all of:

- a real, continuous machined/repaired metal support seat following
  the rounded aperture, with backed-up load path to head/frame;
- two replaceable sealing elements with a monitored interseal
  space, pressure test port and replaceable contamination barrier;
- sixteen positive mechanical dogs with drive rings and wear/
  position indications; the dogs retain against differential
  pressure without energised motors;
- an actuator plus local mechanical hand drive with worm reduction,
  positive stop and a hardware pressure-difference inhibit;
- local differential-pressure gauges and accessible equalisation/
  vent lines that do **not** defeat independent volume isolation;
- drain/cleaning points, removable seal cartridges, inspection
  clearances and a physical proof that the leaf does not collide
  with other pressure or structural members.

The hatch's safe motion sequence is:

1. Obtain current local pressure on both sides, identify which
   volume is isolated, and verify no active fire/toxic atmosphere.
2. Equalise across a controlled, isolatable line. A damaged or
   unreliable gauge triggers a local test or blocks the operation.
3. Verify differential below the hatch's authorised opening limit;
   dogs may then withdraw under power or local manual drive.
4. Move the leaf clear, establish positive open indication, and
   transit only if the opposite bridge-end closure is consistent
   with compartment authority.
5. Close, prove all dogs/seat, isolate the equalisation line,
   and perform a pressure/leak validation if pressure integrity is
   being restored.

Loss of control power leaves a latched door latched. If it is
half-open, losing power may leave a blocked passage and require
local mechanical recovery. The hand drive **does not** override
pressure-difference protection. A single failed dog, torn gasket or
misreported position can create a maintenance incident without
necessarily bursting the vessel. The world owns each actual
condition and action result; sensor indications can be stale or
wrong.

## 3. Bridge wet-service and electrical sleeves

Every bridge is also an infrastructure crossing. The v0.5 candidate
introduces BR-nn-UTILITY-SLEEVE equipment at BR-01 through BR-08,
with physically distinct ways for power A/B, atmosphere,
potable water, greywater, blackwater and low-temperature cooling
to cross. Service edges are retained individually; a composite
sleeve is not a magical master valve that cuts them all.

Routing is anchored to each arc's actual SERVICE-GALLERY,
then BR-nn, then its neighbour's SERVICE-GALLERY. Each line
has end-isolation points in its own service graph. A dry sleeve
may be opened for electrical work without opening wet service;
a compromised wet-service seal need not release a pressure door
when its local branch is isolated. An interspace alarm is
evidence of a possible leak, not proof of which of seven services
failed.

BR-06 is a repaired, locally manually isolatable wet-service
sleeve with remote indications only. Retain that historical
workaround rather than redesigning every bridge to match it.

## 4. Cradles and the rotating habitation framework

The recovered v0.5 trial framework comprised 536 nodes and 896
beam elements; trial steel-like frame mass was about 4,405 t,
with eight 400 t arc gross masses, giving about 7,605 t combined.
In the current 10,500 t habitation dry planning allowance that
*trial combination* would leave approximately 2,895 t for other
habitation structure, bearings, indexers, machinery and services.
That is a useful accounting screen, **not** a verified 38° frame
mass or a fully itemised construction budget.

The recovered calculation caught two real limitations. Every one
of 24 cradles terminated on a single modeled beam-level load path,
and a local beam bounding section encroached as much as
0.325 m into the conservatively modelled pressure shell.
The frame otherwise had at least 0.534 m nearest noncontact
pressure-shell clearance, while nominal indexer/member clearance
was about 1.66 m for those members actually modelled.
The hatch seat gap and unmodelled carrier hardware remain
separate problems.

**B′ selected load paths** supersede the old single-beam cradle
precursor. The eight arcs each have three principal conformal saddles
(24 total), connected to external nonpenetrating reinforcement at the
pressure shell. Each of the **eight keyed central saddles** attaches
through a real diaphragm-supported centre joint, establishing the
circumferential and reference longitudinal datum. Each of the
**sixteen outer saddles slides** to admit normal thermal growth
rather than clamping the 38° shell. Every outer station uses
**three spatially independent branches**, totalling **48 outer
frame branches**, so a single member or node does not masquerade
as the whole support.

The developed B′ centre-joint screening geometry uses a 2.4 ×
1.6 × 1.5 m diaphragm-reinforced box (50 mm principal plates,
40 mm diaphragms), 300 × 35 mm capture retainers and 180 mm
pins as candidate parts. Those are believable current-installation
component sizes, not manufacturing qualifications. **Retainers
must not seize or bottom out during normal thermal motion**;
they provide exceptional-displacement capture and post-failure
recovery. Keep all frame junctions outside intact pressure
membranes with accessible inspection and replacement zones.

The remaining path after a saddle/member defect need only
support *safe spin-down, pressure containment and recovery*
at candidate loads; it is not automatically licensed for full
3.45 rpm operation. Suspected bearing displacement, cradle
movement, large vibration, unbalanced stowage or frame damage
can require slowing/parking the hab rotor, informing command,
preserving atmosphere and using alternate access routes.

The earlier 41° framework still requires full **B′ 38°** mechanical lattice re-topology; its 48 physically distinct outer branch datums and keyed/sliding stations are now specified in `hab_bprime_mechanical_interfaces_v0.5.json`. The chosen support topology and load-path rules are not
contingent on that re-authoring; detailed member footprints,
seal contact and indexer clearance are still to be reconciled.
The B′ loss-of-outer-station screen suggested ~179 mm
movement as a particular failed-state displacement; that is
not the allowed normal service travel.

## 5. The two independent spine–habitation indexers

IX-A and IX-B remain separate transfer stations near x = 445
and x = 465 m in the reference frame, each with its own capsule,
drive, locks and local protected power. Their pressure state
and capture condition are not the same as their navigation
graph connectivity.

Operating states to represent individually:

| State | Physical description |
| --- | --- |
| FIXED_DOCKED | Capsule captured on fixed side, fixed hatch permitted only after pressure equalisation |
| CLOSED_TRANSIT | Both closures shut, capsule moving/matching orbital phase |
| ROTOR_DOCKED | Capsule captured on rotating side, rotating hatch permitted only after equalisation |
| INTERLOCKED | Drive/brake or pressure condition unknown/unsafe, neither hatch released |
| RECOVERY | Local crew or maintenance team restoring drive, seal or mechanical alignment |

Required observations: capsule location/phase, both pressure
indications, hard capture, seal integrity, hatch/dog proof,
motor/brake state, and protected-power condition. Local readouts
need not agree with bridge telemetry when a gateway is sick.

Normal indexing carries people and small tools while habitation
continues rotating. It is not a freight portal. No external
Concordia handler or route finder may claim an instantaneous
transfer by sending a generic movement command. State change
takes world time and can be interrupted. Both capsules have
limited atmosphere and independent recovery preparations,
not an unbounded reserve.

The independently rotating WR-01 machine/stores rotor has its
**own** personnel indexer and separate heavy freight
staging/hard-lock system. Stopping WR-01 for a 50–100 t
equipment move must not stop the residential habitation rotor.

## 6. Failure/recovery cases the ship must support

- **BR-06 wet-service leak:** isolate the affected medium from
  adjacent service galleries. Bridge remains a pressure zone;
  other media and the surrounding walkway are evaluated
  separately. Local manual isolation may require a worker.
- **HAB-03 hatch seat leak:** pressure contamination/small loss
  creates real indications; close both bridge ends, compare
  interspace and arc/bridge pressures, restore fitted seal,
  then perform pressure test before reopening.
- **Indexer A captures but cannot unlatch:** passengers remain
  in a real bounded capsule. Indexer B or opposite-direction
  ring route may recover crew if usable. There is no teleport
  or automatic second-door opening.
- **Single cradle joint damage:** reduce rotor to safe state
  as far as remaining load path allows, inspect locally,
  and restore or park. Continuing full-speed rotation is
  not the implied default.
- **Emergency hab isolation:** ten local occupants have the
  relevant 12-hour scrubber/O2 package, *provided pressure
  integrity and heat/power are intact*. Move to refuge or
  restore utility distribution before the time limit.
- **Full bridge loss:** it breaks one edge of an eight-arc
  ring, not the whole ring. Two sufficiently separated
  bridge failures can create isolated groups and alter
  reachable crew/refuge paths.

## 7. What remains provisional

The operational contract above selects credible hardware types,
crew procedures and failure states. The complete 3D carrier
rings, the pressure seat's precise section/contact, the dog
mechanism, curved head support interactions, shell/stiffener
materials and the precise B′ 38° dimensional adaptation of
earlier CAD remain future physical-model design tasks.

The recovery report's 3°/6° beam screens and valid STEP
imports are useful technical evidence; they do not alone
qualify a passenger hatch. This simulation is not required to
wait for real spacecraft certification, but it **is** required
to have internally coherent serviceable equipment and
physically meaningful failure consequences.

## 8. Explicit machine-readable installed interface follow-on

The B′ mechanical continuation is now in [BPRIME_HAB38_MECHANICAL_CLOSURE.md](BPRIME_HAB38_MECHANICAL_CLOSURE.md), with the corresponding proposed equipment identities in `ox_full_ship_v0.5_candidate.json`. The installed proposal comprises 8 centre keyed assemblies, 16 outer sliding assemblies, 48 individual outer structural branch references, 8 pressure bridge spools, 6 main rotor bearing/drive/brake assemblies and 2 independent 30-tonne reference indexers with 4 distinct capture collars. For the selected 38° geometry the head-port datums lie roughly 4.282 m apart, and the removable pressure bridge spans roughly 3.582 m after nominal collar reservations. This is not a rerun structural qualification of the superseded 41° trial.
