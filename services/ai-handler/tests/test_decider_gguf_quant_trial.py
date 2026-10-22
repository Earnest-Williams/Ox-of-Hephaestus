"""Pure offline tests for genuine option-logit Decider GGUF adapter."""
from __future__ import annotations

import unittest

from scenarios.decider_gguf_quant_trial import GGUFChoiceModel, run


class FakeEngine:
    def __init__(self, invalid=False):
        self.invalid = invalid
        self.requests = []

    def system_one(self, state, questions):
        self.requests.append((state, questions))
        opts = questions["next_action"]["criteria"]
        keys = list(opts)
        if self.invalid:
            keys[0] = "not_offered"
        return {"answers": {"next_action": {
            "type": "choice", "choice": keys[0],
            "probabilities": {k: (1.0 if i == 0 else 0.0)
                              for i, k in enumerate(opts)},
        }}}


class GGUFQuantTests(unittest.TestCase):
    def test_native_choice_uses_typed_option_logits_not_text(self):
        engine = FakeEngine()
        model = GGUFChoiceModel(engine, ("Inspect gauge", "Defer"))
        i, choice, _ = model.sample_choice("Current evidence", ["a", "b"])
        self.assertEqual((i, choice), (0, "a"))
        self.assertEqual(model.calls, 1)
        payload = engine.requests[0][1]
        self.assertEqual(payload["next_action"]["criteria"],
                         {"a": "Inspect gauge", "b": "Defer"})
        with self.assertRaisesRegex(RuntimeError, "never generate"):
            model.sample_text("Please improvise")

    def test_fails_closed_for_unoffered_decisions(self):
        engine = FakeEngine(invalid=True)
        model = GGUFChoiceModel(engine, ("Inspect", "Defer"))
        with self.assertRaisesRegex(ValueError, "Invalid Decider"):
            model.sample_choice("Current evidence", ("a", "b"))
        self.assertEqual(model.calls, 0)

    def test_bounded_4_g11_and_24_counterfactual_pairs(self):
        try:
            from concordia.testing.mock_model import MockModel
        except ImportError:
            self.skipTest("Native Concordia optional extra not installed")
        del MockModel
        engine = FakeEngine()
        report = run(engine, quant="Q2_K", checkpoint={
            "quant": "Q2_K", "gguf_file": "fixture.gguf",
            "repo_revision": "test-checkpoint",
        }, max_pairs=24)
        self.assertEqual(len(report["g11"]["rows"]), 8)
        self.assertEqual(report["counterfactual"]["decisions"], 48)
        self.assertEqual(report["counterfactual"]["pairs"], 24)
        self.assertEqual(report["counterfactual"]["correct"], 24)
        self.assertEqual(report["counterfactual"]["both_correct_pairs"], 0)
        self.assertEqual(report["world_commands_sent"], 0)
        self.assertEqual(report["world_receipts_received"], 0)
        self.assertEqual(len(engine.requests), 56)

    def test_quant_and_case_bounds(self):
        with self.assertRaisesRegex(ValueError, "quantisation"):
            run(FakeEngine(), quant="Q1", checkpoint={}, max_pairs=24)
        with self.assertRaisesRegex(ValueError, "quantisation"):
            run(FakeEngine(), quant="Q4_K_M", checkpoint={}, max_pairs=25)


if __name__ == "__main__":
    unittest.main()
