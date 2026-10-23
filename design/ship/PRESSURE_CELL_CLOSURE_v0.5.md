**CURRENT 23 OCTOBER 2026 v0.5 CANDIDATE:** 133/133 sized nominal pressure cells, 339 rated isolation boundaries: 208 previously registered plus 131 fail-shut interfaces to cargo, machinery and shield compartments whose atmospheres remain unverified. Earlier figures below record design history. See [unknown-environment access closure](UNKNOWN_ENVIRONMENT_ACCESS_CLOSURE_v0.5.md).

# Ox of Hephaestus — pressure-cell separation and gross gas envelopes, v0.5

**HISTORICAL v0.5 CHECKPOINT (22 October 2026):** 421 rooms, 517 access links, 786 equipment units, 1,180 service nodes, 1,176 service links, 1,251 isolation points, 11 inventory accounts and 42 maintenance groups. 133 independently isolatable pressure cells include 101 dimensioned references, 32 unsized, and 208 pressure boundaries. Nominal counted gross air envelope 68,186.014 m³; design free-air screen 54,020.573–62,390.375 m³. Earlier numbers later in the document describe interim v0.5 increments only. [Pressure access](PRESSURE_ACCESS_CLOSURE_v0.5.md) and [byproduct/waste closure](BYPRODUCT_AND_WASTE_CLOSURE_v0.5.md) are the newer physical references; v0.4 canonical and Evennia are unchanged.


**Design-only physical-world correction.** The vessel's 421-space map,
517 authored physical connections and B′ pressure-arc geometry are retained.
There is no Evennia, AI, dashboard or real-time gas simulation change.

**Data:** `pressure_zone_topology_v0.5.json` contains all elementary
pressurised gas cells, their constituent room IDs, the final 339 independently rated
pressure/unknown-environment boundary links, and defensible **gross geometric**
volumes for all 133 selected nominal gas cells. A separate stdlib validator
`check_pressure_cells.py` verifies these declarations and six
failure-inducing mutations.

## 1. Why the existing gas partition was wrong

In the original v0.4 ship-world JSON the 950 m personnel trunk A had
23 physical space records but **one** pressure-zone ID,
`PZ-TRUNK-A`. Trunk B similarly shared `PZ-TRUNK-B` across
23 sections. Yet every one of the **22 connecting doors on each
trunk** was authored as an actual pressure boundary.

If the whole tube were truly one indivisible gas cell, closing
any of those 44 doors could not isolate atmosphere in the model.
That contradicts the ship's longstanding sectional pressure/fire
safety architecture.

The v0.5 candidate now gives every physical trunk section its
**own elemental pressure-zone ID**, derived from the durable room
identity: `TRUNK-A-DR-01` has `PZ-TRUNK-A-DR-01`,
`TRUNK-B-F2` has `PZ-TRUNK-B-F2`, etc.
Every existing door/room ID and physical transit route is unchanged.

**Doors normally open or automatically cycled can still share air
between neighbouring cells.** A pressure-zone ID indicates a
*physically independently isolatable volume*, not a promise that
its doors are always shut. This allows a leak to close the actual
pressure shutters, affects only truly connected volumes, and
lets nearby crew bypass via the second service trunk if routes
remain safely reachable.

There are 46 independent personnel-tube cells, 44 sectional
pressure-door links, and seven dedicated A/B cross-connections
with their own pressure zones and two additional cross-door
boundaries each.

## 2. Three additional isolation corrections

The following protective closures were already represented as
pressure-rated doors but shared the main arc's gas identity:

| Space | Separate gas volume |
| --- | --- |
| `HAB-04-MED-ISO` | `PZ-HAB-04-MED-ISO` |
| `IX-A-FINAL-LIFT` | `PZ-IX-A-FINAL-LIFT` |
| `IX-B-FINAL-LIFT` | `PZ-IX-B-FINAL-LIFT` |

Their boundaries can now isolate bad atmosphere and differential
pressure instead of simply closing a graphical doorway. Actual
lift/capsule hatch status, equalisation, pressure sensing and
mechanical capture remain world-operational systems to implement
after physical design closure.

The F1 and F2 flywheel service bays are explicitly classified as
**unpressurised machinery containment** (`pressure_zone=VACUUM`).
Their entry is through separately pressure-rated service airlocks,
requires rotor and residual-energy isolation, and can demand
suited local work. The ship's existing non-habitable vacuum
machinery philosophy supports this choice.

## 3. Refuges are entire arcs, not little equipment cupboards

`HAB-04-REFUGE` and `HAB-08-REFUGE` are each 40 m²
**equipment stores**, housing the independent battery, protected
oxygen and 72-hour 40-person CO2/air-support packages.

The **actual refugee occupancy volumes** are their host arc
pressure zones, `PZ-HAB-04` and `PZ-HAB-08`. Crew move into
the surviving accessible parts of those separate specialised
modules. We do not put 40 people inside 40 m² of machinery for
three days.

A life-support cupboard remains within its host arc's
atmosphere, so it need not have a separate pressure-hatch entrance.
Each refuge operates only while the hosting arc shell and its
independently closed end boundaries remain intact. Medical
isolation and indexer final-lift compartments may remain
isolated from the refuge zone when unsafe.

Emergency stock remains 106.8 kg O2 in each primary refuge and
4.45 kg in each of eight short-duration arc-local banks:
**249.2 kg total protected breathing oxygen**, not a hidden
extra inventory.

