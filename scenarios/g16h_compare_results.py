"""G16h independent complete native model comparison; no model adoption."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from g16h_counterfactual_cases import fixtures

CASES = tuple(c.name for c in fixtures())
VARIANTS = ("earlier","changed")
ORDERS = ("canonical","reversed")
ROWS = {(c,v,o) for c in CASES for v in VARIANTS for o in ORDERS}
CASE_BY_NAME = {c.name:c for c in fixtures()}
DECIDER_GGUF_SHA256 = "c03deb433d539ef49579fca5a015d5090c739a331448493aded7a57ad9b4261b"
QWEN_GGUF_SHA256 = "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4"
DECIDER_WEIGHT_REVISION = "3b02c98fa0b19e9daab247d633095b6e8a6cd4c5"
DECIDER_TOKENIZER_REVISION = "d3a78581751d518bbfa9e871a6d84059554d53c5"



def check_native_record(row):
    model = row.get("scorer_record")
    if (not isinstance(model, dict)
            or model.get("native_forwards") != 2
            or model.get("selected_semantic_key") != row.get("chosen")
            or len(model.get("passes", ())) != 2
            or set(model.get("semantic_scores", ())) != set(row["offered_verb_order"])):
        raise PermissionError("Native Decider did not provide two complete passes")
    keys = set(row["offered_verb_order"])
    rotated = set()
    for passed in model["passes"]:
        order = passed.get("code_positions")
        scores = passed.get("semantic_scores")
        if (not isinstance(order, list) or set(order) != keys
                or not isinstance(scores, dict) or set(scores) != keys
                or passed.get("selected_key") not in keys
                or any(type(x) not in (float,int) or
                       not math.isfinite(x) or not 0<=x<=1
                       for x in scores.values())
                or not math.isclose(sum(scores.values()),1,abs_tol=0.02)):
            raise ValueError("Malformed native Decider score/pass")
        best = max(scores.values())
        eligible = {key for key, prob in scores.items() if prob >= best - 1e-9}
        if passed["selected_key"] not in eligible:
            raise ValueError("A native System One pass selected a nonwinning score")
        rotated.add(order[0])
    if rotated != keys:
        raise PermissionError("Counterfactual scorer failed code-position balance")
    for key in keys:
        if not math.isclose(model["semantic_scores"][key], sum(
            part["semantic_scores"][key] for part in model["passes"]
        )/2, abs_tol=1e-10):
            raise ValueError("Native balanced score not calculated from recorded passes")
    mean_scores = model["semantic_scores"]
    best = max(mean_scores.values())
    winner = next(key for key in sorted(keys)
                  if mean_scores[key] >= best - 1e-9)
    if winner != row["chosen"]:
        raise ValueError("The recorded chosen action differs from native semantic argmax")


def verified_rows(obj, provider):
    if (obj.get("schema") != 1
            or obj.get("provider") != provider
            or obj.get("fake_provider") is not False
            or obj.get("real_native_measurement") is not True
            or obj.get("source_case_count") != 24
            or obj.get("candidate_decisions") != 96
            or obj.get("model_forwards") != (192 if provider=="decider-q4" else 96)
            or obj.get("world_commands_sent") != 0
            or obj.get("world_receipts_claimed") != 0
            or obj.get("adopted_model_decision") is not False
            or not isinstance(obj.get("model_provenance"),dict)
            or len(obj.get("rows",[])) != 96):
        raise PermissionError("Missing true native matched 24-case model evidence")
    metadata = obj["model_provenance"]
    if provider == "decider-q4":
        if (metadata.get("model") != "decider-q4"
                or metadata.get("sha256") != DECIDER_GGUF_SHA256
                or metadata.get("hf_revision") != DECIDER_WEIGHT_REVISION
                or metadata.get("tokenizer_revision") != DECIDER_TOKENIZER_REVISION
                or metadata.get("size") != 2708804928):
            raise PermissionError("Source native Decider weights or publisher revisions differ")
    elif (metadata.get("model") != "qwen3.5-4b"
          or metadata.get("sha256") != QWEN_GGUF_SHA256):
        raise PermissionError("Qwen chat result was not the verified original GGUF")
    evidence = {}
    for row in obj["rows"]:
        key=(row.get("case"),row.get("variant"),row.get("caller_order"))
        if key not in ROWS:
            raise PermissionError("Unexpected historical authored case")
        original = CASE_BY_NAME[key[0]]
        source_observation = original.earlier if key[1] == "earlier" else original.changed
        authored_expected = (original.expected_earlier if key[1] == "earlier"
                             else original.expected_changed)
        original_order = [original.first_verb, original.second_verb]
        offered_order = (original_order if key[2] == "canonical"
                         else list(reversed(original_order)))
        if (key in evidence
                or row.get("expected") != authored_expected
                or row.get("category") != original.category
                or row.get("offered_verb_order") != offered_order
                or row.get("observed_sha256")
                   != hashlib.sha256(source_observation.encode("utf-8")).hexdigest()
                or row.get("recollection_sha256")
                   != hashlib.sha256(original.recollection.encode("utf-8")).hexdigest()
                or type(row.get("expected_position")) is not int
                or row["expected_position"] not in (0,1)
                or not isinstance(row.get("offered_verb_order"), list)
                or len(row["offered_verb_order"])!=2
                or len(set(row["offered_verb_order"]))!=2
                or row["offered_verb_order"][row["expected_position"]]!=row.get("expected")
                or row.get("chosen") not in row["offered_verb_order"]
                or row.get("correct") is not (row["chosen"]==row["expected"])
                or row.get("world_commands_sent") != 0
                or row.get("native_passes") != (2 if provider=="decider-q4" else 1)
                or type(row.get("seconds")) not in (int,float)
                or not math.isfinite(row["seconds"]) or row["seconds"] < 0
                or not isinstance(row.get("prompt_sha256"),str)
                or len(row["prompt_sha256"])!=64
                or not isinstance(row.get("observed_sha256"),str)
                or len(row["observed_sha256"])!=64):
            raise PermissionError("Incomplete or corrupted option-balanced native row")
        if provider=="decider-q4":
            check_native_record(row)
        elif row.get("scorer_record") is not None:
            raise ValueError("Qwen chat cannot claim native System One probability record")
        evidence[key]=row
    if set(evidence)!=ROWS:
        raise PermissionError("Not all 24 cases, variants and orders were evaluated")
    for case in fixtures():
        for variant in VARIANTS:
            a=evidence[(case.name,variant,"canonical")]
            b=evidence[(case.name,variant,"reversed")]
            if (a["observed_sha256"]!=b["observed_sha256"]
                    or a["offered_verb_order"]!=list(reversed(b["offered_verb_order"]))):
                raise PermissionError("Caller option-order test changed evidence or actions")
    return evidence


def compare(decider_path:Path,qwen_path:Path):
    decider=json.loads(decider_path.read_text(encoding="utf-8"))
    qwen=json.loads(qwen_path.read_text(encoding="utf-8"))
    d=verified_rows(decider,"decider-q4")
    q=verified_rows(qwen,"qwen3.5-4b")
    for key in ROWS:
        if (d[key]["observed_sha256"]!=q[key]["observed_sha256"]
                or d[key]["recollection_sha256"]!=q[key]["recollection_sha256"]
                or d[key]["prompt_sha256"]!=q[key]["prompt_sha256"]
                or d[key]["expected"]!=q[key]["expected"]
                or d[key]["expected_position"]!=q[key]["expected_position"]):
            raise PermissionError("Matched provider branches used different Concordia evidence/prompt")
    outcomes={}
    for provider,data in (("decider-q4",d),("qwen3.5-4b",q)):
        by_order={}
        for order in ORDERS:
            both=sum(
                data[(case.name,"earlier",order)]["correct"] and
                data[(case.name,"changed",order)]["correct"]
                for case in fixtures()
            )
            by_order[order]=both
        outcomes[provider]={
            "both_correct_of_24_by_order":by_order,
            "decisions_correct_of_96":sum(x["correct"] for x in data.values()),
            "accuracy_expected_first_position":sum(
                x["correct"] for x in data.values() if x["expected_position"]==0
            )/48.0,
            "accuracy_expected_second_position":sum(
                x["correct"] for x in data.values() if x["expected_position"]==1
            )/48.0,
            "semantic_order_consistency_of_48":sum(
                data[(case.name,variant,"canonical")]["chosen"] ==
                data[(case.name,variant,"reversed")]["chosen"]
                for case in fixtures() for variant in VARIANTS
            ),
            "median_seconds_per_decision":median(x["seconds"] for x in data.values()),
            "underlying_forwards_total":192 if provider=="decider-q4" else 96,
        }
    return {
        "schema":1,
        "status":"g16h_two_real_native_model_artifacts_reconciled",
        "total_original_G11_pairs":24,
        "caller_positions_for_expected_answer":{str(i):48 for i in (0,1)},
        "matched_bounded_decisions_per_model":96,
        "observed_metrics":outcomes,
        "selected_production_action_scorer":None,
        "production_personality_flag_enabled":False,
        "world_commands_sent":0,
        "limitations":(
            "G11 authored cases are a small evidence/recovery/permission benchmark, "
            "not an operational world or natural personality experiment. "
            "Decider uses two native forward passes per model choice, Qwen one "
            "generative chat choice. Full G16e/g/f and soak acceptance required."
        ),
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--decider",required=True,type=Path)
    p.add_argument("--qwen",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    result=compare(a.decider,a.qwen)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result["observed_metrics"],sort_keys=True))
    print("OX_G16H_REAL_MATCHED_OPTION_ORDER_MODEL_COMPARISON_PASS")


if __name__=="__main__":
    main()
