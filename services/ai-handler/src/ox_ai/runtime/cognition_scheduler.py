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
from collections.abc import Sequence
import math
import time
import threading

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

    def _refresh_budget_window(self) -> None:
        # Model quota is a wall-time rate limit, not a cap on an entire
        # long-lived ship voyage. No model call is caused by this clock read.
        if time.monotonic() - self._window_started >= self._budget_window:
            self._window_started = time.monotonic()
            self._attempts.clear()
            self._total_attempts = 0

    @property
    def metrics(self) -> dict:
        """Diagnostic metadata only; does not expose private prompts or memories."""
        return {
            "started": self._total_attempts,
            "per_actor_started": dict(self._attempts),
            "inflight_roles": sorted(self._inflight),
            "timed_out_or_cancelled_roles": sorted(self._orphaned),
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
        self, role: str, agent: CrewAgent, options: Sequence[CommandOption],
    ):
        """Infer off-thread, then synchronously validate and adopt on the loop."""
        if not isinstance(role, str) or not role or len(role) > 64:
            raise ValueError("Invalid role")
        if not isinstance(agent, CrewAgent):
            raise TypeError("Cognition requires a real CrewAgent")
        if role in self._inflight:
            raise CognitionBusy("An earlier decision is still owned by this actor")
        self._refresh_budget_window()
        if (self._attempts.get(role, 0) >= self._per_actor_budget
                or self._total_attempts >= self._total_budget):
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
        revision = agent.revision
        shadow = agent.fork_for_inference()
        self._attempts[role] = self._attempts.get(role, 0) + 1
        self._total_attempts += 1

        abandoned = threading.Event()
        async def infer():
            async with self._sem:
                # An expired/cancelled decision still waiting for a global
                # inference slot should never consume quota at the provider.
                if abandoned.is_set():
                    raise CognitionTimedOut("Queued inference expired before execution")
                return await asyncio.to_thread(
                    shadow.decide, offered, expected_revision=revision,
                )

        task = asyncio.create_task(infer(), name="ox-infer-" + role)
        self._inflight[role] = task

        def finished(finished_task: asyncio.Task) -> None:
            # Always retrieve exceptions, even when the waiter has already
            # timed out. Late provider details must not escape via task logs.
            if not finished_task.cancelled():
                finished_task.exception()
            if role in self._orphaned and self._inflight.get(role) is finished_task:
                self._orphaned.discard(role)
                del self._inflight[role]

        task.add_done_callback(finished)
        try:
            draft = await asyncio.wait_for(asyncio.shield(task), self._timeout)
            # Only the live agent, on the event loop, can adopt the proposed
            # action. An observation received during inference increments the
            # live revision and makes the snapshot's choice uncommittable.
            return agent.adopt_inference(shadow, draft, offered, expected_revision=revision)
        except asyncio.TimeoutError:
            abandoned.set()
            raise CognitionTimedOut("Inference deadline passed; proposed action discarded") from None
        except asyncio.CancelledError:
            abandoned.set()
            raise
        except (StaleAgentRevision, PermissionError, CognitionBusy,
                CognitionBudgetExceeded):
            raise
        except Exception:
            # Never echo provider exceptions: these may contain prompts or keys.
            raise CognitionUnavailable("Inference failed; no action submitted") from None
        finally:
            if task.done():
                if self._inflight.get(role) is task:
                    del self._inflight[role]
                self._orphaned.discard(role)
            else:
                self._orphaned.add(role)
