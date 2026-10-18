"""Persistent event-driven three-client crew supervisor (P4b).

Normal production entry: python -m ox_ai.runtime.watch_service serve
The supervisor sleeps on ordinary WebSocket observations when no world event
is pending. Evennia alone owns time, role permissions, physical transitions,
event visibility, safety approvals and receipts.

For a disposable two-process acceptance test, "begin" deliberately loses an
isolation acknowledgement after saving the request, and "resume" reconciles
it on a fresh process without repeating the operation.
"""
from __future__ import annotations

import asyncio
import json
from html import unescape
import os
from pathlib import Path
import re
import tempfile
import uuid

from ox_ai.agents.crew import CommandOption
from ox_ai.agents.live_concordia import (
    LiveCrewBrain, build_live_brains, make_model,
)
from ox_ai.agents.goap_crew import pump_action_model
from ox_ai.planning.goap import GoapPlanner
from ox_ai.ports.base import ActionRequest
from ox_ai.ports.evennia.client import EvenniaWebSocketClient, WebPacket
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.scenarios.p3b_goap import inspect
from ox_ai.scenarios.p3c_crew import IDS, URL, next_event, replayable_event

ROOT = Path(".ox-state")
STATE = ROOT / "p4b-supervisor.json"
CHECKPOINTS = ROOT / "p4b"
OLD_CHECKPOINTS = ROOT / "p4a"
CREW_ACCOUNTS = {"lin": "OxBotLin", "ari": "OxBotAri", "iona": "OxBotIona"}


def decode_event(packet: WebPacket, recipient: str) -> dict | None:
    """Ignore other OOB protocols, fail closed for unaddressed observations."""
    if packet.kind != "ox_event":
        return None
    if len(packet.args) != 1 or not isinstance(packet.args[0], dict):
        raise ValueError("Malformed server event")
    wire = packet.args[0]
    if wire.get("recipient_dbref") != recipient:
        raise PermissionError("Cross-recipient world event")
    if "data" in wire:
        raise ValueError("Nested world event is not supported on Evennia OOB")
    if not isinstance(wire.get("event_id"), str):
        raise ValueError("World event missing stable identity")
    result = {key: value for key, value in wire.items()
              if not key.startswith("datum_")}
    result["data"] = {
        key[len("datum_"):]: value
        for key, value in wire.items() if key.startswith("datum_")
    }
    return result


def newest_unseen_alarm(events: list[dict], handled: set[str]) -> tuple[dict | None, set[str]]:
    """Catch up by recipient-owned inbox, selecting newest event on first boot.

    Earlier alarms have already been independently resolved before this
    supervisor was enabled. Mark them as historical, not newly actionable.
    """
    alarms = [e for e in events if e.get("kind") == "coolant_alarm"]
    if not alarms:
        return None, set()
    unseen = [e for e in alarms if e["data"].get("alarm_id") not in handled]
    if not unseen:
        return None, set()
    selected = max(
        unseen, key=lambda e: int(e["event_id"].split("-")[-1])
    )
    return selected, {e["data"]["alarm_id"] for e in alarms}


def active_watch_from_roster(text: str) -> str:
    """Interpret only an authenticated, local posted-roster readout."""
    # Evennia's legacy browser wire format converts text into HTML.
    # Parse the character-visible readout, not markup or operator state.
    plain = unescape(text)
    plain = re.sub(r"(?i)<br\s*/?>|</(?:p|div)>", "\n", plain)
    plain = re.sub(r"<[^>]*>", "", plain).replace("\r", "")
    matches = re.findall(r"(?m)^\s*Active engineering watch:\s*(.+?)\s*$", plain)
    if len(matches) != 1:
        raise RuntimeError("Active engineering watch not observable")
    name = matches[0].strip()
    if name == "Chief Engineer Iona Vek":
        return "iona"
    if name == "Engineer Ari Sen":
        return "ari"
    raise RuntimeError("Unrecognised roster duty holder")


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=path.parent,
            prefix="." + path.name + ".", suffix=".tmp",
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


