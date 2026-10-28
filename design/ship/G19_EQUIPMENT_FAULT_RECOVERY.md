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

## Local fault evidence (current G19 implementation)

`oxplantread fault:<machine-id>` is a crew-attended worksite report. It identifies the
original machine room, exact G19 feeder identities, breaker condition and
latched trips, actual main-panel source node, physically reconstructed
conduction, powered operating status, existing maintenance job, and the
quality and age of the *local* instrument panel. Its power result is a
ship-model reconstruction from fitted switchgear and supplies, **not** a
fictional independent voltmeter. It does not return unknown foreign-room
diagnostics to crew or AI agents.

`oxplant <request-id> fault <machine-id> inspect|isolate|check|authorize|verify`
is receipted in the existing durable global work namespace. The active
permit keeps its original worksite and physical condition evidence. Actual
work still uses the six finite reusable toolkits and individually carried
spares. Isolator closure is blocked during isolated, repairing and repaired
stages, including both fire-pump supply branches. When the permit is checked,
the engineer must manually reclose every genuinely fitted feeder; each
operation stamps that breaker at the authoritative ship game time.
Authorization requires a new credible local instrument sample strictly
**after the final reconnection**.

An energized breaker is not running-equipment proof. After a permitted
local startup, each real physics epoch independently checks the machine's
serviceable body, active command, `physics_online`, zero remaining startup
delay, live individually wired feed, current local powered panel, absent
relevant alarms, still valid reconnection evidence and no active maintenance
work. Only **two consecutive qualified epochs** allow signed verification.
Dark panels, altered breaker states, tripped equipment and stopped machines
reset the count; an epoch cannot be replayed to generate another sample.

**Coverage distinction:** all 98 fitted circuits now have exact physical
diagnosis, isolation and feed-reconnection validation. End-to-end
running-output verification is currently available only where a continuous
operating-state model exists for that machine. Some original auxiliary
motors have no `physics_online` output or direct flow sensor. They remain
unverified rather than being declared repaired on electrical continuity
alone. Their next construction task is an authentic motor-output observation
via the existing linked process or rotor state, without inventing sensors.

## CNC mill integrated power acceptance (28 October 2026)

The G19 installed CNC mill scenario now exercises the full signed work
chain with three kilograms of real issued spare stock, the original
`SHOP-MECH` worksite, `ISO-G19-SVC-SHOP-CNC-MILL` local breaker, a fresh
post-reconnection panel sample, and two subsequent sound operating epochs.
Its focused real Evennia run passed:
[Ox G19 CNC mill recovery #40739117665](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40739117665),
tested at `2c02bc1f`.

**Electrical diagnostic:** the original failing fixture had the GEN-M source
serviceable and commanded on, 3.0 MW rated available against 1.35 MW
selected normal demand, and a conducting CNC feeder. Yet the main
dispatcher correctly delivered **zero** because the fixture had closed
only a power route to the workshop distribution panel, with **no
qualifying fitted downstream consumer**. The initial report showed
`main_available_mw=3.0`, `live_consumer_circuit=false`,
`generator_delivered_mw=0.0` and `unserved_mw=1.35`.
This was not a generator fault and was not solved by bypassing power safety.

The accepted setup retains the real GEN-M -> workshop-panel connection
and additionally closes the existing GEN-M -> HAB-03 fire-detection
consumer route used elsewhere by accepted installed electrical tests.
The ship's G19 model budgets normal operation as a **grouped 1.35 MW load**,
not an invented 1.35 MW demand for the one detector. A live real
consumer is the admission gate to that grouped budget; its presence
must not be interpreted as detailed per-device power metering. The
generator, fuel custody, feeder protection and normal-load threshold
remain unchanged.

Use the focused workflow
`.github/workflows/ox-g19-cnc-recovery.yml` for future isolated repair
regressions; the larger G19 instrumentation workflow must also pass
before subsystem acceptance. Neither workflow runs the 40-person voyage.
