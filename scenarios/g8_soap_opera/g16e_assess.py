"""Independent G16e native six-shard aggregator; never cherry-pick roles.

Structural corruption fails the workflow. Behavioral failure is recorded
honestly in the final JSON and must NOT be confused with CI success.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from statistics import median

ROLES = ("lin", "ari", "iona", "mara", "teo", "captain")
ARMS = ("procedural", "independent")
ORDERS = ("canonical", "cycle_left", "cycle_right")
CASES = (
    "g14.verified_mutual_aid", "g14.finite_spare_dispute",
    "g14.approved_watch_relief", "g14.uncertain_private_apology",
    "g16e.peer_review_after_error",
    "g16e.peer_review_after_disappointment",
    "g16e.authorized_watch_swap_personal_cost",
    "g16e.apology_after_broken_trust",
)
REPEATS = CASES[:4]
FROZEN_PREREG_BLOB_SHA = "e8529be931bebb6cda5c00fab90458cf5ef52a3c"
WEIGHTS_HF_REVISION = "3b02c98fa0b19e9daab247d633095b6e8a6cd4c5"
TOKENIZER_HF_REVISION = "d3a78581751d518bbfa9e871a6d84059554d53c5"


def _scores(scores):
    if (not isinstance(scores, dict) or len(scores) != 3
            or any(type(x) not in (int, float) or not math.isfinite(x)
                   or not 0.0 <= x <= 1.0 for x in scores.values())
            or not math.isclose(sum(scores.values()), 1.0, abs_tol=0.02)):
        raise ValueError("Malformed native semantic option score")


def assess(root: Path):
    files = list(root.glob("*.json"))
    if sorted(x.stem for x in files) != sorted(ROLES):
        raise FileNotFoundError("All six genuine G16e actor shards are mandatory")
    all_rows = {}
    all_repeats = {}
    evidence_roles = set()
    catalog_hashes = set()
    weight_hashes = set()
    for file in files:
        record = json.loads(file.read_text(encoding="utf-8"))
        role = file.stem
        if (record.get("schema") != 1 or record.get("role") != role
                or record.get("status") != "g16e_native_actor_evaluated"
                or record.get("engine") != "decider-q4"
                or record.get("source_g9_run") != 39872687597
                or record.get("native_forwards") != 156
                or record.get("hypothetical_only") is not True
                or record.get("world_commands_sent") != 0
                or type(record.get("source_world_maintenance_receipts")) is not int
                or record["source_world_maintenance_receipts"] < 1
                or len(record.get("factorial_rows", [])) != 48
                or len(record.get("repeat_controls", [])) != 4
                or not isinstance(record.get("source_brain_sha256"), str)
                or len(record["source_brain_sha256"]) != 64
                or not isinstance(record.get("catalog_sha256"), str)
                or len(record["catalog_sha256"]) != 64
                or record.get("frozen_prereg_git_blob_sha")
                   != FROZEN_PREREG_BLOB_SHA
                or not isinstance(record.get("native_model_manifest"), dict)
                or record["native_model_manifest"].get("model") != "decider-q4"
                or record["native_model_manifest"].get("hf_revision")
                   != WEIGHTS_HF_REVISION
                or record["native_model_manifest"].get("tokenizer_revision")
                   != TOKENIZER_HF_REVISION
                or not isinstance(record["native_model_manifest"].get("sha256"), str)
                or len(record["native_model_manifest"]["sha256"]) != 64):
            raise PermissionError("Incomplete or mismatched G16e native actor")
        weight_hashes.add(record["native_model_manifest"]["sha256"])
        catalog_hashes.add(record["catalog_sha256"])
        evidence_roles.add((record["source_brain_sha256"], record["evidence_digest"]))
        rows, repeats = {}, {}
        for is_repeat, source in ((False, record["factorial_rows"]),
                                  (True, record["repeat_controls"])):
            for row in source:
                if (row.get("role") != role
                        or row.get("source_g9_run") != 39872687597
                        or row.get("source_brain_sha256") != record["source_brain_sha256"]
                        or row.get("unchanged_actor_evidence_digest") != record["evidence_digest"]
                        or row.get("catalog_sha256") != record["catalog_sha256"]
                        or row.get("character_id", "")[:1] != "#"
                        or row.get("hypothetical_only") is not True
                        or row.get("world_commands_sent") != 0
                        or row.get("native_calls") != 3
                        or row.get("repeated") is not is_repeat
                        or row.get("scene") not in CASES
                        or row.get("arm") not in ARMS
                        or row.get("order") not in ORDERS
                        or not isinstance(row.get("prompt_control_sha256"), str)
                        or len(row["prompt_control_sha256"]) != 64):
                    raise PermissionError("G16e actor row provenance changed")
                _scores(row["raw_scores"])
                scores = row["raw_scores"]
                top = sorted(scores.values(), reverse=True)
                if not math.isclose(top[0] - top[1],
                                    row["native_score_margin"], abs_tol=1e-8):
                    raise ValueError("Native score margin does not match actual options")
                best = max(scores.values())
                native_winner = next(k for k in sorted(scores)
                                     if scores[k] >= best - 1e-9)
                if native_winner != row["raw_choice"]:
                    raise ValueError("Recorded native winner is not the semantic argmax")
                catalog_keys = sorted(scores)
                if (sorted(row["caller_action_keys"]) != catalog_keys
                        or row["canonical_action_keys"] != catalog_keys):
                    raise ValueError("Native model menu did not use stable semantic keys")
                # Audit 3 ACTUAL native System One forwards, not a claimed
                # forward count or an opaque averaged score. Verify each
                # permutation, code-to-semantic probability and final mean.
                passes = row.get("native_passes")
                if not isinstance(passes, list) or len(passes) != 3:
                    raise PermissionError("Three complete native forwards are mandatory")
                native_pick_list = []
                for offset, passed in enumerate(passes):
                    expected_rotation = catalog_keys[offset:] + catalog_keys[:offset]
                    if (passed.get("native_position") != offset
                            or passed.get("position_to_semantic_key")
                               != expected_rotation
                            or not isinstance(passed.get("position_to_code"), list)
                            or len(passed["position_to_code"]) != 3
                            or len(set(passed["position_to_code"])) != 3
                            or not isinstance(passed.get("prompt_sha256"), str)
                            or len(passed["prompt_sha256"]) != 64):
                        raise PermissionError("G16e native rotation or prompt provenance changed")
                    pass_scores = passed.get("semantic_scores")
                    code_scores = passed.get("response_code_scores")
                    _scores(pass_scores)
                    _scores(code_scores)
                    if set(pass_scores) != set(catalog_keys):
                        raise PermissionError("Unexpected native semantic options")
                    if set(code_scores) != set(passed["position_to_code"]):
                        raise ValueError("Native response-token codes were not complete")
                    for code, key in zip(passed["position_to_code"],
                                         passed["position_to_semantic_key"]):
                        if not math.isclose(code_scores[code], pass_scores[key],
                                            abs_tol=1e-10):
                            raise ValueError("Native letter-to-semantic score mapping changed")
                    native_best = max(code_scores.values())
                    winning_codes = [code for code in passed["position_to_code"]
                                     if code_scores[code] >= native_best - 1e-9]
                    native_pick = passed.get("selected_semantic_key")
                    if native_pick not in {
                        passed["position_to_semantic_key"][
                            passed["position_to_code"].index(code)]
                        for code in winning_codes
                    }:
                        raise ValueError("Native picked action was not a scored winner")
                    native_pick_list.append(native_pick)
                if len({x["prompt_sha256"] for x in passes}) != 1:
                    raise PermissionError("Three forwards did not share actor-private input")
                for key in catalog_keys:
                    average = sum(passed["semantic_scores"][key]
                                  for passed in passes) / 3.0
                    if not math.isclose(average, scores[key], abs_tol=1e-10):
                        raise ValueError("Advertised G15 mean mismatches actual native scores")
                adjusted = row.get("adjusted")
                if row.get("safety_refused"):
                    if (row.get("menu_key") != "g14.finite_spare_dispute"
                            or top[0] >= 0.85
                            or adjusted is not None or row.get("adjusted_choice") is not None):
                        raise ValueError("Unsafe refusal was forged")
                else:
                    if (not isinstance(adjusted, dict)
                            or adjusted.get("selected_semantic_key") != row["adjusted_choice"]
                            or adjusted["selected_semantic_key"] not in scores
                            or adjusted.get("underlying_native_calls") != 3
                            or set(adjusted["raw_scores"]) != set(scores)
                            or not math.isclose(sum(adjusted["adjusted_scores"].values()), 1,
                                                abs_tol=1e-8)):
                        raise ValueError("Adjusted choice lacks authentic full native scores")
                    if adjusted.get("safety_locked") and (
                            row["menu_key"] != "g14.finite_spare_dispute"
                            or adjusted["selected_semantic_key"] != native_winner
                            or any(v != 0.0 for v in adjusted["shifts"].values())):
                        raise PermissionError("A locked safety case was overridden")
                key = (row["scene"], row["arm"], row["order"])
                dest = repeats if is_repeat else rows
                if key in dest:
                    raise ValueError("Duplicate scenario/trait/order member")
                dest[key] = row
        expected = {
            (case, arm, order) for case in CASES
            for arm in ARMS for order in ORDERS
        }
        if set(rows) != expected or set(repeats) != {
            (case, "procedural", "canonical") for case in REPEATS
        }:
            raise PermissionError("Incomplete scenario factorial or repeat controls")

        # A matched counterfactual changes only the private profile: the
        # normalized *other* prompt and actor evidence must be identical.
        for scene in CASES:
            digests = {
                rows[(scene, arm, order)]["prompt_control_sha256"]
                for arm in ARMS for order in ORDERS
            }
            if len(digests) != 1:
                raise PermissionError("G16e changed prompt outside the profile or case")
        all_rows[role], all_repeats[role] = rows, repeats

    if len(catalog_hashes) != 1 or len(evidence_roles) != 6 or len(weight_hashes) != 1:
        raise PermissionError("Cross-actor evidence, weight hash or catalog mismatch")

    non_safety_cases = [c for c in CASES if c != "g14.finite_spare_dispute"]
    changed_adjusted = 0
    changed_raw = 0
    order_invariant = 0
    order_total = 0
    repeats_equal = 0
    repeats_near_scores = 0
    locked_total = 0
    locked_overrides = 0
    safety_refusals = 0
    changed_pairs = []
    new_margins = defaultdict(list)
    for role in ROLES:
        rows = all_rows[role]
        for scene in CASES:
            for arm in ARMS:
                group = [rows[(scene, arm, order)] for order in ORDERS]
                choices = [
                    item["adjusted_choice"] if not item["safety_refused"]
                    else "<safety_refused>"
                    for item in group
                ]
                order_total += 1
                order_invariant += int(len(set(choices)) == 1)
                locked_total += sum(bool(item["adjusted"] and
                                         item["adjusted"]["safety_locked"])
                                    for item in group)
                safety_refusals += sum(item["safety_refused"] for item in group)
                locked_overrides += sum(bool(item["adjusted"] and
                                             item["adjusted"]["safety_locked"] and
                                             item["adjusted_choice"] != item["raw_choice"])
                                        for item in group)
                if scene.startswith("g16e."):
                    new_margins[scene].extend(item["native_score_margin"]
                                              for item in group)
            if scene in non_safety_cases:
                p = rows[(scene, "procedural", "canonical")]
                i = rows[(scene, "independent", "canonical")]
                mismatch = p["adjusted_choice"] != i["adjusted_choice"]
                changed_adjusted += int(mismatch)
                changed_raw += int(p["raw_choice"] != i["raw_choice"])
                changed_pairs.append({
                    "actor": role, "case": scene, "changed_adjusted": mismatch,
                    "raw_changed": p["raw_choice"] != i["raw_choice"],
                    "procedural": p["adjusted_choice"],
                    "independent": i["adjusted_choice"],
                })
        for scene in REPEATS:
            original = rows[(scene, "procedural", "canonical")]
            repeat = all_repeats[role][(scene, "procedural", "canonical")]
            repeats_equal += int(
                original["prompt_control_sha256"] ==
                repeat["prompt_control_sha256"] and
                original["adjusted_choice"] == repeat["adjusted_choice"] and
                original["raw_choice"] == repeat["raw_choice"] and
                original["safety_refused"] == repeat["safety_refused"]
            )
            repeats_near_scores += int(
                all(abs(original["raw_scores"][k] - repeat["raw_scores"][k]) <= 0.01
                    for k in original["raw_scores"])
            )
    valid_new = sum(median(scores) < 0.30 for scores in new_margins.values())
    thresholds = {
        "four_new_non_ceiling": valid_new == 4,
        "personality_differentiation_at_least_11_of_42": changed_adjusted >= 11,
        "zero_locked_safety_overrides": locked_overrides == 0,
        "all_caller_orders_invariant": order_invariant == order_total == 96,
        "24_same_input_choices": repeats_equal == 24,
        "24_native_scores_within_0_01": repeats_near_scores == 24,
    }
    return {
        "schema": 1,
        "status": "g16e_native_structural_integrity_verified",
        "not_a_world_outcome": True,
        "native_forwards": 936,
        "actors": list(ROLES),
        "cases": list(CASES),
        "source_g9_run": 39872687597,
        "catalog_sha256": next(iter(catalog_hashes)),
        "native_gguf_sha256": next(iter(weight_hashes)),
        "frozen_prereg_git_blob_sha": FROZEN_PREREG_BLOB_SHA,
        "unique_non_safety_personality_pairs": 42,
        "changed_adjusted": changed_adjusted,
        "changed_raw": changed_raw,
        "adjusted_disagreement_rate": changed_adjusted / 42,
        "raw_disagreement_rate": changed_raw / 42,
        "caller_order_invariant": order_invariant,
        "caller_order_total": order_total,
        "repeats_identical": repeats_equal,
        "repeats_native_scores_within_0_01": repeats_near_scores,
        "locked_safety_rows": locked_total,
        "safety_refusals": safety_refusals,
        "locked_overrides": locked_overrides,
        "median_new_scene_margins": {
            k: median(v) for k, v in sorted(new_margins.items())
        },
        "non_ceiling_new_scenes": valid_new,
        "acceptance_checks": thresholds,
        "behavioural_acceptance": all(thresholds.values()),
        "note": ("A successful aggregation job proves integrity of complete native data, "
                 "not behavioural success unless every preregistered threshold is true."),
        "non_safety_pair_details": changed_pairs,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = assess(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "native_calls": result["native_forwards"],
        "changed_adjusted": result["changed_adjusted"],
        "changed_raw": result["changed_raw"],
        "order_invariant": result["caller_order_invariant"],
        "repeat_agreement": result["repeats_identical"],
        "safety_refusals": result["safety_refusals"],
        "passed_behavior": result["behavioural_acceptance"],
    }, sort_keys=True))
    print("OX_G16E_SIX_ROLE_STRUCTURAL_EVIDENCE_PASS")
    print("OX_G16E_BEHAVIOURAL_ACCEPTANCE_" +
          ("PASS" if result["behavioural_acceptance"] else "FAIL"))


if __name__ == "__main__":
    main()
