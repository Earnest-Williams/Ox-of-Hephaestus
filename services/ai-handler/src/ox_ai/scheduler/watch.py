"""Event-triggered three-crew supervisor for the authoritative mock world.

A scheduled obligation generates one world event; world observations awaken
only their addressee. No polling per agent, LLM call, or simulated GM narration.
The world owns clock and duty changes, not the scheduler or a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush

from ox_ai.agents.mock_watch import MockWatchAgent, default_watch_agents
from ox_ai.ports.base import ActionRequest
from ox_ai.ports.mock.watch_world import MockWatchWorld


@dataclass(frozen=True, order=True, slots=True)
class ScheduledDuty:
    minute: int
    sequence: int
    kind: str


class WatchSupervisor:
    """Deliver scoped events, execute proposed actions and preserve pending IDs."""

    def __init__(
        self,
        world: MockWatchWorld,
        agents: dict[str, MockWatchAgent] | None = None,
        *,
        initial_schedule: bool = True,
    ) -> None:
        self.world = world
        self.agents = agents if agents is not None else default_watch_agents()
        if set(self.agents) != set(world.crew):
            raise ValueError("Supervisor must bind exactly the three mock crew")
        if any(
            key != agent.identity.character_id
            for key, agent in self.agents.items()
        ):
            raise ValueError("Agent/world character ID mismatch")
        self._agenda: list[ScheduledDuty] = []
        self._serial = 0
        self.wake_counts = {key: 0 for key in self.agents}
        self.world_submissions = 0
        self.inference_calls = 0
        if initial_schedule:
            self.schedule(
                world.ENGINEERING_HANDOVER_MINUTE, "engineering_handover"
            )

    def schedule(self, minute: int, kind: str) -> None:
        if minute < self.world.minute:
            raise ValueError("Cannot schedule events in the world clock's past")
        if kind != "engineering_handover":
            raise ValueError("Unsupported watch-duty event")
        heappush(self._agenda, ScheduledDuty(minute, self._serial, kind))
        self._serial += 1

    @property
    def pending_schedule(self) -> tuple[ScheduledDuty, ...]:
        return tuple(sorted(self._agenda))

    def pump(self, *, max_deliveries: int = 128) -> int:
        """Drain only actual queued events, never call an idle agent.

        Bound work so a faulty agent/world feedback loop cannot monopolise
        the handler. Running again resumes unconsumed world events.
        """
        if max_deliveries < 1:
            raise ValueError("max_deliveries must be positive")
        delivered = 0
        while self.world.pending_observations:
            if delivered >= max_deliveries:
                raise RuntimeError("Mock crew event-dispatch budget exhausted")
            item = self.world.next_observation()
            if item is None:
                break
            character_id, observation = item
            agent = self.agents[character_id]
            request = agent.observe(
                observation, expected_revision=agent.revision
            )
            self.wake_counts[character_id] += 1
            delivered += 1
            if request is not None:
                self._submit(request)
        return delivered

    def _submit(self, request: ActionRequest) -> None:
        if request.character_id not in self.agents:
            raise PermissionError("Unrecognised agent cannot submit commands")
        agent = self.agents[request.character_id]
        if request.agent_revision != agent.revision:
            from ox_ai.agents.crew import StaleAgentRevision

            raise StaleAgentRevision("Discarding stale mock-world action proposal")
        if request not in agent.pending_requests:
            raise PermissionError("Only this agent's outstanding request is valid")
        self.world_submissions += 1
        result = self.world.submit(request)
        self.agents[request.character_id].record_outcome(result)

    def advance_to(self, minute: int) -> int:
        """Advance authoritative mock time, fire due events, drain deliveries."""
        self.world.advance_to(minute)
        while self._agenda and self._agenda[0].minute <= self.world.minute:
            duty = heappop(self._agenda)
            if duty.kind == "engineering_handover":
                self.world.announce_handover_due()
        return self.pump()

    def reconcile_pending(self) -> int:
        """Resolve ACK loss by querying world history, NOT resubmitting."""
        resolved = 0
        for character_id, agent in self.agents.items():
            for request in agent.pending_requests:
                outcome = self.world.reconcile(
                    request.request_id, character_id=character_id
                )
                agent.record_outcome(outcome)
                if outcome.status in ("succeeded", "failed"):
                    resolved += 1
        return resolved

    def snapshot(self) -> dict:
        """Checkpoint handler-owned state only; world remains authoritative."""
        return {
            "world_minute": self.world.minute,
            "agents": {key: agent.snapshot() for key, agent in self.agents.items()},
            "agenda": [
                {"minute": x.minute, "sequence": x.sequence, "kind": x.kind}
                for x in sorted(self._agenda)
            ],
            "serial": self._serial,
            "wake_counts": dict(self.wake_counts),
            "world_submissions": self.world_submissions,
            "inference_calls": 0,
        }

    @classmethod
    def from_snapshot(cls, world: MockWatchWorld, payload: dict) -> WatchSupervisor:
        """Restore against the *same* mock world with no action replay."""
        if world.minute < payload["world_minute"]:
            raise ValueError("Cannot restore handler ahead of world clock")
        known = set(default_watch_agents())
        if set(payload["agents"]) != known:
            raise ValueError("Checkpoint crew identities do not match fixture")
        agents = {
            key: MockWatchAgent.from_snapshot(item)
            for key, item in payload["agents"].items()
        }
        result = cls(world, agents, initial_schedule=False)
        result._agenda = [ScheduledDuty(**item) for item in payload["agenda"]]
        for item in result._agenda:
            if item.minute < world.minute:
                raise ValueError("Checkpoint contains a stale scheduled duty")
        result._serial = payload["serial"]
        result.wake_counts = dict(payload["wake_counts"])
        result.world_submissions = payload["world_submissions"]
        if payload["inference_calls"] != 0:
            raise ValueError("Model invocation count invalid for mock watch")
        return result
