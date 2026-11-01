"""Materialise the canonical Ox topology as persistent Evennia objects.

This is deliberately only the spatial integration slice. It creates the real
421-space ship and its authored physical connections, but leaves ordinary
traversal Developer-only until pressure, EVA, rotation and machinery interlocks
are represented as world-owned state.
"""

from __future__ import annotations

from typing import Any

from evennia.objects.models import ObjectDB
from evennia.utils.create import create_object

from world.ship_model import AccessLinkSpec, ShipWorldModel, SpaceSpec, load_ship_model
from world import planner_stats
from world.tagged import objects_tagged

WORLD_CATEGORY = "ox_ship_world"
ROOT_MARKER = "world-root"
ENTRY_SPACE_ID = "CMD-PRIMARY"
# Analyse once this many spaces exist so the rest of the build plans well.
STATISTICS_SAMPLE_SPACES = 24


def find_world_entity(marker: str):
    """Resolve one canonical-world object by durable tag."""
    matches = objects_tagged(marker, WORLD_CATEGORY)
    if len(matches) > 1:
        raise RuntimeError(f"Duplicate canonical Ox tag {marker!r}; refusing to guess")
    return matches[0] if matches else None


def find_ship_space(space_id: str):
    """Resolve one current-installation space by its source-model id."""
    return find_world_entity(f"space:{space_id}")


def _ensure(marker: str, typeclass: str, key: str, **kwargs):
    existing = find_world_entity(marker)
    if existing is not None:
        return existing, False
    return (
        create_object(
            typeclass,
            key=key,
            tags=[(marker, WORLD_CATEGORY)],
            **kwargs,
        ),
        True,
    )


def _space_description(spec: SpaceSpec) -> str:
    kind = spec.kind.replace("_", " ")
    zone = spec.zone.replace("_", " ")
    frame = spec.frame.replace("_", " ")
    text = f"{spec.name} is a {kind} space in the Ox's {zone} zone, in the {frame} frame."
    sector = spec.metadata.get("damage_control_sector")
    if isinstance(sector, str) and sector:
        text += f" Damage-control sector: {sector.replace('_', ' ')}."
    return text


def _materialise_space(spec: SpaceSpec, model_version: str):
    room, created = _ensure(
        f"space:{spec.id}",
        "typeclasses.ship_world.CanonicalShipRoom",
        spec.name,
        nohome=True,
    )
    room.db.ox_space_id = spec.id
    room.db.ox_space_kind = spec.kind
    room.db.ox_frame = spec.frame
    room.db.ox_zone = spec.zone
    room.db.ox_damage_control_sector = spec.metadata.get("damage_control_sector")
    room.db.ox_source_model_version = model_version
    room.db.ox_static = dict(spec.metadata)
    if created:
        room.db.ox_current_condition = spec.current_condition
        room.db.desc = _space_description(spec)
    return room, created


def _access_name(destination, link: AccessLinkSpec) -> str:
    label = link.metadata.get("name") or link.metadata.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    return f"{destination.key} [{link.kind.replace('_', ' ')}]"


def _materialise_access(
    link: AccessLinkSpec,
    direction: str,
    origin,
    destination,
    destination_id: str,
    model_version: str,
):
    marker = f"access:{link.id}:{direction}"
    access, created = _ensure(
        marker,
        "typeclasses.ship_world.CanonicalShipAccess",
        _access_name(destination, link),
        location=origin,
        destination=destination,
        aliases=[destination.key, destination_id],
    )
    access.db.ox_access_link_id = link.id
    access.db.ox_access_kind = link.kind
    access.db.ox_access_direction = direction
    access.db.ox_source_model_version = model_version
    access.db.ox_static = dict(link.metadata)
    # Old Developer-only access locks survive code changes on persistent exits.
    # The runtime movement gate now makes the authoritative decision.
    access.locks.add("traverse:all()")
    access.db.ox_integration_state = "live_world_gated"
    return access, created


