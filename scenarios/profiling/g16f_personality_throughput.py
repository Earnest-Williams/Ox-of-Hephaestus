"""G16f measured 6/20/40 independent real-Concordia scheduler workloads.

Native mode performs three actual local Decider forwards for EVERY actor,
not a sleep-based extrapolation. Fixture mode exercises identical actor,
scheduler, disposition, ledger and checkpoint code but is expressly NOT
native inference throughput. No world connection, hosted model or command.
"""
from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import tempfile
import threading
import time

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.inference.decider_gguf_choice import DeciderGGUFChoiceModel
from ox_ai.memory.seeds import SeededMemory
from ox_ai.memory.temporal import TemporalMemory
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.runtime.cognition_scheduler import DecisionScheduler
from ox_ai.runtime.personality_routing import (
    CharacterRouteController, PersonalState, PersonalityRouter,
)
from ox_contracts import load_catalog


COHORTS = (6, 20, 40)
MENU_KEY = "g14.verified_mutual_aid"
MODEL_REVISIONS = (
    "3b02c98fa0b19e9daab247d633095b6e8a6cd4c5",
    "d3a78581751d518bbfa9e871a6d84059554d53c5",
)


class ForbiddenBaseline:
    def sample_choice(self, *args, **kwargs):
        raise AssertionError("Unflagged model must not select a G16f action")

    def sample_text(self, *args, **kwargs):
        raise AssertionError("Dialogue generation is outside G16f")


class FakeSystemOne:
    """Real interface, deterministic synthetic scores; NOT native throughput."""
    def system_one(self, prompt, questions):
        criteria = questions["next_action"]["criteria"]
        weights = {}
        for pos, (code, label) in enumerate(criteria.items()):
            key = label.removeprefix("Act: ")
            weights[code] = {
                "accept_help": 0.37, "work_alone": 0.39,
                "reschedule": 0.24,
            }[key] + (0.02 if pos == 0 else 0)
        z = sum(weights.values())
        probability = {code: v / z for code, v in weights.items()}
        return {"answers": {"next_action": {
            "choice": max(probability, key=probability.get),
            "probabilities": probability,
        }}}


class EngineMeter:
    """One shared backend, independently counts actual three-pass forwards."""

    def __init__(self, delegate):
        self.delegate = delegate
        self._lock = threading.Lock()
        self.calls = 0
        self.active = 0
        self.peak_active = 0
        self.latencies_seconds = []

    def system_one(self, prompt, questions):
        with self._lock:
            self.active += 1
            self.peak_active = max(self.peak_active, self.active)
        started = time.perf_counter()
        try:
            result = self.delegate.system_one(prompt, questions)
        finally:
            elapsed = time.perf_counter() - started
            with self._lock:
                self.active -= 1
                self.calls += 1
                self.latencies_seconds.append(elapsed)
        return result


@dataclass(slots=True)
class PendingActor:
    role: str
    brain: CrewAgent
    controller: CharacterRouteController
    router: PersonalityRouter
    router_path: Path
    boundary: str
    writes: list[float]

    def persist(self):
        started = time.perf_counter()
        content = json.dumps(self.router.record, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
        tmp = self.router_path.with_suffix(".tmp")
        with tmp.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, self.router_path)
        self.writes.append(time.perf_counter() - started)


def percentile(xs: Sequence[float], fraction: float) -> float:
    if not xs:
        raise ValueError("No profile samples")
    xs = sorted(xs)
    return float(xs[max(0, min(len(xs)-1, math.ceil(len(xs)*fraction)-1))])


def make_actor(i: int, *, scheduler: DecisionScheduler,
               engine: EngineMeter, path: Path, state: PersonalState,
               menu) -> PendingActor:
    identity = f"#{10000+i}"
    procedural = i % 2 == 0
    traits = (
        {"conscientiousness": 90, "risk_tolerance": 20,
         "authority_challenge": 15, "collaboration": 85,
         "agreeableness": 85}
        if procedural else
        {"conscientiousness": 25, "risk_tolerance": 90,
         "authority_challenge": 90, "collaboration": 20,
         "agreeableness": 25}
    )
    profile = compose_blueprint(
        f"g16f.crew_{i}", f"G16f Crew {i}",
        trait_overrides=traits,
    )
    memories = tuple(
        SeededMemory(
            f"other.{i}.{j}", f"Private duty memory {j} of the station",
            "mara", occurred_turn=-(j+1)*10, salience=56+j,
            trust_effect=(j % 5)-2,
        ) for j in range(6)
    )
    brain = CrewAgent(
        CrewIdentity(f"ox.person.{profile.person_id}", identity,
                     profile.name, "Review own duty notes",
                     "Choose exactly one hypothetical permitted action"),
        ForbiddenBaseline(), blueprint=profile, initial_memories=memories,
    )
    for j in range(2):
        brain.remember_timed(TemporalMemory(
            f"private.{i}.{j}", "mara",
            f"Personal recollection about meeting {j}",
            "witnessed_speech", 10+j, 10+j, 88, 73,
            source_event_id=f"g16f.synthetic.{i}.{j}",
        ))
    boundary = f"g16f.role.{i}.choice.1"
    router = None
    for attempt in range(4096):
        trial = PersonalityRouter(
            profile, identity, {},
            seed=f"ox-g16f-{i}-seed-{attempt}",
        )
        if trial._draw(boundary) < trial.probability(state, "social"):
            router = trial
            break
    if router is None:
        raise AssertionError("Could not obtain real deliberate-route sample")
    role = f"g16f-{i}"
    return PendingActor(
        role, brain,
        CharacterRouteController(
            router, scheduler, role=role, decider_engine=engine,
        ),
        router, path / f"{role}.json", boundary, [],
    )


