"""G16c experimental finite-action personality choice, never dialogue.

Model inference scores three immutable semantic actions with G15's actual
three-pass Decider engine. The same G16a authored tags shift those *scores*
within frozen G16b bounds, then a keyed character-specific BLAKE2b draw
selects one offered action. No world permissions or receipts are inferred.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import blake2b, sha256
import json
import math
from pathlib import Path
from typing import Any

from ox_ai.agents.crew_blueprints import CrewBlueprint
from ox_ai.inference.position_balanced_choice import PositionBalancedDeciderChoiceModel
from ox_ai.runtime.disposition_goap import actor_dispositions


GAIN = 0.10
MAX_SHIFT = 0.21
BASE_TEMP = 0.33
URGENT_TEMP = 0.11
EVIDENCE_LOCK = 0.85
MODEL_POLICY_VERSION = 1


def choice_temperature(profile: CrewBlueprint, *, urgent: bool) -> float:
    if urgent:
        return URGENT_TEMP
    traits = dict(profile.traits)
    t = BASE_TEMP * (1.0 + 0.25 * (
        traits["risk_tolerance"] - traits["conscientiousness"]
    ) / 100.0)
    return min(0.45, max(0.20, t))


def keyed_choice_draw(seed: str, actor: str, boundary: str) -> float:
    if any(not isinstance(x, str) or not x for x in (seed, actor, boundary)):
        raise ValueError("Choice draw needs bound seed, actor and boundary")
    payload = json.dumps(
        (seed, actor, boundary), separators=(",", ":")
    ).encode("utf-8")
    digest = blake2b(payload, digest_size=8, person=b"ox-choice-v1").digest()
    return int.from_bytes(digest, "big") / (2**64)


def score_personality_choice(
    *, native_scores: Mapping[str, float], menu: Any,
    profile: CrewBlueprint, seed: str, actor: str, boundary: str,
    kind: str,
) -> dict:
    """Deterministic transformation of real G15 semantic probabilities.

    An unauthorised, incomplete or low-confidence safety-critical menu fails
    closed. High native scores are not *truth probabilities* or authority:
    the explicit safety lock is only an experimental selection restriction.
    """
    from ox_contracts import TaggedMenu

    if not isinstance(menu, TaggedMenu) or not isinstance(profile, CrewBlueprint):
        raise TypeError("Typed G16a menu and validated character profile required")
    if kind not in ("routine", "ambiguous", "social", "urgent"):
        raise ValueError("Unknown decision boundary kind")
    keys = tuple(sorted(option.semantic_key for option in menu.options))
    if len(keys) != 3 or set(native_scores) != set(keys):
        raise ValueError("A complete three-way semantic score set is required")
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
           for v in native_scores.values()):
        raise ValueError("Native probabilities must be finite within 0..1")
    total = sum(native_scores.values())
    if not math.isclose(total, 1, abs_tol=0.02):
        raise ValueError("Native three-position score vector is not normalized")
    # G15 has already rejected any malformed native intermediate pass.
    normalized = {key: float(native_scores[key]) / total for key in keys}
    native_max = max(normalized.values())
    native_winner = next(key for key in keys
                         if normalized[key] >= native_max - 1e-9)
    lock = menu.safety_critical and native_max >= EVIDENCE_LOCK
    if menu.safety_critical and not lock:
        raise PermissionError(
            "Safety-critical choice lacks a preregistered strong-evidence lock; "
            "no personality or probabilistic fallback allowed"
        )
    dispositions = actor_dispositions(profile)
    shifts = {}
    for option in menu.options:
        lean = option.tags.project(dispositions)
        shifts[option.semantic_key] = (
            0.0 if lock else min(MAX_SHIFT, max(-MAX_SHIFT, GAIN * lean))
        )

    temperature = choice_temperature(profile, urgent=(kind == "urgent"))
    if lock:
        adjusted = {key: float(key == native_winner) for key in keys}
    else:
        logits = {
            key: (math.log(max(normalized[key], 1e-12)) + shifts[key])
                 / temperature
            for key in keys
        }
        high = max(logits.values())
        weights = {key: math.exp(logits[key] - high) for key in keys}
        w_total = sum(weights.values())
        adjusted = {key: weights[key] / w_total for key in keys}

    draw = keyed_choice_draw(seed, actor, boundary)
    chosen = native_winner if lock else keys[-1]
    if not lock:
        cumulative = 0.0
        for key in keys:
            cumulative += adjusted[key]
            if draw < cumulative:
                chosen = key
                break
    return {
        "policy_version": MODEL_POLICY_VERSION,
        "selected_semantic_key": chosen,
        "native_winner": native_winner,
        "raw_scores": normalized,
        "shifts": {key: shifts[key] for key in keys},
        "adjusted_scores": adjusted,
        "temperature": temperature,
        "draw": draw,
        "safety_locked": bool(lock),
        "underlying_native_calls": 3,
    }


class PersonalityAdjustedDeciderChoiceModel(PositionBalancedDeciderChoiceModel):
    """Per-boundary model instance, not a shared mutable cross-actor wrapper."""

    def __init__(
        self, gguf_path: str | Path, options: Sequence[tuple[str, str]],
        *, menu: Any, profile: CrewBlueprint, seed: str,
        actor: str, boundary: str, kind: str,
        engine: Any | None = None, n_threads: int = 4,
    ) -> None:
        from ox_contracts import TaggedMenu
        if not isinstance(menu, TaggedMenu):
            raise TypeError("Typed catalog menu required")
        if {key for key, _ in options} != {
            action.semantic_key for action in menu.options
        } or len(options) != 3:
            raise ValueError("Scorer options differ from the authored menu")
        super().__init__(
            gguf_path, options, engine=engine, n_threads=n_threads,
        )
        self._policy_menu = menu
        self._policy_profile = profile
        self._policy_seed = seed
        self._policy_actor = actor
        self._policy_boundary = boundary
        self._policy_kind = kind

    def sample_choice(
        self, prompt: str, responses: Sequence[str],
        *, seed: int | None = None,
    ):
        # Reset on failure; no partly populated wrapper is an accepted choice.
        self.last = None
        _, _, _meta = super().sample_choice(prompt, responses, seed=seed)
        native = self.last
        if not isinstance(native, dict) or native.get("underlying_native_calls") != 3:
            raise RuntimeError("A complete G15 native inference is required")
        try:
            result = score_personality_choice(
                native_scores=native["semantic_probabilities"],
                menu=self._policy_menu, profile=self._policy_profile,
                seed=self._policy_seed, actor=self._policy_actor,
                boundary=self._policy_boundary, kind=self._policy_kind,
            )
        except BaseException:
            self.last = None
            raise
        result["prompt_sha256"] = sha256(prompt.encode("utf-8")).hexdigest()
        result["balanced_native_picks"] = list(native["permutation_native_picks"])
        result["all_three_positions_per_semantic_option"] = True
        # The response codes index the original caller order, while the choice
        # draw and all score adjustments operate in stable semantic-key order.
        original_keys = tuple(key for key, _ in self.options)
        codes = tuple(responses)
        code = codes[original_keys.index(result["selected_semantic_key"])]
        self.last = result
        return codes.index(code), code, {
            "decider_position_balanced_personality_choice": result,
        }


class ReplayedPersonalityChoiceModel:
    """Adopt a *saved*, prompt-verified finite choice without another inference.

    This does not invent fresh model-quality evidence: underlying native
    calls on this replay are ZERO, and previous scores retain their source.
    """

    def __init__(self, saved: dict, options: Sequence[tuple[str, str]]) -> None:
        self.saved = saved
        self.options = tuple(options)
        self.last: dict | None = None

    def sample_choice(self, prompt: str, responses: Sequence[str],
                      *, seed: int | None = None):
        del seed
        self.last = None
        codes = tuple(responses)
        if (len(codes) != 3 or len(set(codes)) != 3
                or tuple(sorted(key for key, _ in self.options))
                   != tuple(sorted(self.saved["raw_scores"]))
                or sha256(prompt.encode("utf-8")).hexdigest()
                   != self.saved["prompt_sha256"]):
            raise PermissionError("Replayed native prompt/menu changed")
        keys = tuple(key for key, _ in self.options)
        chosen = self.saved["selected_semantic_key"]
        if chosen not in keys:
            raise PermissionError("Saved choice is no longer offered")
        code = codes[keys.index(chosen)]
        self.last = dict(self.saved)
        return codes.index(code), code, {
            "replayed_precommitted_personality_choice": True,
        }

    def sample_text(self, *args, **kwargs):
        raise RuntimeError("Finite-action replay cannot generate text")
