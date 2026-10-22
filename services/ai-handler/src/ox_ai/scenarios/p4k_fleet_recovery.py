"""P4k/P4l: forty model-selected real duty requests across process restarts.

Phase begin: forty separate authenticated native Concordia minds receive
individual world evidence, inspect an actual nearby station, each select
a typed world action, persist the proposed ActionRequest, and issue it.
The world ACKs are deliberately *not* committed to the handler.

Phase resume: fresh Evennia and handler processes reauthenticate all forty
identities, independently attest actor-private journal histories, restore
forty pending model-selected intents and reconcile their unchanged IDs
against world-owned receipts. NO action is resubmitted.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import time

from ox_ai.agents.crew import CommandOption
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.runtime.fleet_recovery import (
    FLEET_COUNT, FLEET_ROLES, FleetRecoverySupervisor,
)
from ox_ai.runtime.watch_service import ROOT, atomic_json


# Mirrors the disposable operator fixture's spatial stations, never an
# authority claim. Every work attempt is rechecked by Evennia regardless.
STATIONS = ("cargo", "scrubber", "operations", "pump")
READOUTS = {
    "cargo": "CARGO RESTRAINT GRID C-01",
    "scrubber": "ATMOSPHERE SCRUBBER A-01",
    "operations": "FREIGHTER OPERATIONS TELEMETRY",
    "pump": "Cooling Pump P-01",
}


def station_for(role: str) -> str:
    if role not in FLEET_ROLES:
        raise PermissionError("Unknown fleet station holder")
    return STATIONS[int(role[-2:]) % len(STATIONS)]


def verify_pending_record(role: str, work: dict) -> None:
    if (not isinstance(work, dict)
            or set(work) not in (
                {"role", "request_id", "station", "status"},
                {"role", "request_id", "station", "status", "source_event_id"},
            )
            or work.get("role") != role
            or work.get("station") != station_for(role)
            or work.get("status") not in ("prepared", "reconciled")
            or not isinstance(work.get("request_id"), str)
            or len(work["request_id"]) != 32):
        raise PermissionError("Recovered pending duty intent is malformed")
    if (work["status"] == "prepared" and "source_event_id" in work
            or work["status"] == "reconciled" and "source_event_id" not in work):
        raise PermissionError("Pending duty outcome was not checkpointed atomically")


async def run(mode: str) -> dict:
    if mode not in {"begin", "resume"}:
        raise ValueError("Expected begin or resume in independent handler process")
    boot = time.perf_counter()
    supervisor = FleetRecoverySupervisor()
    native_restore_seconds = time.perf_counter() - boot
    if len({id(b.agent.entity) for b in supervisor.brains.values()}) != FLEET_COUNT:
        raise RuntimeError("Two fleet characters share a Concordia graph")

    pending = supervisor.state.get("pending_work")
    if mode == "begin" and pending is not None:
        raise RuntimeError("Cannot prepare an existing durable work cohort twice")
    if mode == "resume" and (
        not isinstance(pending, dict) or set(pending) != set(FLEET_ROLES)
    ):
        raise RuntimeError("Fresh process lacks exactly forty pending duty requests")

    checkpoints_before = {
        role: brain.agent.revision for role, brain in supervisor.brains.items()
    }
    start = time.perf_counter()
    try:
        await supervisor.open()
        login_seconds = time.perf_counter() - start
        if not all(client.authenticated for client in supervisor.clients.values()):
            raise PermissionError("Not all forty world puppets authenticated")
        if len({client.character_dbref for client in supervisor.clients.values()}) != 40:
            raise PermissionError("Two sessions claim the same world character")

        observation_started = time.perf_counter()
        ready = []
        by_actor = {}
        for role in FLEET_ROLES:
            view = await supervisor.read_inbox(role)
            posted = list(view.select(kind="fleet_duty_posted"))
            updates = list(view.select(kind="fleet_duty_updated"))
            reports = list(view.select(kind="round_recorded"))
            if (len(posted) != 1
                    or len(updates) != (0 if mode == "begin" else 1)
                    or len(reports) != (0 if mode == "begin" else 1)):
                raise RuntimeError(f"Incomplete or duplicated private journal for {role}")
            brain = supervisor.brains[role]
            anticipated = (1 if mode == "begin" else 2)
            if brain.agent.revision != checkpoints_before[role] + anticipated:
                raise RuntimeError(f"Native checkpoint observation revision drift: {role}")
            memories = brain.agent.memories
            if not any("Private post for " + role in m for m in memories):
                raise RuntimeError("Lost an original private Concordia observation")
            if mode == "resume" and not any(
                "Private update for " + role in m for m in memories
            ):
                raise RuntimeError("World update absent from restored private memory")
            if any(
                "Private post for " + other in text
                or "Private update for " + other in text
                for other in FLEET_ROLES if other != role
                for text in memories
            ):
                raise PermissionError("Another character's private duty leaked")
            by_actor[role] = {
                "dbref": brain.character_id,
                "revision": brain.agent.revision,
                "inbox_cursor": supervisor.state["inbox_cursors"][role],
                "addressed_events": len(view),
                "pending_count": len(brain.agent.pending_requests),
            }
            ready.append(time.perf_counter() - observation_started)

        for role in FLEET_ROLES:
            original_revision = supervisor.brains[role].agent.revision
            await supervisor.read_inbox(role)
            if supervisor.brains[role].agent.revision != original_revision:
                raise RuntimeError("Replayed world evidence duplicated native memory")

        receipt_sources = {}
        if mode == "begin":
            work = {}
            requests = {}
            # Each ordinary character must observe the assigned instrument
            # from the room they actually occupy before being offered work.
            for role in FLEET_ROLES:
                station = station_for(role)
                client = supervisor.clients[role]
                await client.send_line("inspect " + station)
                reading = await client.expect_text(READOUTS[station], timeout=15)
                brain = supervisor.brains[role]
                brain.observe_local("Firsthand " + station + " inspection", reading)
                # Forty actual native Concordia choices. A safe deferral
                # remains available; the mock provider deterministically
                # takes the verified first option for CI acceptance.
                request = brain.agent.decide([
                    CommandOption(
                        "File verified " + station + " station round",
                        "round_report", "ship", {"station": station},
                    ),
                    CommandOption("Defer station report", "defer"),
                ], expected_revision=brain.agent.revision)
                if (request.verb != "round_report" or request.target != "ship"
                        or request.arguments != {"station": station}
                        or request.character_id != client.character_dbref):
                    raise RuntimeError("Model did not select its own permitted duty")
                work[role] = {
                    "role": role, "station": station,
                    "request_id": request.request_id, "status": "prepared",
                }
                requests[role] = request
                if brain.agent.usage.total_calls < 1:
                    raise RuntimeError("A fleet character never consulted its model")

            # All forty original intentions and native pending requests are
            # durable before the first world-side mutation is attempted.
            supervisor.state["pending_work"] = work
            supervisor.checkpoint()
            for role in FLEET_ROLES:
                receipt = await DurableEvenniaPort(
                    supervisor.clients[role]
                ).submit_work(requests[role])
                if receipt.status != "succeeded" or not receipt.source_event_id:
                    raise RuntimeError(f"World rejected {role}'s inspected duty round")
                receipt_sources[role] = receipt.source_event_id
                # Deliberately discard successful ACK for all 40 prepared
                # requests. They remain pending in the native checkpoints.
        else:
            for role in FLEET_ROLES:
                record = pending[role]
                verify_pending_record(role, record)
                brain = supervisor.brains[role]
                outstanding = brain.agent.pending_requests
                if record["status"] == "prepared":
                    if (len(outstanding) != 1
                            or outstanding[0].request_id != record["request_id"]
                            or outstanding[0].character_id != brain.character_id):
                        raise RuntimeError("Original model action was not checkpointed")
                elif outstanding:
                    raise RuntimeError("Reconciled native agent retained old work")
                port = DurableEvenniaPort(supervisor.clients[role])
                receipt = await port.reconcile_work(record["request_id"])
                repeated = await port.reconcile_work(record["request_id"])
                if (receipt.status != "succeeded" or not receipt.source_event_id
                        or receipt != repeated):
                    raise RuntimeError("Unresolved or changing world receipt")
                proof = await supervisor.prove_world_event(
                    role, receipt.source_event_id, kind="round_recorded",
                )
                if (proof["recipient_dbref"] != brain.character_id
                        or proof["data"].get("station") != station_for(role)):
                    raise PermissionError("World receipt source is not private station work")
                if record["status"] == "prepared":
                    brain.agent.record_outcome(receipt)
                    record["status"] = "reconciled"
                    record["source_event_id"] = receipt.source_event_id
                    supervisor.checkpoint_actor(role)
                elif record["source_event_id"] != receipt.source_event_id:
                    raise RuntimeError("Persisted receipt differs from authoritative work")
                if brain.agent.pending_requests:
                    raise RuntimeError("Settled world work still marked pending")
                receipt_sources[role] = receipt.source_event_id

        sorted_ready = sorted(ready)
        return {
            "status": "passed",
            "mode": mode,
            "scope": "forty_model_selected_world_duties_restart",
            "actors": FLEET_COUNT,
            "work_receipts": len(receipt_sources),
            "authenticated_login_seconds": round(login_seconds, 3),
            "native_restore_seconds": round(native_restore_seconds, 3),
            "first_actor_evidence_ready_seconds": round(sorted_ready[0], 3),
            "p95_actor_evidence_ready_seconds": round(sorted_ready[37], 3),
            "fleet_evidence_ready_seconds": round(sorted_ready[-1], 3),
            "receipts_reconciled_without_resubmit": mode == "resume",
            "world_round_receipt_ids": receipt_sources,
            "per_actor": by_actor,
        }
    finally:
        await supervisor.close()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("begin", "resume"):
        raise SystemExit(
            "Usage: python -m ox_ai.scenarios.p4k_fleet_recovery begin|resume"
        )
    mode = sys.argv[1]
    verdict = asyncio.run(run(mode))
    atomic_json(ROOT / "p4k" / (mode + "-verdict.json"), verdict)
    print("OX_P4L_FORTY_MODEL_SELECTED_WORLD_WORK_" + mode.upper() + "_PASS")


if __name__ == "__main__":
    main()
