"""G16h: reject 24-pair position confound without requiring model weights."""
from __future__ import annotations

from copy import deepcopy
import json
import tempfile
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

    def test_independent_aggregate_rejects_fake_and_balances_all_rows(self):
        import g16h_compare_results as aggregate
        source = self.cmp.run("fixture-decider")
        with tempfile.TemporaryDirectory() as root:
            dfile = Path(root) / "decider.json"
            qfile = Path(root) / "qwen.json"
            dfile.write_text(json.dumps(source))
            qfile.write_text(json.dumps(source))
            with self.assertRaises(PermissionError):
                aggregate.compare(dfile, qfile)
            # Pure schema exercise: these copies deliberately remain
            # deterministic *test* data, not native quality evidence.
            decider = deepcopy(source)
            decider["provider"] = "decider-q4"
            decider["fake_provider"] = False
            decider["real_native_measurement"] = True
            decider["model_provenance"] = {
                "model": "decider-q4",
                "sha256": aggregate.DECIDER_GGUF_SHA256,
                "hf_revision": aggregate.DECIDER_WEIGHT_REVISION,
                "tokenizer_revision": aggregate.DECIDER_TOKENIZER_REVISION,
                "size": 2708804928,
            }
            qwen = deepcopy(source)
            qwen["provider"] = "qwen3.5-4b"
            qwen["fake_provider"] = False
            qwen["real_native_measurement"] = True
            qwen["model_provenance"] = {
                "model": "qwen3.5-4b",
                "sha256": aggregate.QWEN_GGUF_SHA256,
            }
            qwen["model_forwards"] = 96
            for row in qwen["rows"]:
                row["native_passes"] = 1
                row["scorer_record"] = None
            dfile.write_text(json.dumps(decider))
            qfile.write_text(json.dumps(qwen))
            result = aggregate.compare(dfile, qfile)
            self.assertEqual(result["matched_bounded_decisions_per_model"], 96)
            self.assertEqual(result["caller_positions_for_expected_answer"],
                             {"0":48, "1":48})
            self.assertFalse(result["production_personality_flag_enabled"])
            self.assertIsNone(result["selected_production_action_scorer"])
            # Explicit adversarial controls; mutating BOTH model records
            # must not be able to rewrite authored expected world evidence.
            for field, replacement in (
                ("expected", "a_forged_correct_action"),
                ("observed_sha256", "0" * 64),
                ("recollection_sha256", "0" * 64),
            ):
                changed_decider = deepcopy(decider)
                changed_qwen = deepcopy(qwen)
                changed_decider["rows"][0][field] = replacement
                changed_qwen["rows"][0][field] = replacement
                dfile.write_text(json.dumps(changed_decider))
                qfile.write_text(json.dumps(changed_qwen))
                with self.subTest(field=field), self.assertRaises(PermissionError):
                    aggregate.compare(dfile, qfile)
            changed_qwen = deepcopy(qwen)
            changed_qwen["model_provenance"]["sha256"] = "f" * 64
            dfile.write_text(json.dumps(decider))
            qfile.write_text(json.dumps(changed_qwen))
            with self.assertRaises(PermissionError):
                aggregate.compare(dfile, qfile)
            changed_decider = deepcopy(decider)
            keys = changed_decider["rows"][0]["offered_verb_order"]
            changed_decider["rows"][0]["scorer_record"]["semantic_scores"] = {
                keys[0]: .65, keys[1]: .35,
            }
            # A forged mean cannot replace the actual two native pass means.
            dfile.write_text(json.dumps(changed_decider))
            qfile.write_text(json.dumps(qwen))
            with self.assertRaises(ValueError):
                aggregate.compare(dfile, qfile)

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
