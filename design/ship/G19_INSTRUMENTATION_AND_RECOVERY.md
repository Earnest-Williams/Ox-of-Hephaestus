# G19 — fitted instrumentation, alarms, fault evidence and attended recovery

**Date:** 28 October 2026  
**Integration:** `g19-complete-ship-systems`, draft [PR #138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138)  
**Contract:** believable original/refitted working-freighter instruments, not spacecraft certification, not an all-knowing simulation UI. No 40-crew voyage.

## Authoritative hardware

The installed reference ship contains **116 independently authored `local_panel` equipment units**. All 116 have separate **original `NODE-<panel-id>` electrical nodes** owned by their original equipment, not fictitious sensors/rooms. Panel identities include inherited `LP-<fixed-room>` and `HAB-xx-<room>-LP` conventions. Commissioning enumerates these directly from the source candidate and validates the corresponding installed equipment and physical power nodes before opening the new evidence ledger.

The pressure topology has 133 canonical pressure cells. The new local panel reads only its current pressure cell and equipment/isolators in **that panel's own room**, when the panel is intact and its own electrical node is energized by the actual network. Unpressurized fixed bays still use existing surveyed/suited electrical-access gates. Fitted fire loops and the eight `HAB-xx-FIRE-DETECT` and `HAB-xx-COMMS-NODE` protected pairs are checked as real hardware, not assumed to be operational by name.

No operator, AI or crew is allowed to read the entire invisible ship state through a workstation. A given worker must be physically at an installed local panel. It is possible for a room to have no reporting panel, for a panel to be dark or failed, and for surviving information to become stale.

## Measured channels and consequences

- **Pressure/air:** observed pressure, oxygen partial pressure, CO2 fraction, smoke fraction, cell temperature, leak rate, fire burn and physical pressure-cell damage. These are measured only at original fitted local-panel pressure-zone positions.
- **Electrical:** latched actual installed breakers in the panel's original room; a dark panel is a loss of telemetry, not proof that its room is safe.
- **Machinery:** physically present equipment condition (degraded/faulted/failed/severed/jammed) and existing, actually observed service outages. No prediction of unknowable failures.
- **Water/food:** commissioned water quality/quarantine, working-tank quantity at real water/ECLSS rooms, depleted surveyed grow nutrients at fitted grow rooms, and actual locally retained spoiled food mass where applicable.
- **Fire loops:** real local detection-loop damage and missing/faulted HAB protected detector supply at the original affected arc.
- **Bridge fire relay:** `ENG-CONTROL`, `CMD-PRIMARY`, `CMD-EMERG` report only serious alerts from each HAB whose **original powered fire detector and protected comm node** are both intact and powered and whose original local source panel is reporting. A failed detector/comm pair is reported as `lost_protected_links`, not a false all-clear. No cross-ship arbitrary machinery-health feed is invented.

Reference alarm limits: pressure outside 80–125 kPa; O2 partial pressure outside 16–26 kPa; CO2 mass fraction above 0.008; smoke fraction above 0.00001; combustion/leak positive; temperature outside 278.15–313.15 K; pressure-cell damage index at least 0.2. These are **gameplay thresholds** calibrated to the existing physics, not a claim about flight hardware certification.

## Fault lifecycle and evidence

Each physically sourced alarm has a stable key `<panel>|<code>|<original-subject>`, distinct first/last witnessed ship times, severity, occurrence count, active/cleared status and **human** acknowledgement with the actual crew dbref. The original ship clock advances it only when physics time advances (no repeated tick credit and no wall-clock extrapolation).

Repeated identical fault readings do not spam history. Acknowledgement changes only the human receipt; **it does not isolate anything, clear the fault or repair equipment**. Two subsequent genuine, successfully sampled good physics ticks are needed to clear an alarm. A blackout or failed panel leaves all prior hazards unresolved and records `INSTRUMENT_LOST` with its previous last-good timestamp. A reasserted fault resets acknowledgement, never silently declaring a repair.

The bounded durable event ring contains at most 2,048 transitions, while active alarm records remain intact. History sequence numbers remain monotonically increasing across restart; finite retention is an explicit limit, not infinite telemetry storage. A diagnostic response is a ranked-*category* operational check with its actual source, not a guaranteed root-cause diagnosis or an authorised repair command.

## Crew operations

After operator `commission_g19_instrumentation(operator_approved=True)` (which requires the installed electrical system and never resets prior valid observations), the following are available:

- `oxplantread instruments`: only powered local panels in the character's current room, with timestamps, sensor quality, measured channels, active alarms and recent events
- `oxplantread panel:LP-ENG-CONTROL`: an identified **physically present**, actually powered original panel
- `oxplantread alarms`: only active alarms on usable local panels in the current compartment
- `oxplantread diagnose:<panel>|<code>|<subject>`: provenance, state, acknowledged-by and safety-constrained *next checks* for a witnessed fault at that same local panel
- `oxplantread alarm_bridge`: only the original protected eight-HAB fire/pressure relay, from its three established command/engineering rooms, and only with real powered hardware and reporting sensor origins
- `oxplant <32hex> instrument <real-panel-id> test`: local powered panel self-test (no fabricated new measurements or repairs)
- `oxplant <32hex> instrument <real-panel-id> ack:<alarm-key>`: physically present authenticated crew member signs a persistent once-only acknowledgement. The existing global `WorkReceipt` and ship event histories prevent replaying an acknowledgement as a second action.

### Actual recovery chain

Pressure leakage → inspect original pressure zone/hatch/isolation/hull work; actual rated isolation and finite-spares hull restoration are already handled by existing commands. Electrical overcurrent → verify real circuit, remove load/clear fault, then physically reset the original breaker; merely acknowledging an alert does not reset it. Lost machine service → examine machine, individual supply and manual restart; repair needs a real toolkit, physical crew, finite spares and measured elapsed work. Water quarantine → attended sample and original finite filtration, not a remote optimistic reset. Fire/smoke → verify real detection, local breathing protection, isolation and actual mist supply. After genuine repair or successful restoration, *two independent live samples* close the alert.

## Acceptance

`.github/workflows/ox-g19-instrumentation.yml` is the independent draft-safe acceptance gate: (1) pure instrument/provenance/latching/tamper/fuzz and established resource-system tests; (2) installed 116-panel/world/fault/self-test/relay tests; and (3) **98 existing installed tests** across electrical, water/waste, food, physiology, movement, EVA, medical, hull and waste repair, in separately isolated sharded jobs. The final code head is accepted only if **every job** succeeds. Independent compatibility tests are not removed or skipped to manufacture acceptance.

This phase extends the operational ship while leaving PR #138 draft and the user-excluded 40-crew voyage unrun. Original hardware identity and live crew point-of-view remain the source of truth.


## Hardening: uncertain sensors, fast failures and recorded panel self-test

- **Physical deterioration matters.** A degraded, powered original panel has `status=degraded`, no fresh credible channel readings, preserves its earlier timestamp and raises `INSTRUMENT_UNRELIABLE`. It cannot silently clear an existing fire, pressure or machinery failure. Two subsequent good, *distinct ship-time* observations are needed to resolve each latched alarm after physical service.
- **Rates are observed rather than guessed.** Two sequential trustworthy original-panel samples can detect a pressure fall faster than **0.12 kPa/s** (`RAPID_DECOMPRESSION`) or a local temperature rise above **0.30 K/s** (`TEMPERATURE_RISE_RATE`), even before an absolute hazard threshold is exceeded. A single sample after blackout or damaged-panel service is not used to extrapolate dangerous trends.
- **The protected HAB relay has three distinct outcomes:** `alerts_by_arc` contains observed issues or a genuine empty warning list with a live sensor; `lost_protected_links` means the actual fire-detector / comms hardware lacks power or integrity; `lost_local_monitoring` means the protected link exists but no dependable local panel samples are being received. Silence is not evidence of safety.
- **Signed panel self-tests are real work.** `oxplant <uuid> instrument <original-panel-id> test` now records an original hardware-condition check, local conducting electrical node, last reliable reading age, and pass/fail into the same durable world event and replay-safe `WorkReceipt`. A passed check means the live source and recent recorded signal are available, not that every physical sensor is calibrated, or that a machine has been repaired.
- **Acceptance tests** include actual degraded panels and restoration, live relay-loss diagnostics, rapid decompression, thermal acceleration, no unsupported trend across dark intervals, replay protection and seeded quality/fault sequences. The existing ship compatibility suite remains intact; the excluded 40-crew voyage is not run.

### CI policy

The food and instrumentation acceptance workflows run for direct G19 branch commits, but automatically **defer expensive pull-request jobs while the PR is draft** and react to `ready_for_review`. This satisfies the repository-wide CI scope guard without treating a prior green commit as acceptance of new runtime edits.
