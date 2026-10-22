# Pressure-volume reconciliation v0.5 — screened gross geometry

22 October 2026. Design-only proposal. No Evennia/runtime integration or v0.4 promotion.

> **Latest v0.5 increment — 22 October 2026:** 101 of 133 pressure cells
> have selected nominal gross dimensions; 32 remain unsized. All ten
> previously unprotected intercell doors now have rated boundary status,
> bringing the count to 208. Six freight locks have 12 m clear
> length around the unchanged 8 m full sled. HAB-04 medical isolation and
> two final-lift volumes are carved out of the respective existing arc
> shell gross, not added to it. Reference free air 54,021–62,390 m³
> (65.047–75.125 tonnes). See
> [pressure-access closure](PRESSURE_ACCESS_CLOSURE_v0.5.md).
> Earlier volume/count figures below are retained as design history.


### First 11-cell audit, retained for comparison


The Ox has 133 independently isolatable pressure cells. Of the prior 48 unsized cells, **11** now have collision-screened nominal gross reference envelopes: six 8 m cargo freight locks (6 x 169.28 m3), four intermediate A/B cross-corridor connections (4 x 52.5 m3), and the bow service volume (854.4 m3). New gross included geometry: **2,080.08 m3**. The engineering ledger now has **96 nominally sized / 37 unsized** cells, **67,629.329 m3 gross**, **53,541.043–61,851.223 m3 planning free gas**, or **64.470–74.476 t** dry-air equivalent at normal reference conditions. The older 85/48 estimates in the preceding docs refer to the previous revision, not these current figures.

The 37 other pressure cells have not been silently given gas volumes. The separate machine-readable `pressure_geometry_reconciliation_v0.5.json` includes all 48 prior exceptions, each source space and its intended disposition. Key as-authored geometry conflicts:
- Aft long-life stores handling gallery overlaps both subordinate food and fluid rooms, 162 m3 each; aft control overlaps two other component boxes (2.73 and 27.04 m3).
- Several command, rescue, EVA, rotary services, and cross-connectors intersect other isolatable rooms or personnel / freight trunk swept envelopes.
- Six drum service galleries lack constituent room geometry. The isolated medical room has floor area without headroom. Indexer capsules and final lifts lack sized swept envelopes.
- Rotating workshop pods require distinct physical placement. Two radially telescoping workshop passages have no fixed deployed length.

**Important:** freight locks have a nominal inner envelope 8 x 4.6 x 4.6 m, while the complete sled/load bounding box is 3.8 x 3.4 x 8 m. A nominal free-gas estimate can be derived, but 8 m versus 8 m does not demonstrate end-door clearance, capture margin or pressure seal-safe freight operation. The free-volume planning fraction is intentionally broad (0.30–0.97). Do not claim the loaded freight lock is proven physically operable until transfer-hatch geometry is reconciled.

All 133 cell `actual_usable_free_air_m3` entries remain null. The two 2.75 t make-up banks and separate 249.2 kg protected oxygen stock are unchanged; initial gas is not counted twice. These are geometric/design screening assumptions, not as-installed measurements, confirmed atmosphere composition, pressure, valve configuration or a repair receipt.

Next: resolve room/trunk collisions, freight lock/sled swept lengths and medical/indexer geometry, then implement waste/byproduct receiving, vent/disposal isolation and independent machinery degraded modes.


## Later mechanical pressure-closure decision

The 11 admitted box envelopes were preserved, but the six drum freight
chambers were lengthened from **8 m to 12 m** to provide **2 m nominal end
clearance each** around the unchanged 8 m sled. The reviewed equipment and
pressure-zone ledger also dimensioned five previously unsized cells:
HAB-04-MED-ISO, IX-A/B-CAPSULE and IX-A/B-FINAL-LIFT. The medical and
final-lift subcells are already contained within their host B′ pressure
shells and therefore **reduce** the host arc gas reference when partitioned,
not increase the outer-shell gross. The indexer capsules are separately
pressurised mobile cabins. There are now **101 sized / 32 held** pressure
cells, **68,186.014 m³ gross**, and **208 pressure-rated doors**. The
old 8 m chamber/doubled-store statements above describe the earlier state.
All 32 held cells retain explicit blockers. For dimensional and safety
rules see `PRESSURE_ACCESS_CLOSURE_v0.5.md`.
