# Ox of Hephaestus — live ship engineering index

**Status: G19 accepted and merged, 30 October 2026.** This directory contains the fitted ship design **and** the operational contracts of its installed Evennia simulation. It is not merely a proposed physical model. [G19 integration PR](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138) · [post-merge physics fix](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/139).

> **Engineering standard:** causal, finite and playable operation of an old working freighter; not fabrication or aerospace certification. [Design philosophy](SHIP_ENGINEERING_DESIGN_STANDARD.md).

## Live ship and source identities

| Component | Current verified basis |
| --- | --- |
| Topology | Published `ox_full_ship.json` v0.4, installed as **421 rooms, 517 physical passages and 1,034 directional exits** |
| Installed operational register | Topology-compatible `ox_full_ship_v0.5_candidate.json`, supplying **808 equipment units in 91 families** |
| Atmosphere | **133 finite pressure cells**, not fictitious breathable space in every room |
| Equipment-family disposition | **349 direct physics / 159 interface or material custody / 300 condition/interlock**, zero unclassified |
| Shared physics | One persistent, replay-safe Evennia-owned clock for power, air, thermal, fire, water, waste, hull, cargo, machinery, propulsion and exposure |
| Crew operations | Real gated exits, instruments, suited access, work permits, carried spares, timed repairs and observed restarts |
| Autonomous AI | Still attached to the **separate seven-compartment proving ground**; full-ship AI duties are future integration |

The **v0.4 topology source has not been replaced** by a promoted v0.5 geometry file. G19 installs the v0.5 engineering register over the matching canonical topology, and once installed, actual physical state belongs to Evennia. The v0.4 [wire renderer](Ox_Ship_Wire_Render_v0.4.html) and [live terminal](LIVE_TERMINAL.md) are read-only references, not world authorities.

## Authoritative G19 records

- [Final acceptance audit](G19_ACCEPTANCE_RECORD_2026-10-29.md) — twelve integrated subsystem groups, final gates and accepted non-blocking exclusions.
- [Post-merge fuzzing report](G19_FUZZ_CAMPAIGN_2026-10-30.md) — corrected heat accounting and remaining persisted-state hardening.
- [Equipment-family audit](G19_EQUIPMENT_FAMILY_CLOSURE_AUDIT.md) — identity and physical-work classification for all 808 units.
- [Full G19 construction log](G19_FULL_SHIP_SYSTEMS_COMPLETION.md) — **historical chronology**; intermediate "pending" statements were superseded by acceptance.
- [Full casualty acceptance](G19_FINAL_MULTI_SYSTEM_ACCEPTANCE_2026-10-29.md) and [seeded sustained damage](G19_SEEDED_ENDURANCE_ACCEPTANCE_2026-10-29.md).
- [Crew access](G19_ACCESS_COVERAGE.md), [rotary/movement mechanisms](G19_MOVEMENT_AND_ROTARY_OPERATIONS.md) and [service access](G19_FREIGHT_SERVICE_ACCESS.md).
- [Electricity and restoration](G19_ELECTRICAL_POWER_AND_RECOVERY.md), [atmosphere refill](G19_ATMOSPHERE_REFILL.md), [water/waste](G19_WATER_WASTE_RECYCLING.md), [hull repair](G19_HULL_BREACH_AND_RESTORATION.md), [equipment recovery](G19_EQUIPMENT_FAULT_RECOVERY.md) and [crew physiology](G19_CREW_PHYSIOLOGY.md).

## Source designs and prior milestones

- [v0.4 topology JSON](ox_full_ship.json), [v0.5 fitted candidate JSON](ox_full_ship_v0.5_candidate.json) and [Evennia integration boundary](EVENNIA_INTEGRATION.md).
- [Fixed spine](FIXED_SPINE_LAYOUT.md), [HAB B-prime mechanical basis](BPRIME_HAB38_MECHANICAL_CLOSURE.md), [HAB pressure access](HAB_PRESSURE_ACCESS_v0.5.md), [design reconciliation](DESIGN_CLOSURE_v0.5.md) and [v0.5 physical closure](PHYSICAL_CLOSURE_v0.5.md).
- [G17 initial installation](G17_FULL_SHIP_RUNTIME_FOUNDATION.md), [G18 physics introduction](G18_CONTINUOUS_PHYSICS.md) and [G18b casualty recovery](G18B_COUPLED_CASUALTY_RECOVERY.md) describe historical stages. These are not active unmerged gates.
- The complete [pre-G19 v0.5 build index](archive/README_V05_BUILD_HISTORY.md) retains evolving dimensions, early totals and prototype design notes without presenting them as the latest installed state.

## Future work is separately scoped

The [G19 accepted deferrals](G19_ACCEPTANCE_RECORD_2026-10-29.md) include secondary ECLSS equipment, navigation-hazard devices and related gameplay. The [active roadmap](../ROADMAP.md) prioritizes fuzz findings and autonomous crew operation across this ship. Any eventual reference-geometry promotion needs a versioned, state-preserving migration and matching visualization, not just a JSON overwrite.
