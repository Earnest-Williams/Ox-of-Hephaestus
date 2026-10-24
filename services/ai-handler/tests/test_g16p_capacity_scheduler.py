"""Real Concordia scheduling with explicitly synthetic, controllable providers."""

from __future__ import annotations

import asyncio
import importlib.util
import threading
import unittest
from unittest import mock

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity, StaleAgentRevision
from ox_ai.ports.base import WorldObservation
from ox_ai.runtime.capacity_scheduler import (
    CapacityAwareDecisionScheduler,
    CognitionAdmissionRefused,
    MeasuredServiceCapacity,
)
from ox_ai.runtime.cognition_scheduler import (
    CognitionBudgetExceeded,
    CognitionBusy,
    CognitionTimedOut,
)

OPTIONS = (CommandOption("Inspect gauge", "inspect", "gauge"), CommandOption("Defer", "defer"))


class FixedModel:
    """Finite synthetic choice; no real inference or dialogue."""

    def sample_choice(self, prompt, responses, *, seed=None):
        return 0, responses[0], {}

    def sample_text(self, *args, **kwargs):
        raise AssertionError("No dialogue")


class HeldModel(FixedModel):
    """Hold the actual executor thread until the test releases it."""

    def __init__(self):
        self.started, self.release = threading.Event(), threading.Event()

    def sample_choice(self, prompt, responses, *, seed=None):
        self.started.set()
        if not self.release.wait(5):
            raise TimeoutError("Test failed to release provider")
        return super().sample_choice(prompt, responses, seed=seed)


def capacity(seconds=1.5):
    """Construct an explicitly synthetic service envelope for fast tests."""
    return MeasuredServiceCapacity.from_samples([seconds / 1.5] * 6, native_units=2)


class CapacityValidationTests(unittest.TestCase):
    def test_measured_bound_and_unsupported_host_refusal(self):
        p = MeasuredServiceCapacity.from_samples(
            [12.0, 13.0, 14.0, 12.0, 15.0, 14.0], native_units=2
        )
        self.assertEqual(p.service_timeout_seconds, 22.5)
        self.assertEqual(p.observed_max_seconds, 15.0)
        for samples in ([1.0] * 5, [float("nan")] * 6, [True] * 6, [81.0] * 6):
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                MeasuredServiceCapacity.from_samples(samples, native_units=2)
        with self.assertRaises(ValueError):
            CapacityAwareDecisionScheduler(
                capacity(120), max_pending=40, queue_timeout_seconds=3600
            )


