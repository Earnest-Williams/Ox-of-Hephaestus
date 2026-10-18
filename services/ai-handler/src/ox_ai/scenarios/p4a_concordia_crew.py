"""P4a: real three-character Evennia incident with native Concordia choices.

The old P3c authored scenario remains the zero-inference regression baseline.
Here each role's *own* Concordia entity chooses the response to its scoped
world events. GOAP handles routine physical repair only after Ari elects it.
All in-world work travels through normal authenticated Evennia clients.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import uuid

from ox_ai.agents.crew import CommandOption
from ox_ai.agents.live_concordia import build_live_brains
from ox_ai.agents.goap_crew import pump_action_model
from ox_ai.planning.goap import GoapPlanner
from ox_ai.ports.base import ActionRequest
from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.scenarios.p3b_goap import inspect
from ox_ai.scenarios.p3c_crew import IDS, URL, next_event, read_console, replayable_event


async def run() -> dict:
    ids = json.loads(IDS.read_text(encoding="utf-8"))
    password = os.environ["OX_PROBE_PASSWORD"]
    root = Path(".ox-state/p4a")
    brains = build_live_brains(ids, journal_dir=root)
    clients = {
        role: EvenniaWebSocketClient(
            URL, name, password, ids[role], timeout=15,
        )
        for role, name in (
            ("lin", "OxBotLin"), ("ari", "OxBotAri"), ("iona", "OxBotIona")
        )
    }
    memory: dict[str, list[dict]] = {role: [] for role in clients}
    world_actions: list[str] = []
    try:
        for client in clients.values():
            await client.open()
        lin, ari, iona = (clients[k] for k in ("lin", "ari", "iona"))
        bridge, engineer, chief = (brains[k] for k in ("lin", "ari", "iona"))

        alarm = await replayable_event(lin, "coolant_alarm", memory["lin"])
        bridge.observe_event(alarm)
        readout = await read_console(lin)
        bridge.observe_local("Bridge telemetry", readout)
        if "LOW PRESSURE" not in readout:
            raise RuntimeError("Bridge did not observe a low-pressure alarm")
        alert = bridge.choose(
            CommandOption("Relay observed alarm to engineering", "oxradio"),
            alternative="Defer alert pending another bridge readout",
        )
        bridge.require(alert, "oxradio")
        await lin.send_line("oxradio")
        radio = await next_event(ari, "radio_alert", memory["ari"])
        bridge.confirm(alert, {
            "event_id": radio["event_id"], "recipient_dbref": bridge.character_id,
            "kind": "radio_delivered", "text": "Engineering received bridge relay",
            "game_time": radio["game_time"],
        }) if False else None
        # The relay is addressed to Ari, not Lin. A cross-recipient event is
        # NEVER a valid acknowledgement to Lin's Concordia memory.
        bridge.record_unknown(alert)
        engineer.observe_event(radio)
        if radio["data"]["alarm_id"] != alarm["data"]["alarm_id"]:
            raise RuntimeError("Engineering heard a different alarm")
        investigate = engineer.choose(
            CommandOption("Inspect nearby pump physically", "inspect_pump"),
            alternative="Ask bridge to reassess without touching machinery",
        )
        engineer.require(investigate, "inspect_pump")
        local = await inspect(ari)
        engineer.observe_local("P-01 direct inspection", local)
        engineer.selected_procedure(investigate)
        if "LOW PRESSURE" not in local:
            raise RuntimeError("Engineer never observed the actual fault")
        decision = engineer.choose(
            CommandOption("Execute trained GOAP isolation-and-repair procedure", "goap"),
            alternative="Escalate fault without attempting repair",
        )
        engineer.require(decision, "goap")
        engineer.selected_procedure(decision)
        plan = GoapPlanner(pump_action_model()).plan(
            frozenset({"at_engineering", "status_known", "pump_low_pressure"}),
            frozenset({"pump_repaired"}),
        )
        ops = [a.verb for a in plan.actions
               if a.verb in {"isolate", "repair", "commission"}]
        if ops != ["isolate", "repair"]:
            raise RuntimeError("GOAP did not select the safe partial repair")
        port = DurableEvenniaPort(ari)
        for verb in ops:
            req = ActionRequest(uuid.uuid4().hex, ids["ari"], verb+"_pump", "pump")
            outcome = await port.submit(req)
            if outcome.status != "succeeded" or not outcome.source_event_id:
                raise RuntimeError(f"World rejected {verb}")
            engineer.observe_local(
                "Authoritative physical receipt",
                f"{outcome.source_event_id}: {verb} {outcome.status}",
            )
            world_actions.append(verb)
        engineer.observe_local("Post-repair inspection", await inspect(ari))
        ask = engineer.choose(
            CommandOption("Request independent chief safety inspection", "oxrequest"),
            alternative="Defer chief safety review",
        )
        engineer.require(ask, "oxrequest")
        await ari.send_line("oxrequest")
        request = await next_event(iona, "release_request", memory["iona"])
        engineer.record_unknown(ask)
        chief.observe_event(request)
        if request["sender_dbref"] != ids["ari"]:
            raise RuntimeError("Chief request did not originate with the engineer")
        chief_inspect = chief.choose(
            CommandOption("Inspect repaired P-01 in person", "inspect_pump"),
            alternative="Withhold safety release without new inspection",
        )
        chief.require(chief_inspect, "inspect_pump")
        check = await inspect(iona)
        chief.observe_local("Independent safety inspection", check)
        chief.selected_procedure(chief_inspect)
        if "REPAIRED" not in check:
            raise RuntimeError("Chief could not verify repaired condition")
        approve = chief.choose(
            CommandOption("Approve independently inspected commissioning", "oxapprove"),
            alternative="Withhold commissioning authorization",
        )
        chief.require(approve, "oxapprove")
        await iona.send_line("oxapprove")
        recorded = await next_event(iona, "release_recorded", memory["iona"])
        chief.confirm(approve, recorded)
        released = await next_event(ari, "release_granted", memory["ari"])
        engineer.observe_event(released)
        commissioning = engineer.choose(
            CommandOption("Commission repaired pump after chief release", "goap"),
            alternative="Defer commissioning even with approval",
        )
        engineer.require(commissioning, "goap")
        engineer.selected_procedure(commissioning)
        final = await port.submit(
            ActionRequest(uuid.uuid4().hex, ids["ari"], "commission_pump", "pump")
        )
        if final.status != "succeeded" or not final.source_event_id:
            raise RuntimeError("World refused commissioning")
        world_actions.append("commission")
        engineer.observe_local("Physical commissioning receipt", final.source_event_id)
        check = await inspect(ari)
        engineer.observe_local("Verified normal loop pressure", check)
        if "NORMAL" not in check:
            raise RuntimeError("Ari never verified restored pressure")
        close = engineer.choose(
            CommandOption("Report verified resolution to bridge and chief", "oxresolve"),
            alternative="Hold incident open for another inspection",
        )
        engineer.require(close, "oxresolve")
        await ari.send_line("oxresolve")
        resolved_bridge = await next_event(lin, "incident_resolved", memory["lin"])
        resolved_chief = await next_event(iona, "incident_resolved", memory["iona"])
        engineer.record_unknown(close)
        bridge.observe_event(resolved_bridge)
        chief.observe_event(resolved_chief)
        due_engineer = await next_event(ari, "handover_due", memory["ari"])
        due_chief = await next_event(iona, "handover_due", memory["iona"])
        engineer.observe_event(due_engineer)
        chief.observe_event(due_chief)
        offer = engineer.choose(
            CommandOption("Offer watch to the incoming chief", "oxhandover"),
            alternative="Hold watch due to unresolved concerns",
        )
        engineer.require(offer, "oxhandover")
        await ari.send_line("oxhandover")
        handover = await next_event(iona, "handover_offer", memory["iona"])
        engineer.record_unknown(offer)
        chief.observe_event(handover)
        take = chief.choose(
            CommandOption("Accept authoritative watch transfer", "oxaccept"),
            alternative="Decline this watch handover",
        )
        chief.require(take, "oxaccept")
        await iona.send_line("oxaccept")
        changed_ari = await next_event(ari, "watch_transferred", memory["ari"])
        changed_iona = await next_event(iona, "watch_transferred", memory["iona"])
        engineer.observe_event(changed_ari)
        chief.confirm(take, changed_iona)
        if changed_iona["data"]["new_watch"] != ids["iona"]:
            raise RuntimeError("World did not transfer to chief")
        if any(
            event["kind"] == "coolant_alarm" for event in memory["iona"]
        ):
            raise PermissionError("Chief had omniscient access to bridge alarm")
        if "pump_readout" in {e["kind"] for e in memory["lin"]}:
            raise PermissionError("Bridge received engineer-only pump data")
        for role, brain in brains.items():
            brain.save_checkpoint(root / f"{role}.json")
        return {
            "status": "passed",
            "scope": "three_native_concordia_entities_live_evennia",
            "roles": ids,
            "model_provider": os.environ.get("OX_COGNITION_PROVIDER", "mock"),
            "decision_calls": {k: v.inference_calls for k, v in brains.items()},
            "world_actions": world_actions,
            "goap_expansions": plan.expanded_states,
            "entity_names": {k: v.agent.entity.name for k, v in brains.items()},
            "private_event_counts": {k: len(v) for k, v in memory.items()},
        }
    finally:
        await asyncio.gather(*(c.close() for c in clients.values()),
                             return_exceptions=True)


def main() -> None:
    verdict = asyncio.run(run())
    path = Path(".ox-state/p4a-verdict.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    print("OX_P4A_NATIVE_CONCORDIA_LIVE_CREW_PASS")


if __name__ == "__main__":
    main()
