"""P2 cooling coordinator reusing the watch event queue and world boundary.

The supervisor never supplies equipment state to a crew policy. It merely
routes addressed observations and submits proposals through MockCoolantWorld.
"""

from __future__ import annotations

from ox_ai.agents.coolant_crew import CoolantCrewAgent, default_coolant_agents
from ox_ai.ports.mock.coolant_world import MockCoolantWorld
from ox_ai.scheduler.watch import WatchSupervisor


class CoolantSupervisor(WatchSupervisor):
    """Three separate, deterministic crew policies with model-free GOAP."""

    def __init__(
        self,
        world: MockCoolantWorld,
        agents: dict[str, CoolantCrewAgent] | None = None,
    ):
        # Incident occurs during an existing watch, before 07:55; the world
        # retains the scheduled duty semantics in the normal WatchSupervisor.
        super().__init__(
            world,
            agents=agents if agents is not None else default_coolant_agents(),
            initial_schedule=False,
        )

    @property
    def planning_calls(self) -> int:
        return sum(agent.planning_calls for agent in self.agents.values())

    @property
    def expanded_states(self) -> int:
        return sum(agent.expanded_states for agent in self.agents.values())

    @property
    def replans(self) -> int:
        return sum(agent.replans for agent in self.agents.values())

    def reconcile_pending(self) -> int:
        """After world receipt reconciliation, resume only unblocked policies."""
        awaiting = {
            key for key, agent in self.agents.items() if agent.pending_requests
        }
        # Process queued post-command observations and urgent interrupts
        # WHILE requests are still pending. A recovering agent must not
        # issue its next physical operation from a stale pre-restart view.
        self.pump()
        resolved = super().reconcile_pending()
        # No retry of the old operation occurs. The next command, if any,
        # uses beliefs already established by delivered world events.
        for key in awaiting:
            agent = self.agents[key]
            if not agent.pending_requests:
                next_request = agent.continue_after_reconciliation()
                if next_request is not None:
                    self._submit(next_request)
        self.pump()
        return resolved

    @classmethod
    def from_snapshot(
        cls, world: MockCoolantWorld, payload: dict
    ) -> CoolantSupervisor:
        if world.minute < payload["world_minute"]:
            raise ValueError("Cannot restore handler ahead of world clock")
        if payload["inference_calls"] != 0:
            raise ValueError("Coolant scenario must not have model calls")
        known = set(default_coolant_agents())
        if set(payload["agents"]) != known:
            raise ValueError("Checkpoint crew does not match the mock world")
        if payload["agenda"]:
            raise ValueError("Cooling fixture cannot restore watch handover duties")
        agents = {
            key: CoolantCrewAgent.from_snapshot(item)
            for key, item in payload["agents"].items()
        }
        result = cls(world, agents)
        result.wake_counts = dict(payload["wake_counts"])
        result.world_submissions = payload["world_submissions"]
        result._serial = payload["serial"]
        return result
