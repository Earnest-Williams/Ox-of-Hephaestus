"""Quantised Decider 4B comparison on native Concordia choices.

Both GGUF weights use the *same* pinned Hugging Face quant repository commit.
The Decider API's system_one answer-slot logits, not text generation, select
from the bounded menu. BF16 Ollaya scores are independent reference results,
NOT assumed to be identical checkpoint weights to this third-party quant.

No WorldPort or Evennia client exists in this harness.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import time

from ox_ai.agents.crew import CommandOption
from scenarios import counterfactual_decision_trial as cf
from scenarios import g11_memory_ab_trial as g11


QUANTS = ("Q2_K", "Q4_K_M")
INSTRUCTIONS = (
    "Which permitted action should this spaceship crew member attempt next, "
    "based on the evidence, duties and memories? "
    "No action has been executed or verified."
)


class GGUFChoiceModel:
    """Native, label-scoring Decider GGUF engine as Concordia LanguageModel."""

    def __init__(self, engine, descriptions: tuple[str, ...]) -> None:
        self.engine = engine
        self.descriptions = descriptions
        self.calls = 0
        self.last_answer = None

    def sample_choice(self, prompt, responses, *, seed=None):
        del seed
        keys = tuple(responses)
        if not 2 <= len(keys) <= 16 or len(self.descriptions) != len(keys):
            raise ValueError("Invalid finite command menu")
        if len(set(keys)) != len(keys) or not isinstance(prompt, str):
            raise ValueError("Duplicate response keys or invalid prompt")
        criteria = dict(zip(keys, self.descriptions))
        response = self.engine.system_one(
            prompt, {"next_action": {
                "type": "choice", "instructions": INSTRUCTIONS,
                "criteria": criteria,
            }},
        )
        if not isinstance(response, dict):
            raise ValueError("Decider returned no decision object")
        answer = response.get("answers", {}).get("next_action", {})
        chosen = answer.get("choice")
        probs = answer.get("probabilities")
        if not isinstance(probs, dict):
            # Publisher's typed system_one contract uses probabilities.
            # Never fall back to text or freeform generation.
            raise ValueError("Missing native option distribution")
        if (chosen not in criteria or set(probs) != set(criteria)
                or any(type(p) not in (float, int) or not math.isfinite(p)
                       or p < 0 or p > 1 for p in probs.values())
                or not math.isclose(sum(probs.values()), 1, abs_tol=0.02)):
            raise ValueError("Invalid Decider option decision")
        self.calls += 1
        self.last_answer = {
            "choice": chosen, "probabilities": probs,
            "confidence": answer.get("confidence"),
        }
        return keys.index(chosen), chosen, {"decider_gguf": self.last_answer}

    def sample_text(self, *args, **kwargs):
        raise RuntimeError("The Decider decision head must never generate text")


def _check_proposal(agent, request, model):
    if model.calls != 1 or len(agent.pending_requests) != 1:
        raise AssertionError("One inference must leave exactly one pending proposal")
    if request.character_id != agent.identity.character_id:
        raise AssertionError("Proposal recipient diverged")
    if agent.usage.total_calls != 1:
        raise AssertionError("Inference usage count was not preserved")


def run(engine, *, quant: str, checkpoint: dict, max_pairs: int = 24) -> dict:
    if quant not in QUANTS or type(max_pairs) is not int or not 1 <= max_pairs <= 24:
        raise ValueError("Invalid quantisation or case bound")

    g11_rows = []
    for i, spec in enumerate(g11.fixtures()):
        models = {
            arm: GGUFChoiceModel(engine, tuple(o.label for o in spec["options"]))
            for arm in (False, True)
        }
        brains = {arm: g11.build(spec, arm, models[arm])
                  for arm in (False, True)}
        if not g11.matched(brains[False], brains[True]):
            raise AssertionError("G11 actor evidence was not matched")
        for arm in ((False, True) if i % 2 == 0 else (True, False)):
            start = time.perf_counter()
            proposal = brains[arm].decide(spec["options"])
            latency = round(time.perf_counter() - start, 4)
            _check_proposal(brains[arm], proposal, models[arm])
            if proposal.verb not in {o.verb for o in spec["options"]}:
                raise AssertionError("Choice escaped G11 options")
            g11_rows.append({
                "case": spec["name"], "arm": "augmented" if arm else "baseline",
                "expected": spec["expected"], "chosen": proposal.verb,
                "correct": proposal.verb == spec["expected"],
                "latency_seconds": latency,
                "native_choice": models[arm].last_answer,
            })
    g11_summary = {}
    for arm in ("baseline", "augmented"):
        sub = [r for r in g11_rows if r["arm"] == arm]
        g11_summary[arm] = {
            "correct": sum(x["correct"] for x in sub),
            "total": len(sub),
            "median_latency_seconds": statistics.median(
                x["latency_seconds"] for x in sub
            ),
        }

    rows = []
    for spec in cf.fixtures()[:max_pairs]:
        for variant in ("earlier", "changed"):
            options = (
                CommandOption(spec.first_option, spec.first_verb),
                CommandOption(spec.second_option, spec.second_verb),
            )
            model = GGUFChoiceModel(engine, tuple(o.label for o in options))
            brain, offered = cf.make_agent(spec, variant, model)
            start = time.perf_counter()
            proposal = brain.decide(offered, expected_revision=1)
            latency = round(time.perf_counter() - start, 4)
            _check_proposal(brain, proposal, model)
            if proposal.agent_revision != 1:
                raise AssertionError("Incorrect observation revision")
            expected = (spec.expected_earlier if variant == "earlier"
                        else spec.expected_changed)
            rows.append({
                "case": spec.name, "category": spec.category,
                "variant": variant, "expected": expected,
                "chosen": proposal.verb, "correct": proposal.verb == expected,
                "latency_seconds": latency,
                "native_choice": model.last_answer,
            })
    pairs = []
    for i in range(max_pairs):
        earlier, changed = rows[2*i:2*i+2]
        pairs.append({
            "case": earlier["case"],
            "both_correct": earlier["correct"] and changed["correct"],
            "flipped": earlier["chosen"] != changed["chosen"],
        })
    return {
        "experiment": "ox_decider_4b_quantisation_native_choice_v1",
        "quantisation": quant,
        "checkpoint": checkpoint,
        "g11": {"summary": g11_summary, "rows": g11_rows},
        "counterfactual": {
            "decisions": len(rows),
            "correct": sum(r["correct"] for r in rows),
            "pairs": len(pairs),
            "both_correct_pairs": sum(p["both_correct"] for p in pairs),
            "flipped_pairs": sum(p["flipped"] for p in pairs),
            "median_latency_seconds": statistics.median(
                r["latency_seconds"] for r in rows
            ),
            "rows": rows,
            "pair_rows": pairs,
        },
        "world_commands_sent": 0,
        "world_receipts_received": 0,
        "limitations": (
            "One pass through 24 authored pairs; quantised GGUF checkpoint "
            "provenance must be checked against the separate Ollaya BF16 v3 "
            "reference before claiming the same fine-tune. Option "
            "probabilities are diagnostic, not assumed calibrated."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quant", choices=QUANTS, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--checkpoint-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-pairs", type=int, default=24)
    args = parser.parse_args()

    from decider.infer import Decider
    checkpoint = json.loads(args.checkpoint_json.read_text(encoding="utf-8"))
    filename = checkpoint["gguf_file"]
    if (checkpoint["quant"] != args.quant or Path(filename).name != filename
            or not filename.endswith(".gguf")):
        raise ValueError("Checkpoint manifest disagrees with selected quantisation")
    path = args.model_dir / filename
    if not path.is_file():
        raise FileNotFoundError("Pinned GGUF file was not downloaded")

    engine = Decider(
        str(path),
        gguf_options={
            "n_gpu_layers": 0,
            "n_threads": 4,
            "n_ctx": 4096,
            "n_batch": 4096,
            "n_seq_max": 1,
        },
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = run(engine, quant=args.quant, checkpoint=checkpoint,
                 max_pairs=args.max_pairs)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    summary = result["counterfactual"]
    print(json.dumps({
        "quantisation": args.quant,
        "g11": result["g11"]["summary"],
        "counterfactual_correct": summary["correct"],
        "counterfactual_total": summary["decisions"],
        "both_correct_pairs": summary["both_correct_pairs"],
        "total_pairs": summary["pairs"],
        "decision_flips": summary["flipped_pairs"],
        "median_latency_seconds": summary["median_latency_seconds"],
        "world_commands_sent": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
