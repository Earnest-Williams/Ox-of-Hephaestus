"""Build a self-contained OFFLINE G16g blind review HTML without an answer key.

Reads only a public blind reviewer sheet and blank scorecard (from
g16g_blind_review.py); provider, prompt arm, original role and secret salt
must remain exclusively in the separately stored answer-key JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


REVIEW_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "design/prototypes/g16g-blind-review-template.html"
)
PACK_SHEET = "g16g_blinded_review_sheet.json"
PACK_BLANK = "g16g_blank_reviewer_template.json"
DIMENSIONS = (
    "voice_distinctiveness", "profile_fidelity", "grounding",
    "naturalness", "emotional_fit",
)
PRIVATE_KEYS = {
    "provider", "model", "profile_arm", "original_role",
    "person_id", "salt_hex_keep_private", "model_id",
}


def validated_public_review(sheet: dict, blank: dict) -> None:
    if (sheet.get("schema") != 1
            or sheet.get("blind_review") is not True
            or sheet.get("prompt_arms_hidden") is not True
            or sheet.get("human_review_needed") is not True
            or (sheet.get("providers_hidden") is not True
                and sheet.get("source_provider_hidden") is not True)
            or not isinstance(sheet.get("items"), list)
            or not len(sheet["items"]) in (48, 96)
            or set(sheet.get("rubric", {})) != set(DIMENSIONS)
            or not isinstance(sheet.get("permitted_flags"), list)
            or blank.get("schema") != 1
            or not isinstance(blank.get("ratings"), list)
            or len(blank["ratings"]) != len(sheet["items"])):
        raise PermissionError("Complete, human-unscored G16g blind review data required")
    canonical = json.dumps(sheet, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != blank.get("blinded_sheet_sha256"):
        raise PermissionError("Public reviewer sheet and blank template do not match")
    identifiers = [r.get("blind_id") for r in sheet["items"]]
    if (len(set(identifiers)) != len(identifiers)
            or any(not isinstance(k, str) or len(k) != 24 for k in identifiers)):
        raise ValueError("Malformed blinded reviewer identifier mapping")
    if set(r.get("blind_id") for r in blank["ratings"]) != set(identifiers):
        raise PermissionError("Blind template dropped or changed an utterance")
    if any(name in sheet for name in ("answer_key", "original_actor_names", "provider_name")):
        raise PermissionError("Private answer key cannot enter public review")
    for row in sheet["items"]:
        if (not isinstance(row, dict)
                or PRIVATE_KEYS.intersection(row)
                or not isinstance(row.get("utterance"), str)
                or not 1 <= len(row["utterance"].strip()) <= 1200
                or not isinstance(row.get("anonymous_speaker_group"), str)
                or not isinstance(row.get("known_context"), str)
                or not isinstance(row.get("preselected_speech_intent"), str)
                or not isinstance(row.get("neutral_original_trait_reference_0_to_100"), dict)
                or len(row["neutral_original_trait_reference_0_to_100"]) != 6):
            raise PermissionError("Blinded sample absent, ungrounded or unmasked")
    for row in blank["ratings"]:
        if (set(row) != {"blind_id", *DIMENSIONS, "flags"}
                or any(row[k] is not None for k in DIMENSIONS)
                or row["flags"] != []):
            raise ValueError("The supplied scorecard is pre-rated or malformed")


def embed_json(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c").replace(">", "\\u003e")
        .replace("&", "\\u0026").replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render(sheet: dict, blank: dict) -> str:
    validated_public_review(sheet, blank)
    source = REVIEW_TEMPLATE.read_text(encoding="utf-8")
    if (source.count("const sheet = __BLIND_SHEET__;") != 1
            or source.count("const template = __BLANK_TEMPLATE__;") != 1):
        raise RuntimeError("Reviewed static HTML template has changed")
    return (source.replace("__BLIND_SHEET__", embed_json(sheet))
                  .replace("__BLANK_TEMPLATE__", embed_json(blank)))


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pack", type=Path, help="Public reviewer ZIP only; never private key")
    group.add_argument("--sheet", type=Path, help="Public blinded JSON sheet")
    parser.add_argument("--blank", type=Path, help="Required with --sheet")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.pack:
        if args.blank is not None:
            parser.error("--blank must be omitted with --pack")
        with zipfile.ZipFile(args.pack) as bundle:
            sheet = json.loads(bundle.read(PACK_SHEET))
            blank = json.loads(bundle.read(PACK_BLANK))
    else:
        if args.blank is None:
            parser.error("--sheet requires --blank")
        sheet = json.loads(args.sheet.read_text(encoding="utf-8"))
        blank = json.loads(args.blank.read_text(encoding="utf-8"))
    html = render(sheet, blank)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print("OX_G16G_PUBLIC_OFFLINE_REVIEWER_HTML_READY", len(sheet["items"]))


if __name__ == "__main__":
    main()
