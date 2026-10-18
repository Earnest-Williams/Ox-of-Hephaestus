"""P3c: three normal Evennia clients coordinate one world-owned incident.

Deterministic event-triggered policies run in a separate process. No NPC sees
the aggregate event log or another person's memory. Each receives ordinary
readouts or addressed OOB events. GOAP plans genuine physical repair commands.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from html import unescape
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


async def next_event(client, expected: str, memory: list[dict],
                     *, timeout: float = 25.0) -> dict:
    """Wait for legitimate, recipient-scoped world observations only."""
    received_types = []
    safe_text_samples = []
    seen = {event.get("event_id") for event in memory}
    try:
        async with asyncio.timeout(timeout):
            for _ in range(128):
                packet = await client.receive()
                received_types.append(packet.kind[:32])
                if packet.kind == "text" and len(safe_text_samples) < 3:
                    # Only synthetic CI observations; redact known secret
                    # before including a bounded diagnostic snippet.
                    safe = re.sub(r"<[^>]*>", "", unescape(packet.text))
                    secret = os.environ.get("OX_PROBE_PASSWORD", "")
                    if secret:
                        safe = safe.replace(secret, "[REDACTED]")
                    lines = [line.strip() for line in safe.splitlines() if line.strip()]
                    diagnostic = (lines[-1] if "Traceback" in safe and lines
                                  else re.sub(r"\s+", " ", safe)[:170])
                    safe_text_samples.append(diagnostic[:260])
                if packet.kind != "ox_event":
                    continue
                if len(packet.args) != 1 or not isinstance(packet.args[0], dict):
                    raise ValueError("Malformed private observation framing")
                wire = packet.args[0]
                if wire.get("recipient_dbref") != client.character_dbref:
                    raise PermissionError("Another character received a private observation")
                if "data" in wire:
                    raise ValueError("Nested world observation is forbidden")
                event = {key: value for key, value in wire.items()
                         if not key.startswith("datum_")}
                event["data"] = {key[len("datum_"):]: value
                                 for key, value in wire.items()
                                 if key.startswith("datum_")}
                if event.get("recipient_dbref") != client.character_dbref:
                    raise PermissionError("Another character's memory leaked")
                event_id = event.get("event_id")
                if not isinstance(event_id, str):
                    raise ValueError("World event lacks a stable ID")
                if event_id not in seen:
                    memory.append(event)
                    seen.add(event_id)
                if event.get("kind") == expected:
                    return event
    except TimeoutError as exc:
        raise TimeoutError(
            "Expected " + expected + " absent; received protocol kinds "
            + repr(received_types[-18:])
            + " text=" + repr(safe_text_samples)
        ) from exc
    raise RuntimeError("Event delivery budget exhausted")


async def replayable_event(client, expected: str, memory: list[dict]) -> dict:
    """On lost delivery, recover ONLY recipient-authorized event history.

    No physical command can be repeated by this helper. It reissues an
    idempotent inbox read at the most recent persisted event cursor.
    """
    for attempt in range(3):
        cursor = max((int(e.get("sequence", e["event_id"].split("-")[-1])) for e in memory),
                     default=0)
        await client.send_line(f"oxinbox {cursor}")
        try:
            return await next_event(client, expected, memory, timeout=9)
        except TimeoutError:
            if attempt == 2:
                raise
    raise RuntimeError("World inbox was unavailable")


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
        alarm = await replayable_event(lin, "coolant_alarm", memories["lin"])
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
