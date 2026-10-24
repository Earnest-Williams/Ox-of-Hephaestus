"""G16o real-controller fixture checks; never native capacity evidence."""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scenarios" / "profiling"))

AVAILABLE = (
    importlib.util.find_spec("concordia") is not None
    and importlib.util.find_spec("ox_contracts") is not None
)
if AVAILABLE:
    from g16o_binary_capacity import capacity_observation, run


@unittest.skipUnless(AVAILABLE, "Requires native Concordia and strict contracts")
class CapacityTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_controller_fixture_runs_all_cohorts_without_native_claim(self):
        with mock.patch.dict(os.environ, {"OX_PERSONALITY_CHOICE": "0"}):
            result = await run("fixture")
            self.assertEqual(os.environ["OX_PERSONALITY_CHOICE"], "0")
        self.assertFalse(result["native_model_verified"])
        self.assertFalse(result["production_activation_accepted"])
        self.assertEqual(result["actual_native_forward_calls"], 0)
        self.assertEqual(result["synthetic_fixture_forward_calls"], 144)
        self.assertEqual(result["capacity_observation"]["status"], "not_established")
        self.assertEqual([r["actors"] for r in result["bursts"]], [6, 20, 40])
        for row in [result["baseline"], *result["bursts"]]:
            self.assertEqual(row["proposals_adopted"], row["actors"])
            self.assertEqual(row["underlying_forward_calls"], row["actors"] * 2)
            self.assertEqual(row["world_commands_sent"], 0)

    async def test_native_mode_requires_provisioned_exact_bytes(self):
        with self.assertRaises(FileNotFoundError):
            await run("decider-q4")

    def test_capacity_estimate_refuses_fixture_or_censored_baseline(self):
        baseline = {
            "proposals_adopted": 6,
            "actor_results": [{"elapsed_seconds": float(n)} for n in range(10, 16)],
        }
        observed = capacity_observation(baseline, native=True)
        self.assertEqual(observed["maximum_seconds"], 15)
        self.assertEqual(observed["sample_p95_seconds"], 15)
        self.assertEqual(observed["estimated_serial_completions_in_25_seconds"], 1)
        self.assertIsNone(observed["guaranteed_completions"])
        self.assertFalse(observed["changes_runtime_configuration"])
        self.assertEqual(capacity_observation(baseline, native=False)["status"], "not_established")
        baseline["proposals_adopted"] = 5
        self.assertEqual(capacity_observation(baseline, native=True)["status"], "not_established")


if __name__ == "__main__":
    unittest.main()
