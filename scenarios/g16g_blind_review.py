"""G16g: produce a genuinely usable blinded human voice review instrument.

Generative data and scorecard are separated. Raw speaker/arm/provider
identity stays in a PRIVATE answer key, never the reviewer sheet.
The neutral trait reference and pseudonymous voice grouping remain
identical across both profile-arm prompts and across providers.

No generated utterance authorizes an action, a ship repair, an
agreement, a diagnosis or a world receipt.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g16g_speech_evaluation import verified_protocol, load_g9_trial

REVIEW_FILE = (
    Path(__file__).resolve().parents[1] /
    "design/prototypes/g16g-blind-review-protocol-v1.json"
)
SHA256_HEX_LEN = 64


def instrument() -> dict:
    spec = json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
    if (spec.get("schema_version") != 1
            or spec.get("status") !=
               "review_instrument_frozen_before_any_human_voice_ratings_not_before_native_generation"
            or len(spec.get("categories", {})) != 5
            or set(spec["categories"]) != {
                "voice_distinctiveness", "profile_fidelity", "grounding",
                "naturalness", "emotional_fit"
            }
            or spec["rating_scale"]["min"] != 1
            or spec["rating_scale"]["max"] != 5
            or spec["review_rules"]["min_independent_reviewers"] != 2):
        raise ValueError("G16g reviewer instrument changed without versioning")
    return spec


def _sha(text: bytes) -> str:
    return hashlib.sha256(text).hexdigest()


def _id(salt: bytes, *parts: str) -> str:
    return hmac.new(salt, json.dumps(parts, separators=(",", ":")).encode(),
                    hashlib.sha256).hexdigest()[:24]


def _verified_native_rows(result: dict) -> list[dict]:
    spec = verified_protocol()
    if (not isinstance(result, dict)
            or result.get("schema") != 1
            or result.get("provider") not in ("qwen-local", "gemini-hosted")
            or result.get("fake_provider") is not False
            or result.get("real_text_generation_measured") is not True
            or result.get("samples") != 48
            or result.get("actors") != 6
            or result.get("scenario_types") != 4
            or result.get("evennia_commands_sent") != 0
            or result.get("action_requests_generated") != 0
            or result.get("model_choice_adopted") is not False
            or len(result.get("rows", ())) != 48):
        raise PermissionError("A complete real-model non-world G16g dataset is required")
    expected = {
        (role, scene["id"], arm)
        for role in spec["roles"] for scene in spec["scenes"]
        for arm in spec["profiles"]
    }
    if (result["provider"] == "qwen-local"
            and (result.get("total_completion_tokens_reported", 0) <= 0
                 or result.get("total_prompt_tokens_reported", 0) <= 0)):
        raise PermissionError("Real Qwen speech must include measured token usage")
    seen = set()
    for row in result["rows"]:
        key = (row.get("role"), row.get("scene"), row.get("profile_arm"))
        if (key not in expected or key in seen
                or row.get("fixture_only") is not False
                or row.get("preselected_speech_intent") != next(
                    scene["speech_intent"] for scene in spec["scenes"]
                    if scene["id"] == key[1]
                )
                or not isinstance(row.get("text"), str)
                or not 1 <= len(row["text"].strip()) <= 1200
                or not isinstance(row.get("model_id"), str)
                or (result["provider"] == "qwen-local"
                    and row.get("model_id") != "qwen3.5-4b-local-q4km")
                or (result["provider"] == "gemini-hosted"
                    and not row.get("model_id", "").startswith("gemini-"))
                or not isinstance(row.get("prompt_sha256"), str)
                or len(row["prompt_sha256"]) != SHA256_HEX_LEN):
            raise PermissionError("A native utterance is missing, forged or mismatched")
        bp = load_g9_trial().g9_blueprint(key[0])
        original = _sha(json.dumps(
            bp.to_record(), sort_keys=True,
            separators=(",", ":")
        ).encode())
        if (row.get("person_id") != bp.person_id
                or row.get("actor_original_blueprint_sha256") != original):
            raise PermissionError("Different actor profile or source history")
        seen.add(key)
    if seen != expected:
        raise PermissionError("Incomplete original six-brain speech factorial")
    return result["rows"]


def prepare(results: list[dict], *, salt: bytes) -> tuple[dict, dict, dict]:
    """One confidential answer key, one anonymous sheet, one blank template."""
    if not isinstance(salt, bytes) or len(salt) < 16:
        raise ValueError("Private review randomization requires >=128-bit salt")
    spec = verified_protocol()
    rubric = instrument()
    if not results:
        raise ValueError("At least one fully evaluated native provider required")
    if len({r.get("provider") for r in results}) != len(results):
        raise ValueError("Duplicate provider/result cannot inflate evidence")
    samples = []
    key_rows = []
    for dataset in results:
        provider = dataset["provider"]
        for row in _verified_native_rows(dataset):
            role, arm, scene_id = (row["role"], row["profile_arm"], row["scene"])
            blueprint = load_g9_trial().g9_blueprint(role)
            traits = dict(blueprint.traits)
            trait_reference = {
                name: traits[name] for name in (
                    "conscientiousness", "risk_tolerance", "authority_challenge",
                    "agreeableness", "collaboration", "openness"
                )
            }
            item = _id(salt, "voice", provider, role, scene_id, arm)
            group = _id(salt, "speaker-group", role)[:12]
            context = next(x for x in spec["scenes"] if x["id"] == scene_id)
            samples.append({
                "blind_id": item,
                "anonymous_speaker_group": group,
                "neutral_original_trait_reference_0_to_100": trait_reference,
                "scenario": scene_id,
                "known_context": context["known_context"],
                "preselected_speech_intent": context["speech_intent"],
                "utterance": row["text"],
            })
            key_rows.append({
                "blind_id": item, "provider": provider,
                "original_role": role, "profile_arm": arm, "scene": scene_id,
                "model_id": row["model_id"],
                "original_prompt_sha256": row["prompt_sha256"],
                "generation_seconds": row["generation_seconds"],
                "prompt_tokens": row.get("prompt_tokens"),
                "completion_tokens": row.get("completion_tokens"),
            })
    if len({x["blind_id"] for x in samples}) != len(samples):
        raise ValueError("Blinded IDs collided, cannot assess independently")
    blinded = {
        "schema": 1, "blind_review": True,
        "providers_hidden": True, "prompt_arms_hidden": True,
        "human_review_needed": True,
        "rubric": rubric["categories"],
        "permitted_flags": rubric["permitted_flags"],
        "items": sorted(samples, key=lambda x: x["blind_id"]),
    }
    secret = {
        "schema": 1, "answer_key_keep_private": True,
        "salt_hex_keep_private": salt.hex(),
        "original_native_provider_count": len(results),
        "items": sorted(key_rows, key=lambda x: x["blind_id"]),
        "blinded_sheet_sha256": _sha(json.dumps(
            blinded, sort_keys=True, separators=(",", ":")
        ).encode()),
    }
    template = {
        "schema": 1, "reviewer_id": "",
        "blinded_sheet_sha256": secret["blinded_sheet_sha256"],
        "ratings": [
            {"blind_id": x["blind_id"],
             **{name: None for name in rubric["categories"]},
             "flags": []}
            for x in blinded["items"]
        ],
    }
    return blinded, secret, template


def summarize_reviews(answer_key: dict, reviews: list[dict]) -> dict:
    """Score only genuinely completed independent human sheets."""
    rubric = instrument()
    key = {row["blind_id"]: row for row in answer_key["items"]}
    required = set(key)
    if len(key) != len(answer_key["items"]) or not required:
        raise PermissionError("The concealed answer key is incomplete")
    if len(reviews) < rubric["review_rules"]["min_independent_reviewers"]:
        raise PermissionError("At least two independently filled human scorecards are required")
    reviewer_ids = set()
    recorded = defaultdict(list)
    flags = defaultdict(set)
    for sheet in reviews:
        reviewer = sheet.get("reviewer_id")
        if (not isinstance(reviewer, str)
                or not 2 <= len(reviewer) <= 80
                or reviewer in reviewer_ids
                or sheet.get("blinded_sheet_sha256")
                   != answer_key["blinded_sheet_sha256"]
                or sheet.get("schema") != 1
                or not isinstance(sheet.get("ratings"), list)):
            raise PermissionError("Invalid or duplicated blind reviewer scorecard")
        reviewer_ids.add(reviewer)
        per_id = {}
        for row in sheet["ratings"]:
            if not isinstance(row, dict):
                raise ValueError("Malformed human scoring entry")
            blind = row.get("blind_id")
            if blind not in required or blind in per_id:
                raise PermissionError("Unknown or duplicate rated utterance")
            scores = {}
            for category in rubric["categories"]:
                score = row.get(category)
                if type(score) is not int or not 1 <= score <= 5:
                    raise ValueError("Incomplete or out-of-range human score")
                scores[category] = score
            reported_flags = row.get("flags")
            if (not isinstance(reported_flags, list)
                    or len(reported_flags) != len(set(reported_flags))
                    or any(v not in rubric["permitted_flags"] for v in reported_flags)):
                raise ValueError("Unrecognized unsupported speech-fidelity flag")
            per_id[blind] = scores
            flags[blind].update(reported_flags)
        if set(per_id) != required:
            raise PermissionError("Every human reviewer must score every utterance")
        for blind, scores in per_id.items():
            recorded[blind].append(scores)
    group = defaultdict(list)
    unsafe = defaultdict(set)
    for blind, scored in recorded.items():
        answer = key[blind]
        label = (answer["provider"], answer["profile_arm"])
        group[label].append({
            "voice": answer["original_role"],
            "scene": answer["scene"],
            "scores": {
                category: statistics.mean(s[category] for s in scored)
                for category in rubric["categories"]
            },
            "flags": sorted(flags[blind]),
        })
        unsafe[label].update(flags[blind])
    summary = []
    for label, rows in sorted(group.items()):
        summary.append({
            "provider": label[0], "profile_arm": label[1],
            "utterances": len(rows),
            "reviewers_per_utterance": len(reviews),
            "mean_ratings": {
                category: statistics.mean(row["scores"][category] for row in rows)
                for category in rubric["categories"]
            },
            "utterances_with_any_fidelity_flag": sum(bool(row["flags"]) for row in rows),
            "flag_categories": sorted(unsafe[label]),
        })
    return {
        "schema": 1,
        "human_review_complete": True,
        "distinct_independent_reviewer_ids": len(reviewer_ids),
        "utterances_reviewed": len(required),
        "per_provider_and_arm": summary,
        "selected_production_speech_provider": None,
        "production_choice_model_unchanged": True,
        "world_commands_sent": 0,
        "limitations": "Descriptive human ratings only. Provider selection additionally requires measured local/hosted price or documented unavailable hosted access, reproducible samples and all G16 safety/soak gates.",
    }


def _dump(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("prepare")
    make.add_argument("--native-results", type=Path, nargs="+", required=True)
    make.add_argument("--public-sheet", type=Path, required=True)
    make.add_argument("--private-key", type=Path, required=True)
    make.add_argument("--blank-template", type=Path, required=True)
    score = commands.add_parser("assess")
    score.add_argument("--private-key", type=Path, required=True)
    score.add_argument("--reviewer-files", type=Path, nargs="+", required=True)
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        datasets = [json.loads(p.read_text(encoding="utf-8"))
                    for p in args.native_results]
        blinded, secret, template = prepare(
            datasets, salt=secrets.token_bytes(16),
        )
        _dump(args.public_sheet, blinded)
        _dump(args.private_key, secret)
        _dump(args.blank_template, template)
        print("OX_G16G_ANONYMOUS_REVIEW_SHEETS_PREPARED",
              len(blinded["items"]))
    else:
        key = json.loads(args.private_key.read_text(encoding="utf-8"))
        reviews = [json.loads(p.read_text(encoding="utf-8"))
                   for p in args.reviewer_files]
        scores = summarize_reviews(key, reviews)
        _dump(args.output, scores)
        print("OX_G16G_TWO_OR_MORE_INDEPENDENT_HUMAN_SHEETS_VALIDATED",
              scores["utterances_reviewed"])


if __name__ == "__main__":
    main()
