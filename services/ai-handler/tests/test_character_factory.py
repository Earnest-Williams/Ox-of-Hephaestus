"""Model-free character composition and optional Concordia lifecycle tests."""
import json
import tempfile
from pathlib import Path
import unittest
from ox_ai.agents.crew_blueprints import (
    ALL_TRAITS, CrewBlueprint, TEMPLATES, compose_blueprint, instantiate_crew,
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

if __name__ == "__main__":
    unittest.main()
