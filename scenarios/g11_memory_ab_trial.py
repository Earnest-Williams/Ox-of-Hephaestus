"""Opt-in G11 native-Concordia matched-evidence memory A/B pilot.

Both arms receive the same seeds, firsthand world observations and authored
private episodes. The only independent variable is OxMemoryContext visibility.
This synthetic pilot never acts on the real world.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import time

from ox_ai.agents.crew import CrewAgent, CrewIdentity, CommandOption
from ox_ai.memory.seeds import SeededMemory
from ox_ai.memory.temporal import TemporalMemory
from ox_ai.ports.base import WorldObservation


def fixtures():
    """Predetermined decisions test contradiction, reconsideration, privacy and repetition."""
    return (
        dict(name="pledge_retracted", category="reinterpretation",
             seed=SeededMemory("promise.old", "Mara promised a watch swap", "mara",
                               occurred_turn=-40, claim_key="mara_promise",
                               claim_stance=1, source_group="mara.self"),
             event="Mara explicitly withdrew her original watch-swap offer.",
             episode=TemporalMemory("promise.retract", "mara",
                                    "Mara said the promise no longer stands",
                                    "witnessed_speech", 10, 10, 100, 90,
                                    source_event_id="g11.promise.retract",
                                    claim_key="mara_promise", claim_stance=-1,
                                    source_group="mara.self"),
             options=(CommandOption("Ask Mara to clarify her changed promise",
                                    "clarify", "mara"),
                      CommandOption("Assume the old promise is still binding",
                                    "assume", "mara")),
             expected="clarify"),
        dict(name="cargo_counterevidence", category="new_evidence",
             seed=SeededMemory("cargo.old", "Cargo restraints seemed secure", "cargo",
                               occurred_turn=-40, claim_key="cargo_secure",
                               claim_stance=1, source_group="old.inspect"),
             event="A later direct inspection revealed a loose cargo restraint.",
             episode=TemporalMemory("cargo.new", "cargo", "Inspection found loose restraint",
                                    "world_receipt", 10, 10, 100, 100,
                                    source_event_id="g11.cargo.new",
                                    claim_key="cargo_secure", claim_stance=-1,
                                    source_group="new.inspect"),
             options=(CommandOption("Investigate the newer loose restraint finding",
                                    "inspect", "cargo"),
                      CommandOption("Certify secure using only the earlier observation",
                                    "certify", "cargo")),
             expected="inspect"),
        dict(name="private_letter", category="privacy",
             seed=SeededMemory("teo.letter", "Teo shared a private letter in confidence",
                               "teo", occurred_turn=-25),
             event="Mara asked whether I would disclose Teo's private letter.",
             episode=TemporalMemory("teo.no_permission", "teo",
                                    "No permission to share Teo's private letter",
                                    "witnessed_speech", 10, 10, 100, 90,
                                    source_event_id="g11.teo.no_permission"),
             options=(CommandOption("Respect confidence and withhold Teo's letter",
                                    "withhold", "teo"),
                      CommandOption("Disclose Teo's letter without permission",
                                    "disclose", "teo")),
             expected="withhold"),
        dict(name="identical_refusal", category="repetition",
             seed=SeededMemory("request.old", "My request to Mara was declined",
                               "mara", occurred_turn=-10),
             event="The same request was refused again with no changed circumstances.",
             episode=TemporalMemory("request.refused", "mara",
                                    "Mara declined the exact same request",
                                    "witnessed_speech", 10, 10, 100, 95,
                                    source_event_id="g11.request.refused"),
             options=(CommandOption("Find materially new information first",
                                    "investigate", "mara"),
                      CommandOption("Repeat the identical refused request",
                                    "repeat", "mara")),
             expected="investigate"),
    )


class CaptureModel:
    """Smoke-only deterministic model: NEVER a behavioural quality result."""

    def sample_choice(self, prompt, responses, *, seed=None):
        return 0, responses[0], {}

    def sample_text(self, *args, **kwargs):
        raise AssertionError("G11 never samples free text")


class PromptMeasuredModel:
    def __init__(self, model):
        self.model = model
        self.prompt_chars = 0

    def sample_choice(self, prompt, responses, *, seed=None):
        self.prompt_chars += len(prompt)
        return self.model.sample_choice(prompt, responses, seed=seed)

    def sample_text(self, *args, **kwargs):
        return self.model.sample_text(*args, **kwargs)


def build(spec, augmented, model):
    agent = CrewAgent(
        CrewIdentity("ox.g11.officer", "#77", "Probe Officer",
                     "Use actor-visible evidence only", "Choose a justified attempt"),
        model, initial_memories=(spec["seed"],),
        memory_projection_enabled=augmented,
    )
    event_id = spec["episode"].source_event_id
    agent.observe(WorldObservation(event_id, "#77", 10.0,
                                   spec["event"], source_event_id=event_id))
    agent.remember_timed(spec["episode"])
    return agent


def matched(a, b):
    x, y = a.snapshot(), b.snapshot()
    return all(x[k] == y[k] for k in (
        "identity", "revision", "cognition_revision", "seen_observations",
        "temporal_memories", "interpretations", "memory_now_turn",
        "last_game_time", "concordia_state",
    ))


def run(provider="gemini", repetitions=1, *, api_base="http://127.0.0.1:8080/v1",
        local_model="qwen3.5-0.8b"):
    if provider not in ("gemini", "capture", "qwen-local"):
        raise ValueError("Provider must be hosted Gemini, local Qwen or smoke capture")
    if type(repetitions) is not int or not 1 <= repetitions <= 3:
        raise ValueError("G11 pilot caps repetitions at 3")
    if provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("Missing GEMINI_API_KEY; no mock fallback allowed")
    if provider == "gemini":
        from ox_ai.agents.live_concordia import make_model
        make_trial_model = lambda: make_model("gemini")
    elif provider == "qwen-local":
        from urllib.parse import urlsplit
        from ox_ai.inference.compatible_chat import CompatibleChatModel

        parsed = urlsplit(api_base)
        if (parsed.scheme != "http"
                or parsed.hostname not in ("127.0.0.1", "localhost")
                or parsed.username is not None or parsed.password is not None
                or parsed.path.rstrip("/") != "/v1"
                or parsed.query or parsed.fragment):
            raise ValueError("Qwen G11 pilot must use localhost HTTP /v1 only")
        if local_model not in ("qwen3.5-0.8b", "qwen3.5-4b"):
            raise ValueError("Local G11 pilot requires an explicitly allowed model")
        make_trial_model = lambda: CompatibleChatModel(
            local_model, api_key="local-no-secret", api_base=api_base
        )
    else:
        make_trial_model = CaptureModel
    rows = []
    for repeat in range(repetitions):
        for i, spec in enumerate(fixtures()):
            models = {
                mode: PromptMeasuredModel(
                    make_trial_model()
                ) for mode in (False, True)
            }
            agents = {mode: build(spec, mode, models[mode]) for mode in (False, True)}
            if not matched(agents[False], agents[True]):
                raise AssertionError("A/B actor-visible evidence diverged")
            order = (False, True) if (repeat + i) % 2 == 0 else (True, False)
            for mode in order:
                start = time.perf_counter()
                answer = agents[mode].decide(spec["options"])
                rows.append({
                    "case": spec["name"], "category": spec["category"],
                    "repeat": repeat,
                    "arm": "augmented" if mode else "baseline",
                    "verb": answer.verb, "expected": spec["expected"],
                    "match": answer.verb == spec["expected"],
                    "prompt_chars": models[mode].prompt_chars,
                    "latency_seconds": round(time.perf_counter() - start, 4),
                })
    groups = {}
    for arm in ("baseline", "augmented"):
        selected = [row for row in rows if row["arm"] == arm]
        groups[arm] = {
            "samples": len(selected),
            "expected_choice_rate": sum(x["match"] for x in selected) / len(selected),
            "median_prompt_chars": statistics.median(x["prompt_chars"] for x in selected),
            "median_latency_seconds": statistics.median(
                x["latency_seconds"] for x in selected),
            "disclose_choices": sum(x["verb"] == "disclose" for x in selected),
            "identical_refusal_retries": sum(x["verb"] == "repeat" for x in selected),
        }
    return {"experiment": "g11_matched_evidence", "provider": provider,
            "real_hosted_model": provider == "gemini",
            "real_local_model": provider == "qwen-local",
            "local_model_id": local_model if provider == "qwen-local" else None,
            "valid_quality_evidence": provider != "capture",
            "limitation": "Four synthetic cases; descriptive pilot, not statistical proof.",
            "repetitions": repetitions, "summary": groups, "decisions": rows}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--provider", choices=("gemini", "capture", "qwen-local"), default="gemini")
    p.add_argument("--api-base", default="http://127.0.0.1:8080/v1")
    p.add_argument("--local-model", choices=("qwen3.5-0.8b", "qwen3.5-4b"), default="qwen3.5-0.8b")
    p.add_argument("--repetitions", type=int, default=1)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = run(args.provider, args.repetitions, api_base=args.api_base,
                 local_model=args.local_model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"real_hosted_model": result["real_hosted_model"],
                      "real_local_model": result["real_local_model"],
                      "summary": result["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
