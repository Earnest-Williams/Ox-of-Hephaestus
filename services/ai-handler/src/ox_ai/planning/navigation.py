"""Per-character GOAP travel over *learned local* world exit capabilities.

No omniscient map, no teleport, no direct Evennia DB access, and no AI
permission shortcut. A route is a hypothesis. Each movement uses the
authenticated character's ordinary stock Evennia exit command and must be
confirmed by a fresh actor-scoped world capability observation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ox_ai.planning.goap import GoapAction, GoapPlanner, PlanUnavailable
from ox_ai.ports.evennia.capabilities import (
    CapabilitySnapshot, ExitCapability, _name, _ref,
)


class RouteUnreachable(RuntimeError):
    """No currently supported route or exploration frontier remains."""


class NavigationKnowledge:
    """Private, persistable *belief* graph owned by exactly one character."""

    VERSION = 1

    def __init__(self, actor_dbref: str, record: Mapping[str, Any] | None = None):
        self.actor_dbref = _ref(actor_dbref)
        self.rooms: dict[str, dict] = {}
        if record is not None:
            if (not isinstance(record, Mapping) or set(record) != {
                "version", "actor_dbref", "rooms"
            } or type(record["version"]) is not int
                    or record["version"] != self.VERSION
                    or record["actor_dbref"] != actor_dbref):
                raise PermissionError("Private navigation state belongs to another character")
            stored = record["rooms"]
            if not isinstance(stored, dict) or len(stored) > 64:
                raise ValueError("Invalid bounded route history")
            for room_id, details in stored.items():
                _ref(room_id)
                if not isinstance(details, dict) or set(details) != {"name", "exits"}:
                    raise ValueError("Malformed saved room observation")
                _name(details["name"])
                if not isinstance(details["exits"], list) or len(details["exits"]) > 16:
                    raise ValueError("Malformed saved exit collection")
                exits = tuple(ExitCapability.from_dict(x) for x in details["exits"])
                if len({x.command.lower() for x in exits}) != len(exits):
                    raise ValueError("Duplicate remembered exit")
                self.rooms[room_id] = {
                    "name": details["name"], "exits": tuple(exits),
                }

    def remember(self, observed: CapabilitySnapshot) -> None:
        """Replace this room's previously observed exits with fresh facts."""
        if observed.actor_dbref != self.actor_dbref:
            raise PermissionError("Another character's private observation")
        if observed.room_dbref is None:
            return
        if observed.room_dbref not in self.rooms and len(self.rooms) >= 64:
            raise ValueError("Route memory capacity exhausted")
        self.rooms[observed.room_dbref] = {
            "name": observed.room_name, "exits": observed.exits,
        }

    def to_record(self) -> dict:
        """JSON-safe history; authoritative current location is never stored."""
        return {
            "version": self.VERSION, "actor_dbref": self.actor_dbref,
            "rooms": {
                room_id: {
                    "name": rec["name"],
                    "exits": [
                        {
                            "exit_dbref": e.exit_dbref,
                            "command": e.command,
                            "destination_dbref": e.destination_dbref,
                            "destination_name": e.destination_name,
                        }
                        for e in rec["exits"]
                    ],
                }
                for room_id, rec in sorted(self.rooms.items())
            },
        }

    def _operators(self, forbidden: set[tuple[str, str]]) -> tuple[GoapAction, ...]:
        actions = []
        for room_id, rec in sorted(self.rooms.items()):
            for ex in rec["exits"]:
                if (room_id, ex.exit_dbref) in forbidden:
                    continue
                actions.append(GoapAction(
                    name=f"exit:{room_id}:{ex.exit_dbref}",
                    requires=frozenset({f"at:{room_id}"}),
                    adds=frozenset({f"at:{ex.destination_dbref}"}),
                    removes=frozenset({f"at:{room_id}"}),
                    cost=1, verb=ex.command, target=ex.destination_dbref,
                ))
        return tuple(actions)

    def next_step(
        self, current_room: str, goal: str,
        *, forbidden: set[tuple[str, str]],
    ) -> tuple[str, ExitCapability] | None:
        """Plan shortest learned route; otherwise target an unexplored frontier."""
        _ref(current_room)
        if not isinstance(goal, str) or not goal or len(goal) > 120:
            raise ValueError("Destination must be an explicit room name or DB ref")
        actions = self._operators(forbidden)
        if not actions:
            raise RouteUnreachable("No traversable learned exits remain")
        planner = GoapPlanner(actions, expansion_cap=512)
        start = frozenset({f"at:{current_room}"})
        known_names = {room_id: rec["name"] for room_id, rec in self.rooms.items()}
        for rec in self.rooms.values():
            for edge in rec["exits"]:
                if edge.destination_dbref in known_names:
                    if known_names[edge.destination_dbref] != edge.destination_name:
                        # Older knowledge should not override a newer local
                        # observation of an adjacent room's identity.
                        continue
                else:
                    known_names[edge.destination_dbref] = edge.destination_name

        if goal.startswith("#"):
            destination_ids = [goal] if goal in known_names else []
        else:
            destination_ids = [room_id for room_id, name in known_names.items()
                               if name.casefold() == goal.casefold()]
        if len(destination_ids) > 1:
            raise RouteUnreachable("Destination room name is ambiguous")
        candidates = []
        if destination_ids:
            try:
                direct = planner.plan(start, {f"at:{destination_ids[0]}"})
                if direct.actions:
                    candidates.append((0, direct.total_cost, destination_ids[0],
                                       direct.actions[0]))
            except PlanUnavailable:
                pass
        # If the destination was not discovered or its old route is blocked,
        # search the nearest not-yet-surveyed room. No global navigation graph
        # is supplied by the world or invented by the model.
        frontier = sorted({
            edge.destination_dbref for rec in self.rooms.values()
            for edge in rec["exits"] if edge.destination_dbref not in self.rooms
        })
        for candidate_id in frontier:
            try:
                p = planner.plan(start, {f"at:{candidate_id}"})
            except PlanUnavailable:
                continue
            if p.actions:
                candidates.append((1, p.total_cost, candidate_id, p.actions[0]))
        if not candidates:
            raise RouteUnreachable("No known path or reachable unexplored compartment")
        _, _cost, _target, action = min(candidates, key=lambda x: (x[0], x[1], x[2]))
        if not action.name.startswith("exit:"):
            raise PermissionError("GOAP proposed an action outside learned exits")
        origin, exit_id = action.name[len("exit:"):].split(":", 1)
        rec = self.rooms.get(origin)
        if rec is None:
            raise PermissionError("GOAP planned an unknown origin room")
        capability = next((e for e in rec["exits"] if e.exit_dbref == exit_id), None)
        if capability is None or capability.command != action.verb:
            raise PermissionError("GOAP edge no longer matches stored world affordance")
        return origin, capability


