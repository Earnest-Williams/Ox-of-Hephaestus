"""Inventory every fitted equipment worksite against real authored ship routes.

No route in this report is a movement permission. A traversable-looking
drawing still requires live pressure, hatch, EVA, motor and crew checks.
"""
from __future__ import annotations

from collections import Counter

from world.ship_access_audit import audit_access_topology, authored_route
from world.ship_model import ShipWorldModel


class WorksiteAuditError(ValueError):
    """Equipment record is duplicated or the installed inventory is malformed."""


def audit_equipment_worksites(model: ShipWorldModel, equipment: list[dict],
                              *, anchor="CMD-PRIMARY") -> dict:
    """Classify physical machinery sites and *static* access dependencies.

    An unplaced component is reported rather than teleported to a guessed
    room. A disconnected room is reported rather than bridged. The selected
    route is only a shortest geometry witness; it need not be an admissible
    crew route, and may have freight-only or hazardous segments.
    """
    access = audit_access_topology(model, anchor=anchor)
    rooms = model.spaces_by_id
    links = {link.id: link for link in model.access_links}
    disconnected = set(access["unreachable_from_command"])
    if not isinstance(equipment, list):
        raise WorksiteAuditError("Installed equipment must be an array")
    seen_ids = set()
    by_family = Counter()
    route_classes = Counter()
    unplaced = []
    disconnected_items = []
    freight_passages = []
    exterior_items = []
    obligations = Counter()
    sited_rooms = set()
    paths = {}

    for number, item in enumerate(equipment):
        if not isinstance(item, dict):
            raise WorksiteAuditError("Non-object installed equipment row")
        ident, family, room_id = (item.get("id"), item.get("kind"),
                                  item.get("space_id"))
        if (not isinstance(ident, str) or not ident
                or ident in seen_ids or not isinstance(family, str)
                or not family):
            raise WorksiteAuditError(
                "Equipment identity or family invalid at row " + str(number))
        seen_ids.add(ident)
        by_family[family] += 1
        if not isinstance(room_id, str) or room_id not in rooms:
            unplaced.append(ident)
            route_classes["unplaced"] += 1
            continue
        sited_rooms.add(room_id)
        if room_id in disconnected:
            disconnected_items.append(ident)
            route_classes["disconnected"] += 1
            continue
        if room_id not in paths:
            paths[room_id] = authored_route(model, room_id, anchor=anchor)
        route = paths[room_id]
        tags = set()
        if room_id.startswith("EXT-"):
            tags.add("exterior_suit_required")
            exterior_items.append(ident)
        for source, link_id, destination in route:
            link = links[link_id]
            name = link.kind.lower()
            if "eva" in name or "external" in name or "airlock" in name:
                tags.add("exterior_transfer")
            if ("indexed" in name or "rotary" in name
                    or rooms[source].frame != rooms[destination].frame):
                tags.add("rotating_transfer")
            if (link.metadata.get("pressure_boundary") is True
                    or "hatch" in name):
                tags.add("pressure_or_hatch")
            if "freight" in name:
                tags.add("freight_segment_not_crew_authorised")
        if "freight_segment_not_crew_authorised" in tags:
            freight_passages.append(ident)
        for tag in tags:
            obligations[tag] += 1
        if "exterior_suit_required" in tags or "exterior_transfer" in tags:
            route_classes["exterior_or_eva"] += 1
        elif "rotating_transfer" in tags:
            route_classes["rotary_or_indexed"] += 1
        elif "freight_segment_not_crew_authorised" in tags:
            route_classes["route_includes_freight_hardware"] += 1
        elif "pressure_or_hatch" in tags:
            route_classes["pressure_hatch"] += 1
        else:
            route_classes["ordinary"] += 1

    return {
        "status": "WORKSITE_GEOMETRY_ONLY_NOT_LIVE_CREW_CLEARANCE",
        "model_version": model.model_version,
        "equipment": len(seen_ids),
        "family_count": len(by_family),
        "by_family": dict(sorted(by_family.items())),
        "sited_compartments": len(sited_rooms),
        "route_classes": dict(sorted(route_classes.items())),
        "selected_route_obligations": dict(sorted(obligations.items())),
        "unplaced_equipment": sorted(unplaced),
        "disconnected_equipment": sorted(disconnected_items),
        "selected_route_uses_freight_hardware": sorted(freight_passages),
        "exterior_equipment_ids": sorted(exterior_items),
        "exterior_equipment_count": len(exterior_items),
        "accessible_in_current_casualty": None,
    }
