# G19 — equipment fault localization and physical repair/restart

## Scope

This is the **source-specific maintenance case protocol**, not an omniscient diagnostic computer. The independently isolated 72 primary motors and 26 secondary controllers/process/shop machines use their actual per-machine G19 breakers and the existing locally operated ship machines. Protected fire pumps have **two actual incoming feeders**, both of which must be isolated for maintenance. An ordinary local panel may observe machine condition, a trip or service outage, but the worker must attend the real room to confirm the cause. Suited-flywheel, hull, and radiator jobs retain their specialized additional permits.

## Case state and acceptance rules

1. **Inspect:** physically present qualified crew inspects an existing machine, records machine condition and revision, present panel-alarm identity if available, existing repair stamp, previous material installation, and installed breaker identities. Hardware damage outranks electrical trips; a tripped breaker is a different fault class from a mechanical defect. A dark panel does not create current good telemetry.
2. **Isolate:** open **every actual feeder**; ensure the machine is commanded off and has no ongoing startup or live work. Real crew presence and safe compartment access are compulsory. Merely opening a breaker does not imply a stopped flywheel.
3. **Repair:** damaged machines use the existing **finite carried spares, issued reusable toolkits, timed physical work, qualified worker, specialist safe-work permits, and persistent equipment repair receipt**. Simple protection faults are checked only after the actual latched trip has been cleared.
4. **Check:** examine the still-isolated, physically restored component and compare its durable completion timestamp and cumulative installed material against the pre-work baseline. Reject a condition-only edit, replayed receipt, missing spare or newly tripped feeder.
5. **Authorize:** return to a measured, genuinely conducting feeder; verify local instrument freshness, absence of latched protection and ongoing work. This is permission to begin a supervised restart, **not** an automatic startup.
6. **Verify:** check actual commanded/on-line machinery, live correct feeder, no source alarm, credible local panel and **two independent subsequent physics instrument samples**. Record verified operator and game time.

Record transitions are structured and validated; no optimistic alarm acknowledgement or simulated test creates free machine performance. Existing engine, rotating mechanism, medical, and hull procedures are not replaced by this generic machine path.

## Verification

Pure tests in `world.tests.test_ship_fault_recovery` exercise complete ordering, dual-feed locks, material provenance, counterfeit restoration, live-trip refusal, non-existent equipment and successive instrument-epoch requirements. The installed-world integration must separately prove that crew commands, actual repair ticks, breaker resets, and local machine power obey the same transition contract. The unrelated 40-person voyage remains excluded.
