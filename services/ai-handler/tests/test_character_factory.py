"""Model-free character composition and optional Concordia lifecycle tests."""
import json
import tempfile
from pathlib import Path
import unittest
from ox_ai.agents.crew_blueprints import (
    ALL_TRAITS, APTITUDES, LEGACY_TRAITS, VERSION, CrewBlueprint,
    CharacterTemplate, TEMPLATES, compose_blueprint, instantiate_crew,
)


class CharacterFactoryTests(unittest.TestCase):
    def test_from_scratch_roundtrip(self):
        p = compose_blueprint("hire.1", "New Person")
        self.assertEqual(dict(p.traits), {k: 50 for k in ALL_TRAITS})
        self.assertEqual(CrewBlueprint.from_record(json.loads(json.dumps(p.to_record()))), p)

    def test_professional_templates_and_mbti_no_double_count(self):
        p = compose_blueprint("hire.2", "Candidate",
            templates=("occupation.environmental_technician",
                       "occupation.supply_manager", "ocean.methodical", "mbti.intj"))
        self.assertEqual(dict(p.starting_skills)["equipment_inspection"], 60)
        self.assertEqual(dict(p.traits)["conscientiousness"], 85)
        self.assertEqual(len([k for k in TEMPLATES if k.startswith("mbti.")]), 16)
        self.assertEqual(len(p.styles), 2)

    def test_conflicts_need_overrides(self):
        with self.assertRaisesRegex(ValueError, "Conflicting trait"):
            compose_blueprint("hire.3", "Person",
                templates=("ocean.methodical", "ocean.collaborative"))
        p = compose_blueprint("hire.3", "Person",
            templates=("ocean.methodical", "ocean.collaborative"),
            trait_overrides={"openness": 61, "conscientiousness": 82,
                "extraversion": 48, "agreeableness": 67, "neuroticism": 31})
        self.assertEqual(dict(p.traits)["openness"], 61)

    def test_reject_bad_traits_and_templates(self):
        for kwargs in ({"trait_overrides": {"openness": True}},
                       {"trait_overrides": {"openness": 101}},
                       {"trait_overrides": {"nonsense": 5}},
                       {"skill_overrides": {"bad key": 3}},
                       {"templates": ("missing",)},
                       {"templates": ("ocean.methodical", "ocean.methodical")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                compose_blueprint("hire.4", "Person", **kwargs)
        data = compose_blueprint("hire.4", "Person").to_record()
        data["traits"]["openness"] = "high"
        with self.assertRaises(ValueError):
            CrewBlueprint.from_record(data)

    def test_world_binding_validation(self):
        p = compose_blueprint("hire.5", "Person")
        with self.assertRaises(ValueError):
            instantiate_crew(p, character_id="invalid", duty="Engineering",
                             goal="Service", model=None)

    def test_isolated_concordia_and_persistent_blueprint(self):
        try:
            from concordia.testing.mock_model import MockModel
        except ImportError:
            self.skipTest("Concordia optional dependency not installed")
        from ox_ai.agents.crew import CrewAgent
        from ox_ai.ports.base import WorldObservation
        a_profile = compose_blueprint("hire.6", "A",
            templates=("occupation.environmental_technician", "ocean.methodical"))
        b_profile = compose_blueprint("hire.7", "B",
            templates=("occupation.environmental_technician", "ocean.collaborative"))
        a = instantiate_crew(a_profile, character_id="#81", duty="Environmental",
                             goal="Maintain air", model=MockModel())
        b = instantiate_crew(b_profile, character_id="#82", duty="Environmental",
                             goal="Maintain air", model=MockModel())
        self.assertIsNot(a.entity, b.entity)
        a.observe(WorldObservation("event1", "#81", 12, "Private report"))
        with self.assertRaises(PermissionError):
            b.observe(WorldObservation("event1", "#81", 12, "Private report"))
        self.assertFalse(any("Private report" in m for m in b.memories))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "crew.json"
            a.save_checkpoint(path)
            restored = CrewAgent.from_checkpoint(path, MockModel())
            self.assertEqual(restored.blueprint, a_profile)
            self.assertEqual(restored.identity.character_id, "#81")
            self.assertIn("Private report", " ".join(restored.memories))
            data = json.loads(path.read_text())
            data["character_blueprint"]["person_id"] = "other"
            path.write_text(json.dumps(data))
            with self.assertRaises(PermissionError):
                CrewAgent.from_checkpoint(path, MockModel())

    def test_v2_has_separate_twelve_aptitudes_and_psychology(self):
        p = compose_blueprint(
            "hire.v2", "Technician", templates=("mbti.intj",),
            aptitude_overrides={"dexterity": 9, "agility": 3, "reasoning": 10},
            trait_overrides={"persistence": 84, "isolation_tolerance": 75},
        )
        self.assertEqual(VERSION, 2)
        self.assertEqual(len(APTITUDES), 12)
        self.assertEqual(len(ALL_TRAITS), 12)
        self.assertEqual(dict(p.aptitudes)["dexterity"], 9)
        self.assertEqual(dict(p.aptitudes)["agility"], 3)
        self.assertEqual(dict(p.aptitudes)["reasoning"], 10)
        self.assertEqual(dict(p.traits)["persistence"], 84)
        self.assertEqual(dict(p.traits)["isolation_tolerance"], 75)
        self.assertEqual(p.to_record()["version"], 2)
        self.assertEqual(CrewBlueprint.from_record(p.to_record()), p)
        self.assertIn("Formative aptitudes", p.cognition_context())
        self.assertIn("MBTI-inspired INTJ", p.cognition_context())

    def test_upgrade_exact_v1_record_without_rewriting_history(self):
        original = compose_blueprint(
            "hire.legacy", "Experienced Worker",
            templates=("occupation.environmental_technician", "ocean.methodical"),
            history=("Previously served on a cargo hauler",),
        )
        raw = original.to_record()
        raw["version"] = 1
        del raw["aptitudes"]
        raw["traits"] = {k: raw["traits"][k] for k in LEGACY_TRAITS}
        unchanged_v1 = json.dumps(raw, sort_keys=True)
        upgraded = CrewBlueprint.from_record(raw)
        self.assertEqual(json.dumps(raw, sort_keys=True), unchanged_v1)
        self.assertEqual(upgraded.person_id, original.person_id)
        self.assertEqual(upgraded.name, original.name)
        self.assertEqual(upgraded.starting_skills, original.starting_skills)
        self.assertEqual(upgraded.history, original.history)
        self.assertEqual(upgraded.template_ids, original.template_ids)
        self.assertEqual(dict(upgraded.traits)["persistence"], 50)
        self.assertEqual(dict(upgraded.traits)["isolation_tolerance"], 50)
        self.assertTrue(all(value == 5 for value in dict(upgraded.aptitudes).values()))
        self.assertEqual(upgraded.to_record()["version"], 2)

    def test_reject_malformed_v2_and_v1_migrations(self):
        for invalid in (
            {"aptitude_overrides": {"dexterity": 0}},
            {"aptitude_overrides": {"agility": 11}},
            {"aptitude_overrides": {"reasoning": True}},
            {"aptitude_overrides": {"imaginary": 5}},
            {"trait_overrides": {"persistence": 101}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                compose_blueprint("hire.invalid", "Person", **invalid)
        record = compose_blueprint("hire.valid", "Person").to_record()
        import copy
        for field, value in (("dexterity", 0), ("agility", 11), ("memory", True)):
            broken = copy.deepcopy(record)
            broken["aptitudes"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                CrewBlueprint.from_record(broken)
        v1 = copy.deepcopy(record)
        v1["version"] = 1
        del v1["aptitudes"]
        v1["traits"] = {k: v1["traits"][k] for k in LEGACY_TRAITS}
        for change in ("missing", "extra", "unknown-version"):
            malformed = copy.deepcopy(v1)
            if change == "missing":
                del malformed["traits"]["openness"]
            elif change == "extra":
                malformed["traits"]["persistence"] = 70
            else:
                malformed["version"] = 99
            with self.subTest(change=change), self.assertRaises(ValueError):
                CrewBlueprint.from_record(malformed)

    def test_template_aptitudes_conflict_require_explicit_override(self):
        import copy
        old_templates = dict(TEMPLATES)
        try:
            TEMPLATES["occupation.fine_motor"] = CharacterTemplate(
                "occupation.fine_motor", "occupation", aptitudes=(("dexterity", 8),)
            )
            TEMPLATES["occupation.clumsy"] = CharacterTemplate(
                "occupation.clumsy", "occupation", aptitudes=(("dexterity", 3),)
            )
            with self.assertRaisesRegex(ValueError, "Conflicting aptitude"):
                compose_blueprint(
                    "hire.conflict", "Person",
                    templates=("occupation.fine_motor", "occupation.clumsy"),
                )
            p = compose_blueprint(
                "hire.conflict", "Person",
                templates=("occupation.fine_motor", "occupation.clumsy"),
                aptitude_overrides={"dexterity": 7},
            )
            self.assertEqual(dict(p.aptitudes)["dexterity"], 7)
        finally:
            TEMPLATES.clear()
            TEMPLATES.update(old_templates)

if __name__ == "__main__":
    unittest.main()
