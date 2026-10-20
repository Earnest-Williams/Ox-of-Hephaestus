"""Nonblocking detached cognition: real Concordia API with bounded fake models."""
import asyncio
import threading
import unittest

from ox_ai.agents.crew import CommandOption, StaleAgentRevision
from ox_ai.memory.temporal import TemporalMemory
from ox_ai.runtime.cognition_scheduler import (
    CognitionBudgetExceeded, CognitionBusy, CognitionTimedOut,
    CognitionUnavailable, DecisionScheduler,
)
try:
    from concordia.testing.mock_model import MockModel
except ImportError:
    MockModel = None


class BudgetValidation(unittest.TestCase):
    def test_invalid_caps_fail_closed(self):
        for kw in ({"max_parallel": 0}, {"max_parallel": True},
                   {"per_actor_budget": -1}, {"total_budget": 0},
                   {"timeout_seconds": float("nan")},
                   {"timeout_seconds": -1},
                   {"budget_window_seconds": 0}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                DecisionScheduler(**kw)


class BlockingChoiceModel:
    """Blocks only its own detached worker, never the async event loop."""
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
    def sample_choice(self, prompt, responses, *, seed=None):
        self.started.set()
        if not self.release.wait(3):
            raise TimeoutError("Test model never released")
        return 0, responses[0], {}
    def sample_text(self, prompt, **kwargs):
        raise AssertionError("Bounded menu requires a choice, not free-form text")


class FailingModel:
    def sample_choice(self, prompt, responses, *, seed=None):
        raise RuntimeError("provider might include a SECRET API KEY in its error")
    def sample_text(self, prompt, **kwargs):
        raise AssertionError


@unittest.skipIf(MockModel is None, "Native Concordia is an optional dependency")
class NativeNonblockingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from ox_ai.agents.live_concordia import LiveCrewBrain
        self.ari_model = BlockingChoiceModel()
        self.ari = LiveCrewBrain("ari", "#71", self.ari_model)
        self.teo = LiveCrewBrain("teo", "#72", MockModel())
        self.primary = CommandOption("Inspect local gauge", "inspect", "gauge")

    async def _running_ari(self, scheduler):
        task = asyncio.create_task(scheduler.choose(
            "ari", self.ari, self.primary, alternative="Defer to a later watch",
        ))
        started = await asyncio.to_thread(self.ari_model.started.wait, 1.0)
        self.assertTrue(started, "Concordia did not start its choice in a worker")
        return task

    async def test_slow_actor_does_not_block_other_inference_or_new_observations(self):
        scheduler = DecisionScheduler(max_parallel=2, timeout_seconds=2)
        slow = await self._running_ari(scheduler)
        try:
            # The second mind makes independent progress while Ari's model
            # is blocked, on a separate authenticated character identity.
            fast = await asyncio.wait_for(scheduler.choose(
                "teo", self.teo, self.primary, alternative="Defer"
            ), timeout=0.6)
            self.assertEqual(fast.character_id, "#72")
            self.assertFalse(slow.done())
            self.assertEqual(self.teo.inference_calls, 1)

            # The LIVE Ari mind can receive a private observation while the
            # detached shadow is calculating; this invalidates Ari's choice.
            self.ari.observe_local("New world reading", "Different local telemetry")
            self.assertEqual(self.ari.agent.revision, 1)
            self.ari_model.release.set()
            with self.assertRaises(StaleAgentRevision):
                await slow
            self.assertFalse(self.ari.agent.pending_requests)
            self.assertIn("Different local telemetry", " ".join(self.ari.agent.memories))
        finally:
            self.ari_model.release.set()

    async def test_private_memory_during_inference_is_never_overwritten(self):
        scheduler = DecisionScheduler(max_parallel=1, timeout_seconds=2)
        slow = await self._running_ari(scheduler)
        try:
            self.assertEqual(self.ari.agent.revision, 0)
            self.assertEqual(self.ari.agent.cognition_revision, 0)
            admitted = self.ari.agent.remember_timed(TemporalMemory(
                "memory.after.snapshot", "mara",
                "Mara disagreed with my original interpretation.",
                "witnessed_speech", 41, 41, 100, 95,
                trust_effect=-5, source_event_id="world-heard-41",
                claim_key="mara_disagreed", claim_subject="mara",
                claim_stance=1, source_group="mara.firsthand",
            ))
            self.assertTrue(admitted)
            self.assertEqual(self.ari.agent.revision, 0)
            self.assertEqual(self.ari.agent.cognition_revision, 1)
            self.ari_model.release.set()
            with self.assertRaises(StaleAgentRevision):
                await slow
            self.assertFalse(self.ari.agent.pending_requests)
            self.assertIsNotNone(self.ari.agent.temporal_memories.get(
                "memory.after.snapshot"))
            self.assertIsNotNone(self.ari.agent.interpretations.get(
                "mara", "mara_disagreed"))
            self.assertEqual(self.ari.agent.cognition_revision, 1)
        finally:
            self.ari_model.release.set()

    async def test_one_actor_cannot_double_schedule_and_timeout_quarantines(self):
        scheduler = DecisionScheduler(max_parallel=2, timeout_seconds=0.1)
        slow = await self._running_ari(scheduler)
        with self.assertRaises(CognitionBusy):
            await scheduler.choose("ari", self.ari, self.primary, alternative="Defer")
        try:
            with self.assertRaises(CognitionTimedOut):
                await slow
            self.assertIn("ari", scheduler.metrics["timed_out_or_cancelled_roles"])
            self.assertFalse(self.ari.agent.pending_requests)
            with self.assertRaises(CognitionBusy):
                await scheduler.choose("ari", self.ari, self.primary, alternative="Defer")
        finally:
            self.ari_model.release.set()
        for i in range(50):
            if not scheduler.metrics["inflight_roles"]:
                break
            await asyncio.sleep(0.01)
        self.assertFalse(scheduler.metrics["inflight_roles"])
        self.assertFalse(self.ari.agent.pending_requests)

    async def test_failing_provider_does_not_leak_exception_or_propose_action(self):
        from ox_ai.agents.live_concordia import LiveCrewBrain
        bad = LiveCrewBrain("mara", "#73", FailingModel())
        scheduler = DecisionScheduler(timeout_seconds=1)
        with self.assertRaises(CognitionUnavailable) as caught:
            await scheduler.choose("mara", bad, self.primary, alternative="Defer")
        self.assertNotIn("SECRET", str(caught.exception))
        self.assertEqual(len(bad.agent.pending_requests), 0)

    async def test_bounded_quotas_reset_on_next_wall_window(self):
        scheduler = DecisionScheduler(per_actor_budget=1, total_budget=1)
        await scheduler.choose("teo", self.teo, self.primary, alternative="Defer")
        with self.assertRaises(CognitionBudgetExceeded):
            await scheduler.choose("teo", self.teo, self.primary, alternative="Defer")
        self.assertEqual(scheduler.metrics["started"], 1)
        scheduler._window_started -= 3601
        response = await scheduler.choose("teo", self.teo, self.primary, alternative="Defer")
        self.assertEqual(response.character_id, "#72")
        self.assertEqual(scheduler.metrics["started"], 1)

    async def test_cross_character_shadow_cannot_be_adopted(self):
        from ox_ai.agents.crew import CrewAgent
        source = self.teo.agent.fork_for_inference()
        choices = (self.primary, CommandOption("Defer", "defer"))
        draft = await asyncio.to_thread(source.decide, choices)
        self.assertIsInstance(source, CrewAgent)
        with self.assertRaises(PermissionError):
            self.ari.agent.adopt_inference(
                source, draft, choices, expected_revision=self.ari.agent.revision,
                expected_cognition_revision=self.ari.agent.cognition_revision,
            )
        self.assertFalse(self.ari.agent.pending_requests)

if __name__ == "__main__":
    unittest.main()
