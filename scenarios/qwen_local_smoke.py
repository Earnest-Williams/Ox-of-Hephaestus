"""One real-model proposal through Ox's native Concordia entity.

No Evennia process or world port is created. A model can propose one finite-
menu action, but nothing in this probe can execute that action.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity
from ox_ai.ports.base import WorldObservation


MODEL_ID = "qwen3.5-0.8b"


def run_probe(model) -> dict:
    """Exercise native Concordia against actor-scoped synthetic evidence."""
    agent = CrewAgent(
        CrewIdentity(
            agent_id="ox.qwen.probe.ari",
            character_id="#801",
            name="Ari Sen",
            duty="Investigate a cooling system anomaly before requesting physical work.",
            goal="Preserve the ship and obtain verified evidence.",
        ),
        model,
    )
    assert agent.observe(WorldObservation(
        observation_id="qwen-probe-obs-1",
        character_id="#801",
        game_time=120.0,
        text="Local P-01 pressure readout is below nominal. "
             "No repair has been attempted or confirmed.",
        source_event_id="qwen-probe-world-1",
    ))
    options = (
        CommandOption("Inspect the P-01 pressure gauge", "inspect", "gauge"),
        CommandOption("Defer action and request another report", "defer"),
    )
    start = time.perf_counter()
    request = agent.decide(options, expected_revision=1)
    duration = time.perf_counter() - start
    if not any(
        request.verb == opt.verb and request.target == opt.target
        for opt in options
    ):
        raise AssertionError("Concordia proposed a command outside the finite menu")
    if request.character_id != "#801" or request.agent_revision != 1:
        raise AssertionError("Proposal lost its character identity or observation revision")
    if agent.usage.total_calls != 1:
        raise AssertionError("Expected exactly one inference request")
    if len(agent.pending_requests) != 1 or agent.pending_requests[0] != request:
        raise AssertionError("Unconfirmed proposal not retained as pending")
    # No WorldPort is constructed or called; this is not a world receipt.
    return {
        "experiment": "qwen3.5_0.8b_cpu_proposal",
        "model": MODEL_ID,
        "native_concordia": True,
        "character_id": request.character_id,
        "observation_revision": request.agent_revision,
        "choice_verb": request.verb,
        "choice_target": request.target,
        "inference_calls": agent.usage.total_calls,
        "pending_requests": len(agent.pending_requests),
        "world_commands_sent": 0,
        "world_receipts_received": 0,
        "world_state_verified": False,
        "inference_latency_seconds": round(duration, 4),
        "scope": "one synthetic character, not a live-world repair",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    endpoint = urlsplit(args.api_base)
    if endpoint.scheme != "http" or endpoint.hostname not in ("127.0.0.1", "localhost"):
        parser.error("--api-base must point to localhost over HTTP")

    from ox_ai.inference.compatible_chat import CompatibleChatModel
    model = CompatibleChatModel(
        MODEL_ID, api_key="local-no-secret", api_base=args.api_base,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = run_probe(model)
    except Exception as exc:
        args.output.write_text(json.dumps({
            "experiment": "qwen3.5_0.8b_cpu_proposal",
            "status": "failed",
            "exception": type(exc).__name__,
            "detail": str(exc)[:240],
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise
    args.output.write_text(
        json.dumps({"status": "passed", **report}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "passed", **report}, sort_keys=True))


if __name__ == "__main__":
    main()
