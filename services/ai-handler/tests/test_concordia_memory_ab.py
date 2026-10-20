"""Exercise paired evidence and mode persistence without hosted API calls."""
from __future__ import annotations

from importlib.util import find_spec
import tempfile
from pathlib import Path
import unittest


@unittest.skipUnless(find_spec("concordia") is not None, "Native Concordia required")
class MatchedEvidenceTests(unittest.TestCase):
    def test_matched_world_evidence_and_private_state(self):
        from scenarios.g11_memory_ab_trial import (
            CaptureModel, PromptMeasuredModel, fixtures, build, matched,
        )
        for spec in fixtures():
            with self.subTest(case=spec["name"]):
                a = build(spec, False, PromptMeasuredModel(CaptureModel()))
                b = build(spec, True, PromptMeasuredModel(CaptureModel()))
                self.assertTrue(matched(a, b))
                self.assertEqual(a.cognition_revision, b.cognition_revision)
                self.assertFalse(a.memory_projection_enabled)
                self.assertTrue(b.memory_projection_enabled)

    def test_mode_survives_fork_and_checkpoint(self):
        from scenarios.g11_memory_ab_trial import (
            CaptureModel, fixtures, build,
        )
        from ox_ai.agents.crew import CrewAgent
        baseline = build(fixtures()[0], False, CaptureModel())
        self.assertFalse(baseline.fork_for_inference().memory_projection_enabled)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "brain.json"
            baseline.save_checkpoint(path)
            restored = CrewAgent.from_checkpoint(path, CaptureModel())
            self.assertFalse(restored.memory_projection_enabled)
        with self.assertRaises(TypeError):
            CrewAgent(baseline.identity, CaptureModel(),
                      memory_projection_enabled="yes")

    def test_smoke_cannot_be_mistaken_for_real_quality_data(self):
        from scenarios.g11_memory_ab_trial import run
        data = run("capture", 1)
        self.assertFalse(data["real_hosted_model"])
        self.assertFalse(data["valid_quality_evidence"])
        self.assertEqual(len(data["decisions"]), 8)
        self.assertEqual(data["summary"]["augmented"]["samples"], 4)
        with self.assertRaises(ValueError):
            run("capture", 4)


if __name__ == "__main__":
    unittest.main()
