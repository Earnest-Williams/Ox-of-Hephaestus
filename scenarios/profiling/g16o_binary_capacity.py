"""G16o per-host binary service measurements and real queued bursts.

Uses actual Concordia minds with explicitly synthetic private backgrounds,
the existing offline gauge menu, and the durable binary controller. Every
proposal is inert. Fixture timings never become native capacity evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import asyncio
import json
import math
import os
import platform
import statistics
import tempfile
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from g16f_personality_throughput import EngineMeter, make_actor, percentile
from g16m_native_queue_burst import native_engine
from ox_ai.agents.crew import CommandOption
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.runtime.cognition_scheduler import CognitionTimedOut, DecisionScheduler
from ox_ai.runtime.personality_routing import PersonalState
from ox_contracts import load_catalog

MENU_KEY = "offline.personality_gauge"
BURSTS = (6, 20, 40)
DEADLINE = 25.0


class BinaryFixture:
    """Synthetic scores only; deliberately has no native performance meaning."""

    def system_one(self, prompt, questions):
        criteria = questions["next_action"]["criteria"]
        codes = tuple(criteria)
        if len(codes) != 2:
            raise AssertionError("Capacity fixture requires exactly two choices")
        return {
            "answers": {
                "next_action": {
                    "choice": codes[0],
                    "probabilities": {codes[0]: 0.6, codes[1]: 0.4},
                }
            }
        }


def host_metadata() -> dict:
    """Record the measured process environment, without machine credentials."""
    cpu = "unknown"
    if Path("/proc/cpuinfo").is_file():
        cpu = next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            cpu,
        )
    root = Path(__file__).resolve().parents[2]
    source_paths = [
        "scenarios/profiling/g16o_binary_capacity.py",
        "scenarios/profiling/g16f_personality_throughput.py",
        "scenarios/profiling/g16m_native_queue_burst.py",
        "services/ai-handler/src/ox_ai/agents/crew.py",
        "services/ai-handler/src/ox_ai/inference/decider_gguf_choice.py",
        "services/ai-handler/src/ox_ai/inference/position_balanced_choice.py",
        "services/ai-handler/src/ox_ai/inference/disposition_choice.py",
        "services/ai-handler/src/ox_ai/runtime/g16_decision_controller.py",
        "services/ai-handler/src/ox_ai/runtime/personality_choice_ledger.py",
        "services/ai-handler/src/ox_ai/runtime/cognition_scheduler.py",
        "contracts/ox_contracts/data/personality_action_tags.v1.json",
    ]
    source_hashes = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_paths
    }
    packages = {}
    for name in ("gdm-concordia", "decider-ai", "llama-cpp-python", "transformers", "torch"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {
        "source_file_sha256": source_hashes,
        "packages": packages,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_model": cpu,
        "cgroup_cpu_max": (
            Path("/sys/fs/cgroup/cpu.max").read_text().strip()
            if Path("/sys/fs/cgroup/cpu.max").is_file()
            else None
        ),
        "logical_cpus": os.cpu_count(),
        "cpu_affinity": (
            sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
        ),
        "concordia": version("gdm-concordia"),
        "native_threads": 2,
        "native_concurrency": 1,
        "runner_sample": os.environ.get("G16O_RUNNER_SAMPLE", "local"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "source_sha": os.environ.get("GITHUB_SHA"),
    }


async def sample_batch(
    size: int, *, pattern: str, meter: EngineMeter, timeout_seconds: float
) -> dict:
    """Measure one shared worker, then prove all late work has drained."""
    if (
        type(size) is not int
        or size not in BURSTS
        or pattern not in ("sequential", "burst")
        or (pattern == "sequential" and size != 6)
    ):
        raise ValueError("Only six sequential samples and 6/20/40 bursts are registered")
    menu = load_catalog().menu(MENU_KEY)
    if menu.scope != "offline_trial" or menu.safety_critical or len(menu.options) != 2:
        raise PermissionError("Expected the unchanged two-action offline gauge catalog")
    options = tuple(CommandOption("Act: " + a.semantic_key, a.verb, a.target) for a in menu.options)
    planner = GoapPlanner(
        tuple(GoapAction(a.semantic_key, verb=a.verb, target=a.target) for a in menu.options)
    )
    state = PersonalState(stress=0.35, social_pressure=0.65, fatigue=0.2, uncertainty=0.4)
    scheduler = DecisionScheduler(
        max_parallel=1, timeout_seconds=timeout_seconds, per_actor_budget=2, total_budget=size * 2
    )
    before = meter.calls
    rows = []
    with tempfile.TemporaryDirectory(prefix="ox-g16o-") as tmp:
        actors = [
            make_actor(i, scheduler=scheduler, engine=meter, path=Path(tmp), state=state, menu=menu)
            for i in range(size)
        ]

        async def one(actor):
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
            except CognitionTimedOut:
                accepted = False
            else:
                saved = actor.router.record["personality_choices"][actor.boundary]
                if (
                    result.model_calls != 2
                    or result.route.selected != "llm"
                    or saved["choice"]["policy_version"] != 2
                    or saved["choice"]["underlying_native_calls"] != 2
                    or saved["request_id"] != result.action.request_id
                    or result.action not in actor.brain.pending_requests
                ):
                    raise AssertionError("Binary proposal lost its durable actor binding")
                accepted = True
            rows.append(
                {
                    "role": actor.role,
                    "adopted_unexecuted_proposal": accepted,
                    "elapsed_seconds": time.perf_counter() - began,
                }
            )

        began = time.perf_counter()
        if pattern == "sequential":
            for actor in actors:
                await one(actor)
        else:
            await asyncio.gather(*(one(actor) for actor in actors))
        callers_elapsed = time.perf_counter() - began
        drain_start = time.perf_counter()
        while scheduler.metrics["inflight_roles"]:
            if time.perf_counter() - drain_start > 180:
                raise TimeoutError("Native binary worker did not drain")
            await asyncio.sleep(0.025)
        drain_elapsed = time.perf_counter() - drain_start
        metrics = scheduler.metrics
        telemetry = metrics["queue_observability"]
        by_role = {row["role"]: row for row in rows}
        accepted = sum(row["adopted_unexecuted_proposal"] for row in rows)
        for actor in actors:
            recorded = json.loads(actor.router_path.read_text())
            ok = by_role[actor.role]["adopted_unexecuted_proposal"]
            if (
                recorded != actor.router.record
                or len(actor.writes) != (2 if ok else 1)
                or len(actor.brain.pending_requests) != int(ok)
                or (actor.boundary in recorded.get("personality_choices", {})) != ok
            ):
                raise PermissionError("Late worker changed a live actor or durable choice")
        if (
            len(rows) != size
            or metrics["started"] != size * 2
            or telemetry["proposals_adopted"] != accepted
            or telemetry["inference_invocations_started"]
            != telemetry["inference_invocations_finished"]
            or 2 * telemetry["inference_invocations_finished"] != meter.calls - before
            or telemetry["inference_failed"]
            or telemetry["stale_proposals_rejected"]
            or telemetry["maximum_simultaneous_inference_invocations"] != 1
            or metrics["timed_out_or_cancelled_roles"]
        ):
            raise AssertionError("Binary scheduler accounting or containment failed")
    return {
        "actors": size,
        "pattern": pattern,
        "deadline_seconds": timeout_seconds,
        "proposals_adopted": accepted,
        "timed_out_no_proposal": size - accepted,
        "underlying_forward_calls": meter.calls - before,
        "callers_wall_seconds": callers_elapsed,
        "worker_drain_seconds": drain_elapsed,
        "telemetry": telemetry,
        "actor_results": sorted(rows, key=lambda r: r["role"]),
        "world_commands_sent": 0,
        "world_receipts_claimed": 0,
    }


def capacity_observation(sequential: dict, *, native: bool) -> dict:
    """A conservative sample-based planning estimate, never a runtime grant."""
    if not native or sequential["proposals_adopted"] != 6:
        return {
            "status": "not_established",
            "reason": "native complete six-sample baseline required",
        }
    values = [r["elapsed_seconds"] for r in sequential["actor_results"]]
    high = max(values)
    planning_service = high * 1.25
    return {
        "status": "observed_sample_only",
        "sample_count": len(values),
        "median_seconds": statistics.median(values),
        "sample_p95_seconds": percentile(values, 0.95),
        "maximum_seconds": high,
        "planning_service_seconds_including_25_percent_headroom": planning_service,
        "estimated_serial_completions_in_25_seconds": math.floor(DEADLINE / planning_service),
        "guaranteed_completions": None,
        "changes_runtime_configuration": False,
        "production_activation_accepted": False,
    }


async def run(
    engine_name: str, *, gguf_path: Path | None = None, manifest: Path | None = None
) -> dict:
    """Require exact pinned real bytes for native claims; never auto-enable."""
    if engine_name == "decider-q4":
        if gguf_path is None or manifest is None:
            raise FileNotFoundError("Pinned GGUF and provenance manifest required")
        engine, provenance = native_engine(gguf_path, manifest)
    elif engine_name == "fixture":
        engine, provenance = BinaryFixture(), {"synthetic_fixture": True}
    else:
        raise ValueError("Select fixture or genuine decider-q4 explicitly")
    meter = EngineMeter(engine)
    # Deliberately scoped to this offline measurement process.
    previous_flag = os.environ.get("OX_PERSONALITY_CHOICE")
    os.environ["OX_PERSONALITY_CHOICE"] = "1"
    try:
        baseline = await sample_batch(6, pattern="sequential", meter=meter, timeout_seconds=120)
        if engine_name == "decider-q4":
            print(
                "OX_G16O_SEQUENTIAL_RECORDED",
                baseline["proposals_adopted"],
                [round(r["elapsed_seconds"], 3) for r in baseline["actor_results"]],
                flush=True,
            )
        bursts = []
        for size in BURSTS:
            batch = await sample_batch(size, pattern="burst", meter=meter, timeout_seconds=DEADLINE)
            bursts.append(batch)
            if engine_name == "decider-q4":
                print(
                    "OX_G16O_BURST_RECORDED",
                    size,
                    batch["proposals_adopted"],
                    batch["timed_out_no_proposal"],
                    flush=True,
                )
    finally:
        if previous_flag is None:
            os.environ.pop("OX_PERSONALITY_CHOICE", None)
        else:
            os.environ["OX_PERSONALITY_CHOICE"] = previous_flag
    native = engine_name == "decider-q4"
    return {
        "schema": 1,
        "experiment": "g16o_binary_host_capacity",
        "backend": engine_name,
        "native_model_verified": native,
        "model_provenance": provenance,
        "host": host_metadata(),
        "actor_history": "synthetic per-actor memories; not authenticated G9 histories",
        "menu_key": MENU_KEY,
        "binary_policy_version": 2,
        "baseline": baseline,
        "bursts": bursts,
        "capacity_observation": capacity_observation(baseline, native=native),
        "forward_elapsed_seconds": list(meter.latencies_seconds),
        "actual_native_forward_calls": meter.calls if native else 0,
        "synthetic_fixture_forward_calls": 0 if native else meter.calls,
        "maximum_simultaneous_native_forwards": meter.peak_active if native else None,
        "world_commands_sent": 0,
        "world_receipts_claimed": 0,
        "production_activation_accepted": False,
    }


def main() -> None:
    """Write a reproducible local or CI sample without changing live policy."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, choices=("fixture", "decider-q4"))
    parser.add_argument("--gguf-path", type=Path)
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = asyncio.run(run(args.engine, gguf_path=args.gguf_path, manifest=args.model_manifest))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("OX_G16O_BINARY_CAPACITY_OBSERVATION_RECORDED", args.engine)


if __name__ == "__main__":
    main()
