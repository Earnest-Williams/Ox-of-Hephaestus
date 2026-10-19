"""Firsthand investigative learning without diagnosis or hidden-cause certification."""

from __future__ import annotations

import json
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from commands.crew import CmdOxWork
from django.db import IntegrityError, transaction
from world.bootstrap import build_ship
from world.character_profiles import profile_for_actor
from world.inquiry_learning import (
    ATTEMPT_LIFETIME,
    CREDIT_INTERVAL,
    FOUNDATION,
    MAX_MASTERY,
    REVIEW_SECONDS,
    record_inquiry_experience,
)
from world.investigation import arm_anomaly, take_sample
from world.investigation_followup import take_probe
from world.learning import progression_threshold
from world.models import (
    CaptainObligation,
    CharacterKnowledge,
    CharacterLearningEvidence,
    CharacterSkill,
    CharacterTechnique,
    CrewEvent,
    InquiryLearningAttempt,
    InvestigationCase,
    WorkReceipt,
)
from world.task_shadow import evaluate_world_shadow
from world.work_actions import execute_work, work_receipt

from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaTestCase


def solve_review(event) -> dict:
    """Use only the investigator's delivered observation and transfer material."""
    data = event.details
    exercise = json.loads(data["transfer_exercise"])
    count = len({row["source_id"] for row in exercise["reports"]})
    return {
        "interpretation": (
            "supported_unconfirmed" if data["reading"] == "supports" else "unsupported_not_excluded"
        ),
        "independent_sources": "one_source" if count == 1 else "two_sources",
    }


@contextmanager
def forbid_secret_case_fields():
    """Make any attempt by the learning path to read latent truth fail loudly."""

    def forbidden(_instance):
        """Reject hidden physical causes, random draws or unconfirmed theories."""
        raise AssertionError("Learning tried to consult a private case field")

    with ExitStack() as stack:
        for name in ("cause", "signals", "probe_key", "assessment", "reassessment"):
            stack.enter_context(patch.object(InvestigationCase, name, property(forbidden)))
        yield