async def profile_cohort(size: int, *, meter: EngineMeter,
                         mode: str, max_parallel: int) -> dict:
    if size not in COHORTS or mode not in ("sequential", "burst"):
        raise ValueError("Unexpected preregistered G16f population/mode")
    menu = load_catalog().menu(MENU_KEY)
    offered = tuple(
        CommandOption("Act: " + option.semantic_key,
                      option.verb, option.target)
        for option in menu.options
    )
    planner = GoapPlanner(tuple(
        GoapAction(option.semantic_key, requires=frozenset({"notes_active"}),
                   adds=frozenset({"decision"}), verb=option.verb,
                   target=option.target)
        for option in menu.options
    ))
    state = PersonalState(stress=0.35, social_pressure=0.65,
                          fatigue=0.20, uncertainty=0.4)
    scheduler = DecisionScheduler(
        max_parallel=max_parallel, per_actor_budget=3,
        total_budget=size*3, timeout_seconds=120,
    )
    before = meter.calls
    elapsed = {}
    proposals = {}
    with tempfile.TemporaryDirectory(prefix="ox-g16f-") as root:
        directory = Path(root)
        create_started = time.perf_counter()
        actors = [
            make_actor(i, scheduler=scheduler, engine=meter,
                       path=directory, state=state, menu=menu)
            for i in range(size)
        ]
        create_seconds = time.perf_counter() - create_started
        async def decide(actor):
            started = time.perf_counter()
            result = await actor.controller.decide(
                agent=actor.brain, planner=planner,
                beliefs=frozenset({"notes_active"}),
                goals=frozenset({"decision"}),
                options=offered, boundary_id=actor.boundary,
                kind="social", state=state,
                menu_key=MENU_KEY,
                persist=actor.persist,
            )
            elapsed[actor.role] = time.perf_counter() - started
            proposals[actor.role] = result
        started = time.perf_counter()
        if mode == "sequential":
            for actor in actors:
                await decide(actor)
        else:
            await asyncio.gather(*(decide(a) for a in actors))
        decision_seconds = time.perf_counter() - started
        if (len(proposals) != size or meter.calls - before != size*3
                or scheduler.metrics["started"] != size*3
                or scheduler.metrics["timed_out_or_cancelled_roles"]
                or scheduler.metrics["inflight_roles"]):
            raise AssertionError("Native forward budget, proposals or workers incomplete")
        saved_bytes = []
        checkpoint_bytes = []
        for actor in actors:
            result = proposals[actor.role]
            if (result.route.selected != "llm"
                    or result.model_calls != 3
                    or len(actor.brain.pending_requests) != 1
                    or result.action not in actor.brain.pending_requests
                    or len(actor.writes) != 2):
                # Pending_requests is a tuple; membership compares the exact
                # original immutable ActionRequest, not a work receipt.
                raise AssertionError("G16f did not durably adopt one audited proposal")
            entry = actor.router.record["personality_choices"][actor.boundary]
            if (entry["request_id"] != result.action.request_id
                    or not actor.router_path.is_file()
                    or entry["choice"]["underlying_native_calls"] != 3
                    or entry["actor"] != actor.brain.identity.character_id):
                raise AssertionError("G16f ledger or actor provenance invalid")
            saved = json.loads(actor.router_path.read_text(encoding="utf-8"))
            if saved != actor.router.record:
                raise AssertionError("Durable router snapshot does not match in-memory ledger")
            saved_bytes.append(actor.router_path.stat().st_size)
            checkpoint_bytes.append(len(json.dumps(actor.brain.snapshot())))
        writes = [x for actor in actors for x in actor.writes]
    return {
        "actors": size,
        "arrival_pattern": mode,
        "max_parallel_scoring_workers": max_parallel,
        "model_forwards_counted": meter.calls - before,
        "decisions_completed": len(proposals),
        "creation_seconds": create_seconds,
        "decisions_wall_seconds": decision_seconds,
        "measured_decisions_per_hour_at_this_backend": (
            3600.0 * size / decision_seconds
        ),
        "median_end_to_end_seconds": statistics.median(elapsed.values()),
        "p95_end_to_end_seconds": percentile(tuple(elapsed.values()), .95),
        "median_durable_checkpoint_seconds": statistics.median(writes),
        "p95_durable_checkpoint_seconds": percentile(writes, .95),
        "total_durable_router_bytes": sum(saved_bytes),
        "total_live_agent_snapshot_bytes": sum(checkpoint_bytes),
        "worst_case_pending_actions_per_actor": 1,
    }


