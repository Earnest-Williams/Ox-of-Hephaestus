# Ox of Hephaestus — B′ habitation mechanical interface closure, v0.5

**Design selection:** B′ / B-prime, eight independent **38°** pressure-rated arcs,
45° pitch, 40-person ship capacity. The original 41° recovered beam/CAD
work is superseded as **installed geometry** but remains useful as a
mechanical trial. This is a plausible *working ship* and simulation
engineering specification, **not** a buildable or certified spacecraft.

**Machine-readable reference:** `hab_bprime_mechanical_interfaces_v0.5.json`
with eight arc geometries, 24 saddles, 48 individual **outer** members,
eight bridge pressure assemblies and two independent 30 t reference indexers.
It is referenced by `ox_full_ship_v0.5_candidate.json`.
B′ authority lives in the existing `habitation_support_contract`; this
increment gives that already selected architecture identifiable installed
machinery and consistent coordinate datums.

## 1. 38° pressure ends and bridge geometry

The circular pressure-section centreline is at radius **73.15 m**.
Arcs subtend **38°**, centred every **45°**. An end is therefore
at `theta = centre ± 19°`. Adjacent ends differ by **7°**.

The nominal pressure-section inner diameter is 9.5 m. The proposed 2:1
ellipsoidal head has tangent depth **2.375 m** and a separate total
installation envelope around **2.75 m** after frames, seat and hardware.
A 1.4 m axial-width × 2.2 m radial-height rounded personnel opening,
with R0.20 m corners, is centred 0.75 m radial-outboard of the head's
reference centre.

Using the 2.375 m theoretical head-depth **port datum**, and the
0.75 m outboard offset, adjacent pressure-head port datums are separated
by approximately **4.281834 m** along their joining centreline. The
two end axes disagree by 7°, or **3.5°** relative to the bridge's
symmetry plane. This datum is not a claim about final gasket/compression
surface placement on the curved head.

The connecting pressure assembly is a physically separate pressure
volume. Its proposed **3.0 m clear bore** encloses the personnel
hatch opening. Two end-collar/deflection interfaces each reserve
approximately 0.35 m nominal axial projection, leaving a central
replaceable spool of approximately **3.581834 m**. All eight bridge
assemblies have individual equipment IDs `BR-nn-SPOOL`, retain
separate `PZ-BR-nn` pressure zones, and host an independently
isolateable seven-medium `BR-nn-UTILITY-SLEEVE`.

The adopted B′ bridge travel doctrine is preserved:

- **125 mm normal relative service travel** supported by deliberately
  compliant, sealed bridge joint details;
- **450 mm exceptional failed-state translation envelope**, **not**
  normal permitted bellows travel; passage can become obstructed and
  both independent head hatches must be closed/isolated;
- there is **no radial structural load transfer** through the
  flexible bridge that substitutes for the three module saddles.

At the superseded 41° geometry the same reference head-port datums
would be only about **0.411 m apart**. That is incompatible with the
selected independent, maintainable bridge spool and is a further
reason not to import the 41° trial unchanged.

An approximate full-bore cylindrical pressure envelope per bridge is
30.27 m³. Eight bridges contribute about 242.2 m³ **gross geometric**
volume. These are not certified volumes or free-gas inventories.

## 2. Arc pressure closures: real load, real seat, real recovery

Each arc has **two** independent end-pressure hatch assemblies with
equipment identities `HAB-nn-END-HATCH-CW` and `-CCW`.
The fitted current-installation hatch has:

- structurally supported continuous metal seat, two replaceable seals,
  a monitored seal interspace and accessible leak-test fittings;
- sixteen positive mechanical dogs around the curved opening,
  with load distribution not assumed perfectly uniform;
- an inward-opening leaf which **withdraws 120 mm into its arc**
  before **swinging 90° inward**;
- local equalisation gauges/lines and hardware inhibits that prevent
  unsafe differential-pressure unlatching;
- hand recovery that can actuate the mechanism but cannot override
  pressure integrity.

