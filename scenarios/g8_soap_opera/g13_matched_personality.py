"""G13: within-actor, matched-evidence native personality counterfactuals.

Every arm starts with the SAME authenticated G9 private checkpoint. The only
intervention is six of the character's twelve psychological traits, including
the corresponding read-only Concordia profile text. The 4 situations are NEW
hypothetical prompts, not observed Evennia events or executable agreements.
No actual world commands or relationship transitions are possible.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ox_ai.agents.crew import CommandOption, CrewAgent
from ox_ai.agents.crew_blueprints import CrewBlueprint
from ox_ai.runtime.personality_routing import PersonalState, PersonalityRouter

from g10_decider_battery import (
    ROLES, BRAIN_SHA256, authenticated_archive, actor_archive, last_counterpart,
    FixtureFirst,
)

ARMS = ("original", "procedural", "independent")
ORDERS = ("canonical", "reverse", "rotate")
POSITIONS = {
    "canonical": (0, 1, 2),
    "reverse": (2, 1, 0),
    "rotate": (1, 2, 0),
}
REPLIES = (
    ("accept", "Accept the proposed commitment, knowing it can create obligations."),
    ("defer", "Defer a decision and tell the colleague the offer remains unresolved."),
    ("decline", "Decline the proposal explicitly, accepting possible social disappointment."),
)
TRAIT_INTERVENTIONS = {
    "procedural": {
        "conscientiousness": 92, "risk_tolerance": 12,
        "authority_challenge": 12, "agreeableness": 76,
        "collaboration": 86, "openness": 32,
    },
    "independent": {
        "conscientiousness": 28, "risk_tolerance": 90,
        "authority_challenge": 92, "agreeableness": 30,
        "collaboration": 30, "openness": 94,
    },
}


@dataclass(frozen=True)
class Case:
    key: str
    text: str
    pressure: PersonalState


CASES = (
    Case("ordinary_favor",
         "Hypothetical only: the colleague offers to exchange short, optional "
         "post-watch documentation reviews next week. Both are qualified, "
         "there is no conflict with scheduled duties, and no agreement exists.",
         PersonalState(stress=.20, fatigue=.25, social_pressure=.32, uncertainty=.20)),
    Case("strained_repair",
         "Hypothetical only: after an old personal misunderstanding that neither "
         "has conclusively resolved, the colleague offers to meet privately and "
         "commit to an honest discussion. Their intentions remain uncertain.",
         PersonalState(stress=.46, fatigue=.30, social_pressure=.72, uncertainty=.78)),
    Case("fatigue_pressure",
         "Hypothetical only: while you are tired after a demanding watch, the "
         "colleague urges you to promise attendance at a voluntary gathering. "
         "You may refuse without violating any professional responsibility.",
         PersonalState(stress=.66, fatigue=.90, social_pressure=.92, uncertainty=.33)),
    Case("conflicted_loyalty",
         "Hypothetical only: the colleague proposes that you stand with them "
         "during a private interpersonal dispute with no verified finding. "
         "You know conflicting accounts; this offer cannot suppress truthful "
         "ship records or change formal duty or safety reporting.",
         PersonalState(stress=.43, fatigue=.36, social_pressure=.86, uncertainty=.91)),
)


def load_g9_trial():
    path = Path(__file__).with_name("live_trial.py")
    spec = spec_from_file_location("ox_g13_g9_trial", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def profile_for(original: dict, arm: str) -> CrewBlueprint:
    if arm not in ARMS:
        raise ValueError("Unrecognized psychological intervention")
    record = json.loads(json.dumps(original["character_blueprint"]))
    if arm != "original":
        record["traits"].update(TRAIT_INTERVENTIONS[arm])
    return CrewBlueprint.from_record(record)


def _replace_profile_text(value, original: str, replacement: str):
    """Only replace the exact constant profile, even within serialized state."""
    if isinstance(value, str):
        return value.replace(original, replacement)
    if isinstance(value, dict):
        return {k: _replace_profile_text(v, original, replacement)
                for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_profile_text(v, original, replacement) for v in value]
    return value


def isolated_snapshot(original: dict, arm: str) -> tuple[dict, CrewBlueprint]:
    """Same actor, identity, observation, memory and native brain state.

    Replacing the exact CharacterProfile constant is necessary because native
    Concordia restores its component graph from the saved checkpoint. The
    experimental record MUST round-trip to the original if the trait vector
    and this one read-only constant are restored. Nothing else is writable.
    """
    before = profile_for(original, "original")
    after = profile_for(original, arm)
    saved = json.loads(json.dumps(original))
    saved["character_blueprint"]["traits"] = dict(after.traits)
    original_context = before.cognition_context()
    new_context = after.cognition_context()
    saved["concordia_state"] = _replace_profile_text(
        original["concordia_state"], original_context, new_context
    )
    if arm != "original":
        reverse = _replace_profile_text(
            saved["concordia_state"], new_context, original_context
        )
        if reverse != original["concordia_state"]:
            raise PermissionError("Counterfactual modified non-profile brain state")
        saved["character_blueprint"]["traits"] = dict(before.traits)
        if saved != original:
            raise PermissionError("Personality trial modified actor evidence")
        saved["character_blueprint"]["traits"] = dict(after.traits)
    else:
        if saved != original:
            raise PermissionError("Original profile replay changed evidence")
    return saved, after


def menu(case: Case, counterpart: str, order: str) -> tuple[CommandOption, ...]:
    if order not in ORDERS:
        raise ValueError("Unknown menu order")
    result = tuple(CommandOption(
        "Hypothetical personal commitment offered by " + counterpart + ": " + label,
        "consider." + choice, "g13." + case.key,
    ) for choice, label in (REPLIES[i] for i in POSITIONS[order]))
    if len(result) != 3 or len({r.verb for r in result}) != 3:
        raise AssertionError("G13 social choices must be finite and unique")
    return result


class ProfileAuditor:
    """Observe the actual prompt sent to Decider, not the claimed profile."""

    def __init__(self, backend, active_context: str, original_context: str):
        self.backend = backend
        self.active_context = active_context
        self.original_context = original_context
        self.prompt_control_sha256 = None

    def sample_choice(self, prompt, responses, *, seed=None):
        if prompt.count(self.active_context) != 1:
            raise PermissionError("Injected psychological traits did not reach native model")
        if (self.active_context != self.original_context
                and self.original_context in prompt):
            raise PermissionError("Original trait vector leaked into counterfactual")
        normalized = prompt.replace(self.active_context, "<CONTROLLED_TRAITS>")
        self.prompt_control_sha256 = hashlib.sha256(
            normalized.encode("utf-8")).hexdigest()
        return self.backend.sample_choice(prompt, responses, seed=seed)

    def sample_text(self, *args, **kwargs):
        raise AssertionError("G13 is choice-only, never free-form generation")


def evidence_digest(original: dict) -> str:
    """Hash exactly those actor fields no trial is allowed to alter."""
    unchanged = {k: v for k, v in original.items()
                 if k not in ("character_blueprint", "concordia_state")}
    return hashlib.sha256(json.dumps(
        unchanged, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def evaluate_role(root: Path, role: str, *, engine_name: str,
                  gguf_path: Path | None = None) -> dict:
    if role not in ROLES or engine_name not in ("fixture", "decider-q4"):
        raise ValueError("Unrecognized identity or inference engine")
    state, report = authenticated_archive(root)
    original = actor_archive(root, role)
    trial = load_g9_trial()
    baseline = trial.g9_blueprint(role)
    if original["character_blueprint"] != baseline.to_record():
        raise PermissionError("Original personality is not the authenticated G9 profile")
    if original.get("pending_requests"):
        raise PermissionError("Cannot fork a brain with unverified world requests")
    counterpart = last_counterpart(state, role)
    name = trial.ROLES[counterpart][0]
    archive_digest = evidence_digest(original)
    engine = None
    calls = 0

    def one(case: Case, arm: str, order: str) -> dict:
        nonlocal calls, engine
        saved, active = isolated_snapshot(original, arm)
        if evidence_digest(saved) != archive_digest:
            raise PermissionError("Actor world/private evidence changed between treatments")
        offered = menu(case, name, order)
        if engine_name == "fixture":
            backend = FixtureFirst()
        else:
            from ox_ai.inference.decider_gguf_choice import DeciderGGUFChoiceModel
            backend = DeciderGGUFChoiceModel(
                gguf_path, [x.label for x in offered], engine=engine
            )
            if engine is None:
                engine = backend.engine
        auditor = ProfileAuditor(
            backend, active.cognition_context(), baseline.cognition_context()
        )
        with TemporaryDirectory() as temp:
            checkpoint = Path(temp) / "isolated.json"
            checkpoint.write_text(json.dumps(saved), encoding="utf-8")
            actor = CrewAgent.from_checkpoint(checkpoint, auditor)
            if (actor.identity.character_id != original["identity"]["character_id"]
                    or actor.identity.agent_id != original["identity"]["agent_id"]
                    or actor.blueprint != active
                    or actor.revision != original["revision"]
                    or actor.cognition_revision != original["cognition_revision"]
                    or actor.memory_now_turn != original["memory_now_turn"]
                    or len(actor.temporal_memories) !=
                    len(original["temporal_memories"])):
                raise PermissionError("Counterfactual escaped the preserved actor")
            request = actor.decide(
                offered, expected_revision=actor.revision,
                decision_context=(
                    "PERSONAL COUNTERFACTUAL ONLY; there is no new Evennia "
                    "observation, no authenticated pending social offer, and "
                    "no permission to act. " + case.text +
                    " You are considering only whether to accept, defer, or "
                    "decline this hypothetical offer. Your personal recollections "
                    "remain fallible and are not objective world testimony."
                ),
            )
            if (request.character_id != original["identity"]["character_id"]
                    or request.target != "g13." + case.key
                    or request.verb not in {v.verb for v in offered}
                    or actor.usage.total_calls != 1):
                raise PermissionError("Invalid native actor-scoped choice")
        calls += 1
        chosen = request.verb.removeprefix("consider.")
        native = backend.last["probabilities"]
        codes = tuple(native)
        scores = {op.verb.removeprefix("consider."): native[code]
                  for op, code in zip(offered, codes)}
        if set(scores) != {"accept", "defer", "decline"}:
            raise ValueError("Native model omitted a response category")
        route = PersonalityRouter(
            active, original["identity"]["character_id"], {},
            seed="g13-observational-policy-" + role
        )
        return {
            "role": role, "case": case.key, "arm": arm, "order": order,
            "choice": chosen, "position": tuple(op.verb for op in offered).index(
                request.verb),
            "scores": scores, "prompt_control_sha256": auditor.prompt_control_sha256,
            "route_probability_only": route.probability(case.pressure, "social"),
            "evidence_digest": archive_digest, "model_calls": 1,
            "world_commands_sent": 0, "hypothetical": True,
        }

    rows = [
        one(case, arm, order)
        for case in CASES for order in ORDERS for arm in ARMS
    ]
    repeats = [
        one(case, "original", "canonical")
        for case in CASES
    ]
    if len(rows) != 36 or len(repeats) != 4 or calls != 40:
        raise AssertionError("Incomplete G13 experiment for actor")
    for case in CASES:
        for order in ORDERS:
            paired = [row for row in rows
                      if row["case"] == case.key and row["order"] == order]
            if (len(paired) != 3
                    or len({row["prompt_control_sha256"] for row in paired}) != 1
                    or len({row["evidence_digest"] for row in paired}) != 1):
                raise PermissionError("Model prompts or evidence are confounded")
    return {
        "schema": 1, "status": "g13_matched_counterfactual_complete",
        "engine": engine_name, "role": role, "counterpart": counterpart,
        "source_g9_run": 39872687597, "g9_brain_sha256": BRAIN_SHA256[role],
        "evidence_digest": archive_digest,
        "source_world_maintenance_receipts": len(report["verified_world_work"]),
        "hypothetical_only": True, "world_commands_sent": 0,
        "native_model_calls": calls,
        "rows": rows, "repeat_controls": repeats,
        "choice_counts": dict(Counter(x["choice"] for x in rows)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--role", choices=ROLES, required=True)
    parser.add_argument("--model", choices=("fixture", "decider-q4"), default="decider-q4")
    parser.add_argument("--gguf-path", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.model == "decider-q4" and args.gguf_path is None:
        parser.error("Real Decider requires a GGUF file")
    result = evaluate_role(
        args.root, args.role, engine_name=args.model, gguf_path=args.gguf_path
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "role": args.role, "engine": result["engine"],
        "calls": result["native_model_calls"],
        "choices": result["choice_counts"],
        "repeats": len(result["repeat_controls"]),
    }, sort_keys=True))
    print("OX_G13_ACTOR_PROFILE_MATCHED_PASS")


if __name__ == "__main__":
    main()