class CrewWatchSupervisor:
    """One persistent handler process, three private native Concordia actors."""

    def __init__(self, *, state_path: Path = STATE) -> None:
        self.state_path = Path(state_path)
        self.ids = json.loads(IDS.read_text(encoding="utf-8"))
        if set(self.ids) != set(CREW_ACCOUNTS):
            raise ValueError("World character identities must be complete")
        password = os.environ["OX_PROBE_PASSWORD"]
        self.clients = {
            role: EvenniaWebSocketClient(
                URL, name, password, self.ids[role], timeout=15
            ) for role, name in CREW_ACCOUNTS.items()
        }
        self.state = (
            json.loads(self.state_path.read_text(encoding="utf-8"))
            if self.state_path.is_file() else
            {"version": 1, "phase": "idle", "handled_alarms": [],
             "current": None, "completed": []}
        )
        if self.state.get("version") != 1:
            raise RuntimeError("Incompatible handler checkpoint format")
        self.brains = self._restore_brains()
        self.memories: dict[str, list[dict]] = {role: [] for role in self.clients}

    def _restore_brains(self) -> dict[str, LiveCrewBrain]:
        restored = {}
        for role in CREW_ACCOUNTS:
            stored = CHECKPOINTS / (role + ".json")
            previous = OLD_CHECKPOINTS / (role + ".json")
            path = stored if stored.is_file() else previous
            if path.is_file():
                restored[role] = LiveCrewBrain.from_checkpoint(
                    role, self.ids[role], make_model(), path
                )
            else:
                restored[role] = LiveCrewBrain(
                    role, self.ids[role], make_model()
                )
        return restored

    def checkpoint(self) -> None:
        """Persist character cognition before the phase record can advance."""
        for role, brain in self.brains.items():
            brain.save_checkpoint(CHECKPOINTS / (role + ".json"))
        atomic_json(self.state_path, self.state)

    async def open(self) -> None:
        for client in self.clients.values():
            await client.open()

    async def close(self) -> None:
        await asyncio.gather(
            *(client.close() for client in self.clients.values()),
            return_exceptions=True,
        )

    async def read_inbox(self, role: str) -> list[dict]:
        """Catch up only on the calling character's own durable event journal."""
        client = self.clients[role]
        await client.send_line("oxinbox 0")
        events = []
        async with asyncio.timeout(15):
            for _ in range(256):
                packet = await client.receive()
                if packet.kind == "ox_inbox_done":
                    return events
                event = decode_event(packet, client.character_dbref)
                if event is not None:
                    if event["event_id"] not in {e["event_id"] for e in events}:
                        events.append(event)
        raise RuntimeError("Game inbox did not finish")

    async def next_alarm(self, *, block: bool) -> dict | None:
        history = await self.read_inbox("lin")
        alarm, prior_ids = newest_unseen_alarm(
            history, set(self.state["handled_alarms"])
        )
        if alarm is not None:
            self.state["handled_alarms"] = sorted(
                set(self.state["handled_alarms"]) | prior_ids
            )
            return alarm
        if not block:
            return None
        # Indefinite idle suspension: no model calls, polling, timeout or
        # arbitrary packet budget. Check each addressed event's provenance.
        while True:
            packet = await self.clients["lin"].receive()
            event = decode_event(packet, self.ids["lin"])
            if event is None:
                continue
            if event["kind"] != "coolant_alarm":
                if event["event_id"] not in {
                    e["event_id"] for e in self.memories["lin"]
                }:
                    self.memories["lin"].append(event)
                    self.brains["lin"].observe_event(event)
                continue
            alarm_id = event["data"]["alarm_id"]
            if alarm_id not in self.state["handled_alarms"]:
                self.state["handled_alarms"].append(alarm_id)
                return event

    async def begin(self, *, block: bool = False, drop_ack: bool = False) -> bool:
        """React to one new world alarm; stop with an unknown isolation ACK."""
        if self.state["phase"] != "idle":
            raise RuntimeError("Cannot begin over an unresolved world operation")
        lin = self.clients["lin"]
        alarm = await self.next_alarm(block=block)
        if alarm is None:
            return False
        brain = self.brains["lin"]
        brain.observe_event(alarm)
        # World telemetry, not the age of an inbox event, determines whether
        # an incident is still active after an offline catch-up.
        await lin.send_line("inspect console")
        telemetry = await lin.expect_text("BRIDGE COOLING TELEMETRY", timeout=10)
        brain.observe_local("Bridge telemetry during incident catch-up", telemetry)
        if "LOW PRESSURE" not in telemetry:
            self.checkpoint()
            return False
        await lin.send_line("inspect roster")
        roster = await lin.expect_text("Active engineering watch:", timeout=10)
        active = active_watch_from_roster(roster)
        worker = self.clients[active]
        reviewer = "ari" if active == "iona" else "iona"
        notice = brain.choose(
            CommandOption("Relay new bridge alarm to the posted watch", "oxradio"),
            alternative="Defer until an additional bridge reading",
        )
        brain.require(notice, "oxradio")
        await lin.send_line("oxradio")
        event = await replayable_event(
            worker, "radio_alert", self.memories[active]
        )
        brain.record_unknown(notice)
        if event["data"]["alarm_id"] != alarm["data"]["alarm_id"]:
            raise RuntimeError("World relayed a mismatched alarm")
        engineer = self.brains[active]
        engineer.observe_event(event)
        local = await inspect(worker)
        engineer.observe_local("Physical engineering inspection", local)
        if "LOW PRESSURE" not in local:
            raise RuntimeError("No fault verified at the physical pump")
        choose = engineer.choose(
            CommandOption("Execute known safe GOAP isolation procedure", "goap"),
            alternative="Defer physical isolation and request assistance",
        )
        engineer.require(choose, "goap")
        engineer.selected_procedure(choose)
        planned = GoapPlanner(pump_action_model()).plan(
            frozenset({"at_engineering", "status_known", "pump_low_pressure"}),
            frozenset({"pump_isolated"}),
        )
        if [a.verb for a in planned.actions if a.verb == "isolate"] != ["isolate"]:
            raise RuntimeError("GOAP supplied no safe isolation plan")
        request_id = uuid.uuid4().hex
        self.state.update({
            "phase": "unknown_isolate",
            "current": {
                "alarm_id": alarm["data"]["alarm_id"],
                "active": active, "reviewer": reviewer,
                "request_id": request_id, "status": "unknown",
                "goap_expansions": planned.expanded_states,
            },
        })
        # Record pending physical request BEFORE sending: on arbitrary handler
        # crash, a missing outcome cannot trigger an unsafe retry.
        self.checkpoint()
        result = await DurableEvenniaPort(worker).submit(
            ActionRequest(request_id, self.ids[active], "isolate_pump", "pump")
        )
        if result.status != "succeeded" or not result.source_event_id:
            raise RuntimeError("World did not execute initial isolation")
        if not drop_ack:
            # Normal always-on behavior retains a successful world ACK; the
            # resumed work still validates the world ledger before acting.
            self.state["phase"] = "isolate_verified"
            self.state["current"]["receipt_event_id"] = result.source_event_id
            self.checkpoint()
        # The two-process acceptance mode intentionally loses this ACK in
        # handler memory to test reconciliation without any command replay.
        return True

    async def resume(self) -> dict:
        """Reconcile lost ACK and let active watch + separate reviewer finish."""
        if self.state["phase"] not in ("unknown_isolate", "isolate_verified"):
            raise RuntimeError("No isolation-phase operation to reconcile")
        pending = dict(self.state["current"])
        active, reviewer = pending["active"], pending["reviewer"]
        if active == reviewer or set((active, reviewer)) != {"ari", "iona"}:
            raise PermissionError("Authoritative watch/reviewer pairing invalid")
        worker = self.clients[active]
        port = DurableEvenniaPort(worker)
        receipt = await port.reconcile(pending["request_id"])
        if receipt.status != "succeeded" or not receipt.source_event_id:
            raise RuntimeError("Isolation outcome unknown; no duplicate command allowed")
        checked = await inspect(worker)
        engineer = self.brains[active]
        engineer.observe_local(
            "Reconciled isolation receipt", receipt.source_event_id
        )
        engineer.observe_local("Post-restart physical inspection", checked)
        if "ISOLATED" not in checked:
            raise RuntimeError("World condition disagrees with recovered receipt")
        planned = GoapPlanner(pump_action_model()).plan(
            frozenset({"at_engineering", "status_known", "pump_isolated"}),
            frozenset({"pump_repaired"}),
        )
        if [a.verb for a in planned.actions if a.verb == "repair"] != ["repair"]:
            raise RuntimeError("GOAP cannot restore this state")
        repair = await port.submit(ActionRequest(
            uuid.uuid4().hex, self.ids[active], "repair_pump", "pump"
        ))
        if repair.status != "succeeded" or not repair.source_event_id:
            raise RuntimeError("Real world refused repair")
        if "REPAIRED" not in await inspect(worker):
            raise RuntimeError("Repaired pump was not locally verified")
        engineer.observe_local("Repair receipt", repair.source_event_id)
        ask = engineer.choose(
            CommandOption("Request separate safety inspection", "oxrequest"),
            alternative="Keep repaired equipment isolated",
        )
        engineer.require(ask, "oxrequest")
        await worker.send_line("oxrequest")
        reviewer_client = self.clients[reviewer]
        requested = await replayable_event(
            reviewer_client, "release_request", self.memories[reviewer]
        )
        if requested["sender_dbref"] != self.ids[active]:
            raise PermissionError("Release request was not submitted by the watch")
        engineer.record_unknown(ask)
        inspecting = self.brains[reviewer]
        inspecting.observe_event(requested)
        choice = inspecting.choose(
            CommandOption("Perform independent local safety inspection", "inspect_pump"),
            alternative="Withhold approval without safety inspection",
        )
        inspecting.require(choice, "inspect_pump")
        reading = await inspect(reviewer_client)
        inspecting.observe_local("Independent inspection", reading)
        inspecting.selected_procedure(choice)
        if "REPAIRED" not in reading:
            raise RuntimeError("Independent reviewer cannot verify repairs")
        consent = inspecting.choose(
            CommandOption("Authorize commissioning after inspection", "oxapprove"),
            alternative="Decline to authorize commissioning",
        )
        inspecting.require(consent, "oxapprove")
        await reviewer_client.send_line("oxapprove")
        recorded = await next_event(
            reviewer_client, "release_recorded", self.memories[reviewer]
        )
        inspecting.confirm(consent, recorded)
        grant = await next_event(worker, "release_granted", self.memories[active])
        engineer.observe_event(grant)
        commission = await port.submit(ActionRequest(
            uuid.uuid4().hex, self.ids[active], "commission_pump", "pump"
        ))
        if commission.status != "succeeded" or not commission.source_event_id:
            raise RuntimeError("World withheld commissioning")
        reading = await inspect(worker)
        engineer.observe_local("Post-commission inspection", reading)
        if "NORMAL" not in reading:
            raise RuntimeError("Pressure not verified normal")
        closing = engineer.choose(
            CommandOption("Report physically verified resolution", "oxresolve"),
            alternative="Keep incident open",
        )
        engineer.require(closing, "oxresolve")
        await worker.send_line("oxresolve")
        bridge_notice = await next_event(
            self.clients["lin"], "incident_resolved", self.memories["lin"]
        )
        reviewer_notice = await next_event(
            reviewer_client, "incident_resolved", self.memories[reviewer]
        )
        engineer.record_unknown(closing)
        self.brains["lin"].observe_event(bridge_notice)
        inspecting.observe_event(reviewer_notice)
        verdict = {
            "alarm_id": pending["alarm_id"],
            "active_engineer": active,
            "independent_reviewer": reviewer,
            "reconciled_isolation": receipt.source_event_id,
            "repair_event": repair.source_event_id,
            "commission_event": commission.source_event_id,
            "goap_expansions": pending["goap_expansions"] + planned.expanded_states,
            "inference_calls_this_run": {
                role: brain.inference_calls for role, brain in self.brains.items()
            },
        }
        self.state["completed"].append(verdict)
        self.state["phase"] = "idle"
        self.state["current"] = None
        self.checkpoint()
        return verdict

    async def serve(self) -> None:
        """Run indefinitely, but remain dormant between legitimate world events."""
        if self.state["phase"] in ("unknown_isolate", "isolate_verified"):
            await self.resume()
        while True:
            if await self.begin(block=True, drop_ack=False):
                await self.resume()


async def main_async(mode: str) -> None:
    supervisor = CrewWatchSupervisor()
    try:
        await supervisor.open()
        if mode == "begin":
            if not await supervisor.begin(block=False, drop_ack=True):
                raise RuntimeError("No new addressed world alarm")
            print("OX_P4B_UNKNOWN_ISOLATION_DURABLY_CHECKPOINTED")
        elif mode == "resume":
            verdict = await supervisor.resume()
            atomic_json(ROOT / "p4b-verdict.json", verdict)
            print("OX_P4B_RESTORED_ENGINEER_RESOLVED_SECOND_INCIDENT")
        elif mode == "serve":
            await supervisor.serve()
        else:
            raise ValueError("Unknown supervisor mode")
    finally:
        await supervisor.close()


def main() -> None:
    import sys
    if len(sys.argv) != 2 or sys.argv[1] not in ("begin", "resume", "serve"):
        raise SystemExit(
            "Usage: python -m ox_ai.runtime.watch_service begin|resume|serve"
        )
    asyncio.run(main_async(sys.argv[1]))


if __name__ == "__main__":
    main()
