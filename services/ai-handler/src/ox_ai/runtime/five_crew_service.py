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
from pathlib import Path
import sys

from ox_ai.agents.crew import CommandOption
from ox_ai.agents.live_concordia import LiveCrewBrain, make_model
from ox_ai.ports.base import ActionOutcome
from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.runtime.work_steps import WorkStepLedger, SimulatedWorkInterruption
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
        self.state.setdefault("specialist_jobs", {"mara": None, "teo": None})
        self.state.setdefault("specialist_handled", {"mara": [], "teo": []})
        self.state.setdefault("specialist_completed", [])
        if set(self.state["specialist_jobs"]) != set(EXTRA_ACCOUNTS):
            raise RuntimeError("Incompatible specialist job state")

    def checkpoint(self) -> None:
        """Persist each individual native Concordia graph and then the ledger."""
        for role, brain in self.brains.items():
            brain.save_checkpoint(CHECKPOINTS / (role + ".json"))
        atomic_json(self.state_path, self.state)

    async def _start_job(self, role: str) -> bool:
        if self.state["specialist_jobs"][role] is not None:
            return True
        events = await self.read_inbox(role)
        handled = set(self.state["specialist_handled"][role])
        new = [e for e in events
               if e["kind"] == ALARMS[role]
               and e["event_id"] not in handled]
        if not new:
            return False
        # The newest world alarm determines the present work. Older alarms
        # are not treated as permission to replay obsolete physical actions.
        latest = new[-1]
        self.state["specialist_handled"][role] = sorted(
            handled | {e["event_id"] for e in new}
        )
        self.brains[role].observe_event(latest)
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
    ) -> bool:
        if not await self._start_job(role):
            return False
        job = self.state["specialist_jobs"][role]
        if job["deferred"]:
            return False
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
                if expected not in reading:
                    # If the world has already resolved this old alarm through
                    # authorized human work, record no fictitious AI repair.
                    if job["index"] == 0 and (
                        ("SECURED" in reading and role == "mara")
                        or ("NOMINAL" in reading and role == "teo")
                    ):
                        job["index"] = len(plan)
                        break
                    raise RuntimeError(
                        f"{role}: expected {expected} from a local inspection"
                    )
                job["index"] += 1
                self.checkpoint()
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
                stage = f"physical-{job['index']}-{operation}"
                ledger = WorkStepLedger(
                    job, self.checkpoint, character_ids=self.ids,
                )
                if stage not in ledger.steps:
                    choice = brain.choose(
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

            if result.status != "succeeded" or not result.source_event_id:
                        raise RuntimeError("No committed action ACK to discard")
                    raise SimulatedLostAcknowledgement(
                        f"World committed {role} {operation}; ACK intentionally lost"
                    )

            if result.status != "succeeded" or not result.source_event_id:
                raise RuntimeError(
                    f"{role} {operation}: unknown or denied world action; "
                    "no fresh request will be generated"
                )
            brain.observe_local(
                f"World-confirmed {operation} receipt", result.source_event_id
            )
            job["effects"].append(result.source_event_id)
            job["pending"] = None
            job["index"] += 1
            self.checkpoint()

        self.state["specialist_completed"].append({
            "role": role,
            "alarm_event_id": job["event_id"],
            "world_effects": list(job["effects"]),
        })
        self.state["specialist_jobs"][role] = None
        self.checkpoint()
        return True

    async def service_departments(self) -> bool:
        """Prioritize life support over routine freight work, with no polling."""
        for role in ("teo", "mara"):
            if await self._advance_job(role):
                return True
        return False


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
            or not (sys.argv[1] in ("serve", "drop-replace-ack")
                    or sys.argv[1].startswith("interrupt-")
                    or sys.argv[1].startswith("finish-"))):
        raise SystemExit(
            "Usage: python -m ox_ai.runtime.five_crew_service "
            "serve|drop-replace-ack|interrupt-<role>-<op>-<point>|finish-<role>"
        )
    asyncio.run(run(sys.argv[1]))


if __name__ == "__main__":
    main()
