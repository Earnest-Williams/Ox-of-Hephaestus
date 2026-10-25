"""Measured, bounded admission around the existing detached actor scheduler.

Queue lifetime and provider service time have separate limits. A slot remains
owned until its actual worker exits, including after caller cancellation.
This schedules proposals; it neither accelerates a model nor executes work.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from types import MappingProxyType

from ox_ai.agents.crew import CommandOption, CrewAgent, StaleAgentRevision
from ox_ai.runtime.cognition_scheduler import (
    CognitionBudgetExceeded,
    CognitionBusy,
    CognitionTimedOut,
    DecisionScheduler,
)


class CognitionAdmissionRefused(CognitionBusy):
    """No capacity reservation, provider call, quota bill or action was created."""


@dataclass(frozen=True, slots=True)
class MeasuredServiceCapacity:
    """Workload-specific planning bound, with overruns still failing closed."""

    native_units: int
    service_timeout_seconds: float
    sample_count: int
    observed_max_seconds: float
    headroom: float = 1.5

    @classmethod
    def from_samples(cls, samples: Sequence[float], *, native_units: int):
        """Use six or more current-backend observations plus 50% headroom."""
        values = tuple(samples)
        if (
            type(native_units) is not int
            or native_units not in (2, 3)
            or not 6 <= len(values) <= 256
            or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values)
        ):
            raise ValueError("Six bounded service observations and two/three native units required")
        return cls(native_units, max(values) * 1.5, len(values), max(values))

    def __post_init__(self):
        """Refuse unsupported service times rather than clipping measurements."""
        if (
            type(self.native_units) is not int
            or self.native_units not in (2, 3)
            or type(self.sample_count) is not int
            or not 6 <= self.sample_count <= 256
            or any(
                type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                for v in (self.service_timeout_seconds, self.observed_max_seconds)
            )
            or self.headroom != 1.5
            or not math.isclose(
                self.service_timeout_seconds, self.observed_max_seconds * self.headroom
            )
            or self.service_timeout_seconds > 120
        ):
            raise ValueError(
                "Measured service bound must fit the supported 120-second worker limit"
            )


class CapacityAwareDecisionScheduler:
    """One native lane, bounded pending identities, fresh snapshots at dispatch.

    A refused/expired ticket leaves any persisted route intact. A provider
    overrun opens the circuit: queued/new work must obtain a newly measured
    scheduler, while the old worker keeps its slot until it actually drains.
    """

    def __init__(
        self,
        capacity: MeasuredServiceCapacity | Sequence[MeasuredServiceCapacity],
        *,
        max_pending: int = 40,
        queue_timeout_seconds: float = 3600,
        per_actor_budget: int = 500,
        total_budget: int = 2500,
        budget_window_seconds: float = 3600,
    ):
        """Reserve quota on admission; bill it only when real work dispatches."""
        profiles = (capacity,) if isinstance(capacity, MeasuredServiceCapacity) else tuple(capacity)
        if (
            not 1 <= len(profiles) <= 2
            or any(not isinstance(p, MeasuredServiceCapacity) for p in profiles)
            or len({p.native_units for p in profiles}) != len(profiles)
        ):
            raise TypeError("Distinct measured native workload profiles required")
        self.capacities = MappingProxyType({p.native_units: p for p in profiles})
        capacity = max(profiles, key=lambda p: p.service_timeout_seconds)
        if (
            type(max_pending) is not int
            or not 1 <= max_pending <= 128
            or type(queue_timeout_seconds) not in (float, int)
            or not math.isfinite(queue_timeout_seconds)
            or not 0 < queue_timeout_seconds <= 3600
            or (max_pending - 1) * capacity.service_timeout_seconds > queue_timeout_seconds
        ):
            raise ValueError("Pending capacity must fit the bounded queue lifetime")
        self.capacity = capacity
        self._max_pending = max_pending
        self._queue_timeout = float(queue_timeout_seconds)
        self._lane = asyncio.Semaphore(1)
        self._worker = DecisionScheduler(
            max_parallel=1,
            timeout_seconds=capacity.service_timeout_seconds,
            per_actor_budget=per_actor_budget,
            total_budget=total_budget,
            budget_window_seconds=budget_window_seconds,
        )
        self._roles: dict[str, str] = {}
        self._actors: dict[str, str] = {}
        self._waiting: set[str] = set()
        self._drains: dict[str, asyncio.Task] = {}
        self._reserved_units = 0
        self._failed = False
        self._queue_samples = deque(maxlen=256)
        self._counts = dict(
            admitted=0,
            refused_full=0,
            refused_profile=0,
            expired_in_queue=0,
            stale_before_dispatch=0,
            cancelled_in_queue=0,
            provider_overruns=0,
            dispatched=0,
            maximum_pending=0,
        )

    @property
    def metrics(self) -> dict:
        """Separate admission counts from the underlying billed/started units."""
        return {
            **self._worker.metrics,
            "capacity_admission": {
                **self._counts,
                "pending_roles": sorted(self._roles),
                "waiting_roles": sorted(self._waiting),
                "draining_roles": sorted(self._drains),
                "reserved_unbilled_units": self._reserved_units,
                "profile_failed": self._failed,
                "max_pending": self._max_pending,
                "queue_timeout_seconds": self._queue_timeout,
                "service_timeout_seconds": self.capacity.service_timeout_seconds,
                "expected_native_units": sorted(self.capacities),
                "service_limits_by_native_units": {
                    str(k): p.service_timeout_seconds for k, p in self.capacities.items()
                },
                "observed_service_max_seconds": self.capacity.observed_max_seconds,
                "calibration_sample_count": self.capacity.sample_count,
                "queue_wait_seconds": list(self._queue_samples),
            },
        }

    def _forget(self, role: str):
        """Release exactly this actor's admission identity."""
        actor = self._roles.pop(role)
        del self._actors[actor]

    async def _release_after_worker(self, role: str):
        """Quarantine the physical slot until the delegate's worker exits."""
        try:
            while role in self._worker.metrics["inflight_roles"]:
                await asyncio.sleep(0.01)
        finally:
            # A cancelled observer may not release a still-running provider.
            if role not in self._worker.metrics["inflight_roles"]:
                self._lane.release()
                self._forget(role)
                self._drains.pop(role, None)

    async def drain(self):
        """Wait for quarantined workers without cancelling their slot owners."""
        while self._drains:
            await asyncio.shield(asyncio.gather(*tuple(self._drains.values())))

    async def decide(
        self,
        role: str,
        agent: CrewAgent,
        options: Sequence[CommandOption],
        *,
        cost_units: int = 1,
        **kwargs,
    ):
        """Admit before copying a brain; keep queued evidence and routes bound."""
        if not isinstance(agent, CrewAgent):
            raise TypeError("Cognition requires a real CrewAgent")
        actor_remaining, global_remaining = self._worker.remaining_budget(role)
        from ox_ai.inference.disposition_choice import ReplayedPersonalityChoiceModel

        replay = isinstance(kwargs.get("inference_model"), ReplayedPersonalityChoiceModel)
        if (
            type(cost_units) is not int
            or (replay and cost_units != 1)
            or (not replay and cost_units not in self.capacities)
        ):
            raise ValueError("Decision cost differs from the measured workload")
        if "service_timeout_seconds" in kwargs:
            raise ValueError("Caller cannot override measured service limits")
        selected_capacity = (
            min(self.capacities.values(), key=lambda p: p.service_timeout_seconds)
            if replay
            else self.capacities[cost_units]
        )
        offered = tuple(options)
        if (
            not 1 <= len(offered) <= 26
            or any(not isinstance(o, CommandOption) or not o.label or not o.verb for o in offered)
            or len({o.label for o in offered}) != len(offered)
        ):
            raise ValueError("Invalid bounded command menu")
        # Isolate mutable argument dictionaries before any queue suspension.
        offered = tuple(
            CommandOption(o.label, o.verb, o.target, MappingProxyType(dict(o.arguments)))
            for o in offered
        )
        context = kwargs.get("decision_context")
        if context is not None and (not isinstance(context, str) or not 1 <= len(context) <= 1200):
            raise ValueError("Decision context must be bounded nonempty text")
        identity = agent.identity
        actor = identity.character_id
        if role in self._roles or actor in self._actors:
            raise CognitionBusy("This actor already owns a queued or active decision")
        if self._failed:
            self._counts["refused_profile"] += 1
            raise CognitionAdmissionRefused("Service bound exceeded; fresh calibration required")
        if len(self._roles) >= self._max_pending:
            self._counts["refused_full"] += 1
            raise CognitionAdmissionRefused("Inference admission is full; original route retained")
        if actor_remaining < cost_units or global_remaining - self._reserved_units < cost_units:
            raise CognitionBudgetExceeded("No unreserved inference quota available")
        revision, cognition = agent.revision, agent.cognition_revision
        self._roles[role] = actor
        self._actors[actor] = role
        self._reserved_units += cost_units
        self._counts["admitted"] += 1
        self._counts["maximum_pending"] = max(self._counts["maximum_pending"], len(self._roles))
        self._waiting.add(role)
        reserved, acquired = True, False
        began = time.monotonic()
        try:
            try:
                await asyncio.wait_for(self._lane.acquire(), self._queue_timeout)
            except asyncio.TimeoutError:
                self._counts["expired_in_queue"] += 1
                raise CognitionTimedOut(
                    "Admission queue lifetime expired; no provider work"
                ) from None
            acquired = True
            self._waiting.discard(role)
            self._queue_samples.append(time.monotonic() - began)
            if self._failed:
                self._counts["refused_profile"] += 1
                raise CognitionAdmissionRefused(
                    "Service bound exceeded; fresh calibration required"
                )
            if (
                agent.identity != identity
                or agent.revision != revision
                or agent.cognition_revision != cognition
            ):
                self._counts["stale_before_dispatch"] += 1
                raise StaleAgentRevision("Queued actor evidence changed before inference")
            self._reserved_units -= cost_units
            reserved = False
            self._counts["dispatched"] += 1
            try:
                return await self._worker.decide(
                    role,
                    agent,
                    offered,
                    cost_units=cost_units,
                    service_timeout_seconds=selected_capacity.service_timeout_seconds,
                    **kwargs,
                )
            except CognitionTimedOut:
                self._failed = True
                self._counts["provider_overruns"] += 1
                raise
        except asyncio.CancelledError:
            if not acquired:
                self._counts["cancelled_in_queue"] += 1
            raise
        finally:
            self._waiting.discard(role)
            if reserved:
                self._reserved_units -= cost_units
            if acquired and role in self._worker.metrics["inflight_roles"]:
                self._drains[role] = asyncio.create_task(self._release_after_worker(role))
            else:
                if acquired:
                    self._lane.release()
                self._forget(role)