def _ensure_developer_entry(spaces: dict[str, Any], model_version: str) -> None:
    """Expose the real ship separately from the legacy proving-ground board exit."""
    bridge = spaces.get(ENTRY_SPACE_ID)
    limbo = ObjectDB.objects.filter(id=2).first()
    if bridge is None or limbo is None or limbo.key.lower() != "limbo":
        return

    board, _created = _ensure(
        "entry:board-ox",
        "typeclasses.ship_world.CanonicalShipAccess",
        "board ox",
        location=limbo,
        destination=bridge,
        aliases=["ox", "canonical ship"],
    )
    board.db.ox_access_link_id = "runtime-entry"
    board.db.ox_access_kind = "development_entry"
    board.db.ox_source_model_version = model_version

    leave, _created = _ensure(
        "entry:leave-ox",
        "typeclasses.ship_world.CanonicalShipAccess",
        "disembark ox",
        location=bridge,
        destination=limbo,
        aliases=["leave ox"],
    )
    leave.db.ox_access_link_id = "runtime-exit"
    leave.db.ox_access_kind = "development_entry"
    leave.db.ox_source_model_version = model_version


def build_canonical_ship(model: ShipWorldModel | None = None) -> dict[str, Any]:
    """Idempotently materialise the prepared full-ship topology.

    Existing live conditions and room descriptions are never reset. A newer
    source model may add missing objects and refresh static identity metadata,
    but removal/re-routing requires an explicit migration rather than deletion
    by deserialisation.
    """
    model = model or load_ship_model()
    root_name = model.principal.get("name")
    if not isinstance(root_name, str) or not root_name.strip():
        root_name = "Ox of Hephaestus"
    root, root_created = _ensure(
        ROOT_MARKER,
        "typeclasses.ship_world.ShipWorldRoot",
        f"{root_name} world model",
        nohome=True,
    )
    # Mark incomplete before work begins. If startup is interrupted, a later
    # ensure call resumes idempotently instead of trusting a partial graph.
    root.db.ox_topology_complete = False

    spaces: dict[str, Any] = {}
    created_spaces = 0
    for index, spec in enumerate(model.spaces):
        room, created = _materialise_space(spec, model.model_version)
        spaces[spec.id] = room
        created_spaces += int(created)
        if index == STATISTICS_SAMPLE_SPACES and created_spaces:
            planner_stats.refresh()
    if created_spaces:
        planner_stats.refresh()

    created_accesses = 0
    access_objects: dict[str, Any] = {}
    for link in model.access_links:
        forward, created = _materialise_access(
            link,
            "forward",
            spaces[link.from_id],
            spaces[link.to_id],
            link.to_id,
            model.model_version,
        )
        access_objects[f"{link.id}:forward"] = forward
        created_accesses += int(created)
        # The authored ship schema defines physical connections, not directed
        # transport. Every v0.4 and candidate v0.5 link has two exit objects.
        # Implement an explicit schema/version contract before adding one-way
        # semantics; arbitrary metadata is not a traversal permission source.
        reverse, created = _materialise_access(
            link,
            "reverse",
            spaces[link.to_id],
            spaces[link.from_id],
            link.from_id,
            model.model_version,
        )
        access_objects[f"{link.id}:reverse"] = reverse
        created_accesses += int(created)

    _ensure_developer_entry(spaces, model.model_version)

    root.db.ox_schema_version = model.schema_version
    root.db.ox_model_version = model.model_version
    root.db.ox_space_count = len(model.spaces)
    root.db.ox_access_link_count = len(model.access_links)
    root.db.ox_topology_complete = True

    return {
        "root": root,
        "root_created": root_created,
        "model": model,
        "spaces": spaces,
        "access": access_objects,
        "created_spaces": created_spaces,
        "created_accesses": created_accesses,
    }


def ensure_canonical_ship() -> dict[str, Any]:
    """Build the topology only when the deployed model is absent or incomplete."""
    model = load_ship_model()
    root = find_world_entity(ROOT_MARKER)
    if (
        root is not None
        and root.db.ox_topology_complete
        and root.db.ox_schema_version == model.schema_version
        and root.db.ox_model_version == model.model_version
        and int(root.db.ox_space_count or -1) == len(model.spaces)
        and int(root.db.ox_access_link_count or -1) == len(model.access_links)
        and (
            not model.access_links or
            getattr(
                getattr(find_world_entity(
                    f"access:{model.access_links[0].id}:forward"), "db", None),
                "ox_integration_state", None) == "live_world_gated"
        )
    ):
        return {
            "root": root,
            "root_created": False,
            "model": model,
            "spaces": None,
            "access": None,
            "created_spaces": 0,
            "created_accesses": 0,
            "skipped": True,
        }
    result = build_canonical_ship(model)
    result["skipped"] = False
    return result
