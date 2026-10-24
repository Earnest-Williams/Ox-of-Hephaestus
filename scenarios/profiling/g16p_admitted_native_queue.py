"""G16p: current-host calibration, forty admitted native choices, overload retry.

All actors and histories are synthetic, every command remains unexecuted.
The old 25-second burst gate is unchanged. This tests a separately registered
asynchronous queue with explicit queue/service limits and actual 40/40 work.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from g16f_personality_throughput import EngineMeter, make_actor
from g16m_native_queue_burst import native_engine
from g16o_binary_capacity import MENU_KEY, BinaryFixture, host_metadata, sample_batch
from ox_ai.agents.crew import CommandOption
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.runtime.capacity_scheduler import (
    CapacityAwareDecisionScheduler,
    CognitionAdmissionRefused,
    MeasuredServiceCapacity,
)
from ox_ai.runtime.personality_choice_ledger import deterministic_proposal_id
from ox_ai.runtime.personality_routing import PersonalState
from ox_contracts import load_catalog


async def run(
    engine_name: str, *, gguf_path: Path | None = None, manifest: Path | None = None
) -> dict:
    """Freeze a measured service bound before starting the forty-person queue."""
    native = engine_name == "decider-q4"
    if native:
        if gguf_path is None or manifest is None:
            raise FileNotFoundError("Pinned real GGUF and manifest required")
        engine, provenance = native_engine(gguf_path, manifest)
    elif engine_name == "fixture":
        engine, provenance = BinaryFixture(), {"synthetic_fixture": True}
    else:
        raise ValueError("Explicit fixture or decider-q4 backend required")
    meter = EngineMeter(engine)
    host = host_metadata()
    root = Path(__file__).resolve().parents[2]
    for path in (
        "services/ai-handler/src/ox_ai/runtime/capacity_scheduler.py",
        "scenarios/profiling/g16p_admitted_native_queue.py",
    ):
        host["source_file_sha256"][path] = hashlib.sha256((root / path).read_bytes()).hexdigest()
    host["source_git_commit"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    previous_flag = os.environ.get("OX_PERSONALITY_CHOICE")
    os.environ["OX_PERSONALITY_CHOICE"] = "1"
    try:
        calibration = await sample_batch(6, pattern="sequential", meter=meter, timeout_seconds=120)
        if calibration["proposals_adopted"] != 6:
            raise RuntimeError("Current-host calibration was censored; no usable capacity")
        observations = [r["elapsed_seconds"] for r in calibration["actor_results"]]
        capacity = MeasuredServiceCapacity.from_samples(
            observations if native else [1.0] * 6,
            native_units=2,
        )
        print("OX_G16P_CAPACITY_FROZEN", asdict(capacity), flush=True)
        scheduler = CapacityAwareDecisionScheduler(
            capacity,
            max_pending=40,
            queue_timeout_seconds=3600,
            per_actor_budget=2,
            total_budget=82,
            budget_window_seconds=86400,
        )
        menu = load_catalog().menu(MENU_KEY)
        options = tuple(
            CommandOption("Act: " + a.semantic_key, a.verb, a.target) for a in menu.options
        )
        planner = GoapPlanner(
            tuple(GoapAction(a.semantic_key, verb=a.verb, target=a.target) for a in menu.options)
        )
        state = PersonalState(stress=0.35, social_pressure=0.65, fatigue=0.2, uncertainty=0.4)
        heartbeats = []
        stop = asyncio.Event()

        async def heartbeat():
            while not stop.is_set():
                heartbeats.append(time.perf_counter())
                try:
                    await asyncio.wait_for(stop.wait(), 0.02)
                except asyncio.TimeoutError:
                    pass

        rows = []
        with tempfile.TemporaryDirectory(prefix="ox-g16p-") as tmp:
            actors = [
                make_actor(
                    i, scheduler=scheduler, engine=meter, path=Path(tmp), state=state, menu=menu
                )
                for i in range(41)
            ]

            async def choose(actor, *, overload=False):
                began = time.perf_counter()
                try:
                    result = await actor.controller.decide(
                        agent=actor.brain,
                        planner=planner,
                        beliefs=frozenset(),
                        goals=frozenset({"reviewed"}),
                        options=options,
                        boundary_id=actor.boundary,
                        kind="social",
                        state=state,
                        persist=actor.persist,
                        menu_key=MENU_KEY,
                    )
                except Exception as error:
                    # Only class names are retained; never provider prompt/error text.
                    return {
                        "role": actor.role,
                        "status": type(error).__name__,
                        "elapsed_seconds": time.perf_counter() - began,
                    }
                saved = actor.router.record["personality_choices"][actor.boundary]
                if (
                    result.model_calls != 2
                    or result.route.selected != "llm"
                    or result.action.request_id != saved["request_id"]
                    or saved["choice"]["underlying_native_calls"] != 2
                    or saved["choice"]["policy_version"] != 2
                    or result.action not in actor.brain.pending_requests
                ):
                    raise AssertionError("Unbound or non-native binary adoption")
                row = {
                    "role": actor.role,
                    "status": "adopted_unexecuted",
                    "request_id": result.action.request_id,
                    "prompt_sha256": saved["choice"]["prompt_sha256"],
                    "elapsed_seconds": time.perf_counter() - began,
                }
                if not overload:
                    print(
                        "OX_G16P_QUEUE_COMPLETED",
                        actor.role,
                        round(row["elapsed_seconds"], 3),
                        flush=True,
                    )
                return row

            before = meter.calls
            began = time.perf_counter()
            pulse = asyncio.create_task(heartbeat())
            tasks = [asyncio.create_task(choose(a)) for a in actors[:40]]
            excess = actors[40]
            # All forty admissions reach their first await before this task;
            # a 41st request must be refused without joining the provider queue.
            overflow_task = asyncio.create_task(choose(excess, overload=True))
            try:
                rows = await asyncio.gather(*tasks)
                overflow = await overflow_task
                await asyncio.wait_for(scheduler.drain(), 180)
                batch_seconds = time.perf_counter() - began
                batch_calls = meter.calls - before
                metrics_before_retry = scheduler.metrics
                rejected_route = excess.router.record["boundaries"][excess.boundary]
                original_id = deterministic_proposal_id(excess.router, excess.boundary)
                rejection_verified = (
                    overflow["status"] == CognitionAdmissionRefused.__name__
                    and rejected_route["selected"] == "llm"
                    and excess.role not in metrics_before_retry["per_actor_started"]
                    and not excess.brain.pending_requests
                    and "personality_choices" not in excess.router.record
                    and len(excess.writes) == 1
                )
                retry = await choose(excess, overload=True) if rejection_verified else None
                await asyncio.wait_for(scheduler.drain(), 180)
            finally:
                stop.set()
                await pulse
            for actor in actors[:40]:
                if (len(actor.brain.pending_requests) != 1 or len(actor.writes) != 2) and all(
                    r["status"] == "adopted_unexecuted" for r in rows
                ):
                    raise AssertionError(
                        "Accepted actor lost its unique pending proposal/checkpoint"
                    )
            for actor in actors:
                if json.loads(actor.router_path.read_text()) != actor.router.record:
                    raise AssertionError("Durable router differs from its actual checkpoint")
            completed = sum(r["status"] == "adopted_unexecuted" for r in rows)
            metrics = scheduler.metrics
            admission = metrics["capacity_admission"]
            telemetry = metrics["queue_observability"]
            accepted = (
                completed == 40
                and batch_calls == 80
                and rejection_verified
                and retry is not None
                and retry["status"] == "adopted_unexecuted"
                and retry["request_id"] == original_id
                and metrics["started"] == 82
                and meter.calls == 94
                and telemetry["proposals_adopted"] == 41
                and telemetry["inference_invocations_finished"] == 41
                and telemetry["maximum_simultaneous_inference_invocations"] == 1
                and not admission["pending_roles"]
                and not admission["draining_roles"]
                and not admission["reserved_unbilled_units"]
                and not admission["profile_failed"]
                and admission["maximum_pending"] == 40
                and admission["refused_full"] == 1
                and not admission["expired_in_queue"]
                and not admission["provider_overruns"]
                and meter.peak_active == 1
                and len(heartbeats) > 1
            )
        for name, expected in host["source_file_sha256"].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
                raise PermissionError("Source changed during the registered measurement")
        return {
            "schema": 1,
            "experiment": "g16p_measured_bounded_admission",
            "backend": engine_name,
            "native_model_verified": native,
            "model_provenance": provenance,
            "host": host,
            "capacity_profile_source": (
                "current_process_native_samples" if native else "explicit_synthetic_fixture"
            ),
            "capacity": asdict(capacity),
            "calibration": calibration,
            "cohort_size": 40,
            "completed_unexecuted_proposals": completed,
            "batch_elapsed_seconds": batch_seconds,
            "batch_forward_calls": batch_calls,
            "actor_results": rows,
            "overflow": overflow,
            "overflow_refusal_verified": rejection_verified,
            "retry": retry,
            "metrics_before_retry": metrics_before_retry,
            "metrics": metrics,
            "heartbeat_samples": len(heartbeats),
            "maximum_observed_heartbeat_gap_seconds": max(
                (b - a for a, b in zip(heartbeats, heartbeats[1:])), default=0
            ),
            "actual_native_forward_calls": meter.calls if native else 0,
            "synthetic_fixture_forward_calls": 0 if native else meter.calls,
            "forward_elapsed_seconds": list(meter.latencies_seconds),
            "bounded_queue_acceptance": bool(accepted),
            "original_25_second_burst_gate_retested": False,
            "world_commands_sent": 0,
            "world_receipts_claimed": 0,
            "production_activation_accepted": False,
        }
    finally:
        if previous_flag is None:
            os.environ.pop("OX_PERSONALITY_CHOICE", None)
        else:
            os.environ["OX_PERSONALITY_CHOICE"] = previous_flag


def main():
    """Record truthful outcomes even if bounded admission acceptance fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, choices=("fixture", "decider-q4"))
    parser.add_argument("--gguf-path", type=Path)
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args.engine, gguf_path=args.gguf_path, manifest=args.model_manifest))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("OX_G16P_BOUNDED_QUEUE_RECORDED", result["bounded_queue_acceptance"], flush=True)
    if not result["bounded_queue_acceptance"]:
        raise SystemExit(
            "Bounded queue acceptance failed; retained measurements remain authoritative"
        )


if __name__ == "__main__":
    main()
