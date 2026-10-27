"""G19 authored access graph audit, independent of Evennia or switch state.

This is a route *inventory*, not proof that a hatch is presently open,
an indexer synchronised, an EVA suit charged or a damaged passage safe.
"""
from __future__ import annotations

from collections import Counter, deque

from world.ship_model import ShipWorldModel


class ShipAccessAuditError(ValueError):
    """The fitted ship has missing, contradictory or unreachable access."""


def audit_access_topology(model: ShipWorldModel, *, anchor="CMD-PRIMARY",
                          require_connected=False) -> dict:
    """Index each physical bidirectional link and report reachable spaces.

    A model link is the authored geometry, not an unrestricted movement
    permission. Cross-frame links remain subject to crew-access preflight.
    """
    rooms = model.spaces_by_id
    if not rooms or len(rooms) != len(model.spaces):
        raise ShipAccessAuditError("Missing or duplicate authored spaces")
    if anchor not in rooms:
        raise ShipAccessAuditError("Ship command anchor is not an installed space")
    adjacency = {name: [] for name in rooms}
    ids = set()
    kinds = Counter()
    cross_frame = Counter()
    pressure_boundaries = 0
    for link in model.access_links:
        if (link.id in ids or link.from_id == link.to_id
                or link.from_id not in rooms or link.to_id not in rooms):
            raise ShipAccessAuditError("Invalid authored physical link: " + link.id)
        ids.add(link.id)
        adjacency[link.from_id].append((link.to_id, link.id))
        adjacency[link.to_id].append((link.from_id, link.id))
        kinds[link.kind] += 1
        if rooms[link.from_id].frame != rooms[link.to_id].frame:
            cross_frame[link.kind] += 1
        if link.metadata.get("pressure_boundary") is True:
            pressure_boundaries += 1

    parents = {anchor: None}
    queue = deque([anchor])
    while queue:
        current = queue.popleft()
        for neighbor, link_id in adjacency[current]:
            if neighbor not in parents:
                parents[neighbor] = (current, link_id)
                queue.append(neighbor)
    unreached = sorted(set(rooms) - set(parents))
    components = []
    unseen = set(rooms)
    while unseen:
        origin = min(unseen)
        seen = {origin}
        stack = [origin]
        while stack:
            name = stack.pop()
            for neighbor, _ in adjacency[name]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        unseen.difference_update(seen)
        components.append({"size": len(seen), "example": min(seen)})
    components.sort(key=lambda row: (-row["size"], row["example"]))
    outcome = {
        "status": "STATIC_ROUTES_ONLY",
        "model_version": model.model_version,
        "spaces": len(rooms),
        "physical_links": len(ids),
        "installed_exit_directions_expected": len(ids) * 2,
        "reachable_from_command": len(parents),
        "unreachable_from_command": unreached,
        "component_sizes": [row["size"] for row in components],
        "component_examples": [row["example"] for row in components],
        "link_kinds": dict(sorted(kinds.items())),
        "cross_frame_link_kinds": dict(sorted(cross_frame.items())),
        "rated_pressure_boundary_labels": pressure_boundaries,
        "equipment_sites_assessed": False,
    }
    if unreached and require_connected:
        raise ShipAccessAuditError(
            f"{len(unreached)} authored spaces have no physical route from "
            f"{anchor}: {', '.join(unreached[:16])}")
    return outcome


def authored_route(model: ShipWorldModel, destination: str,
                   *, anchor="CMD-PRIMARY") -> list[tuple[str, str, str]]:
    """Return a *static* link itinerary without implying operational clearance."""
    if destination not in model.spaces_by_id:
        raise ShipAccessAuditError("Unknown destination")
    if anchor not in model.spaces_by_id:
        raise ShipAccessAuditError("Unknown departure room")
    graph = {name: [] for name in model.spaces_by_id}
    for link in model.access_links:
        graph[link.from_id].append((link.to_id, link.id))
        graph[link.to_id].append((link.from_id, link.id))
    parents = {anchor: None}
    queue = deque([anchor])
    while queue:
        current = queue.popleft()
        if current == destination:
            break
        for neighbor, link_id in graph[current]:
            if neighbor not in parents:
                parents[neighbor] = (current, link_id)
                queue.append(neighbor)
    if destination not in parents:
        raise ShipAccessAuditError("No physical passage to " + destination)
    steps = []
    current = destination
    while current != anchor:
        predecessor, link_id = parents[current]
        steps.append((predecessor, link_id, current))
        current = predecessor
    return list(reversed(steps))


# A candidate for a *personnel* itinerary is not an approved live passage.
# Freight docking/freight-only conveyors and cargo portal mechanisms cannot
# transport a person, even if they shorten the static geometry graph.
# Weight special operations heavily so an ordinary interior route wins over
# a nominally shorter EVA journey.
_PERSONNEL_LINK_COST = {
    "pressure_door": 1, "service_door": 1, "door": 1,
    "cargo_service_door": 1, "cabin_door": 1,
    "pressure_hatch": 1, "service_hatch": 1,
    "store_door": 1, "fire_door": 1,
    "service_corridor": 1, "internal_access": 1,
    "service_panel": 20,
    "indexed_rotary_transfer": 100, "indexer_hatch": 100,
    "service_airlock": 1000,
    "eva_rail": 1000, "airlock_outer_hatch": 1000,
    "eva_work_platform_transfer": 1000,
}


def candidate_personnel_routes(model: ShipWorldModel, *,
                               anchor="CMD-PRIMARY") -> dict:
    """Return geometry-only, least-special-operation personnel route witnesses.

    Excluded freight kinds are deliberate, not silently converted into
    crew corridors. Rated doors, vacuum work, indexers and hatch positions
    still need the real Evennia crew traversal preflight when used.
    """
    from heapq import heappop, heappush
    audit_access_topology(model, anchor=anchor)
    graph = {key: [] for key in model.spaces_by_id}
    for link in model.access_links:
        weight = _PERSONNEL_LINK_COST.get(link.kind)
        if weight is None:
            continue
        graph[link.from_id].append((link.to_id, link.id, weight))
        graph[link.to_id].append((link.from_id, link.id, weight))
    distance = {anchor: (0, 0)}
    parents = {anchor: None}
    heap = [(0, 0, anchor)]
    while heap:
        cost, hops, current = heappop(heap)
        if (cost, hops) != distance[current]:
            continue
        for neighbor, link_id, weight in sorted(graph[current]):
            candidate = (cost + weight, hops + 1)
            if candidate < distance.get(neighbor, (float("inf"), float("inf"))):
                distance[neighbor] = candidate
                parents[neighbor] = (current, link_id)
                heappush(heap, (candidate[0], candidate[1], neighbor))
    result = {}
    for destination in parents:
        steps = []
        current = destination
        while current != anchor:
            source, link_id = parents[current]
            steps.append((source, link_id, current))
            current = source
        result[destination] = list(reversed(steps))
    return result
