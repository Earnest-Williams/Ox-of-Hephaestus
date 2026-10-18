"""Run Scenario 0 end-to-end with three independently scoped mock crew.

Usage:
    python -m ox_ai.scenarios.watch_handover

The printed JSON is an OPERATOR diagnostic (private agent memories included);
it is not an NPC observation stream or proof of live Evennia transport.
"""

from __future__ import annotations

from dataclasses import asdict
import json

from ox_ai.ports.mock.watch_world import MockWatchWorld
from ox_ai.scheduler.watch import WatchSupervisor


def run_demo() -> dict:
    world = MockWatchWorld()
    handler = WatchSupervisor(world)
    quiet_deliveries = handler.advance_to(440)

    world.advance_to(450)
    world.sense_pressure_drift(
        "P-01 pressure oscillation; unverified, inspect next watch"
    )
    world.bridge_navigation_update(
        "Navigation plot nominal; follow the posted bridge watch"
    )
    initial_deliveries = handler.pump()
    before = world.active_watch["engineering"]
    handler.advance_to(474)
    handover_deliveries = handler.advance_to(475)

    private_memories = {
        key: list(agent.memories) for key, agent in handler.agents.items()
    }
    assert quiet_deliveries == 0
    assert initial_deliveries == 2
    assert before == "ari"
    assert world.active_watch["engineering"] == "iona"
    assert handler.inference_calls == 0
    assert handler.world_submissions == 2
    assert any(
        event["kind"] == "handover_report"
        for event in private_memories["iona"]
    )
    assert not any(
        "pressure oscillation" in event["text"]
        for event in private_memories["lin"]
    )
    assert all(not agent.pending_requests for agent in handler.agents.values())

    return {
        "scenario": "shift_handover_00",
        "status": "passed",
        "scope": "deterministic_mock_world_only",
        "game_minute": world.minute,
        "quiet_interval_wakeups": quiet_deliveries,
        "initial_scoped_deliveries": initial_deliveries,
        "handover_deliveries": handover_deliveries,
        "original_active_engineer": before,
        "current_active_engineer": world.active_watch["engineering"],
        "world_submissions": handler.world_submissions,
        "inference_calls": handler.inference_calls,
        "wake_counts": handler.wake_counts,
        "authoritative_events": [asdict(event) for event in world.events],
        "operator_only_agent_memories": private_memories,
    }


def main() -> None:
    print(json.dumps(run_demo(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
