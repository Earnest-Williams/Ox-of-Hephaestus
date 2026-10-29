# G19 — attended fire mist and potable-water recovery

**Date:** 29 October 2026  
**Integration:** [PR #138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138) (draft)  
**As-fitted source:** original v0.5 ship, original HAB fire-main outlet and forward fire pump, original A-side ECLSS water/waste machinery, forward EVA lock, and DR-03 cargo shell.

## Runtime safety correction

Before this revision, the crew command `mist PZ-HAB-xx start` accepted the inherited character attribute `ox_suit_verified` as its sole protective-gear test. This was not linked to an actually issued suit or finite breathing oxygen.

The G19 command now checks actual installed EVA suit custody via `suit_of`, the enrolled crew's real health row, remaining positive suit oxygen, minimum suit integrity, noncritical physiological condition, and absence of active EVA transit. A stale boolean alone cannot authorize a person to enter the active fire's hazard zone. Mist **stop** remains available to the local operator; this does not fabricate fire-water delivery or clear a fire automatically.

## Installed compound-recovery contract

The disposable, canonical Evennia world explicitly commissions real equipment and persistent material ledgers, and conducts the following in the **same** physical epoch:

1. Routes genuine `NODE-GEN-B` power to `NODE-LP-WATER-FWD` and the independent `NODE-HAB-06-ECLSS-A-LP` water-treatment panel, while the main generator serves an original fire-detector source. The independently fused forward pump and both actual A-side treatment/waste motors are selected. The original potable, grey and black wet-network valves must physically conduct.
2. Verifies the as-authored forward fire-main graph reaches a real HAB mist endpoint. Injects a finite fire load and 1.5 kg of suspected potable contamination, and registers a separately surveyed shell leak in `DR-03-SEC-05`. These faults are not crew-level powers.
3. Proves that a legacy `ox_suit_verified=True` flag without an issued suit fails authorization without creating an accepted work receipt. An enrolled worker physically stages 0.75 kg breathing oxygen, enters the original forward EVA lock through its actual pressure hatch, checks out a fitted suit, returns through the rated hatch, and can start mist even after the legacy flag is set **false**.
4. Requires actual forward fire-pump output in the ship's process-output ledger and finite normal-water consumption. Opens the forward pump's individual source fuse and confirms delivered mist drops to **zero** while the fire persists. Reclosing the fitted fuse restores observed discharge without creating an independent fire-water reserve.
5. Positively surveys and carries exactly 1 kg of filter medium from the correct original store, loads the existing A-side water processor, and commands a real decontamination run. A passing physical tick must record `decontaminated_kg > 0`, consume filter media, and deliver captured hazardous residue. The original main potable water can pass a later crew-attended quality sample and clear quarantine only after contamination is removed.
6. Fire smoke, burnt fuel and leaked cargo gas remain real. Replayed fire-mist command IDs remain immutable and do not duplicate canonical physics events. No continuous ship tick is applied twice.

## Acceptance evidence

- [Focused installed run #40955124764](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40955124764) **passed 1/1** at runtime commit `23a6e257948a84bad79f05f762371b05ce0e56e1`. This proved actual suit and source-independent water-treatment recovery in one installed world.
- The subsequent test assertion explicitly sets `ox_suit_verified=False` after issued-suit checkout, to prove the positive case does not depend on the old flag. The revised focused acceptance is subject to its own result.
- The same scenario is now included in `.github/workflows/ox-g19-final-campaign.yml` as the **13th** independently selected installed compatibility witness. The five-job campaign's complete final-head acceptance remains a separate requirement.

## Scope

This closes a specific G19 fail-open command path and verifies the selected physical firefighting/water-recovery process. It does not claim every fire nozzle, filter location, thermal zone or casualty combination has been independently tested, nor substitute for other already accepted equipment-fault, cargo, EVA and pressure-boundary gates. No original hardware was invented or repositioned.
