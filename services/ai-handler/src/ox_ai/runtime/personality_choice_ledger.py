"""G16c private, durable personality choice records, never world receipts.

The event-bound router remains the authority for consultation. This add-on
stores a distinct actor-private *choice* once, before a detached native proposal
is adopted on the main event loop. All records fail closed under provenance
or schema drift; no arbitrary text, foreign data or world DB access.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping
from hashlib import blake2b
from typing import Any

from ox_ai.runtime.personality_routing import PersonalityRouter, Route

MAX_PERSONALITY_CHOICES = 2048
MAX_CHOICE_RECORD_BYTES = 12000
_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,159}$")
_HEX = re.compile(r"^[0-9a-f]{32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DIMENSIONS = frozenset(("risk", "deference", "social", "autonomy", "procedure"))


def deterministic_proposal_id(router: PersonalityRouter, boundary: str) -> str:
    if not isinstance(router, PersonalityRouter) or not _ID.fullmatch(boundary):
        raise ValueError("An actor-bound stable boundary is required")
    payload = json.dumps(
        (router.record["seed"], router.character_id, boundary),
        separators=(",", ":"),
    ).encode("utf-8")
    return blake2b(
        payload, digest_size=16, person=b"ox-choice-id-v1",
    ).hexdigest()


def _score_mapping(values: object, keys: set[str], *,
                   normalized: bool) -> None:
    if not isinstance(values, dict) or set(values) != keys:
        raise ValueError("Choice scores do not match the authored semantic options")
    if any(type(v) not in (int, float) or not math.isfinite(v)
           or (normalized and not 0.0 <= v <= 1.0)
           for v in values.values()):
        raise ValueError("Corrupt saved model scores")
    if normalized and not math.isclose(sum(values.values()), 1.0, abs_tol=1e-8):
        raise ValueError("Saved selection probabilities are not normalized")


class PersonalityChoiceLedger:
    """Owns one append-only choice entry per event-bound router decision."""

    def __init__(self, router: PersonalityRouter) -> None:
        if not isinstance(router, PersonalityRouter):
            raise TypeError("An authenticated event router is required")
        self.router = router
        table = router.record.get("personality_choices", {})
        if not isinstance(table, dict) or len(table) > MAX_PERSONALITY_CHOICES:
            raise ValueError("Invalid or unbounded personality choice checkpoint")
        for boundary, entry in table.items():
            if (not isinstance(boundary, str) or not _ID.fullmatch(boundary)
                    or not isinstance(entry, dict)
                    or entry.get("version") != 1
                    or entry.get("actor") != router.character_id
                    or entry.get("request_id") != deterministic_proposal_id(router, boundary)
                    or entry.get("route") not in ("goap", "llm")
                    or boundary not in router.record["boundaries"]
                    or entry["route"] != router.record["boundaries"][boundary]["selected"]
                    or len(json.dumps(entry, sort_keys=True)) > MAX_CHOICE_RECORD_BYTES):
                raise ValueError("Corrupt or actor-crossing choice checkpoint")

    def _validate(
        self, boundary: str, *, route: Route,
        menu: Any, catalog_sha256: str,
    ) -> dict | None:
        if route.boundary_id != boundary or not _ID.fullmatch(boundary):
            raise ValueError("Choice was rebound to a different routing event")
        table = self.router.record.get("personality_choices", {})
        entry = table.get(boundary)
        if entry is None:
            return None
        if not _SHA256.fullmatch(catalog_sha256):
            raise ValueError("A versioned catalog fingerprint is required")
        keys = {option.semantic_key for option in menu.options}
        expected_tags = {
            option.semantic_key: option.tags.model_dump(mode="json")
            for option in menu.options
        }
        common = {
            "version", "route", "actor", "menu_key", "catalog_sha256",
            "semantic_keys", "tag_snapshot", "selected_semantic_key",
            "request_id", "observation_revision", "cognition_revision",
            "choice",
        }
        if (set(entry) != common or entry["actor"] != self.router.character_id
                or entry["route"] != route.selected
                or entry["menu_key"] != menu.menu_key
                or entry["catalog_sha256"] != catalog_sha256
                or entry["semantic_keys"] != sorted(keys)
                or entry["tag_snapshot"] != expected_tags
                or entry["selected_semantic_key"] not in keys
                or entry["request_id"] != deterministic_proposal_id(self.router, boundary)
                or entry["observation_revision"] != route.observation_revision
                or entry["cognition_revision"] != route.cognition_revision
                or not isinstance(entry["choice"], dict)):
            raise PermissionError("Saved personality choice changed actor, catalog or evidence")
        meta = entry["choice"]
        if entry["route"] == "llm":
            size = len(keys)
            position_field = (
                "all_two_positions_per_semantic_option"
                if size == 2
                else "all_three_positions_per_semantic_option"
            )
            required = {
                "policy_version",
                "selected_semantic_key",
                "native_winner",
                "raw_scores",
                "shifts",
                "adjusted_scores",
                "temperature",
                "draw",
                "safety_locked",
                "underlying_native_calls",
                "prompt_sha256",
                "balanced_native_picks",
                position_field,
            }
            if (
                size not in (2, 3)
                or set(meta) != required
                or type(meta["policy_version"]) is not int
                or meta["policy_version"] != (2 if size == 2 else 1)
                or type(meta["underlying_native_calls"]) is not int
                or meta["underlying_native_calls"] != size
                or meta["selected_semantic_key"] != entry["selected_semantic_key"]
                or meta["native_winner"] not in keys
                or not isinstance(meta["prompt_sha256"], str)
                or not _SHA256.fullmatch(meta["prompt_sha256"])
                or type(meta["temperature"]) not in (float, int)
                or not math.isfinite(meta["temperature"])
                or not 0.0 < meta["temperature"] <= 1.0
                or type(meta["draw"]) not in (float, int)
                or not math.isfinite(meta["draw"])
                or not 0.0 <= meta["draw"] < 1.0
                or type(meta["safety_locked"]) is not bool
                or meta[position_field] is not True
                or not isinstance(meta["balanced_native_picks"], list)
                or len(meta["balanced_native_picks"]) != size
                or any(pick not in keys for pick in meta["balanced_native_picks"])
            ):
                raise ValueError("Corrupt native choice audit ledger")
            _score_mapping(meta["raw_scores"], keys, normalized=True)
            _score_mapping(meta["adjusted_scores"], keys, normalized=True)
            _score_mapping(meta["shifts"], keys, normalized=False)
            if any(abs(v) > 0.21 + 1e-8 for v in meta["shifts"].values()):
                raise ValueError("Personality shift exceeded frozen G16b cap")
            if meta["safety_locked"] and (
                meta["selected_semantic_key"] != meta["native_winner"]
                or any(v != 0.0 for v in meta["shifts"].values())
            ):
                raise ValueError("Safety lock allowed an override")
            # Recompute *all* choice policy arithmetic from the saved native
            # probabilities, actor profile, catalog and boundary. A checkpoint
            # with altered shifts, draw, temperature or winner fails closed
            # instead of silently adopting a forged preference.
            from ox_ai.inference.disposition_choice import score_personality_choice
            expected = score_personality_choice(
                native_scores=meta["raw_scores"], menu=menu,
                profile=self.router.profile, seed=self.router.record["seed"],
                actor=self.router.character_id, boundary=boundary,
                kind=self.router.record["boundaries"][boundary]["kind"],
            )
            for key in ("selected_semantic_key", "native_winner",
                        "safety_locked", "underlying_native_calls"):
                if meta[key] != expected[key]:
                    raise PermissionError("Saved native policy result was modified")
            for key in ("temperature", "draw"):
                if not math.isclose(meta[key], expected[key], abs_tol=1e-10):
                    raise PermissionError("Saved native temperature/draw was modified")
            for name in ("raw_scores", "shifts", "adjusted_scores"):
                if any(not math.isclose(meta[name][k], expected[name][k],
                                        abs_tol=1e-10)
                       for k in keys):
                    raise PermissionError("Saved personality score calculus was modified")
        else:
            if (set(meta) != {"planner_costs", "draw", "operator_name"}
                    or not isinstance(meta.get("operator_name"), str)
                    or not meta["operator_name"]
                    or meta["operator_name"] not in meta.get("planner_costs", {})
                    or type(meta["draw"]) not in (int, float)
                    or not math.isfinite(meta["draw"])
                    or not 0 <= meta["draw"] < 1
                    or not isinstance(meta["planner_costs"], dict)
                    or not meta["planner_costs"]
                    or any(type(cost) not in (float, int)
                           or not math.isfinite(cost) or cost <= 0
                           for cost in meta["planner_costs"].values())):
                raise ValueError("Corrupt personality-weighted GOAP checkpoint")
        return entry

    def saved(self, *, route: Route, menu: Any,
              catalog_sha256: str) -> dict | None:
        return self._validate(
            route.boundary_id, route=route,
            menu=menu, catalog_sha256=catalog_sha256,
        )

    def commit(
        self, *, route: Route, menu: Any, catalog_sha256: str,
        selected_semantic_key: str, choice: Mapping[str, Any],
        persist: Callable[[], None],
    ) -> dict:
        if not callable(persist):
            raise TypeError("Durable checkpoint callback is required")
        previous = self.saved(
            route=route, menu=menu, catalog_sha256=catalog_sha256,
        )
        if previous is not None:
            if (previous["selected_semantic_key"] != selected_semantic_key
                    or previous["choice"] != dict(choice)):
                raise ValueError("Cannot reroll an already recorded personality choice")
            return previous

        if selected_semantic_key not in {o.semantic_key for o in menu.options}:
            raise ValueError("Chosen action was not part of the tagged menu")
        choices = self.router.record.setdefault("personality_choices", {})
        if len(choices) >= MAX_PERSONALITY_CHOICES:
            raise RuntimeError("Personality choice checkpoint at capacity")
        entry = {
            "version": 1, "route": route.selected,
            "actor": self.router.character_id,
            "menu_key": menu.menu_key,
            "catalog_sha256": catalog_sha256,
            "semantic_keys": sorted(o.semantic_key for o in menu.options),
            "tag_snapshot": {
                o.semantic_key: o.tags.model_dump(mode="json")
                for o in menu.options
            },
            "selected_semantic_key": selected_semantic_key,
            "request_id": deterministic_proposal_id(
                self.router, route.boundary_id,
            ),
            "observation_revision": route.observation_revision,
            "cognition_revision": route.cognition_revision,
            "choice": dict(choice),
        }
        choices[route.boundary_id] = entry
        try:
            # Validate before side-effect. This includes the full native-score
            # audit and all original actor provenance.
            self._validate(
                route.boundary_id, route=route, menu=menu,
                catalog_sha256=catalog_sha256,
            )
            if len(json.dumps(entry, sort_keys=True)) > MAX_CHOICE_RECORD_BYTES:
                raise ValueError("Personality choice record exceeded bound")
            persist()
        except BaseException:
            del choices[route.boundary_id]
            if not choices:
                del self.router.record["personality_choices"]
            raise
        return entry