async def run(*, engine_name: str, mode: str,
              gguf_path: Path | None, model_manifest: Path | None) -> dict:
    if engine_name not in ("fixture", "decider-q4"):
        raise ValueError("Unrecognized scoring provider")
    if engine_name == "decider-q4":
        if mode != "sequential":
            raise ValueError("Native shared GGUF engine is profiled with serial scheduler only")
        if (gguf_path is None or model_manifest is None
                or not gguf_path.is_file() or not model_manifest.is_file()):
            raise FileNotFoundError("Real native score requires GGUF and publisher manifest")
        provenance = json.loads(model_manifest.read_text(encoding="utf-8"))
        if (provenance.get("model") != "decider-q4"
                or (provenance.get("hf_revision"),
                    provenance.get("tokenizer_revision")) != MODEL_REVISIONS
                or provenance.get("size") != gguf_path.stat().st_size):
            raise PermissionError("Native GGUF source is not the pinned G14/G16e revision")
        digest = hashlib.sha256()
        with gguf_path.open("rb") as source:
            while block := source.read(8*1024*1024):
                digest.update(block)
        if provenance.get("sha256") != digest.hexdigest():
            raise PermissionError("Native GGUF SHA-256 differs from model manifest")
        engine = DeciderGGUFChoiceModel(
            gguf_path, ("accept_help", "work_alone", "reschedule"),
            n_threads=2,
        ).engine
    else:
        engine, provenance = FakeSystemOne(), None
    meter = EngineMeter(engine)
    cohorts = []
    for population in COHORTS:
        cohorts.append(await profile_cohort(
            population, meter=meter, mode=mode,
            max_parallel=1 if engine_name == "decider-q4" else 2,
        ))
    recorded = [x["model_forwards_counted"] for x in cohorts]
    if recorded != [18, 60, 120] or meter.calls != 198:
        raise AssertionError("G16f missed genuine three-pass consultations")
    return {
        "schema": 1, "experiment": "g16f_deliberate_personality_throughput",
        "backend": engine_name,
        "native_gguf_forwards_measured": engine_name == "decider-q4",
        "hypothetical_only": True, "evennia_commands_sent": 0,
        "engine_manifest": provenance,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "peak_rusage_maxrss_kib_linux": resource.getrusage(
                resource.RUSAGE_SELF).ru_maxrss,
        },
        "forward_calls": meter.calls,
        "maximum_concurrent_native_forwards": meter.peak_active,
        "per_forward_latency_median_seconds": statistics.median(
            meter.latencies_seconds
        ),
        "per_forward_latency_p95_seconds": percentile(
            meter.latencies_seconds, .95,
        ),
        "measured_cohorts": cohorts,
        "default_production_timeout_seconds": 25,
        "default_production_max_parallel": 2,
        "default_production_total_forward_budget_per_hour": 2500,
        "median_native_three_forward_estimate_seconds": (
            3 * statistics.median(meter.latencies_seconds)
            if engine_name == "decider-q4" else None
        ),
        "limits": (
            "One identical finite non-safety menu per actor, serial genuine "
            "native scoring or concurrent synthetic fixture, 66 consultations. "
            "No world actions or NPC duty-roster mix. Fixture rate is not "
            "native model throughput; native serial results cannot be "
            "extrapolated to 2 worker speedup without a separate measurement."
        ),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--engine", choices=("fixture", "decider-q4"),
                   default="fixture")
    p.add_argument("--mode", choices=("sequential", "burst"),
                   default="sequential")
    p.add_argument("--gguf-path", type=Path)
    p.add_argument("--model-manifest", type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if os.getenv("OX_PERSONALITY_CHOICE") != "1":
        p.error("G16f only runs with explicitly enabled experimental flag")
    result = asyncio.run(run(
        engine_name=args.engine, mode=args.mode,
        gguf_path=args.gguf_path, model_manifest=args.model_manifest,
    ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "engine": result["backend"], "forwards": result["forward_calls"],
        "cohorts": [x["actors"] for x in result["measured_cohorts"]],
        "median_forward_seconds": result["per_forward_latency_median_seconds"],
        "native": result["native_gguf_forwards_measured"],
    }, sort_keys=True))
    print("OX_G16F_THREE_COHORT_PROFILE_COMPLETE")


if __name__ == "__main__":
    main()
