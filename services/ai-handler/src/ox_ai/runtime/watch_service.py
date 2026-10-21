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
from collections import deque
import json
from html import unescape
import os
from pathlib import Path
import re
import tempfile
import uuid

from ox_ai.agents.crew import CommandOption
from ox_ai.runtime.cognition_scheduler import DecisionScheduler
from ox_ai.runtime.evidence_index import ActorEvidenceIndex, EvidenceView
from ox_ai.runtime.supervisor_lease import SupervisorLease
from ox_ai.agents.live_concordia import (
    LiveCrewBrain, build_live_brains, make_model,
)
from ox_ai.agents.goap_crew import pump_action_model
from ox_ai.planning.goap import GoapPlanner
from ox_ai.ports.base import ActionRequest
from ox_ai.ports.evennia.client import EvenniaWebSocketClient, WebPacket
from ox_ai.ports.evennia.clock import WorldClockPort
from ox_ai.ports.evennia.evidence import WorldEventPort
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
    page_sink=None,
) -> tuple[list[dict], int]:
    """Authenticate every inbox page before optionally streaming it to disk.

    Without page_sink, preserve the existing list-returning test/client API.
    With it, only the current <=128-event page is held in Python memory.
    The caller must enclose the sink in a single archive transaction: a
    disconnection mid-replay cannot publish a partial indexed history.
    """
    if type(after) is not int or after < 0:
        raise ValueError("Invalid inbox cursor")
    cursor = after
    collected: list[dict] = []
    for _page_number in range(10000):
        await client.send_line(f"oxinbox {cursor}")
        done = None
        page: list[dict] = []
        async with asyncio.timeout(20):
            for _frame_number in range(512):
                packet = await client.receive_matching(
                    lambda p: p.kind == "ox_inbox_done" or (
                        p.kind == "ox_event"
                        and p.options.get("ox_inbox_page") is True
                    ),
                    frame_budget=512,
                )
                if packet.kind == "ox_inbox_done":
                    if len(packet.args) != 1 or not isinstance(packet.args[0], dict):
                        raise ValueError("Invalid world inbox completion frame")
                    done = packet.args[0]
                    break
                event = decode_event(packet, client.character_dbref)
                if event is not None:
                    page.append(event)
        if done is None:
            raise RuntimeError("World inbox page never completed")
        count = done.get("count")
        if type(count) is not int or not 0 <= count <= 128:
            raise ValueError("Invalid world inbox page count")
        if len(page) != count:
            raise RuntimeError("World inbox completion count disagrees with frames")
        if done.get("version") is None:
            # Pre-P4f has no continuation cursor. Only the non-streaming
            # compatibility call can use it, and refuses full pages.
            if page_sink is not None:
                raise RuntimeError("Indexed inbox requires versioned world history")
            if count == 128:
                raise RuntimeError("Legacy inbox may have silently truncated history")
            collected.extend(page)
            return collected, cursor
        if done.get("version") != 2:
            raise RuntimeError("Unsupported world inbox protocol version")
        following = done.get("next_cursor")
        more = done.get("has_more")
        if (type(following) is not int or following < cursor
                or type(more) is not bool):
            raise ValueError("Invalid world inbox continuation")
        if (page and (
                any(type(e.get("sequence")) is not int for e in page)
                or page[0]["sequence"] <= cursor
                or any(a["sequence"] >= b["sequence"]
                       for a, b in zip(page, page[1:]))
                or page[-1]["sequence"] != following)):
            raise RuntimeError("World inbox page sequence/cursor mismatch")
        if not page and following != cursor:
            raise RuntimeError("Empty world inbox page advanced its cursor")
        if more and (count == 0 or following <= cursor):
            raise RuntimeError("World inbox stalled with more pages pending")
        if page_sink is None:
            collected.extend(page)
        else:
            page_sink(page)
        cursor = following
        if not more:
            return collected, cursor
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
        # Live OOB wake-up frames are a transient hint, NOT the world journal.
        # Cap this unrelated legacy staging buffer; all durable evidence
        # remains available in the actor-scoped index and native checkpoints.
        self.memories: dict[str, deque[dict]] = {
            role: deque(maxlen=256) for role in self.clients
        }
        # This directory is deliberately disposable. Every new process
        # re-verifies old events through the actor's world-authenticated inbox.
        # Older event IDs are indexed on disk, never retained in a Python
        # voyage-length list. It is not an alternative world authority.
        self._evidence_temporary = tempfile.TemporaryDirectory(prefix="ox-evidence-")
        self._evidence_indexes: dict[str, ActorEvidenceIndex] = {}
        self._inbox_hydrated: set[str] = set()
        self._inbox_role_locks: dict[str, asyncio.Lock] = {}
        self.cognition = DecisionScheduler(
            max_parallel=int(os.getenv("OX_MAX_PARALLEL_COGNITION", "2")),
            per_actor_budget=int(os.getenv("OX_COGNITION_ACTOR_BUDGET", "500")),
            total_budget=int(os.getenv("OX_COGNITION_TOTAL_BUDGET", "2500")),
            timeout_seconds=float(os.getenv("OX_COGNITION_TIMEOUT_SECONDS", "25")),
        )
        # All supervisor variants lock the same stable file inode before
        # opening ordinary world sessions or performing any work.
        self.lease = SupervisorLease(
            ROOT / "supervisor.lock", owner=type(self).__name__,
        )

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
        self.lease.acquire()
        try:
            for client in self.clients.values():
                await client.open()
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        try:
            await asyncio.gather(
                *(client.close() for client in self.clients.values()),
                return_exceptions=True,
            )
        finally:
            for index in self._evidence_indexes.values():
                index.close()
            self._evidence_indexes.clear()
            self._evidence_temporary.cleanup()
            self.lease.release()

    async def choose(
        self, role: str, primary: CommandOption, *, alternative: str,
    ):
        """Cognition happens on an independent snapshot; no blocking LLM I/O."""
        self.lease.assert_held()
        if role not in self.brains or role not in self.clients:
            raise PermissionError("Cannot schedule thought for an unknown actor")
        # The world, not this supervisor, supplies elapsed simulation time.
        # A read-only, nonce-checked observation precedes each model choice,
        # including choices taken after a long interval without new memories.
        clock = await WorldClockPort(self.clients[role]).observe()
        self.brains[role].advance_game_time(clock.game_seconds)
        return await self.cognition.choose(
            role, self.brains[role], primary, alternative=alternative,
        )

    async def ensure_station(self, role: str, destination: str):
        """Reach assigned compartment by local capability + stock exit steps.

        The private map is stored with the supervisor checkpoint. Physical
        locations are never trusted from the checkpoint: each attempt begins
        with a fresh authenticated world observation and verifies arrivals.
        """
        from ox_ai.planning.navigation import CrewNavigator, NavigationKnowledge
        from ox_ai.ports.evennia.capabilities import CapabilityPort

        self.lease.assert_held()
        if role not in self.ids or role not in self.clients or role not in self.brains:
            raise PermissionError("Navigator role not authenticated in this ship")
        records = self.state.setdefault("navigation_knowledge", {})
        if not isinstance(records, dict) or any(k not in self.ids for k in records):
            raise PermissionError("Invalid or foreign private route checkpoint")
        private_map = NavigationKnowledge(self.ids[role], records.get(role))
        navigator = CrewNavigator(
            CapabilityPort(self.clients[role]),
            brain=self.brains[role], knowledge=private_map,
        )
        result = await navigator.navigate(destination, max_movements=20)
        records[role] = navigator.knowledge.to_record()
        self.checkpoint()
        if result.status != "arrived":
            raise RuntimeError(
                f"{role} cannot reach assigned station; no physical work requested"
            )
        return result

    async def prove_world_event(
        self, role: str, event_id: str, *, kind: str,
        sender_dbref: str | None = None,
    ) -> dict:
        """Verify one old actor-addressed event directly against Evennia.

        This explicit proof lookup does not replay the voyage, advance a
        cursor, infer an obligation's outcome, or automatically alter a
        character's memory. It is serialized against inbox pagination for
        the same authenticated socket, preserving packet provenance.
        """
        self.lease.assert_held()
        if (role not in self.clients or role not in self.brains
                or self.ids.get(role) != self.clients[role].character_dbref):
            raise PermissionError("No authenticated actor for event proof")
        async with self._inbox_role_locks.setdefault(role, asyncio.Lock()):
            proof = await WorldEventPort(self.clients[role]).lookup(event_id)
        return proof.require(kind=kind, sender_dbref=sender_dbref)

    def inbox_events_since(self, role: str, sequence: int) -> EvidenceView:
        """Return a bounded-memory, actor-scoped delta from historical proof."""
        if (role not in self.clients or type(sequence) is not int
                or sequence < 0 or role not in self._inbox_hydrated):
            raise ValueError("Actor inbox must be hydrated before delta lookup")
        return self._evidence_indexes[role].view(after=sequence)

    async def read_inbox(self, role: str) -> EvidenceView:
        """Return a stable, indexed, read-only snapshot of this actor's history.

        Each process rehydrates world-addressed history from cursor zero,
        streaming each verified page into a disposable private SQLite index.
        Later requests begin at the index's high-water mark. Legacy lookups
        traverse the index lazily rather than keeping complete Python lists.

        The native brain must save before the supervisor's high-water cursor.
        Five-crew private proof and agenda cursors are independent and may
        backfill from the indexed history after a checkpoint interruption.
        """
        if role not in self.clients or role not in self.brains:
            raise PermissionError("Unknown authenticated crew inbox")
        if self.ids.get(role) != self.clients[role].character_dbref:
            raise PermissionError("Actor inbox is not the authenticated character")
        async with self._inbox_role_locks.setdefault(role, asyncio.Lock()):
            cursors = self.state.setdefault("inbox_cursors", {})
            if not isinstance(cursors, dict):
                raise PermissionError("Invalid actor inbox cursor checkpoint")
            previous = cursors.get(role, 0)
            if type(previous) is not int or previous < 0:
                raise PermissionError("Invalid actor inbox high-water mark")
            index = self._evidence_indexes.get(role)
            if index is None:
                index = ActorEvidenceIndex(
                    Path(self._evidence_temporary.name) / (role + ".sqlite3"),
                    self.ids[role],
                )
                self._evidence_indexes[role] = index
            before = index.cursor
            # The world, not this process, determines the continuation token.
            # Commit the full multi-page index batch or none of it.
            with index.transaction():
                _unused, cursor = await replay_inbox_pages(
                    self.clients[role], after=before,
                    page_sink=index.append_page,
                )
                if cursor != index.cursor or cursor < previous:
                    raise RuntimeError("World inbox behind local actor checkpoint")
            if cursor > previous:
                for event in index.view(after=previous, through=cursor):
                    self.brains[role].observe_event(event)
                cursors[role] = cursor
                try:
                    # Character checkpoints precede any durable cursor
                    # advancement. An interrupted save is ID-replay-safe.
                    self.checkpoint()
                except BaseException:
                    if previous:
                        cursors[role] = previous
                    else:
                        cursors.pop(role, None)
                    raise
            self._inbox_hydrated.add(role)
            return index.view(through=cursor)

    async def next_alarm(self, *, block: bool) -> dict | None:
        history = await self.read_inbox("lin")
        alarm, prior_ids = newest_unseen_alarm(
            history.select(kind="coolant_alarm"), set(self.state["handled_alarms"])
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

    async def begin(
        self, *, block: bool = False, drop_ack: bool = False,
        interrupt_at: str | None = None,
    ) -> bool:
        """Start or recover a bridge alarm before the first physical action.

        A prior implementation could lose the bridge relay ACK and forget
        which alarm had been dispatched. Persist the incident identity and
        the global radio request ID before network submission; a restarted
        handler reconciles that ID before trying isolation.
        """
        phase = self.state["phase"]
        lin = self.clients["lin"]
        brain = self.brains["lin"]
        if phase == "idle":
            alarm = await self.next_alarm(block=block)
            if alarm is None:
                return False
            brain.observe_event(alarm)
            await lin.send_line("inspect console")
            telemetry = await lin.expect_text(
                "BRIDGE COOLING TELEMETRY", timeout=10,
            )
            brain.observe_local("Bridge incident catch-up", telemetry)
            if "LOW PRESSURE" not in telemetry:
                self.checkpoint()
                return False
            await lin.send_line("inspect roster")
            active = active_watch_from_roster(
                await lin.expect_text("Active engineering watch:", timeout=10)
            )
            reviewer = "ari" if active == "iona" else "iona"
            self.state.update({
                "phase": "begin_alarm",
                "current": {
                    "alarm_id": alarm["data"]["alarm_id"],
                    "active": active,
                    "reviewer": reviewer,
                    "goap_expansions": 0,
                },
            })
            self.checkpoint()
        elif phase == "begin_alarm":
            # Read *only* Lin's legitimate bridge observations. An arbitrary
            # saved alarm ID cannot authorize an unobserved new incident.
            pending = self.state["current"]
            if not isinstance(pending, dict):
                raise RuntimeError("Incomplete bridge work checkpoint")
            history = await self.read_inbox("lin")
            alarm = history.latest(
                "coolant_alarm", data={"alarm_id": pending["alarm_id"]},
            )
            if alarm is None:
                raise PermissionError("Restored incident not observed by bridge")
            brain.observe_event(alarm)
        else:
            raise RuntimeError("Cannot begin over an unresolved world operation")

        pending = self.state["current"]
        active, reviewer = pending["active"], pending["reviewer"]
        if (active not in ("ari", "iona") or reviewer not in ("ari", "iona")
                or active == reviewer):
            raise PermissionError("Recovered watch/reviewer pairing invalid")
        worker = self.clients[active]

        async def propose_radio() -> None:
            proposal = await self.choose("lin", 
                CommandOption(
                    "Relay verified bridge alarm to the posted watch", "oxradio",
                ),
                alternative="Defer until an additional bridge reading",
            )
            brain.require(proposal, "oxradio")
            brain.selected_procedure(proposal)

        relay = await WorkStepLedger(
            pending, self.checkpoint, character_ids=self.ids,
        ).run(
            "radio", "lin", "radio", "ship", DurableEvenniaPort(lin),
            prepare=propose_radio, interrupt_at=interrupt_at,
        )
        if relay.status != "succeeded" or not relay.source_event_id:
            raise RuntimeError("Bridge relay lacks authoritative receipt")
        addressed = await self.read_inbox(active)
        event = addressed.get(relay.source_event_id, kind="radio_alert")
        if (event is None or event["sender_dbref"] != self.ids["lin"]
                or event["data"].get("alarm_id") != pending["alarm_id"]):
            raise PermissionError("Radio alert not addressed to active engineer")
        engineer = self.brains[active]
        engineer.observe_event(event)

        await self.ensure_station(active, "Engineering")
        local = await inspect(worker)
        engineer.observe_local("Physical engineering inspection", local)
        if "LOW PRESSURE" not in local:
            raise RuntimeError("No current fault verified at physical pump")
        choose = await self.choose(active, 
            CommandOption("Execute verified GOAP isolation", "goap"),
            alternative="Defer physical isolation and request assistance",
        )
        engineer.require(choose, "goap")
        engineer.selected_procedure(choose)
        planned = GoapPlanner(pump_action_model()).plan(
            frozenset({"at_engineering", "status_known", "pump_low_pressure"}),
            frozenset({"pump_isolated"}),
        )
        if [action.verb for action in planned.actions
                if action.verb == "isolate"] != ["isolate"]:
            raise RuntimeError("GOAP supplied no safe isolation plan")
        request_id = uuid.uuid4().hex
        pending.update({
            "request_id": request_id,
            "status": "unknown",
            "goap_expansions": planned.expanded_states,
        })
        self.state["phase"] = "unknown_isolate"
        self.checkpoint()
        result = await DurableEvenniaPort(worker).submit(
            ActionRequest(request_id, self.ids[active], "isolate_pump", "pump")
        )
        if result.status != "succeeded" or not result.source_event_id:
            raise RuntimeError("World did not execute initial isolation")
        if not drop_ack:
            self.state["phase"] = "isolate_verified"
            pending["receipt_event_id"] = result.source_event_id
            self.checkpoint()
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
            await self.ensure_station(active, "Engineering")
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
            ask = await self.choose(active, 
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
        requested = reviewer_events.get(
            request.source_event_id, kind="release_request",
        )
        if requested is None or requested["sender_dbref"] != self.ids[active]:
            raise PermissionError("No addressed, engineer-authored safety request")
        inspecting.observe_event(requested)

        async def prepare_approval() -> None:
            await self.ensure_station(reviewer, "Engineering")
            choice = await self.choose(reviewer, 
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
            consent = await self.choose(reviewer, 
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
        grant = worker_events.get(
            approval.source_event_id, kind="release_granted",
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
            closing = await self.choose(active, 
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
        bridge_notice = bridge_events.get(
            resolution.source_event_id, kind="incident_resolved",
        )
        if bridge_notice is None:
            raise PermissionError("Bridge never received world incident resolution")
        reviewer_events = await self.read_inbox(reviewer)
        reviewer_notice = reviewer_events.latest(
            "incident_resolved", data={"alarm_id": pending["alarm_id"]},
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

    async def handover_if_due(
        self, *, interrupt_at: str | None = None,
    ) -> bool:
        """Reconcile an authorized watch offer/accept across handler restarts."""
        if self.state["phase"] != "idle":
            return False
        old = self.clients["ari"]
        incoming = self.clients["iona"]
        work = self.state.get("handover_work")
        if work is None:
            history = await self.read_inbox("ari")
            due = history.latest("handover_due")
            if due is None:
                return False
            bridge = self.clients["lin"]
            await bridge.send_line("inspect roster")
            current = active_watch_from_roster(
                await bridge.expect_text("Active engineering watch:", timeout=10)
            )
            if current != "ari":
                return False
            incoming_events = await self.read_inbox("iona")
            if incoming_events.latest("handover_due") is None:
                return False
            work = {
                "due_event_id": due["event_id"],
                "outgoing": self.ids["ari"], "incoming": self.ids["iona"],
            }
            self.state["handover_work"] = work
            self.checkpoint()
        else:
            if (not isinstance(work, dict)
                    or work.get("outgoing") != self.ids["ari"]
                    or work.get("incoming") != self.ids["iona"]):
                raise PermissionError("Persisted handover no longer matches identities")
            source = (await self.read_inbox("ari")).get(
                work.get("due_event_id"), kind="handover_due",
            )
            if source is None:
                raise PermissionError("Persisted handover lacks world-issued duty")
        ledger = WorkStepLedger(
            work, self.checkpoint, character_ids=self.ids,
        )
        ari = self.brains["ari"]
        iona = self.brains["iona"]

        if "offer" not in ledger.steps:
            proposal = await self.choose("ari", 
                CommandOption("Offer posted watch at due time", "oxhandover"),
                alternative="Defer handover for an unresolved safety concern",
            )
            if proposal.verb != "oxhandover":
                ari.record_unknown(proposal)
                # No world action has been requested. Reconsider on a future
                # event, preserving the due obligation on the world roster.
                self.state["handover_work"] = None
                self.checkpoint()
                return False
            ari.selected_procedure(proposal)
        offer = await ledger.run(
            "offer", "ari", "offer", "ship", DurableEvenniaPort(old),
            interrupt_at=interrupt_at,
        )
        offered = (await self.read_inbox("iona")).get(
            offer.source_event_id, kind="handover_offer",
        )
        if offered is None or offered["sender_dbref"] != self.ids["ari"]:
            raise PermissionError("Incoming watch did not receive an authorized offer")
        iona.observe_event(offered)

        if "accept" not in ledger.steps:
            proposal = await self.choose("iona", 
                CommandOption("Accept scheduled engineering watch", "oxaccept"),
                alternative="Decline to assume the scheduled watch",
            )
            if proposal.verb != "oxaccept":
                iona.record_unknown(proposal)
                self.checkpoint()
                return False
            iona.selected_procedure(proposal)
        accepted = await ledger.run(
            "accept", "iona", "accept", "ship",
            DurableEvenniaPort(incoming), interrupt_at=interrupt_at,
        )
        outgoing_events = await self.read_inbox("ari")
        transferred = outgoing_events.get(
            accepted.source_event_id, kind="watch_transferred",
        )
        if (transferred is None or transferred["sender_dbref"] != self.ids["iona"]
                or transferred["data"].get("new_watch") != self.ids["iona"]):
            raise PermissionError("Outgoing watch did not observe world transfer")
        own_events = await self.read_inbox("iona")
        if own_events.latest(
            "watch_transferred", data={"new_watch": self.ids["iona"]},
        ) is None:
            raise PermissionError("Incoming watch lacks world transfer confirmation")
        await self.clients["lin"].send_line("inspect roster")
        roster = await self.clients["lin"].expect_text(
            "Active engineering watch:", timeout=10,
        )
        if active_watch_from_roster(roster) != "iona":
            raise RuntimeError("World roster did not transfer authorized watch")
        self.state["handover_work"] = None
        self.checkpoint()
        return True

    async def service_departments(self) -> bool:
        """Optional specialist-work hook; historical three-crew runtime is idle."""
        return False

    async def service_independent_rounds(self) -> bool:
        """Optional lowest-priority initiative, after urgent work/hails/relief."""
        return False

    async def respond_to_hails(
        self, *, interrupt_at: str | None = None,
    ) -> int:
        """Process independent recipients concurrently, never sharing a mind.

        Each ordinary character has its own authenticated socket, so a slow
        model response for one crew member cannot delay another crew member's
        hail response. Every physical/social effect still uses its own
        source-addressed receipt and persisted WorkStepLedger.
        """
        completed = await asyncio.gather(
            *(
                self._answer_role_hails(role, interrupt_at=interrupt_at)
                for role in self.clients
            ),
            return_exceptions=True,
        )
        # Do not abandon other actors' in-flight durable work after one
        # provider failure; wait until each has either settled or failed.
        for result in completed:
            if isinstance(result, BaseException):
                raise result
        return sum(completed)

    async def _answer_role_hails(
        self, role: str, *, interrupt_at: str | None = None,
    ) -> int:
        self.lease.assert_held()
        if role not in self.clients or role not in self.brains:
            raise PermissionError("Cannot handle another character's hails")
        count = 0
        pending = self.state.setdefault("hail_work", {})
        events = await self.read_inbox(role)
        # Resolved hails normally disappear from the pending index. An
        # interrupted work ledger must still reconcile its original source.
        # Never silently discard a previously persisted operation.
        candidates = {e["data"]["hail_id"]: e for e in events.pending("hail")}
        for hail_id, work in pending.items():
            if work.get("role") == role and hail_id not in candidates:
                source = events.get(work.get("hail_event_id"), kind="crew_hail")
                if source is None or source["data"].get("hail_id") != hail_id:
                    raise PermissionError("Persisted hail has no addressed source")
                candidates[hail_id] = source
        for hail_id, event in sorted(
            candidates.items(), key=lambda pair: pair[1]["sequence"],
        ):
            work = pending.get(hail_id)
            brain = self.brains[role]
            brain.observe_event(event)
            if work is None:
                proposal = await self.choose(role, 
                    CommandOption(
                        "Give authoritative station status", "status",
                    ),
                    alternative="Acknowledge without unverified claims",
                )
                mode = proposal.verb if proposal.verb == "status" else "ack"
                work = {
                    "role": role,
                    "mode": mode,
                    "hail_event_id": event["event_id"],
                }
                pending[hail_id] = work
                self.checkpoint()
            if (work.get("role") != role
                    or work.get("hail_event_id") != event["event_id"]
                    or work.get("mode") not in ("status", "ack")):
                raise PermissionError("Recovered hail belongs to another recipient")
            result = await WorkStepLedger(
                work, self.checkpoint, character_ids=self.ids,
            ).run(
                "answer", role, "answer", "ship",
                DurableEvenniaPort(self.clients[role]),
                arguments={"hail_id": hail_id, "mode": work["mode"]},
                interrupt_at=interrupt_at,
            )
            if result.status != "succeeded":
                raise RuntimeError("World did not accept addressed hail")
            verified = (await self.read_inbox(role)).latest(
                "hail_answered", data={"hail_id": hail_id, "mode": work["mode"]},
            )
            if verified is None:
                raise RuntimeError("Hail answer unconfirmed by world journal")
            brain.observe_event(verified)
            del pending[hail_id]
            count += 1
            self.checkpoint()
        return count

    async def serve(self) -> None:
        """Independent multi-source event dispatch; no idle model polling."""
        if self.state["phase"] == "begin_alarm":
            await self.begin()
            await self.resume()
        elif self.state["phase"] in ("unknown_isolate", "isolate_verified"):
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
            if await self.service_independent_rounds():
                continue
            # Wait for ANY addressed character event, not only bridge faults.
            # No concurrent consumer reads a socket during another protocol.
            pending = {
                asyncio.create_task(client.receive()): role
                for role, client in self.clients.items()
            }
            try:
                await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
            finally:
                for task in pending:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
            # A second role can complete while the first completion is being
            # handled. Process every completed receive, not only the initial
            # FIRST_COMPLETED snapshot; canceled reads have no packet.
            for task, role in pending.items():
                if task.cancelled():
                    continue
                packet = task.result()
                event = decode_event(packet, self.ids[role])
                if event is not None:
                    self.memories[role].append(event)


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
        elif mode.startswith("begin-radio-interrupt-"):
            point = mode.removeprefix("begin-radio-interrupt-")
            if point not in ("prepared", "committed", "ack"):
                raise ValueError("Unsupported radio interruption point")
            try:
                await supervisor.begin(interrupt_at="radio:" + point)
            except SimulatedWorkInterruption:
                print("OX_P4I_RADIO_INTERRUPTED " + point)
                return
            raise RuntimeError("Radio interruption never occurred")
        elif mode == "handover-once":
            if not await supervisor.handover_if_due():
                raise RuntimeError("No authorized posted handover was completed")
            print("OX_P4I_HANDOVER_DONE")
        elif mode.startswith("handover-interrupt-"):
            parts = mode.removeprefix("handover-interrupt-").split("-")
            if (len(parts) != 2
                    or parts[0] not in ("offer", "accept")
                    or parts[1] not in ("prepared", "committed", "ack")):
                raise ValueError("Unsupported handover interruption point")
            try:
                await supervisor.handover_if_due(interrupt_at=":".join(parts))
            except SimulatedWorkInterruption:
                print("OX_P4I_HANDOVER_INTERRUPTED " + ":".join(parts))
                return
            raise RuntimeError("Handover interruption never occurred")
        elif mode == "hails-once":
            if not await supervisor.respond_to_hails():
                raise RuntimeError("No authorized recipient hail was answered")
            print("OX_P4I_HAIL_DONE")
        elif mode.startswith("hails-interrupt-answer-"):
            point = mode.removeprefix("hails-interrupt-answer-")
            if point not in ("prepared", "committed", "ack"):
                raise ValueError("Unsupported hail interruption point")
            try:
                await supervisor.respond_to_hails(interrupt_at="answer:" + point)
            except SimulatedWorkInterruption:
                print("OX_P4I_HAIL_INTERRUPTED " + point)
                return
            raise RuntimeError("Hail interruption never occurred")
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
            or not (sys.argv[1] in (
                "begin", "resume", "serve", "handover-once", "hails-once",
            )
                    or any(sys.argv[1].startswith(prefix) for prefix in (
                        "resume-interrupt-", "begin-radio-interrupt-",
                        "handover-interrupt-", "hails-interrupt-answer-",
                    )))):
        raise SystemExit(
            "Usage: python -m ox_ai.runtime.watch_service "
            "begin|resume|serve|handover-once|hails-once|<stage>-interrupt-<point>"
        )
    asyncio.run(main_async(sys.argv[1]))


if __name__ == "__main__":
    main()
