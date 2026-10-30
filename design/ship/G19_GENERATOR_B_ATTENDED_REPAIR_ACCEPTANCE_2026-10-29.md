# G19 — original GEN-B attended repair and retained isolation

**Date:** 29 October 2026  
**Integration:** [PR #138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138), branch `g19-complete-ship-systems`  
**Physically tested code:** `f9f46ad8c9ed079fc028520aae4b7c0da22f5759`  
**Installed acceptance:** [waste/offload and equipment repairs #40958586487](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40958586487), **6/6 installed Evennia tests passed**  
**Coupled compatibility:** [five-job multi-system #40958586524](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40958586524), **5/5 passed**  
**Sustained hazards:** [seeded casualty endurance #40958586472](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40958586472), **7/7 passed**

## Original failure

A previously accepted legacy generator-repair test attempted to maintain the installed `GEN-B` from `GEN-B-ROOM` after setting `ox_suit_verified=True`. The ship now rejects this attestation: a boolean is neither an oxygen supply nor a personally signed rated-space maintenance permit. Both the installed waste/repair matrix and the wider instrumentation matrix identified the same regression against their existing generator repair test. These were compatibility test defects, **not** evidence that the current physical safety gate should be disabled.

## Correct as-fitted operating sequence

The updated `test_failed_generator_needs_isolation_and_never_restarts_after_repair` now:

1. Commissions the original electrical, water, repair, EVA, individual physiology and three-generator-room ledgers; uses the original equipment and original crew character, not a parallel ship.
2. Trips the installed `GEN-B` machine and opens `ISO-GEN-B` from the real engineering controller. Operator-observed failed machinery stays offline and physically isolated.
3. Positively surveys the existing `GEN-B-ROOM` finite gas and skin temperatures, records the original suited-maintenance worksite, and issues **3 kg of physical spares** plus a reusable toolkit.
4. Denies repair and owner lockout when the engineer has only an obsolete suit flag. Stages a finite 0.75 kg oxygen issue and actually checks out one of the four original EVA suits through the aft EVA lock and its bidirectional rated pressure hatch.
5. Personally secures the original `GEN-B-ROOM` permit from `TRUNK-B-AFT`, opens and traverses `ACC-GEN-B-ROOM`, closes the hatch and inspects the stopped original machine.
6. Begins a signed, repeat-safe attended 600-second repair while keeping the legacy suit flag **false**. Each real clock tick advances the same installed repair ledger; the work consumes the already carried 3 kg rather than making new stock.
7. Verifies that the machine is serviceable but its `physics_online` and `physics_commanded_on` flags remain **false**. The original generator breaker stays **open**: repair completion is not a restart.
8. Returns through the fitted rated hatch, closes it and releases the exclusive maintenance permit without automatically energising the source.

The repair request has a globally deduplicated receipt, one installed part debit and one authoritative world clock. The former profile-flag shortcut is neither required for genuine repair nor capable of authorising entry by itself.

## Ongoing integration standard

The accompanying instrumentation workflow has been extended to trigger when `game/world/tests/test_installed_ship_waste_repair.py` changes, so its existing cross-system generator recovery witness cannot silently remain on the old implementation after future changes. This is one original generator's actual service repair acceptance, separate from generator overcurrent trip/reset evidence at [GEN-M #40941917450](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40941917450) and the installed three-generator rated-room entry suite.

The G19 integration PR remains draft until its remaining full-branch acceptance and closure review are completed.
