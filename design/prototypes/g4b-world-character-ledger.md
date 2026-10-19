# G4b - World-owned crew identities and granular competencies

**Status:** implementation PR stacked on G4a (#55). World facts remain Evennia-owned; no simulation behavior or LLM decisions changed in this slice.

## Scope

1. Six existing, distinct people have permanent `person_id` identities, bound to their existing Evennia character DBrefs. This identity is **not** role, watch, current job, nickname or agent identity.
2. `CharacterProfile` stores exactly twelve formative aptitudes (1-10) and twelve OCEAN/Ox psychological dimensions (0-100); the initial six people have deliberately **neutral** values because no authored personal histories have been accepted. No invented individual history is produced by bootstrap.
3. `CharacterSkill` has one row per (person, canonical skill), immutable provenance for its starting value, proficiency 0-100 and an indexed unique constraint. The first catalogue contains **55 skills in sixteen disciplines**, with stable IDs and foundation/aptitude metadata. A later stage adds practical technique history and theoretical understanding.
4. Convert existing G3f 0-4 **estimates** using 0->0, 1->20, 2->40, 3->60, 4->80 for a narrow explicit crosswalk. When two broad competencies seed the same new skill, choose the maximum. The resulting world-owned records do **not** retroactively assert that the person has demonstrated that exact technique.
5. Bootstrap is idempotent: never rewrite identities, aptitudes, psychology, moved character locations, job assignments, or previously modified skill values. Reject a marker tied to the wrong character and DB-level duplicate person/skill bindings.
6. No character, handler, LLM or recruitment profile can directly set authoritative proficiency through an ordinary command. There is intentionally **no character-sheet or remote profile query** in this slice; self-assessment and employer opinions will be separate actor-scoped observations.

## Authority boundary

Evennia owns character identity, aptitude records, competency values, effective task results and physical receipts. Concordia retains private knowledge, plans and judgments about personal ability. A starting profile is never an authorisation. Changing a crew role must never change the person's underlying competence. The original captain command and independent investigation flows remain intact.

This slice is **storage and initial data only**. A high score here does not yet make an operation succeed or enable an inspection. Existing G3f diagnostic qualification currently still reads `actor.db.ox_skills["diagnostics"]` and stays authoritative until the focused gate migration. Do not claim two simultaneous mechanic implementations are a permanent solution.

## Framework reduction

G4a replaced the inherited generic MUD character commands with an Ox allowlist. G4b adds no new stock Evennia character-system dependencies. The next skill-consumer PR should switch captain inspection and subsequent technical checks to one world-owned `CharacterSkill` policy, update the G3f tests, then retire the temporary `ox_skills` vector and source module when every reader is migrated.

We keep Django models, Evennia typeclasses, locks, authenticated command routing and the durable event journal. We do not delete upstream engine files merely because gameplay no longer exposes them.

## Gates

- `python -m world.test_runner world.tests.test_character_profiles world.tests.test_character_command_boundary --verbosity=2`
- `python -m world.test_runner world.tests.test_captain_followthrough world.tests.test_investigation world.tests.test_work_receipts --verbosity=2`
- Check aptitudes and psychological field names against handler G4a blueprint constants.
- Existing ship/Concordia real-world integration, concurrent work, captain obligation and restart tests should remain green.
- An `oxwork` replay cannot generate progress in this PR; progression is a later world-receipted step.

## Follow-up

G4c: migrate actual authority checks to canonical skills; implement a world-owned task resolver in shadow mode, validate routine-versus-novel calibration, and remove the superseded coarse skill access once equivalence is proved. G4d: task receipts, bounded experience gain, training and diminishing returns; later acquired attributes and individual technique histories.
