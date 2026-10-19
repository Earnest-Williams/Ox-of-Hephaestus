"""Supervised conceptual learning requires independent, local world evidence."""

from __future__ import annotations

import json
from unittest.mock import patch

from commands.crew import CmdOxWork
from django.db import IntegrityError, transaction
from world.bootstrap import build_ship
from world.character_profiles import profile_for_actor
from world.concept_learning import (
    COURSE,
    LESSON_LIFETIME,
    OFFER_LIFETIME,
    REPEAT_INTERVAL,
    record_concept_experience,
)
from world.learning import progression_threshold
from world.live_crew import fixture_setup
from world.models import (
    CharacterKnowledge,
    CharacterLearningEvidence,
    CharacterSkill,
    CharacterTechnique,
    ConceptLesson,
    CrewEvent,
    WorkReceipt,
)
from world.task_shadow import evaluate_world_shadow
from world.work_actions import execute_work, work_receipt

from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaTestCase


def solve_exercise(exercise: dict) -> dict:
    """Solve only the delivered measurements, without reading the private rubric."""
    observations = exercise["observations"]
    speed_varies = len({run["shaft_rpm"] for run in observations}) > 1
    bus_varies = len({run["drive_bus"] for run in observations}) > 1
    if speed_varies and bus_varies:
        return {"supported_factor": "insufficient_evidence", "controlled_factor": "none"}
    return {
        "supported_factor": "speed" if speed_varies else "drive_bus",
        "controlled_factor": "drive_bus" if speed_varies else "speed",
    }


