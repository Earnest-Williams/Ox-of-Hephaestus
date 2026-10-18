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
from ox_ai.runtime.work_steps import WorkStepLedger, SimulatedWorkInterruption

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
        unseen, key=lambda e: int(e.get("sequence", e["event_id"].split("-")[-1]))
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


async def replay_inbox_pages(
    client: EvenniaWebSocketClient, *, after: int = 0,
) -> tuple[list[dict], int]:
    """Replay every addressed page, failing closed on an incomplete response.

    Each page is retrieved from world truth. The caller may checkpoint the
    resulting observations before advancing its durable cursor; packet
    delivery and handler checkpoints are not an atomic network operation.
    """
    if isinstance(after, bool) or not isinstance(after, int) or after < 0:
        raise ValueError("Invalid inbox cursor")
    cursor = after
    events: list[dict] = []
    seen: set[str] = set()
    # A finite safety budget is an explicit error, never a silent truncation.
    for _page_number in range(10000):
        await client.send_line(f"oxinbox {cursor}")
        done = None
        received = 0
        async with asyncio.timeout(20):
            for _frame_number in range(512):
                packet = await client.receive()
                if packet.kind == "ox_inbox_done":
                    if len(packet.args) != 1 or not isinstance(packet.args[0], dict):
                        raise ValueError("Invalid world inbox completion frame")
                    done = packet.args[0]
                    break
                event = decode_event(packet, client.character_dbref)
                if event is not None:
                    received += 1
                    if event["event_id"] not in seen:
                        seen.add(event["event_id"])
                        events.append(event)
        if done is None:
            raise RuntimeError("World inbox page never completed")
        count = done.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 128:
            raise ValueError("Invalid world inbox page count")
        if done.get("version") is None:
            # Historic pre-P4f servers have no continuation token. Refuse an
            # apparently full page, whose missing next page cannot be proven.
            if count == 128:
                raise RuntimeError("Legacy inbox may have silently truncated history")
            return events, cursor
        if done.get("version") != 2:
            raise RuntimeError("Unsupported world inbox protocol version")
        following = done.get("next_cursor")
        more = done.get("has_more")
        if (isinstance(following, bool) or not isinstance(following, int)
                or following < cursor or not isinstance(more, bool)):
            raise ValueError("Invalid world inbox continuation")
        if more and (count == 0 or following <= cursor):
            raise RuntimeError("World inbox stalled with more pages pending")
        cursor = following
        if not more:
            return events, cursor
    raise RuntimeError("World inbox exceeded explicit page safety budget")


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
        """Losslessly replay legacy consumers' full authenticated history.

        Existing P4e routines still need historical hail/shift context, so
        this compatibility reader scans from zero. For every newly observed
        event it also advances a durable, per-character high-water mark only
        AFTER each character brain is checkpointed. A crash before the final
        state checkpoint triggers harmless replay and observation-ID dedup.
        Later agenda consumers can switch to cursor-only fetches.
        """
        events, cursor = await replay_inbox_pages(self.clients[role])
        cursors = self.state.setdefault("inbox_cursors", {})
        previous = int(cursors.get(role, 0))
        if cursor > previous:
            for event in events:
                serial = int(event.get(
                    "sequence", event["event_id"].split("-")[-1]
                ))
                if serial > previous:
                    self.brains[role].observe_event(event)
            cursors[role] = cursor
            # checkpoint() persists individual brain state before the
            # supervisor cursor. A partial crash is always replay-safe.
            self.checkpoint()
        return events

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

    async def resume(self, *, interrupt_at: str | None = None) -> dict:
        """Resume every pump-work stage using the same persisted work IDs.

        The initial isolation uses the original P4b receipt for backward
        compatibility. All subsequent physical and social actions use the
        global WorkReceipt interface. Every stage checkpoints its work ID
        before submission, and a restart reconciles the original ID before
        considering any new work.
        """
        if self.state["phase"] not in ("unknown_isolate", "isolate_verified"):
            raise RuntimeError("No isolation-phase incident to reconcile")
        pending = self.state["current"]
        if not isinstance(pending, dict):
            raise RuntimeError("Missing persisted physical incident")
        active, reviewer = pending["active"], pending["reviewer"]
        if active == reviewer or set((active, reviewer)) != {"ari", "iona"}:
            raise PermissionError("Authoritative watch/reviewer pairing invalid")
        worker = self.clients[active]
        reviewer_client = self.clients[reviewer]
        port = DurableEvenniaPort(worker)
        ledger = WorkStepLedger(
            pending, self.checkpoint, character_ids=self.ids,
        )
        # Reconcile the ORIGINAL P4b isolation ID, not a fresh action.
        isolation = await port.reconcile(pending["request_id"])
        if isolation.status != "succeeded" or not isolation.source_event_id:
            raise RuntimeError(
                "Isolation outcome unknown; no duplicate command allowed"
            )
        engineer = self.brains[active]
        inspecting = self.brains[reviewer]
        engineer.observe_local(
            "Reconciled isolation receipt", isolation.source_event_id,
        )

        async def prepare_repair() -> None:
            reading = await inspect(worker)
            engineer.observe_local("Pre-repair local inspection", reading)
            if "ISOLATED" not in reading:
                raise RuntimeError("World condition contradicts isolation receipt")
            planned = GoapPlanner(pump_action_model()).plan(
                frozenset({"at_engineering", "status_known", "pump_isolated"}),
                frozenset({"pump_repaired"}),
            )
            if [a.verb for a in planned.actions if a.verb == "repair"] != ["repair"]:
                raise RuntimeError("GOAP cannot restore this state")
            pending["repair_expansions"] = planned.expanded_states

        repair = await ledger.run(
            "repair", active, "repair_pump", "pump", port,
            prepare=prepare_repair, interrupt_at=interrupt_at,
        )
        if repair.status != "succeeded" or not repair.source_event_id:
            raise RuntimeError("No world-confirmed repair receipt")
        # A crash after commissioning must not reassert that P-01 is
        # REPAIRED when a later recorded stage has made it NORMAL.
        if "commission" not in ledger.steps:
            reading = await inspect(worker)
            engineer.observe_local("World verification of repaired P-01", reading)
            if "REPAIRED" not in reading:
                raise RuntimeError("World repair receipt disagrees with local state")

        async def prepare_request() -> None:
            ask = engineer.choose(
                CommandOption("Request separate safety inspection", "oxrequest"),
                alternative="Keep repaired equipment isolated",
            )
            engineer.require(ask, "oxrequest")
            engineer.selected_procedure(ask)

        request = await ledger.run(
            "request", active, "request", "ship", port,
            prepare=prepare_request, interrupt_at=interrupt_at,
        )
        if not request.source_event_id:
            raise RuntimeError("World did not emit a safety release request")
        # The reviewer must actually have received the request. The
        # private inbox remains authoritative across dropped OOB packets.
        reviewer_events = await self.read_inbox(reviewer)
        requested = next(
            (e for e in reviewer_events
             if e["event_id"] == request.source_event_id
             and e["kind"] == "release_request"), None,
        )
        if requested is None or requested["sender_dbref"] != self.ids[active]:
            raise PermissionError("No addressed, engineer-authored safety request")
        inspecting.observe_event(requested)

        async def prepare_approval() -> None:
            choice = inspecting.choose(
                CommandOption(
                    "Perform independent local safety inspection", "inspect_pump",
                ),
                alternative="Withhold approval without safety inspection",
            )
            inspecting.require(choice, "inspect_pump")
            reading = await inspect(reviewer_client)
            inspecting.observe_local("Independent safety inspection", reading)
            inspecting.selected_procedure(choice)
            if "REPAIRED" not in reading:
                raise RuntimeError("Reviewer cannot verify repaired pump")
            consent = inspecting.choose(
                CommandOption(
                    "Authorize commissioning after inspection", "oxapprove",
                ),
                alternative="Decline to authorize commissioning",
            )
            inspecting.require(consent, "oxapprove")
            inspecting.selected_procedure(consent)

        approval = await ledger.run(
            "approve", reviewer, "approve", "ship",
            DurableEvenniaPort(reviewer_client),
            prepare=prepare_approval, interrupt_at=interrupt_at,
        )
        if not approval.source_event_id:
            raise RuntimeError("World safety approval has no addressed source")
        worker_events = await self.read_inbox(active)
        grant = next(
            (e for e in worker_events
             if e["event_id"] == approval.source_event_id
             and e["kind"] == "release_granted"), None,
        )
        if grant is None or grant["sender_dbref"] != self.ids[reviewer]:
            raise PermissionError("Separate reviewer has not granted commissioning")
        engineer.observe_event(grant)

        async def prepare_commission() -> None:
            reading = await inspect(worker)
            engineer.observe_local("Pre-commission pump inspection", reading)
            if "REPAIRED" not in reading:
                raise RuntimeError("Pump cannot be commissioned from this state")

        commission = await ledger.run(
            "commission", active, "commission_pump", "pump", port,
            prepare=prepare_commission, interrupt_at=interrupt_at,
        )
        if commission.status != "succeeded" or not commission.source_event_id:
            raise RuntimeError("World withheld pump commissioning")

        async def prepare_resolution() -> None:
            reading = await inspect(worker)
            engineer.observe_local("Post-commission inspection", reading)
            if "NORMAL" not in reading:
                raise RuntimeError("Pressure not independently verified normal")
            closing = engineer.choose(
                CommandOption(
                    "Report physically verified resolution", "oxresolve",
                ),
                alternative="Keep incident open",
            )
            engineer.require(closing, "oxresolve")
            engineer.selected_procedure(closing)

        resolution = await ledger.run(
            "resolve", active, "resolve", "ship", port,
            prepare=prepare_resolution, interrupt_at=interrupt_at,
        )
        if not resolution.source_event_id:
            raise RuntimeError("Resolved incident lacks a world event")
        bridge_events = await self.read_inbox("lin")
        bridge_notice = next(
            (e for e in bridge_events
             if e["event_id"] == resolution.source_event_id
             and e["kind"] == "incident_resolved"), None,
        )
        if bridge_notice is None:
            raise PermissionError("Bridge never received world incident resolution")
        reviewer_events = await self.read_inbox(reviewer)
        reviewer_notice = next(
            (e for e in reviewer_events
             if e["kind"] == "incident_resolved"
             and e["data"].get("alarm_id") == pending["alarm_id"]), None,
        )
        if reviewer_notice is None:
            raise PermissionError("Reviewer never received incident resolution")
        self.brains["lin"].observe_event(bridge_notice)
        inspecting.observe_event(reviewer_notice)

        verdict = {
            "alarm_id": pending["alarm_id"],
            "active_engineer": active,
            "independent_reviewer": reviewer,
            "reconciled_isolation": isolation.source_event_id,
            "repair_event": repair.source_event_id,
            "commission_event": commission.source_event_id,
            "resolution_event": resolution.source_event_id,
            "goap_expansions": (
                pending["goap_expansions"]
                + pending.get("repair_expansions", 0)
            ),
            "inference_calls_this_run": {
                role: brain.inference_calls for role, brain in self.brains.items()
            },
        }
        self.state["completed"].append(verdict)
        self.state["phase"] = "idle"
        self.state["current"] = None
        self.checkpoint()
        return verdict

    async def handover_if_due(self) -> bool:
        """Independently react to world-issued duty events, even with no fault."""
        if self.state["phase"] != "idle":
            return False
        # Only a real addressed due event can authorize this procedure.
        old = self.clients["ari"]
        incoming = self.clients["iona"]
        history = await self.read_inbox("ari")
        due = [e for e in history if e["kind"] == "handover_due"]
        if not due:
            return False
        bridge = self.clients["lin"]
        await bridge.send_line("inspect roster")
        current = active_watch_from_roster(
            await bridge.expect_text("Active engineering watch:", timeout=10)
        )
        if current != "ari":
            return False
        # The receiving crewmember must also have been sent the duty event.
        if not any(e["kind"] == "handover_due" for e in
                   await self.read_inbox("iona")):
            return False
        ari = self.brains["ari"]
        iona = self.brains["iona"]
        ari.observe_event(due[-1])
        offer = ari.choose(
            CommandOption("Offer posted watch at due time", "oxhandover"),
            alternative="Defer handover for an unresolved safety concern",
        )
        if offer.verb != "oxhandover":
            ari.record_unknown(offer)
            self.checkpoint()
            return False
        await old.send_line("oxhandover")
        offered = await replayable_event(incoming, "handover_offer",
                                         self.memories["iona"])
        ari.record_unknown(offer)
        iona.observe_event(offered)
        take = iona.choose(
            CommandOption("Accept scheduled engineering watch", "oxaccept"),
            alternative="Decline to assume the scheduled watch",
        )
        if take.verb != "oxaccept":
            iona.record_unknown(take)
            self.checkpoint()
            return False
        await incoming.send_line("oxaccept")
        transferred = await replayable_event(
            incoming, "watch_transferred", self.memories["iona"]
        )
        iona.confirm(take, transferred)
        self.checkpoint()
        return True

    async def service_departments(self) -> bool:
        """Optional specialist-work hook; historical three-crew runtime is idle."""
        return False

    async def respond_to_hails(self) -> int:
        """Consume recipient-private hails, with world-side duplicate defence."""
        count = 0
        for role in self.clients:
            events = await self.read_inbox(role)
            answered = {e["data"]["hail_id"] for e in events
                        if e["kind"] == "hail_answered"}
            for event in events:
                if event["kind"] != "crew_hail":
                    continue
                hail_id = event["data"]["hail_id"]
                if hail_id in answered:
                    continue
                brain = self.brains[role]
                brain.observe_event(event)
                proposal = brain.choose(
                    CommandOption("Give an authoritative station status", "status"),
                    alternative="Acknowledge request without unverified claims",
                )
                mode = proposal.verb if proposal.verb == "status" else "ack"
                await self.clients[role].send_line(
                    f"oxanswer {hail_id} {mode}"
                )
                # Re-read the world-owned durable event before recording success.
                result = await self.read_inbox(role)
                confirmed = [e for e in result if e["kind"] == "hail_answered"
                             and e["data"]["hail_id"] == hail_id]
                if not confirmed:
                    brain.record_unknown(proposal)
                    raise RuntimeError("Hail answer unconfirmed by world")
                brain.confirm(proposal, confirmed[-1])
                answered.add(hail_id)
                count += 1
                self.checkpoint()
        return count

    async def serve(self) -> None:
        """Independent multi-source event dispatch; no idle model polling."""
        if self.state["phase"] in ("unknown_isolate", "isolate_verified"):
            await self.resume()
        while True:
            # First reconcile world-owned pending duties on reconnect.
            if await self.begin(block=False, drop_ack=False):
                await self.resume()
                continue
            if await self.service_departments():
                continue
            # Cooling faults first; then answer addressed player requests
            # before optional routine handovers so a due roster cannot
            # postpone legitimate human interaction indefinitely.
            if await self.respond_to_hails():
                continue
            if await self.handover_if_due():
                continue
            # Wait for ANY addressed character event, not only bridge faults.
            # No concurrent consumer reads a socket during another protocol.
            pending = {
                asyncio.create_task(client.receive()): role
                for role, client in self.clients.items()
            }
            try:
                done, _ = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    packet = task.result()
                    event = decode_event(packet, self.ids[pending[task]])
                    if event is not None:
                        self.memories[pending[task]].append(event)
            finally:
                for task in pending:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)


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
        elif mode.startswith("resume-interrupt-"):
            parts = mode.removeprefix("resume-interrupt-").split("-")
            if (len(parts) != 2
                    or parts[0] not in (
                        "repair", "request", "approve", "commission", "resolve",
                    )
                    or parts[1] not in ("prepared", "committed", "ack")):
                raise ValueError("Unsupported work interruption point")
            try:
                await supervisor.resume(interrupt_at=":".join(parts))
            except SimulatedWorkInterruption:
                print("OX_P4H_WORLD_STEP_INTERRUPTED " + ":".join(parts))
                return
            raise RuntimeError("Requested stage interruption never occurred")
        else:
            raise ValueError("Unknown supervisor mode")
    finally:
        await supervisor.close()


def main() -> None:
    import sys
    if (len(sys.argv) != 2
            or not (sys.argv[1] in ("begin", "resume", "serve")
                    or sys.argv[1].startswith("resume-interrupt-"))):
        raise SystemExit(
            "Usage: python -m ox_ai.runtime.watch_service "
            "begin|resume|serve|resume-interrupt-<stage>-<point>"
        )
    asyncio.run(main_async(sys.argv[1]))


if __name__ == "__main__":
    main()
