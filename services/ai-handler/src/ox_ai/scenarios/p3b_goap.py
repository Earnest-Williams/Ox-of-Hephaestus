"""An external GOAP repair whose handler restarts after losing an ACK.

'start' and 'resume' run as separate OS processes. The world continues.
The first process deliberately discards the acknowledged isolate outcome,
checkpointing ONLY an unresolved request ID. The next process reconciles
with a real, persistent Evennia receipt and never repeats isolation.
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

CHECKPOINT = Path(".ox-state/p3b-pending.json")
CREW_IDS = Path(".ox-state/p3a-ids.json")
URL = "ws://127.0.0.1:4002"


async def inspect(client: EvenniaWebSocketClient) -> str:
    for attempt in range(3):
        await client.send_line("inspect pump")
        try:
            return await client.expect_text("Cooling Pump P-01", timeout=6)
        except TimeoutError:
            if attempt == 2:
                raise
    raise RuntimeError("Physical readout unavailable")


def plan_from(text: str, expected: str) -> tuple[list[str], int]:
    if expected not in text:
        raise RuntimeError("Engineer lacks a fresh physical observation of " + expected)
    state = {"LOW PRESSURE": "pump_low_pressure", "ISOLATED": "pump_isolated"}[expected]
    plan = GoapPlanner(pump_action_model()).plan(
        frozenset({"at_engineering", "status_known", state}),
        frozenset({"pump_normal"}),
    )
    ops = [a.verb for a in plan.actions if a.verb in {"isolate", "repair", "commission"}]
    required = (["isolate", "repair", "commission"] if expected == "LOW PRESSURE"
                else ["repair", "commission"])
    if ops != required:
        raise AssertionError("GOAP did not produce a safe recovery sequence")
    return ops, plan.expanded_states


async def start() -> None:
    crew = json.loads(CREW_IDS.read_text())
    async with EvenniaWebSocketClient(URL, "OxBotAri",
                                      os.environ["OX_PROBE_PASSWORD"],
                                      crew["ari"]) as client:
        ops, count = plan_from(await inspect(client), "LOW PRESSURE")
        ident = uuid.uuid4().hex
        CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT.write_text(json.dumps({
            "character": crew["ari"], "request_id": ident,
            "status": "unknown", "planned": ops, "goap_expansions": count,
        }), encoding="utf-8")
        await client.send_line(f"oxaction {ident} isolate")
        # Intercept the real OOB packet, discard it as if its delivery were
        # lost, and terminate without recording success in handler state.
        for _ in range(48):
            packet = await client.receive()
            if packet.kind == "ox_receipt":
                break
        else:
            raise RuntimeError("No authoritative isolation receipt to drop")
    print("OX_P3B_UNKNOWN_ISOLATION_CHECKPOINTED")


async def resume() -> None:
    snapshot = json.loads(CHECKPOINT.read_text())
    crew = json.loads(CREW_IDS.read_text())
    if snapshot["character"] != crew["ari"] or snapshot["status"] != "unknown":
        raise RuntimeError("Cannot restore mismatched handler checkpoint")
    async with EvenniaWebSocketClient(URL, "OxBotAri",
                                      os.environ["OX_PROBE_PASSWORD"],
                                      crew["ari"]) as client:
        port = DurableEvenniaPort(client)
        original = await port.reconcile(snapshot["request_id"])
        if original.status != "succeeded" or not original.source_event_id:
            raise RuntimeError("Lost isolation ACK not reconciled to a world transition")
        actions, expansions = plan_from(await inspect(client), "ISOLATED")
        new_requests = []
        for operation in actions:
            req = ActionRequest(uuid.uuid4().hex, crew["ari"],
                                operation + "_pump", "pump")
            result = await port.submit(req)
            if result.status != "succeeded" or not result.source_event_id:
                raise RuntimeError("Physical operation was not confirmed: " + operation)
            new_requests.append(req.request_id)
        if "NORMAL" not in await inspect(client):
            raise RuntimeError("Engineer could not verify final normal pressure")
    CHECKPOINT.with_name("p3b-verdict.json").write_text(json.dumps({
        "status": "passed", "reconciled_event": original.source_event_id,
        "new_action_ids": new_requests, "inference_calls": 0,
        "goap_expansions": expansions + snapshot["goap_expansions"],
    }), encoding="utf-8")
    print("OX_P3B_DURABLE_GOAP_PASS")


def main() -> None:
    import sys
    if len(sys.argv) != 2 or sys.argv[1] not in ("start", "resume"):
        raise SystemExit("Usage: python -m ox_ai.scenarios.p3b_goap start|resume")
    asyncio.run(start() if sys.argv[1] == "start" else resume())


if __name__ == "__main__":
    main()
