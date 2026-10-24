"""G16m genuine 6/20/40 simultaneous G16c three-pass scheduling trial.

Unlike G16i's deterministic QUEUE MODEL this sends concurrently arriving
separate Concordia actors to the actual configured G16c DecisionScheduler.
Native mode verifies the exact original Decider 4B Q4_K_M SHA256 and makes
real CPU GGUF forwards behind ONE shared worker (never thread-unsafe
parallel scoring). It records true on-time adoption versus timeouts and
waits for abandoned native workers to drain before reporting.

All commands are hypothetical, remain unexecuted, and never touch Evennia.
The full real-world 40-actor supervisor/permission soak remains another gate.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import tempfile
import time

from ox_ai.agents.crew import CommandOption
from ox_ai.inference.decider_gguf_choice import DeciderGGUFChoiceModel
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.runtime.cognition_scheduler import (
    CognitionTimedOut, DecisionScheduler,
)
from ox_ai.runtime.personality_routing import PersonalState
from ox_contracts import load_catalog

from g16f_personality_throughput import (
    COHORTS, MENU_KEY, MODEL_REVISIONS, FakeSystemOne, EngineMeter,
    make_actor, percentile,
)

PINNED_GGUF_SHA = "c03deb433d539ef49579fca5a015d5090c739a331448493aded7a57ad9b4261b"
NATIVE_DEADLINE = 25.0


def native_engine(gguf_path: Path, manifest: Path):
    if not gguf_path.is_file() or not manifest.is_file():
        raise FileNotFoundError("G16m requires original pinned native model and manifest")
    meta = json.loads(manifest.read_text(encoding="utf-8"))
    if (meta.get("model") != "decider-q4"
            or (meta.get("hf_revision"),
                meta.get("tokenizer_revision")) != MODEL_REVISIONS
            or meta.get("size") != gguf_path.stat().st_size
            or meta.get("sha256") != PINNED_GGUF_SHA):
        raise PermissionError("Not the original Decider Q4 model and publisher tokenizer")
    sha = hashlib.sha256()
    with gguf_path.open("rb") as handle:
        while part := handle.read(8 * 1024 * 1024):
            sha.update(part)
    if sha.hexdigest() != PINNED_GGUF_SHA:
        raise PermissionError("Wrong real GGUF bytes")
    return DeciderGGUFChoiceModel(
        gguf_path, ("accept_help", "work_alone", "reschedule"),
        n_threads=2,
    ).engine, meta


async def run_cohort(
    size: int, *, meter: EngineMeter, timeout_seconds: float,
    native: bool,
) -> dict:
    if size not in COHORTS:
        raise ValueError("G16m only accepts 6, 20, 40 separate character cohorts")
    if not 0 < timeout_seconds <= 120:
        raise ValueError("Invalid per-character wall deadline")
    catalog = load_catalog()
    menu = catalog.menu(MENU_KEY)
    if menu.scope != "hypothetical" or menu.safety_critical or len(menu.options) != 3:
        raise PermissionError("Native burst benchmark requires the unchanged tagged G16a menu")
    offered = tuple(
        CommandOption("Act: " + item.semantic_key, item.verb, item.target)
        for item in menu.options
    )
    planner = GoapPlanner(tuple(
        GoapAction(
            item.semantic_key, requires=frozenset({"notes_active"}),
            adds=frozenset({"decision"}),
            verb=item.verb, target=item.target,
        ) for item in menu.options
    ))
    state = PersonalState(
        stress=.35, social_pressure=.65, fatigue=.20, uncertainty=.4,
    )
    scheduler = DecisionScheduler(
        max_parallel=1, per_actor_budget=3,
        total_budget=size * 3, timeout_seconds=timeout_seconds,
    )
    before = meter.calls
    started_by_actor: dict[str, float] = {}
    completed: dict[str, dict] = {}
    timed_out: dict[str, float] = {}

    with tempfile.TemporaryDirectory(prefix="ox-g16m-") as folder:
        actors = [
            make_actor(i, scheduler=scheduler, engine=meter,
                       path=Path(folder), state=state, menu=menu)
            for i in range(size)
        ]

        async def deliberate(actor):
            start = time.perf_counter()
            started_by_actor[actor.role] = start
            try:
                proposal = await actor.controller.decide(
                    agent=actor.brain, planner=planner,
                    beliefs=frozenset({"notes_active"}),
                    goals=frozenset({"decision"}),
                    options=offered, boundary_id=actor.boundary,
                    kind="social", state=state,
                    menu_key=MENU_KEY, persist=actor.persist,
                )
            except CognitionTimedOut:
                timed_out[actor.role] = time.perf_counter() - start
            else:
                entry = actor.router.record["personality_choices"][actor.boundary]
                if (proposal.route.selected != "llm"
                        or proposal.model_calls != 3
                        or entry["request_id"] != proposal.action.request_id
                        or entry["choice"]["underlying_native_calls"] != 3
                        or proposal.action not in actor.brain.pending_requests):
                    raise AssertionError("Adopted actor action lacked authentic bound G16c ledger")
                completed[actor.role] = {
                    "elapsed_seconds": time.perf_counter() - start,
                    "request_id": proposal.action.request_id,
                    "semantic_key": entry["selected_semantic_key"],
                }

        began = time.perf_counter()
        tasks = [asyncio.create_task(deliberate(a)) for a in actors]
        # One event-loop scheduling turn means these are offered as one burst,
        # not forty serial model invocations.
        await asyncio.gather(*tasks)
        caller_elapsed = time.perf_counter() - began
        caller_metrics = scheduler.metrics
        # A thread in asyncio.to_thread cannot be cancelled by a timed-out
        # caller. It must fully exit before a benchmark process is allowed
        # to report a finished native workload.
        drain_start = time.perf_counter()
        while scheduler.metrics["inflight_roles"]:
            if time.perf_counter() - drain_start > 180:
                raise TimeoutError("Native provider did not drain its orphaned inference")
            await asyncio.sleep(.025)
        drain_seconds = time.perf_counter() - drain_start
        observed = scheduler.metrics
        telemetry = observed["queue_observability"]
        if (len(started_by_actor) != size
                or len(completed) + len(timed_out) != size
                or set(completed).intersection(timed_out)
                or observed["started"] != size * 3
                or observed["inflight_roles"]
                or observed["timed_out_or_cancelled_roles"]
                or telemetry["requests_accepted_for_scheduling"] != size
                or telemetry["inference_invocations_started"]
                    != telemetry["inference_invocations_finished"]
                or telemetry["proposals_adopted"] != len(completed)
                or telemetry["inference_invocations_started"] * 3
                    != meter.calls - before
                or telemetry["inference_failed"]
                or telemetry["stale_proposals_rejected"]
                or telemetry["cancelled"]
                or telemetry["waiting_for_inference_slot"]
                or telemetry["provider_active_roles"]
                or telemetry["maximum_simultaneous_inference_invocations"] != 1
                or telemetry["provider_finished_after_abandonment"]
                    > len(timed_out)):
            raise AssertionError("Native burst observation or worker containment broken")

        # A native late answer cannot appear in either the original actor
        # pending requests or a checkpoint-backed personality decision.
        for actor in actors:
            recorded = json.loads(actor.router_path.read_text(encoding="utf-8"))
            if recorded != actor.router.record or not actor.writes:
                raise AssertionError("Original actor's routing checkpoint not durable")
            if actor.role in completed:
                if (len(actor.writes) != 2
                        or len(actor.brain.pending_requests) != 1
                        or actor.boundary not in recorded["personality_choices"]):
                    raise AssertionError("Accepted actor lost choice/pending ledger")
            else:
                if (len(actor.writes) != 1
                        or actor.brain.pending_requests
                        or "personality_choices" in recorded):
                    raise PermissionError("Timed-out worker reached live decision ledger")
            if (actor.router.record["boundaries"][actor.boundary]["selected"]
                    != "llm"):
                raise AssertionError("Timeout changed a persisted route into GOAP")

    first = min(started_by_actor.values())
    skew = max(started_by_actor.values()) - first
    result = {
        "actors": size,
        "native": native,
        "arrival_pattern": "same_event_loop_turn",
        "burst_launch_skew_seconds": skew,
        "queue_includes_wall_deadline": timeout_seconds,
        "one_shared_native_worker": True,
        "caller_wall_seconds": caller_elapsed,
        "post_timeout_worker_drain_seconds": drain_seconds,
        "accepted_unexecuted_proposals": len(completed),
        "timed_out_no_proposal": len(timed_out),
        "underlying_actual_System_One_forwards": meter.calls - before,
        "provider_invocations_started": (
            telemetry["inference_invocations_started"]),
        "provider_invocations_finished": (
            telemetry["inference_invocations_finished"]),
        "telemetry": telemetry,
        "accepted_actor_ids": sorted(completed),
        "timed_out_actor_ids": sorted(timed_out),
        "median_successful_end_to_end_seconds": (
            statistics.median(x["elapsed_seconds"] for x in completed.values())
            if completed else None
        ),
        "p95_successful_end_to_end_seconds": (
            percentile(tuple(x["elapsed_seconds"] for x in completed.values()), .95)
            if completed else None
        ),
        "world_commands_sent": 0,
        "accepted_evennia_receipts": 0,
    }
    if result["accepted_unexecuted_proposals"] == 0:
        result["interpretation"] = "No successful native decisions within this runner deadline"
    elif result["accepted_unexecuted_proposals"] == size:
        result["interpretation"] = "This runner completed the whole same-time queue, NOT evidence of world work"
    else:
        result["interpretation"] = (
            "Some proposals finished in time, others timed out; the queue "
            "limit is measured for this exact native backend and hardware"
        )
    return result


async def run(*, engine_name: str, gguf_path: Path | None = None,
              manifest: Path | None = None,
              timeout_override: float | None = None):
    if engine_name not in ("fixture", "decider-q4"):
        raise ValueError("G16m backend must be explicitly selected")
    native = engine_name == "decider-q4"
    if native:
        if gguf_path is None or manifest is None:
            raise FileNotFoundError("Pinned native model required")
        if timeout_override is not None:
            raise ValueError("Native benchmark cannot override production 25s deadline")
        engine, provenance = native_engine(gguf_path, manifest)
        deadline = NATIVE_DEADLINE
    else:
        engine, provenance = FakeSystemOne(), None
        deadline = timeout_override or 12.0
    meter = EngineMeter(engine)
    cohorts = [
        await run_cohort(size, meter=meter,
                         timeout_seconds=deadline, native=native)
        for size in COHORTS
    ]
    if sum(x["underlying_actual_System_One_forwards"] for x in cohorts) != meter.calls:
        raise AssertionError("Counted model forwards changed between cohorts")
    return {
        "schema": 1,
        "experiment": "g16m_real_g16c_simultaneous_6_20_40_queue",
        "backend": engine_name,
        "model_provenance": provenance,
        "actual_native_gguf_forward_calls": meter.calls if native else 0,
        "synthetic_fixture_forward_calls": meter.calls if not native else 0,
        "native_model_verified": native,
        "deadline_seconds": deadline,
        "native_concurrency": 1,
        "max_active_system_one_forwards": meter.peak_active,
        "environment": {
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "process_peak_rss_kib_linux": resource.getrusage(
                resource.RUSAGE_SELF).ru_maxrss,
        },
        "cohorts": cohorts,
        "personality_policy_production_enabled": False,
        "evennia_world_connections": 0,
        "world_commands_sent": 0,
        "world_receipts_claimed": 0,
        "limitations": (
            "Actual real G16c scheduler, but hypothetical same-time arrivals "
            "and original G16f synthetic actor minds/finite non-safety menu. "
            "One shared CPU inference engine only; cannot infer two-lane "
            "speedup, real 40-person duty rate or authenticated Evennia work. "
            "No model choice or personality calibration from this cost trial."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("fixture", "decider-q4"), required=True)
    parser.add_argument("--gguf-path", type=Path)
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.getenv("OX_PERSONALITY_CHOICE") != "1":
        parser.error("G16m isolated test requires opt-in in its own process")
    result = asyncio.run(run(
        engine_name=args.engine, gguf_path=args.gguf_path,
        manifest=args.model_manifest,
    ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "model": result["backend"],
        "native_forwards": result["actual_native_gguf_forward_calls"],
        "outcomes": [
            {"actors": r["actors"],
             "adopted": r["accepted_unexecuted_proposals"],
             "timed_out": r["timed_out_no_proposal"],
             "late_started_workers": r["telemetry"]["timed_out_with_provider_active"],
             "queued_expired": r["telemetry"]["timed_out_waiting_for_slot"]}
            for r in result["cohorts"]
        ],
    }, sort_keys=True))
    print("OX_G16M_REAL_QUEUE_MEASUREMENT_OR_EXPLICIT_SYNTHETIC_FIXTURE_RECORDED")


if __name__ == "__main__":
    main()
