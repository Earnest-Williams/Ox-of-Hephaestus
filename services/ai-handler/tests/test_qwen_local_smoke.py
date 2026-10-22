"""Offline invariants for the opt-in Qwen CPU integration probe."""
from __future__ import annotations

import unittest

from scenarios.qwen_local_smoke import run_probe

try:
    from concordia.testing.mock_model import MockModel
except ImportError:
    MockModel = None


class RefusingModel:
    """Never convert an invalid model choice into an accepted command."""

    def sample_choice(self, prompt, responses, *, seed=None):
        raise ValueError("Model returned an invalid action choice")

    def sample_text(self, *args, **kwargs):
        raise AssertionError("Probe should not call free-text inference")


@unittest.skipIf(MockModel is None, "Install handler[concordia] for native integration")
class QwenLocalProbeTests(unittest.TestCase):
    def test_native_concordia_produces_only_an_unconfirmed_proposal(self):
        report = run_probe(MockModel())
        self.assertEqual(report["inference_calls"], 1)
        self.assertEqual(report["pending_requests"], 1)
        self.assertEqual(report["character_id"], "#801")
        self.assertEqual(report["choice_verb"], "inspect")
        self.assertEqual(report["world_commands_sent"], 0)
        self.assertEqual(report["world_receipts_received"], 0)
        self.assertFalse(report["world_state_verified"])

    def test_invalid_model_output_is_not_an_accepted_proposal(self):
        with self.assertRaisesRegex(ValueError, "invalid action choice"):
            run_probe(RefusingModel())


if __name__ == "__main__":
    unittest.main()
