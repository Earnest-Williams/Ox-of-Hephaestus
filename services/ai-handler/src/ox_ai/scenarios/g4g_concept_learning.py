"""Disposable G4g two-client lesson, restart and lost-acknowledgement probe.

This is an acceptance scenario, not an autonomous study scheduler. It knows
only its own persisted intents and the learner's addressed course observations.
The separate world-side verifier checks actual mastery and evidence afterward.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from ox_ai.ports.base import ActionRequest
from ox_ai.ports.evennia.capabilities import CapabilityPort
from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.scenarios.p3c_crew import replayable_event

STATE = Path(".ox-state/g4g-learning.json")
COURSE_ID = "mechanical.controlled_comparison.v1"


def _save(state: dict) -> None:
    """Persist the original work IDs before any request can reach the world."""
    temporary = STATE.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(state, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(STATE)


def _solve(exercise: dict) -> dict:
    """Apply the taught principle to delivered data, without a server answer key."""
    if "expected" in exercise:
        raise AssertionError("Private grading rubric leaked to the learner")
    observations = exercise["observations"]
    speed_varies = len({run["shaft_rpm"] for run in observations}) > 1
    bus_varies = len({run["drive_bus"] for run in observations}) > 1
    if speed_varies and bus_varies:
        return {"supported_factor": "insufficient_evidence", "controlled_factor": "none"}
    return {
        "supported_factor": "speed" if speed_varies else "drive_bus",
        "controlled_factor": "drive_bus" if speed_varies else "speed",
    }


async def run(stage: str) -> None:
    """Operate separately authenticated pupil and teacher across three processes."""
    if os.environ.get("OX_CONCEPT_LEARNING_CI") != "1":
        raise RuntimeError("This finite probe requires disposable CI opt-in")
    if stage not in ("begin", "finish", "recover"):
        raise ValueError("Expected begin, finish or recover")
    identities = json.loads(Path(".ox-state/p3a-ids.json").read_text())
    clients = {
        role: EvenniaWebSocketClient(
            "ws://127.0.0.1:4002",
            username,
            os.environ["OX_PROBE_PASSWORD"],
            identities[role],
        )
        for role, username in (("ari", "OxBotAri"), ("iona", "OxBotIona"))
    }
    try:
        for client in clients.values():
            for attempt in range(60):
                try:
                    await client.open()
                    break
                except OSError:
                    if attempt == 59:
                        raise
                    await asyncio.sleep(0.5)
        pupil, teacher = clients["ari"], clients["iona"]
        pupil_port, teacher_port = DurableEvenniaPort(pupil), DurableEvenniaPort(teacher)
        if stage == "begin":
            if STATE.exists():
                raise RuntimeError("Refusing to replace an existing learning intent ledger")
            state = {key: uuid.uuid4().hex for key in ("offer", "begin", "answer")}
            _save(state)
            for client in (teacher, pupil):
                here = await CapabilityPort(client).observe()
                if here.room_name != "Machine Shop":
                    await client.send_line("workshop")
                    here = await CapabilityPort(client).observe()
                assert here.room_name == "Machine Shop", here
            result = await teacher_port.submit_work(
                ActionRequest(
                    state["offer"],
                    teacher.character_dbref,
                    "lesson_offer",
                    "learning",
                    {"course_id": COURSE_ID, "learner_dbref": pupil.character_dbref},
                )
            )
            assert result.status == "succeeded", result
            offer = await replayable_event(pupil, "lesson_offered", [])
            assert offer["data"]["lesson_id"] == state["offer"]
            result = await pupil_port.submit_work(
                ActionRequest(
                    state["begin"],
                    pupil.character_dbref,
                    "lesson_begin",
                    "learning",
                    {"lesson_id": state["offer"]},
                )
            )
            assert result.status == "succeeded", result
            started = await replayable_event(pupil, "lesson_started", [])
            state["answers"] = _solve(json.loads(started["data"]["exercise"]))
            state["started_event_id"] = started["event_id"]
            _save(state)
            print("OX_G4G_STARTED", flush=True)
            return
        state = json.loads(STATE.read_text())
        assert (await pupil_port.reconcile_work(state["begin"])).status == "succeeded"
        arguments = {"lesson_id": state["offer"], **state["answers"]}
        request = ActionRequest(
            state["answer"], pupil.character_dbref, "lesson_answer", "learning", arguments
        )
        if stage == "finish":
            # The world was restarted after begin. Respect its running game clock.
            await asyncio.sleep(16)
            result = await pupil_port.submit_work(request)
            assert result.status == "succeeded", result
            # Simulate termination after the actual commit but before saving its ACK.
            # STATE still contains the original pending ID, with no claimed outcome.
            print("OX_G4G_COMMITTED_ACK_FORGOTTEN", flush=True)
            return
        recovered = await pupil_port.reconcile_work(state["answer"])
        assert recovered.status == "succeeded", recovered
        replay = await pupil_port.submit_work(request)
        assert replay == recovered
        refused = await pupil_port.submit_work(
            ActionRequest(
                uuid.uuid4().hex,
                pupil.character_dbref,
                "lesson_answer",
                "learning",
                arguments,
            )
        )
        assert refused.status == "failed", refused
        assert (await teacher_port.reconcile_work(state["answer"])).status == "unknown"
        result = await replayable_event(pupil, "lesson_assessed", [])
        assert result["data"]["result"] == "passed"
        print("OX_G4G_RECOVERED_ONCE", flush=True)
    finally:
        for client in clients.values():
            await client.close()


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1]))
