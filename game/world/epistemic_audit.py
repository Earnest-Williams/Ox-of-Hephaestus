"""OPERATOR-ONLY comparison of world facts with a character's private beliefs.

This module is not part of the authenticated character protocol, the
Concordia prompt/context, or the AI-handler's world port. A privileged
operator can bring together an authoritative world fact (from Evennia) and
a separate actor-private epistemic snapshot (from the handler) to assess
their relationship. Ordinary agents must never receive that joined view.

Importantly, unknown unknown is a *present, actor-relative* category of
world-known truths. It does not require eventual discovery or a recorded
surprise. A post-discovery surprise is a different kind of event.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
import re
from typing import Literal

PROPOSITION = re.compile(r"[a-z][a-z0-9_.:-]{0,95}")
DBREF = re.compile(r"#[1-9][0-9]*")

Relation = Literal[
    "known_known", "known_unknown", "unknown_unknown",
    "modeled_belief", "mistaken_observation", "exposed_unassimilated",
]


@dataclass(frozen=True, slots=True)
class OperatorFactAssessment:
    """A privileged verdict; deliberately does not duplicate the secret."""

    relation: Relation
    belief_matches_world: bool | None = None


def classify_world_fact(
    *,
    proposition: str,
    actual_world_value: str | int | float | bool | None,
    actor_epistemics: Mapping,
    actor_dbref: str,
    world_time: float,
    evidence_disclosed_to_actor: bool,
) -> OperatorFactAssessment:
    """Compare ONE real world proposition against ONE character's perspective.

    This function does not fetch or transmit world facts. The operator must
    obtain them through an independently authorized world read and supply a
    correctly matched private actor snapshot. The caller also checks whether
    the world actually disclosed evidence of the proposition to this actor.
    It is NEVER a cognition input, a game command or a shipwide observation.

    A more general question (e.g., what is beyond the moon) does not turn
    every particular hidden fact there (e.g., a waiting pirate) into a
    known unknown. A specific question or belief must represent that fact.
    """
    if not isinstance(proposition, str) or not PROPOSITION.fullmatch(proposition):
        raise ValueError("A concrete, bounded world proposition is required")
    if not isinstance(actor_dbref, str) or not DBREF.fullmatch(actor_dbref):
        raise ValueError("Invalid world character ID")
    if type(world_time) not in (int, float) or not math.isfinite(world_time) or world_time < 0:
        raise ValueError("Invalid world clock")
    if type(evidence_disclosed_to_actor) is not bool:
        raise ValueError("Only a world-grounded disclosure flag is permitted")
    if (not isinstance(actor_epistemics, Mapping)
            or actor_epistemics.get("character_id") != actor_dbref):
        raise PermissionError("Foreign or missing actor knowledge snapshot")
    if type(actor_epistemics.get("version")) is not int or actor_epistemics["version"] != 1:
        raise ValueError("Unsupported actor knowledge schema")
    observations = actor_epistemics.get("observations")
    questions = actor_epistemics.get("questions")
    beliefs = actor_epistemics.get("beliefs")
    if not all(isinstance(entry, Mapping) for entry in (observations, questions, beliefs)):
        raise ValueError("Incomplete actor-private knowledge snapshot")
    if not isinstance(actual_world_value, (str, bool, int, float, type(None))):
        raise ValueError("Unsupported world fact type")
    if isinstance(actual_world_value, float) and not math.isfinite(actual_world_value):
        raise ValueError("Nonfinite world truth is not a fact")

    observation = observations.get(proposition)
    if observation is not None:
        if not isinstance(observation, Mapping):
            raise ValueError("Malformed actor observation")
        at = observation.get("at")
        ttl = observation.get("valid_for")
        if (type(at) not in (int, float) or type(ttl) not in (int, float)
                or not math.isfinite(at) or not math.isfinite(ttl)
                or ttl < 0 or at < 0):
            raise ValueError("Observation has invalid provenance time")
        if at <= world_time <= at + ttl:
            if type(observation.get("value")) is type(actual_world_value) and (
                observation["value"] == actual_world_value
            ):
                return OperatorFactAssessment("known_known")
            return OperatorFactAssessment("mistaken_observation")

    # Specific, acknowledged lack of current evidence is a known unknown.
    question = questions.get(proposition)
    if question is not None:
        if not isinstance(question, Mapping):
            raise ValueError("Malformed question state")
        if question.get("status") in ("open", "answered"):
            return OperatorFactAssessment("known_unknown")
        raise ValueError("Invalid question status")
    if observation is not None:
        # The actor is familiar with this proposition, but their evidence
        # for its *current* world value has expired.
        return OperatorFactAssessment("known_unknown")

    belief = beliefs.get(proposition)
    if belief is not None:
        if not isinstance(belief, Mapping):
            raise ValueError("Malformed belief record")
        if belief.get("state") == "hypothesis":
            # Even an accurate guess is NOT a known known. This alignment
            # is for operator diagnostics only and may not reach the agent.
            agrees = (type(belief.get("value")) is type(actual_world_value)
                      and belief["value"] == actual_world_value)
            return OperatorFactAssessment("modeled_belief", agrees)
        if belief.get("state") != "refuted":
            raise ValueError("Unsupported belief disposition")
        # Refuted belief still means this fact was conceptually considered.
        return OperatorFactAssessment("known_unknown")

    if evidence_disclosed_to_actor:
        # World evidence was addressed or perceived, but the model's
        # checkpoint did not assimilate it. This is an audit discrepancy,
        # NOT proof that the world fact was unknown or that it may be leaked.
        return OperatorFactAssessment("exposed_unassimilated")

    # This world fact already exists, but this character has no
    # proposition-specific knowledge, question, belief, or disclosure.
    # It can be classified NOW without ever showing the fact to the actor.
    return OperatorFactAssessment("unknown_unknown")
