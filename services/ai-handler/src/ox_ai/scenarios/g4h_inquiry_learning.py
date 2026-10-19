"""Disposable authenticated investigation, reflection and lost-ACK acceptance probe.

Only the investigator's own observations supply the case, reading and exercise.
This finite scenario is not an autonomous study policy or a diagnosis oracle.
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

STATE = Path(".ox-state/g4h-learning.json")


def _save(state: dict) -> None:
    """Save original intended work identities before delivering any command."""
    temporary = STATE.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(state, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(STATE)


def _solve(data: dict) -> dict:
    """Interpret the delivered fallible reading and fresh source-count example."""
    exercise = json.loads(data["transfer_exercise"])
    assert "expected" not in exercise and "cause" not in data
    return {
        "interpretation": (
            "supported_unconfirmed" if data["reading"] == "supports" else "unsupported_not_excluded"
        ),
        "independent_sources": (
            "one_source"
            if len({row["source_id"] for row in exercise["reports"]}) == 1
            else "two_sources"
        ),
    }


async def run(stage: str) -> None:
    """Run three independent client processes around an actual world restart."""
    if os.environ.get("OX_INQUIRY_LEARNING_CI") != "1":
        raise RuntimeError("This finite probe requires disposable CI opt-in")
    if stage not in ("begin", "finish", "recover"):
        raise ValueError("Expected begin, finish or recover")
    identities = json.loads(Path(".ox-state/p3a-ids.json").read_text())
    clients = {
        role: EvenniaWebSocketClient(
            "ws://127.0.0.1:4002", username, os.environ["OX_PROBE_PASSWORD"], identities[role]
        )
        for role, username in (("ari", "OxBotAri"), ("lin", "OxBotLin"))
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
        investigator, observer = clients["ari"], clients["lin"]
        port, observer_port = DurableEvenniaPort(investigator), DurableEvenniaPort(observer)
        assert (await CapabilityPort(investigator).observe()).room_name == "Engineering"
        if stage == "begin":
            if STATE.exists():
                raise RuntimeError("Refusing to replace an existing investigative intent ledger")
            notice = await replayable_event(investigator, "anomaly_notice", [])
            state = {
                "case_id": notice["data"]["case_id"],
                "ids": {
                    key: uuid.uuid4().hex
                    for key in (
                        "anomaly_report",
                        "anomaly_question",
                        "inquiry_predict",
                        "anomaly_probe_report",
                        "inquiry_review",
                        "inquiry_reflect",
                        "repeat",
                    )
                },
            }
            _save(state)
            await investigator.send_line("oxsample " + state["case_id"])
            await replayable_event(investigator, "anomaly_sampled", [])
            for operation in ("anomaly_report", "anomaly_question", "inquiry_predict"):
                args = {"case_id": state["case_id"]}
                if operation == "inquiry_predict":
                    args["prediction"] = "does_not_support"
                outcome = await port.submit_work(
                    ActionRequest(
                        state["ids"][operation],
                        investigator.character_dbref,
                        operation,
                        "learning" if operation.startswith("inquiry_") else "ship",
                        args,
                    )
                )
                assert outcome.status == "succeeded", outcome
            await investigator.send_line("oxprobe " + state["case_id"])
            sample = await replayable_event(investigator, "anomaly_probe_sampled", [])
            for operation, target in (
                ("anomaly_probe_report", "ship"),
                ("inquiry_review", "learning"),
            ):
                outcome = await port.submit_work(
                    ActionRequest(
                        state["ids"][operation],
                        investigator.character_dbref,
                        operation,
                        target,
                        {"case_id": state["case_id"]},
                    )
                )
                assert outcome.status == "succeeded", outcome
            review = await replayable_event(investigator, "inquiry_review_ready", [])
            assert review["data"]["sample_event_id"] == sample["event_id"]
            state["answers"] = _solve(review["data"])
            _save(state)
            print("OX_G4H_PERSONAL_EVIDENCE_REVIEWED", flush=True)
            return
        state = json.loads(STATE.read_text())
        assert (await port.reconcile_work(state["ids"]["inquiry_review"])).status == "succeeded"
        arguments = {"case_id": state["case_id"], **state["answers"]}
        request = ActionRequest(
            state["ids"]["inquiry_reflect"],
            investigator.character_dbref,
            "inquiry_reflect",
            "learning",
            arguments,
        )
        if stage == "finish":
            # The world-owned clock must accrue at least five game minutes.
            await asyncio.sleep(6)
            outcome = await port.submit_work(request)
            assert outcome.status == "succeeded", outcome
            # Deliberately omit the committed ACK from the persisted intent ledger.
            print("OX_G4H_COMMITTED_ACK_FORGOTTEN", flush=True)
            return
        recovered = await port.reconcile_work(request.request_id)
        assert recovered.status == "succeeded", recovered
        assert await port.submit_work(request) == recovered
        repeated = await port.submit_work(
            ActionRequest(
                state["ids"]["repeat"],
                investigator.character_dbref,
                "inquiry_reflect",
                "learning",
                arguments,
            )
        )
        assert repeated.status == "failed", repeated
        assert (await observer_port.reconcile_work(request.request_id)).status == "unknown"
        reflected = await replayable_event(investigator, "inquiry_reflected", [])
        assert reflected["data"]["result"] == "passed"
        print("OX_G4H_RECOVERED_ONCE_WITHOUT_FOREIGN_RECEIPT", flush=True)
    finally:
        for client in clients.values():
            await client.close()


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1]))
