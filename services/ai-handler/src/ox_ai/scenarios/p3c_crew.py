"""P3c: three normal Evennia clients coordinate one world-owned incident.

Deterministic event-triggered policies run in a separate process. No NPC sees
the aggregate event log or another person's memory. Each receives ordinary
readouts or addressed OOB events. GOAP plans genuine physical repair commands.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import uuid

from ox_ai.agents.goap_crew import pump_action_model
from ox_ai.planning.goap import GoapPlanner
from ox_ai.ports.base import ActionRequest
from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.scenarios.p3b_goap import inspect

IDS = Path(".ox-state/p3a-ids.json")
URL = "ws://127.0.0.1:4002"


async def next_event(client, expected: str, memory: list[dict]) -> dict:
    """Block on actual character-addressed world messages, not an idle tick."""
    async with asyncio.timeout(25):
        for _ in range(128):
            packet = await client.receive()
            if packet.kind != "ox_event":
                continue
            if len(packet.args) == 1 and isinstance(packet.args[0], str):
                event = json.loads(packet.args[0])
            else:
                raise ValueError("Malformed private observation framing")
            if not isinstance(event, dict) or not isinstance(event.get("data"), dict):
                raise ValueError("Malformed world event content")
            if event.get("recipient_dbref") != client.character_dbref:
                raise PermissionError("Another character's memory leaked")
            memory.append(event)
            if event.get("kind") == expected:
                return event
    raise RuntimeError("Expected scoped world event never arrived")


async def read_console(client) -> str:
    for attempt in range(3):
        await client.send_line("inspect console")
        try:
            return await client.expect_text("BRIDGE COOLING TELEMETRY", timeout=6)
        except TimeoutError:
            if attempt == 2:
                raise
    raise RuntimeError("No bridge telemetry")


async def main_async() -> dict:
    ids = json.loads(IDS.read_text())
    password = os.environ["OX_PROBE_PASSWORD"]
    clients = {
        role: EvenniaWebSocketClient(
            URL, name, password, ids[role], timeout=15,
        )
        for role, name in (
            ("lin", "OxBotLin"), ("ari", "OxBotAri"), ("iona", "OxBotIona")
        )
    }
    memories = {role: [] for role in clients}
    transitions = []
    planning_expansions = 0
    try:
        # All three independent in-game bodies become authenticated. Only
        # the bridge officer asks for the initial persisted bridge alarm.
        for client in clients.values():
            await client.open()
        lin, ari, iona = (clients[role] for role in ("lin", "ari", "iona"))
        await lin.send_line("oxinbox 0")
        alarm = await next_event(lin, "coolant_alarm", memories["lin"])
        if "LOW PRESSURE" not in await read_console(lin):
            raise RuntimeError("Lin could not verify the low-pressure bridge alarm")
        await lin.send_line("oxradio")
        report = await next_event(ari, "radio_alert", memories["ari"])
        if report["data"]["alarm_id"] != alarm["data"]["alarm_id"]:
            raise RuntimeError("Ari's radio message did not identify Lin's alarm")

        local = await inspect(ari)
        if "LOW PRESSURE" not in local:
            raise RuntimeError("Ari did not physically inspect the broken pump")
        plan = GoapPlanner(pump_action_model()).plan(
            frozenset({"at_engineering", "status_known", "pump_low_pressure"}),
            frozenset({"pump_repaired"}),
        )
        planning_expansions += plan.expanded_states
        physical_actions = [action.verb for action in plan.actions
                            if action.verb in ("isolate", "repair", "commission")]
        if physical_actions != ["isolate", "repair"]:
            raise RuntimeError("GOAP failed to plan proper pre-commission repair")
        port = DurableEvenniaPort(ari)
        for verb in physical_actions:
            request = ActionRequest(uuid.uuid4().hex, ids["ari"],
                                    verb + "_pump", "pump")
            result = await port.submit(request)
            if result.status != "succeeded" or not result.source_event_id:
                raise RuntimeError("The world refused GOAP action " + verb)
            transitions.append(verb)
        if "REPAIRED" not in await inspect(ari):
            raise RuntimeError("GOAP effects were not independently observed")

        await ari.send_line("oxrequest")
        await next_event(iona, "release_request", memories["iona"])
        if "REPAIRED" not in await inspect(iona):
            raise RuntimeError("Chief did not personally inspect repaired P-01")
        await iona.send_line("oxapprove")
        await next_event(ari, "release_granted", memories["ari"])
        request = ActionRequest(uuid.uuid4().hex, ids["ari"],
                                "commission_pump", "pump")
        commissioned = await port.submit(request)
        if commissioned.status != "succeeded" or not commissioned.source_event_id:
            raise RuntimeError("Chief release was not world-valid")
        transitions.append("commission")
        if "NORMAL" not in await inspect(ari):
            raise RuntimeError("Ari could not verify commissioned pressure")
        await ari.send_line("oxresolve")
        await next_event(lin, "incident_resolved", memories["lin"])
        await next_event(iona, "incident_resolved", memories["iona"])

        # The authoritative world advances its scripted watch time at the
        # resolved incident. Each character sees only their own due event.
        await next_event(ari, "handover_due", memories["ari"])
        await next_event(iona, "handover_due", memories["iona"])
        await ari.send_line("oxhandover")
        offer = await next_event(iona, "handover_offer", memories["iona"])
        if offer["data"]["uncertainty"] != "unverified":
            raise RuntimeError("Handover distorted uncertain knowledge")
        await iona.send_line("oxaccept")
        await next_event(ari, "watch_transferred", memories["ari"])
        await next_event(iona, "watch_transferred", memories["iona"])

        if "pump_readout" in [item["kind"] for item in memories["lin"]]:
            raise AssertionError("Bridge received a private pump inspection")
        if "coolant_alarm" in [item["kind"] for item in memories["iona"]]:
            raise AssertionError("Chief received an omniscient bridge alarm")
        if not memories["ari"] or not memories["lin"] or not memories["iona"]:
            raise AssertionError("One crew member had no individual experiences")
        return {
            "status": "passed", "scope": "real_evennia_three_clients",
            "roles": ids, "goap_expanded_states": planning_expansions,
            "physical_actions": transitions, "inference_calls": 0,
            "private_memories_operator_only": memories,
        }
    finally:
        await asyncio.gather(*(client.close() for client in clients.values()),
                             return_exceptions=True)


def main() -> None:
    result = asyncio.run(main_async())
    path = Path(".ox-state/p3c-verdict.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("OX_P3C_LIVE_THREE_CREW_PASS")


if __name__ == "__main__":
    main()