## 4. What the geometric volume calculation does and does not say

At normal reference conditions (101.325 kPa, 20°C, dry air),
ideal-air density is approximately **1.204 kg/m³**.
The **earliest v0.5 core-only geometry checkpoint** calculated these
**gross enclosing envelopes**, before the 48 specialist/transfer cells
were dimensioned. They are an historical subtotal, not today's full gas
inventory or actual free-gas measurements:

| Subsystem | Independently isolatable cells | Gross envelope |
| --- | ---: | ---: |
| Personnel trunk A (3 m clear × 950 m) | 23 | 6,715 m³ |
| Personnel trunk B (3 m clear × 950 m) | 23 | 6,715 m³ |
| Heavy logistics tube (5.5 m clear × 950 m) | 23 | 22,570 m³ |
| Eight B′ 38° habitation arcs with paired half-heads | 8 | 29,306 m³ |
| Eight 3 m-bore inter-arc bridge pressure volumes | 8 | 242 m³ |
| **Historical core subtotal only** | **85** | **65,549 m³** |

The **current** ledger has **133/133 dimensioned nominal pressure cells**
(48 later reconciled specialist compartments, cross-connectors, indexed lifts
and other individually rated subspaces beyond the 85 early core). Their
complete nominal gross reference is **100,772.940 m³**, fitted planning
free-gas interval **65,832.797–88,021.802 m³**, and reference dry-air
inventory **79.270–105.989 t**. These are geometry-based planning
bounds, not observed installed atmosphere measurements.

The gross envelope implies **about 78.9 tonnes of air** at
the reference state *if all these physical envelopes were
empty cylinders/heads completely pressurised*. It is not an
oxygen-cylinder reserve requirement or a reliable as-installed
free-gas total. Floors, machinery, partition frames, furniture
and sealed-off hollows reduce the breathable gas volume,
while pressurised fixed workplaces not in the sized set
increase the total.

The existing 5.5 t *arc refill-gas* figure is larger than
the **approximately 4.4 t full gross air mass per unoccupied
B′ arc**, so it is plausible as a **single-arc replenishment
allowance**, not enough to replenish the entire Ox. The subsequent physical-design increment now identifies two independent 2.75 t compressed breathing-air stores and an isolatable refill distribution network; see `PRESSURE_GAS_RECOVERY_v0.5.md`.

## 5. Conservative uncertainty and current physical state

The candidate retains **83 spaces with no asserted
pressure-zone classification**. Many are cargo sectors,
bearings, generators or machinery housings not assumed to
be occupied at normal pressure. They should be sorted by
their specific physical function before anyone claims
their gas inventory or refuge use. A null classification
must not become breathable by software default.

The ledger also recognises **26 known vacuum spaces**:
24 external work locations/routes plus F1 and F2 flywheel
machinery rooms. The current v0.5 candidate has **339 rated
pressure and environmental-threshold access links** (the earlier
208 plus 131 cargo/industrial/shield threshold guards). These
connections are not permission for unsuited access, regardless
of assumed nominal pressure on either side.

Neither the nominal atmosphere in the static JSON nor a
successful repair action is proof of present pressure.
Sensor readings, remote reports, local gauges and the
underlying physical gas mass remain separate authorities.

## 6. Consequences that now make sense

- **Trunk A ruptures near DR-02:** close its two neighbouring
  section pressure doors; unaffected A-sections and trunk B
  may remain usable, subject to cross-connection states.
- **Central trunk failure while a personnel cart is moving:**
  pressure shutters and the cart block controller become
  a real competing-interlock/recovery task, not automatic
  teleportation around the damaged segment.
- **HAB-04 medical isolation contamination:** the isolation
  room can be sealed without treating the entire HAB-04 refuge
  as the same indivisible gas chamber.
- **Indexer A transfer capsule leak:** close the fixed/rotor
  capture collars and final-lift boundaries; neither a
  completed docking instruction nor a graphical passage
  implies a sound seal.
- **Flywheel F1 servicing:** suited, lockout-controlled
  entry through the pressured airlock into a vacuum bay;
  no casually occupied machine room during full rotation.

Further as-installed work: observe fitted free air, pressure,
composition, live leakage and thermal states; the bounded design
now has stored routine inert gas and separate mixed-air casualty
banks, and retains explicit isolatable delivery and exhaust paths.
That is operating uncertainty, not unresolved nominal geometry,
and not a demand for real-world spacecraft certification.

## 7. Bounded free-volume and refill extension

The `pressure_gas_recovery_v0.5.json` screens **all 133 nominally dimensioned pressure cells**, each with an explicit void-fraction interval, including 45 individually overridden specialist/occupied cells and separately assessed transfer capsules, medical space, bores and bridges. The **current free-gas reference is 65,832.797–88,021.802 m³ (79.270–105.989 t)**; no as-installed net-volume measurement is claimed. The emergency **5.5 t** mixed-air stock remains two independent **2.75 t** banks supplying 69 taps and the eight-arc refill ring; routine **4.456–5.958 t** inert-gas loss over 730 days is budgeted instead from **two 3.5 t** metered inert stores feeding ECLSS A/B oxygen-controlled mixing, not the casualty banks. All **83** unknown-environment cargo/industrial/shield spaces remain nonbreathable by default. See [B′ Issue 1.3 reconciliation](BPRIME_ISSUE13_MISSION_RECONCILIATION.md).
