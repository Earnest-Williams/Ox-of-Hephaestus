# G4e — Independent theoretical knowledge and personal machine familiarity

**Scope:** Adds world-owned theoretical foundations and procedure/equipment familiarity to the six-person Ox character system, without changing any physical task outcomes, authorisation rules, AI memory, or crew autonomy.

## Separation of responsibilities

| Character dimension | Meaning | Canonical record | Example |
| --- | --- | --- | --- |
| Practical skill | Demonstrated or estimated ability to perform a professional technique | `CharacterSkill` | Pump servicing |
| Theoretical knowledge | Subject-specific concepts and ability to apply them | `CharacterKnowledge` | Rotating machinery principles |
| Equipment/procedure familiarity | Experience with a particular method on specific equipment | `CharacterTechnique` | P-01 routine service |
| Formative aptitude | Slow-changing potential and cognitive/physical disposition | `CharacterProfile.aptitudes` | Reasoning or fine-motor Dexterity |
| Psychological disposition | Tendencies affecting decisions, not task authority | `CharacterProfile.psychology` | Persistence |

The first three dimensions are **independently persistent**. A character can be highly skilled but lack a particular theoretical foundation, know relevant principles without practical experience, or be expert on one pump but unfamiliar with its other procedures. Higher Reasoning cannot create a foundation record; a professional job title cannot update any of them.

## Data and migration

- Migration `world.0009_knowledge_technique` adds `CharacterKnowledge(person, foundation_id, mastery 0–100, source, first_recorded_game_time)` and `CharacterTechnique(person, technique_id, familiarity 0–100, source, first_recorded_game_time)`.
- Both have database-enforced per-person unique keys and bounded numeric scores.
- `world.technique_catalogue.TECHNIQUES` gives each procedure a stable versionable ID, actual fixture marker, and relevant professional skill. Routine P-01 servicing, unfamiliar P-01 repair and P-01 vibration-analyser investigation deliberately use **different** technique IDs even though the equipment is shared.
- `world.crew_initial_learning` contains distinct starting records for the six **specific people**, based conservatively on their already-established duties and competency sketches. All seeds retain `source=g4e_initial_estimate`; **they are calibration assumptions, not verified training, qualifications, educational histories, or gained XP**. Do not retcon formal qualifications from these values.
- The world bootstrap `get_or_create` backfills only missing records and never overwrites progression, later source provenance, current roles, attributes, injuries, or individual technique learning. No new Evennia `.db` state is needed; canonical data goes into Django tables.

## Shadow task resolver changes

- `TaskDefinition.technique_id` binds task familiarity to an exact canonical procedure and validates it against the task's primary skill.
- `evaluate_world_shadow` reads `CharacterKnowledge` for the skill's declared foundation and `CharacterTechnique` for that task's procedure. It **never** infers knowledge from high practical skill, sums related skills, or treats familiarity with a different procedure as equivalent.
- If a record is absent, its value is zero and provenance is `not_recorded`. A zero is **not** necessarily ignorance in the character's beliefs; it means there is no authoritative competence record for that component.
- World projections report their record `source` as `knowledge_source` and `familiarity_source`, so authored starting estimates cannot be passed off as measured learning.
- These scores and task benchmark metadata remain **server/operator-private** and do not appear in `oxcapabilities`, ordinary world commands or Concordia observations.
- A knowledge prerequisite/floor remains a separately testable shadow finding, **not** a hidden fact disclosure or automatic live work block. Physical outcomes, world work receipts and the captain qualification check are unchanged.

## Framework reduction and migration safety

Evennia remains the movement/room/lock/session engine. The character's conceptual knowledge and machine familiarity are *not* stored in generic Evennia `Attribute` bags or a new role/level system. No additional stock gameplay commands are enabled. This prevents the second parallel authoritative competency system previously retired by G4d.

## Acceptance tests

- All 6 people receive individually scoped foundation and technique records; initial values remain explicitly estimates.
- A high-skill, high-Reasoning character can lack a necessary theoretical foothold.
- Equal practical proficiency and aptitudes can yield different shadow scores from theory alone or familiarity alone.
- Experience on P-01 routine servicing does not grant automatic familiarity with P-01 unfamiliar repairs.
- A captain's high knowledge/familiarity does **not** confer the separate world-owned 40/100 diagnostic qualification.
- Repeated bootstrap neither re-seeds developed records nor changes duties/roles/positions.
- Unique keys and numeric bounds are enforced by the database; no learning values leak through local capabilities.
- Existing work receipts, captain obligations, hidden-cause epistemics, long voyages and live multi-actor transport remain regression gates.

## Next dependency

**G4f: verified work and instruction evidence.** Introduce an append-only experience ledger tied to consequential `WorkReceipt` and task identity, with no duplicate credit from retries. Only then should a successful task, a failure followed by verified correction, or actual instruction change numerical knowledge, practical skill or familiarity. Physical task-resolution changes should remain feature-gated until calibration and receipts are verified.
