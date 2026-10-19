# G4d - Canonical skill authority and read-only task calibration

**Status:** implementation PR on top of merged G4a/G4b/G4c. These notes describe the intended code path, not test evidence until the final-head CI finishes.

## Responsibilities changed

1. The captain's optional firsthand bridge diagnostic qualification now reads the authoritative `CharacterSkill` record for `investigation.instrument_analysis` with minimum **40/100**, preserving the old `diagnostics >= 2/4` intent. The captain's normal initial skill remains **20/100**. Command authority alone cannot pass a technical qualification.
2. The `can_personally_inspect` notification and the actual command validation call the **same world-owned predicate**. AI beliefs, ordinary character speech and old Evennia `ox_skills` keys cannot confer qualification. Locality, role, ticket, and verified work receipt rules remain independent and fully enforced.
3. Bootstrap now seeds the six *persons* by their existing `person_id`, using explicit canonical 0-100 values rather than deriving abilities anew from their current roles. Existing `CharacterSkill` rows always win; role changes never grant competence. Values preserve the G3f->G4b historical 0-4 conversion without retaining 0-4 gameplay mechanics.
4. A pre-G4d world may still contain the Evennia attribute `ox_skills`. The authoritative world bootstrap performs a one-time import (including personally modified coarse values when skill records are absent), creates any missing canonical skill rows, then removes the obsolete Evennia attribute **in the same transaction**. Repeated bootstraps do not re-seed advanced skill values. Historical conversion helpers remain in `skill_catalogue.py` solely for migration/testing.
5. The obsolete `world/crew_competencies.py` module has been deleted. There is no live 0-4 policy reader after this change.

## Shadow-only task evaluator

`world/task_resolution.py` introduces immutable task metadata for familiar servicing, unfamiliar repairs and novel scientific diagnosis. It accepts individual:
- practical skill (0-100)
- conceptual knowledge (0-100)
- relevant formative aptitudes (1-10, including **Dexterity distinct from Agility**)
- equipment/procedure familiarity (0-100)

Preliminary weight profiles are:

| Work profile | Skill | Knowledge | Aptitude | Familiarity |
| --- | ---: | ---: | ---: | ---: |
| Routine | 65% | 15% | 15% | 5% |
| Unfamiliar repair | 60% | 15% | 20% | 5% |
| Novel investigation | 35% | 25% | 35% | 5% |

A novel task also defines a prerequisite theoretical foothold. High reasoning cannot invent missing knowledge. The output contains only a provisional relative score, comparison margin and knowledge-footing flag; it is **never a probability, eligibility grant, diagnosis, random roll or physical outcome**.

`world/task_shadow.py` may compare authoritative crew records **only from server/operator context**. It uses an explicitly named same-foundation practical-skill proxy for conceptual knowledge because the independently verified knowledge ledger does not exist yet, and defaults equipment familiarity to zero because its ledger does not yet exist. The routine/novel weighting and differential are test hypotheses, not validated human psychometrics.

## Absolute safety and epistemic boundaries

- No normal Ox command or agent/OOB capability exposes the evaluator, task difficulties, score or world-secret cause.
- No physical machine state, supply record, work receipt, skill XP, clock, personnel state or character memory is written by a shadow evaluation.
- A qualified captain still needs actual bridge presence and an open case. No broad rank-based diagnostic grant.
- The existing G3e hidden-cause measurements are still sampled by their actual world rules, unaffected by this model.
- Multiple distinct real physical operations and failure consequences are **future task-resolver work**. This is strictly a comparison/calibration slice.
- The initial six people still have neutral, unproven aptitude profiles; the gifted-veteran experiment uses labelled synthetic candidates rather than fabricated biographies.

## Tests and progression gate

- World skill substitution, legacy-attribute spoofing, fresh bootstrap and one-time legacy conversion.
- Safe repeated bootstrap after independently changing world skill and aptitude values.
- Deterministic matched-skill novice/veteran/routine/novel comparisons with no random calls.
- Strict score and task validation; a missing conceptual foothold remains missing.
- Shadow world comparison leaves physical state, work receipts, and private crew events unchanged.
- Existing full captain, cargo, life support, inventory, navigation, zero-inference idle, multi-client and PostgreSQL regressions.

**Next:** model evidence-backed theoretical knowledge and learned equipment procedures; compare shadow predictions against real task attempts; then introduce authoritative graded outcomes under an explicit opt-in equipment integration, one fixture at a time, preserving existing safety and idempotent world receipts.
