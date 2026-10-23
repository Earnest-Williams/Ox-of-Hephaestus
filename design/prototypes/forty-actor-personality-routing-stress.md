# Forty-character personality routing checkpoint stress

This is **not** a 40-character Evennia world or 40 local model agents.
The G10/G11 experiments separately covered 216 native Decider decisions and
three real 205-turn Evennia voyages. The scaling test isolates the *routing
ledger*, because it must work independently for more than six live crew.

The offline test creates 40 distinct validated 12-dimensional character
profiles, each with a different authenticated-character-shaped DBREF, history,
and pseudorandom route seed. It exercises **512 independent boundary keys per
character**, spanning routine, ambiguous, social, and urgent conditions.
Each select commits its actor-specific route via the callback before returning.

The script then verifies:
- Every one of the **20,480 unique boundaries** was persisted exactly once.
- All 40 histories survive JSON serialization and reconstruction.
- All 20,480 historical decisions survive reversed-order restart without
  rerolling, even when the supplied personal state and cognition revision
  change on replay.
- A new router given the exact same seed/blueprint/boundary keys in reverse
  evaluation order makes the same choice, ruling out use of a process-global
  Python random sequence.
- Attempts to rebind each ledger to a different character ID, different
  personality blueprint, or changed routing seed are rejected (**120
  negative cases**).
- One deliberately failed storage persistence callback rolls back its newly
  selected boundary instead of pretending the outcome was checkpointed.
- Two internally varied groups (20 procedurally inclined and 20
  improvisation-oriented) have substantively different *configured*
  Decider-consultation rates, not forced right/wrong choices.

Importantly, this is a deterministic engineering stress test and should
never be presented as 20,480 **native model** decisions. It invokes
**zero** native Decider calls and sends **zero** actual world actions.
The meaningful Decider behaviour and actual world consequences remain in
G10/G11. Its report is produced as a downloadable CI artifact.

## Verified run, 2026-10-23

[GitHub Actions evidence run #39884678442](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39884678442) passed its router stress, existing personality regression and schema checks.

| Observed measurement | Actual value |
| --- | ---: |
| Distinct character personalities | 40 |
| Fresh checkpointed route boundaries | 20,480 |
| Exact replayed boundaries after checkpoint | 20,480 |
| Identical routes despite reversed evaluation order | 20,480 |
| Persist callback invocations | 20,480 |
| Per-character JSON durability snapshots | 320 |
| Actor/profile/seed rebind refusals | 120 |
| Injected storage-persist failures rolled back | 1 |
| GOAP routes selected | 12,697 |
| Decider consultations *scheduled* | 7,783 |
| Mean consultation rate, procedure-oriented group | 10.3223% |
| Mean consultation rate, independent group | 65.6836% |
| Actual native Decider model calls | **0** |
| Actual Evennia commands | **0** |

The combined policy rate is a configuration property under the selected
controlled stress/uncertainty settings, *not* empirical human behaviour.