class ConceptLearningTests(EvenniaTestCase):
    """Exercise actual lesson work, progression and independent authority boundaries."""

    def setUp(self):
        """Keep a qualified teacher, ordinary learner and controlled world clock."""
        super().setUp()
        fixture_setup(scheduled_clock=True)
        self.ship = build_ship()
        self.teacher = self.ship["chief"]
        self.pupil = self.ship["watch"]
        self.room = self.ship["workshop"]
        self.teacher.move_to(self.room, quiet=True)
        self.pupil.move_to(self.room, quiet=True)
        self.person = profile_for_actor(self.pupil)
        self.instructor = profile_for_actor(self.teacher)
        self.knowledge = CharacterKnowledge.objects.get(
            person=self.person,
            foundation_id=COURSE.foundation_id,
        )
        self.clock = patch("world.concept_learning.gametime.gametime", return_value=100000.0)
        self.time = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.serial = 0

    def _id(self) -> str:
        """Use unique global work IDs for independent attempts."""
        self.serial += 1
        return f"{self.serial:032x}"

    def _work(self, actor, operation: str, arguments: dict, request_id=None) -> dict:
        """Submit a typed request through the production world transaction."""
        return execute_work(
            actor, request_id or self._id(), operation, "learning", arguments=arguments
        )

    def _offer(self) -> str:
        """Have the instructor offer one course without enrolling the pupil."""
        request_id = self._id()
        result = self._work(
            self.teacher,
            "lesson_offer",
            {
                "course_id": COURSE.course_id,
                "learner_dbref": self.pupil.dbref,
            },
            request_id,
        )
        self.assertEqual(result["status"], "succeeded")
        return request_id

    def _begin(self, variant="drive_bus") -> tuple[str, dict]:
        """Accept instruction and read only the learner's public exercise event."""
        lesson_id = self._offer()
        with patch("world.concept_learning.secrets.choice", return_value=variant):
            result = self._work(self.pupil, "lesson_begin", {"lesson_id": lesson_id})
        self.assertEqual(result["status"], "succeeded")
        event = CrewEvent.objects.get(event_id=result["source_event_id"])
        exercise = json.loads(event.details["exercise"])
        self.assertNotIn("expected", exercise)
        self.assertNotIn("mastery", json.dumps(event.details))
        return lesson_id, solve_exercise(exercise)

    def _complete(self, lesson_id, answers, request_id=None) -> dict:
        """Submit a solved assessment after the world-owned duration."""
        lesson = ConceptLesson.objects.get(pk=lesson_id)
        self.time.return_value = lesson.due_game_time
        return self._work(
            self.pupil,
            "lesson_answer",
            {
                "lesson_id": lesson_id,
                **answers,
            },
            request_id,
        )

    def test_offer_begin_and_waiting_alone_never_grant_learning(self):
        """Consent, instruction and elapsed time are distinct from demonstrated understanding."""
        lesson_id, _answers = self._begin()
        self.time.return_value += COURSE.duration * 2
        self.assertEqual(ConceptLesson.objects.get(pk=lesson_id).status, "active")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        self.knowledge.refresh_from_db()
        self.assertEqual((self.knowledge.mastery, self.knowledge.study_progress), (55, 0))

    def test_each_transfer_variant_credits_only_the_conceptual_foundation(self):
        """Variable control and confounding can each be judged from delivered facts."""
        for variant in ("drive_bus", "speed", "confounded"):
            with self.subTest(variant=variant):
                before_skills = list(
                    CharacterSkill.objects.values_list(
                        "person_id", "skill_id", "proficiency", "practice_progress"
                    )
                )
                before_techniques = list(
                    CharacterTechnique.objects.values_list(
                        "person_id", "technique_id", "familiarity", "practice_progress"
                    )
                )
                lesson_id, answers = self._begin(variant)
                result = self._complete(lesson_id, answers)
                self.assertEqual(result["status"], "succeeded")
                lesson = ConceptLesson.objects.get(pk=lesson_id)
                self.assertEqual(lesson.status, "passed")
                self.assertEqual(lesson.instructor_id, self.instructor.pk)
                self.assertEqual(lesson.qualification["instructor_mastery"], 75)
                evidence = CharacterLearningEvidence.objects.get(receipt_id=result["request_id"])
                self.assertEqual(
                    (evidence.component_kind, evidence.component_id),
                    ("knowledge", COURSE.foundation_id),
                )
                self.assertEqual(
                    (evidence.progress_before, evidence.progress_after),
                    (self.serial // 3 - 1, self.serial // 3),
                )
                self.assertEqual(evidence.task_id, COURSE.course_id)
                self.assertEqual(lesson.completion_receipt_id, result["request_id"])
                self.assertEqual(
                    list(
                        CharacterSkill.objects.values_list(
                            "person_id", "skill_id", "proficiency", "practice_progress"
                        )
                    ),
                    before_skills,
                )
                self.assertEqual(
                    list(
                        CharacterTechnique.objects.values_list(
                            "person_id", "technique_id", "familiarity", "practice_progress"
                        )
                    ),
                    before_techniques,
                )
                self.time.return_value += REPEAT_INTERVAL

    def test_earned_mastery_improves_unfamiliar_shadow_without_granting_authority(self):
        """Verified concepts transfer while practical experience and access stay independent."""
        self.knowledge.study_progress = progression_threshold(self.knowledge.mastery) - 1
        self.knowledge.save(update_fields=["study_progress"])
        before = evaluate_world_shadow(self.pupil, "pump.novel_interference")
        baseline = profile_for_actor(self.pupil)
        lesson_id, answers = self._begin()
        self._complete(lesson_id, answers)
        self.knowledge.refresh_from_db()
        self.assertEqual((self.knowledge.mastery, self.knowledge.study_progress), (56, 0))
        after = evaluate_world_shadow(self.pupil, "pump.novel_interference")
        self.assertEqual(after.evaluation.primary_skill, before.evaluation.primary_skill)
        self.assertEqual(after.evaluation.familiarity, before.evaluation.familiarity)
        self.assertAlmostEqual(
            after.evaluation.provisional_score - before.evaluation.provisional_score, 0.25
        )
        current = profile_for_actor(self.pupil)
        self.assertEqual(
            (current.aptitudes, current.psychology), (baseline.aptitudes, baseline.psychology)
        )
        self.pupil.db.crew_role = "captain"
        self.pupil.move_to(self.ship["pump"].location, quiet=True)
        self.assertEqual(execute_work(self.pupil, self._id(), "repair", "pump")["status"], "failed")

    def test_wrong_answer_consumes_assessment_but_does_not_assert_learning(self):
        """A real submitted assessment can complete unsuccessfully with no theory credit."""
        lesson_id, _answers = self._begin()
        wrong = {"supported_factor": "speed", "controlled_factor": "none"}
        result = self._complete(lesson_id, wrong)
        self.assertEqual(result["status"], "succeeded")  # submission was performed
        lesson = ConceptLesson.objects.get(pk=lesson_id)
        self.assertEqual(lesson.status, "failed")
        self.assertEqual(lesson.answers, wrong)
        self.assertEqual(lesson.completion_receipt_id, result["request_id"])
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        retry = self._work(
            self.pupil,
            "lesson_answer",
            {
                "lesson_id": lesson_id,
                "supported_factor": "drive_bus",
                "controlled_factor": "speed",
            },
        )
        self.assertEqual(retry["status"], "failed")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        self.assertNotIn("expected", json.dumps(result))

    def test_early_attempt_is_a_durable_refusal_even_after_time_passes(self):
        """Neither immediate answers nor retrying their refused IDs can teach."""
        lesson_id, answers = self._begin()
        request_id = self._id()
        arguments = {"lesson_id": lesson_id, **answers}
        early = self._work(self.pupil, "lesson_answer", arguments, request_id)
        self.assertEqual(early["status"], "failed")
        self.assertEqual(ConceptLesson.objects.get(pk=lesson_id).status, "active")
        self.time.return_value += COURSE.duration
        self.assertEqual(self._work(self.pupil, "lesson_answer", arguments, request_id), early)
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        self.assertEqual(self._work(self.pupil, "lesson_answer", arguments)["status"], "succeeded")

    def test_same_and_new_request_ids_cannot_recredit_completed_lesson(self):
        """Global receipt replay and the activity identity independently prevent duplication."""
        lesson_id, answers = self._begin()
        result = self._complete(lesson_id, answers)
        arguments = {"lesson_id": lesson_id, **answers}
        self.assertEqual(
            self._work(self.pupil, "lesson_answer", arguments, result["request_id"]), result
        )
        self.assertEqual(self._work(self.pupil, "lesson_answer", arguments)["status"], "failed")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 1)
        self.assertEqual(work_receipt(self.pupil, result["request_id"]), result)
        self.assertEqual(work_receipt(self.teacher, result["request_id"])["status"], "unknown")
        with self.assertRaises(PermissionError):
            self._work(self.teacher, "lesson_answer", arguments, result["request_id"])

    def test_impostor_cannot_accept_or_answer_another_persons_lesson(self):
        """Possession of an activity ID is not learner identity or authorization."""
        lesson_id = self._offer()
        self.ship["cargo"].move_to(self.room, quiet=True)
        result = self._work(self.ship["cargo"], "lesson_begin", {"lesson_id": lesson_id})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(ConceptLesson.objects.get(pk=lesson_id).status, "offered")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)

    def test_teacher_qualification_is_personal_theory_not_rank_or_practical_skill(self):
        """A captain's title and high repair skill cannot substitute for understanding."""
        CharacterKnowledge.objects.filter(
            person=self.instructor, foundation_id=COURSE.foundation_id
        ).update(mastery=59)
        self.teacher.db.crew_role = "captain"
        CharacterSkill.objects.filter(person=self.instructor).update(proficiency=100)
        result = self._work(
            self.teacher,
            "lesson_offer",
            {
                "course_id": COURSE.course_id,
                "learner_dbref": self.pupil.dbref,
            },
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(ConceptLesson.objects.count(), 0)

    def test_theory_gap_self_teaching_and_unknown_people_are_rejected(self):
        """Neither self-certification nor inventing an unregistered learner mints a person."""
        visitor = create_object("typeclasses.ship.CrewCharacter", key="Visitor", location=self.room)
        CharacterKnowledge.objects.filter(pk=self.knowledge.pk).update(mastery=66)
        for target in (self.pupil.dbref, self.teacher.dbref, visitor.dbref, "#999999"):
            with self.subTest(target=target):
                result = self._work(
                    self.teacher,
                    "lesson_offer",
                    {
                        "course_id": COURSE.course_id,
                        "learner_dbref": target,
                    },
                )
                self.assertEqual(result["status"], "failed")
        self.assertEqual(ConceptLesson.objects.count(), 0)

    def test_instructor_and_learner_presence_are_required_at_offer_and_begin(self):
        """Instruction cannot be offered or accepted remotely."""
        self.teacher.move_to(self.ship["pump"].location, quiet=True)
        result = self._work(
            self.teacher,
            "lesson_offer",
            {
                "course_id": COURSE.course_id,
                "learner_dbref": self.pupil.dbref,
            },
        )
        self.assertEqual(result["status"], "failed")
        self.teacher.move_to(self.room, quiet=True)
        lesson_id = self._offer()
        self.pupil.move_to(self.ship["pump"].location, quiet=True)
        self.assertEqual(
            self._work(self.pupil, "lesson_begin", {"lesson_id": lesson_id})["status"], "failed"
        )

    def test_either_participant_leaving_interrupts_and_returning_cannot_resume(self):
        """Normal Evennia movement ends supervision, including leave-and-return attempts."""
        for party in (self.teacher, self.pupil):
            with self.subTest(party=party.dbref):
                lesson_id, answers = self._begin()
                party.move_to(self.ship["pump"].location, quiet=True)
                party.move_to(self.room, quiet=True)
                self.assertEqual(ConceptLesson.objects.get(pk=lesson_id).status, "interrupted")
                self.assertEqual(self._complete(lesson_id, answers)["status"], "failed")
                self.assertEqual(CharacterLearningEvidence.objects.count(), 0)

    def test_expired_offer_and_assessment_are_refused(self):
        """Abandoned offers and stale exercises do not remain valid indefinitely."""
        lesson_id = self._offer()
        self.time.return_value += OFFER_LIFETIME
        self.assertEqual(
            self._work(self.pupil, "lesson_begin", {"lesson_id": lesson_id})["status"], "failed"
        )
        lesson_id, answers = self._begin()
        self.time.return_value += LESSON_LIFETIME
        self.assertEqual(
            self._work(self.pupil, "lesson_answer", {"lesson_id": lesson_id, **answers})["status"],
            "failed",
        )
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)

    def test_repeated_success_and_failed_guess_both_require_spaced_relearning(self):
        """New work IDs cannot grind successful lessons or brute-force failed exercises."""
        for correct in (False, True):
            with self.subTest(correct=correct):
                lesson_id, answers = self._begin()
                if not correct:
                    answers["controlled_factor"] = "none"
                self._complete(lesson_id, answers)
                result = self._work(
                    self.teacher,
                    "lesson_offer",
                    {
                        "course_id": COURSE.course_id,
                        "learner_dbref": self.pupil.dbref,
                    },
                )
                self.assertEqual(result["status"], "failed")
                self.time.return_value += REPEAT_INTERVAL

    def test_both_qualifications_are_rechecked_at_assessment(self):
        """A prior offer is not a lasting certificate of the instructor's knowledge."""
        lesson_id, answers = self._begin()
        CharacterKnowledge.objects.filter(
            person=self.instructor, foundation_id=COURSE.foundation_id
        ).update(mastery=59)
        self.assertEqual(self._complete(lesson_id, answers)["status"], "failed")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)

    def test_elementary_course_cannot_raise_knowledge_above_its_ceiling(self):
        """Bounded curriculum gains stop at the taught level and clear excess progress."""
        CharacterKnowledge.objects.filter(
            person=self.instructor, foundation_id=COURSE.foundation_id
        ).update(mastery=100)
        self.knowledge.mastery = COURSE.maximum_learner_mastery - 1
        self.knowledge.study_progress = progression_threshold(self.knowledge.mastery) - 1
        self.knowledge.save()
        lesson_id, answers = self._begin()
        self._complete(lesson_id, answers)
        self.knowledge.refresh_from_db()
        self.assertEqual((self.knowledge.mastery, self.knowledge.study_progress), (70, 0))
        self.time.return_value += REPEAT_INTERVAL
        result = self._work(
            self.teacher,
            "lesson_offer",
            {
                "course_id": COURSE.course_id,
                "learner_dbref": self.pupil.dbref,
            },
        )
        self.assertEqual(result["status"], "failed")

    def test_unsourced_foundation_can_start_from_zero_after_verified_instruction(self):
        """An actually taught subject may create a record; a role change cannot."""
        self.knowledge.delete()
        lesson_id, answers = self._begin()
        self._complete(lesson_id, answers)
        knowledge = CharacterKnowledge.objects.get(
            person=self.person, foundation_id=COURSE.foundation_id
        )
        self.assertEqual((knowledge.mastery, knowledge.study_progress), (0, 1))
        self.assertEqual(knowledge.source, "world_verified_instruction")

    def test_learning_failure_rolls_back_assessment_receipt_evidence_and_notifications(self):
        """All conceptual changes share the original work transaction."""
        lesson_id, answers = self._begin()
        request_id = self._id()
        before_events = CrewEvent.objects.count()
        from world.concept_learning import record_concept_experience as actual_hook

        def fail_after_award(actor, receipt):
            """Fail after actual progression to verify that it is transactional."""
            actual_hook(actor, receipt)
            raise RuntimeError("synthetic conceptual writer failure")

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with patch(
                "world.concept_learning.record_concept_experience", side_effect=fail_after_award
            ):
                with self.assertRaises(RuntimeError):
                    self._complete(lesson_id, answers, request_id)
        self.assertEqual(callbacks, [])
        self.assertFalse(WorkReceipt.objects.filter(pk=request_id).exists())
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        self.assertEqual(CrewEvent.objects.count(), before_events)
        lesson = ConceptLesson.objects.get(pk=lesson_id)
        self.assertEqual(
            (lesson.status, lesson.answers, lesson.completion_receipt_id), ("active", {}, None)
        )
        self.knowledge.refresh_from_db()
        self.assertEqual(self.knowledge.study_progress, 0)
        self.assertEqual(self._complete(lesson_id, answers, request_id)["status"], "succeeded")

    def test_only_participants_see_lesson_events_and_no_hidden_case_is_disclosed(self):
        """Training facts are independent of both private competence and ship truth."""
        from world.investigation import arm_anomaly
        from world.models import InvestigationCase

        case_id = arm_anomaly(cause="scrubber_bypass", seed=6)
        before = InvestigationCase.objects.get(pk=case_id).__dict__.copy()
        lesson_id, answers = self._begin()
        self._complete(lesson_id, answers)
        events = CrewEvent.objects.filter(kind__startswith="lesson_")
        self.assertEqual(
            set(events.values_list("recipient_dbref", flat=True)),
            {self.teacher.dbref, self.pupil.dbref},
        )
        delivered = json.dumps(list(events.values("details", "text")))
        for secret in (case_id, "scrubber_bypass", "expected", "mastery", "qualification"):
            self.assertNotIn(secret, delivered)
        after = InvestigationCase.objects.get(pk=case_id).__dict__.copy()
        before.pop("_state")
        after.pop("_state")
        self.assertEqual(before, after)

    def test_client_cannot_supply_credit_mastery_evidence_or_instructor_identity(self):
        """Only typed activity choices and exercise answers are accepted."""
        for extra in (
            {"mastery": 100},
            {"credit_units": 1},
            {"event_key": "invented"},
            {"instructor_dbref": self.teacher.dbref},
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self._work(
                    self.teacher,
                    "lesson_offer",
                    {
                        "course_id": COURSE.course_id,
                        "learner_dbref": self.pupil.dbref,
                        **extra,
                    },
                )
        self.assertEqual(WorkReceipt.objects.count(), 0)
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)

    def test_db_rejects_invalid_study_progress_and_self_lessons(self):
        """Database constraints protect score bounds and distinct instructional identity."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            CharacterKnowledge.objects.filter(pk=self.knowledge.pk).update(study_progress=1000)
        lesson_id = self._offer()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConceptLesson.objects.filter(pk=lesson_id).update(instructor=self.person)

    def test_bootstrap_and_person_role_changes_preserve_verified_study(self):
        """World setup does not replace earned progress with initial estimates."""
        lesson_id, answers = self._begin()
        self._complete(lesson_id, answers)
        self.pupil.db.crew_role = "chief_engineer"
        build_ship()
        self.knowledge.refresh_from_db()
        self.assertEqual((self.knowledge.mastery, self.knowledge.study_progress), (55, 1))

    def test_normal_work_command_supports_the_complete_lesson_protocol(self):
        """Ordinary character commands reach the same actor-bound world receipt path."""
        command = CmdOxWork()
        command.caller = self.teacher
        lesson_id = self._id()
        command.args = f"{lesson_id} lesson_offer learning {COURSE.course_id} {self.pupil.dbref}"
        with patch.object(self.teacher, "msg") as sent:
            command.func()
        self.assertEqual(sent.call_args.kwargs["ox_receipt"][0][0]["status"], "succeeded")
        command.caller = self.pupil
        command.args = f"{self._id()} lesson_begin learning {lesson_id}"
        with patch.object(self.pupil, "msg") as sent:
            command.func()
        result = sent.call_args.kwargs["ox_receipt"][0][0]
        exercise = json.loads(
            CrewEvent.objects.get(event_id=result["source_event_id"]).details["exercise"]
        )
        answers = solve_exercise(exercise)
        self.time.return_value += COURSE.duration
        command.args = (
            f"{self._id()} lesson_answer learning {lesson_id} "
            f"{answers['supported_factor']} {answers['controlled_factor']}"
        )
        with patch.object(self.pupil, "msg") as sent:
            command.func()
        self.assertEqual(sent.call_args.kwargs["ox_receipt"][0][0]["status"], "succeeded")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 1)

    def test_foreign_actor_cannot_reinterpret_assessment_as_own_learning(self):
        """Even the server hook rejects a different learner's completed receipt."""
        lesson_id, answers = self._begin()
        result = self._complete(lesson_id, answers)
        with self.assertRaises(PermissionError), transaction.atomic():
            record_concept_experience(
                self.teacher, WorkReceipt.objects.get(pk=result["request_id"])
            )
