"""Shadow calibration tests; no roll may alter Ox physics or cognition."""
from __future__ import annotations

from copy import deepcopy
import unittest

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.character_profiles import profile_for_actor
from world.models import CrewEvent, WorkReceipt, CharacterSkill
from world.task_resolution import TASKS, WEIGHTS, compare_shadow, evaluate_shadow
from world.task_shadow import evaluate_world_shadow


def inputs(task_id, *, skill=85, knowledge=75, aptitude=5, familiarity=80):
    return {
        "proficiency": skill,
        "knowledge": knowledge,
        "familiarity": familiarity,
        "aptitudes": {name: aptitude for name in TASKS[task_id].relevant_aptitudes},
    }


class ShadowTaskCalibrationTests(unittest.TestCase):
    def test_weights_are_declared_and_no_rolls_or_implicit_outcomes(self):
        self.assertEqual(WEIGHTS["routine"], (65, 15, 15, 5))
        self.assertEqual(WEIGHTS["novel_investigation"], (35, 25, 35, 5))
        for task_id in TASKS:
            t = inputs(task_id)
            first = evaluate_shadow(task_id, **t)
            second = evaluate_shadow(task_id, **t)
            self.assertEqual(first, second)
            self.assertEqual(first.mode, "shadow")
            self.assertGreaterEqual(first.provisional_score, 0)
            self.assertLessEqual(first.provisional_score, 100)
            self.assertEqual(first.skill_id, TASKS[task_id].skill_id)

    def test_professional_expertise_outweighs_untrained_genius_in_routine_work(self):
        tid = "pump.routine_service"
        outcomes = compare_shadow(tid, {
            "novice_genius": inputs(
                tid, skill=15, knowledge=15, aptitude=10, familiarity=0,
            ),
            "ordinary_veteran": inputs(
                tid, skill=85, knowledge=75, aptitude=5, familiarity=80,
            ),
        })
        self.assertGreater(
            outcomes["ordinary_veteran"].provisional_score,
            outcomes["novice_genius"].provisional_score + 30,
        )

    def test_equal_expertise_gifted_veteran_has_bigger_novelty_advantage(self):
        routine = "pump.routine_service"
        novel = "pump.novel_interference"
        r_ordinary = evaluate_shadow(routine, **inputs(routine, aptitude=5))
        r_gifted = evaluate_shadow(routine, **inputs(routine, aptitude=10))
        n_ordinary = evaluate_shadow(novel, **inputs(novel, aptitude=5))
        n_gifted = evaluate_shadow(novel, **inputs(novel, aptitude=10))
        routine_gain = r_gifted.provisional_score - r_ordinary.provisional_score
        novel_gain = n_gifted.provisional_score - n_ordinary.provisional_score
        self.assertGreater(novel_gain, routine_gain * 2)
        self.assertEqual(routine_gain, 7.5)
        self.assertEqual(novel_gain, 17.5)
        self.assertTrue(n_gifted.theoretical_foothold)

    def test_innovation_cannot_conjure_missing_theoretical_foundation(self):
        tid = "pump.novel_interference"
        genius = evaluate_shadow(
            tid, **inputs(tid, skill=85, knowledge=0,
                          aptitude=10, familiarity=70),
        )
        self.assertFalse(genius.theoretical_foothold)
        self.assertEqual(genius.mode, "shadow")
        candidate = evaluate_shadow(
            tid, **inputs(tid, skill=85, knowledge=20,
                          aptitude=5, familiarity=70),
        )
        self.assertTrue(candidate.theoretical_foothold)

    def test_agility_is_not_fine_hand_dexterity(self):
        repair = "pump.routine_service"
        cargo = "cargo.restow"
        self.assertIn("dexterity", TASKS[repair].relevant_aptitudes)
        self.assertNotIn("agility", TASKS[repair].relevant_aptitudes)
        self.assertIn("agility", TASKS[cargo].relevant_aptitudes)
        a = inputs(cargo)
        b = deepcopy(a)
        b["aptitudes"]["agility"] = 10
        self.assertGreater(
            evaluate_shadow(cargo, **b).provisional_score,
            evaluate_shadow(cargo, **a).provisional_score,
        )

    def test_reject_untrusted_shaped_scores_and_unknown_task(self):
        t = inputs("pump.routine_service")
        for bad in (True, -1, 101, 10.5, "50"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                evaluate_shadow("pump.routine_service", **{**t, "proficiency": bad})
        bad = {**t, "aptitudes": {**t["aptitudes"], "agility": 9}}
        with self.assertRaises(ValueError):
            evaluate_shadow("pump.routine_service", **bad)
        bad = {**t, "aptitudes": {**t["aptitudes"], "dexterity": True}}
        with self.assertRaises(ValueError):
            evaluate_shadow("pump.routine_service", **bad)
        with self.assertRaises(ValueError):
            evaluate_shadow("not.a.real_task", **t)


class ShadowWorldReadOnlyTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()

    def test_world_projection_is_repeatable_and_has_no_side_effects(self):
        actor = self.ship["watch"]
        event_count = CrewEvent.objects.count()
        receipt_count = WorkReceipt.objects.count()
        skill_count = CharacterSkill.objects.count()
        state = self.ship["pump"].state
        before = evaluate_world_shadow(actor, "pump.routine_service")
        again = evaluate_world_shadow(actor, "pump.routine_service")
        self.assertEqual(before, again)
        self.assertEqual(before.person_id, "crew.ari-sen")
        self.assertEqual(before.evaluation.primary_skill, 60)
        self.assertEqual(before.knowledge_source, "provisional_same_foundation_skill_proxy")
        self.assertEqual(before.familiarity_source, "not_yet_world_modelled")
        self.assertEqual(before.evaluation.familiarity, 0)
        self.assertEqual(CrewEvent.objects.count(), event_count)
        self.assertEqual(WorkReceipt.objects.count(), receipt_count)
        self.assertEqual(CharacterSkill.objects.count(), skill_count)
        self.assertEqual(self.ship["pump"].state, state)

    def test_shadow_uses_actual_person_skills_not_role_and_is_sensitive_to_aptitudes(self):
        watch = self.ship["watch"]
        chief = self.ship["chief"]
        ordinary = evaluate_world_shadow(watch, "pump.routine_service")
        veteran = evaluate_world_shadow(chief, "pump.routine_service")
        self.assertGreater(
            veteran.evaluation.provisional_score,
            ordinary.evaluation.provisional_score,
        )
        profile = profile_for_actor(watch)
        profile.aptitudes = {**profile.aptitudes, "dexterity": 10}
        profile.save(update_fields=["aptitudes"])
        new = evaluate_world_shadow(watch, "pump.routine_service")
        self.assertGreater(new.evaluation.provisional_score,
                           ordinary.evaluation.provisional_score)
        watch.db.crew_role = "captain"
        self.assertEqual(
            evaluate_world_shadow(watch, "pump.routine_service"),
            new,
        )
        self.assertFalse(watch.attributes.has("ox_skills"))

    def test_world_uses_validated_authority_and_not_unknown_causes(self):
        with self.assertRaises(ValueError):
            evaluate_world_shadow(self.ship["chief"], "nonexistent")
        actor = self.ship["captain"]
        before = CrewEvent.objects.count()
        sample = evaluate_world_shadow(actor, "analyzer.inconsistent_readings")
        self.assertEqual(sample.evaluation.mode, "shadow")
        self.assertFalse(hasattr(sample.evaluation, "hidden_cause"))
        self.assertEqual(CrewEvent.objects.count(), before)
        profile = profile_for_actor(actor)
        profile.aptitudes = {**profile.aptitudes, "reasoning": 11}
        profile.save(update_fields=["aptitudes"])
        with self.assertRaises(ValueError):
            evaluate_world_shadow(actor, "analyzer.inconsistent_readings")


if __name__ == "__main__":
    unittest.main()
