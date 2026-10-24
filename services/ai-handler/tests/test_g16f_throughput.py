"""G16f structural performance gates, never fabricated native rate claims."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

try:
    import ox_contracts
except ImportError:
    ox_contracts = None


@unittest.skipUnless(
    ox_contracts is not None and importlib.util.find_spec("concordia") is not None,
    "Optional pinned Concordia and shared G16a package absent",
)
class ProfileRuntimeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(root / "scenarios/profiling"))
        from g16f_personality_throughput import run
        cls.profile = staticmethod(run)

    async def test_sequential_six_twenty_forty_concordia_choices(self):
        with mock.patch.dict(os.environ, {"OX_PERSONALITY_CHOICE": "1"}):
            data = await self.profile(
                engine_name="fixture", mode="sequential",
                gguf_path=None, model_manifest=None,
            )
        self.assertEqual(data["backend"], "fixture")
        self.assertFalse(data["native_gguf_forwards_measured"])
        self.assertEqual(data["forward_calls"], 198)
        self.assertEqual([x["actors"] for x in data["measured_cohorts"]],
                         [6, 20, 40])
        self.assertEqual([x["model_forwards_counted"]
                          for x in data["measured_cohorts"]],
                         [18, 60, 120])
        for cohort in data["measured_cohorts"]:
            self.assertEqual(cohort["actors"], cohort["decisions_completed"])
            self.assertEqual(cohort["max_parallel_scoring_workers"], 2)
            self.assertEqual(cohort["worst_case_pending_actions_per_actor"], 1)
            self.assertGreater(cohort["total_live_agent_snapshot_bytes"], 0)
            self.assertGreater(cohort["total_durable_router_bytes"], 0)
            self.assertGreater(cohort["measured_decisions_per_hour_at_this_backend"], 0)
        self.assertEqual(data["evennia_commands_sent"], 0)

    async def test_burst_same_real_agents_scheduler_and_durable_ledger(self):
        with mock.patch.dict(os.environ, {"OX_PERSONALITY_CHOICE": "1"}):
            data = await self.profile(
                engine_name="fixture", mode="burst",
                gguf_path=None, model_manifest=None,
            )
        self.assertEqual(data["forward_calls"], 198)
        self.assertEqual(data["maximum_concurrent_native_forwards"], 1)
        self.assertTrue(all(x["decisions_completed"] == x["actors"]
                            for x in data["measured_cohorts"]))
        self.assertEqual(data["measured_cohorts"][-1]["actors"], 40)

    async def test_true_native_needs_pinned_gguf_and_manifest(self):
        with self.assertRaises(FileNotFoundError):
            await self.profile(
                engine_name="decider-q4", mode="sequential",
                gguf_path=None, model_manifest=None,
            )
        with self.assertRaises(ValueError):
            await self.profile(
                engine_name="decider-q4", mode="burst",
                gguf_path=None, model_manifest=None,
            )

if __name__ == "__main__":
    unittest.main()
