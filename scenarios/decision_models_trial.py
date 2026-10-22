"""Compare native-Concordia choices using Ollaya decision models.

This is a four-case synthetic G11 pilot, not live-world action execution.
Laya / JevK5 are decision heads: they score a finite menu in one inference
call rather than generating words. Their output is never world authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scenarios.g11_memory_ab_trial import build, fixtures, matched


MODELS = ("laya:en", "laya:typed-decisions", "jevk5:4b")


def localhost_api(base: str) -> str:
    """Fail closed: prevent a model test from silently calling hosted APIs."""
    parsed = urlsplit(base)
    if (parsed.scheme != "http"
            or parsed.hostname not in ("localhost", "127.0.0.1")
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
        raise ValueError("Decision-model experiment requires local Ollaya HTTP")
    return base.rstrip("/") + "/api/decide"


class OllayaChoiceModel:
    """Map an authored, finite Concordia action menu to Ollaya choice scores."""

    def __init__(self, model_id: str, descriptions: tuple[str, ...],
                 endpoint: str, *, timeout: int = 180) -> None:
        if model_id not in MODELS:
            raise ValueError("Unexpected decision model")
        self.model_id = model_id
        self.descriptions = descriptions
        self.endpoint = endpoint
        self.timeout = timeout
        self.last_answer = None
        self.calls = 0

    def sample_choice(self, prompt, responses, *, seed=None):
        del seed
        allowed = tuple(responses)
        if not 2 <= len(allowed) <= 16 or len(self.descriptions) != len(allowed):
            raise ValueError("Invalid finite menu")
        if len(set(allowed)) != len(allowed):
            raise ValueError("Duplicate action codes")
        options = dict(zip(allowed, self.descriptions))
        payload = {
            "model": self.model_id,
            "state": prompt,
            "questions": {
                "next_action": {
                    "type": "choice",
                    "instructions": (
                        "Which permitted action should this spaceship crew member "
                        "attempt next, based on the evidence, duties and memories? "
                        "No action has been executed or verified."
                    ),
                    "criteria": options,
                }
            },
            "keep_alive": "10m",
        }
        raw = json.dumps(payload).encode("utf-8")
        req = Request(self.endpoint, raw, {
            "Content-Type": "application/json",
        }, method="POST")
        try:
            with urlopen(req, timeout=self.timeout) as response:
                data = json.load(response)
        except HTTPError as exc:
            raise RuntimeError(
                f"Local Ollaya returned HTTP {exc.code}: "
                + exc.read(1000).decode("utf-8", errors="replace")
            ) from exc
        if data.get("state_truncated") is not False:
            raise ValueError("Decision model truncated or did not attest its state")
        answer = data.get("answers", {}).get("next_action", {})
        selected = answer.get("choice")
        probabilities = answer.get("probabilities")
        if selected not in options or answer.get("type") != "choice":
            raise ValueError(f"Decision model returned an invalid choice: {selected!r}")
        if not isinstance(probabilities, dict) or set(probabilities) != set(options):
            raise ValueError("Decision model returned malformed option probabilities")
        self.calls += 1
        self.last_answer = {
            "choice": selected,
            "confidence": answer.get("confidence"),
            "probabilities": probabilities,
            "eval_duration_ns": data.get("eval_duration"),
            "input_tokens": data.get("usage", {}).get("input_tokens"),
            "actual_model": data.get("model"),
        }
        return allowed.index(selected), selected, {"ollaya": self.last_answer}

    def sample_text(self, *args, **kwargs):
        raise RuntimeError("A decision head cannot generate text")


def run(model_id: str, repetitions: int, *, api_base: str) -> dict:
    if model_id not in MODELS or type(repetitions) is not int or not 1 <= repetitions <= 3:
        raise ValueError("Invalid model or repetition count")
    endpoint = localhost_api(api_base)
    rows = []
    for repeat in range(repetitions):
        for i, spec in enumerate(fixtures()):
            models = {
                mode: OllayaChoiceModel(
                    model_id,
                    tuple(option.label for option in spec["options"]),
                    endpoint,
                ) for mode in (False, True)
            }
            agents = {mode: build(spec, mode, models[mode])
                      for mode in (False, True)}
            if not matched(agents[False], agents[True]):
                raise AssertionError("Matched G11 evidence diverged")
            for mode in ((False, True) if (repeat + i) % 2 == 0 else (True, False)):
                start = time.perf_counter()
                attempt = agents[mode].decide(spec["options"])
                elapsed = time.perf_counter() - start
                model = models[mode]
                if model.calls != 1 or len(agents[mode].pending_requests) != 1:
                    raise AssertionError("Model choice did not produce one pending proposal")
                if attempt.verb not in {x.verb for x in spec["options"]}:
                    raise AssertionError("Choice escaped permitted action menu")
                rows.append({
                    "case": spec["name"], "category": spec["category"],
                    "repeat": repeat,
                    "arm": "augmented" if mode else "baseline",
                    "verb": attempt.verb,
                    "expected": spec["expected"],
                    "match": attempt.verb == spec["expected"],
                    "latency_seconds": round(elapsed, 4),
                    "decision": model.last_answer,
                    "world_commands_sent": 0,
                })
    summary = {}
    for arm in ("baseline", "augmented"):
        group = [row for row in rows if row["arm"] == arm]
        summary[arm] = {
            "samples": len(group),
            "expected_choice_rate": sum(row["match"] for row in group) / len(group),
            "median_latency_seconds": statistics.median(
                row["latency_seconds"] for row in group),
            "disclose_choices": sum(row["verb"] == "disclose" for row in group),
            "identical_refusal_retries": sum(row["verb"] == "repeat" for row in group),
        }
    return {
        "experiment": "g11_native_decision_heads",
        "provider": "local_ollaya",
        "model": model_id,
        "real_local_model": True,
        "native_concordia": True,
        "repetitions": repetitions,
        "summary": summary,
        "decisions": rows,
        "world_commands_sent": 0,
        "world_receipts_received": 0,
        "limitation": (
            "Four synthetic fixtures only. Native typed-decision API differs "
            "from chat completion; results are descriptive, not a model ranking."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--repetitions", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--api-base", default="http://127.0.0.1:11435")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = run(args.model, args.repetitions, api_base=args.api_base)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"model": result["model"], "summary": result["summary"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
