# Unknown-environment pressure isolation — Ox v0.5

**23 October 2026 · Selected physical candidate, not as-installed qualification or Evennia migration.**

## Fault discovered after 133-cell volume closure

The ship already contains 133 nominally bounded pressure cells and 83 cargo,
machinery and shield spaces whose atmosphere is unclassified. The source
correctly refuses to call those 83 spaces breathable. Nevertheless, **131
existing access connections** ran directly from known pressurised rooms into
these spaces while marked `pressure_boundary: false`. A suit, access-graph
connection or generic service hatch does not contain the pressure of the
adjacent gallery when a receiving cargo sector is vacuum or hazardous.

The earlier validators tested isolation between two *known* pressure zones
but exempted links involving a null zone. That was a real containment gap,
not a missing nominal-volume measurement.

## Selected physical correction

Every affected existing hatch/shutter now has independent pressure-rated,
normally closed, isolatable boundary status. None of the 421 spaces or 517
access IDs was added or renamed. The original 208 rated interfaces remain
unchanged; **131 additional existing thresholds** bring the ship to **339
registered rated interfaces**, while the known cell count stays **133**.

| Unknown receiving space / access mechanism | Number | Isolation decision |
| --- | ---: | --- |
| Cargo sector from personnel gallery | 48 | Independently rated service hatch |
| Same cargo sector from heavy-freight handling berth | 48 | Separate pressure-rated cargo shutter |
| Commercial exterior cargo portal (inner end) | 12 | Rated inner seal, capture required |
| High-energy plant and bearing enclosures | 20 | Rated plant service hatch |
| Unknown shield or fluid-tank bays | 2 | Rated service inspection hatch |
| Propulsion workshop from logistics stopping station | 1 | Rated heavy-engineering freight closure |
| **Total newly protected** | **131** | **No new gas cells** |

The two gates into each of the 48 sector cargo holds are individually
registered. A stopped drum's heavy-freight path cannot bypass the safer
personnel hatch, or vice versa, and a sector breach need not depressurise
a 2,691 m³ service ring when both physical gates hold.

All 131 entries in `environmental_access_boundaries_v0.5.json` retain
their original opening identity and kind (including the historically
named `freight_handling_route`, now a rated actual shutter at that
threshold). Each names its known pressure cell, unknown environmental
receiver, existing maintenance-work group and separate operating interlock.
No additional 131 equipment objects, doors in the traversable room graph,
or atmospheric mass are manufactured by this correction.

## Physical operating restrictions

The selected design class is nominally **150 kPa differential** for each
shut gateway. That is a credible bulkhead selection, not a verified
as-installed pressure rating. **Opening** a gateway requires separate
local readings confirming the pressure difference is **at most 2 kPa**,
plus a compatible receiver-gas sample or separately contained transfer,
correct cargo/machinery permits, and a positive mechanical seat/lock witness.

An EVA suit does not permit opening a cargo sector at vacuum into a
breathable personnel gallery. Pressure equalisation is not permission
to expose the ring to toxic/flammable cargo atmospheres. Crews instead
use a properly isolated local transfer volume, controlled pressure
cycling and approved exterior access; an inaccessible sector remains
closed until that work can be done.

Industrial machinery doors demand a local energy/rotation lockout as
well as pressure/chemistry evidence. Commercial exterior cargo portals
must be positively captured and structurally locked. For a cargo sector,
both the service and freight shutters are independent: the other opening
must be proven shut during an individual transfer. A failed sensor,
bad cargo manifest, missing hand gauge, false 'dock captured' status,
damaged local seal or unavailable containment route each stops release.

## Mechanical evidence and regression

The register `pressure_zone_topology_v0.5.json` now contains 339
individual rated boundary records, including all new interfaces whose
receiving zone remains `null`. No unknown space is assigned an
invented volume or a safe atmosphere.

`check_environmental_boundaries.py` cross-checks the world links,
receiver safety-role policy, maintenance assignments and both cargo-sector
portals. It screens hypothetical safe and unsafe local-release cases,
including vacuum receiving sectors, stale gas sampling, incompatible
cargo media, a second sector hatch open, and broken positive capture.
Thirteen deliberate model mutations must fail. Both broader existing
pressure validators and the v0.5 candidate-vs-v0.4 check also reject
these missing ratings.

These are nominal selected installed-hardware interfaces. Current
physical state, gauge fidelity, patchwork retrofits, valid EVA supplies
and access safety still belong to the later world runtime. No Evennia,
handler, UI, published v0.4 JSON or standalone wire render was touched.
