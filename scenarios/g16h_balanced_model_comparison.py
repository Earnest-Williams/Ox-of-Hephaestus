"""G16h: position-balanced 24-case Decider Q4 versus Qwen3.5-4B.

Preserves all 24 G11 authored evidence reversals without changing the
correct choice, but presents the expected answer in BOTH caller positions.
Binary Decider scores both option-letter rotations; Qwen makes one chat
choice in each outer order. All outcomes are inert actor proposals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity
from ox_ai.memory.seeds import SeededMemory
from ox_ai.ports.base import WorldObservation
from ox_ai.inference.decider_gguf_choice import DeciderGGUFChoiceModel
from g16h_counterfactual_cases import fixtures, Case

QWEN4B_SHA = "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4"
DECIDER_WEIGHT_REVISION = "3b02c98fa0b19e9daab247d633095b6e8a6cd4c5"
DECIDER_TOKENIZER_REVISION = "d3a78581751d518bbfa9e871a6d84059554d53c5"
ORDERS = ("canonical", "reversed")
VARIANTS = ("earlier", "changed")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(8*1024*1024):
            h.update(chunk)
    return h.hexdigest()


class FirstCodeNativeFixture:
    def system_one(self, prompt, questions):
        codes = list(questions["next_action"]["criteria"])
        return {"answers": {"next_action": {
            "choice": codes[0],
            "probabilities": {code: 0.8 if i == 0 else 0.2
                              for i, code in enumerate(codes)},
        }}}


class BalancedBinaryDecider:
    """Two real System One passes; caller-order semantic probability average."""

    def __init__(self, engine, options):
        if (len(options) != 2
                or len({k for k, _ in options}) != 2
                or len({x for _, x in options}) != 2):
            raise ValueError("Two distinct semantic binary options required")
        self.engine, self.options = engine, tuple(options)
        self.last = None

    def sample_choice(self, prompt, responses, *, seed=None):
        del seed
        codes = tuple(responses)
        if (not isinstance(prompt, str) or not prompt.strip()
                or len(codes) != 2 or len(set(codes)) != 2):
            raise ValueError("Exactly two unique finite response codes required")
        self.last = None
        labels = dict(self.options)
        keys = tuple(sorted(labels))
        sums = {key: 0.0 for key in keys}
        passes = []
        for offset in range(2):
            order = keys[offset:] + keys[:offset]
            questions = {
                "next_action": {
                    "type": "choice",
                    "instructions": (
                        "Based solely on the actor's directly observed "
                        "evidence and authorized options, which action "
                        "should the character attempt next? This is NOT "
                        "a claim of completed world work."
                    ),
                    "criteria": {
                        code: labels[key] for code, key in zip(codes, order)
                    },
                }
            }
            response = self.engine.system_one(prompt, questions)
            answer = response.get("answers", {}).get("next_action", {})
            scores = answer.get("probabilities")
            chosen = answer.get("choice")
            if (chosen not in codes or not isinstance(scores, dict)
                    or set(scores) != set(codes)
                    or any(type(v) not in (int, float) or
                           not math.isfinite(v) or not 0 <= v <= 1
                           for v in scores.values())
                    or not math.isclose(sum(scores.values()), 1.0, abs_tol=0.02)):
                raise ValueError("Malformed native Decider binary scorer result")
            semantic = {
                key: float(scores[code]) for code, key in zip(codes, order)
            }
            for key in keys:
                sums[key] += semantic[key]
            passes.append({
                "code_positions": list(order),
                "semantic_scores": semantic,
                "selected_key": order[codes.index(chosen)],
            })
        means = {key: sums[key] / 2 for key in keys}
        if {item["code_positions"][0] for item in passes} != set(keys):
            raise AssertionError("Binary position-balance failed")
        high = max(means.values())
        winner = next(key for key in keys if means[key] >= high - 1e-9)
        caller_keys = tuple(key for key, _ in self.options)
        code = codes[caller_keys.index(winner)]
        self.last = {
            "native_forwards": 2,
            "semantic_scores": means,
            "passes": passes,
            "selected_semantic_key": winner,
        }
        return codes.index(code), code, {"g16h_binary_native": self.last}

    def sample_text(self, *args, **kwargs):
        raise RuntimeError("Native Decider cannot generate dialogue")


class PromptCapture:
    def __init__(self, delegate):
        self.delegate = delegate
        self.prompt_sha = None

    def sample_choice(self, prompt, responses, *, seed=None):
        self.prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return self.delegate.sample_choice(prompt, responses, seed=seed)

    def sample_text(self, *args, **kwargs):
        raise RuntimeError("G16h compares finite choices, not generated speech")


def actor_from_case(case: Case, variant: str, model):
    if variant not in VARIANTS:
        raise ValueError("Invalid counterfactual variant")
    agent = CrewAgent(
        CrewIdentity(
            agent_id="ox.counterfactual.officer", character_id="#77",
            name="Probe Officer",
            duty="Consider only directly observed evidence and permissions",
            goal="Choose a justified next attempt without asserting success",
        ),
        model,
        initial_memories=(SeededMemory(
            "cf." + case.name, case.recollection, "watch",
            occurred_turn=-30,
        ),),
    )
    observation = case.earlier if variant == "earlier" else case.changed
    event = "cf." + case.name + "." + variant
    if not agent.observe(WorldObservation(
        event, "#77", 10.0, observation, source_event_id=event,
    )):
        raise PermissionError("Counterfactual observation could not be admitted")
    return agent, observation


def run(provider: str, *, gguf_path: Path | None = None,
        model_manifest: Path | None = None,
        qwen_api_base: str = "http://127.0.0.1:8080/v1"):
    if provider not in ("fixture-decider", "decider-q4", "qwen3.5-4b"):
        raise ValueError("Unknown G16h provider")
    provenance = {"model": provider}
    if provider == "decider-q4":
        if (gguf_path is None or model_manifest is None
                or not gguf_path.is_file() or not model_manifest.is_file()):
            raise FileNotFoundError("Decider native weights and exact manifest required")
        record = json.loads(model_manifest.read_text(encoding="utf-8"))
        if (record.get("hf_revision") != DECIDER_WEIGHT_REVISION
                or record.get("tokenizer_revision") != DECIDER_TOKENIZER_REVISION
                or record.get("sha256") != sha256_file(gguf_path)):
            raise PermissionError("Native Decider weights/revision changed")
        engine = DeciderGGUFChoiceModel(
            gguf_path, ("semantic_option_a", "semantic_option_b"),
            n_threads=2,
        ).engine
        provenance.update(record)
    elif provider == "fixture-decider":
        engine = FirstCodeNativeFixture()
        provenance["fake"] = True
    else:
        if (gguf_path is None or not gguf_path.is_file()
                or sha256_file(gguf_path) != QWEN4B_SHA
                or qwen_api_base != "http://127.0.0.1:8080/v1"):
            raise PermissionError("Qwen model must be pinned and on localhost")
        provenance["sha256"] = QWEN4B_SHA
        engine = None
    cases = fixtures()
    if len(cases) != 24 or len({case.name for case in cases}) != 24:
        raise AssertionError("Historical G11 fixtures changed or were filtered")

    results = []
    for case in cases:
        for variant in VARIANTS:
            for order in ORDERS:
                original = (
                    CommandOption(case.first_option, case.first_verb),
                    CommandOption(case.second_option, case.second_verb),
                )
                offered = original if order == "canonical" else tuple(reversed(original))
                expected = (case.expected_earlier if variant == "earlier"
                            else case.expected_changed)
                position = next(i for i, opt in enumerate(offered)
                                if opt.verb == expected)
                if provider == "qwen3.5-4b":
                    from ox_ai.inference.compatible_chat import CompatibleChatModel
                    backend = CompatibleChatModel(
                        "qwen3.5-4b", api_key="local-no-secret",
                        api_base=qwen_api_base,
                    )
                else:
                    backend = BalancedBinaryDecider(
                        engine, tuple((o.verb, o.label) for o in offered)
                    )
                captured = PromptCapture(backend)
                brain, observed = actor_from_case(case, variant, captured)
                t0 = time.perf_counter()
                proposal = brain.decide(offered, expected_revision=1)
                latency = time.perf_counter() - t0
                if (proposal.verb not in {o.verb for o in offered}
                        or proposal.character_id != "#77"
                        or proposal.agent_revision != 1
                        or len(brain.pending_requests) != 1
                        or brain.usage.total_calls != 1
                        or captured.prompt_sha is None):
                    raise PermissionError("Unbound actor proposal or missing decision")
                metadata = getattr(backend, "last", None)
                if provider != "qwen3.5-4b" and (
                        metadata is None or metadata["native_forwards"] != 2):
                    raise RuntimeError("Missing two position-balanced native forwards")
                results.append({
                    "case": case.name, "category": case.category,
                    "variant": variant, "caller_order": order,
                    "expected": expected, "expected_position": position,
                    "chosen": proposal.verb, "correct": proposal.verb == expected,
                    "observed_sha256": hashlib.sha256(
                        observed.encode("utf-8")).hexdigest(),
                    "recollection_sha256": hashlib.sha256(
                        case.recollection.encode("utf-8")).hexdigest(),
                    "prompt_sha256": captured.prompt_sha,
                    "offered_verb_order": [o.verb for o in offered],
                    "native_passes": 1 if provider == "qwen3.5-4b" else 2,
                    "scorer_record": metadata,
                    "seconds": latency,
                    "world_commands_sent": 0,
                })
    if len(results) != 96:
        raise AssertionError("Did not evaluate all 24 paired situations and both orders")
    rows = {(r["case"], r["variant"], r["caller_order"]): r for r in results}
    invariant = sum(
        rows[(case.name, variant, "canonical")]["chosen"] ==
        rows[(case.name, variant, "reversed")]["chosen"]
        for case in cases for variant in VARIANTS
    )
    both = {
        order: sum(
            rows[(case.name, "earlier", order)]["correct"]
            and rows[(case.name, "changed", order)]["correct"]
            for case in cases
        )
        for order in ORDERS
    }
    by_position = {
        str(i): {
            "count": sum(r["expected_position"] == i for r in results),
            "correct": sum(r["correct"] for r in results
                           if r["expected_position"] == i),
        }
        for i in (0,1)
    }
    if any(x["count"] != 48 for x in by_position.values()):
        raise AssertionError("Expected choice did not occupy each display position equally")
    return {
        "schema": 1, "experiment": "g16h_balanced_24_counterfactual_pairs",
        "provider": provider, "fake_provider": provider == "fixture-decider",
        "real_native_measurement": provider != "fixture-decider",
        "source_case_count": 24, "candidate_decisions": 96,
        "model_forwards": sum(r["native_passes"] for r in results),
        "semantic_order_invariant_of_48": invariant,
        "expected_position_accuracy": by_position,
        "both_correct_of_24_per_order": both,
        "all_decision_correct": sum(r["correct"] for r in results),
        "median_decision_seconds": statistics.median(r["seconds"] for r in results),
        "total_inference_seconds": sum(r["seconds"] for r in results),
        "model_provenance": provenance,
        "world_commands_sent": 0, "world_receipts_claimed": 0,
        "adopted_model_decision": False,
        "rows": results,
        "limitations": ("Authored evidence reversals only; not an Evennia world test. "
                        "Qwen chat and native Decider serve different inference tasks. "
                        "No option-1-only comparison; report both positions separately."),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--provider", choices=("fixture-decider","decider-q4","qwen3.5-4b"),
                   required=True)
    p.add_argument("--gguf-path", type=Path)
    p.add_argument("--model-manifest", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    outcome = run(
        args.provider, gguf_path=args.gguf_path,
        model_manifest=args.model_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "model": outcome["provider"], "cases": outcome["source_case_count"],
        "decisions": outcome["candidate_decisions"],
        "forwards": outcome["model_forwards"],
        "both_correct": outcome["both_correct_of_24_per_order"],
        "correct": outcome["all_decision_correct"],
    }, sort_keys=True))
    print("OX_G16H_BOTH_POSITIONS_24_COUNTERFACTUAL_PAIRS_COMPLETE")


if __name__ == "__main__":
    main()
