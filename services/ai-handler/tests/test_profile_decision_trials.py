"""Profile choice evidence, without pretending a deterministic fixture is cognition."""
import unittest

from ox_ai.agents.crew import CommandOption
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.agents.decision_trials import (
    DecisionScenario, SCENARIOS, compare_profiles, representative_profiles,
)


class TrialBoundaryTests(unittest.TestCase):
    def test_invalid_scenarios_and_repeats_refused(self):
        for options in (
            (CommandOption("Only choice", "inspect"),),
            (CommandOption("Same", "inspect"), CommandOption("Same", "defer")),
            (CommandOption("One", "inspect"), CommandOption("Two", "inspect")),
        ):
            with self.assertRaises(ValueError):
                DecisionScenario("bad", "A valid observation", options)
        with self.assertRaises(ValueError):
            compare_profiles(representative_profiles(), model_factory=lambda: None,
                             repeats=0)
        with self.assertRaises(ValueError):
            compare_profiles({"only": compose_blueprint("one", "Person")},
                             model_factory=lambda: None)

    def test_shared_starting_skills_and_distinct_personality(self):
        cohort = representative_profiles()
        a, b = cohort["methodical"], cohort["collaborative"]
        self.assertEqual(a.starting_skills, b.starting_skills)
        self.assertNotEqual(a.traits, b.traits)
        self.assertEqual(SCENARIOS[0].options[0].verb, "inspect")


try:
    from concordia.testing.mock_model import MockModel
except ImportError:
    MockModel = None


@unittest.skipIf(MockModel is None, "Pinned Concordia optional dependency unavailable")
class NativeConcordiaDecisionTests(unittest.TestCase):
    def test_real_concordia_same_options_mock_is_not_personality_sensitive(self):
        report = compare_profiles(representative_profiles(),
                                  model_factory=MockModel, repeats=3)
        self.assertEqual(report["world_actions_submitted"], 0)
        self.assertEqual(report["total_inference_calls"], 12)
        self.assertEqual(report["profiles"]["methodical"],
                         report["profiles"]["collaborative"])
        self.assertEqual(report["profiles"]["methodical"]["uncertain_reading"],
                         {"Inspect another local instrument": 3})

    def test_profile_context_reaches_real_concordia_prompt_and_changes_proposal(self):
        prompts = []
        class ProfileProbeModel:
            """Synthetic profile-responsive model, not evidence of real intelligence."""
            def sample_choice(self, prompt, responses, *, seed=None):
                prompts.append(prompt)
                # Same options, same order, same situation; profile text is
                # the only condition in this intentionally synthetic fixture.
                chosen = 1 if "agreeableness=85" in prompt else 0
                return chosen, responses[chosen], {}
            def sample_text(self, prompt, **kwargs):
                raise AssertionError("Choice-only scenario must not generate text")

        report = compare_profiles(representative_profiles(),
            model_factory=ProfileProbeModel, repeats=4)
        self.assertEqual(report["world_actions_submitted"], 0)
        self.assertEqual(report["profiles"]["methodical"]["uncertain_reading"],
                         {"Inspect another local instrument": 4})
        self.assertEqual(report["profiles"]["collaborative"]["uncertain_reading"],
                         {"Ask a colleague to independently check": 4})
        self.assertEqual(len(prompts), 16)
        self.assertTrue(any("agreeableness=85" in x for x in prompts))
        self.assertTrue(any("agreeableness=60" in x for x in prompts))

    def test_malformed_model_cannot_invent_world_action(self):
        class UnauthorizedModel:
            def sample_choice(self, prompt, responses, *, seed=None):
                return 100, "Open unrestricted world admin interface", {}
            def sample_text(self, prompt, **kwargs):
                raise AssertionError
        with self.assertRaises((ValueError, IndexError)):
            compare_profiles(representative_profiles(),
                model_factory=UnauthorizedModel, repeats=1, scenarios=(SCENARIOS[0],))


    def test_profiled_live_slots_preserve_individual_names_and_identity(self):
        import json
        import tempfile
        from pathlib import Path
        from ox_ai.agents.live_concordia import LiveCrewBrain, build_live_brains
        profiles = representative_profiles()
        ids = {"lin": "#101", "ari": "#102", "iona": "#103",
               "mara": "#104", "teo": "#105"}
        assigned = build_live_brains(ids, blueprints={"teo": profiles["collaborative"]})
        self.assertEqual(assigned["teo"].agent.identity.name, "Collaborative Candidate")
        self.assertEqual(assigned["teo"].agent.identity.agent_id,
                         "ox.person.probe.collaborative")
        self.assertEqual(assigned["mara"].agent.identity.agent_id, "ox.live.mara")
        self.assertEqual(assigned["teo"].role, "teo")
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "teo.json"
            assigned["teo"].save_checkpoint(file)
            restored = LiveCrewBrain.from_checkpoint("teo", "#105", MockModel(), file)
            self.assertEqual(restored.agent.blueprint, profiles["collaborative"])
            with self.assertRaises(PermissionError):
                LiveCrewBrain.from_checkpoint("teo", "#999", MockModel(), file)
            state = json.loads(file.read_text())
            state["identity"]["agent_id"] = "ox.person.someone_else"
            file.write_text(json.dumps(state))
            with self.assertRaises(PermissionError):
                LiveCrewBrain.from_checkpoint("teo", "#105", MockModel(), file)
        with self.assertRaises(ValueError):
            build_live_brains(ids, blueprints={"mara": profiles["methodical"],
                                              "teo": profiles["methodical"]})
        with self.assertRaises(ValueError):
            build_live_brains(ids, blueprints={"not-a-role": profiles["methodical"]})


if __name__ == "__main__":
    unittest.main()
