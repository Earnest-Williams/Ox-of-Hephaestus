"""G16e preregistered six-actor REAL native behavioral evaluation.

This is a hypothetical isolated-actor experiment, never Evennia work.
All raw/adjusted choices share exactly the same three native G15 forwards.
The experiment is not an adoption test for world authority or dialogue.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from ox_ai.agents.crew import CrewAgent
from ox_ai.inference.position_balanced_choice import PositionBalancedDeciderChoiceModel
from ox_ai.runtime.disposition_goap import actor_dispositions
from ox_ai.inference.disposition_choice import score_personality_choice
from ox_contracts import load_catalog

from g13_matched_personality import (
    ROLES, BRAIN_SHA256, authenticated_archive, actor_archive,
    last_counterpart, load_g9_trial, isolated_snapshot,
    evidence_digest, ProfileAuditor,
)
from g14_profile_salience import CASES as G14_CASES, menu as g14_menu, ORDERS

ARMS = ("procedural", "independent")
ENGINE_CHOICES = ("fixture", "decider-q4")
PREREG = Path(__file__).resolve().parents[2] / (
    "design/prototypes/g16e-preregistration-v1.json"
)
SEED = "ox-g16e-native-v1"
FROZEN_PREREG_BLOB_SHA = "e8529be931bebb6cda5c00fab90458cf5ef52a3c"


class FakePositionBiasedEngine:
    """Mock scoring solely for structural testing, NOT native quality."""
    def system_one(self, prompt, questions):
        criteria = questions["next_action"]["criteria"]
        codes = list(criteria)
        probabilities = {
            code: (0.80 if i == 0 else 0.10)
            for i, code in enumerate(codes)
        }
        return {"answers": {"next_action": {
            "choice": codes[0], "probabilities": probabilities,
        }}}


class ObservedNativeForwards:
    """Record each actual native score vector without changing the engine.

    Reports semantic scores and native code positions for each of the three
    forwards. Prompts themselves remain actor-private; only SHA-256 is stored.
    """

    def __init__(self, engine, options):
        self.engine = engine
        self.label_to_key = {description: key for key, description in options}
        if len(self.label_to_key) != 3:
            raise ValueError("Native observation requires distinct option labels")
        self.records = []

    def system_one(self, prompt, questions):
        criteria = questions["next_action"]["criteria"]
        native = self.engine.system_one(prompt, questions)
        answer = native["answers"]["next_action"]
        scores = answer["probabilities"]
        if (len(criteria) != 3 or set(scores) != set(criteria)
                or any(not isinstance(v, (int, float))
                       or not math.isfinite(v) or not 0 <= v <= 1
                       for v in scores.values())
                or not math.isclose(sum(scores.values()), 1.0, abs_tol=0.02)):
            raise ValueError("Unverified native Decider pass")
        keys = [self.label_to_key[description] for description in criteria.values()]
        chosen_code = answer["choice"]
        if chosen_code not in criteria:
            raise ValueError("Unrecognized native chosen code")
        self.records.append({
            "native_position": len(self.records),
            "position_to_code": list(criteria),
            "position_to_semantic_key": keys,
            "semantic_scores": {
                self.label_to_key[label]: float(scores[code])
                for code, label in criteria.items()
            },
            "response_code_scores": {code: float(scores[code]) for code in criteria},
            "selected_semantic_key": self.label_to_key[criteria[chosen_code]],
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        })
        return native



def fixed_protocol():
    raw_manifest = PREREG.read_bytes()
    git_blob_hash = hashlib.sha1(
        b"blob " + str(len(raw_manifest)).encode("ascii") + bytes((0,)) + raw_manifest
    ).hexdigest()
    if git_blob_hash != FROZEN_PREREG_BLOB_SHA:
        raise PermissionError("G16e preregistration changed after being frozen")
    protocol = json.loads(raw_manifest)
    if (protocol.get("schema_version") != 1
            or protocol.get("status") != "preregistered_before_native_G16e"
            or protocol["design_facts"]["total_planned_native_forwards"] != 936
            or len(protocol.get("scenarios", ())) != 8
            or tuple(protocol["design_facts"]["caller_orders"]) != ORDERS
            or protocol["design_facts"]["models"] != [
                "Decider 4B Q4_K_M native G15 three-pass scorer"
            ]):
        raise ValueError("G16e preregistration changed without versioning")
    original = {case.key: case for case in G14_CASES}
    catalog = load_catalog()
    scenarios = []
    for row in protocol["scenarios"]:
        if row["source"] == "g14":
            key = row["id"].removeprefix("g14.")
            if key not in original or row["id"] != "g14." + key:
                raise ValueError("Unknown published G14 control scene")
            case = original[key]
        else:
            if row["source"] != "preregistered_new":
                raise ValueError("Unknown non-ceiling scenario source")
            menu_key = row["menu_key"]
            key = menu_key.removeprefix("g14.")
            if key not in original or not row["id"].startswith("g16e."):
                raise ValueError("New G16e case must reuse exactly an authored G14 menu")
            case = replace(original[key], context=row["context"])
        key = "g14." + case.key
        if row["menu_key"] != key:
            raise ValueError("Scenario action menu differs from its fixed G14 menu")
        menu = catalog.menu(key)
        if menu.safety_critical != row["safety"]:
            raise ValueError("Scenario may not silently change its safety classification")
        actual = {
            ("consider." + label, "g14." + case.key, ())
            for label, _ in case.options
        }
        if {o.signature for o in menu.options} != actual:
            raise ValueError("G14 menu no longer matches authored G16a action tags")
        scenarios.append((row, case, menu))
    if (len({row["id"] for row, _, _ in scenarios}) != 8
            or sum(row["source"] == "preregistered_new" for row, _, _ in scenarios) != 4
            or sum(row["safety"] for row, _, _ in scenarios) != 1):
        raise ValueError("G16e case cardinality or safety classification changed")
    return protocol, tuple(scenarios), catalog


def evaluate_role(root: Path, role: str, *, engine_name: str,
                  gguf_path: Path | None = None,
                  model_manifest: Path | None = None):
    if role not in ROLES or engine_name not in ENGINE_CHOICES:
        raise ValueError("Expected a preregistered G9 actor and inference provider")
    protocol, scenes, catalog = fixed_protocol()
    world, world_report = authenticated_archive(root)
    original = actor_archive(root, role)
    trial = load_g9_trial()
    if original["character_blueprint"] != trial.g9_blueprint(role).to_record():
        raise PermissionError("Actor-specific authentic original profile changed")
    if original.get("pending_requests"):
        raise PermissionError("Unresolved world operation cannot enter G16e")
    original_evidence = evidence_digest(original)
    counterpart = last_counterpart(world, role)
    peer_name = trial.ROLES[counterpart][0]
    model_engine = FakePositionBiasedEngine() if engine_name == "fixture" else None
    model_metadata = None
    if engine_name == "decider-q4":
        if (gguf_path is None or model_manifest is None
                or not gguf_path.is_file() or not model_manifest.is_file()):
            raise FileNotFoundError("Native GGUF and exact weight manifest are required")
        model_metadata = json.loads(model_manifest.read_text(encoding="utf-8"))
        if (model_metadata.get("model") != "decider-q4"
                or model_metadata.get("hf_revision") != "3b02c98fa0b19e9daab247d633095b6e8a6cd4c5"
                or model_metadata.get("tokenizer_revision") != "d3a78581751d518bbfa9e871a6d84059554d53c5"
                or not isinstance(model_metadata.get("sha256"), str)
                or len(model_metadata["sha256"]) != 64
                or model_metadata.get("size") != gguf_path.stat().st_size):
            raise PermissionError("Unpinned native Decider model revision or weights")
        digest = hashlib.sha256()
        with gguf_path.open("rb") as handle:
            while chunk := handle.read(8 * 1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != model_metadata["sha256"]:
            raise PermissionError("Real native GGUF differs from the published weight manifest")
    rows = []
    repeats = []
    native_forwards = 0

    def one(row, case, tagged_menu, *, arm, order, repeated=False):
        nonlocal model_engine, native_forwards
        saved, profile = isolated_snapshot(original, arm)
        if (saved["identity"] != original["identity"]
                or evidence_digest(saved) != original_evidence):
            raise PermissionError("Experiment changed actor-private evidence")
        # Preserve the caller's proposed display order for reporting but
        # canonicalize the actual Concordia model options by stable semantic
        # identity, exactly as the G16c opt-in path does in real runtime.
        caller_offered = g14_menu(case, peer_name, order)
        native_offered = tuple(sorted(
            caller_offered,
            key=lambda x: tagged_menu.by_command(
                x.verb, x.target, x.arguments
            ).semantic_key,
        ))
        options = tuple(
            (tagged_menu.by_command(x.verb, x.target, x.arguments).semantic_key,
             x.label) for x in native_offered
        )
        if len(options) != 3 or len(set(key for key, _ in options)) != 3:
            raise ValueError("Native G15 decision must present exactly three semantic actions")
        backend = PositionBalancedDeciderChoiceModel(
            str(gguf_path or ""), options, engine=model_engine,
        )
        if engine_name != "fixture" and model_engine is None:
            model_engine = backend.engine
        observe = ObservedNativeForwards(backend.engine, options)
        backend.engine = observe
        active_context = profile.cognition_context()
        audit = ProfileAuditor(
            backend, active_context, trial.g9_blueprint(role).cognition_context(),
        )
        with TemporaryDirectory() as scratch:
            snapshot = Path(scratch) / "isolated.json"
            snapshot.write_text(json.dumps(saved), encoding="utf-8")
            actor = CrewAgent.from_checkpoint(snapshot, audit)
            if (actor.identity.character_id != original["identity"]["character_id"]
                    or actor.identity.agent_id != original["identity"]["agent_id"]
                    or actor.blueprint != profile
                    or actor.revision != original["revision"]
                    or actor.cognition_revision != original["cognition_revision"]
                    or len(actor.temporal_memories) != len(original["temporal_memories"])):
                raise PermissionError("G16e native brain failed provenance validation")
            request = actor.decide(
                native_offered, expected_revision=actor.revision,
                decision_context=(
                    "PERSONAL COUNTERFACTUAL CHOICE ONLY, no Evennia command "
                    "may be executed. Scenario " + row["id"] + ". " +
                    case.context.format(peer=peer_name) +
                    " Competing human motives may conflict; decide only from "
                    "this character's own memories and stated evidence."
                ),
            )
            if (request.character_id != original["identity"]["character_id"]
                    or request.verb not in {o.verb for o in native_offered}
                    or request.target != "g14." + case.key
                    or actor.usage.total_calls != 1):
                raise PermissionError("G16e generated an unauthorised world proposal")
        native = backend.last
        if (not isinstance(native, dict)
                or native.get("underlying_native_calls") != 3
                or native.get("all_three_positions_per_semantic_option") is not True):
            raise ValueError("Native G15 failed one-of-each position scoring")
        raw_scores = native["semantic_probabilities"]
        if set(raw_scores) != {o.semantic_key for o in tagged_menu.options}:
            raise ValueError("Missing semantic option score")
        if len(observe.records) != 3:
            raise ValueError("Actual native forwards missing or duplicated")
        keys = sorted(raw_scores)
        positions = {key: set() for key in keys}
        for passed in observe.records:
            for letter_position, key in enumerate(passed["position_to_semantic_key"]):
                positions[key].add(letter_position)
        if any(positions[key] != {0, 1, 2} for key in keys):
            raise ValueError("Native positions are not Latin-square balanced")
        for key in keys:
            mean = sum(passed["semantic_scores"][key]
                       for passed in observe.records) / 3
            if not math.isclose(mean, raw_scores[key], abs_tol=1e-10):
                raise ValueError("Reported mean was not derived from three native passes")
        if tuple(passed["selected_semantic_key"] for passed in observe.records) != (
                tuple(native["permutation_native_picks"])):
            raise ValueError("Native pass selections disagree with G15 scorer")
        native_winner = native["selected_semantic_key"]
        if request.verb != tagged_menu.by_key(native_winner).verb:
            raise PermissionError("Native Concordia proposal differs from score argmax")

        native_forwards += 3
        adjusted = None
        refused = False
        try:
            adjusted = score_personality_choice(
                native_scores=raw_scores, menu=tagged_menu, profile=profile,
                seed=SEED, actor=actor.identity.character_id,
                boundary="g16e." + row["id"], kind=case.kind,
            )
        except PermissionError:
            if not tagged_menu.safety_critical:
                raise
            refused = True
        original_digest = hashlib.sha256(
            json.dumps(original["character_blueprint"], sort_keys=True).encode()
        ).hexdigest()
        observed_scores = [float(x) for x in raw_scores.values()]
        high = sorted(observed_scores, reverse=True)
        result = {
            "role": role, "scene": row["id"], "menu_key": row["menu_key"],
            "source": row["source"], "order": order, "arm": arm,
            "repeated": repeated, "hypothetical_only": True,
            "world_commands_sent": 0, "source_g9_run": 39872687597,
            "source_brain_sha256": BRAIN_SHA256[role],
            "unchanged_actor_evidence_digest": original_evidence,
            "original_blueprint_sha256": original_digest,
            "person_id": profile.person_id,
            "character_id": actor.identity.character_id,
            "catalog_sha256": catalog.content_sha256(),
            "caller_action_keys": [
                tagged_menu.by_command(o.verb, o.target, o.arguments).semantic_key
                for o in caller_offered
            ],
            "canonical_action_keys": [key for key, _ in options],
            "prompt_control_sha256": audit.prompt_control_sha256,
            "native_score_margin": high[0] - high[1],
            "raw_scores": raw_scores,
            "native_passes": observe.records,
            "raw_choice": native_winner,
            "adjusted_choice": None if refused else adjusted["selected_semantic_key"],
            "adjusted": adjusted,
            "safety_refused": refused,
            "native_calls": 3,
        }
        return result

    for row, case, tagged_menu in scenes:
        for arm in ARMS:
            for order in ORDERS:
                rows.append(one(row, case, tagged_menu, arm=arm, order=order))
    for row, case, tagged_menu in scenes[:4]:
        repeats.append(
            one(row, case, tagged_menu, arm="procedural",
                order="canonical", repeated=True)
        )
    if (len(rows) != 8 * 2 * 3 or len(repeats) != 4
            or native_forwards != 156
            or any(result["world_commands_sent"] != 0 for result in (*rows, *repeats))):
        raise AssertionError("G16e missing native calls or actor-private controls")
    return {
        "schema": 1, "status": "g16e_native_actor_evaluated",
        "role": role, "engine": engine_name,
        "source_g9_run": 39872687597,
        "source_brain_sha256": BRAIN_SHA256[role],
        "evidence_digest": original_evidence,
        "source_world_maintenance_receipts": len(world_report["verified_world_work"]),
        "catalog_sha256": catalog.content_sha256(),
        "frozen_prereg_git_blob_sha": FROZEN_PREREG_BLOB_SHA,
        "native_model_manifest": model_metadata,
        "native_forwards": native_forwards,
        "factorial_rows": rows,
        "repeat_controls": repeats,
        "world_commands_sent": 0,
        "hypothetical_only": True,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--role", choices=ROLES, required=True)
    p.add_argument("--engine", choices=ENGINE_CHOICES, default="decider-q4")
    p.add_argument("--gguf-path", type=Path)
    p.add_argument("--model-manifest", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.engine == "decider-q4" and (
            args.gguf_path is None or not args.gguf_path.is_file()):
        p.error("Native G16e requires the provisioned Decider Q4 GGUF")
    outcome = evaluate_role(
        args.root, args.role, engine_name=args.engine,
        gguf_path=args.gguf_path, model_manifest=args.model_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "role": outcome["role"], "engine": outcome["engine"],
        "native_forwards": outcome["native_forwards"],
        "safety_refusals": sum(x["safety_refused"]
                              for x in outcome["factorial_rows"]),
        "source_world_receipts": outcome["source_world_maintenance_receipts"],
    }, sort_keys=True))
    print("OX_G16E_ACTOR_RECORDED_ALL_156_NATIVE_FORWARDS")


if __name__ == "__main__":
    main()
