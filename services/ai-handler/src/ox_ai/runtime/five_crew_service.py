"""P4e: five independent Concordia crew, bounded department work and recovery.

Run: python -m ox_ai.runtime.five_crew_service serve

This is a separate *external* five-client handler. Each character connects
through a normal Evennia account and receives only addressed world events and
local readouts. Evennia owns every physical state and receipt.

For CI: 'drop-replace-ack' deliberately loses the world-confirmed cartridge
replacement acknowledgement, then a fresh 'serve' process must reconcile the
same request before executing further work. Never run this supervisor
simultaneously with the three-character watch_service for the same ship.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
import sys

from ox_ai.agents.crew import CommandOption
from ox_ai.agents.live_concordia import LiveCrewBrain, make_model
from ox_ai.ports.base import ActionOutcome
from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.ports.evennia.inventory import InventoryPort
from ox_ai.runtime.work_steps import WorkStepLedger, SimulatedWorkInterruption
from ox_ai.runtime.crew_agenda import AgentAgenda, ACTIVE, WAITING
from ox_ai.runtime.epistemics import AgentEpistemics
from ox_ai.runtime.watch_service import (
    CrewWatchSupervisor, ROOT, URL, atomic_json,
)

IDS = ROOT / "p4e-ids.json"
STATE = ROOT / "p4e-supervisor.json"
CHECKPOINTS = ROOT / "p4e"
EXTRA_ACCOUNTS = {"mara": "OxBotMara", "teo": "OxBotTeo"}

# Every task is a finite, predeclared *work plan*. Only the world can say
# whether an action was legal or changed real equipment. The two procedures
# have different requirements and observed intermediate states.
PROCEDURES = {
    "mara": (
        ("inspect", "UNSECURED"),
        ("restow", None),
        ("inspect", "RESTOWED"),
        ("certify", None),
        ("inspect", "SECURED"),
    ),
    "teo": (
        ("inspect", "SATURATED"),
        ("isolate", None),
        ("inspect", "ISOLATED"),
        ("replace", None),
        ("inspect", "SERVICED"),
        ("restart", None),
        ("inspect", "NOMINAL"),
    ),
}
TARGET = {"mara": "cargo", "teo": "scrubber"}
ALARMS = {"mara": "cargo_shift", "teo": "atmosphere_alarm"}
HEADERS = {
    "mara": "CARGO RESTRAINT GRID C-01",
    "teo": "ATMOSPHERE SCRUBBER A-01",
}

# Scheduling policy, NOT crew authority. Every task is grounded in a
# private world event, and its physical actions still require Evennia.
PRIORITY = {"mara": 40, "teo": 95}
RECONSIDER_ON = {
    "mara": ("cargo_shift", "cargo_review", "duty_review"),
    "teo": ("atmosphere_alarm", "supply_replenished", "duty_review"),
}


class SimulatedLostAcknowledgement(RuntimeError):
    """CI-only interruption after a physical commit and before handler ACK."""


class FiveCrewSupervisor(CrewWatchSupervisor):
    """Event-driven five-body supervisor, with two additional private brains."""

    def _restore_brains(self) -> dict[str, LiveCrewBrain]:
        """Override legacy snapshot search to use one dedicated P4e directory."""
        restored = {}
        for role in self.ids:
            path = CHECKPOINTS / (role + ".json")
            restored[role] = (
                LiveCrewBrain.from_checkpoint(role, self.ids[role], make_model(), path)
                if path.is_file()
                else LiveCrewBrain(role, self.ids[role], make_model())
            )
        return restored

    def __init__(self, *, state_path: Path = STATE) -> None:
        # The parent first validates the historical three-person ID file.
        # It never loads an omniscient world state or bypasses client auth.
        super().__init__(state_path=state_path)
        identities = json.loads(IDS.read_text(encoding="utf-8"))
        if set(identities) != set(self.ids) | set(EXTRA_ACCOUNTS):
            raise ValueError("Five unique world character IDs are required")
        if len(set(identities.values())) != 5:
            raise ValueError("Multiple crew accounts may not puppet one body")
        if any(identities[role] != self.ids[role] for role in self.ids):
            raise PermissionError("The legacy and five-crew identities disagree")
        password = os.environ["OX_PROBE_PASSWORD"]
        for role, username in EXTRA_ACCOUNTS.items():
            self.ids[role] = identities[role]
            self.clients[role] = EvenniaWebSocketClient(
                URL, username, password, self.ids[role], timeout=15
            )
            path = CHECKPOINTS / (role + ".json")
            self.brains[role] = (
                LiveCrewBrain.from_checkpoint(
                    role, self.ids[role], make_model(), path
                ) if path.is_file()
                else LiveCrewBrain(role, self.ids[role], make_model())
            )
            self.memories[role] = []
        if os.getenv("OX_CAPTAIN_OVERSIGHT", "0") == "1":
            captain_ids = ROOT / "p4f-captain-id.json"
            if not captain_ids.is_file():
                raise RuntimeError("Captain mode needs sixth authenticated world identity")
            captain_record = json.loads(captain_ids.read_text(encoding="utf-8"))
            if set(captain_record) != {"captain"}:
                raise PermissionError("Only one separate captain identity is allowed")
            captain_id = captain_record["captain"]
            if (not isinstance(captain_id, str) or not captain_id.startswith("#")
                    or captain_id in self.ids.values()):
                raise PermissionError("Captain must puppet a distinct real world character")
            self.ids["captain"] = captain_id
            self.clients["captain"] = EvenniaWebSocketClient(
                URL, "OxBotCaptain", password, captain_id, timeout=15,
            )
            captain_path = CHECKPOINTS / "captain.json"
            self.brains["captain"] = (
                LiveCrewBrain.from_checkpoint(
                    "captain", captain_id, make_model(), captain_path,
                ) if captain_path.is_file()
                else LiveCrewBrain("captain", captain_id, make_model())
            )
            self.memories["captain"] = []
        self.state.setdefault("specialist_jobs", {"mara": None, "teo": None})
        self.state.setdefault("specialist_handled", {"mara": [], "teo": []})
        self.state.setdefault("specialist_completed", [])
        if set(self.state["specialist_jobs"]) != set(EXTRA_ACCOUNTS):
            raise RuntimeError("Incompatible specialist job state")
        stored = self.state.setdefault("agendas", {})
        if not isinstance(stored, dict) or any(role not in self.ids for role in stored):
            raise PermissionError("Invalid or cross-character agenda state")
        self.agendas = {
            role: AgentAgenda(
                stored.setdefault(role, {}),
                role=role, character_id=actor,
            )
            for role, actor in self.ids.items()
        }
        # Belief is actor-private, never a proxy for the world DB. An old
        # checkpoint is additively upgraded without silently claiming facts.
        stored_epistemics = self.state.setdefault("epistemics", {})
        if (not isinstance(stored_epistemics, dict)
                or any(role not in self.ids for role in stored_epistemics)):
            raise PermissionError("Invalid cross-character epistemic state")
        self.epistemics = {
            role: AgentEpistemics(
                stored_epistemics.setdefault(role, {}),
                role=role, character_id=character_id,
            )
            for role, character_id in self.ids.items()
        }
        proof_cursors = self.state.setdefault("epistemic_event_cursors", {})
        if (not isinstance(proof_cursors, dict)
                or any(role not in self.ids or type(serial) is not int or serial < 0
                       for role, serial in proof_cursors.items())):
            raise PermissionError("Invalid actor-private event proof cursors")

    async def read_inbox(self, role: str) -> list[dict]:
        """Ingest ONLY this actor's real events into their private agenda.

        Old P4e histories are fully paginated by the parent reader. Replays
        do not reawaken deferred work or recreate completed obligations.
        """
        events = await super().read_inbox(role)
        agenda = self.agendas[role]
        changed = False
        proof_cursors = self.state.setdefault("epistemic_event_cursors", {})
        proof_cursor = proof_cursors.get(role, 0)
        if type(proof_cursor) is not int or proof_cursor < 0:
            raise PermissionError("Invalid private proof cursor")
        for event in events:
            sequence = int(event["sequence"])
            # The legacy consumer replays the entire inbox on every pass.
            # Prove each NEW addressed event once; replaying aged proofs
            # would otherwise churn a bounded 512-entry evidence cache.
            if sequence > proof_cursor:
                self.epistemics[role].receive_event(event)
                proof_cursor = sequence
                proof_cursors[role] = sequence
                changed = True
            if sequence > agenda.record["last_sequence"]:
                agenda.observe(event)
                changed = True
            if role in EXTRA_ACCOUNTS and event["kind"] == ALARMS[role]:
                if agenda.task(event["event_id"]) is None:
                    agenda.offer(
                        event, priority=PRIORITY[role],
                        kind=ALARMS[role],
                    )
                    changed = True
        # Additively upgrade pre-G2 completed P4e entries only when their
        # original private source event was genuinely observed by this role.
        for finished in self.state["specialist_completed"]:
            if finished.get("role") != role:
                continue
            item = agenda.task(finished["alarm_event_id"])
            if item and item["status"] == "offered":
                effects = finished.get("world_effects") or []
                if not effects:
                    # A P4e job could be discarded after observing that a
                    # human had already restored the equipment. That is not
                    # this AI's world-confirmed success.
                    agenda.set_status(
                        item["task_id"], "declined",
                        reason="historic_alarm_already_resolved_by_world",
                    )
                else:
                    agenda.set_status(
                        item["task_id"], "accepted",
                        reason="historical_world_confirmed_obligation",
                    )
                    agenda.set_status(
                        item["task_id"], "in_progress",
                        reason="historical_world_confirmed_work",
                    )
                    agenda.set_status(
                        item["task_id"], "completed",
                        reason="historical_verified_specialist_receipts",
                        effects=effects,
                    )
                changed = True
        if changed:
            self.checkpoint()
        return events

    def _job_task(self, role: str) -> dict:
        job = self.state["specialist_jobs"][role]
        if not isinstance(job, dict):
            raise RuntimeError("Specialist has no active world-grounded work")
        task = self.agendas[role].task(job["event_id"])
        if task is None:
            raise PermissionError("Specialist work has no private source event")
        return task

    def _ready_specialists(self) -> list[tuple[str, dict]]:
        candidates = []
        for role in EXTRA_ACCOUNTS:
            job = self.state["specialist_jobs"][role]
            if job is None:
                continue
            task = self._job_task(role)
            if task["status"] in ACTIVE and not job["deferred"]:
                candidates.append((role, task))
        return sorted(
            candidates, key=lambda pair: (
                -pair[1]["priority"], pair[1]["source_sequence"], pair[0]
            ),
        )

    def checkpoint(self) -> None:
        """Persist each individual native Concordia graph and then the ledger."""
        for role, brain in self.brains.items():
            brain.save_checkpoint(CHECKPOINTS / (role + ".json"))
        atomic_json(self.state_path, self.state)

    async def _start_job(self, role: str) -> bool:
        # Always ingest new addressed events, including reconsideration
        # triggers, *before* deciding whether a retained job is ready.
        events = await self.read_inbox(role)
        job = self.state["specialist_jobs"][role]
        if job is not None:
            task = self.agendas[role].task(job["event_id"])
            if task is None:
                # Recovery of a pre-G2 P4e snapshot: recover its actual
                # originally addressed event, never fabricate task authority.
                previous = next(
                    (e for e in events
                     if e["event_id"] == job["event_id"]
                     and e["kind"] == ALARMS[role]), None,
                )
                if previous is None:
                    raise PermissionError("Persisted job lacks source observation")
                task = self.agendas[role].offer(
                    previous, kind=ALARMS[role], priority=PRIORITY[role],
                )
            changed = False
            if task["status"] == "offered":
                if job["deferred"]:
                    # Legacy deferred work must NOT silently wake just because
                    # its event history was replayed during checkpoint upgrade.
                    self.agendas[role].defer(
                        job["event_id"],
                        reason="legacy_deferred_requires_new_evidence",
                        event_kinds=RECONSIDER_ON[role],
                        after_sequence=self.agendas[role].record["last_sequence"],
                    )
                else:
                    self.agendas[role].set_status(
                        job["event_id"], "accepted",
                        reason="restored_existing_world_obligation",
                    )
                changed = True
            if job["deferred"] and task["status"] == "accepted":
                job["deferred"] = False
                changed = True
            if changed:
                self.checkpoint()
            return True
        handled = set(self.state["specialist_handled"][role])
        new = [
            e for e in events if e["kind"] == ALARMS[role]
            and e["event_id"] not in handled
        ]
        if not new:
            return False
        # The latest alarm determines current equipment state. Older
        # observations remain audited as locally declined superseded tasks,
        # never disappear from the agenda without an explicit disposition.
        latest = new[-1]
        for obsolete in new[:-1]:
            item = self.agendas[role].task(obsolete["event_id"])
            if item is not None and item["status"] == "offered":
                self.agendas[role].set_status(
                    obsolete["event_id"], "declined",
                    reason="superseded_by_later_equipment_alarm",
                )
        self.state["specialist_handled"][role] = sorted(
            handled | {e["event_id"] for e in new}
        )
        self.brains[role].observe_event(latest)
        if role == "teo":
            self.epistemics[role].ask(
                "scrubber.spares",
                reason="Cartridge availability requires a current local inspection",
            )
        self.agendas[role].set_status(
            latest["event_id"], "accepted",
            reason="posted_specialist_duty_selected",
        )
        self.state["specialist_jobs"][role] = {
            "event_id": latest["event_id"], "index": 0,
            "pending": None, "deferred": False, "effects": [],
        }
        self.checkpoint()
        return True

    async def _advance_job(
        self, role: str, *, drop_after: str | None = None,
        interrupt_operation: str | None = None,
        interrupt_point: str | None = None,
        stop_after: str | None = None,
        allow_preemption: bool = False,
    ) -> bool:
        if not await self._start_job(role):
            return False
        job = self.state["specialist_jobs"][role]
        task = self._job_task(role)
        if job["deferred"] or task["status"] in WAITING:
            return False
        if task["status"] in ("accepted", "interrupted"):
            self.agendas[role].set_status(
                job["event_id"], "in_progress",
                reason="resuming_locally_selected_work",
            )
            self.checkpoint()
        elif task["status"] != "in_progress":
            raise RuntimeError("Specialist has no selectable obligation")
        # The role's historical checkpoint is not evidence of physical
        # presence. An independently authenticated character must travel
        # through real exits and re-observe its own assigned workstation.
        await self.ensure_station(
            role, "Cargo Hold" if role == "mara" else "Environmental Plant",
        )
        client = self.clients[role]
        brain = self.brains[role]
        port = DurableEvenniaPort(client)
        target = TARGET[role]
        plan = PROCEDURES[role]

        while job["index"] < len(plan):
            operation, expected = plan[job["index"]]
            if operation == "inspect":
                await client.send_line("inspect " + target)
                reading = await client.expect_text(HEADERS[role], timeout=12)
                brain.observe_local("Local specialist equipment inspection", reading)
                if role == "teo":
                    # The earlier text readout does NOT include a world
                    # timestamp, so using the brain's last event time would
                    # misdate subsequent inspections. Query the separately
                    # typed, authenticated LOCAL stock port for both amount
                    # and actual source-world game time instead.
                    snapshot = await InventoryPort(client).observe()
                    if snapshot.local_cartridges is not None:
                        self.epistemics[role].observe_verified(
                            "scrubber.spares", snapshot.local_cartridges,
                            evidence_id="worldinv-" + uuid.uuid4().hex,
                            at=snapshot.game_time, valid_for=0,
                            source="world_local",
                        )
                        if snapshot.local_cartridges == 0:
                            self.epistemics[role].ask(
                                "scrubber.next_restock_at",
                                reason="No actual future delivery has been confirmed",
                            )
                if expected not in reading:
                    # If the world has already resolved this old alarm through
                    # authorized human work, record no fictitious AI repair.
                    if job["index"] == 0 and (
                        ("SECURED" in reading and role == "mara")
                        or ("NOMINAL" in reading and role == "teo")
                    ):
                        job["index"] = len(plan)
                        job["resolved_elsewhere"] = True
                        break
                    raise RuntimeError(
                        f"{role}: expected {expected} from a local inspection"
                    )
                job["index"] += 1
                self.checkpoint()
                if allow_preemption and await self._interrupt_for_urgent(role):
                    return True
                continue

            legacy_pending = job["pending"]
            if legacy_pending is not None:
                # A pre-P4j checkpoint may contain a submitted equipment-
                # specific oxaction ID. NEVER transfer that ID to the newer
                # namespace or create a replacement; reconcile the original
                # world fixture receipt for this exact stage.
                if (legacy_pending["operation"] != operation
                        or legacy_pending["index"] != job["index"]):
                    raise RuntimeError(
                        "Legacy pending physical action mismatches work plan"
                    )
                result = await port.reconcile(
                    legacy_pending["request_id"], target=target,
                )
            else:
                # New work has one actor-scoped global WorkReceipt ID per
                # procedure step, saved inside the independent handler's
                # specialist job checkpoint before any network transmission.
                base_stage = f"physical-{job['index']}-{operation}"
                attempts = job.setdefault("work_attempts", {})
                generation = int(attempts.get(base_stage, 0))
                stage = (base_stage if not generation
                         else f"{base_stage}-retry-{generation}")
                ledger = WorkStepLedger(
                    job, self.checkpoint, character_ids=self.ids,
                )
                # A past world refusal stays permanently receipted. The
                # next attempt gets a NEW ID only after a new, correctly
                # addressed world event has reaccepted the blocked agenda.
                prior = ledger.steps.get(stage)
                if prior and prior.get("status") == "failed":
                    attempts[base_stage] = generation + 1
                    generation += 1
                    stage = f"{base_stage}-retry-{generation}"
                    self.checkpoint()
                if stage not in ledger.steps:
                    choice = await self.choose(role, 
                        CommandOption(
                            f"Perform verified {operation} on local {target}",
                            operation + "_" + target,
                        ),
                        alternative="Defer until equipment can be serviced safely",
                    )
                    if choice.verb != operation + "_" + target:
                        brain.agent.record_outcome(ActionOutcome(
                            choice.request_id, "succeeded",
                            "Chose deferral; no physical command dispatched",
                        ))
                        self.agendas[role].defer(
                            job["event_id"],
                            reason="agent_deferred_" + operation,
                            event_kinds=RECONSIDER_ON[role],
                            after_sequence=self.agendas[role].record["last_sequence"],
                        )
                        job["deferred"] = True
                        self.checkpoint()
                        return False
                    brain.selected_procedure(choice)
                crash_point = None
                if drop_after == operation:
                    crash_point = stage + ":committed"
                if interrupt_operation == operation:
                    if interrupt_point not in ("prepared", "committed", "ack"):
                        raise ValueError("Invalid specialist interruption point")
                    crash_point = stage + ":" + interrupt_point
                try:
                    result = await ledger.run(
                        stage, role, operation + "_" + target, target,
                        port, interrupt_at=crash_point,
                    )
                except SimulatedWorkInterruption as exc:
                    raise SimulatedLostAcknowledgement(str(exc)) from exc
                except RuntimeError:
                    settled = ledger.steps.get(stage)
                    if settled is None or settled.get("status") != "failed":
                        # Unknown provider/socket state is not a refusal;
                        # preserve original work ID for exact reconciliation.
                        raise
                    self.agendas[role].defer(
                        job["event_id"],
                        reason="world_refused_" + operation,
                        blocked=True,
                        event_kinds=RECONSIDER_ON[role],
                        after_sequence=self.agendas[role].record["last_sequence"],
                    )
                    job["deferred"] = True
                    self.checkpoint()
                    return False

            if result.status != "succeeded" or not result.source_event_id:
                raise RuntimeError(
                    f"{role} {operation}: unknown or denied world action; "
                    "no fresh request will be generated"
                )
            brain.observe_local(
                f"World-confirmed {operation} receipt", result.source_event_id
            )
            if result.source_event_id not in job["effects"]:
                job["effects"].append(result.source_event_id)
            job["pending"] = None
            job["index"] += 1
            self.checkpoint()
            if stop_after == operation:
                return True
            if allow_preemption and await self._interrupt_for_urgent(role):
                return True

        if job.get("resolved_elsewhere"):
            self.agendas[role].set_status(
                job["event_id"], "declined",
                reason="world_equipment_already_resolved_by_another_actor",
            )
        else:
            self.agendas[role].set_status(
                job["event_id"], "completed",
                reason="world_receipts_and_local_final_inspection",
                effects=list(job["effects"]),
            )
        self.state["specialist_completed"].append({
            "role": role,
            "alarm_event_id": job["event_id"],
            "world_effects": list(job["effects"]),
        })
        self.state["specialist_jobs"][role] = None
        self.checkpoint()
        return True

    async def _interrupt_for_urgent(self, role: str) -> bool:
        """Only preempt between world-validated steps, never mid-request."""
        for other in EXTRA_ACCOUNTS:
            if other != role:
                await self._start_job(other)
        candidates = self._ready_specialists()
        if not candidates or candidates[0][0] == role:
            return False
        urgent = candidates[0][1]
        job = self.state["specialist_jobs"][role]
        if job and self.agendas[role].interrupt(
            job["event_id"], urgent=urgent,
        ):
            self.checkpoint()
            return True
        return False

    async def _maybe_supply_cooperation(self) -> bool:
        """Opt-in bounded multi-actor handoff; preserves legacy world trials."""
        if os.getenv("OX_G3_COOPERATIVE_SUPPLY", "0") != "1":
            return False
        from ox_ai.runtime.cooperative_supply import CooperativeSupply
        coordinator = CooperativeSupply(self)
        if coordinator.record is not None and coordinator.record["completed"]:
            return False
        result = await coordinator.advance()
        return result in ("requested", "completed", "teo_work_in_progress")

    async def service_independent_rounds(self) -> bool:
        # Existing priority: faults, human hails, watch handover, then
        # investigation, then optional wear rounds. No idle model polling.
        if await self.service_uncertain_investigation():
            return True
        if await self.service_captain_oversight():
            return True
        if await self.service_followup_investigation():
            return True
        return await self._service_existing_independent_rounds()

    async def service_captain_oversight(self) -> bool:
        """Sixth independently authenticated officer ensures open work continues."""
        if os.getenv("OX_CAPTAIN_OVERSIGHT", "0") != "1":
            return False
        from ox_ai.runtime.captain_followthrough import CaptainFollowthrough
        return await CaptainFollowthrough(self).advance()

    async def service_followup_investigation(self) -> bool:
        """Opt-in independent challenges/tests before optional wear rounds."""
        if os.getenv("OX_G3E_FOLLOWUP", "0") != "1":
            return False
        from ox_ai.runtime.investigation_followup import FollowupInvestigation
        return await FollowupInvestigation(self).advance()

    async def _service_existing_independent_rounds(self) -> bool:
        """Let one actor elect a private world-created duty opportunity.

        This hook is opt-in, preserves incident precedence and performs no
        hidden-state lookup. The world still requires physical inspection
        before a round report or preventive operation succeeds.
        """
        if os.getenv("OX_G3D_INDEPENDENT_ROUNDS", "0") != "1":
            return False
        stations = {
            "lin": ("Bridge", "operations", "FREIGHTER OPERATIONS TELEMETRY"),
            "ari": ("Engineering", "pump", "Cooling Pump P-01"),
            "iona": ("Engineering", "pump", "Cooling Pump P-01"),
            "mara": ("Cargo Hold", "cargo", "CARGO RESTRAINT GRID C-01"),
            "teo": ("Environmental Plant", "scrubber", "ATMOSPHERE SCRUBBER A-01"),
        }
        rounds = self.state.setdefault("independent_rounds", {})
        if not isinstance(rounds, dict) or any(r not in self.ids for r in rounds):
            raise PermissionError("Invalid character-scoped independent round state")
        for role in self.ids:
            events = await self.read_inbox(role)
            windows = [e for e in events if e["kind"] == "crew_round_window"]
            if not windows:
                continue
            latest = max(windows, key=lambda e: int(e["data"]["cycle"]))
            cycle = int(latest["data"]["cycle"])
            record = rounds.get(role)
            if record is not None:
                if (record.get("actor") != self.ids[role]
                        or type(record.get("cycle")) is not int
                        or record["cycle"] < 1):
                    raise PermissionError("Cross-character round checkpoint")
                if record["cycle"] > cycle:
                    raise RuntimeError("World round sequence went backwards")
                if record["cycle"] == cycle and record.get("done"):
                    continue
                if record["cycle"] < cycle:
                    if not record.get("done"):
                        # Complete the earlier receipted work before a new round.
                        pass
                    else:
                        record = None
            if record is None:
                offer = await self.choose(
                    role, CommandOption(
                        "Take an independent station inspection round", "round_inspect",
                    ), alternative="Defer optional rounds for this duty window",
                )
                record = {
                    "actor": self.ids[role], "cycle": cycle,
                    "selected": offer.verb == "round_inspect",
                    "station": stations[role][1], "done": False,
                }
                rounds[role] = record
                self.checkpoint()
            if not record["selected"]:
                record["done"] = True
                self.checkpoint()
                return True
            place, station, expected = stations[role]
            await self.ensure_station(role, place)
            client = self.clients[role]
            # Confirm actual presence by an authenticated local readout.
            # This observation must not be inferred from the private map.
            if "work_steps" not in record or "report" not in record["work_steps"]:
                await client.send_line("inspect " + station)
                reading = await client.expect_text(expected, timeout=12)
                self.brains[role].observe_local(
                    "Self-directed local round at " + station, reading,
                )
            ledger = WorkStepLedger(record, self.checkpoint,
                                    character_ids=self.ids)
            outcome = await ledger.run(
                "report", role, "round_report", "ship",
                DurableEvenniaPort(client), arguments={"station": station},
            )
            if not outcome.source_event_id:
                raise RuntimeError("World gave no round report proof")
            self.epistemics[role].observe_verified(
                "rounds." + station, cycle,
                evidence_id=outcome.source_event_id,
                at=float(latest["game_time"]), source="world_receipt",
            )
            # The first-person world round receipt is not a diagnosis.
            # Re-read this actor's addressed report for its wear finding;
            # do not consult world Attributes or the bridge's private mail.
            own = await self.read_inbox(role)
            reports = [
                e for e in own if e["kind"] == "round_recorded"
                and e["event_id"] == outcome.source_event_id
                and e["data"].get("cycle") == record["cycle"]
                and e["data"].get("station") == station
            ]
            if not reports:
                raise RuntimeError("Authenticated local round proof not delivered")
            report = reports[-1]
            if (role in ("mara", "teo")
                    and report["data"].get("finding") == "maintenance_due"):
                operation = "retension" if role == "mara" else "purge"
                target = "cargo" if role == "mara" else "scrubber"
                if "preventive_selected" not in record:
                    choice = await self.choose(
                        role, CommandOption(
                            "Perform locally indicated preventive " + operation,
                            operation + "_" + target,
                        ), alternative="File finding without preventive intervention",
                    )
                    record["preventive_selected"] = (
                        choice.verb == operation + "_" + target
                    )
                    self.checkpoint()
                if record["preventive_selected"]:
                    await WorkStepLedger(
                        record, self.checkpoint, character_ids=self.ids,
                    ).run(
                        "preventive", role, operation + "_" + target,
                        target, DurableEvenniaPort(client),
                    )
            record["done"] = True
            self.checkpoint()
            return True
        return False

    async def service_uncertain_investigation(self) -> bool:
        """Opt-in five-person investigation, with no oracle and no forced answer.

        Each participant receives their own case notice, chooses to visit the
        instrument, obtains a real local sample, and files one durable report.
        Only Lin sees reported cross-department evidence. A diagnosis may be
        wrong and is explicitly tentative; unseen root cause is never read.
        """
        if os.getenv("OX_G3E_INVESTIGATION", "0") != "1":
            return False
        stations = {
            "lin": "Bridge", "ari": "Engineering", "iona": "Engineering",
            "mara": "Cargo Hold", "teo": "Environmental Plant",
        }
        cases = self.state.setdefault("g3e_investigations", {})
        if not isinstance(cases, dict) or any(k not in self.ids for k in cases):
            raise PermissionError("Foreign investigation checkpoint")
        for role in self.ids:
            messages = await self.read_inbox(role)
            notices = [e for e in messages if e["kind"] == "anomaly_notice"]
            if not notices:
                continue
            notice = notices[-1]
            case_id = notice["data"].get("case_id")
            if not isinstance(case_id, str) or len(case_id) != 32:
                raise RuntimeError("Malformed world investigation identity")
            record = cases.get(role)
            if record is not None and (record.get("actor") != self.ids[role]
                                       or record.get("case_id") != case_id):
                raise PermissionError("Investigation case identity mismatch")
            if record is None:
                decision = await self.choose(
                    role, CommandOption("Investigate the unexplained anomaly", "investigate"),
                    alternative="Defer nonurgent investigation",
                )
                record = {"actor": self.ids[role], "case_id": case_id,
                          "selected": decision.verb == "investigate", "done": False}
                cases[role] = record
                self.checkpoint()
            if not record["selected"] or record["done"]:
                continue
            await self.ensure_station(role, stations[role])
            client = self.clients[role]
            if "report" not in record.get("work_steps", {}):
                await client.send_line("oxsample " + case_id)
                reading = await client.expect_text("OX_ANOMALY_SAMPLE " + case_id, timeout=12)
                self.brains[role].observe_local("Firsthand anomaly instrument", reading)
                self.checkpoint()
            result = await WorkStepLedger(
                record, self.checkpoint, character_ids=self.ids,
            ).run(
                "report", role, "anomaly_report", "ship",
                DurableEvenniaPort(client), arguments={"case_id": case_id},
            )
            if not result.source_event_id:
                raise RuntimeError("No world-proven anomaly report")
            events = await self.read_inbox(role)
            if not any(e["event_id"] == result.source_event_id
                       and e["kind"] == "anomaly_report_recorded" for e in events):
                raise RuntimeError("Report not visible to its own author")
            record["done"] = True
            self.checkpoint()
            return True
        # Assessment is a separate bridge decision after authenticated
        # reports from engineering and a specialist; never forced by the GM.
        lin = cases.get("lin")
        if lin is None or not lin.get("done") or lin.get("assessment_done"):
            return False
        case_id = lin["case_id"]
        events = await self.read_inbox("lin")
        reports = [e for e in events if e["kind"] == "anomaly_crew_report"
                   and e["data"].get("case_id") == case_id]
        senders = {e["sender_dbref"] for e in reports}
        if not (any(self.ids[r] in senders for r in ("ari", "iona"))
                and any(self.ids[r] in senders for r in ("mara", "teo"))):
            return False
        # Preserve all candidate causes. Inference sees only Lin's own
        # memory, which includes legitimate world-delivered crew reports.
        if "hypothesis" not in lin:
            options = [
                CommandOption("Hypothesis: cargo vapors", "cargo_vapors"),
                CommandOption("Hypothesis: scrubber bypass", "scrubber_bypass"),
                CommandOption("Hypothesis: electrical bus interference", "bus_interference"),
                CommandOption("Insufficient evidence: defer diagnosis", "defer"),
            ]
            choice = await self.cognition.decide(
                "lin", self.brains["lin"].agent, options,
            )
            lin["hypothesis"] = choice.verb
            self.checkpoint()
        if lin["hypothesis"] == "defer":
            # Deferral does not erase a known unknown or prevent specialists
            # from independently pursuing evidence in the next wake cycle.
            if os.getenv("OX_G3E_INDEPENDENT_QUESTIONS", "0") == "1":
                self.epistemics["lin"].ask(
                    "anomaly." + case_id + ".cause",
                    reason="World analyzer discrepancy remains unexplained",
                )
            lin["assessment_done"] = True
            self.checkpoint()
            return True
        result = await WorkStepLedger(
            lin, self.checkpoint, character_ids=self.ids,
        ).run(
            "assessment", "lin", "anomaly_assess", "ship",
            DurableEvenniaPort(self.clients["lin"]),
            arguments={"case_id": case_id, "hypothesis": lin["hypothesis"]},
        )
        if not result.source_event_id:
            raise RuntimeError("World did not record provisional assessment")
        lin["assessment_done"] = True
        self.checkpoint()
        return True

    async def service_departments(self) -> bool:
        """Choose actual duties, then consider blocked real supply dependencies."""
        for role in EXTRA_ACCOUNTS:
            await self._start_job(role)
        candidates = self._ready_specialists()
        if not candidates:
            return await self._maybe_supply_cooperation()
        role, urgent = candidates[0]
        for other, task in candidates[1:]:
            if self.agendas[other].interrupt(
                task["task_id"], urgent=urgent,
            ):
                self.checkpoint()
        progressed = await self._advance_job(role, allow_preemption=True)
        if not progressed:
            return await self._maybe_supply_cooperation()
        return progressed


async def run(mode: str) -> None:
    supervisor = FiveCrewSupervisor()
    try:
        await supervisor.open()
        if mode == "drop-replace-ack":
            try:
                await supervisor._advance_job("teo", drop_after="replace")
            except SimulatedLostAcknowledgement:
                print("OX_P4E_REPLACEMENT_ACK_DROPPED_WORLD_COMMITTED")
                return
            raise RuntimeError("No environmental replacement was interrupted")
        if mode.startswith("interrupt-"):
            parts = mode.split("-")
            if (len(parts) != 4 or parts[1] not in EXTRA_ACCOUNTS
                    or parts[3] not in ("prepared", "committed", "ack")
                    or parts[2] not in {
                        op for op, _ in PROCEDURES[parts[1]] if op != "inspect"
                    }):
                raise ValueError("Unsupported specialist work interruption")
            try:
                await supervisor._advance_job(
                    parts[1],
                    interrupt_operation=parts[2],
                    interrupt_point=parts[3],
                )
            except SimulatedLostAcknowledgement:
                print("OX_P4J_SPECIALIST_INTERRUPTED " + ":".join(parts[1:]))
                return
            raise RuntimeError("Requested specialist interruption did not occur")
        if mode == "agenda-pause-cargo":
            progressed = await supervisor._advance_job(
                "mara", stop_after="restow",
            )
            job = supervisor.state["specialist_jobs"]["mara"]
            if not progressed or job is None or job["index"] != 2:
                raise RuntimeError("Cargo pause did not stop after real restow")
            print("OX_G2_CARGO_PAUSED_AFTER_WORLD_RESTOW")
            return
        if mode == "captain-drain":
            if os.getenv("OX_CAPTAIN_OVERSIGHT", "0") != "1":
                raise RuntimeError("Captain trial requires sixth authenticated crew")
            progressed = 0
            for _ in range(50):
                if not await supervisor.service_captain_oversight():
                    break
                progressed += 1
            else:
                raise RuntimeError("Captain follow-up did not reach bounded idle")
            print("OX_G3F_CAPTAIN_DRAINED", progressed)
            return
        if mode == "followup-drain":
            if os.getenv("OX_G3E_FOLLOWUP", "0") != "1":
                raise RuntimeError("G3e follow-up requires explicit opt-in")
            count = 0
            for _ in range(6):
                if not await supervisor.service_followup_investigation():
                    break
                count += 1
            else:
                raise RuntimeError("Follow-up exceeded bounded work stages")
            print("OX_G3E_FOLLOWUP_DRAINED", count)
            return
        if mode == "investigation-drain":
            if os.getenv("OX_G3E_INVESTIGATION", "0") != "1":
                raise RuntimeError("G3e investigation requires opt-in")
            total = 0
            for _ in range(8):
                if not await supervisor.service_uncertain_investigation():
                    break
                total += 1
            else:
                raise RuntimeError("Investigation exceeded bounded steps")
            print("OX_G3E_INVESTIGATION_DRAINED", total)
            return
        if mode == "round-drain":
            if os.getenv("OX_G3D_INDEPENDENT_ROUNDS", "0") != "1":
                raise RuntimeError("Independent round test requires explicit opt-in")
            completed = 0
            for _ in range(len(supervisor.ids) + 1):
                if not await supervisor.service_independent_rounds():
                    break
                completed += 1
            else:
                raise RuntimeError("Independent round drain exceeded crew budget")
            print("OX_G3D_ROUNDS_DRAINED", completed)
            return
        if mode == "agenda-once":
            progressed = await supervisor.service_departments()
            print("OX_G2_AGENDA_STEP", progressed)
            return
        if mode == "agenda-finish":
            for attempt in range(12):
                if not await supervisor.service_departments():
                    break
            else:
                raise RuntimeError("Agenda dispatch exceeded bounded wake cycle")
            print("OX_G2_AGENDA_DRAINED")
            return
        if mode.startswith("finish-"):
            role = mode.removeprefix("finish-")
            if role not in EXTRA_ACCOUNTS:
                raise ValueError("Unknown specialist duty")
            if not await supervisor._advance_job(role):
                raise RuntimeError("No specialist work was completed")
            print("OX_P4J_SPECIALIST_FINISHED " + role)
            return
        if mode != "serve":
            raise ValueError("Unknown five-crew runtime mode")
        await supervisor.serve()
    finally:
        await supervisor.close()


def main() -> None:
    if (len(sys.argv) != 2
            or not (sys.argv[1] in (
                "serve", "drop-replace-ack",
                "agenda-pause-cargo", "agenda-once", "agenda-finish",
                "round-drain", "investigation-drain", "followup-drain", "captain-drain",
            )
                    or sys.argv[1].startswith("interrupt-")
                    or sys.argv[1].startswith("finish-"))):
        raise SystemExit(
            "Usage: python -m ox_ai.runtime.five_crew_service "
            "serve|drop-replace-ack|agenda-pause-cargo|agenda-once|agenda-finish|round-drain|investigation-drain|followup-drain|captain-drain|"
            "interrupt-<role>-<op>-<point>|finish-<role>"
        )
    asyncio.run(run(sys.argv[1]))


if __name__ == "__main__":
    main()
