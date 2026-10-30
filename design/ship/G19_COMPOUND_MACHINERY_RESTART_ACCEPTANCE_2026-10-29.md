# G19 — physically verified CNC repair/restart amid coupled ship casualties

**Accepted at installed-subsystem level:** 29 October 2026  
**Tested code revision:** `3605df603956ab817bf6d77314a3ac4e0af18381`  
**CI evidence:** [G19 CNC mill recovery #40939873917](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40939873917) — **4 pure + 4 installed Evennia tests passed (8/8)**  
**Integration:** [PR #138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138), same original `g19-complete-ship-systems` branch

## Actual G19 machinery recovery under compound hazards

The new installed test `test_live_cnc_repair_and_restart_survives_compound_ship_casualties` extends the established original `SHOP-CNC-MILL` recovery case. A real physical machine with its original `NODE-LP-SHOP-MECH` panel and `ISO-G19-SVC-SHOP-CNC-MILL` feeder is placed in a witnessed failed condition.

The authenticated local crew member:

1. Attends the original workshop, physically inspects the fault, opens the specific fitted breaker and receives a durable isolation record.
2. Obtains a reusable toolkit from the original tool crib and exactly 3 kg of finite, locally surveyed spare parts at the central stores.
3. Returns to `SHOP-MECH`, begins an actual timed equipment repair, and remains at the worksite through 600 seconds of authoritative clock ticks.

During the work the **same** installed world holds a finite HAB-01 fire, continuing background heat, 7 kg of suspected drinking-water contamination under quarantine and a measured `0.015 kg/s` shell leak in the separately surveyed original `DR-04-SEC-03` cargo sector. The test checks live loss and conservation, persistent source isolation during repair, spent repair stock, real thermal change and water quality restraints. No fictional repair output is credited by changing a fault label.

## Interrupted restart and non-fabricated positive output

After serviceable equipment condition and finite material consumption are established, the same worker executes an attended post-repair check, manually recloses the original breaker, obtains a **later** panel sample and authorises the first startup. An actual `plant on` command drives the original machine gauge; mere breaker closure is insufficient.

The worker then **opens the fitted feeder during the initial restart-proof sequence**, producing lost machine output, a latched restart requirement and physical instrument-alarm history. The original supply is reclosed, but cannot automatically restart the mill. The worker explicitly requests the machinery to run again.

The equipment can be signed off only after the local instrument signals recover from their latched lost/unreliable state and the physically measured spindle completes **two fresh consecutive good observations**. The final verification is signed and globally receipt-deduplicated. The original cargo leak and contaminated water remain physically damaged at the end.

The acceptance run also repeats the original installed CNC finite-repair/restart path, spindle-coasting isolation safety and the legacy work-order breaker's isolation requirements, alongside four pure workshop-gauge tests.

## Boundaries and continuation

This is accepted proof of **one fitted high-energy workshop machine's positive recovery** under simultaneous thermal/fire, potable-water and cargo-shell casualties, plus interruption of its own local electrical feeder. It does not waive requirements for local instruments, manual restart, real source power, or finite work materials on other machinery.

The parallel six-drum attended cargo-shell repairs and long-duration fire/water/power casualties are independently accepted in [G19 all-six-drum damage-control acceptance](G19_ALL_SIX_DRUMS_DAMAGE_CONTROL_ACCEPTANCE_2026-10-29.md), while the broader G19 final integration gate remains authoritative for source, physics and multi-system compatibility.
