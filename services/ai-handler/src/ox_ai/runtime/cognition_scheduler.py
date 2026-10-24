"""Bounded asynchronous per-character Concordia inference.

The live Concordia entity remains on the event-loop thread. A *detached
snapshot* does synchronous model inference in a worker thread; fresh addressed
observations can arrive meanwhile and invalidate the result. Only an unexpired,
same-revision result is admitted to the real agent's pending *proposal* ledger.
This module never submits a physical action or reads the Evennia database.

Timed-out work may continue in its detached worker. It is quarantined: a
second decision for that actor is refused until the old worker has exited.
The model/provider must also enforce a real I/O timeout.
"""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Sequence
import math
import time
import threading
from typing import Any

from ox_ai.ports.base import ActionRequest
from ox_ai.agents.crew import CommandOption, CrewAgent, StaleAgentRevision


class CognitionBusy(RuntimeError):
    """One actor has an unresolved inference; no second invocation allowed."""


class CognitionTimedOut(RuntimeError):
    """No inference proposal was adopted before the configured deadline."""


class CognitionUnavailable(RuntimeError):
    """Provider/model did not supply a validated and usable proposal."""


class CognitionBudgetExceeded(RuntimeError):
    """Bounded model-call quota reached; no provider work was started."""


class DecisionScheduler:
    """Independently queue role-scoped inference with a global concurrency cap.

    This is a cognition scheduler, not a simultaneous physical-action executor.
    No thread can mutate a live mind or submit an Evennia command.
    """

    def __init__(
        self, *, max_parallel: int = 2, per_actor_budget: int = 500,
        total_budget: int = 2500, timeout_seconds: float = 25.0,
        budget_window_seconds: float = 3600.0,
    ) -> None:
        if (isinstance(max_parallel, bool) or not isinstance(max_parallel, int)
                or not 1 <= max_parallel <= 16):
            raise ValueError("max_parallel must be an integer from 1 to 16")
        for value in (per_actor_budget, total_budget):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1000000:
                raise ValueError("Inference budgets must be positive bounded integers")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool):
            raise ValueError("Invalid inference deadline")
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120:
            raise ValueError("Inference deadline must be between 0 and 120 seconds")
        if (not isinstance(budget_window_seconds, (int, float))
                or isinstance(budget_window_seconds, bool)
                or not math.isfinite(budget_window_seconds)
                or not 60 <= budget_window_seconds <= 86400):
            raise ValueError("Budget window must be 60-86400 wall seconds")
        self._budget_window = float(budget_window_seconds)
        self._window_started = time.monotonic()
        self._sem = asyncio.Semaphore(max_parallel)
        self._per_actor_budget = per_actor_budget
        self._total_budget = total_budget
        self._timeout = float(timeout_seconds)
        self._inflight: dict[str, asyncio.Task] = {}
        self._orphaned: set[str] = set()
        self._attempts: dict[str, int] = {}
        self._total_attempts = 0
        # Ephemeral, bounded, actor-role-only operational telemetry.
        # Counters and samples are not evidence of completed ship work.
        self._telemetry = {
            "requests_accepted_for_scheduling": 0,
            "inference_invocations_started": 0,
            "inference_invocations_finished": 0,
            "proposals_adopted": 0,
            "inference_failed": 0,
            "stale_proposals_rejected": 0,
            "timed_out_waiting_for_slot": 0,
            "timed_out_with_provider_active": 0,
            "cancelled": 0,
            "provider_finished_after_abandonment": 0,
            "expired_queue_entries_discarded": 0,
        }
        self._pending_slot_roles: set[str] = set()
        self._native_running_roles: set[str] = set()
        self._maximum_simultaneous_inference_invocations = 0
        self._queue_wait_seconds: deque[float] = deque(maxlen=256)
        self._provider_elapsed_seconds: deque[float] = deque(maxlen=256)
        self._adopted_elapsed_seconds: deque[float] = deque(maxlen=256)

    def _refresh_budget_window(self) -> None:
        # Model quota is a wall-time rate limit, not a cap on an entire
        # long-lived ship voyage. No model call is caused by this clock read.
        if time.monotonic() - self._window_started >= self._budget_window:
            self._window_started = time.monotonic()
            self._attempts.clear()
            self._total_attempts = 0

    def remaining_budget(self, role: str) -> tuple[int, int]:
        """Return unbilled actor/global units after refreshing the rate window."""
        if not isinstance(role, str) or not role or len(role) > 64:
            raise ValueError("Invalid role")
        self._refresh_budget_window()
        return (
            self._per_actor_budget - self._attempts.get(role, 0),
            self._total_budget - self._total_attempts,
        )

    @staticmethod
    def _sample_percentile(items: deque[float], quantile: float) -> float | None:
        if not items:
            return None
        ordered = sorted(items)
        return round(ordered[max(0, math.ceil(quantile * len(ordered)) - 1)], 5)

    @property
    def metrics(self) -> dict:
        """Bounded process-local queue metrics; never world receipts or private text.

        Existing 'started' is billed inference budget UNITS, not started
        underlying model forwards. G16 three-pass scoring bills three units
        for one detached Concordia invocation.
        """
        return {
            "started": self._total_attempts,
            "per_actor_started": dict(self._attempts),
            "inflight_roles": sorted(self._inflight),
            "timed_out_or_cancelled_roles": sorted(self._orphaned),
            "queue_observability": {
                **self._telemetry,
                "waiting_for_inference_slot": sorted(self._pending_slot_roles),
                "provider_active_roles": sorted(self._native_running_roles),
                "maximum_simultaneous_inference_invocations": (
                    self._maximum_simultaneous_inference_invocations),
                "queue_wait_samples": len(self._queue_wait_seconds),
                "provider_elapsed_samples": len(self._provider_elapsed_seconds),
                "adopted_elapsed_samples": len(self._adopted_elapsed_seconds),
                "queue_wait_median_seconds": self._sample_percentile(
                    self._queue_wait_seconds, 0.5),
                "queue_wait_p95_seconds": self._sample_percentile(
                    self._queue_wait_seconds, 0.95),
                "provider_elapsed_p95_seconds": self._sample_percentile(
                    self._provider_elapsed_seconds, 0.95),
                "adopted_elapsed_p95_seconds": self._sample_percentile(
                    self._adopted_elapsed_seconds, 0.95),
                "samples_per_metric_bounded_at": 256,
                "real_native_forward_count_not_established": True,
                "process_restart_resets_observability": True,
            },
        }

    async def choose(
        self, role: str, brain, primary: CommandOption, *, alternative: str,
    ):
        """Offer the same action and safe defer option as legacy LiveCrewBrain."""
        if brain.role != role or not isinstance(primary, CommandOption):
            raise PermissionError("Inconsistent world role and cognition identity")
        if not isinstance(alternative, str) or not alternative:
            raise ValueError("Deferral label is required")
        return await self.decide(
            role, brain.agent, (primary, CommandOption(alternative, "defer")),
        )

    async def decide(
        self,
        role: str,
        agent: CrewAgent,
        options: Sequence[CommandOption],
        *,
        decision_context: str | None = None,
        inference_model: Any | None = None,
        prepared_request_id: str | None = None,
        before_adopt: Callable[[CrewAgent, ActionRequest], None] | None = None,
        cost_units: int = 1,
        service_timeout_seconds: float | None = None,
    ):
        """Infer off-thread, checkpoint optional choice before main-loop adoption.

        The optional G16c hook executes only on the event-loop owner, after
        detached inference and revision checks but BEFORE the live agent gets
        a pending ActionRequest. A failing callback cannot adopt a proposal.
        All legacy callers use the unchanged default one-unit path.
        """
        if not isinstance(role, str) or not role or len(role) > 64:
            raise ValueError("Invalid role")
        if not isinstance(agent, CrewAgent):
            raise TypeError("Cognition requires a real CrewAgent")
        if role in self._inflight:
            raise CognitionBusy("An earlier decision is still owned by this actor")
        if type(cost_units) is not int or not 1 <= cost_units <= 16:
            raise ValueError("Model call units must be 1..16")
        if before_adopt is not None and not callable(before_adopt):
            raise TypeError("Pre-adoption checkpoint hook must be callable")
        deadline = self._timeout if service_timeout_seconds is None else service_timeout_seconds
        if (
            type(deadline) not in (int, float)
            or not math.isfinite(deadline)
            or not 0 < deadline <= self._timeout
        ):
            raise ValueError("Service deadline may only narrow the configured worker limit")
        self._refresh_budget_window()
        if (self._attempts.get(role, 0) + cost_units > self._per_actor_budget
                or self._total_attempts + cost_units > self._total_budget):
            raise CognitionBudgetExceeded("Inference quota exhausted; no action authorised")
        # Validate the menu before charging for or beginning inference. An
        # output will always be checked against this identical finite menu.
        offered = tuple(options)
        if not offered or any(not isinstance(x, CommandOption) for x in offered):
            raise ValueError("Invalid bounded menu")
        if len({x.label for x in offered}) != len(offered) or any(
            not x.label or not x.verb for x in offered
        ):
            raise ValueError("Duplicate/empty offered option")
        if decision_context is not None and (
            not isinstance(decision_context, str)
            or not 1 <= len(decision_context) <= 1200
        ):
            raise ValueError("Decision context must be bounded nonempty text")
        revision = agent.revision
        cognition_revision = agent.cognition_revision
        shadow = (agent.fork_for_inference() if inference_model is None
                  else agent.fork_for_inference(model_override=inference_model))
        self._attempts[role] = self._attempts.get(role, 0) + cost_units
        self._total_attempts += cost_units
        self._telemetry["requests_accepted_for_scheduling"] += 1
        queued_at = time.monotonic()

        abandoned = threading.Event()
        provider_started = False

        async def infer():
            nonlocal provider_started
            self._pending_slot_roles.add(role)
            try:
                async with self._sem:
                    self._pending_slot_roles.discard(role)
                    # An expired/cancelled decision still waiting for a
                    # global inference slot cannot start native work.
                    if abandoned.is_set():
                        self._telemetry["expired_queue_entries_discarded"] += 1
                        raise CognitionTimedOut(
                            "Queued inference expired before execution")
                    started_at = time.monotonic()
                    self._queue_wait_seconds.append(started_at - queued_at)
                    self._native_running_roles.add(role)
                    provider_started = True
                    self._telemetry["inference_invocations_started"] += 1
                    self._maximum_simultaneous_inference_invocations = max(
                        self._maximum_simultaneous_inference_invocations,
                        len(self._native_running_roles))
                    try:
                        choose_kwargs = {
                            "expected_revision": revision,
                            "decision_context": decision_context,
                        }
                        if prepared_request_id is not None:
                            choose_kwargs["request_id"] = prepared_request_id
                        return await asyncio.to_thread(
                            shadow.decide, offered, **choose_kwargs,
                        )
                    finally:
                        self._native_running_roles.discard(role)
                        self._telemetry["inference_invocations_finished"] += 1
                        self._provider_elapsed_seconds.append(
                            time.monotonic() - started_at)
            finally:
                self._pending_slot_roles.discard(role)

        task = asyncio.create_task(infer(), name="ox-infer-" + role)
        self._inflight[role] = task

        def finished(finished_task: asyncio.Task) -> None:
            # Always retrieve exceptions, even when the waiter has already
            # timed out. Late provider details must not escape via task logs.
            if not finished_task.cancelled():
                finished_task.exception()
            if role in self._orphaned and self._inflight.get(role) is finished_task:
                # Expired tasks that never passed the semaphore are not
                # late provider completions. Count only real started work.
                if provider_started:
                    self._telemetry["provider_finished_after_abandonment"] += 1
                self._orphaned.discard(role)
                del self._inflight[role]

        task.add_done_callback(finished)
        try:
            draft = await asyncio.wait_for(asyncio.shield(task), deadline)
            # Only the event-loop owner may write a durable G16c choice.
            # This guard avoids freezing a choice from a stale worker before
            # the live agent's own adopt_inference repeats its full checks.
            if before_adopt is not None:
                if (agent.revision != revision
                        or agent.cognition_revision != cognition_revision):
                    raise StaleAgentRevision("Choice changed while inference was detached")
                before_adopt(shadow, draft)
            # Only the live agent, on the event loop, can adopt the proposed
            # action. Both authenticated observations AND new private memories
            # can invalidate a detached actor while inference is underway.
            adopted = agent.adopt_inference(
                shadow, draft, offered,
                expected_revision=revision,
                expected_cognition_revision=cognition_revision,
            )
            self._telemetry["proposals_adopted"] += 1
            self._adopted_elapsed_seconds.append(
                time.monotonic() - queued_at)
            return adopted
        except asyncio.TimeoutError:
            abandoned.set()
            bucket = ("timed_out_with_provider_active"
                      if role in self._native_running_roles
                      else "timed_out_waiting_for_slot")
            self._telemetry[bucket] += 1
            raise CognitionTimedOut("Inference deadline passed; proposed action discarded") from None
        except asyncio.CancelledError:
            abandoned.set()
            self._telemetry["cancelled"] += 1
            raise
        except StaleAgentRevision:
            self._telemetry["stale_proposals_rejected"] += 1
            raise
        except (PermissionError, CognitionBusy, CognitionBudgetExceeded):
            self._telemetry["inference_failed"] += 1
            raise
        except Exception:
            self._telemetry["inference_failed"] += 1
            # Never echo provider exceptions: these may contain prompts or keys.
            raise CognitionUnavailable("Inference failed; no action submitted") from None
        finally:
            if task.done():
                if self._inflight.get(role) is task:
                    del self._inflight[role]
                self._orphaned.discard(role)
            else:
                self._orphaned.add(role)
