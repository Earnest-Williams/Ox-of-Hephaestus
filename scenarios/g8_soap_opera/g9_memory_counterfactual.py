"""Actor-local, no-world Decider test on G9 *actually acquired* memories.

After the authenticated G9 voyage, hold each person's world-observed
checkpoint, identity, personality, menu, model, and sampling method fixed.
Compare its normal indexed private recollection projection with a version
in which ONLY that read-only projection is disabled. Both native recent
world observations and the originally observed action menu stay identical.

This is NOT a GOAP rate test, not a world action, not a causal study of
the entire character memory system, and not a model-generated explanation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from ox_ai.agents.crew import CommandOption, CrewAgent
from ox_ai.inference.decider_gguf_choice import DeciderGGUFChoiceModel
from ox_ai.memory.concordia_context import OxMemoryContext


def load_trial():
    spec = spec_from_file_location(
        "ox_g9_memory_trial", Path(__file__).with_name("live_trial.py")
    )
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def menu_for_target(trial, role, target):
    if role not in trial.ROSTER or target not in trial.ROSTER or role == target:
        raise ValueError("Counterpart must be a distinct authenticated role")
    choices, mappings = [], {}
    for intent in trial.G9_INTENTS:
        actions = trial.GOAP.plan(
            {"together", "conversation_open", "heard_uncertainty"},
            {trial.GOALS[intent]},
        ).actions
        if not actions or actions[0].verb != "say":
            raise RuntimeError("No safe first symbolic dialogue action")
        first = actions[0]
        line = next(item.line for item in trial.SOCIAL_OPERATORS
                    if item.name == first.name)
        choices.append(CommandOption(
            f"Speaking with {trial.ROLES[target][0]} ({target}): "
            f"{intent}: {line}", first.verb, first.target
        ))
        mappings[(first.verb, first.target)] = intent
    if len(mappings) != len(choices):
        raise RuntimeError("Unclear actor-safe finite menu")
    return tuple(choices), mappings


def run(root: Path, *, gguf_path: Path) -> dict:
    trial = load_trial()
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    if state["turn"] != 205 or state.get("cognition_mode") != "decider":
        raise RuntimeError("Requires completed real G9 longitudinal voyage")
    if len(state["trace"]) != 205 or len(state["route_audit"]) < 8:
        raise RuntimeError("Incomplete verified world encounter history")
    # Uses the actual co-worker most recently encountered at a personality
    # boundary. Nothing is fabricated about the world's equipment state.
    last_peer = {}
    for item in state["route_audit"]:
        last_peer[item["actor"]] = item["target"]
    if set(last_peer) != set(trial.ROSTER):
        raise RuntimeError("Not every crew member received a bounded boundary")
    engine = None
    records = []
    for role in trial.ROSTER:
        target = last_peer[role]
        offered, mapping = menu_for_target(trial, role, target)
        original = json.loads((root / f"{role}.brain.json").read_text(
            encoding="utf-8"))
        if original["identity"]["agent_id"] != "ox.person.g9." + role:
            raise PermissionError("Cross-actor counterfactual checkpoint")
        if original.get("memory_projection_enabled") is not True:
            raise RuntimeError("Expected remembered actor projection baseline")
        if original["pending_requests"]:
            raise RuntimeError("Cannot run with unresolved world proposals")
        for projection in (True, False):
            variant = json.loads(json.dumps(original))
            variant["memory_projection_enabled"] = projection
            with TemporaryDirectory() as tmp:
                filepath = Path(tmp) / "actor.json"
                filepath.write_text(json.dumps(variant), encoding="utf-8")
                model = DeciderGGUFChoiceModel(
                    gguf_path, trial.G9_DESCRIPTIONS, engine=engine,
                )
                if engine is None:
                    engine = model.engine
                actor = CrewAgent.from_checkpoint(filepath, model)
                if (actor.identity.character_id != original["identity"]["character_id"]
                        or actor.blueprint != trial.g9_blueprint(role)):
                    raise PermissionError("Wrong identity in remembered replay")
                projected = OxMemoryContext(actor).pre_act(
                    SimpleNamespace(options=tuple(c.label for c in offered)),
                )
                if bool(projected) != projection:
                    raise RuntimeError("Private memory context projection arm invalid")
                # This choice is a proposal in an isolated local actor with no
                # Evennia port and no world command or evidence receipt.
                proposed = actor.decide(
                    offered,
                    expected_revision=actor.revision,
                    decision_context=(
                        "Actor-local social appraisal: make a bounded dialogue "
                        "choice based only on your perceived exchanges. "
                        "Your private recollections may be mistaken."
                    ),
                )
                selected = mapping.get((proposed.verb, proposed.target))
                if selected is None or proposed.character_id != actor.identity.character_id:
                    raise PermissionError("An unoffered world-facing choice appeared")
                records.append({
                    "role": role, "target": target,
                    "projection": projection,
                    "choice": selected,
                    "world_commands_sent": 0,
                    "model_calls": actor.usage.total_calls,
                    "model_native_logits": model.last,
                    "source_revision": original["revision"],
                    "cognition_revision": original["cognition_revision"],
                    "indexed_memory_count": len(actor.temporal_memories),
                    "projected_context_chars": len(projected),
                    "recollected_episode_count": projected.count("- Remembered "),
                    "native_observation_window": actor.observation_history_length,
                })
    pairs = []
    for role in trial.ROSTER:
        pair = [r for r in records if r["role"] == role]
        if len(pair) != 2 or not pair[0]["projection"] or pair[1]["projection"]:
            raise RuntimeError("Incomplete within-actor counterfactual")
        full, ablated = pair
        if (full["source_revision"], full["cognition_revision"],
                full["indexed_memory_count"]) != (
                ablated["source_revision"], ablated["cognition_revision"],
                ablated["indexed_memory_count"]):
            raise RuntimeError("Actor evidence changed across ablation")
        pairs.append({
            "role": role, "target": full["target"],
            "full_memory_choice": full["choice"],
            "projection_off_choice": ablated["choice"],
            "choice_changed": full["choice"] != ablated["choice"],
            "remembered_episodes_eligible": full["recollected_episode_count"],
        })
    if len(records) != 12 or any(x["model_calls"] != 1 for x in records):
        raise RuntimeError("Not precisely one real Decider call per arm")
    return {
        "schema": 1,
        "model": "Decider 4B Q4_K_M",
        "world": "observed G9 checkpoints, not active Evennia commands",
        "mode": "paired_actor_native_context_projection_on_vs_off",
        "limits": [
            "Only the Ox indexed/private interpretation read-only prompt projection is ablated.",
            "Native recent observed world exchanges remain in both arms.",
            "A changed choice is sensitivity to remembered text, not proof of psychological causality.",
            "The chosen action is a local proposal that is never submitted to Evennia."
        ],
        "world_commands_sent": 0,
        "rows": records,
        "pairs": pairs,
        "choice_changes": sum(int(p["choice_changed"]) for p in pairs),
        "intents": dict(Counter(r["choice"] for r in records)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(".ox-state/g9"))
    parser.add_argument("--gguf-path", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root, gguf_path=args.gguf_path)
    (args.root / "g9-memory-ablation.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8",
    )
    print(json.dumps({
        "world_commands_sent": result["world_commands_sent"],
        "model": result["model"], "choice_changes": result["choice_changes"],
        "pairs": result["pairs"],
        "distribution": result["intents"],
    }, sort_keys=True))
    print("OX_G9_REAL_MEMORY_ABLATION_PASS")


if __name__ == "__main__":
    main()