The recovered local trial pressure load was approximately 456.85 kN
over a 3.04566 m² rounded aperture at an illustrative 150 kPa
differential (28.55 kN per dog **mean**, not selected dog rating).
The old STEP assembly's 32 mm open seating gap is **not** the
installed condition: current-world assemblies have a fitted
load-bearing seat and seal compression.

Crew actions can fail independently: sensor bad, equalisation valve
seized, dog half-withdrawn, seal torn, leaf not swung clear, or
pressure bridge accidentally re-pressurised. The world must represent
these separate states. An ordinary access link is never enough to
authorise an otherwise unsafe opening.

## 3. B′ three-saddle, keyed/sliding structural authority

**Do not replace B′ with two identical braces at every saddle.**
Its support topology is intentionally asymmetric.

Per arc: one **keyed central saddle** at centre angle and two
**thermally sliding outer saddles** nominally at centre ±12°.
There are **eight keyed centres and sixteen sliding outers** total.

- The *keyed centre* has a diaphragm-reinforced load-spreading box
  and a positive circumferential/longitudinal reference. The B′
  trial component screen uses a 2.4×1.6×1.5 m box with 50 mm principal
  plates, 40 mm diaphragm plates, 300×35 mm retainer sections and
  180 mm pins. These are proposed in-world hardware dimensions,
  not proven fabrication details.
- Each *outer saddle* slides to accommodate normal structural and
  thermal motion, with exceptional positive capture at the retainer.
  A maintenance-induced seizure may increase pressure-shell load
  even when no part has visibly broken.
- Every outer station has **three spatially non-coincident outer
  frame branches**, with separate root/junction IDs. Sixteen
  stations × three paths = **48** outer branches. The centre
  saddle does not turn into an ordinary sliding outer and does not
  receive these three branch IDs.

For a conservative cross-section screen only, the 48 branch endpoints
begin at radius **78.65 m**, outside the pressure-shell radial guard
at **77.92 m**. A 0.40×0.40 m candidate outer box section has
a circumscribed half-diagonal of 0.28284 m, leaving a minimum
radial lower-bound clearance of approximately **0.447 m** from
the conservative occupied shell annulus before considering
fittings and deflection. Pad contact with the pressure membrane
is a separate, conformal intentional interface; none of the box
struts is allowed to end by penetrating intact pressure plating.

The independent ring joints require re-topology of the old
41° 536-node/896-beam lattice before a new full-frame linear or
nonlinear structural analysis can be described as a 38° result.
The machine-readable reference provides the actual distinct strut
endpoints and stable individual IDs, **not** a fraudulent new FEA pass.

At 3.45 rpm a 400 t trial arc at r73.15 m has approximately
**3.819 MN centrifugal radial load**. This is an engineering
screen, not real reaction distribution between keyed/sliding
supports. B′ retains a roughly **179 mm exceptional outer-station
loss displacement** from its previous trade-screen evidence.
One lost support does **not** license continued full-speed
rotation. The accepted failure doctrine is guarded spin-down,
pressure containment, positive parking and local inspection.

## 4. Main rotor and independent 30 t indexers

The ship's habitation structural support and rotation uses:

- main bearing planes near **x439 m** (axially locating fore)
  and **x471 m** (radial support with aft thermal axial freedom);
- corresponding coordinated drives and controlled parking brakes,
  now six separate equipment IDs with owner-local controls;
- **IX-A at x445 m** and **IX-B at x465 m**, independent
  separately driven phase-matching capsule carriers.

Each indexer uses B′'s **30 t reference carrier mass**, not
the superseded 12 t early engineering fixture. At a 10.5 m
orbital radius and 3.45 rpm, 30 t alone creates approximately
41.1 kN radial load. An idealised 12-second change from rest to
nominal rotor rate on that 30 t point-mass fixture would need
about **99.6 kN·m** peak angular torque, *excluding* the
carrier rings, counterbalance masses, docking collars and
mechanical friction. That is not a selected actuator rating.

