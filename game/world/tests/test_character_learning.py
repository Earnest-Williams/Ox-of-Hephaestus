"""Separate conceptual knowledge and personally learned equipment familiarity."""
from __future__ import annotations

import json
from django.db import IntegrityError, transaction
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.captain import captain_qualified_observation
from world.capabilities import local_capabilities
from world.character_profiles import (
    familiarity_for_actor, knowledge_for_actor, profile_for_actor, skill_for_actor,
)
from world.crew_initial_learning import (
    PERSON_STARTING_FOUNDATIONS, PERSON_STARTING_TECHNIQUES,
    starting_foundations_for_person, starting_techniques_for_person,
)
from world.investigation import arm_anomaly
from world.models import CharacterKnowledge, CharacterTechnique, CharacterSkill
from world.skill_catalogue import FOUNDATIONS
from world.task_resolution import TASKS
from world.task_shadow import evaluate_world_shadow
from world.technique_catalogue import TECHNIQUES

NONCE = "c" * 32


class KnowledgeAndEquipmentWorldTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()

    def test_all_six_people_have_independent_persistent_initial_records(self):
        self.assertEqual(len(PERSON_STARTING_FOUNDATIONS), 6)
        self.assertEqual(len(PERSON_STARTING_TECHNIQUES), 6)
        self.assertEqual(
            CharacterKnowledge.objects.count(),
            sum(len(x) for x in PERSON_STARTING_FOUNDATIONS.values()),
        )
        self.assertEqual(
            CharacterTechnique.objects.count(),
            sum(len(x) for x in PERSON_STARTING_TECHNIQUES.values()),
        )
        for actor in (self.ship[k] for k in
                      ("chief", "watch", "officer", "cargo", "environment", "captain")):
            person = profile_for_actor(actor)
            with self.subTest(person=person.person_id):
                self.assertEqual(
                    set(person.knowledge_records.values_list("foundation_id", flat=True)),
                    set(starting_foundations_for_person(person.person_id)),
                )
                self.assertEqual(
                    set(person.technique_records.values_list("technique_id", flat=True)),
                    set(starting_techniques_for_person(person.person_id)),
                )
                self.assertTrue(all(
                    item.source == "g4e_initial_estimate"
                    for item in person.knowledge_records.all()
                ))
                self.assertTrue(all(
                    item.source == "g4e_initial_estimate"
                    for item in person.technique_records.all()
                ))
        self.assertFalse(self.ship["watch"].attributes.has("ox_skills"))

    def test_all_task_techniques_have_exactly_defined_fixture_and_skill(self):
        for name, task in TASKS.items():
            with self.subTest(task=name):
                self.assertIn(task.technique_id, TECHNIQUES)
                definition = TECHNIQUES[task.technique_id]
                self.assertEqual(definition.relevant_skill_id, task.skill_id)
                self.assertTrue(definition.fixture_marker)
        self.assertEqual(
            TECHNIQUES["pump.p01.routine_service"].fixture_marker, "pump-p01",
        )
        self.assertEqual(
            TECHNIQUES["pump.p01.unfamiliar_repair"].fixture_marker, "pump-p01",
        )
        self.assertNotEqual(
            TASKS["pump.routine_service"].technique_id,
            TASKS["pump.unfamiliar_repair"].technique_id,
        )

    def test_skill_knowledge_and_technique_can_change_independently(self):
        watch = self.ship["watch"]
        person = profile_for_actor(watch)
        skill_before = skill_for_actor(watch, "mechanical.pump_service")
        knowledge_before = knowledge_for_actor(watch, "mechanical.rotating_machinery")
        technique_before = familiarity_for_actor(watch, "pump.p01.routine_service")
        self.assertEqual((skill_before, knowledge_before, technique_before),
                         (60, 55, 60))
        CharacterKnowledge.objects.filter(
            person=person, foundation_id="mechanical.rotating_machinery",
        ).update(mastery=85)
        self.assertEqual(
            knowledge_for_actor(watch, "mechanical.rotating_machinery"), 85,
        )
        self.assertEqual(skill_for_actor(watch, "mechanical.pump_service"), 60)
        self.assertEqual(
            familiarity_for_actor(watch, "pump.p01.routine_service"), 60,
        )
        CharacterTechnique.objects.filter(
            person=person, technique_id="pump.p01.routine_service",
        ).update(familiarity=20)
        self.assertEqual(
            familiarity_for_actor(watch, "pump.p01.routine_service"), 20,
        )
        self.assertEqual(
            knowledge_for_actor(watch, "mechanical.rotating_machinery"), 85,
        )
        self.assertEqual(skill_for_actor(watch, "mechanical.pump_service"), 60)

    def test_equally_skilled_engineers_can_differ_by_theory_or_machine(self):
        watch = self.ship["watch"]
        chief = self.ship["chief"]
        for actor in (watch, chief):
            person = profile_for_actor(actor)
            CharacterSkill.objects.filter(
                person=person, skill_id="mechanical.pump_service",
            ).update(proficiency=60)
            CharacterTechnique.objects.filter(
                person=person, technique_id="pump.p01.routine_service",
            ).update(familiarity=50)
        low = evaluate_world_shadow(watch, "pump.routine_service")
        high = evaluate_world_shadow(chief, "pump.routine_service")
        self.assertEqual(low.evaluation.primary_skill, high.evaluation.primary_skill)
        self.assertEqual(low.evaluation.familiarity, high.evaluation.familiarity)
        self.assertEqual(low.evaluation.aptitude_score, high.evaluation.aptitude_score)
        self.assertEqual(low.evaluation.conceptual_knowledge, 55)
        self.assertEqual(high.evaluation.conceptual_knowledge, 75)
        self.assertAlmostEqual(
            high.evaluation.provisional_score - low.evaluation.provisional_score, 3.0,
        )
        CharacterKnowledge.objects.filter(
            person=profile_for_actor(chief),
            foundation_id="mechanical.rotating_machinery",
        ).update(mastery=55)
        CharacterTechnique.objects.filter(
            person=profile_for_actor(chief),
            technique_id="pump.p01.routine_service",
        ).update(familiarity=90)
        now = evaluate_world_shadow(chief, "pump.routine_service")
        self.assertEqual(now.evaluation.conceptual_knowledge, 55)
        self.assertEqual(now.evaluation.familiarity, 90)
        self.assertGreater(now.evaluation.provisional_score,
                           low.evaluation.provisional_score)

    def test_procedure_is_specific_not_a_generic_pump_bonus(self):
        watch = self.ship["watch"]
        person = profile_for_actor(watch)
        before = evaluate_world_shadow(watch, "pump.unfamiliar_repair")
        routine_before = evaluate_world_shadow(watch, "pump.routine_service")
        CharacterTechnique.objects.filter(
            person=person, technique_id="pump.p01.routine_service",
        ).update(familiarity=100)
        self.assertEqual(
            evaluate_world_shadow(watch, "pump.unfamiliar_repair"), before,
        )
        routine_after = evaluate_world_shadow(watch, "pump.routine_service")
        self.assertGreater(routine_after.evaluation.provisional_score,
                           routine_before.evaluation.provisional_score)

    def test_exceptional_reasoning_and_practical_skill_do_not_create_theory(self):
        watch = self.ship["watch"]
        person = profile_for_actor(watch)
        CharacterSkill.objects.filter(
            person=person, skill_id="mechanical.vibration_diagnostics",
        ).update(proficiency=100)
        person.aptitudes = {**person.aptitudes, "reasoning": 10,
                            "attention": 10, "perception": 10}
        person.save(update_fields=["aptitudes"])
        CharacterKnowledge.objects.filter(
            person=person, foundation_id="mechanical.rotating_machinery",
        ).update(mastery=0)
        evaluated = evaluate_world_shadow(watch, "pump.novel_interference")
        self.assertEqual(evaluated.evaluation.primary_skill, 100)
        self.assertEqual(evaluated.evaluation.aptitude_score, 100)
        self.assertEqual(evaluated.evaluation.conceptual_knowledge, 0)
        self.assertFalse(evaluated.evaluation.theoretical_foothold)

    def test_missing_knowledge_does_not_fall_back_to_related_practical_skill(self):
        captain = self.ship["captain"]
        self.assertEqual(knowledge_for_actor(captain, "mechanical.rotating_machinery"), 0)
        self.assertEqual(familiarity_for_actor(captain, "pump.p01.routine_service"), 0)
        self.assertGreater(skill_for_actor(captain, "mechanical.pump_service"), 0)
        shadow = evaluate_world_shadow(captain, "pump.novel_interference")
        self.assertEqual(shadow.evaluation.conceptual_knowledge, 0)
        self.assertEqual(shadow.evaluation.familiarity, 0)
        self.assertEqual(shadow.knowledge_source, "not_recorded")
        self.assertEqual(shadow.familiarity_source, "not_recorded")
        for f in ("wrong", "", None):
            with self.subTest(foundation=f), self.assertRaises(ValueError):
                knowledge_for_actor(captain, f)
        with self.assertRaises(ValueError):
            familiarity_for_actor(captain, "pump.p01.unknown")

    def test_repeated_bootstrap_preserves_individually_updated_learning(self):
        chief = self.ship["chief"]
        person = profile_for_actor(chief)
        CharacterKnowledge.objects.filter(
            person=person, foundation_id="mechanical.rotating_machinery",
        ).update(mastery=99, source="verified_world_instruction")
        CharacterTechnique.objects.filter(
            person=person, technique_id="pump.p01.routine_service",
        ).update(familiarity=98, source="verified_world_practice")
        count_knowledge = CharacterKnowledge.objects.count()
        count_techniques = CharacterTechnique.objects.count()
        chief.db.crew_role = "cargo_officer"
        build_ship()
        self.assertEqual(CharacterKnowledge.objects.count(), count_knowledge)
        self.assertEqual(CharacterTechnique.objects.count(), count_techniques)
        know = CharacterKnowledge.objects.get(
            person=person, foundation_id="mechanical.rotating_machinery",
        )
        proc = CharacterTechnique.objects.get(
            person=person, technique_id="pump.p01.routine_service",
        )
        self.assertEqual((know.mastery, know.source), (99, "verified_world_instruction"))
        self.assertEqual((proc.familiarity, proc.source), (98, "verified_world_practice"))

    def test_knowledge_and_familiarity_alone_cannot_grant_captain_inspection(self):
        captain = self.ship["captain"]
        person = profile_for_actor(captain)
        CharacterKnowledge.objects.filter(
            person=person, foundation_id="investigation.methods",
        ).update(mastery=100)
        CharacterTechnique.objects.filter(
            person=person, technique_id="captain.bridge.instrument_review",
        ).update(familiarity=100)
        ticket = arm_anomaly(cause="scrubber_bypass", seed=6)
        self.assertIsNone(captain_qualified_observation(captain, ticket))
        self.assertEqual(skill_for_actor(captain, "investigation.instrument_analysis"), 20)

    def test_private_learning_values_are_not_publicly_exposed(self):
        captain = self.ship["captain"]
        cap = local_capabilities(captain, NONCE)
        payload = json.dumps(cap).lower()
        for secret in ("characterknowledge", "charactertechnique",
                       "foundation_id", "technique_id", "mastery", "familiarity"):
            self.assertNotIn(secret, payload)

    def test_db_enforces_unique_per_person_and_bounded_scores(self):
        person = profile_for_actor(self.ship["watch"])
        know = CharacterKnowledge.objects.get(
            person=person, foundation_id="mechanical.rotating_machinery",
        )
        proc = CharacterTechnique.objects.get(
            person=person, technique_id="pump.p01.routine_service",
        )
        for obj, field in ((know, "mastery"), (proc, "familiarity")):
            with self.subTest(field=field), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    type(obj).objects.filter(pk=obj.pk).update(**{field: 101})
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CharacterKnowledge.objects.create(
                    person=person, foundation_id=know.foundation_id, mastery=20,
                )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CharacterTechnique.objects.create(
                    person=person, technique_id=proc.technique_id, familiarity=20,
                )


if __name__ == "__main__":
    import unittest
    unittest.main()
