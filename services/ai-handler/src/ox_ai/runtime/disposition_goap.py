"""G16d experimental, non-authoritative personality-weighted GOAP costs.

The underlying planner still operates ONLY on actor beliefs. These weights
change predicted habit preferences, never Evennia permissions, procedures,
physical outcomes or equipment authority. Not switched on in the supervisor.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from ox_ai.agents.crew_blueprints import CrewBlueprint
from ox_ai.planning.goap import GoapPlanner

if TYPE_CHECKING:
    from ox_contracts import TaggedMenu
    from ox_ai.agents.crew import CommandOption


DIMENSIONS = ("risk", "deference", "social", "autonomy", "procedure")
DEFAULT_K = 0.5


def actor_dispositions(profile: CrewBlueprint) -> dict[str, float]:
    """Project the existing immutable Ox trait vector, not a second profile.

    All inputs come from the actor's own validated CrewBlueprint. Intentional
    author policy rather than statistically estimated human psychology.
    """
    if not isinstance(profile, CrewBlueprint):
        raise TypeError("An authenticated validated character blueprint is required")
    traits = dict(profile.traits)
    normal = lambda name: (traits[name] - 50.0) / 50.0
    result = {
        "risk": normal("risk_tolerance"),
        "deference": -normal("authority_challenge"),
        "social": (normal("collaboration") + normal("agreeableness")) / 2.0,
        "autonomy": (normal("authority_challenge") - normal("collaboration")) / 2.0,
        "procedure": normal("conscientiousness"),
    }
    if set(result) != set(DIMENSIONS) or any(
        not math.isfinite(value) or not -1.0 <= value <= 1.0
        for value in result.values()
    ):
        raise ValueError("The source psychological profile produced invalid dispositions")
    return result


def personality_goap_costs(
    planner: GoapPlanner, menu: TaggedMenu, profile: CrewBlueprint,
    *, offered: Sequence[CommandOption], k: float = DEFAULT_K,
) -> dict[str, float]:
    """Price *all* operator steps using the *same* G16a action metadata.

    Fail closed if any planner step is untagged, if the offered menu changed,
    or if a safety-critical menu lacks an independently authored safe policy.
    No implicit zero tags, shared-weight mutation or model fallback.
    """
    if not isinstance(planner, GoapPlanner):
        raise TypeError("Expected an existing symbolic GOAP planner")
    # Import lazily: legacy/unflagged handler usage needs no new dependency.
    from ox_contracts import TaggedMenu
    if not isinstance(menu, TaggedMenu):
        raise TypeError("Expected the exact shared G16a contract")
    if menu.safety_critical:
        raise PermissionError("Safety-critical weighting requires a separate authored safe policy")
    if type(k) not in (float, int) or not math.isfinite(k) or not 0.0 < k <= 2.0:
        raise ValueError("GOAP disposition gain must be positive and bounded")
    from ox_ai.agents.crew import CommandOption
    offered = tuple(offered)
    if any(not isinstance(o, CommandOption) for o in offered):
        raise TypeError("All offered commands must be typed CommandOptions")
    offered_sigs = {
        (o.verb, o.target, tuple(sorted(o.arguments.items()))) for o in offered
    }
    tagged_sigs = {action.signature for action in menu.options}
    if (len(offered_sigs) != len(offered)
            or offered_sigs != tagged_sigs):
        raise ValueError("The source offer does not match the authored G16a menu")

    by_signature = {a.signature: a for a in menu.options}
    dispositions = actor_dispositions(profile)
    prices = {}
    for operator in planner.actions:
        # A full multistep planner needs tags for *every* intermediate action,
        # not just one possible first step. A duplicate verb/target in a
        # distinct symbolic planning phase needs an explicit future contract.
        signature = (operator.verb, operator.target, ())
        tag = by_signature.get(signature)
        if tag is None:
            raise ValueError(f"Untagged GOAP operator {operator.name!r}")
        lean = tag.tags.project(dispositions)
        multiplier = min(2.0, max(0.5, math.exp(-float(k) * lean)))
        value = float(operator.cost) * multiplier
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Disposition cost was not positive and finite")
        prices[operator.name] = value
    if set(prices) != {a.name for a in planner.actions}:
        raise AssertionError("Not every GOAP action was priced")
    return prices
