"""G16l offline structural burst exercise; fake System One is NOT native evidence."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
import time
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scenarios/profiling"))
import g16l_real_native_burst as g16l
from g16f_personality_throughput import EngineMeter, FakeSystemOne
from ox_ai.runtime.cognition_scheduler import DecisionScheduler as RealScheduler


class SlowFakeSystemOne(FakeSystemOne):
    def system_one(self, prompt, questions):
        time.sleep(.15)
        return super().system_one(prompt, questions)


class ProvenanceTests(TestCase):
    def test_native_requires_exact_publisher_weights_or_explicit_fixture(self):
        for name in ("decider-q4", "invented-provider"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                g16l.validate_source(None, None, name)
        fake, source = g16l.validate_source(None, None, "fixture")
        self.assertIsInstance(fake, FakeSystemOne)
        self.assertTrue(source["synthetic_source_for_shape_only"])


class ActualAsyncBurstBoundaryTests(IsolatedAsyncioTestCase):
    async def test_all_original_synthetic_personae_and_checkpoint_ledgers(self):
        with patch.dict(os.environ, {"OX_PERSONALITY_CHOICE": "1"}):
            result = await g16l.evaluate("fixture", None, None)
        self.assertFalse(result["all_native_forwards_real"])
        self.assertEqual(result["population"], [6, 20, 40])
        self.assertEqual(result["total_native_system_one_forwards"], 198)
        self.assertEqual(result["max_actual_concurrent_native_system_one_forwards"], 1)
        self.assertFalse(result["production_policy_adopted"])
        self.assertEqual(result["real_world_actions_submitted"], 0)
        for n, row in zip((6,20,40),result["measured_cohorts"]):
            self.assertEqual(row["actors"], n)
            self.assertEqual(row["adopted_valid_nonworld_proposals"], n)
            self.assertEqual(row["expired_no_world_proposals"], 0)
            self.assertEqual(row["native_forward_calls"], 3*n)
            self.assertTrue(row["all_underlying_native_workers_reaped"])
            self.assertEqual(row["physical_work_receipts_created"], 0)
            self.assertEqual(row["scheduler_metrics"]["queue_observability"][
                "inference_invocations_finished"], n)

    async def test_real_async_timeouts_do_not_adopt_late_native_proposals(self):
        def rapid_deadline(*a, **kw):
            kw["timeout_seconds"] = .10
            return RealScheduler(*a, **kw)
        with patch.dict(os.environ, {"OX_PERSONALITY_CHOICE": "1"}):
            with patch.object(g16l, "DecisionScheduler", rapid_deadline):
                x=await g16l.actual_burst(
                    6,meter=EngineMeter(SlowFakeSystemOne()),
                )
        metric=x["scheduler_metrics"]["queue_observability"]
        self.assertEqual(x["adopted_valid_nonworld_proposals"], 0)
        self.assertEqual(x["expired_no_world_proposals"], 6)
        self.assertEqual(x["native_forward_calls"], 3)
        self.assertEqual(metric["inference_invocations_started"], 1)
        self.assertEqual(metric["inference_invocations_finished"], 1)
        self.assertEqual(metric["provider_finished_after_abandonment"], 1)
        self.assertEqual(metric["timed_out_waiting_for_slot"], 5)
        self.assertEqual(metric["timed_out_with_provider_active"], 1)
        self.assertEqual(metric["expired_queue_entries_discarded"], 5)
        self.assertEqual(metric["proposals_adopted"], 0)
        self.assertTrue(x["all_underlying_native_workers_reaped"])
        self.assertEqual(x["evennia_commands_sent"], 0)

    async def test_flag_must_be_an_explicit_isolated_optin(self):
        with patch.dict(os.environ, {"OX_PERSONALITY_CHOICE": "0"}):
            with self.assertRaises(PermissionError):
                await g16l.actual_burst(
                    6,meter=EngineMeter(FakeSystemOne()),
                )


if __name__ == "__main__":
    import unittest
    unittest.main()
