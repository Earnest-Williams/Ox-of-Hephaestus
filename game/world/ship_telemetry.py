"""Read-only, explicitly bounded spatial telemetry from canonical Evennia state.

No JSON-model conditions, NPC memory, character positions, journals, or
prototype-fixture internals are part of this projection. The authenticated
web view decides who may receive it; callers never get a mutation API.
"""

from __future__ import annotations

from evennia.objects.models import ObjectDB

from world.ship_world import ROOT_MARKER, WORLD_CATEGORY, find_world_entity

SCHEMA = "ox.telemetry.spatial/0.1"
EXPORTED_ATTRIBUTES = frozenset({"ox_space_id", "ox_current_condition"})


def _persisted_values(room) -> dict[str, object]:
    """Read a prefetched attribute set, avoiding per-room ORM lookups.

    Evennia's Attribute.value property unpickles stored values. Export only
    two explicitly allowlisted, low-sensitivity keys.
    """
    return {
        attribute.db_key: attribute.value
        for attribute in room.db_attributes.all()
        if attribute.db_key in EXPORTED_ATTRIBUTES
    }


def read_spatial_telemetry() -> dict[str, object]:
    """Return persisted spatial conditions, never inferred system health."""
    root = find_world_entity(ROOT_MARKER)
    expected = int(root.db.ox_space_count or 0) if root else 0
    version = str(root.db.ox_model_version or "") if root else ""
    complete = bool(root.db.ox_topology_complete) if root else False

    # The tag prefix excludes the world anchor, exits, and any prototype rooms.
    # Prefetching Attributes keeps the full-room scan at bounded query cost
    # rather than one or two separate SQL reads for every compartment.
    rooms = (
        ObjectDB.objects.filter(
            db_tags__db_category__iexact=WORLD_CATEGORY,
            db_tags__db_key__istartswith="space:",
        )
        .distinct()
        .prefetch_related("db_attributes")
    )
    states: list[dict[str, str]] = []
    for room in rooms:
        values = _persisted_values(room)
        space_id = values.get("ox_space_id")
        if not isinstance(space_id, str) or not space_id:
            continue
        condition = values.get("ox_current_condition")
        if not isinstance(condition, str) or not condition:
            condition = "unknown"
        states.append({"id": space_id, "condition": condition[:100]})
    states.sort(key=lambda state: state["id"])

    return {
        "schema": SCHEMA,
        "model_version": version,
        "topology_complete": bool(complete and expected and len(states) == expected),
        "scope": "developer_spatial_only",
        "coverage": {
            "spaces_expected": expected,
            "spaces_reporting": len(states),
            "equipment": "not_integrated",
            "service_networks": "not_integrated",
            "crew": "not_exported",
        },
        "space_states": states,
    }
