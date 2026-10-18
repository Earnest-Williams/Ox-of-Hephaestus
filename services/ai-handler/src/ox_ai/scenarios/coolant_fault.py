"""Scenario 1: coordinated cooling repair by three independently informed crew.

Usage:
    python -m ox_ai.scenarios.coolant_fault

Operator-only JSON includes the mock world's true machinery history and each
NPC's private delivered observations. None of that aggregate view is an
input to the characters themselves. Game time advances on explicit events.
"""

from __future__ import annotations

from dataclasses import asdict
import json

from ox_ai.ports.mock.coolant_world import MockCoolantWorld
from ox_ai.scheduler.coolant import CoolantSupervisor


def run_demo() -> dict:
    world = MockCoolantWorld()
    supervisor = CoolantSupervisor(world)
    quiet = supervisor.advance_to(120)
    assert quiet == 0
    assert supervisor.world_submissions == 0

    world.advance_to(180)
    alarm_id = world.trigger_fault()
    deliveries = supervisor.pump()
    actions = [event.operation for event in world.pump_history]
    actual = [event.actor_id for event in world.pump_history]
    memories = {
        key: list(agent.memories) for key, agent in supervisor.agents.items()
    }

    assert world.pump_state == "normal"
    assert world.incident_closed
    assert actions == ["fault", "isolate", "repair", "commission"]
    assert actual == [None, "ari", "ari", "ari"]
    assert supervisor.world_submissions == 10
    assert supervisor.inference_calls == 0
    assert supervisor.planning_calls >= 2
    assert supervisor.replans == 0
    assert all(not agent.pending_requests for agent in supervisor.agents.values())
    assert memories["lin"][0]["kind"] == "coolant_alarm"
    assert memories["ari"][0]["kind"] == "radio_alert"
    assert memories["iona"][0]["kind"] == "release_request"
    assert "coolant_alarm" not in [x["kind"] for x in memories["iona"]]
    assert "pump_readout" not in [x["kind"] for x in memories["lin"]]
    assert "incident_resolved" in [x["kind"] for x in memories["lin"]]
    assert alarm_id == memories["lin"][0]["observation_id"]

    return {
        "scenario": "coolant_fault_01",
        "scope": "deterministic_mock_world_only",
        "status": "passed",
        "game_minute": world.minute,
        "quiet_interval_wakeups": quiet,
        "event_deliveries": deliveries,
        "world_action_requests": supervisor.world_submissions,
        "inference_calls": supervisor.inference_calls,
        "goap_searches": supervisor.planning_calls,
        "goap_expanded_states": supervisor.expanded_states,
        "replans": supervisor.replans,
        "pump_state": world.pump_state,
        "incident_closed": world.incident_closed,
        "active_engineering_watch": world.active_watch["engineering"],
        "authoritative_pump_history": [
            asdict(item) for item in world.pump_history
        ],
        "authoritative_world_events": [asdict(e) for e in world.events],
        "wake_counts": supervisor.wake_counts,
        "operator_only_agent_memories": memories,
    }


def main() -> None:
    print(json.dumps(run_demo(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
