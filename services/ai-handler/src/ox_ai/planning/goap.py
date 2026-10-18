"""Small, dependency-free GOAP engine with explicit symbolic action schemas.

The search operates on an agent's *beliefs*, never on Evennia's world database.
Action effects are planning predictions, not proof that an attempted command
actually changed the world. The caller must reconcile observed outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
from typing import Iterable


class PlanUnavailable(RuntimeError):
    """No safe plan exists in the agent's current action model and beliefs."""


@dataclass(frozen=True, slots=True)
class GoapAction:
    """A grounded operator with STRIPS preconditions/effects and positive cost."""

    name: str
    requires: frozenset[str] = field(default_factory=frozenset)
    adds: frozenset[str] = field(default_factory=frozenset)
    removes: frozenset[str] = field(default_factory=frozenset)
    cost: int = 1
    verb: str = ""
    target: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.verb or self.cost <= 0:
            raise ValueError("GOAP action needs a name, verb and positive cost")
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
    total_cost: int
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
    ) -> GoapPlan:
        start = frozenset(beliefs)
        goal = frozenset(goals)
        if goal.issubset(start):
            return GoapPlan((), 0, 0)
        disabled = frozenset(excluded)
        work = count()
        queue: list[tuple[int, int, frozenset[str], tuple[GoapAction, ...]]] = []
        heappush(queue, (0, next(work), start, ()))
        best = {start: 0}
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
                new_cost = price + action.cost
                if new_cost >= best.get(projected, float("inf")):
                    continue
                best[projected] = new_cost
                heappush(queue, (
                    new_cost, next(work), projected, steps + (action,)
                ))

        raise PlanUnavailable("No GOAP plan satisfies the goal from current beliefs")