@dataclass(frozen=True)
class NavigationResult:
    status: str
    final_room: str | None
    final_room_name: str | None
    traversed_exits: tuple[str, ...]
    observations: int
    reason: str


class CrewNavigator:
    """Independent role-scoped exploration with real authenticated exits."""

    def __init__(self, port, *, brain=None, knowledge: NavigationKnowledge | None = None):
        self.port = port
        actor = port.client.character_dbref
        if brain is not None and brain.character_id != actor:
            raise PermissionError("Navigator cannot read or move another crew body")
        if knowledge is not None and knowledge.actor_dbref != actor:
            raise PermissionError("Character-private maps cannot be shared")
        self.brain = brain
        self.knowledge = knowledge if knowledge is not None else NavigationKnowledge(actor)

    def _learn(self, observation: CapabilitySnapshot) -> None:
        if observation.actor_dbref != self.knowledge.actor_dbref:
            raise PermissionError("Received somebody else's physical location")
        self.knowledge.remember(observation)
        if self.brain is not None and observation.room_dbref is not None:
            exits = ", ".join(
                f"{x.command} to {x.destination_name}" for x in observation.exits
            )
            self.brain.observe_local(
                "Locally observed exits",
                f"{observation.room_name} ({observation.room_dbref}); {exits or 'none'}",
            )

    async def navigate(self, destination: str, *, max_movements: int = 16) -> NavigationResult:
        if (type(max_movements) is not int or not 1 <= max_movements <= 64):
            raise ValueError("Navigation travel budget must be 1-64 moves")
        traversed: list[str] = []
        attempts = 0
        observations = 0
        forbidden: set[tuple[str, str]] = set()
        snapshot = await self.port.observe()
        observations += 1
        self._learn(snapshot)
        while True:
            if snapshot.room_dbref is None:
                return NavigationResult("blocked", None, None, tuple(traversed),
                                        observations, "Outside the traversable ship")
            if (snapshot.room_dbref == destination
                    or snapshot.room_name.casefold() == destination.casefold()):
                return NavigationResult(
                    "arrived", snapshot.room_dbref, snapshot.room_name,
                    tuple(traversed), observations, "Verified by local world observation",
                )
            if attempts >= max_movements:
                return NavigationResult("blocked", snapshot.room_dbref,
                                        snapshot.room_name, tuple(traversed),
                                        observations, "Bounded navigation budget exhausted")
            try:
                step = self.knowledge.next_step(
                    snapshot.room_dbref, destination, forbidden=forbidden
                )
            except RouteUnreachable as exc:
                return NavigationResult("blocked", snapshot.room_dbref,
                                        snapshot.room_name, tuple(traversed),
                                        observations, str(exc))
            if step is None:
                raise RuntimeError("No planning step despite being away from destination")
            origin, planned_exit = step
            if origin != snapshot.room_dbref:
                raise PermissionError("GOAP attempted remote exit traversal")
            attempts += 1
            next_snap, succeeded = await self.port.traverse(snapshot, planned_exit)
            observations += 2  # refreshed before traverse + arrival check
            if succeeded:
                traversed.append(planned_exit.command)
            elif next_snap.room_dbref == snapshot.room_dbref:
                # Treat a withdrawn capability/late closed hatch as blocked
                # for THIS run; never retry unboundedly from stale beliefs.
                forbidden.add((origin, planned_exit.exit_dbref))
            snapshot = next_snap
            self._learn(snapshot)
