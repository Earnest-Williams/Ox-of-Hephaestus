"""Offline tests for typed decision-model integration; no model downloads."""
from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from scenarios.decision_models_trial import OllayaChoiceModel, localhost_api, run


class DecisionHeadTests(unittest.TestCase):
    def test_nonlocalhost_api_rejected(self):
        for endpoint in (
            "https://127.0.0.1:11435",
            "http://example.com:11435",
            "http://127.0.0.1:11435/remote",
            "http://user:pass@localhost:11435",
            "http://localhost.evil.test:11435",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                localhost_api(endpoint)

    def test_reject_unknown_and_empty_menus(self):
        with self.assertRaises(ValueError):
            OllayaChoiceModel("unknown", ("a", "b"), localhost_api("http://localhost"))
        model = OllayaChoiceModel("laya:en", ("only one",),
                                  localhost_api("http://localhost"))
        with self.assertRaises(ValueError):
            model.sample_choice("prompt", ("a",))

    def test_choice_scores_are_checked_before_action_is_accepted(self):
        good = {
            "model": "laya:en",
            "state_truncated": False,
            "answers": {"next_action": {
                "type": "choice", "choice": "a", "confidence": .8,
                "probabilities": {"a": .8, "b": .2},
            }},
            "usage": {"input_tokens": 100},
            "eval_duration": 10000,
        }
        model = OllayaChoiceModel("laya:en", ("Inspect gauge", "Wait"),
                                  localhost_api("http://127.0.0.1:11435"))
        with patch("scenarios.decision_models_trial.urlopen",
                   return_value=io.BytesIO(json.dumps(good).encode())) as request:
            idx, choice, _ = model.sample_choice("What next?", ("a", "b"))
        self.assertEqual((idx, choice), (0, "a"))
        self.assertEqual(model.calls, 1)
        sent = json.loads(request.call_args.args[0].data)
        self.assertEqual(sent["questions"]["next_action"]["criteria"]["a"], "Inspect gauge")

        for data in (
            {**good, "state_truncated": True},
            {**good, "answers": {"next_action": {
                "type": "choice", "choice": "c",
                "probabilities": {"a": .3, "b": .3, "c": .4},
            }}},
        ):
            with patch("scenarios.decision_models_trial.urlopen",
                       return_value=io.BytesIO(json.dumps(data).encode())):
                with self.assertRaises(ValueError):
                    model.sample_choice("What next?", ("a", "b"))

    def test_matched_native_concordia_trial_never_claims_world_effect(self):
        try:
            from concordia.testing.mock_model import MockModel
        except ImportError:
            self.skipTest("native Concordia not installed")
        del MockModel
        response = {
            "model": "laya:en", "state_truncated": False,
            "answers": {"next_action": {
                "type": "choice", "choice": "a", "confidence": .5,
                "probabilities": {"a": .5, "b": .5},
            }},
            "usage": {"input_tokens": 90}, "eval_duration": 1000,
        }

        def fake_urlopen(request, timeout=180):
            return io.BytesIO(json.dumps(response).encode())

        with patch("scenarios.decision_models_trial.urlopen", fake_urlopen):
            result = run("laya:en", 1, api_base="http://localhost:11435")
        self.assertEqual(len(result["decisions"]), 8)
        self.assertTrue(result["native_concordia"])
        self.assertEqual(result["world_commands_sent"], 0)
        self.assertEqual(result["world_receipts_received"], 0)


if __name__ == "__main__":
    unittest.main()
