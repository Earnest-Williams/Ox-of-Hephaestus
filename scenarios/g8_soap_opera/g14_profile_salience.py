"""G14: paired native Decider test of numeric versus qualitative trait rendering.

All arms restore the exact authenticated G9 private brain for the SAME actor.
One controlled intervention swaps six stable trait values; another changes
only their read-only characterization from numeric to derived prose.
Hypothetical choices only: no authentication, Evennia commands or receipts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ox_ai.agents.crew import CommandOption, CrewAgent
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.runtime.personality_routing import PersonalityRouter, PersonalState

from g13_matched_personality import (
    ROLES, BRAIN_SHA256, authenticated_archive, actor_archive,
    last_counterpart, load_g9_trial, isolated_snapshot, evidence_digest,
    _replace_profile_text, ProfileAuditor, FixtureFirst,
)

ARMS = ("numeric_original", "numeric_independent",
        "prose_original", "prose_independent")
ORDERS = ("canonical", "cycle_left", "cycle_right")
# Each semantic option occupies every display position exactly once.
POSITIONS = {
    "canonical": (0, 1, 2),
    "cycle_left": (1, 2, 0),
    "cycle_right": (2, 0, 1),
}

@dataclass(frozen=True)
class Case:
    key: str
    kind: str
    context: str
    baseline: str
    options: tuple[tuple[str, str], ...]


CASES = (
    Case(
        "verified_mutual_aid", "social",
        "A colleague {peer} offers to double-check your completed, nonconfidential "
        "duty notes with you before submission. The colleague is competent, "
        "available, and has no conflicting duty; accepting is permitted. "
        "You value autonomy too, and need not accept an offered favor.",
        "accept_help",
        (
            ("accept_help", "Accept the colleague's available help and review the notes together."),
            ("work_alone", "Thank the colleague but complete the final review independently."),
            ("reschedule", "Ask to revisit the optional offer on another shift instead."),
        ),
    ),
    Case(
        "finite_spare_dispute", "ambiguous",
        "There is only one spare life-support cartridge. A crewmate {peer} "
        "wants it for a nonurgent preventive replacement; holding the reserve "
        "protects against a possible later alarm, while a loan helps the colleague. "
        "You cannot execute maintenance or allocate inventory yourself.",
        "reserve_spare",
        (
            ("reserve_spare", "Advocate keeping the last cartridge in reserve and explain the risk."),
            ("support_loan", "Support the colleague's nonurgent request despite the possible later need."),
            ("seek_review", "Ask the authorized chief to weigh the conflicting needs explicitly."),
        ),
    ),
    Case(
        "approved_watch_relief", "social",
        "A colleague {peer} needs a short personal appointment and offers to "
        "exchange an ordinary watch. The duty officer has already confirmed "
        "both of you are qualified and authorizes either choice. The change "
        "would mildly inconvenience you but does not risk ship operations.",
        "cover_watch",
        (
            ("cover_watch", "Agree to the authorized watch exchange to help the colleague."),
            ("keep_watch", "Politely retain your assigned watch and let them seek other coverage."),
            ("offer_alternative", "Offer a smaller later favor instead of this watch exchange."),
        ),
    ),
    Case(
        "uncertain_private_apology", "ambiguous",
        "After a real but minor interpersonal misunderstanding with {peer}, "
        "they request a private conversation and offer an apology. Their "
        "intentions are not fully known. No violence or operational hazard is "
        "present. You are free to reconcile, postpone or set a boundary.",
        "consider_talk",
        (
            ("consider_talk", "Accept the offered private conversation and hear the apology."),
            ("protect_space", "Decline the meeting, protecting personal boundaries."),
            ("ask_later", "Postpone the conversation and request time to reconsider."),
        ),
    ),
)


def _tendency(value: int, *, high: str, low: str, middle: str) -> str:
    return high if value >= 70 else low if value <= 35 else middle


def prose_profile(blueprint) -> str:
    """Interpret a fixed trait vector as descriptive inclinations, not orders.

    No case-specific target, suggested option or mandatory behavior is inserted.
    The facts of the current world, permissions and private memory stay intact.
    """
    traits = dict(blueprint.traits)
    interpretations = (
        ("Conscientiousness", _tendency(
            traits["conscientiousness"],
            high="prefers predictable procedures and finished obligations",
            low="often improvises and tolerates unfinished routines",
            middle="balances planning and flexibility")),
        ("Agreeableness", _tendency(
            traits["agreeableness"],
            high="is often accommodating and motivated to preserve rapport",
            low="readily asserts individual boundaries even against social pressure",
            middle="weighs kindness against self-protection")),
        ("Risk tolerance", _tendency(
            traits["risk_tolerance"],
            high="is comfortable with uncertain outcomes",
            low="is cautious about uncertain outcomes",
            middle="considers both upside and uncertainty")),
        ("Authority challenge", _tendency(
            traits["authority_challenge"],
            high="readily questions familiar authority and conventions",
            low="normally defers to established procedures and supervisors",
            middle="questions authority selectively")),
        ("Collaboration", _tendency(
            traits["collaboration"],
            high="prefers collective solutions and mutual support",
            low="prefers independent action and personal discretion",
            middle="adapts between joint and solo work")),
        ("Openness", _tendency(
            traits["openness"],
            high="welcomes novel approaches and social possibilities",
            low="prefers familiar practices and settled commitments",
            middle="is selectively open to change")),
    )
    # Do not accidentally remove any unmodified personality dimensions,
    # aptitudes, personal history or descriptive styles. The presentation
    # intervention changes ONLY the way the six selected traits are expressed.
    interpreted = {
        "conscientiousness", "agreeableness", "risk_tolerance",
        "authority_challenge", "collaboration", "openness",
    }
    uninterpreted = ", ".join(
        f"{name}={traits[name]}" for name in sorted(set(traits) - interpreted)
    )
    source = blueprint.cognition_context()
    marker = "Formative aptitudes (1-10): "
    if source.count(marker) != 1:
        raise ValueError("Cannot preserve unchanged blueprint context")
    original_tail = marker + source.split(marker, 1)[1]
    result = (
        "Characterisation, not a rule or authorisation. Stable tendencies: " +
        "; ".join(name + ": " + tendency for name, tendency in interpretations) +
        ". Other unchanged traits (0-100): " + uninterpreted + ". " +
        "These dispositions may conflict and are not commands. " + original_tail
    )
    if not 100 <= len(result) <= 1800:
        raise ValueError("Narrative traits must be bounded")
    return result


def treatment(original: dict, arm: str):
    if arm not in ARMS:
        raise ValueError("Unknown trait/presentation arm")
    vector = "independent" if arm.endswith("independent") else "original"
    saved, blueprint = isolated_snapshot(original, vector)
    previous = blueprint.cognition_context()
    context = prose_profile(blueprint) if arm.startswith("prose_") else previous
    if context != previous:
        saved["concordia_state"] = _replace_profile_text(
            saved["concordia_state"], previous, context)
        # A prose treatment may touch only read-only profile text, just as
        # G13's numeric-treatment round-trip preserves actor-private history.
        if _replace_profile_text(
            saved["concordia_state"], context, previous
        ) != isolated_snapshot(original, vector)[0]["concordia_state"]:
            raise PermissionError("Prose changed other native component state")
    if evidence_digest(saved) != evidence_digest(original):
        raise PermissionError("Experimental prose changed actor-private evidence")
    return saved, blueprint, context


def menu(case: Case, counterpart: str, order: str):
    if order not in ORDERS:
        raise ValueError("Unknown option-order treatment")
    return tuple(CommandOption(
        f"Planning only, discussing {counterpart}: {label}",
        "consider." + choice, "g14." + case.key
    ) for choice, label in (case.options[i] for i in POSITIONS[order]))


def goap_baseline(case: Case):
    """Existing symbolic planning of an authored baseline, not world success."""
    options = tuple(
        GoapAction(name=key, requires=frozenset({"choice_open"}),
                   adds=frozenset({"handled"}) if key == case.baseline
                   else frozenset({"considered_" + key}),
                   cost=1 if key == case.baseline else 4,
                   verb="consider." + key, target="g14." + case.key)
        for key, _ in case.options
    )
    path = GoapPlanner(options).plan({"choice_open"}, {"handled"}).actions
    if len(path) != 1 or path[0].name != case.baseline:
        raise AssertionError("Symbolic GOAP baseline is missing")
    return path[0].name


def evaluate_role(root: Path, role: str, *, engine_name: str,
                  gguf_path: Path | None = None):
    if role not in ROLES or engine_name not in ("fixture","decider-q4"):
        raise ValueError("Unknown G14 actor or model")
    state, report = authenticated_archive(root)
    original = actor_archive(root, role)
    trial = load_g9_trial()
    if original["character_blueprint"] != trial.g9_blueprint(role).to_record():
        raise PermissionError("Invalid actor's original authenticated profile")
    if original.get("pending_requests"):
        raise PermissionError("Cannot reuse unresolved actions in a counterfactual")
    counterpart = last_counterpart(state, role)
    counterpart_name = trial.ROLES[counterpart][0]
    frozen_evidence = evidence_digest(original)
    engine = None
    calls = 0

    def one(case: Case, arm: str, order: str):
        nonlocal engine, calls
        saved, blueprint, context = treatment(original, arm)
        if (saved["identity"] != original["identity"]
                or evidence_digest(saved) != frozen_evidence):
            raise PermissionError("Counterfactual evidence/identity leaked")
        offered = menu(case, counterpart_name, order)
        if engine_name == "fixture":
            backend = FixtureFirst()
        else:
            from ox_ai.inference.decider_gguf_choice import DeciderGGUFChoiceModel
            backend = DeciderGGUFChoiceModel(
                gguf_path, [x.label for x in offered], engine=engine)
            if engine is None:
                engine = backend.engine
        auditor = ProfileAuditor(
            backend, context, trial.g9_blueprint(role).cognition_context())
        auditor.response_codes = None
        original_sample = auditor.sample_choice
        def record_response_codes(prompt, responses, *, seed=None):
            auditor.response_codes = tuple(responses)
            return original_sample(prompt, responses, seed=seed)
        auditor.sample_choice = record_response_codes
        with TemporaryDirectory() as temp:
            path = Path(temp) / "isolated.json"
            path.write_text(json.dumps(saved), encoding="utf-8")
            actor = CrewAgent.from_checkpoint(path, auditor)
            if (actor.identity.character_id != original["identity"]["character_id"]
                    or actor.identity.agent_id != original["identity"]["agent_id"]
                    or actor.blueprint != blueprint
                    or actor.revision != original["revision"]
                    or actor.cognition_revision != original["cognition_revision"]
                    or len(actor.temporal_memories) != len(original["temporal_memories"])):
                raise PermissionError("Restored native actor did not retain its history")
            request = actor.decide(
                offered, expected_revision=actor.revision,
                decision_context=(
                    "PERSONAL COUNTERFACTUAL PLANNING ONLY. The following is "
                    "not an observed Evennia fact; the crew cannot execute "
                    "these options through this exercise. " +
                    case.context.format(peer=counterpart_name) +
                    " Consider the competing motives and current stated "
                    "circumstances, recognizing that memories may be fallible."
                ),
            )
            if (request.character_id != original["identity"]["character_id"]
                    or request.target != "g14." + case.key
                    or request.verb not in {x.verb for x in offered}
                    or actor.usage.total_calls != 1):
                raise PermissionError("Unrecognized model proposal")
        calls += 1
        code_probs = backend.last["probabilities"]
        # Capture Concordia's actual response-code order at the inference
        # boundary; dictionary iteration order is not a valid semantic map.
        codes = auditor.response_codes
        if (codes is None or len(codes) != len(offered)
                or set(code_probs) != set(codes)):
            raise AssertionError("Native response codes differ from offered menu")
        semantic_scores = {
            option.verb.removeprefix("consider."): code_probs[code]
            for option, code in zip(offered, codes)
        }
        if set(semantic_scores) != {key for key, _ in case.options}:
            raise AssertionError("A native option was omitted")
        selected = request.verb.removeprefix("consider.")
        if semantic_scores[selected] + 1e-9 < max(semantic_scores.values()):
            raise AssertionError("Native choice does not maximize reported score")
        return {
            "role": role, "case": case.key, "order": order, "arm": arm,
            "choice": selected,
            "position": tuple(x.verb for x in offered).index(request.verb),
            "offered_actions": [x.verb.removeprefix("consider.") for x in offered],
            "scores": semantic_scores, "goap_baseline": goap_baseline(case),
            "prompt_control_sha256": auditor.prompt_control_sha256,
            "evidence_digest": frozen_evidence,
            "model_calls": 1, "world_commands_sent": 0,
            "hypothetical_only": True,
        }

    rows = [one(case, arm, order)
            for case in CASES for order in ORDERS for arm in ARMS]
    repeats = [one(case, "numeric_original", "canonical") for case in CASES]
    if calls != 52 or len(rows) != 48 or len(repeats) != 4:
        raise AssertionError("G14 missing native factorial and repeat controls")
    for case in CASES:
        for order in ORDERS:
            paired = [x for x in rows if x["case"] == case.key
                      and x["order"] == order]
            if (len(paired) != 4
                    or len({x["prompt_control_sha256"] for x in paired}) != 1
                    or len({x["evidence_digest"] for x in paired}) != 1):
                raise PermissionError("Profile treatments changed non-profile context")
    return {
        "schema": 2, "status": "g14_matched_balanced_profile_arms_complete",
        "engine": engine_name, "role": role, "counterpart": counterpart,
        "source_g9_run": 39872687597, "g9_brain_sha256": BRAIN_SHA256[role],
        "evidence_digest": frozen_evidence,
        "source_world_maintenance_receipts": len(report["verified_world_work"]),
        "hypothetical_only": True, "world_commands_sent": 0,
        "native_model_calls": calls, "rows": rows, "repeat_controls": repeats,
        "choice_counts": dict(Counter(x["choice"] for x in rows)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--role", choices=ROLES, required=True)
    parser.add_argument("--model", choices=("fixture","decider-q4"),
                        default="decider-q4")
    parser.add_argument("--gguf-path", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.model == "decider-q4" and args.gguf_path is None:
        parser.error("Selected Decider Q4_K_M requires a GGUF file")
    result = evaluate_role(
        args.root, args.role, engine_name=args.model, gguf_path=args.gguf_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True),
                        encoding="utf-8")
    print(json.dumps({
        "role": result["role"], "engine": result["engine"],
        "model_calls": result["native_model_calls"],
        "choices": result["choice_counts"],
    }, sort_keys=True))
    print("OX_G14_FOUR_ARM_NATIVE_PROFILE_PASS")


if __name__ == "__main__":
    main()
