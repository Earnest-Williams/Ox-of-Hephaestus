# G19 targeted fuzzing campaign — 30 October 2026

**Scope:** the G19 full-ship systems after merge of PR #138: the casualty-refill kernel, the installed physics clock, the crew action dispatcher and persisted ship state.
**Method:** seeded, replayable fuzzing in the repository's existing style (`random.Random` seeds, labelled steps, real Evennia operations, no mocks). Every failure names its seed and step. `OX_FUZZ_SCALE` multiplies trial counts.
**Harnesses:** `game/world/tests/test_g19_refill_fuzz.py` (pure), `game/world/tests/test_installed_ship_g19_fuzz.py` (installed), `game/world/tests/test_ship_heat_capacity_consistency.py` (regression guard). CI: `.github/workflows/ox-g19-fuzz.yml`.

## Summary

| # | Target | Kind | Result |
| --- | --- | --- | --- |
| F1 | Refill ledger | Pure, model-based | Pass at 50× scale: 80,000 random start/record/stop operations match a shadow model exactly |
| F2 | Refill metering | Pure, property | Pass at 50×: 400,000 cases never exceed rate, stock or setpoint |
| F3 | Refill routes on the real v0.5 graph | Pure, differential | Pass at 50×: 30,000 random lineups and all 143 single-valve lineups match an independent union-find oracle; opening never removes and failure never adds cells |
| F4 | Tick chunking | Installed, differential | **Finding F4-1 (High), fixed.** Pass after fix at 3× scale |
| F5 | Crew action sequences | Installed, stateful | Pass at 3×: 360 steps, 115 successes, 96 refusals, 56 replays, 21 ID collisions, 72 ticks. **Finding F5-1 (Medium), open** |
| F6 | Persisted-state corruption | Installed, exploratory | 332 corruptions classified. **Findings F6-1 to F6-3 (Medium/Low), open** |

**Fuzzer sensitivity.** Three bugs were planted in the refill kernel: metering ignoring the setpoint, routes ignoring failed equipment, and the ledger accepting over-delivery. The first two are caught. The third survives only because the ledger enforces the bound twice; with the first check removed the code still behaves identically, so there is nothing for the fuzzer to find. The setpoint mutant was missed by the first version of F2, which now biases half its cases to within two metering steps of setpoint.

## Findings

### F4-1 (High, fixed): occupied cells lose heat at every tick boundary

**Symptom.** Advancing the same interval in different 10-second-aligned tick splits gave different ship states. In a quiet ship (no casualties, no refill) `PZ-HUB-SVC` was 0.39 K colder after two 10 s ticks than after one 20 s tick. After a one-hour warm-up at 60 s ticks it had fallen to about 266 K with nothing happening, and about 1.2 % of its gas had moved to its neighbours. Mass was conserved to 10⁻¹² kg, so the gas balance check could not see it.

**Isolation.** The effect was present with and without the B1 refill code and without any casualties. It followed the crew member: moving the only commissioned crew member from `ENG-CONTROL` to `CMD-PRIMARY` moved the cold spot from `PZ-HUB-SVC` to `PZ-BOW-CMD`.

**Root cause.** `ship_crew_physiology.py` recomputed the occupied cell's temperature with `GAS_CP_KJ_KG_K = 1.005`. The physics clock defines cell energy as `(capacity + mass · 1.0) · T` and rebuilds it from the stored temperature every tick. Each physiology step therefore wrote back a temperature about 0.4 K low, and the next tick turned that into lost energy. More tick calls meant more loss. `ship_eva_operations.py` had the same mistake inline (`mass * 1.005`) when rebuilding airlock-cell energy after a pump cycle.

**Fix.** Both modules now use 1.0, matching the clock, with a comment tying them to it. `test_ship_heat_capacity_consistency.py` fails if any module-level heat-capacity constant differs from the clock's, or if a `1.005`, `1.0045` or `0.718` literal appears in world code. It was confirmed to fail on the pre-fix source.

**After the fix,** chunking moves about 10⁻⁷ of a cell's mass and a few milligrams of CO₂, with no temperature difference. That residual is operator splitting: physiology integrates a call's breathing after that call's physics substeps rather than interleaved with them. F4 now asserts 10⁻⁶ relative and 10⁻⁵ kg absolute, and excludes only the per-call bookkeeping (`ticks`, `summary`, `instrumentation` sampling).

