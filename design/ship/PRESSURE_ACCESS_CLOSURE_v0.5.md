# Ox of Hephaestus — pressure-access and compartment-volume closure v0.5

**22 October 2026 · Physical candidate only · The selected B′ 38° HAB architecture is unchanged.**
Data: `ox_full_ship_v0.5_candidate.json`, `pressure_zone_topology_v0.5.json`,
`pressure_gas_recovery_v0.5.json`, and `pressure_geometry_reconciliation_v0.5.json`.
Checks: `check_v05_candidate.py`, `check_pressure_cells.py`, `check_pressure_gas.py`, `check_pressure_geometry.py`.

## 1. Physical changes

The Ox remains a **950 m**, **421-space**, **517-link** working freighter. It has 133
isolatable pressurised cells and 26 separately identified vacuum spaces.
The previously accepted 3.8 × 3.4 × 8 m *complete* guided freight-sled envelope
is not reduced merely to make a lock fit.

**All six DR-nn freight locks now have a nominal 12 × 4.6 × 4.6 m clear internal envelope.**
Each is centred on its original axial handling station, within the drum's
existing approximately 75 m span. A restrained 8 m-long complete sled has
**2 m nominal axial clearance at each end** before considering the as-fitted
hatch dogs, head curvature, load stops and seal sweeps. Nominal empty gross
volume per chamber is 253.920 m³ (formerly 169.280 m³). The full sled/load
bounding box occupies up to 103.36 m³, leaving 150.56 m³ empty by a gross
rectangular subtraction *before* other hardware and cargo-contingent cavities.
Planning free-volume fraction is bounded 0.50–0.97. This is a credible
operational allocation, **not** a fully modelled door-sweep or machining drawing.

The indexed **IX-A and IX-B passenger capsules** are independent four-seat
pressurised cylinders: **4.6 m long, 2.6 m clear internal bore**, 24.423 m³
gross each. The 4.6 m axial length fits inside the existing 7.8 m-wide
carrier sweep; with the cabin centred at orbital radius 10.5 m its
nominal interior radial span of 9.20–11.80 m fits inside the reserved
8.55–12.531 m mechanism radial envelope. Each 30 t carrier/ring reference
remains a *machinery mass*, not a cabin-gas mass; the available exterior
0.65–0.73 m guard is for structural insulation, pressure hardware and moving
interfaces, not additional room gas. Each capsule may be independently
isolated when both rotary connection collars retract.

The **HAB-04 medical isolation cabin** uses the already authored 25 m²
net floor area, arranged as a reference 5 × 5 m plan with 2.7 m clear
vertical envelope: **67.5 m³ gross internal cabin**. The two **final
habitation lifts**, one per independently accessed refuge arc, are
four-seat rated cylindrical pressure cars 3 m long by 2.6 m clear
internal bore: **15.928 m³ each**. Final lifts are separate cells
behind their own rated entry and arc exit hatches; their associated
radial passages and vestibules remain in their respective arc volumes.

## 2. Nested gas volumes are never counted twice

The gross B′ shell-envelope reference for each arc was
**3,663.303551 m³**. The isolation and final-lift cabins are **inside**
the existing HAB pressure vessels, not new hulls outside them.

| Pressure cell | New nominal gross volume (m³) | Original parent pressure shell |
| --- | ---: | --- |
| HAB-04 host, excluding two daughters | 3,579.876 | Originally 3,663.304 |
| HAB-04 medical isolation | 67.500 | Included within HAB-04 complete shell |
| IX-A final lift | 15.928 | Included within HAB-04 complete shell |
| HAB-08 host, excluding final lift | 3,647.376 | Originally 3,663.304 |
| IX-B final lift | 15.928 | Included within HAB-08 complete shell |
| IX-A indexed passenger capsule | 24.423 | Separate from both fixed-spine and HAB shell |
| IX-B indexed passenger capsule | 24.423 | Separate from both fixed-spine and HAB shell |

The unrounded machine-readable figures, not this human-readable three-decimal
table, drive accounting. The original full HAB-04 and HAB-08
shell volume is conserved in the sum of each parent and daughters.
The independent indexed capsules lie outside both shell volumes, so they
are the only gas-volume additions among these five new pressure cells.
The six lengthened freight locks account for the other volume increase.

