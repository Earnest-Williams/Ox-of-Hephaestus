"""Contract checks for the opt-in paired, Decider-only behavioural assay."""
import asyncio
import unittest

from ox_ai.scenarios.personality_dilemmas import (
    DILEMMAS, PERSONAS, FixtureFirstChoice, coverage_seed,
    profile_for, run_dossier,
)
from ox_ai.runtime.personality_routing import PersonalityRouter


class PersonalityDilemmaTests(unittest.TestCase):
    def test_scenarios_have_distinct_authorized_menu_signatures(self):
        self.assertEqual(len(DILEMMAS), 4)
        for scenario in DILEMMAS:
            self.assertGreaterEqual(len(scenario.choices), 3)
            self.assertEqual(scenario.procedure.verb, scenario.choices[0].verb)
            self.assertEqual(scenario.procedure.target, scenario.choices[0].target)
            signatures = [(c.verb, c.target, tuple(sorted(c.arguments.items())))
                          for c in scenario.choices]
            self.assertEqual(len(signatures), len(set(signatures)))
        self.assertEqual(len(PERSONAS), 3)

    def test_coverage_seed_is_stable_and_character_local(self):
        situation = DILEMMAS[0]
        for persona, data in PERSONAS.items():
            profile = profile_for(persona)
            boundary = "fixture." + situation.key + ".procedure"
            seed = coverage_seed(profile, data["actor"], boundary,
                                 situation.state, situation.kind)
            router = PersonalityRouter(profile, data["actor"], {}, seed=seed)
            self.assertLess(router._draw(boundary),
                            router.probability(situation.state, situation.kind))

    def test_fixture_covers_all_pairs_without_world_action(self):
        result = asyncio.run(run_dossier(model_name="fixture"))
        self.assertEqual(result["world_commands_sent"], 0)
        self.assertEqual(len(result["rows"]), 48)
        self.assertEqual(len(result["paired"]), 24)
        self.assertEqual(len(result["order_invariant"]), 24)
        self.assertEqual(result["model_generated_reasons"], False)
        self.assertEqual({r["route"] for r in result["rows"]}, {"llm"})
        self.assertEqual({r["chosen_position"] for r in result["rows"]}, {0})
        self.assertEqual({r["order"] for r in result["rows"]}, {"canonical", "reversed"})
        self.assertEqual({r["case"] for r in result["rows"]}, {d.key for d in DILEMMAS})
        self.assertEqual({r["model_calls"] for r in result["rows"]}, {1})
        self.assertTrue(all(r["same_route_roll"] for r in result["paired"]))
        self.assertFalse(any(r["memory_changed_choice"] for r in result["paired"]))
        self.assertFalse(any(r["same_choice_across_order"] for r in result["order_invariant"]))

    def test_only_selected_engine_and_explicit_fixture_supported(self):
        with self.assertRaises(ValueError):
            asyncio.run(run_dossier(model_name="qwen-q4"))


if __name__ == "__main__":
    unittest.main()
