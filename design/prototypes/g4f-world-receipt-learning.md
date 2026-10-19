# G4f — World-receipted practical experience

**Status:** stacked implementation on G4e. The entire learning hook is Evennia/world-owned. Autonomous crew control, personality, hidden facts, ship permissions, physical transitions and existing work request/receipt formats remain unchanged.

## What now develops

The first real (not shadow) experience mechanism can update:

- **Practical skill:** `CharacterSkill.proficiency` with a separate `practice_progress` counter.
- **Exact machine/procedure familiarity:** `CharacterTechnique.familiarity` with its own independent `practice_progress`.

It deliberately **does not** update theoretical knowledge `CharacterKnowledge.mastery`, formative aptitudes, injury conditions, psychological traits, beliefs, or permission checks from a generic physical repair. A crewmember must obtain independently validated educational or investigative evidence for conceptual learning in a later slice.

## Eligibility and causation

A world-created successful `WorkReceipt`, committed via `world.work_actions.execute_work`, is the *only* ordinary source of practice. The first conservative whitelist is:

| Durable target and operation | Task | Practical component | Specific familiarity |
| --- | --- | --- | --- |
| `pump / repair` | `pump.routine_service` | `mechanical.pump_service` | `pump.p01.routine_service` |
| `cargo / restow` | `cargo.restow` | `freight.cargo_rigging` | `cargo.c01.restow` |
| `scrubber / replace` | `environment.scrubber_service` | `environmental.atmosphere_maintenance` | `environment.a01.scrubber_service` |

All require a world-authorised physical transition reporting `status=succeeded`, `reason=transition_applied`, a physical source event ID and a receipt whose actor matches. Failed authorisations, rejected commands, inspections, social hails, delegation and ordinary reports earn nothing. Unknown visitors without a person record cannot magically gain an identity or proficiency.

No agent can submit `learning_credit` as an action, specify a score, or supply a fabricated source event to an Ox command. This function is invoked inside the existing world transaction after a successful durable receipt is written.

## Evidence and anti-replay

Migration `0010_learning_evidence` adds:

- `CharacterLearningEvidence`: append-only world-owned provenance keyed uniquely by person, work receipt, component type and topic; a second uniqueness constraint blocks another receipt for the same physical event and topic.
- Persisted `practice_progress` on skills and techniques, independent of their starting score.
- Credited units (0/1), before/after score and progress, source event, exact task and world game time.

Retries of an original `request_id` exit before practice processing. A new request wrapping an already credited physical `event_key` is also refused credit. If the world effects, credit or receipt cannot all commit, the database transaction rolls back together. The old event/receipt APIs remain compatible.

## Conservative progression rate

Each genuinely completed eligible action yields one unit of practice per corresponding component, subject to a maximum **three credited repetitions of the same subject in one game hour**. Further legitimate tasks within that hour are still recorded as evidence with zero credit.

The score threshold per one-point gain increases with current proficiency:

| Current score | Credits for next point |
| --- | ---: |
| 0–24 | 4 |
| 25–49 | 7 |
| 50–74 | 12 |
| 75–89 | 20 |
| 90–99 | 30 |
| 100 | No increase |

This is a first calibration, **not** a claim about empirical learning rates. It discourages grinding but does not make high-skill workers incapable of improving. Gained practice never confers safety authorisation, rank, or access by itself; those remain independent checks.

## Why no failure XP yet

The present work receipt `failed` status includes *world-refused* operations—wrong location, invalid equipment state and lack of authority. It cannot reliably distinguish an actually attempted mechanical procedure from an invalid command. Awarding experience for that status would reward invalid submissions.

A subsequent task-result schema must distinguish **refused**, **physically attempted and failed**, **partially executed**, and **success with quality penalties** before failed work can confer any learning credit. It must also verify whether the character actually learned from the error.

## Framework reduction

No skills, levels, experience points or machine familiarity are stored in generic Evennia object attributes or user-editable descriptions. These records use the single existing Ox world ORM and work-receipt system. No duplicate alternate learning engine or client-provided XP authorisation is created.

## CI gates

- Actual pump work grants precisely two appropriate evidence records; isolate and routine reports grant none.
- Duplicate request, new request carrying the same physical source event, missing/foreign actor, wrong duty and world refusal cannot mint extra experience.
- Skill and technique practice independently accumulate toward a bounded score increase, with diminishing returns for repeated work.
- Work rollback also rolls back new receipt and progression. No theory or psychology changes from generic repairs.
- Existing character identity migrations, rate limits, long-voyage concurrency, cargo/environment stock conservation, captain obligations, epistemic privacy and real authenticated multi-actor workflows remain intact.

**Next:** equipment-specific graded outcomes after shadow calibration, earned theoretical knowledge from verified inquiry and real instruction, and attribute changes arising from documented experiences—not invented by the LLM.
