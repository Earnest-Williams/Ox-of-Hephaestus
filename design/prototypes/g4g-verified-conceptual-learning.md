# G4g — Verified conceptual learning

**Scope:** One world-owned, supervised course with an independently graded
transfer exercise. This extends G4f's learning evidence without changing
physical task outcomes or scheduling autonomous education.

## What is verified

The first curriculum is `mechanical.controlled_comparison.v1`, teaching
controlled comparisons of shaft speed, drive-bus loading and vibration. It
develops the `mechanical.rotating_machinery` theoretical foundation. The
exercise uses freshly generated, idealised **training measurements**. They
are separate from actual ship instruments, uncertain investigation cases,
hidden fault causes and character hypotheses.

The world can verify the following activity:

1. A separately identified instructor offers the authored course to a
   separately identified learner. Both bodies must be at the Machine Shop
   bench. An offer does not enrol its recipient or grant credit.
2. The learner accepts the specific offer. The instructor needs at least
   60/100 conceptual mastery and at least ten points more than the learner.
   The course teaches only below 70/100. Job title, practical repair skill,
   self-description and a command order cannot meet these requirements.
3. The world records the participants, curriculum version, qualification
   snapshot, room, start, earliest assessment time and expiry. It delivers
   instruction and a new exercise privately to the learner. Both people
   must remain at the bench; ordinary movement by either interrupts the
   lesson, and returning cannot restore it.
4. After fifteen game minutes, the learner names the factor supported by
   the measurements and the factor held fixed. A comparison in which both
   changed requires acknowledging insufficient evidence. The rubric stays
   world-private. The instructor's presence and qualification are rechecked.
5. A correct assessment produces one bounded conceptual-study credit.
   Incorrect answers consume that assessment and produce an auditable
   failed lesson, with no learning credit or disclosed answer key.

The instruction text is authored; the instructor's generative teaching
quality is not evaluated here. Passing verifies the narrow authored transfer
exercise, not an unrestricted claim about understanding or a real fault's
cause. `command.instruction` is not yet used to grade teaching quality.

## Persistent authority and progression

Migration `0011_concept_lessons` adds `ConceptLesson` and independent
`CharacterKnowledge.study_progress`. It preserves existing skill, technique,
knowledge, person and evidence records with zero initial study progress.
The existing `source` field continues to describe a score's initial origin;
earned changes are attributed by the append-only evidence, not by rewriting
an estimated starting history as verified education.

`ConceptLesson` records the actual activity, private exercise/rubric,
submitted answers, result event and completion receipt. The existing
`CharacterLearningEvidence` records the learner, foundation, course identity,
receipt, source activity, credit, and score/progress before and after. Joining
that evidence to its lesson preserves the instructional identity and activity
without duplicating another authoritative learning system.

Each passed session earns one study unit, subject to G4f's increasing
4/7/12/20/30-unit thresholds for the next mastery point and at most three
credited events per foundation per game hour. The same course additionally
requires **one game day between completed assessments**, successful or
unsuccessful. Fresh request IDs cannot bypass either rule. The course's
70/100 ceiling prevents elementary instruction from training expert mastery.
At the ceiling, excess progress is cleared.

Practical proficiency, machine/procedure familiarity, formative aptitudes,
psychological dispositions, duties, safety permissions and equipment state
receive no lesson credit. A theory point can affect an existing operator-only
unfamiliar/novel task comparison; those shadow scores still do not decide live
repair success or authorize equipment operation.

## Requests, replay and privacy

The existing authenticated `oxwork` command and handler `DurableEvenniaPort`
support three typed activities:

~~~text
oxwork <request-id> lesson_offer learning mechanical.controlled_comparison.v1 <learner-dbref>
oxwork <request-id> lesson_begin learning <lesson-id>
oxwork <request-id> lesson_answer learning <lesson-id> <supported-factor> <controlled-factor>
~~~

The lesson ID is the instructor's offering work request ID. Answer choices
are `drive_bus`, `speed`, `insufficient_evidence`; controlled-factor choices
are `drive_bus`, `speed`, `none`. Clients cannot supply mastery, credit,
instructor qualification, evidence events or a grading rubric.

All lesson stages use the existing common ship lock and global actor-bound
`WorkReceipt` namespace. The assessment, participant notifications, receipt,
study progress and learning evidence commit or roll back together. An early
or unauthorized request remains refused under its original ID. Once an
assessment is consumed, a new ID cannot resubmit it; another receipt cannot
recredit the same activity. Recovery queries `oxworkreceipt` using the
original pending ID.

A successful *submission receipt* means the assessment was performed. It
does not itself mean the answers were correct: the learner's addressed
`lesson_assessed` event reports `passed` or `failed`. The instructor receives
the outcome without the learner's private numerical competence. No other
crewmember receives either person's lesson observations. The world record
is not automatically imported as the character's belief or self-assessment.

Offers expire after one game hour; accepted lessons expire after two game
hours. A participant cannot take part in two active lessons at once. Stale
records remain for audit, but do not reserve people forever.

## Verification

The focused world suite covers all three generated exercise variants,
consent, timing, identity, subject qualification, theoretical ceilings,
spacing, replay, foreign receipts, movement interruption, hidden-case
non-disclosure, bootstrap preservation and complete rollback after a
learning-writer failure. It also demonstrates a real mastery gain at a
threshold and its transfer to a novel-task shadow without practical gains.

[`ox-g4g-concept-learning.yml`](../../.github/workflows/ox-g4g-concept-learning.yml)
adds an independent real-server gate: ordinary Iona/Ari accounts meet and
begin a lesson over separate authenticated WebSockets, the world restarts,
the learner completes the assessment, a new client process reconciles a
deliberately forgotten ACK, and an independent world read proves exactly
one persisted conceptual credit. A separate opt-in CI settings file runs the
game clock at 60×; the normal game and curriculum duration are unchanged.
The probe solves only the learner's delivered measurements. It is an authored
acceptance policy, not an LLM reasoning benchmark.

**Remaining:** evidence-backed learning from real investigations, additional
curricula and teaching-quality effects, autonomous study agendas, and typed
graded physical task attempts. Ordinary repairs, reports, speculation,
hearsay and agreeing with a world-secret answer do not acquire theory XP.