class InquiryLearningTests(EvenniaTestCase):
    """Exercise the real question/probe/report chain before assessing conceptual gains."""

    def setUp(self):
        """Use a genuine uncertain case, separately bound people and a controlled clock."""
        super().setUp()
        self.ship = build_ship()
        self.actor = self.ship["watch"]
        self.person = profile_for_actor(self.actor)
        self.knowledge = CharacterKnowledge.objects.get(
            person=self.person, foundation_id=FOUNDATION
        )
        self.serial = 100
        self.clock = patch("world.inquiry_learning.gametime.gametime", return_value=100000.0)
        self.time = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.case_id = arm_anomaly(cause="scrubber_bypass", seed=6)

    def _id(self):
        """Keep independent work IDs distinct from the activity and case identity."""
        self.serial += 1
        return f"{self.serial:032x}"

    def _work(self, operation, *, actor=None, target="learning", request_id=None, **arguments):
        """Use the production world transaction for every report and learning stage."""
        return execute_work(
            actor or self.actor,
            request_id or self._id(),
            operation,
            target,
            arguments={"case_id": self.case_id, **arguments},
        )

    def _initial(self, actor=None):
        """Collect and report an actual actor-local first measurement."""
        actor = actor or self.actor
        self.assertIsNotNone(take_sample(actor, self.case_id))
        self.assertEqual(
            self._work("anomaly_report", actor=actor, target="ship")["status"], "succeeded"
        )

    def _register(self, *, challenge=False):
        """Register either an independent question or an alternative to an existing theory."""
        self._initial()
        if challenge:
            self._initial(self.ship["officer"])
            self._initial(self.ship["cargo"])
            self.assertEqual(
                self._work(
                    "anomaly_assess",
                    actor=self.ship["officer"],
                    target="ship",
                    hypothesis="cargo_vapors",
                )["status"],
                "succeeded",
            )
            result = self._work("anomaly_challenge", target="ship", hypothesis="bus_interference")
        else:
            result = self._work("anomaly_question", target="ship")
        self.assertEqual(result["status"], "succeeded")

    def _predict(self, prediction="does_not_support"):
        """Save a forecast before the subsequent instrument draw."""
        result = self._work("inquiry_predict", prediction=prediction)
        self.assertEqual(result["status"], "succeeded")
        return result["request_id"]

    def _physical(self, reading="supports"):
        """Fix only the test's physical draw; learning never receives this fixture control."""
        with patch("world.investigation_followup._measurement", return_value=reading):
            sample = take_probe(self.actor, self.case_id)
        self.assertIsNotNone(sample)
        report = self._work("anomaly_probe_report", target="ship")
        self.assertEqual(report["status"], "succeeded")
        return sample, report

    def _review(self, *, duplicate_sources=False):
        """Read a genuine review observation with controlled fresh training-source structure."""
        exercise = {
            "reports": [
                {"source_id": "training-a", "reading": "supports"},
                {
                    "source_id": "training-a" if duplicate_sources else "training-b",
                    "reading": "supports",
                },
            ],
            "question": "Count distinct independent source IDs; copies retain the same ID.",
            "options": ["one_source", "two_sources"],
        }
        with patch("world.inquiry_learning._exercise", return_value=exercise):
            result = self._work("inquiry_review")
        self.assertEqual(result["status"], "succeeded")
        event = CrewEvent.objects.get(event_id=result["source_event_id"])
        return solve_review(event)

    def _ready(self, *, reading="supports", challenge=False, duplicate_sources=False):
        """Perform the complete causal prerequisite chain through ordinary world functions."""
        self._register(challenge=challenge)
        prediction_id = self._predict()
        self._physical(reading)
        answers = self._review(duplicate_sources=duplicate_sources)
        return prediction_id, answers

    def _complete(self, answers, request_id=None):
        """Complete a due reflection without exposing any private world cause to the actor."""
        attempt = InquiryLearningAttempt.objects.get(person=self.person, case_id=self.case_id)
        self.time.return_value = attempt.due_game_time
        return self._work("inquiry_reflect", request_id=request_id, **answers)

    def _next_case(self):
        """Operator-only fixture: isolate successive actual case histories for spacing tests."""
        InvestigationCase.objects.filter(pk=self.case_id).update(status="closed")
        self.case_id = arm_anomaly(cause="scrubber_bypass", seed=6)

    def test_prediction_probe_reporting_and_time_do_not_by_themselves_grant_theory(self):
        """A causal history is required but is not itself proof of conceptual learning."""
        prediction_id, _answers = self._ready()
        self.time.return_value += REVIEW_SECONDS * 2
        attempt = InquiryLearningAttempt.objects.get(pk=prediction_id)
        self.assertEqual(attempt.status, "reviewing")
        self.assertEqual(attempt.prediction_receipt_id, prediction_id)
        self.assertIsNotNone(attempt.report_receipt_id)
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        self.knowledge.refresh_from_db()
        self.assertEqual((self.knowledge.mastery, self.knowledge.study_progress), (50, 0))

    def test_positive_negative_and_copied_source_exercises_can_earn_only_method_knowledge(self):
        """Both directions of fallible evidence and both source structures are learnable."""
        for reading, duplicate in (("supports", False), ("does_not_support", True)):
            with self.subTest(reading=reading, duplicate=duplicate):
                skills = list(
                    CharacterSkill.objects.values_list("id", "proficiency", "practice_progress")
                )
                techniques = list(
                    CharacterTechnique.objects.values_list("id", "familiarity", "practice_progress")
                )
                prediction_id, answers = self._ready(reading=reading, duplicate_sources=duplicate)
                result = self._complete(answers)
                self.assertEqual(result["status"], "succeeded")
                attempt = InquiryLearningAttempt.objects.get(pk=prediction_id)
                self.assertEqual(attempt.status, "passed")
                evidence = CharacterLearningEvidence.objects.get(receipt_id=result["request_id"])
                self.assertEqual(
                    (evidence.component_kind, evidence.component_id, evidence.credit_units),
                    ("knowledge", FOUNDATION, 1),
                )
                self.assertEqual(evidence.event_key, "inquiry:" + self.case_id)
                self.assertEqual(attempt.completion_receipt_id, evidence.receipt_id)
                self.assertEqual(
                    list(
                        CharacterSkill.objects.values_list("id", "proficiency", "practice_progress")
                    ),
                    skills,
                )
                self.assertEqual(
                    list(
                        CharacterTechnique.objects.values_list(
                            "id", "familiarity", "practice_progress"
                        )
                    ),
                    techniques,
                )
                self.time.return_value += CREDIT_INTERVAL
                self._next_case()

    def test_wrong_forecast_and_retained_wrong_diagnosis_do_not_block_actual_learning(self):
        """The grade concerns evidence limits, not lucky prediction or a truth-matching opinion."""
        prediction_id, answers = self._ready(challenge=True, reading="supports")
        self.assertEqual(
            self._work("anomaly_reconsider", target="ship", hypothesis="bus_interference")[
                "status"
            ],
            "succeeded",
        )
        self._complete(answers)
        attempt = InquiryLearningAttempt.objects.get(pk=prediction_id)
        self.assertNotEqual(attempt.prediction, attempt.reading)
        case = InvestigationCase.objects.get(pk=self.case_id)
        self.assertEqual(case.cause, "scrubber_bypass")
        self.assertEqual(case.reconsiderations[self.actor.dbref]["hypothesis"], "bus_interference")
        self.assertEqual(case.assessment["hypothesis"], "cargo_vapors")
        self.assertEqual(case.status, "open")
        self.assertEqual(CaptainObligation.objects.get(pk=self.case_id).status, "open")
        self.assertEqual(CharacterLearningEvidence.objects.get().credit_units, 1)

    def test_learning_path_cannot_read_cause_noise_or_bridge_theories(self):
        """Deferring secret columns is enforced by a descriptor that rejects any access."""
        self._register()
        with forbid_secret_case_fields():
            prediction_id = self._predict()
        self._physical()
        with forbid_secret_case_fields():
            answers = self._review()
            self._complete(answers)
        self.assertEqual(InquiryLearningAttempt.objects.get(pk=prediction_id).status, "passed")

    def test_only_actual_investigator_receives_learning_events_without_hidden_verdicts(self):
        """Neither other minds nor an operator-only correctness oracle become actor observations."""
        _prediction_id, answers = self._ready()
        self._complete(answers)
        events = CrewEvent.objects.filter(kind__startswith="inquiry_")
        self.assertEqual(set(events.values_list("recipient_dbref", flat=True)), {self.actor.dbref})
        delivered = json.dumps(list(events.values("details", "text")))
        for forbidden in (
            "scrubber_bypass",
            "true_cause",
            "correct_diagnosis",
            "probability",
            "mastery",
            "expected",
        ):
            self.assertNotIn(forbidden, delivered)

    def test_prediction_requires_receipted_firsthand_report_and_registered_inquiry(self):
        """A declaration before any evidence or without a question does not enrol a learner."""
        self.assertEqual(self._work("inquiry_predict", prediction="supports")["status"], "failed")
        self._initial()
        self.assertEqual(self._work("inquiry_predict", prediction="supports")["status"], "failed")
        self.assertEqual(InquiryLearningAttempt.objects.count(), 0)

    def test_forecast_cannot_be_registered_after_observing_the_probe(self):
        """New IDs and even a correct reading cannot backdate a prediction."""
        self._register()
        self._physical()
        self.assertEqual(self._work("inquiry_predict", prediction="supports")["status"], "failed")
        self.assertEqual(InquiryLearningAttempt.objects.count(), 0)
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)

    def test_forecast_and_reflection_each_need_the_investigators_own_local_identity(self):
        """Rank, a case ID, another person's body and a remote location provide no evidence."""
        self._register()
        for actor in (self.ship["officer"], self.ship["chief"], self.ship["captain"]):
            self.assertEqual(
                self._work("inquiry_predict", actor=actor, prediction="supports")["status"],
                "failed",
            )
        visitor = create_object(
            "typeclasses.ship.CrewCharacter", key="Visitor", location=self.actor.location
        )
        visitor.db.crew_role = "watch_engineer"
        self.assertEqual(
            self._work("inquiry_predict", actor=visitor, prediction="supports")["status"], "failed"
        )
        self.actor.move_to(self.ship["bridge"], quiet=True)
        denied_id = self._id()
        denied = self._work("inquiry_predict", request_id=denied_id, prediction="supports")
        self.assertEqual(denied["status"], "failed")
        self.actor.move_to(self.ship["pump"].location, quiet=True)
        self.assertEqual(
            self._work("inquiry_predict", request_id=denied_id, prediction="supports"), denied
        )
        self._predict()

    def test_missing_or_other_persons_report_receipt_cannot_be_used_as_provenance(self):
        """The case's JSON references are checked against actual actor-bound source receipts."""
        self._register()
        report_id = InvestigationCase.objects.get(pk=self.case_id).reports[self.actor.dbref]
        WorkReceipt.objects.filter(
            operation="anomaly_report", actor_dbref=self.actor.dbref
        ).delete()
        self.assertTrue(CrewEvent.objects.filter(event_id=report_id).exists())
        self.assertEqual(self._work("inquiry_predict", prediction="supports")["status"], "failed")

    def test_each_existing_specialist_learns_only_from_their_own_station_evidence(self):
        """The four actual investigators retain distinct activities and conceptual ledgers."""
        for member in ("watch", "chief", "cargo", "environment"):
            with self.subTest(member=member):
                self.actor = self.ship[member]
                self.person = profile_for_actor(self.actor)
                self.knowledge = CharacterKnowledge.objects.get(
                    person=self.person, foundation_id=FOUNDATION
                )
                prediction_id, answers = self._ready()
                result = self._complete(answers)
                attempt = InquiryLearningAttempt.objects.get(pk=prediction_id)
                self.assertEqual(attempt.status, "passed")
                sample = CrewEvent.objects.get(event_id=attempt.sample_event_id)
                self.assertEqual(sample.recipient_dbref, self.actor.dbref)
                evidence = CharacterLearningEvidence.objects.get(receipt_id=result["request_id"])
                self.assertEqual(evidence.person_id, self.person.pk)
                self.assertEqual(evidence.credit_units, int(self.knowledge.mastery < MAX_MASTERY))
        self.assertEqual(InquiryLearningAttempt.objects.count(), 4)

    def test_remote_reflection_is_refused_without_consuming_the_local_assessment(self):
        """Station presence is rechecked after a valid review, not only at prediction time."""
        prediction_id, answers = self._ready()
        self.time.return_value += REVIEW_SECONDS
        self.actor.move_to(self.ship["bridge"], quiet=True)
        self.assertEqual(self._work("inquiry_reflect", **answers)["status"], "failed")
        self.assertEqual(InquiryLearningAttempt.objects.get(pk=prediction_id).status, "reviewing")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        self.actor.move_to(self.ship["pump"].location, quiet=True)
        self.assertEqual(self._work("inquiry_reflect", **answers)["status"], "succeeded")
        self.assertEqual(CharacterLearningEvidence.objects.get().credit_units, 1)

    def test_review_requires_actual_subsequent_probe_and_its_receipted_report(self):
        """Forecasting and taking an unreported measurement cannot create a review."""
        self._register()
        self._predict()
        self.assertEqual(self._work("inquiry_review")["status"], "failed")
        self.assertIsNotNone(take_probe(self.actor, self.case_id))
        self.assertEqual(self._work("inquiry_review")["status"], "failed")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)

    def test_case_reference_to_old_or_foreign_sample_cannot_pass_review(self):
        """The new sample must have the correct stage, actor and causal sequence."""
        self._register()
        self._predict()
        self._physical()
        case = InvestigationCase.objects.get(pk=self.case_id)
        probes = dict(case.probes)
        probes[self.actor.dbref] = {
            **probes[self.actor.dbref],
            "sample_event_id": case.samples[self.actor.dbref],
        }
        case.probes = probes
        case.save(update_fields=["probes"])
        self.assertEqual(self._work("inquiry_review")["status"], "failed")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)

    def test_early_reflection_remains_refused_under_original_id_when_later_due(self):
        """Elapsed time cannot retroactively authorize a previously rejected request."""
        _prediction_id, answers = self._ready()
        request_id = self._id()
        denied = self._work("inquiry_reflect", request_id=request_id, **answers)
        self.assertEqual(denied["status"], "failed")
        self.time.return_value += REVIEW_SECONDS
        self.assertEqual(self._work("inquiry_reflect", request_id=request_id, **answers), denied)
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        self.assertEqual(self._work("inquiry_reflect", **answers)["status"], "succeeded")

    def test_wrong_scope_or_count_consumes_attempt_without_conceptual_credit(self):
        """Parroting a reading while mishandling independent sources does not demonstrate the method."""
        prediction_id, answers = self._ready(duplicate_sources=True)
        wrong = {**answers, "independent_sources": "two_sources"}
        result = self._complete(wrong)
        self.assertEqual(result["status"], "succeeded")  # the submission happened
        self.assertEqual(InquiryLearningAttempt.objects.get(pk=prediction_id).status, "failed")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        self.assertEqual(self._work("inquiry_reflect", **answers)["status"], "failed")
        self.assertEqual(self._work("inquiry_predict", prediction="supports")["status"], "failed")

    def test_same_and_new_ids_and_foreign_receipts_cannot_double_credit(self):
        """One actual person/case activity and a globally actor-bound receipt are separate guards."""
        _prediction_id, answers = self._ready()
        original = self._complete(answers)
        self.assertEqual(
            self._work("inquiry_reflect", request_id=original["request_id"], **answers), original
        )
        self.assertEqual(self._work("inquiry_reflect", **answers)["status"], "failed")
        self.assertEqual(work_receipt(self.actor, original["request_id"]), original)
        self.assertEqual(
            work_receipt(self.ship["chief"], original["request_id"])["status"], "unknown"
        )
        with self.assertRaises(PermissionError):
            self._work(
                "inquiry_reflect",
                actor=self.ship["chief"],
                request_id=original["request_id"],
                **answers,
            )
        with transaction.atomic():
            self.assertEqual(
                record_inquiry_experience(
                    self.actor, WorkReceipt.objects.get(pk=original["request_id"])
                ),
                0,
            )
        self.assertEqual(CharacterLearningEvidence.objects.count(), 1)

    def test_success_and_failure_both_space_credit_without_blocking_new_real_inquiry(self):
        """Repeated actual cases still proceed, but quick repeats do not produce extra theory units."""
        _prediction_id, answers = self._ready()
        wrong = {**answers, "interpretation": "unsupported_not_excluded"}
        self._complete(wrong)
        self._next_case()
        _prediction_id, answers = self._ready()
        self._complete(answers)
        evidence = CharacterLearningEvidence.objects.get()
        self.assertEqual(evidence.credit_units, 0)
        self.assertEqual(evidence.progress_before, evidence.progress_after)
        self.time.return_value += CREDIT_INTERVAL
        self._next_case()
        _prediction_id, answers = self._ready()
        self._complete(answers)
        self.assertEqual(
            list(
                CharacterLearningEvidence.objects.order_by("id").values_list(
                    "credit_units", flat=True
                )
            ),
            [0, 1],
        )

    def test_method_knowledge_gain_transfers_to_novel_shadow_without_practical_or_permission_gain(
        self,
    ):
        """A real threshold crossing affects the conceptual input only."""
        self.knowledge.study_progress = progression_threshold(self.knowledge.mastery) - 1
        self.knowledge.save(update_fields=["study_progress"])
        before = evaluate_world_shadow(self.actor, "analyzer.inconsistent_readings")
        _prediction_id, answers = self._ready()
        self._complete(answers)
        after = evaluate_world_shadow(self.actor, "analyzer.inconsistent_readings")
        self.knowledge.refresh_from_db()
        self.assertEqual((self.knowledge.mastery, self.knowledge.study_progress), (51, 0))
        self.assertAlmostEqual(
            after.evaluation.provisional_score - before.evaluation.provisional_score, 0.25
        )
        self.assertEqual(after.evaluation.primary_skill, before.evaluation.primary_skill)
        self.assertEqual(after.evaluation.familiarity, before.evaluation.familiarity)
        self.assertEqual(self.actor.db.crew_role, "watch_engineer")

    def test_ceiling_does_not_erase_pending_progress_from_more_advanced_study(self):
        """A zero-credit elementary assessment leaves an expert's other study progress intact."""
        self.knowledge.mastery = MAX_MASTERY + 5
        self.knowledge.study_progress = 5
        self.knowledge.save()
        _prediction_id, answers = self._ready()
        self._complete(answers)
        self.knowledge.refresh_from_db()
        self.assertEqual((self.knowledge.mastery, self.knowledge.study_progress), (75, 5))
        evidence = CharacterLearningEvidence.objects.get()
        self.assertEqual(
            (evidence.credit_units, evidence.progress_before, evidence.progress_after), (0, 5, 5)
        )

    def test_previously_unsourced_foundation_uses_inquiry_provenance(self):
        """A newly evidenced subject is attributed to inquiry rather than invented instruction."""
        self._register()
        self._predict()
        self._physical()
        self.knowledge.delete()
        self._complete(self._review())
        knowledge = CharacterKnowledge.objects.get(person=self.person, foundation_id=FOUNDATION)
        self.assertEqual((knowledge.mastery, knowledge.study_progress), (0, 1))
        self.assertEqual(knowledge.source, "world_verified_inquiry")

    def test_closed_case_can_be_reflected_on_without_reopening_it(self):
        """Learning from completed evidence does not require keeping a problem unresolved."""
        self._register()
        self._predict()
        self._physical()
        InvestigationCase.objects.filter(pk=self.case_id).update(status="closed")
        self._complete(self._review())
        self.assertEqual(CharacterLearningEvidence.objects.get().credit_units, 1)
        self.assertEqual(InvestigationCase.objects.get(pk=self.case_id).status, "closed")

    def test_expired_activity_does_not_produce_new_learning(self):
        """A remembered case ID is not an indefinitely reusable learning authorization."""
        prediction_id, answers = self._ready()
        self.time.return_value += ATTEMPT_LIFETIME
        self.assertEqual(self._work("inquiry_reflect", **answers)["status"], "failed")
        self.assertEqual(InquiryLearningAttempt.objects.get(pk=prediction_id).status, "reviewing")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)

    def test_learning_writer_failure_rolls_back_grade_receipt_progress_and_notifications(self):
        """An assessment cannot commit independently of its conceptual evidence."""
        prediction_id, answers = self._ready()
        before_events = CrewEvent.objects.count()
        request_id = self._id()
        from world.inquiry_learning import record_inquiry_experience as actual_hook

        def fail_after_award(actor, receipt):
            """Fail only after actual ledger writes so rollback is meaningfully exercised."""
            actual_hook(actor, receipt)
            raise RuntimeError("synthetic inquiry evidence writer failure")

        with self.captureOnCommitCallbacks(execute=True) as notifications:
            with patch(
                "world.inquiry_learning.record_inquiry_experience", side_effect=fail_after_award
            ):
                with self.assertRaises(RuntimeError):
                    self._complete(answers, request_id)
        self.assertEqual(notifications, [])
        self.assertEqual(CrewEvent.objects.count(), before_events)
        self.assertFalse(WorkReceipt.objects.filter(pk=request_id).exists())
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        attempt = InquiryLearningAttempt.objects.get(pk=prediction_id)
        self.assertEqual(
            (attempt.status, attempt.answers, attempt.completion_receipt_id),
            ("reviewing", {}, None),
        )
        self.knowledge.refresh_from_db()
        self.assertEqual(self.knowledge.study_progress, 0)
        self.assertEqual(self._complete(answers, request_id)["status"], "succeeded")

    def test_client_cannot_submit_knowledge_credit_source_events_or_world_cause(self):
        """Requests contain only bounded actions and reasoning answers."""
        for extra in (
            {"mastery": 100},
            {"credit_units": 1},
            {"source_event_id": "invented"},
            {"cause": "scrubber_bypass"},
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self._work("inquiry_predict", prediction="supports", **extra)
        self.assertEqual(InquiryLearningAttempt.objects.count(), 0)

    def test_database_enforces_prediction_and_stage_vocabulary(self):
        """World persistence also rejects impossible typed attempt states."""
        self._register()
        prediction_id = self._predict()
        for updates in ({"prediction": "true_cause"}, {"status": "invented"}):
            with (
                self.subTest(updates=updates),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                InquiryLearningAttempt.objects.filter(pk=prediction_id).update(**updates)

    def test_character_command_routes_the_reflection_to_the_same_world_receipt(self):
        """Normal characters use existing oxwork, not a privileged learning endpoint."""
        _prediction_id, answers = self._ready()
        self.time.return_value += REVIEW_SECONDS
        request_id = self._id()
        command = CmdOxWork()
        command.caller = self.actor
        command.args = (
            f"{request_id} inquiry_reflect learning {self.case_id} "
            f"{answers['interpretation']} {answers['independent_sources']}"
        )
        with patch.object(self.actor, "msg") as sent:
            command.func()
        self.assertEqual(sent.call_args.kwargs["ox_receipt"][0][0]["status"], "succeeded")
        self.assertEqual(CharacterLearningEvidence.objects.get().receipt_id, request_id)
