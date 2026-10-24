"""G16h: reject 24-pair position confound without requiring model weights."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

try:
    import ox_ai
except ImportError:
    ox_ai = None


@unittest.skipUnless(
    ox_ai is not None and importlib.util.find_spec("concordia") is not None,
    "Optional pinned Concordia not installed in the minimal service scaffold",
)
class BalancedComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scenarios"))
        import g16h_balanced_model_comparison as comparison
        cls.cmp = comparison

    def test_original_g11_cases_retain_expected_semantic_reversals(self):
        cases = self.cmp.fixtures()
        self.assertEqual(len(cases), 24)
        self.assertEqual(len({x.name for x in cases}), 24)
        for case in cases:
            self.assertEqual(case.expected_earlier, case.first_verb)
            self.assertEqual(case.expected_changed, case.second_verb)
            self.assertNotEqual(case.first_verb, case.second_verb)

    def test_two_pass_score_averages_semantic_not_display_position(self):
        c = self.cmp
        cases = c.fixtures()
        case = cases[0]
        first = c.BalancedBinaryDecider(
            c.FirstCodeNativeFixture(),
            ((case.first_verb, case.first_option),
             (case.second_verb, case.second_option)),
        )
        reverse = c.BalancedBinaryDecider(
            c.FirstCodeNativeFixture(),
            ((case.second_verb, case.second_option),
             (case.first_verb, case.first_option)),
        )
        first.sample_choice("Same actor evidence", ("A","B"))
        reverse.sample_choice("Same actor evidence", ("A","B"))
        self.assertEqual(first.last["selected_semantic_key"],
                         reverse.last["selected_semantic_key"])
        self.assertEqual(first.last["semantic_scores"],
                         reverse.last["semantic_scores"])
        self.assertEqual(first.last["native_forwards"], 2)
        self.assertEqual(len(first.last["passes"]), 2)
        for key, prob in first.last["semantic_scores"].items():
            self.assertAlmostEqual(prob, .5)
        self.assertEqual(
            {x["code_positions"][0] for x in first.last["passes"]},
            set(first.last["semantic_scores"]),
        )

    def test_complete_fixture_has_equal_expected_action_position_coverage(self):
        outcome = self.cmp.run("fixture-decider")
        self.assertFalse(outcome["real_native_measurement"])
        self.assertTrue(outcome["fake_provider"])
        self.assertEqual(outcome["candidate_decisions"], 96)
        self.assertEqual(outcome["model_forwards"], 192)
        self.assertEqual(
            [x["count"] for x in outcome["expected_position_accuracy"].values()],
            [48,48],
        )
        self.assertEqual(outcome["source_case_count"], 24)
        self.assertEqual(len(outcome["rows"]), 96)
        self.assertEqual(outcome["world_commands_sent"], 0)
        self.assertEqual(outcome["world_receipts_claimed"], 0)
        self.assertFalse(outcome["adopted_model_decision"])

    def test_reject_invalid_two_option_native_scorer_menus(self):
        scorer = self.cmp.BalancedBinaryDecider
        with self.assertRaises(ValueError):
            scorer(self.cmp.FirstCodeNativeFixture(),
                   (("same","one"),("same","two")))
        with self.assertRaises(ValueError):
            scorer(self.cmp.FirstCodeNativeFixture(),
                   (("first","same"),("second","same")))
        with self.assertRaises(ValueError):
            scorer(self.cmp.FirstCodeNativeFixture(),
                   (("one","one"),))
        model = scorer(self.cmp.FirstCodeNativeFixture(),
                       (("first","first"),("second","second")))
        with self.assertRaises(ValueError):
            model.sample_choice("Prompt", ("A","A"))

if __name__ == "__main__":
    unittest.main()
