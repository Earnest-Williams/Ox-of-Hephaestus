"""Small, dependency-free GOAP engine with explicit symbolic action schemas.

The search operates on an agent's *beliefs*, never on Evennia's world database.
Action effects are planning predictions, not proof that an attempted command
actually changed the world. The caller must reconcile observed outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
import math
from typing import Iterable, Mapping


class PlanUnavailable(RuntimeError):
    """No safe plan exists in the agent's current action model and beliefs."""


@dataclass(frozen=True, slots=True)
class GoapAction:
    """A grounded operator with STRIPS preconditions/effects and positive cost."""

    name: str
    requires: frozenset[str] = field(default_factory=frozenset)
    adds: frozenset[str] = field(default_factory=frozenset)
    removes: frozenset[str] = field(default_factory=frozenset)
    cost: float = 1
    verb: str = ""
    target: str | None = None

    def __post_init__(self) -> None:
        if (not self.name or not self.verb
                or type(self.cost) not in (int, float)
                or not math.isfinite(self.cost) or self.cost <= 0):
            raise ValueError("GOAP action needs a name, verb and positive finite cost")
        if self.adds & self.removes:
            raise ValueError("An action may not add and delete the same fact")

    def applicable(self, facts: frozenset[str] | set[str]) -> bool:
        return self.requires.issubset(facts)

    def project(self, facts: frozenset[str]) -> frozenset[str]:
        """Hypothetical state after execution; NOT an observed world outcome."""
        return (facts - self.removes) | self.adds


@dataclass(frozen=True, slots=True)
class GoapPlan:
    actions: tuple[GoapAction, ...]
    total_cost: float
    expanded_states: int


class GoapPlanner:
    """Deterministic uniform-cost symbolic search (Dijkstra over fact sets).

    Positive action costs ensure that the first solution found is a minimum-
    cost plan within this action model. An expansion cap bounds worst-case
    planning work in the independent AI handler.
    """

    def __init__(self, actions: Iterable[GoapAction], *, expansion_cap: int = 4096):
        self.actions = tuple(actions)
        if not self.actions or len({a.name for a in self.actions}) != len(self.actions):
            raise ValueError("GOAP actions must have unique nonempty names")
        if expansion_cap < 1:
            raise ValueError("expansion_cap must be positive")
        self.expansion_cap = expansion_cap

    def plan(
        self,
        beliefs: Iterable[str],
        goals: Iterable[str],
        *,
        excluded: Iterable[str] = (),
        cost_overrides: Mapping[str, float] | None = None,
    ) -> GoapPlan:
        start = frozenset(beliefs)
        goal = frozenset(goals)
        if goal.issubset(start):
            return GoapPlan((), 0, 0)
        disabled = frozenset(excluded)
        # Validate the entire explicit override before search; omissions and
        # stale operator names must not silently become neutral personality.
        # The original operator costs remain intact for other characters.
        if cost_overrides is None:
            prices = {action.name: action.cost for action in self.actions}
        else:
            if not isinstance(cost_overrides, Mapping):
                raise TypeError("GOAP cost overrides must map all operator names")
            if set(cost_overrides) != {action.name for action in self.actions}:
                raise ValueError("GOAP cost overrides must cover exactly the planner")
            prices = dict(cost_overrides)
            if any(type(price) not in (int, float) or
                   not math.isfinite(price) or price <= 0 for price in prices.values()):
                raise ValueError("GOAP cost overrides must be finite and positive")
        work = count()
        queue: list[tuple[float, int, frozenset[str], tuple[GoapAction, ...]]] = []
        heappush(queue, (0, next(work), start, ()))
        best: dict[frozenset[str], float] = {start: 0}
        expanded = 0

        while queue:
            price, _serial, facts, steps = heappop(queue)
            if price != best.get(facts):
                continue
            if goal.issubset(facts):
                return GoapPlan(steps, price, expanded)
            if expanded >= self.expansion_cap:
                raise PlanUnavailable("GOAP search expansion budget exhausted")
            expanded += 1
            for action in self.actions:
                if action.name in disabled or not action.applicable(facts):
                    continue
                projected = action.project(facts)
                if projected == facts:
                    continue
                new_cost = price + prices[action.name]
                if new_cost >= best.get(projected, float("inf")):
                    continue
                best[projected] = new_cost
                heappush(queue, (
                    new_cost, next(work), projected, steps + (action,)
                ))

        raise PlanUnavailable("No GOAP plan satisfies the goal from current beliefs")