The working ledger now covers **101 geometrically dimensioned pressure
cells and 32 still unresolved**, totalling **68,186.014 m³ nominal gross**.
Void/displacement ranges yield **54,020.573–62,390.375 m³ estimated free air**
(about **65.047–75.125 t** nominal dry air at reference pressure and
temperature). No cell has a certified as-installed free-gas measurement.
The existing two 2.75 t makeup-air banks and 249.2 kg refuge/local protected
oxygen are unaffected and are not double-counted as initial atmosphere.

## 3. Ten previously unsafe pressure-door definitions corrected

Every connection between two **known different environmental cells**
must have a capable pressure closure. The prior source retained ten
connections whose door records were not marked as rated although the
two sides were independently isolatable:

- `ACC-IX-A-FINAL` and `ACC-IX-B-FINAL`, between each HAB rotary
  access path and its isolated final lift. Both now **normally closed**.
- Five `ACC-LOGI-AFT-*` store/magazine freight doors, between the
  aft logistics stopping cell and the protected stores pressure volume.
- `ACC-WR-FREIGHT-STAGING`, between the central heavy-freight transit
  cell and the fixed WR staging plant.
- `ACC-LOGI-F1-BAY` and `ACC-LOGI-F2-BAY`, between the normally
  pressurised logistics section and flywheel machinery vacuum.

Those ten *existing* doors are now explicitly pressure-rated; no room or
travel edge is duplicated. The pressure-boundary register now contains
**208** entries, matching all rated authored access links.

The F1/F2 freight closures must **not** simply be opened as ordinary
double doors. For heavy flywheel maintenance the local logistics stop
is isolated by its sectional shutters, with ordinary pressure protected
elsewhere; the isolated segment is depressurised or its gas recovered
under permit before the vacuum-side cargo shutter opens. Flywheels are
stopped and stored energy locked out; personnel enter suited or via their
separate service airlocks. The new link restrictions include all those
interlocks. Thus a vacuum-bay maintenance event can consume time, recover
gas and block through-freight traffic **without venting the entire spine**.

The final lifts similarly require positive car capture, measured
equalisation and the opposite hatch closed. A reported button press or
a travel-graph connection does not prove safe transfer. Aft stores and
WR-01 freight staging require restrained load, verified gas
conditions and their particular stop/index/hard-lock states.

## 4. Structural and simulation boundaries

- Freight chamber **12 m clear length** is an operational nominal envelope.
  Door leaf sweep, cylinder loads, seals, tie-down and cargo handling
  can be detailed from this allocation without changing the sled again.
- Medical isolation geometry is a *chosen reference cabin footprint*
  inside the 38° arc. Its exact curved-shell local placement and
  associated duct penetration details remain to be surveyed.
- The indexer capsule and final-lift **pressure volumes** are dimensioned.
  This does **not** claim a solid, contact-qualified 30 t carrier ring,
  shaft, collar or actuator model. Preserve the B′ mechanical reference
  and its existing swept-envelope interlocks.
- A volume calculation is not a safe unsuited-access decision, a live
  mass measurement, a proof of gas purity or a successful leak check.
  Environmental state remains world-authoritative.
- The **32 pressure cells still held** include physically contradictory
  room/trunk overlaps, multiroom store galleries, six unsized drum service
  galleries and deployable workshop-rotor passages. The machine-readable
  audit preserves each unresolved case, rather than adding phantom gas.

## 5. Further physical work

Resolve the overlapping fixed-room and 3 m / 5.5 m trunk envelopes
without shrinking already accepted tube clearances; reconcile compartment
walls, floor placement and local pressure-shutter footprints. Then finish
individual waste/byproduct receivers, pumps, vent recovery and
anti-backflow routing for 40 occupants over a 730-day leg, including
degraded and manually recoverable operating states.

**Authority:** `ox_full_ship_v0.5_candidate.json` remains a design-only
working model. `ox_full_ship.json` (v0.4) and the legacy standalone
wire render are not promoted; PR #101 and Evennia/AI/UI source remain
untouched.
