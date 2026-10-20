"""G12 reproducible native Concordia dispatch and snapshot microprofile.

Six, twenty and forty simultaneous private brains; *local* choice model.
No hosted calls, world operation, or inference-quality claim.
"""
from __future__ import annotations

import argparse
import gc
import json
import math
from pathlib import Path
import platform
import statistics
import tempfile
import time
import tracemalloc

from ox_ai.agents.crew import CrewAgent, CrewIdentity, CommandOption
from ox_ai.memory.seeds import SeededMemory
from ox_ai.memory.temporal import TemporalMemory


class CaptureChoiceModel:
    def __init__(self):
        self.prompt_chars = []
        self.sampled_calls = 0

    def sample_choice(self, prompt, responses, *, seed=None):
        self.prompt_chars.append(len(prompt))
        self.sampled_calls += 1
        return 0, responses[0], {}

    def sample_text(self, *args, **kwargs):
        raise AssertionError("No free-form model calls in performance sampling")


OPTIONS = (
    CommandOption("Review recent evidence with Mara", "speak", "mara"),
    CommandOption("Wait for further information", "defer"),
)


def percentile(samples, pct):
    ordered = sorted(samples)
    if not ordered:
        raise ValueError("Cannot calculate empty percentile")
    return ordered[min(len(ordered)-1, max(0, math.ceil(len(ordered) * pct)-1))]


def create_agent(i, *, journal_path=None):
    seeds = tuple(SeededMemory(
        f"mara.{i}.{j}", f"Personal recollection {j} about Mara's prior shift",
        "mara", occurred_turn=-(j + 1) * 10, salience=55 + j,
        trust_effect=(j % 5) - 2,
    ) for j in range(12))
    model = CaptureChoiceModel()
    brain = CrewAgent(
        CrewIdentity(f"ox.profile.{i}", f"#{10000+i}", f"Profiler {i}",
                     "Consider only own experience", "Propose an available action"),
        model, initial_memories=seeds, journal_path=journal_path,
    )
    for j in range(4):
        brain.remember_timed(TemporalMemory(
            f"world.{i}.{j}", "mara",
            f"Recipient-observed exchange about duty {j}",
            "witnessed_speech", 20+j, 20+j, 90, 80,
            source_event_id=f"source.{i}.{j}",
        ))
    return brain, model


def cohort(population, rounds):
    gc.collect()
    tracemalloc.start()
    start = time.perf_counter()
    actors = [create_agent(i) for i in range(population)]
    construction = time.perf_counter() - start
    dispatch = []
    for _ in range(rounds):
        for brain, model in actors:
            tick = time.perf_counter_ns()
            brain.decide(OPTIONS)
            dispatch.append((time.perf_counter_ns() - tick) / 1_000_000)
    copies, sizes = [], []
    for brain, model in actors:
        tick = time.perf_counter_ns()
        shadow = brain.fork_for_inference()
        copies.append((time.perf_counter_ns() - tick) / 1_000_000)
        assert shadow.temporal_memories.to_records() == brain.temporal_memories.to_records()
        sizes.append(len(json.dumps(brain.snapshot(), separators=(",", ":")).encode()))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    char_lengths = [size for _, m in actors for size in m.prompt_chars]
    calls = sum(m.sampled_calls for _, m in actors)
    assert calls == population * rounds
    return {
        "population": population, "rounds_per_actor": rounds,
        "total_native_choice_dispatches": calls,
        "construction_seconds": round(construction, 5),
        "median_dispatch_ms": round(statistics.median(dispatch), 4),
        "p95_dispatch_ms": round(percentile(dispatch, .95), 4),
        "median_fork_ms": round(statistics.median(copies), 4),
        "p95_fork_ms": round(percentile(copies, .95), 4),
        "mean_checkpoint_bytes": round(statistics.mean(sizes), 1),
        "total_checkpoint_bytes": sum(sizes),
        "peak_tracemalloc_bytes": peak,
        "median_prompt_chars": statistics.median(char_lengths),
        "p95_prompt_chars": percentile(char_lengths, .95),
    }


def journal_cost(decisions=20):
    """Relative cost of optional per-decision fsync diagnostics, not an SLA."""
    with tempfile.TemporaryDirectory() as root:
        times = {}
        bytes_written = 0
        for label, journal in (("off", None), ("on", Path(root) / "crew.jsonl")):
            brain, model = create_agent(300, journal_path=journal)
            timings = []
            for _ in range(decisions):
                start = time.perf_counter_ns()
                brain.decide(OPTIONS)
                timings.append((time.perf_counter_ns()-start)/1_000_000)
            times[label] = statistics.median(timings)
            if journal is not None:
                bytes_written = journal.stat().st_size
        return {
            "decisions_per_arm": decisions,
            "median_dispatch_without_journal_ms": round(times["off"], 4),
            "median_dispatch_with_journal_ms": round(times["on"], 4),
            "journal_bytes": bytes_written,
            "mean_journal_bytes_per_choice": round(bytes_written/decisions, 1),
            "qualification": "Journaling includes seed-admission traces; bytes/choice is an upper-bound proxy.",
        }


def run(rounds=2):
    if type(rounds) is not int or not 1 <= rounds <= 5:
        raise ValueError("Bound profile to 1-5 rounds per actor")
    return {
        "experiment": "g12_native_concordia_scale_profile",
        "provider": "local deterministic capture only",
        "hosted_inference_latency_measured": False,
        "environment": {"python": platform.python_version(),
                        "platform": platform.platform(),
                        "processor": platform.processor()},
        "cohorts": [cohort(size, rounds) for size in (6, 20, 40)],
        "optional_diagnostics": journal_cost(),
        "limits": ("Sequential native dispatch, no hosted inference; "
                   "tracemalloc is Python allocations, not full process RSS; "
                   "prompt size is characters, not provider tokens."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.rounds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