@unittest.skipUnless(importlib.util.find_spec("concordia"), "Requires real Concordia")
class CapacitySchedulerTests(unittest.IsolatedAsyncioTestCase):
    def actor(self, i, model=None):
        """Use a distinct native actor identity and private component graph."""
        return CrewAgent(
            CrewIdentity(
                f"g16p.{i}",
                f"#{500+i}",
                f"Worker {i}",
                "Review local gauge",
                "Choose an offered action",
            ),
            model or FixedModel(),
        )

    async def start_held(self, scheduler, model, actor=None):
        """Wait for native-interface entry, without blocking the event loop."""
        actor = actor or self.actor(0, model)
        task = asyncio.create_task(scheduler.decide("role0", actor, OPTIONS, cost_units=2))
        self.assertTrue(await asyncio.to_thread(model.started.wait, 1))
        return task, actor

    async def test_forty_eligible_decisions_finish_with_one_lane(self):
        scheduler = CapacityAwareDecisionScheduler(capacity(), per_actor_budget=2, total_budget=80)
        actors = [self.actor(i) for i in range(40)]
        results = await asyncio.gather(
            *(scheduler.decide(f"r{i}", a, OPTIONS, cost_units=2) for i, a in enumerate(actors))
        )
        self.assertEqual(len(results), 40)
        metrics = scheduler.metrics
        self.assertEqual(metrics["started"], 80)
        self.assertEqual(metrics["queue_observability"]["proposals_adopted"], 40)
        self.assertEqual(
            metrics["queue_observability"]["maximum_simultaneous_inference_invocations"], 1
        )
        self.assertFalse(metrics["capacity_admission"]["pending_roles"])
        self.assertEqual(metrics["capacity_admission"]["reserved_unbilled_units"], 0)

    async def test_full_admission_refuses_before_copying_or_charging(self):
        model = HeldModel()
        scheduler = CapacityAwareDecisionScheduler(capacity(), max_pending=1, total_budget=10)
        task, actor = await self.start_held(scheduler, model)
        other = self.actor(1)
        try:
            with mock.patch.object(
                other, "fork_for_inference", side_effect=AssertionError("copied")
            ):
                with self.assertRaises(CognitionAdmissionRefused):
                    await scheduler.decide("other", other, OPTIONS, cost_units=2)
            self.assertEqual(scheduler.metrics["started"], 2)
            self.assertEqual(scheduler.metrics["capacity_admission"]["maximum_pending"], 1)
        finally:
            model.release.set()
            await task
        result = await scheduler.decide("other", other, OPTIONS, cost_units=2)
        self.assertEqual(result.character_id, other.identity.character_id)

    async def test_global_quota_is_reserved_before_other_actors_queue(self):
        model = HeldModel()
        scheduler = CapacityAwareDecisionScheduler(
            capacity(), max_pending=3, per_actor_budget=2, total_budget=4
        )
        first, _ = await self.start_held(scheduler, model)
        second = asyncio.create_task(
            scheduler.decide("second", self.actor(1), OPTIONS, cost_units=2)
        )
        await asyncio.sleep(0)
        try:
            with self.assertRaises(CognitionBudgetExceeded):
                await scheduler.decide("third", self.actor(2), OPTIONS, cost_units=2)
            self.assertEqual(scheduler.metrics["capacity_admission"]["reserved_unbilled_units"], 2)
        finally:
            model.release.set()
            await asyncio.gather(first, second)
        self.assertEqual(scheduler.metrics["started"], 4)

    async def test_queued_revision_change_rejects_before_copy_or_billing(self):
        model = HeldModel()
        scheduler = CapacityAwareDecisionScheduler(capacity(), max_pending=2, total_budget=10)
        first, _ = await self.start_held(scheduler, model)
        other = self.actor(1)
        queued = asyncio.create_task(scheduler.decide("second", other, OPTIONS, cost_units=2))
        await asyncio.sleep(0)
        other.observe(
            WorldObservation(
                "new-reading",
                other.identity.character_id,
                1.0,
                "The local condition changed",
                source_event_id="new-reading",
            )
        )
        with mock.patch.object(
            other, "fork_for_inference", side_effect=AssertionError("stale copy")
        ):
            model.release.set()
            await first
            with self.assertRaises(StaleAgentRevision):
                await queued
        self.assertFalse(other.pending_requests)
        self.assertEqual(scheduler.metrics["started"], 2)
        self.assertEqual(scheduler.metrics["capacity_admission"]["stale_before_dispatch"], 1)

    async def test_mixed_profile_queue_and_worker_limit_validation(self):
        from ox_ai.runtime.cognition_scheduler import DecisionScheduler

        profiles = (capacity(), MeasuredServiceCapacity.from_samples([2.0] * 6, native_units=3))
        scheduler = CapacityAwareDecisionScheduler(
            profiles, max_pending=2, per_actor_budget=3, total_budget=5
        )
        await asyncio.gather(
            scheduler.decide("two", self.actor(1), OPTIONS, cost_units=2),
            scheduler.decide("three", self.actor(2), OPTIONS, cost_units=3),
        )
        self.assertEqual(scheduler.metrics["started"], 5)
        self.assertEqual(
            scheduler.metrics["capacity_admission"]["service_limits_by_native_units"],
            {"2": 1.5, "3": 3.0},
        )
        base = DecisionScheduler(timeout_seconds=1)
        with self.assertRaises(ValueError):
            await base.decide("bad", self.actor(3), OPTIONS, service_timeout_seconds=2)
        self.assertEqual(base.metrics["started"], 0)
        with self.assertRaises(ValueError):
            await scheduler.decide(
                "override", self.actor(4), OPTIONS, cost_units=2, service_timeout_seconds=10
            )

    async def test_queued_actor_identity_cannot_be_rebound(self):
        from dataclasses import replace

        model = HeldModel()
        scheduler = CapacityAwareDecisionScheduler(capacity(), max_pending=2, total_budget=10)
        first, _ = await self.start_held(scheduler, model)
        other = self.actor(1)
        queued = asyncio.create_task(scheduler.decide("second", other, OPTIONS, cost_units=2))
        await asyncio.sleep(0)
        other.identity = replace(other.identity, character_id="#999")
        model.release.set()
        await first
        with self.assertRaises(StaleAgentRevision):
            await queued
        self.assertFalse(other.pending_requests)
        self.assertEqual(scheduler.metrics["started"], 2)

    async def test_active_cancellation_keeps_slot_until_worker_drains(self):
        model = HeldModel()
        scheduler = CapacityAwareDecisionScheduler(capacity(), max_pending=1, total_budget=10)
        task, actor = await self.start_held(scheduler, model)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        try:
            with self.assertRaises(CognitionAdmissionRefused):
                await scheduler.decide("second", self.actor(1), OPTIONS, cost_units=2)
            with self.assertRaises(CognitionBusy):
                await scheduler.decide("alias", actor, OPTIONS, cost_units=2)
            self.assertEqual(scheduler.metrics["capacity_admission"]["draining_roles"], ["role0"])
        finally:
            model.release.set()
            await asyncio.wait_for(scheduler.drain(), 2)
        self.assertFalse(actor.pending_requests)
        self.assertFalse(scheduler.metrics["capacity_admission"]["pending_roles"])

    async def test_queue_expiry_and_cancellation_return_unbilled_reservations(self):
        model = HeldModel()
        scheduler = CapacityAwareDecisionScheduler(
            capacity(0.15), max_pending=2, queue_timeout_seconds=0.2, total_budget=10
        )
        first, _ = await self.start_held(scheduler, model)
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        try:
            with self.assertRaises(CognitionTimedOut):
                await scheduler.decide("expiry", self.actor(1), OPTIONS, cost_units=2)
            pending = asyncio.create_task(
                scheduler.decide("cancel", self.actor(2), OPTIONS, cost_units=2)
            )
            await asyncio.sleep(0)
            pending.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await pending
            self.assertEqual(scheduler.metrics["started"], 2)
            self.assertEqual(scheduler.metrics["capacity_admission"]["reserved_unbilled_units"], 0)
        finally:
            model.release.set()
            await scheduler.drain()

    async def test_provider_overrun_trips_profile_without_starting_next_actor(self):
        model = HeldModel()
        scheduler = CapacityAwareDecisionScheduler(capacity(0.15), max_pending=2, total_budget=10)
        first, actor = await self.start_held(scheduler, model)
        second_actor = self.actor(1)
        second = asyncio.create_task(
            scheduler.decide("second", second_actor, OPTIONS, cost_units=2)
        )
        try:
            with self.assertRaises(CognitionTimedOut):
                await first
            self.assertTrue(scheduler.metrics["capacity_admission"]["profile_failed"])
            self.assertEqual(scheduler.metrics["started"], 2)
        finally:
            model.release.set()
            await scheduler.drain()
        with self.assertRaises(CognitionAdmissionRefused):
            await second
        self.assertFalse(actor.pending_requests)
        self.assertFalse(second_actor.pending_requests)
        self.assertEqual(scheduler.metrics["capacity_admission"]["provider_overruns"], 1)


