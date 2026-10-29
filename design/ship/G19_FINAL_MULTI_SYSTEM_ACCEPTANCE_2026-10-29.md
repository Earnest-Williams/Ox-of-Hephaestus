# G19 — integrated multi-system casualty and restart acceptance

**Date:** 29 October 2026  
**Single integration branch:** `g19-complete-ship-systems`  
**Pull request:** [#138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138) (draft; not merged)  
**Tested code revision:** `ac7f35e0566503d75e75fcec42972a8c8fd76698`  
**CI evidence:** [run #40931792635](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40931792635) — **5/5 jobs successful**

## Scope and result

The final-campaign workflow now triggers on changes under `game/world/**`, instead of only a small subset of the ship physics files. It executes the original canonical Evennia world and runs both cross-system failures and individually witnessed physical outputs, rather than only checking that service endpoints are registered.

| Job | Result | Evidence |
| --- | ---: | --- |
| `pure` | **30/30 tests** | Conservation and repair/fault-recovery kernels; original access/casualty contracts |
| `installed_campaign` | **7/7 tests** | Four existing multi-system/restart/atomicity scenarios plus three independently ordered compound-fault scenarios |
| `adjacent_systems` | **3/3 tests** | Installed brownout, stale instrumentation, and original cargo-breach/casualty extraction |
| `cross_system_compatibility` | **12/12 tests** | Existing physical-output and failure checks across G18 fire/thermal/water, live atmospheric CO2 capture, bearing lubrication, water processors, food spoilage, portable smoke control, workshop machining/repaired output, propulsion delta-v, medical feeder loss, port/movement interlocks, suited hull recovery, and powered cabin fan-coil cooling |
| `independent_process_restart` | **3/3 process phases** | Distinct interpreter A/B/C instances against the same disposable, durable as-installed ship |

**Total:** **52/52 automated unit/installed checks plus all three independent-process phases passed**, in one successful five-job run. The immediately preceding expanded casualty-only run [#40931574145](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40931574145) also passed all four of its jobs at code revision `bea9396579ceec53f07ded8b17fd1d70eb26f9e1`.

## Cross-system invariants exercised

- Authentic DR-01 cargo shell loss, a deliberately opened fitted pressure boundary, a live HAB-01 fire, quarantined working drinking water, and the actual severed `EDGE-GEN-M` electrical feeder coexist in the authoritative physical clock.
- Three ordered hazard sequences exercise fire → water → power, power → fire → water, and water → power → fire. Intervening clock steps cannot erase earlier losses, heal the feeder, restart a restrained cargo rotor, or clear untreated water.
- Closing the original cargo-sector pressure hatch stops further exchange into its service gallery while the isolated breached sector continues to lose its own finite gas.
- Per-tick measurements track lost gas and consumed fuel monotonically. Replaying an equal-time tick and a previous signed physical-work request cannot reapply resources or duplicate canonical journal events.
- A forced exception in a later physics substep rolls back earlier gas, generator resource, water, fire and atmosphere effects atomically. A successful retry advances the original interval once.
- Three wholly separate Python processes retain one persistent clock, one signed receipt, an actual broken generator feeder, contamination and consumed resources. Their evidence advanced at game times **1060 → 1290 → 1350 s**; original cargo-sector gas loss advanced **18 → 87 → 105 kg** without restoration.

## Evidence boundaries

This is an **accepted integrated multi-system casualty and persistence gate** at the stated revision. It is stronger than independent equipment-family classification or a single subsystem-only smoke test, but it is not proof that every one of the 808 fitted devices has passed every possible coupled failure. Preserve the original pressure-cell inventories, the 421 original spaces, the 517 authored undirected passages, and individually located original equipment.

Keep PR #138 in draft until remaining whole-ship closure criteria have explicitly been judged against its current code head. Continue with longer seeded combined-operation sequences and regression compatibility whenever cross-system code changes. Do not silently treat successful registration, source availability or a repaired component as proof of positive output or authorised restart.


## Follow-on endurance signoff, same integration branch

The subsequent [seeded sustained casualty campaign](G19_SEEDED_ENDURANCE_ACCEPTANCE_2026-10-29.md) passed **7/7 independent installed Evennia jobs** in [CI #40936113860](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40936113860), tested at code revision `c8b0bb962e17a99d045be0b1ece077822e7a85a0`.

Six separate 24-minute runs cover **all six permutations** of fire, power and water contamination during a true cargo-sector shell casualty. A seventh **180-minute** run retains the same physical faults without time-skipped resources, damaged-hatch repair or automatic inventory restock. Total independently tested game time is **324 minutes**, with minute-by-minute original pressure-cell, gas loss, fuel custody, generator supply, quarantine, instrument time and replay checks. This strengthens the earlier 52-test acceptance without revising its separate tested code revision.


## New 13th physical-output witness — green revised integration gate

After the G19 attended HAB fire-water recovery fix, the selected real-world
compatibility matrix gained its **13th** installed witness. It requires a
physically issued, finite-oxygen EVA suit to start HAB fire-mist suppression;
the old `ox_suit_verified` profile flag cannot substitute for gear. It also
requires actual `FIRE-PUMP-FWD` discharge under motor-fuse interruption,
a physically carried, consumed chemistry filter, positive original
`WATER-PROC-A` treatment and attended potable quality clearance, while an
independent original DR-03 cargo shell remains damaged.

**Current validated code revision:** `f9f46ad8c9ed079fc028520aae4b7c0da22f5759`.
[CI #40958586524](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40958586524)
passed **5/5 jobs**: **30 pure**, **7 installed casualty/replay**, **3 adjacent
installed**, **13 selected live physical-output compatibility tests**, and
**3 independent-process restart phases**. This updates the earlier 52-test
snapshot to **53/53 automated tests plus the 3 restart phases**. The earlier
historical acceptance revisions listed above remain valid as historical
records, rather than being silently rewritten to describe tests they did not
contain. [Detailed physical fire and water recovery contract](G19_ATTENDED_FIRE_WATER_RECOVERY_2026-10-29.md).

The same revised test code passed the [seven-case seeded endurance run
#40958586472](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40958586472)
and [five-job original waste and generator repair run #40958586487](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40958586487).
