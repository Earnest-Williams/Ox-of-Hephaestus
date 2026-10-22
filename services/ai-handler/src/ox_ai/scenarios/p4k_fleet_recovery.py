"""P4k live acceptance: forty authenticated Evennia bodies across two boots.

Run as distinct handler processes:
  python -m ox_ai.scenarios.p4k_fleet_recovery begin
  # Stop Evennia, issue world-owned advance_fleet_recovery(), restart.
  python -m ox_ai.scenarios.p4k_fleet_recovery resume

One cargo round is world-receipted in 'begin' but deliberately *not*
acknowledged in the persisted handler state. 'resume' reconciles that same
request ID without repeating it. This is not a forty-agent GOAP trial.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import time
import uuid

from ox_ai.ports.base import ActionRequest
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.runtime.fleet_recovery import (
    FLEET_COUNT, FLEET_ROLES, FleetRecoverySupervisor,
)
from ox_ai.runtime.watch_service import ROOT, atomic_json


async def run(mode: str) -> dict:
    if mode not in {"begin", "resume"}:
        raise ValueError("Specify begin or resume for a fresh handler process")
    boot = time.perf_counter()
    supervisor = FleetRecoverySupervisor()
    native_restore_seconds = time.perf_counter() - boot
    if len({id(b.agent.entity) for b in supervisor.brains.values()}) != FLEET_COUNT:
        raise RuntimeError("Native fleet contains shared Concordia graphs")
    if mode == "begin" and supervisor.state["pending_work"] is not None:
        raise RuntimeError("Cannot prepare the same crash-recovery trial twice")
    if mode == "resume" and not isinstance(supervisor.state["pending_work"], dict):
        raise RuntimeError("Fresh process has no durably prepared world action")
    readiness = {}
    checkpoints_before = {
        role: brain.agent.revision for role, brain in supervisor.brains.items()
    }
    opened = time.perf_counter()
    try:
        await supervisor.open()
        login_seconds = time.perf_counter() - opened
        if not all(client.authenticated for client in supervisor.clients.values()):
            raise PermissionError("Not all forty world puppets authenticated")
        if len({client.character_dbref for client in supervisor.clients.values()}) != 40:
            raise PermissionError("Multiple sessions attempted to control one body")

        reading_started = time.perf_counter()
        per_role = {}
        for role in FLEET_ROLES:
            view = await supervisor.read_inbox(role)
            opening = list(view.select(kind="fleet_duty_posted"))
            updates = list(view.select(kind="fleet_duty_updated"))
            recorded = list(view.select(kind="round_recorded"))
            if (len(opening) != 1
                    or len(updates) != (0 if mode == "begin" else 1)
                    or len(recorded) != (0 if mode == "begin" else int(role == "fleet00"))):
                raise RuntimeError(f"Missing or duplicate world duty evidence for {role}")
            brain = supervisor.brains[role]
            if (brain.agent.revision != checkpoints_before[role]
                    + (1 if mode == "begin" else (2 if role == "fleet00" else 1))):
                raise RuntimeError(f"Native checkpoint cursor/revision mismatch for {role}")
            if not any("fleet_duty_posted" in m for m in brain.agent.memories):
                raise RuntimeError(f"Lost previously observed native memory: {role}")
            if mode == "resume" and not any(
                "fleet_duty_updated" in m for m in brain.agent.memories
            ):
                raise RuntimeError(f"Missing world update in native cognition: {role}")
            if any(
                f"Fleet Recovery Crew {j:02d}" in m
                for j in range(FLEET_COUNT) if j != int(role[-2:])
                for m in brain.agent.memories
            ):
                raise PermissionError("Another person's private duty memory leaked")
            per_role[role] = {
                "dbref": brain.character_id,
                "revision": brain.agent.revision,
                "inbox_cursor": supervisor.state["inbox_cursors"][role],
                "addressed_events": len(view),
            }
            readiness[role] = time.perf_counter() - reading_started

        # A replay of the same authentic world inbox is idempotent and must
        # neither inflate native cognition nor create duplicate work.
        for role in FLEET_ROLES:
            before = supervisor.brains[role].agent.revision
            await supervisor.read_inbox(role)
            if supervisor.brains[role].agent.revision != before:
                raise RuntimeError("Journal replay duplicated character cognition")

        if mode == "begin":
            client = supervisor.clients["fleet00"]
            # This qualified cargo officer obtains a real local readout
            # before asking the world to record one inspected duty round.
            await client.send_line("inspect cargo")
            await client.expect_text("CARGO RESTRAINT GRID C-01", timeout=15)
            request_id = uuid.uuid4().hex
            supervisor.state["pending_work"] = {
                "role": "fleet00", "request_id": request_id,
                "verb": "round_report", "target": "ship",
                "station": "cargo", "status": "prepared",
            }
            # Stable ID and intent survive; no world operation is submitted
            # until after the durable handler snapshot is on disk.
            supervisor.checkpoint()
            receipt = await DurableEvenniaPort(client).submit_work(ActionRequest(
                request_id, client.character_dbref, "round_report", "ship",
                arguments={"station": "cargo"},
            ))
            if receipt.status != "succeeded" or not receipt.source_event_id:
                raise RuntimeError("World did not commit the verified cargo duty round")
            # Simulate a lost handler ACK: do NOT checkpoint the successful
            # receipt or mark the prepared operation complete.
            proof_event_id = receipt.source_event_id
        else:
            work = supervisor.state["pending_work"]
            if (set(work) != {
                "role", "request_id", "verb", "target", "station", "status"
            } or work["role"] != "fleet00" or work["status"] != "prepared"
                    or work["verb"] != "round_report" or work["target"] != "ship"
                    or work["station"] != "cargo"):
                raise PermissionError("Recovered work intent is not the prepared duty")
            port = DurableEvenniaPort(supervisor.clients["fleet00"])
            first = await port.reconcile_work(work["request_id"])
            second = await port.reconcile_work(work["request_id"])
            if (first.status != "succeeded" or not first.source_event_id
                    or first != second):
                raise RuntimeError("World work receipt was lost, inconsistent or uncommitted")
            world_proof = await supervisor.prove_world_event(
                "fleet00", first.source_event_id, kind="round_recorded",
            )
            if world_proof["recipient_dbref"] != supervisor.ids["fleet00"]:
                raise PermissionError("Round receipt is not addressed to the actor")
            work["status"] = "reconciled"
            work["source_event_id"] = first.source_event_id
            supervisor.checkpoint()
            proof_event_id = first.source_event_id

        elapsed = sorted(readiness.values())
        result = {
            "status": "passed",
            "mode": mode,
            "scope": "forty_native_concordia_auth_world_continuity",
            "actors": FLEET_COUNT,
            "all_authenticated": True,
            "native_restore_seconds": round(native_restore_seconds, 4),
            "authenticated_login_seconds": round(login_seconds, 4),
            "first_actor_evidence_ready_seconds": round(elapsed[0], 4),
            "p95_actor_evidence_ready_seconds": round(elapsed[37], 4),
            "fleet_evidence_ready_seconds": round(elapsed[-1], 4),
            "world_round_receipt_id": proof_event_id,
            "receipt_reconciled_without_resubmit": mode == "resume",
            "per_actor": per_role,
        }
        return result
    finally:
        await supervisor.close()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("begin", "resume"):
        raise SystemExit(
            "Usage: python -m ox_ai.scenarios.p4k_fleet_recovery begin|resume"
        )
    mode = sys.argv[1]
    result = asyncio.run(run(mode))
    atomic_json(ROOT / "p4k" / (mode + "-verdict.json"), result)
    print("OX_P4K_FORTY_AUTHENTICATED_RECOVERY_" + mode.upper() + "_PASS")


if __name__ == "__main__":
    main()
