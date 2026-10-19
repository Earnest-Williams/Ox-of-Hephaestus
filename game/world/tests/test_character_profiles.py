"""World-owned identity/skill foundation; no implicit authority or progression."""
from __future__ import annotations

from copy import deepcopy

from django.db import IntegrityError, transaction
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.character_dimensions import APTITUDES, PSYCHOLOGY, validate_profile
from world.character_profiles import (
    FIXTURE_PERSON_IDS, profile_for_actor, seed_existing_crew, skill_for_actor,
)
from world.models import CharacterProfile, CharacterSkill, CharacterKnowledge, CharacterTechnique
from world.crew_initial_skills import PERSON_STARTING_SKILLS, starting_skills_for_person
from world.skill_catalogue import (
    DISCIPLINES, FOUNDATIONS, LEGACY_COMPETENCY_SKILLS, SKILLS,
    initial_skill_estimates, legacy_proficiency,
)


class CharacterFoundationWorldTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()

    def test_six_permanent_person_bindings_distinct_from_roles(self):
        self.assertEqual(CharacterProfile.objects.count(), 6)
        self.assertEqual(len(FIXTURE_PERSON_IDS), 6)
        roles = {
            "crew-chief": "chief", "crew-watch": "watch", "crew-bridge": "officer",
            "crew-cargo": "cargo", "crew-environment": "environment",
            "crew-captain": "captain",
        }
        for marker, key in roles.items():
            actor = self.ship[key]
            profile = profile_for_actor(actor)
            with self.subTest(marker=marker):
                self.assertEqual(profile.person_id, FIXTURE_PERSON_IDS[marker])
                self.assertEqual(profile.character_dbref, actor.dbref)
                self.assertEqual(profile.schema_version, 2)
                self.assertEqual(profile.source, "g4b_existing_crew")
                self.assertEqual(len(profile.aptitudes), 12)
                self.assertEqual(len(profile.psychology), 12)
                validate_profile(profile.aptitudes, profile.psychology)
                self.assertEqual(set(profile.aptitudes), set(APTITUDES))
                self.assertEqual(set(profile.psychology), set(PSYCHOLOGY))
                self.assertEqual(profile.styles, [])

    def test_catalogue_covers_current_and_future_professions(self):
        self.assertEqual(len(DISCIPLINES), 16)
        self.assertGreaterEqual(len(SKILLS), 55)
        self.assertEqual(set(skill.discipline for skill in SKILLS.values()), set(DISCIPLINES))
        for key, skill in SKILLS.items():
            with self.subTest(skill=key):
                self.assertEqual(key, skill.skill_id)
                self.assertIn(skill.foundation_id, FOUNDATIONS)
                self.assertTrue(all(a in APTITUDES for a in skill.aptitudes))
        for group, links in LEGACY_COMPETENCY_SKILLS.items():
            self.assertTrue(links, group)
            self.assertTrue(all(name in SKILLS for name in links), group)

    def test_legacy_scores_are_once_only_estimates_not_captain_permissions(self):
        self.assertEqual(skill_for_actor(self.ship["captain"], "command.ship_coordination"), 80)
        self.assertEqual(skill_for_actor(self.ship["captain"], "investigation.instrument_analysis"), 20)
        self.assertEqual(skill_for_actor(self.ship["watch"], "mechanical.pump_service"), 60)
        self.assertEqual(skill_for_actor(self.ship["chief"], "mechanical.pump_service"), 80)
        self.assertEqual(skill_for_actor(self.ship["cargo"], "freight.cargo_rigging"), 80)
        self.assertEqual(skill_for_actor(self.ship["environment"], "environmental.atmosphere_maintenance"), 80)
        self.assertFalse(self.ship["captain"].attributes.has("ox_skills"))
        self.assertEqual(
            starting_skills_for_person("crew.captain-initial")[
                "investigation.instrument_analysis"
            ], 20,
        )
        with self.assertRaises(ValueError):
            skill_for_actor(self.ship["captain"], "fake.unrecognised")
        with self.assertRaises(ValueError):
            legacy_proficiency(True)
        with self.assertRaises(ValueError):
            legacy_proficiency(5)
        self.assertEqual(
            initial_skill_estimates({"command": 3, "coordination": 4})["command.delegation"],
            80,
        )

    def test_repeated_bootstrap_preserves_developed_skills_and_baselines(self):
        actor = self.ship["watch"]
        before = profile_for_actor(actor)
        aptitudes = deepcopy(before.aptitudes)
        psychology = deepcopy(before.psychology)
        aptitudes["dexterity"] = 9
        aptitudes["agility"] = 3
        psychology["persistence"] = 92
        before.aptitudes = aptitudes
        before.psychology = psychology
        before.save(update_fields=["aptitudes", "psychology"])
        skill = CharacterSkill.objects.get(person=before, skill_id="mechanical.pump_service")
        skill.proficiency = 93
        skill.save(update_fields=["proficiency"])
        actor.db.duty_title = "Relief assignment, not original watch"
        self.assertTrue(actor.move_to(self.ship["mess"], quiet=True))
        count = CharacterSkill.objects.count()
        self.ship = build_ship()
        after = profile_for_actor(self.ship["watch"])
        self.assertEqual(after.person_id, before.person_id)
        self.assertEqual(after.aptitudes["dexterity"], 9)
        self.assertEqual(after.aptitudes["agility"], 3)
        self.assertEqual(after.psychology["persistence"], 92)
        self.assertEqual(skill_for_actor(actor, "mechanical.pump_service"), 93)
        self.assertEqual(CharacterProfile.objects.count(), 6)
        self.assertEqual(CharacterSkill.objects.count(), count)
        self.assertEqual(actor.location, self.ship["mess"])
        self.assertEqual(actor.db.duty_title, "Relief assignment, not original watch")

    def test_no_wrong_person_bindings_or_role_based_mutation(self):
        chief = self.ship["chief"]
        watch = self.ship["watch"]
        with self.assertRaises(PermissionError):
            seed_existing_crew("crew-chief", watch)
        with self.assertRaises(ValueError):
            seed_existing_crew("invented-crew", chief)
        before = skill_for_actor(watch, "mechanical.pump_service")
        watch.db.crew_role = "chief_engineer"
        seed_existing_crew("crew-watch", watch)
        self.assertEqual(skill_for_actor(watch, "mechanical.pump_service"), before)
        self.assertNotEqual(profile_for_actor(watch).person_id,
                            profile_for_actor(chief).person_id)

    def test_canonical_initial_values_are_per_person_not_job_title(self):
        self.assertEqual(len(PERSON_STARTING_SKILLS), 6)
        captain = self.ship["captain"]
        self.assertEqual(skill_for_actor(captain, "command.ship_coordination"), 80)
        self.assertEqual(skill_for_actor(captain, "investigation.instrument_analysis"), 20)
        copy = starting_skills_for_person("crew.captain-initial")
        copy["investigation.instrument_analysis"] = 99
        self.assertEqual(
            starting_skills_for_person("crew.captain-initial")[
                "investigation.instrument_analysis"
            ], 20,
        )
        with self.assertRaises(ValueError):
            starting_skills_for_person("crew.unknown")
        captain.db.crew_role = "watch_engineer"
        self.assertEqual(skill_for_actor(captain, "command.ship_coordination"), 80)
        build_ship()
        self.assertEqual(skill_for_actor(captain, "command.ship_coordination"), 80)
        self.assertFalse(captain.attributes.has("ox_skills"))

    def test_legacy_world_vector_is_converted_and_destroyed_once(self):
        captain = self.ship["captain"]
        original = profile_for_actor(captain)
        # Simulate a genuinely pre-G4d world. G4e's protected dependent
        # records must be removed in this disposable test fixture first.
        CharacterSkill.objects.filter(person=original).delete()
        CharacterKnowledge.objects.filter(person=original).delete()
        CharacterTechnique.objects.filter(person=original).delete()
        original.delete()
        # A pre-upgrade world may have actual personalised coarse estimates.
        captain.db.ox_skills = {"diagnostics": 3, "command": 2}
        seeded = seed_existing_crew("crew-captain", captain)
        self.assertEqual(seeded.person_id, "crew.captain-initial")
        self.assertEqual(
            skill_for_actor(captain, "investigation.instrument_analysis"), 60,
        )
        self.assertEqual(skill_for_actor(captain, "command.ship_coordination"), 40)
        self.assertFalse(captain.attributes.has("ox_skills"))
        CharacterSkill.objects.filter(
            person=seeded, skill_id="investigation.instrument_analysis",
        ).update(proficiency=72)
        seed_existing_crew("crew-captain", captain)
        self.assertEqual(
            skill_for_actor(captain, "investigation.instrument_analysis"), 72,
        )
        self.assertFalse(captain.attributes.has("ox_skills"))

    def test_world_db_range_and_person_identity_constraints(self):
        skill = CharacterSkill.objects.get(
            person=profile_for_actor(self.ship["captain"]),
            skill_id="investigation.instrument_analysis",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CharacterSkill.objects.filter(pk=skill.pk).update(proficiency=101)
        self.assertEqual(
            CharacterSkill.objects.get(pk=skill.pk).proficiency, 20,
        )
        profile = profile_for_actor(self.ship["captain"])
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CharacterProfile.objects.create(
                    person_id="crew.impostor",
                    character_dbref=profile.character_dbref,
                    aptitudes=profile.aptitudes,
                    psychology=profile.psychology,
                )

    def test_reject_invalid_formative_dimensions(self):
        aptitude, psych = (
            deepcopy(profile_for_actor(self.ship["captain"]).aptitudes),
            deepcopy(profile_for_actor(self.ship["captain"]).psychology),
        )
        aptitude["reasoning"] = True
        with self.assertRaises(ValueError):
            validate_profile(aptitude, psych)
        aptitude["reasoning"] = 10
        psych["persistence"] = 101
        with self.assertRaises(ValueError):
            validate_profile(aptitude, psych)


if __name__ == "__main__":
    import unittest
    unittest.main()