# Re-run the actual durable G16o controller contracts through the new scheduler.
# Import the fixture module, not its TestCase class, to avoid duplicate discovery.
import test_g16o_binary_choice as binary_fixture


class CapacityControllerTests(binary_fixture.BinaryControllerTests):
    """The identical native-component checkpoint/replay/safety contract."""

    def controller(self, engine, *, record=None, budget=2, timeout=30):
        router = binary_fixture.PersonalityRouter(
            self.profile, "#301", record or {}, seed=self.seed
        )
        return binary_fixture.CharacterRouteController(
            router,
            CapacityAwareDecisionScheduler(
                capacity(timeout), per_actor_budget=budget, total_budget=budget
            ),
            role="g16p",
            decider_engine=engine,
        )


import test_g16_choice as ternary_fixture


class TernaryCapacityControllerTests(ternary_fixture.NativeControllerTests):
    """Preserve the existing three-forward durable controller contract."""

    def controller(self, router, *, engine=None):
        self.router = router
        profile = MeasuredServiceCapacity.from_samples([20.0] * 6, native_units=3)
        return ternary_fixture.CharacterRouteController(
            router,
            CapacityAwareDecisionScheduler(profile, per_actor_budget=64, total_budget=64),
            role="g16p-ternary",
            decider_engine=engine,
        )


if __name__ == "__main__":
    unittest.main()