### F5-1 (Medium, open): one misplaced character stops the whole clock

If a commissioned, unsuited crew member stands in a room with no pressure cell (for example `STORE-FLUID-AFT` or a generator enclosure), every physics tick raises `Unknown life-support envelope at crew position`. The entire ship's physics stops until that character is moved.

Gated traversal requires a suit for those rooms, so ordinary play cannot cause this. An operator teleport, the Developer `board ox` path, or a future access bug can. Failing closed is the intended behaviour for that character, but halting every other system is disproportionate.

**Recommendation:** treat that character as in an unknown, non-breathable envelope (no gas exchange, exposure accrues, an alarm is raised) and let the rest of the ship advance.

### F6: single-field corruption of persisted state

Each trial corrupted one field (NaN, infinity, negative, a 10³⁰ value, a string, `None`, a dropped key or an extra key) in the live clock ledgers, a pressure cell or an inventory row, then ran one tick inside a savepoint.

| Outcome | Count | Meaning |
| --- | ---: | --- |
| Rejected | 153 | Graceful `PhysicsError` / `ValueError`: fails closed |
| Rejected by storage | 67 | SQLite refuses NaN/infinity in JSON fields |
| Accepted, then overwritten | 34 | Recomputed by the tick; harmless |
| Crashed | 22 | `TypeError` / `KeyError` mid-tick; rolled back atomically, so still fails closed, but not gracefully |
| Accepted and persisted | 56 | The corruption survived a tick |

No crew action can produce these states (F5 holds every invariant under random crew actions). They matter for operator scripts, migrations and future bugs.

- **F6-1 (Medium): stock and meter bounds.** `INV-WATER-NORMAL` and `INV-SPARES` accept 10³⁰ t, `INV-REACTION` accepts infinity and `INV-FTL-FUEL` accepts `None`. Electrical meters accept absurd stored energy, and ship velocity accepts 10³⁰ m/s. The tick rejects negatives and some infinities but checks no upper bounds. The refill banks reject every corruption, because B1 reconciles them against the ledger each tick. **Recommendation:** per-stock physical maxima (authored nominal mass) and ledger reconciliation for every consumed stock.
- **F6-2 (Medium): interlock state types.** A drum's `hardlock`, `brake`, `indexing` or `freight_collar` set to `None`, and `drive_condition` set to an arbitrary string, are accepted. A `None` hardlock reads as false and could defeat a rotor or freight interlock. **Recommendation:** validate rotor and motion state with the same strict key-set and type checks the hull and refill ledgers use.
- **F6-3 (Low): schema strictness and error quality.** Unknown extra keys are accepted in pressure-cell details, rotors, water, cargo and electrical ledgers, and 22 corruptions crash with `TypeError` / `KeyError` rather than a `PhysicsError`. **Recommendation:** strict key sets and numeric coercion in each ledger's validator.

B1 hardening from this campaign: a missing or non-numeric `scenario_initial_pressure_pa` now refuses a refill start with a `PhysicsError` instead of a `TypeError`.

## Reproduce

```bash
cd game
python -m unittest world.tests.test_g19_refill_fuzz world.tests.test_ship_heat_capacity_consistency -v
OX_FUZZ_SCALE=50 python -m unittest world.tests.test_g19_refill_fuzz
python -m world.test_runner world.tests.test_installed_ship_g19_fuzz --verbosity=2
OX_FUZZ_EXPLORE=1 OX_FUZZ_REPORT=/tmp/f6.json \
  python -m world.test_runner world.tests.test_installed_ship_g19_fuzz.PersistedStateCorruptionFuzz
```

F4 diagnostics: `OX_FUZZ_F4_SCENARIO` (`full`, `quiet`, `quietwarm`, `norefill`, `refillonly`), `OX_FUZZ_F4_TOTAL`, `OX_FUZZ_F4_CHUNKS` (for example `60,60`), `OX_FUZZ_WARMUP`, `OX_FUZZ_WORKER_ROOM` and `OX_FUZZ_DIFF_DUMP` (write every difference to a file).
