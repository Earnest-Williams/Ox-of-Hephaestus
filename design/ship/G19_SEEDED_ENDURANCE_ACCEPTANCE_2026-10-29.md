# G19 — sustained seeded, full-world casualty acceptance

**Accepted:** 29 October 2026  
**Single G19 integration PR:** [#138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138)  
**Tested branch revision:** `c8b0bb962e17a99d045be0b1ece077822e7a85a0`  
**Source and workflow:** `game/world/tests/test_installed_ship_g19_seeded_endurance.py`, `.github/workflows/ox-g19-seeded-endurance.yml`  
**GitHub Actions:** [#40936113860](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40936113860) — **7/7 independent installed-world jobs passed**

## Authoritative installation and fault-order matrix

All cases begin with the canonical as-fitted Evennia ship, install its authentic pressure cells and equipment, and run the same G19 clock and controller interfaces. Each case has one real crew character in the original DR-01 service gallery, a manifest-surveyed cargo-sector atmosphere, an operator-attested finite shell breach, a genuinely opened original rated hatch, a physically operated isolation closure after nine simulated minutes, a HAB-01 fire, water contamination and a severed original `EDGE-GEN-M` feeder.

The random generator is locally seeded; the event-order mapping is asserted so that all six permutations are genuinely exercised, not merely drawn with replacement.

| Seed | Fault order | Duration | Original cargo sector | Vented cargo gas | Fuel burned |
| --- | --- | ---: | --- | ---: | ---: |
| `19A0` | Water → fire → power | 24 min | `DR-01-SEC-01` | 57.600 kg | 7.000 kg |
| `19A1` | Fire → water → power | 24 min | `DR-01-SEC-03` | 64.800 kg | 5.000 kg |
| `19A3` | Water → power → fire | 24 min | `DR-01-SEC-06` | 64.800 kg | 9.000 kg |
| `19A6` | Power → fire → water | 24 min | `DR-01-SEC-01` | 43.200 kg | 6.000 kg |
| `19A7` | Power → water → fire | 24 min | `DR-01-SEC-03` | 64.800 kg | 7.000 kg |
| `19C3` | Fire → power → water | 24 min | `DR-01-SEC-04` | 43.200 kg | 6.000 kg |
| `19D4` | Water → power → fire | **180 min** | `DR-01-SEC-08` | **81.057 kg** | 9.000 kg |

The seven isolated test worlds account for **324 minutes (5 h 24 min)** of simulated ship time. Their fuel and gas losses are separate observations in separate authoritative installed worlds, not quantities added to a single ship's inventory.

## Per-minute checks

The test does not trust a single final summary. Every simulated minute is a bounded, transactional G19 world tick; the following conditions are checked on the persistent real world state:

1. Original cargo gas mass plus cumulative shell loss minus measured gallery exchange equals the measured initial gas charge, including after the hatch is shut.
2. Global vented mass, cargo shell loss and burned fuel never reverse. The DR-01 movement controller remains inhibited while the actual damaged sector prevents safe rotation.
3. Actual generator-cartridge inventory plus the spent-cartridge custody ledger equals the original finite magazine charge. The failed `EDGE-GEN-M` remains broken and cannot continue assuring normal power.
4. Contaminated working water stays quarantined until it receives an actual treatment and quality-clearance operation. It is never reset merely because time advances.
5. The observed instruments share the same game-clock epoch and maintain a current sample timestamp.
6. Previously signed crew hatch work and already completed ticks cannot be replayed to duplicate canonical events or resource flows; the original hatch can be closed without restoring the shell damage.
7. Recommissioning cannot replace the established ship epoch or refill losses after the prolonged run.

The real three-hour case holds the damage and quarantine state substantially beyond the initial casualty transition; it does not gain an infinite battery, vented air, water-treatment credit, or automatic feeder repair.

## Scope boundary and continuation

This establishes a **passing, sustained, deterministic multi-system physical-failure gate**. It complements the already accepted 52-test integrated fire/electrical/water/cargo/crew-output suite at [#40931792635](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40931792635) and its three independent persistent-process phases.

It does not prove every possible fault in every one of the fitted original equipment families. Other focused installed acceptance cases remain the evidence for physically verified machining, medical treatment, airlocks, crew access, propulsion, radiator service and EVA repair.

Keep these tests in G19's single integration branch. Preserve the distinction between tested revisions, later documentation revisions, and whole-project merge acceptance.


## Broader current-code regression acceptance

The adjacent five-job **final multi-system** regression also completed successfully after the endurance test module was introduced, at code revision `e8182a621f94838114f9d7c88eb3aed902255967`: [run #40936062977](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40936062977).

All five jobs passed: 30 pure conservation/repair tests, seven installed compound-casualty/replay tests, three adjacent installed regressions, 12 positive-output and failure-path compatibility regressions, and three independent fresh-process restart phases. **52/52 executable tests plus the three process-restart phases passed** in that broader gate. The subsequent seed workflow revision `c8b0bb96` only alters workflow configuration; the original clock and ship runtime remain the same as the tested `e8182a62` revision.