The moving capsule/indexer assembly retains the earlier
bounded axial envelope of station ±3.9 m and radial moving
envelope r8.55–12.5314 m. Its nominal guard to the stationary
spine at r8 is 0.55 m, and to the retracted r13.05 rotating
shaft is approximately 0.519 m. The primary-bearing axial
clearance is at least 1.3 m in the trial coordinates. Those
guards are reference geometry; actual docking hardware,
fail-stuck collars, thermal drift and dynamic deflection
must not be treated as already cleared.

Each carrier has a fixed-side and rotor-side mechanically
capturing **retractable pressure collar**. The possible
states include fixed captured, sealed transit, rotor
captured, interlocked and local recovery. A cap cannot
be simultaneously docked at both ends; drive motion is
inhibited while a collar is extended. Pressure equalisation
and positive capture are independent prerequisites for
opening either access hatch.

The independently rotating WR-01 engineering workshop
and its personnel/heavy freight interfaces remain
separate. Stopping the shop rotor does not stop habitation.

## 5. Approximate habitation structural mass allowance

The accepted whole-ship dry-mass accounting contains **10,500 t**
allocated to habitation. Earlier 41° beam trial mass was
**4,404.9 t**, and the 8×400 t reference arcs contributed
**3,200 t**. Their difference, **2,895.1 t**, is the existing
habitation allowance for uncounted supports, machinery,
indexers, services and fit-out; it is not free cargo mass.

The present v0.5 candidate carries a **planning** distribution
inside that 2,895.1 t: 80 t keyed boxes, 96 t sliding pads,
50 t ring/adaptation work, 400 t primary bearings,
90 t drives, 50 t brakes, 180 t two complete indexer
assemblies, 20 t four collars, 64 t eight bridge spools,
leaving approximately **1,865.1 t** for remaining habitation
utilities, installation, services and fit-out.

These figures are explicit planning reservations, not new
scale readings or double-counted extra mass. The old trial
frame mass already contains its former cradle struts; the
new 48-member strut screen must be accounted for by a later
frame replacement delta, not added wholesale to the same
structural category. Pressure head/hatch mass sits inside the
arc gross reference, not a second counted batch.

## 6. Failure paths and crew consequences

| Physical fault | Consequence and believable crew response |
| --- | --- |
| BR-06 wet-service sleeve leak | Isolate the failed service branch locally without treating every fluid/cable line or the bridge air volume as a single valve |
| BR-03 bellows overtravel | Inhibit passage, close both end hatches if safe; a 450 mm excursion is a casualty not guaranteed remaining open |
| HAB-07 outer slide seizes | Thermal strain rises, watch vibration and load; derate, park, obtain exterior work access and free/replace slide |
| HAB-02 outer branch fractures | Other two physical branches remain inspectable; controlled spin-down rather than unrestricted full RPM |
| HAB-04 keyed centre reference drifts | Rotary phase and structural datum fault; forbid ordinary indexing and rotation until verified |
| IX-A rotating collar jams while extended | Passenger capsule can be trapped and ring drive interlocked; IX-B is an alternate only where actually reachable |
| One bridge isolated | Eight-arc ring remains traversable the long way if the other seven bridge passages remain available |
| BR-01 and BR-03 both inaccessible | HAB-02/HAB-03 form a component without either HAB-04 or HAB-08 refuge; alternate safe spine transfer requires explicit availability |

## 7. Continuing physical design, not interface work

The mechanical interface and world identity are now specific enough
for simulation-level acceptance. Future work should complete the
per-pressure-zone **net free-gas volume** and gas refill stock,
arc/bridge service penetration details, actual bearing/capture
and pressure-system state machines, the cargo freight-lock clearance
envelope, and full shipwide fault isolation/repair-routing cases.

There is **no requirement** to qualify real-world fabrication
tolerances or full finite-element/contact certification before
accepting the playable configuration. The only blockers should
be contradictions that make movement, pressure containment,
fault response or engineering access impossible.
