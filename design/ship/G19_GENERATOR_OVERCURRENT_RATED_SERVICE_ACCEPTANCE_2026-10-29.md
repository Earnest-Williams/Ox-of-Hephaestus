# G19 — original GEN-M overcurrent and rated service reset

**Date:** 29 October 2026  
**Integrated PR:** [#138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138) (draft)  
**Tested revision:** `bdc274590fd7888bf34fe5898dc48ed95d5c9dca`  
**CI evidence:** [run #40941917450](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40941917450) — **1/1 actual installed Evennia test passed**.

## Physical operating contract verified

The original `GEN-M` feeder `ISO-GEN-M`, installed in `GEN-M-ROOM`, is put under a genuine excessive electrical load at the existing generator management network. G19 trips it OPEN and latches `physics_power_trip_latched`, reducing assured electrical generation. A nonlocal switch close or breaker reset cannot bypass protective trip; reducing the observed overcurrent does not itself reset the latch.

The test also explicitly verifies that **positive gas surveying cannot begin while the installed generator is running**. The operator's initial survey attempt is denied by the original machine-stop interlock. From the real `ENG-CONTROL` station, an attended crew member invokes `generator_bay trip`, leaving the generator offline, isolated and still latched at its feeder. Only then is the enclosed generator room surveyed with positive finite atmosphere/skin measurements.

Original shared water, physical repair and EVA accounts plus individual enrolled crew physiology are commissioned without manufacturing a new air volume. The worker actually stages finite breathing oxygen and checks out one issued EVA suit through the original aft EVA lock; a legacy `ox_suit_verified` flag has previously been shown not to authorise hazardous switchgear. From `TRUNK-A-AFT`, a crew member obtains an exclusive, personally signed `generator_bay secure` permit and uses the original bidirectional `ACC-GEN-M-ROOM` pressure hatch to enter and close the enclosure. The original generator remains mechanically stopped throughout.

Only this suited worker, physically inside the surveyed and secured original room, can issue a signed `power ISO-GEN-M reset` request, clearing the protective trip flag once. Replaying the request produces exactly the same durable work receipt. Reset leaves the original breaker **OPEN**; it neither reconnects source power nor silently restarts the stopped generator. The worker exits by the same rated hatch and releases the original exclusive service permit. No global remote reset, added ship air, invented operator or automatic generator restart is permitted.

## Broader integration relationship

This accepts the original fitted GEN-M **overcurrent diagnosis and attended protection reset**, not every possible generator or switchboard failure. Generator mechanical rearm after an empty safe worksite remains independently tested by the original generator-bay suite. Nearby industrial BE-01 switchgear is covered by [focused rated-access acceptance #40940915917](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40940915917). All six cargo-drum attended damage repairs are independently accepted in [G19 six-drum report](G19_ALL_SIX_DRUMS_DAMAGE_CONTROL_ACCEPTANCE_2026-10-29.md). The general G19 multi-system gate remains authoritative for whole-vessel power/atmosphere/thermal integration.

This change preserves the fail-closed runtime access gate. The code revision updates test procedures to match current machinery safety, rather than weakening the original installed physical controls.
