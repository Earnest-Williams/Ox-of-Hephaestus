# G19 — acceptance record

**Integration PR:** [#138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138), branch `g19-complete-ship-systems`
**Audited head:** `c56990ca7a3cee79029ea50d50b96f6da7ede0e9` (GEN-B finite restart proof)
**Fix head:** `7071f815` (casualty repressurisation, blocker B1), plus this documentation commit (blocker B2)
**Base:** `main` @ `9085c77` (G18c). The branch contains `main` with no drift: 937 commits, 237 files, +54,519 / −179.
**Audit date:** 29–30 October 2026
**Method:** local reproduction at the exact head on Python 3.12, using the same commands as the workflows. GitHub Actions results for this head were **not** read; see "Evidence limits".

## Decision

**Accepted and merged.** Both blockers are fixed; PR #138 was squash-merged into `main` as `d7fc201d` on 30 October 2026 after 47/47 workflows passed at its final head `8802f8c3`.

The audit at `c56990c` found two blockers. Both are now fixed on the branch.

| # | Blocker | Kind | Resolution |
| --- | --- | --- | --- |
| B1 | Atmosphere could not be restored after a breach: the v0.5 refill gas chain was classified but not simulated | Required ship function missing | `7071f815`: [casualty repressurisation](G19_ATMOSPHERE_REFILL.md) from the fitted banks over the authored network |
| B2 | Top-level docs described the full ship as Developer-only, contradicting this PR; no G19 status row | `design/ROADMAP.md` same-PR documentation rule | README, STATUS, `game/README`, `design/ship/README` and `EVENNIA_INTEGRATION` updated |

Everything else required by the closure plan was verified at the audited head or is recorded below as explicitly deferred and non-blocking. Per the stopping rule, G19 does not expand beyond B1 and B2.

## 1. Physical ship inventory

Recomputed independently from the data files the installed world loads.

| Item | Required | Found | Source |
| --- | ---: | ---: | --- |
| Original spaces | 421 | **421** | `ox_full_ship.json` (topology) and v0.5 candidate; identical ID sets |
| Authored passages | 517 | **517** | Identical link IDs and endpoints in both files; 1,034 directional exits |
| Equipment units | 808 | **808** | v0.5 candidate; all IDs unique; every unit placed in a real space |
| Equipment families | 91 | **91** | `kind` field; all 91 dispositioned in `ship_equipment_family_audit.py` |
| Source data changed by PR | none | **none** | Neither ship JSON file is in the diff |

Evidence tiers at the audited head (343 direct physics / 159 interface or custody / 306 controlled hardware / 0 open) sum to 808 units and 91 families. B1 promotes the refill bank, regulator and rotary-union families, giving 349 / 159 / 300 / 0 units and 37 / 26 / 28 / 0 families. All 17 `design/ship/check_*.py` validators pass.

## 2. Functional systems

Each area is judged on the closure plan's three questions: the behaviour exists; it acts on the installed ship rather than a separate model; it can fail, be diagnosed and be restored by credible operations.

| Area | Exists | Installed ship | Fail / diagnose / restore | Representative evidence at head |
| --- | :---: | :---: | :---: | --- |
| Electrical | Yes | Yes | Yes | `installed_ship_electrical`, `generator_bays`, `waste_repair` (GEN-B finite restart with delivered bus energy) |
| Atmosphere | Yes | Yes | Yes (B1 fixed) | `crew_physiology`, `portable_air`, `survival_craft_air`, `gas_refill` (bank air metered back to setpoint after restoration) |
| Thermal | Yes | Yes | Yes | `exterior_radiators`, `cabin_fancoils`, G18 fire/thermal regression |
| Fire | Yes | Yes | Yes (pressure cells) | `g19_attended_fire_water_recovery` (finite metered pump discharge, fuse loss and restore) |
| Equipment | Yes | Yes | Yes | `equipment_family_audit`, `instrumentation`, `workshop_fabrication`, `workshop_welding` |
| Hull | Yes | Yes | Yes | `hull_restoration`, `eva_major`, `g19_cross_drum_repair` (6/6 drums), then `gas_refill` |
| Water / waste | Yes | Yes | Yes | `water_recycling`, `waste_repair` |
| Cargo / mechanics | Yes | Yes | Yes | `unclassified`, `freight_service`, `movement` |
| Propulsion | Yes | Yes | Yes | `propulsion_proof`, `rcs_proof`, `propulsion_bay`, `propulsion_exterior` |
| Crew exposure | Yes | Yes | Yes | `crew_physiology`, `medical`, `casualty_transport` |
| Navigation / access | Yes | Yes | Yes | `access_audit`, `indexed_personnel`, `hazardous_access`, `industrial`, `operational_routes` |
| Fault recovery | Yes | Yes | Yes | `instrumentation`, final campaign, seeded endurance |

## 3. Integrated casualty invariants

| Invariant | Status | Evidence |
| --- | --- | --- |
| Gas, O₂, water, fuel, energy and repair materials accounted for | Holds | Per-tick monotonic loss and fuel custody in the final campaign; every stock-setting operator survey refuses a second survey (checked for nutrients, portable damage, portable air, weld filler, refuge sorbent) |
| Damage persists until repaired | Holds | Ordered compound-fault scenarios; 180-minute seeded run |
| Isolation stops flow without fixing damage | Holds | Closed cargo-sector hatch stops gallery exchange while the sector keeps losing gas |
| Repairs need equipment, access, time and authorised people | Holds | Finite spares, issued suits, permits, timed work orders; role checks in the crew dispatcher |
| No automatic restart when serviceable | Holds | `test_failed_generator_needs_isolation_and_never_restarts_after_repair` |
| Crew location, exposure and access respected | Holds | Gated traversal; physiology sampling from the occupied cell |
| Faults propagate without impossible side effects | Holds | Atomic rollback of a failed substep; replay of equal-time ticks and signed requests is a no-op |

**Authority boundary.** Player commands `oxplant` / `oxplantread` reach only the crew dispatcher. The 22 operator survey functions and `configure_scenario_casualty` are not exposed by any command. Inside the dispatcher, `Developer` permission substitutes for a crew role at nine checks, so AI crew accounts must never hold `Developer`.

## 4. Persistence and deterministic operation

| Check | Result at head |
| --- | --- |
| Three independent processes on one durable database (prepare / resume / confirm) | Pass: game time 1060 → 1290 → 1350 s; cargo-sector loss 18 → 87 → 105 kg without refill; one durable receipt; feeder still severed; 3.5 kg fuel burned |
| Rearm, rebuild and backlog with exactly-once work receipt | Pass (installed campaign) |
| Persistent timer rebinding without twin scripts or re-armed gas | Pass (installed campaign) |
| Failed 30-second substep commits nothing | Pass (installed campaign) |

## 5. Regression results

### At the audited head `c56990c`

#### Final multi-system campaign (`ox-g19-final-campaign.yml`)

| Job | Result |
| --- | --- |
| `pure` | **30/30** |
| `installed_campaign` | **7/7** |
| `adjacent_systems` | **3/3** |
| `cross_system_compatibility` | **14/14** |
| `independent_process_restart` | **3/3 phases** |

**Total: 54/54 tests plus 3/3 restart phases at the audited head.** This is the set 30 + 7 + 3 + 14. Earlier documents stop at 53 because the 14th compatibility check, the GEN-B never-restarts test, was added after the last recorded run.

#### Module sweep at `c56990c`

| Scope | Modules | Tests | Result |
| --- | ---: | ---: | --- |
| Pure G19 modules (`unittest`) | 51 | 365 | All pass |
| Other modules (`world.test_runner`), stopped after 35 of 84 to retest at the fix head | 35 | 209 | All pass except `test_agent_repair`, which needed the `ox_ai` handler package installed (environment, not code) |
| Ship design validators | 17 | — | All pass |
| `.github/ci/check_ox_ci_scope.py` | — | 156 filters | 0 errors |
| Full `compileall` (game, handler, scenarios, CI) | — | — | Pass |

Every one of the 617 test methods in the 91 PR-touched modules is referenced by at least one of the 38 G19 workflows; there are no orphan tests.

### At the fix head

Verified locally at `7071f815`:

| Scope | Result |
| --- | --- |
| Pure G19 modules, including the 16 new refill tests | 52 modules, 381 tests, all pass |
| Installed refill module (`test_installed_ship_gas_refill`) | 4/4 |
| Documentation workflow checks (context rot, local links) | Pass; 606 local references |
| `.github/ci/check_ox_ci_scope.py` | 0 errors |

GitHub Actions at `7071f815`: **35 workflows succeeded, 0 failed**, plus 43 skipped by the draft-PR gate. The documentation and fast PR gates were superseded by the docs push and passed at `ae23bc9e`.

| Workflow | Result |
| --- | --- |
| [Final multi-system campaign #40978161099](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40978161099) | 5/5 jobs: pure **46/46**, installed **7/7**, adjacent **3/3**, compatibility **18/18** (14 earlier + 4 refill), restart **3/3** phases. **74/74 tests.** Restart evidence unchanged: 1060 → 1290 → 1350 s, 18 → 87 → 105 kg |
| [Seeded endurance #40978161101](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40978161101) | Success |
| [808 equipment-family audit #40978162517](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40978162517) | Success, with the 349/159/300 tiers |
| [Electrical power and protection #40978161494](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40978161494) | Success |
| [Installed hull restoration #40978161195](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40978161195) | Success |
| Documentation consistency and fast PR gate at `ae23bc9e` | Success |

The supplementary local run of all 137 test modules at `7071f815` completed: 915 tests, one failure (the stale `test_ship_world` assertion, fixed in `8802f8c3`), and all three restart phases passed.

### PR review notes (non-blocking)

- `CanonicalShipAccess` exits move from `traverse:perm(Developer)` to `traverse:all()` with crew gating in `at_traverse`. Existing worlds upgrade correctly: the builder re-applies the lock and `ensure_canonical_ship` rebuilds if the first exit is not `live_world_gated`. The check samples one exit; a partially upgraded world is still caught because the builder rewrites every exit.
- No migrations are added; `0015_full_ship_state` predates the PR.
- `continuous_ship_physics.py` grows to 11,967 lines (+11,155). Split it along the existing pure-module seams after merge.
- `oxplant` usage text omitted the accepted `cabin_air` and `rescue_air` actions; fixed in `7071f815`.

## 6. Deferred, non-blocking

| Item | Why it can wait |
| --- | --- |
| Routine inert make-up (`INV-INERT-MAKEUP-A/B`, mixers, inert regulators) | No routine leakage is simulated, so the 7 t stock has nothing to replace yet. Implement together with routine leakage. Casualty refill (B1) is separate and done. |
| Direct refill taps for 56 cells | The design gives bridges, drum galleries and locks, hubs, indexers and workshop-rotor cells no tap; they refill by equalisation through rated hatches from a served neighbour. |
| Cabin emergency scrubbers (8) and oxygen banks (10) | Not simulated; refuge packs, portable scrubbers and suits cover the crew-survival path that is tested. Needed before long ECLSS-blackout scenarios. |
| Generator-room local fire suppression (`SUPP-GEN-*`, 9 units) | Fire is modelled only in the 133 pressure cells; the generator enclosures are not among them, so these units have no fire to act on. |
| Bow debris radar, dust ionizer, field coils | Navigation-hazard simulation is outside G19. |
| Personnel carts, freight sleds, parts-wash water unit, WR-01 trim | Interface-tier hardware; owning operations are exercised. |
| 40-crew voyage | Excluded from this round by owner decision. |
| Autonomous crew on the full ship | Next stage (crew intelligence, GOAP, missions). |

## 7. Evidence limits

- GitHub Actions results for `c56990c` were not read in this audit. Local runs used the workflow commands on Python 3.12 with SQLite in-memory test databases. Run the workflows on the final head before merging.
- The audit reproduces tests; it does not certify physical realism beyond the game-world contract in `G19_FULL_SHIP_SYSTEMS_COMPLETION.md`.

## 8. Path to merge

1. ~~Push the B1 fix and documentation to PR #138.~~ Done: `7071f815`, `ae23bc9e`.
2. ~~Confirm the G19 workflows green on the pushed head.~~ Done; see section 5.
3. ~~Mark PR #138 ready and merge.~~ Done. Leaving draft ran the 43 draft-gated workflows for the first time, and a full local run of all 137 test modules had already found the one stale assertion they would have hit (`test_ship_world` still expected Developer-only exits); it was fixed in `8802f8c3`. Merged as `d7fc201d`, whose tree is identical to `8802f8c3`.
4. ~~Run `ox-ship-world`, `ox-continuous-ship-physics` and the final campaign on `main`.~~ Done: all 28 workflow runs on `d7fc201d` succeeded, including the dispatched [final campaign #40989739818](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40989739818), G18 continuous physics and the spaceship game tests. **G19 is closed.**

## 9. Post-merge targeted fuzzing (30 October 2026)

A seeded fuzzing campaign after merge found one High-severity defect that the acceptance tests could not see: crew physiology used a different gas heat capacity from the physics clock, so every occupied cell lost about 0.4 K at each tick boundary (mass was conserved, so the gas balance check passed). It is fixed, with a source-level regression guard. Open hardening items (a misplaced character halting the clock, and bounds and type checks on persisted stocks and interlock state) are listed with recommendations in the [fuzzing campaign report](G19_FUZZ_CAMPAIGN_2026-10-30.md). None is reachable by crew actions.

