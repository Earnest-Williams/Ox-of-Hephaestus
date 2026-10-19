"""Practice can only arise from committed, consequential world work."""
from __future__ import annotations

from unittest.mock import patch

from django.db import transaction
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.character_profiles import profile_for_actor
from world.learning import (
    LEARNING_WINDOW_SECONDS, MAX_CREDITED_REPETITIONS,
    progression_threshold, record_work_experience,
)
from world.live_crew import fixture_setup
from world.models import (
    CharacterSkill, CharacterTechnique, CharacterKnowledge,
    CharacterLearningEvidence, WorkReceipt,
)
from world.work_actions import execute_work

ISOLATE = "1" * 32
REPAIR = "2" * 32


class WorldReceiptLearningTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        fixture_setup(scheduled_clock=True)
        self.ship = build_ship()
        self.ari = self.ship["watch"]
        self.person = profile_for_actor(self.ari)
        self.skill = CharacterSkill.objects.get(
            person=self.person, skill_id="mechanical.pump_service",
        )
        self.technique = CharacterTechnique.objects.get(
            person=self.person, technique_id="pump.p01.routine_service",
        )

    def _perform_repair(self):
        first = execute_work(self.ari, ISOLATE, "isolate", "pump")
        self.assertEqual(first["status"], "succeeded")
        repair = execute_work(self.ari, REPAIR, "repair", "pump")
        self.assertEqual(repair["status"], "succeeded")
        return repair

    def test_only_completed_physical_repair_creates_two_evidence_records(self):
        prior_theory = dict(
            CharacterKnowledge.objects.filter(person=self.person)
            .values_list("foundation_id", "mastery")
        )
        repaired = self._perform_repair()
        self.assertIsNotNone(repaired["source_event_id"])
        self.assertEqual(
            CharacterLearningEvidence.objects.filter(receipt_id=ISOLATE).count(), 0,
        )
        evidence = list(CharacterLearningEvidence.objects.filter(receipt_id=REPAIR)
                        .order_by("component_kind"))
        self.assertEqual(len(evidence), 2)
        self.assertEqual(
            {(e.component_kind, e.component_id) for e in evidence},
            {("skill", "mechanical.pump_service"),
             ("technique", "pump.p01.routine_service")},
        )
        self.assertTrue(all(e.credit_units == 1 for e in evidence))
        self.assertTrue(all(e.event_key.startswith("pump:p01-") for e in evidence))
        self.assertEqual(
            CharacterKnowledge.objects.filter(person=self.person)
            .values_list("foundation_id", "mastery"),
            CharacterKnowledge.objects.filter(person=self.person)
            .values_list("foundation_id", "mastery"),
        )
        self.assertEqual(
            dict(CharacterKnowledge.objects.filter(person=self.person)
                 .values_list("foundation_id", "mastery")),
            prior_theory,
        )
        self.assertEqual(CharacterLearningEvidence.objects.count(), 2)
        self.assertEqual(execute_work(self.ari, REPAIR, "repair", "pump"), repaired)
        self.assertEqual(CharacterLearningEvidence.objects.count(), 2)

    def test_practice_progress_accumulates_and_crosses_threshold(self):
        self.assertEqual(progression_threshold(60), 12)
        CharacterSkill.objects.filter(pk=self.skill.pk).update(practice_progress=11)
        CharacterTechnique.objects.filter(pk=self.technique.pk).update(practice_progress=11)
        self._perform_repair()
        self.skill.refresh_from_db()
        self.technique.refresh_from_db()
        self.assertEqual((self.skill.proficiency, self.skill.practice_progress), (61, 0))
        self.assertEqual((self.technique.familiarity, self.technique.practice_progress),
                         (61, 0))
        score_after = {e.component_kind: e.score_after for e in
                       CharacterLearningEvidence.objects.filter(receipt_id=REPAIR)}
        self.assertEqual(score_after, {"skill": 61, "technique": 61})

    def test_refused_operations_and_social_talk_cannot_generate_xp(self):
        rejected = execute_work(self.ship["environment"], "3" * 32, "repair", "pump")
        self.assertEqual(rejected["status"], "failed")
        self.assertEqual(rejected["source_event_id"], None)
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        self.assertEqual(execute_work(self.ship["officer"], "4" * 32, "radio")["status"],
                         "succeeded")
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        self.skill.refresh_from_db()
        self.assertEqual(self.skill.practice_progress, 0)

    def test_foreign_actor_cannot_reinterpret_someone_elses_receipt(self):
        self._perform_repair()
        receipt = WorkReceipt.objects.get(pk=REPAIR)
        count = CharacterLearningEvidence.objects.count()
        with self.assertRaises(PermissionError):
            with transaction.atomic():
                record_work_experience(self.ship["chief"], receipt)
        self.assertEqual(CharacterLearningEvidence.objects.count(), count)

    def test_same_physical_source_event_cannot_be_credited_by_new_request_id(self):
        repaired = self._perform_repair()
        first_count = CharacterLearningEvidence.objects.count()
        before_skill = CharacterSkill.objects.get(pk=self.skill.pk).practice_progress
        # Operator-created duplicate receipt for the same *physical* event.
        # This is a synthetic test fixture, not an ordinary ship command.
        replacement_id = "6" * 32
        copied = {**repaired, "request_id": replacement_id}
        with transaction.atomic():
            receipt = WorkReceipt.objects.create(
                request_id=replacement_id,
                actor_dbref=self.ari.dbref,
                target="pump", operation="repair",
                arguments={}, outcome=copied,
                game_time=WorkReceipt.objects.get(pk=REPAIR).game_time,
            )
            self.assertEqual(record_work_experience(self.ari, receipt), 0)
        self.assertEqual(CharacterLearningEvidence.objects.count(), first_count)
        self.assertEqual(
            CharacterSkill.objects.get(pk=self.skill.pk).practice_progress, before_skill,
        )

    def test_practice_rate_limit_records_real_repeats_without_awarding_credit(self):
        self.assertEqual(MAX_CREDITED_REPETITIONS, 3)
        self.assertGreater(LEARNING_WINDOW_SECONDS, 0)
        self._perform_repair()
        source = WorkReceipt.objects.get(pk=REPAIR)
        original_score = CharacterSkill.objects.get(pk=self.skill.pk).proficiency
        original_practice = CharacterSkill.objects.get(pk=self.skill.pk).practice_progress
        # Explicitly trusted operator fixtures for the rate-limit arithmetic.
        # The normal execute_work pipeline never accepts these model objects.
        for index in range(3):
            req = f"{index + 20:032x}"
            outcome = {**source.outcome, "request_id": req,
                       "source_event_id": f"p01-synthetic-{index:04d}"}
            with transaction.atomic():
                synthetic = WorkReceipt.objects.create(
                    request_id=req, actor_dbref=self.ari.dbref,
                    target="pump", operation="repair",
                    arguments={}, outcome=outcome, game_time=source.game_time,
                )
                record_work_experience(self.ari, synthetic)
        recent = CharacterLearningEvidence.objects.filter(
            person=self.person, component_kind="skill",
            component_id="mechanical.pump_service",
        ).order_by("id")
        self.assertEqual(list(recent.values_list("credit_units", flat=True)),
                         [1, 1, 1, 0])
        self.assertEqual(CharacterSkill.objects.get(pk=self.skill.pk).proficiency,
                         original_score)
        self.assertEqual(CharacterSkill.objects.get(pk=self.skill.pk).practice_progress,
                         original_practice + 2)

    def test_failed_learning_hook_rolls_back_receipt_and_experience(self):
        isolate = execute_work(self.ari, ISOLATE, "isolate", "pump")
        self.assertEqual(isolate["status"], "succeeded")
        with patch("world.learning.record_work_experience",
                   side_effect=RuntimeError("synthetic learning writer failure")):
            with self.assertRaises(RuntimeError):
                execute_work(self.ari, REPAIR, "repair", "pump")
        self.assertFalse(WorkReceipt.objects.filter(pk=REPAIR).exists())
        self.assertEqual(CharacterLearningEvidence.objects.count(), 0)
        self.skill.refresh_from_db()
        self.assertEqual(self.skill.practice_progress, 0)

    def test_receipt_replay_cannot_run_new_learning_or_advance_role(self):
        self._perform_repair()
        prior = CharacterLearningEvidence.objects.count()
        self.ari.db.crew_role = "captain"
        cached = execute_work(self.ari, REPAIR, "repair", "pump")
        self.assertEqual(cached["status"], "succeeded")
        self.assertEqual(CharacterLearningEvidence.objects.count(), prior)


if __name__ == "__main__":
    import unittest
    unittest.main()
