"""Real external navigation probe: ordinary Ari client, no privileged transport.

The world test fixture initially stations Ari in the Crew Mess. This
handler never uses move_to() or accesses Evennia's database. It learns
ship topology only through the oxcapabilities command and uses stock exits.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import os
import sys

from ox_ai.agents.live_concordia import LiveCrewBrain, make_model
from ox_ai.planning.navigation import CrewNavigator, NavigationKnowledge
from ox_ai.ports.evennia.capabilities import CapabilityPort
from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.runtime.watch_service import ROOT, URL, atomic_json


async def run(mode: str) -> dict:
    if mode not in ("direct", "blocked", "reroute"):
        raise ValueError("Unknown navigation trial mode")
    identities = json.loads((ROOT / "p3a-ids.json").read_text(encoding="utf-8"))
    actor_id = identities["ari"]
    checkpoint = ROOT / "g2c-ari-navigation.json"
    previous = (json.loads(checkpoint.read_text(encoding="utf-8"))
                if checkpoint.exists() else None)
    knowledge = NavigationKnowledge(actor_id, previous)
    brain = LiveCrewBrain("ari", actor_id, make_model("mock"))
    client = EvenniaWebSocketClient(
        URL, "OxBotAri", os.environ["OX_PROBE_PASSWORD"], actor_id, timeout=15,
    )
    async with client:
        navigator = CrewNavigator(CapabilityPort(client), brain=brain,
                                  knowledge=knowledge)
        result = await navigator.navigate("Engineering", max_movements=24)
        atomic_json(checkpoint, navigator.knowledge.to_record())
        report = {
            **asdict(result),
            "mode": mode,
            "actor_dbref": actor_id,
            "inference_calls": brain.inference_calls,
            "known_rooms": len(navigator.knowledge.rooms),
            "equipment_work_submissions": 0,
        }
        atomic_json(ROOT / "g2c-navigation-result.json", report)
    print("OX_G2C_NAVIGATION_RESULT", json.dumps(report, sort_keys=True))
    return report


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m ox_ai.runtime.navigation_trial direct|blocked|reroute")
    asyncio.run(run(sys.argv[1]))


if __name__ == "__main__":
    main()
