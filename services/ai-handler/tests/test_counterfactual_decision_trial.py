"""Offline counterfactual suite invariants; never downloads or calls a model."""
from __future__ import annotations

import unittest

from scenarios.counterfactual_decision_trial import fixtures, make_agent, run


class CounterfactualDataTests(unittest.TestCase):
    def test_all_24_pairs_have_distinct_states_and_reversing_answers(self):
        cases = fixtures()
        self.assertEqual(len(cases), 24)
        self.assertEqual(len({case.name for case in cases}), 24)
        for case in cases:
            with self.subTest(case=case.name):
                self.assertNotEqual(case.earlier, case.changed)
                self.assertNotEqual(case.expected_earlier, case.expected_changed)
                self.assertNotEqual(case.first_verb, case.second_verb)
                self.assertNotEqual(case.first_option, case.second_option)

    def test_observations_are_scoped_and_alternative_state_is_not_leaked(self):
        from scenarios.g11_memory_ab_trial import CaptureModel
        for case in fixtures()[:3]:
            a, options = make_agent(case, "earlier", CaptureModel())
            b, options_b = make_agent(case, "changed", CaptureModel())
            self.assertEqual(options, options_b)
            self.assertEqual(a.identity, b.identity)
            self.assertEqual(a.revision, 1)
            self.assertEqual(b.revision, 1)
            self.assertEqual(len(a.temporal_memories.entries()), 1)
            self.assertEqual(len(b.temporal_memories.entries()), 1)
            self.assertNotEqual(a.snapshot()["concordia_state"],
                                b.snapshot()["concordia_state"])

    def test_smoke_capture_is_not_real_quality_evidence(self):
        try:
            from concordia.testing.mock_model import MockModel
        except ImportError:
            self.skipTest("Native Concordia optional dependency not installed")
        del MockModel
        report = run("capture", "capture", api_base="http://localhost", max_pairs=3)
        self.assertEqual(report["decisions"], 6)
        self.assertEqual(report["pairs"], 3)
        self.assertEqual(report["world_commands_sent"], 0)
        self.assertEqual(report["world_receipts_received"], 0)
        self.assertFalse(report["real_model"])
        self.assertEqual(len(report["records"]), 6)
        self.assertEqual(len(report["pair_records"]), 3)
        self.assertEqual(report["changed_decision_rate"], 0.0)

    def test_invalid_provider_and_model_fail_before_network(self):
        with self.assertRaises(ValueError):
            run("ollaya", "other:2b", api_base="http://127.0.0.1:11435")
        with self.assertRaises(ValueError):
            run("ollaya", "decider:2b", api_base="https://public.example")
        with self.assertRaises(ValueError):
            run("qwen-local", "qwen3.5-4b", api_base="http://example.com/v1")
        with self.assertRaises(ValueError):
            run("capture", "capture", api_base="http://localhost", max_pairs=25)


if __name__ == "__main__":
    unittest.main()
