"""Personality-weighted, *boundary-scoped* routing between GOAP and Concordia.

The route is a stable, persisted personal preference, NOT an error injection,
a substitute for a GOAP operator, or a grant of Evennia authority.

This opt-in prototype works with the existing authored CrewBlueprint,
GoapPlanner, CrewAgent, DecisionScheduler and ActionRequest contracts.
It never submits commands, asserts physical outcomes, reads a world database,
or sees any character's observations other than those in its own CrewAgent.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
import re
from collections.abc import Callable, Sequence
import uuid

from ox_ai.agents.crew import CommandOption, CrewAgent
from ox_ai.agents.crew_blueprints import CrewBlueprint
from ox_ai.planning.goap import GoapPlanner, PlanUnavailable
from ox_ai.ports.base import ActionRequest, WorldObservation


VERSION = 1
BOUNDARY_KINDS = frozenset({"routine", "ambiguous", "social", "urgent"})
_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,159}$")
MAX_BOUNDARIES = 2048
MAX_FEEDBACK = 2048


@dataclass(frozen=True, slots=True)
class PersonalState:
    """Character-local interpretation, not verified world physiology.

    0..1 values are bounded input ratings. In a production implementation
    these should be inferred from character observations, never omniscient
    world state or an arbitrary real-time background clock.
    """
    stress: float = 0.0
    fatigue: float = 0.0
    social_pressure: float = 0.0
    uncertainty: float = 0.0

    def __post_init__(self) -> None:
        for name in ("stress", "fatigue", "social_pressure", "uncertainty"):
            value = getattr(self, name)
            if (type(value) not in (float, int) or
                    not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError("Personal state must contain finite scores in 0..1")


@dataclass(frozen=True, slots=True)
class Route:
    boundary_id: str
    selected: str
    probability_llm: float
    roll: float
    observation_revision: int
    cognition_revision: int


@dataclass(frozen=True, slots=True)
class RoutedProposal:
    route: Route
    action: ActionRequest
    model_calls: int
    goap_action: str | None


class PersonalityRouter:
    """Own the actor-private routing ledger; caller checkpoints it durably.

    Decisions use a keyed BLAKE2b pseudorandom draw, independent of the
    Python random global stream and of evaluation order. The ledger freezes
    probability and route at each meaningful event/boundary: a new observation
    doesn't silently re-roll an in-progress physical operation.
    """

    def __init__(self, profile: CrewBlueprint, character_id: str, record: dict,
                 *, seed: str) -> None:
        if not isinstance(profile, CrewBlueprint):
            raise TypeError("Personality routing requires a validated blueprint")
        if not isinstance(character_id, str) or not re.fullmatch(r"#[1-9][0-9]*", character_id):
            raise ValueError("Routing requires an authenticated character ID")
        if not isinstance(seed, str) or not 8 <= len(seed) <= 128 or not _ID.fullmatch(seed):
            raise ValueError("A stable bounded checkpoint seed is required")
        if not isinstance(record, dict):
            raise TypeError("Mutable persistent routing record required")
        self.profile = profile
        self.character_id = character_id
        self.record = record
        signature = hashlib.sha256(json.dumps(
            profile.to_record(), sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        if record:
            if (record.get("version") != VERSION
                    or record.get("character_id") != character_id
                    or record.get("person_id") != profile.person_id
                    or record.get("profile_sha256") != signature
                    or record.get("seed") != seed
                    or type(record.get("reliance_basis_points")) is not int
                    or not -2000 <= record["reliance_basis_points"] <= 2000
                    or not isinstance(record.get("boundaries"), dict)
                    or not isinstance(record.get("feedback"), dict)):
                raise PermissionError("Routing ledger cannot be rebound or reconfigured")
            if (len(record["boundaries"]) > MAX_BOUNDARIES
                    or len(record["feedback"]) > MAX_FEEDBACK):
                raise ValueError("Routing ledger is unbounded")
        else:
            record.update({
                "version": VERSION, "character_id": character_id,
                "person_id": profile.person_id,
                "profile_sha256": signature, "seed": seed,
                "reliance_basis_points": 0,
                "boundaries": {}, "feedback": {},
            })
        self._validate_saved_entries()

    def _validate_saved_entries(self) -> None:
        for key, item in self.record["boundaries"].items():
            if (not isinstance(key, str) or not _ID.fullmatch(key)
                    or not isinstance(item, dict)
                    or set(item) != {
                        "selected", "probability_llm", "roll",
                        "observation_revision", "cognition_revision", "kind",
                    } or item["selected"] not in ("goap", "llm")
                    or item["kind"] not in BOUNDARY_KINDS
                    or any(type(item[k]) is not int or item[k] < 0
                           for k in ("observation_revision", "cognition_revision"))
                    or any(type(item[k]) not in (float, int)
                           or not math.isfinite(item[k])
                           or not 0 <= item[k] <= 1
                           for k in ("probability_llm", "roll"))):
                raise ValueError("Corrupt historical routing decision")
        for key, val in self.record["feedback"].items():
            if (not isinstance(key, str) or not _ID.fullmatch(key)
                    or not isinstance(val, dict)
                    or set(val) != {"boundary_id", "interpretation"}
                    or val["boundary_id"] not in self.record["boundaries"]
                    or val["interpretation"] not in ("success", "failure")):
                raise ValueError("Corrupt perceived-consequence ledger")

    def probability(self, state: PersonalState, kind: str) -> float:
        if not isinstance(state, PersonalState) or kind not in BOUNDARY_KINDS:
            raise ValueError("Invalid routing situation")
        traits = dict(self.profile.traits)
        normalized = lambda key: (traits[key] - 50) / 50
        # Authored starting rates, NOT an empirical personality measurement.
        # All terms are explicit and testable. Deliberately no random
        # "mistake" term: the LLM remains free to choose the GOAP option.
        p = (
            0.19
            + 0.11 * normalized("openness")
            + 0.12 * normalized("risk_tolerance")
            + 0.14 * normalized("authority_challenge")
            - 0.16 * normalized("conscientiousness")
            + 0.09 * state.stress * (1 + normalized("neuroticism") * 0.5)
            + 0.06 * state.fatigue
            + 0.10 * state.social_pressure
            + 0.09 * state.uncertainty
            + {"routine": 0.0, "ambiguous": 0.08,
               "social": 0.13, "urgent": -0.06}[kind]
            + self.record["reliance_basis_points"] / 10000
        )
        return round(min(0.9, max(0.02, p)), 6)

    def _draw(self, boundary_id: str) -> float:
        digest = hashlib.blake2b(
            json.dumps((self.record["seed"], self.character_id, boundary_id),
                       separators=(",", ":")).encode("utf-8"),
            digest_size=8, person=b"ox-route-v1",
        ).digest()
        return int.from_bytes(digest, "big") / 2**64

    def select(self, *, boundary_id: str, kind: str, state: PersonalState,
               observation_revision: int, cognition_revision: int,
               persist: Callable[[], None]) -> Route:
        """Freeze the route, checkpoint BEFORE any model call or action proposal.

        A caller must use a world-evidence-derived id for the decision boundary
        and the same ID for recoveries. New material evidence warrants a NEW
        boundary, not an unrecorded new roll of an outstanding operation.
        """
        if not isinstance(boundary_id, str) or not _ID.fullmatch(boundary_id):
            raise ValueError("Boundary ID must be a bounded stable event key")
        if kind not in BOUNDARY_KINDS or not isinstance(state, PersonalState):
            raise ValueError("Unknown decision situation")
        if (type(observation_revision) is not int or observation_revision < 0
                or type(cognition_revision) is not int or cognition_revision < 0):
            raise ValueError("Invalid actor-scoped observation/cognition revision")
        if not callable(persist):
            raise TypeError("Durable checkpoint callback required")
        saved = self.record["boundaries"].get(boundary_id)
        if saved is not None:
            if saved["kind"] != kind:
                raise ValueError("Replayed boundary changed kind")
            # Persisted route remains authoritative for this personal
            # preference even if new memories arrive before a resumed action.
            return Route(boundary_id, saved["selected"], saved["probability_llm"],
                         saved["roll"], saved["observation_revision"],
                         saved["cognition_revision"])
        if len(self.record["boundaries"]) >= MAX_BOUNDARIES:
            raise RuntimeError("Routing ledger full; archive safely before continuing")
        p = self.probability(state, kind)
        roll = self._draw(boundary_id)
        selected = "llm" if roll < p else "goap"
        entry = {
            "kind": kind, "selected": selected,
            "probability_llm": p, "roll": roll,
            "observation_revision": observation_revision,
            "cognition_revision": cognition_revision,
        }
        self.record["boundaries"][boundary_id] = entry
        try:
            persist()
        except BaseException:
            del self.record["boundaries"][boundary_id]
            raise
        return Route(boundary_id, selected, p, roll,
                     observation_revision, cognition_revision)

    def perceived_consequence(self, *, boundary_id: str,
                               observation: WorldObservation,
                               interpretation: str,
                               persist: Callable[[], None]) -> None:
        """A character's own *interpretation*, never an authoritative outcome.

        A received observation is provenance for the character's belief,
        not proof of real equipment success. Do not change world receipts.
        Each source is applied at most once even after restart.
        """
        if boundary_id not in self.record["boundaries"]:
            raise KeyError("Cannot learn from an unencountered boundary")
        if (not isinstance(observation, WorldObservation)
                or observation.character_id != self.character_id
                or not isinstance(observation.source_event_id, str)
                or not _ID.fullmatch(observation.source_event_id)):
            raise PermissionError("Feedback needs actor-addressed source evidence")
        if interpretation not in ("success", "failure") or not callable(persist):
            raise ValueError("Invalid perceived outcome or checkpoint callback")
        source_id = observation.source_event_id
        existing = self.record["feedback"].get(source_id)
        if existing is not None:
            if existing != {"boundary_id": boundary_id,
                            "interpretation": interpretation}:
                raise ValueError("Same evidence cannot be applied to a different strategy or interpretation")
            return
        if len(self.record["feedback"]) >= MAX_FEEDBACK:
            raise RuntimeError("Perceived-outcome ledger at capacity")
        prior = self.record["reliance_basis_points"]
        # Reinforce whichever strategy the character actually used.
        # A successful GOAP outcome discourages future improvisation;
        # successful LLM reliance encourages it. Failure generally reverses
        # that association; a highly authority-challenging character can
        # defensively *increase* reliance after an LLM failure.
        selected = self.record["boundaries"][boundary_id]["selected"]
        challenge = dict(self.profile.traits)["authority_challenge"]
        if selected == "llm":
            step = 350 if interpretation == "success" else (-350 if challenge < 75 else 80)
        else:
            step = -350 if interpretation == "success" else 350
        self.record["feedback"][source_id] = {
            "boundary_id": boundary_id, "interpretation": interpretation,
        }
        self.record["reliance_basis_points"] = max(
            -2000, min(2000, prior + step))
        try:
            persist()
        except BaseException:
            del self.record["feedback"][source_id]
            self.record["reliance_basis_points"] = prior
            raise


class CharacterRouteController:
    """Choose GOAP's first planned action OR consult a real native mind.

    The returned ActionRequest is a PROPOSAL, not an executed command.
    A caller must use the existing durable WorkStepLedger and Evennia port
    for actual effects. No automatic fallback on inference failure.
    """
    def __init__(self, router: PersonalityRouter, scheduler, *, role: str,
                 decider_engine=None):
        if not isinstance(router, PersonalityRouter):
            raise TypeError("Character routing needs a persistent router")
        if not isinstance(role, str) or not role or len(role) > 64:
            raise ValueError("Invalid actor role")
        self.router, self.scheduler, self.role = router, scheduler, role
        self.decider_engine = decider_engine  # Opt-in per-boundary native scorer backend.

    async def decide(
        self, *, agent: CrewAgent, planner: GoapPlanner,
        beliefs: frozenset[str], goals: frozenset[str],
        options: Sequence[CommandOption], boundary_id: str,
        kind: str, state: PersonalState,
        persist: Callable[[], None],
        menu_key: str | None = None,
    ) -> RoutedProposal:
        if not isinstance(agent, CrewAgent) or agent.identity.character_id != self.router.character_id:
            raise PermissionError("Cannot route another character's cognition")
        if agent.blueprint != self.router.profile:
            raise PermissionError("Cannot route a different psychological profile")
        if not isinstance(planner, GoapPlanner):
            raise TypeError("GOAP must be an actual symbolic planner")
        offered = tuple(options)
        if not 2 <= len(offered) <= 26 or any(not isinstance(o, CommandOption) for o in offered):
            raise ValueError("A finite offered action menu is required")
        signatures = [(o.verb, o.target, tuple(sorted(o.arguments.items()))) for o in offered]
        if len(set(signatures)) != len(signatures) or len({o.label for o in offered}) != len(offered):
            raise ValueError("Duplicate available actions")
        feature = os.environ.get("OX_PERSONALITY_CHOICE", "0")
        if feature not in ("0", "1"):
            raise ValueError("OX_PERSONALITY_CHOICE must be exactly 0 or 1")
        if feature == "1":
            if not isinstance(menu_key, str) or not menu_key:
                raise ValueError("Opt-in personality choice requires an explicit tagged menu key")
            from ox_ai.runtime.g16_decision_controller import decide_g16
            return await decide_g16(
                self, agent=agent, planner=planner,
                beliefs=beliefs, goals=goals, offered=offered,
                boundary_id=boundary_id, kind=kind, state=state,
                persist=persist, menu_key=menu_key,
            )
        route = self.router.select(
            boundary_id=boundary_id, kind=kind, state=state,
            observation_revision=agent.revision,
            cognition_revision=agent.cognition_revision,
            persist=persist,
        )
        if route.selected == "goap":
            plan = planner.plan(beliefs, goals)
            if not plan.actions:
                raise PlanUnavailable("GOAP reached its goal; no new action proposal")
            action = plan.actions[0]
            choices = [o for o in offered if (
                o.verb, o.target, tuple(sorted(o.arguments.items()))
            ) == (action.verb, action.target, action.arguments)]
            if len(choices) != 1:
                raise PlanUnavailable("Planned action is not in the offered world menu")
            choice = choices[0]
            proposal = ActionRequest(
                request_id=uuid.uuid4().hex,
                character_id=agent.identity.character_id,
                verb=choice.verb, target=choice.target,
                arguments=dict(choice.arguments),
                agent_revision=agent.revision,
            )
            return RoutedProposal(route, proposal, 0, action.name)
        # The existing Concordia entity already receives all stable trait
        # dimensions and profile history via CharacterProfile. Add transient
        # actor-self-assessed context ONLY to this one choice prompt.
        description = (
            "Character-local self-assessment; not a world observation, "
            "permission, order, or fact about other people. "
            f"Situation={kind}. Subjective stress={state.stress:.2f}, "
            f"fatigue={state.fatigue:.2f}, social_pressure={state.social_pressure:.2f}, "
            f"uncertainty={state.uncertainty:.2f}. "
            "All offered options remain choices; there is no instruction "
            "to make an error or to ignore an observed procedure."
        )
        before = agent.usage.total_calls
        action = await self.scheduler.decide(
            self.role, agent, offered, decision_context=description,
        )
        return RoutedProposal(route, action, agent.usage.total_calls - before, None)
