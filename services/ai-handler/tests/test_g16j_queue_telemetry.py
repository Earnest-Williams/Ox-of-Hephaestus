"""G16j: actual event-loop queue instrumentation, no native/model-quality claims."""
from __future__ import annotations

import asyncio
import json
import threading
import unittest

from ox_ai.agents.crew import CommandOption
from ox_ai.runtime.cognition_scheduler import (
    CognitionTimedOut, CognitionUnavailable, DecisionScheduler,
)

try:
    from ox_ai.agents.live_concordia import LiveCrewBrain
    from concordia.testing.mock_model import MockModel
except ImportError:
    LiveCrewBrain = None
    MockModel = None


class BlockingChoice:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def sample_choice(self, prompt, responses, *, seed=None):
        self.started.set()
        if not self.release.wait(4):
            raise TimeoutError("Blocked model test exceeded cleanup deadline")
        return 0, responses[0], {}

    def sample_text(self, *args, **kwargs):
        raise RuntimeError("No generative text in finite-choice scheduler test")


class SecretError:
    def sample_choice(self, prompt, responses, *, seed=None):
        raise RuntimeError("fake service SECRET_LLM_KEY must never enter metrics")

    def sample_text(self, *args, **kwargs):
        raise RuntimeError("No text")


@unittest.skipUnless(
    LiveCrewBrain is not None and MockModel is not None,
    "Native Concordia optional dependency required",
)
class RealAsyncQueueObservabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.primary = CommandOption("Inspect private gauge", "inspect", "gauge")

    async def test_one_actor_reports_real_invocation_not_three_native_forwards(self):
        brain = LiveCrewBrain("teo", "#772", MockModel())
        sched = DecisionScheduler(max_parallel=1, timeout_seconds=2)
        response = await sched.choose("teo", brain, self.primary,
                                      alternative="Defer for safety")
        self.assertEqual(response.character_id, "#772")
        m = sched.metrics
        x = m["queue_observability"]
        self.assertEqual(m["started"], 1)
        self.assertEqual(x["requests_accepted_for_scheduling"], 1)
        self.assertEqual(x["inference_invocations_started"], 1)
        self.assertEqual(x["inference_invocations_finished"], 1)
        self.assertEqual(x["proposals_adopted"], 1)
        self.assertEqual(x["maximum_simultaneous_inference_invocations"], 1)
        self.assertEqual(x["queue_wait_samples"], 1)
        self.assertEqual(x["provider_elapsed_samples"], 1)
        self.assertEqual(x["adopted_elapsed_samples"], 1)
        self.assertGreaterEqual(x["queue_wait_median_seconds"], 0)
        self.assertGreaterEqual(x["adopted_elapsed_p95_seconds"],
                                x["queue_wait_p95_seconds"])
        self.assertTrue(x["real_native_forward_count_not_established"])
        self.assertEqual(x["waiting_for_inference_slot"], [])
        self.assertEqual(x["provider_active_roles"], [])
        self.assertEqual(m["inflight_roles"], [])

    async def test_busy_lane_distinguishes_waiting_from_active_deadline(self):
        stalled = BlockingChoice()
        ari = LiveCrewBrain("ari", "#771", stalled)
        teo = LiveCrewBrain("teo", "#772", MockModel())
        sched = DecisionScheduler(max_parallel=1, timeout_seconds=0.17)
        slow = asyncio.create_task(sched.choose(
            "ari", ari, self.primary, alternative="Defer"))
        try:
            self.assertTrue(await asyncio.to_thread(stalled.started.wait, 2))
            waiting = asyncio.create_task(sched.choose(
                "teo", teo, self.primary, alternative="Defer"))
            await asyncio.sleep(0.02)
            m = sched.metrics["queue_observability"]
            self.assertIn("ari", m["provider_active_roles"])
            self.assertIn("teo", m["waiting_for_inference_slot"])
            with self.assertRaises(CognitionTimedOut):
                await slow
            with self.assertRaises(CognitionTimedOut):
                await waiting
        finally:
            stalled.release.set()
        for _ in range(150):
            if not sched.metrics["inflight_roles"]:
                break
            await asyncio.sleep(0.01)
        obs = sched.metrics["queue_observability"]
        self.assertEqual(obs["timed_out_with_provider_active"], 1)
        self.assertEqual(obs["timed_out_waiting_for_slot"], 1)
        self.assertEqual(obs["expired_queue_entries_discarded"], 1)
        self.assertEqual(obs["inference_invocations_started"], 1)
        self.assertEqual(obs["inference_invocations_finished"], 1)
        self.assertEqual(obs["proposals_adopted"], 0)
        self.assertEqual(obs["maximum_simultaneous_inference_invocations"], 1)
        self.assertEqual(obs["provider_finished_after_abandonment"], 1)
        self.assertFalse(ari.agent.pending_requests)
        self.assertFalse(teo.agent.pending_requests)

    async def test_provider_error_is_counted_without_leaking_prompts_or_keys(self):
        bad = LiveCrewBrain("mara", "#773", SecretError())
        sched = DecisionScheduler(max_parallel=1, timeout_seconds=1)
        with self.assertRaises(CognitionUnavailable) as e:
            await sched.choose("mara", bad, self.primary, alternative="Defer")
        self.assertNotIn("SECRET_LLM_KEY", str(e.exception))
        m = sched.metrics
        self.assertNotIn("SECRET_LLM_KEY", json.dumps(m))
        self.assertNotIn("Inspect private gauge", json.dumps(m))
        self.assertEqual(m["queue_observability"]["inference_failed"], 1)
        self.assertEqual(m["queue_observability"]["proposals_adopted"], 0)
        self.assertEqual(m["queue_observability"]["provider_elapsed_samples"], 1)
        self.assertFalse(bad.agent.pending_requests)

    async def test_sample_windows_are_bounded_and_budget_units_not_calls(self):
        b = LiveCrewBrain("teo", "#772", MockModel())
        s = DecisionScheduler(max_parallel=1, timeout_seconds=1)
        await s.decide(
            "teo", b.agent, (self.primary, CommandOption("Defer", "defer")),
            cost_units=3,
        )
        m=s.metrics
        self.assertEqual(m["started"], 3)
        self.assertEqual(m["queue_observability"]["inference_invocations_started"], 1)
        self.assertEqual(m["queue_observability"]["samples_per_metric_bounded_at"], 256)
        s._queue_wait_seconds.extend(float(i) for i in range(300))
        self.assertEqual(s.metrics["queue_observability"]["queue_wait_samples"], 256)


if __name__ == "__main__":
    unittest.main()
