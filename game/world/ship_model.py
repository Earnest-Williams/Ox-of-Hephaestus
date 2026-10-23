"""Load and validate the canonical Ox physical-world source model.

The JSON under ``design/ship`` is design/current-installation source data. This
module deliberately performs only structural validation and topology indexing;
Evennia objects created from it become the persistent runtime authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "ox.ship-world/0.1"
REQUIRED_TOP_LEVEL = (
    "schema_version",
    "model_version",
    "principal",
    "spaces",
    "access_links",
    "equipment",
    "service_nodes",
    "service_edges",
    "isolation_points",
    "modifications",
    "documentation_records",
    "maintenance_tasks",
    "inventories",
)


class ShipModelError(ValueError):
    """Raised when the prepared physical model is structurally unsafe to load."""


@dataclass(frozen=True, slots=True)
class SpaceSpec:
    """One persistent location in the canonical ship model."""

    id: str
    name: str
    kind: str
    frame: str
    zone: str
    current_condition: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AccessLinkSpec:
    """One authored physical connection between two canonical spaces."""

    id: str
    from_id: str
    to_id: str
    kind: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ShipWorldModel:
    """The runtime-relevant topology plus its source-model identity."""

    schema_version: str
    model_version: str
    principal: dict[str, Any]
    spaces: tuple[SpaceSpec, ...]
    access_links: tuple[AccessLinkSpec, ...]

    @property
    def spaces_by_id(self) -> dict[str, SpaceSpec]:
        """Index spaces by their durable source-model identifiers."""
        return {space.id: space for space in self.spaces}


def canonical_model_path() -> Path:
    """Return the repository path of the prepared current-installation model."""
    return Path(__file__).resolve().parents[2] / "design" / "ship" / "ox_full_ship.json"


def _record_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ShipModelError(f"{key!r} must be an array")
    if any(not isinstance(item, dict) for item in value):
        raise ShipModelError(f"{key!r} must contain only objects")
    return value


def _required_text(record: dict[str, Any], key: str, section: str, index: int) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ShipModelError(f"{section}[{index}] requires non-empty string {key!r}")
    return value


def load_ship_model(path: str | Path | None = None) -> ShipWorldModel:
    """Load the canonical model without turning source JSON into runtime truth.

    The loader verifies only the invariants needed to safely materialise a
    navigable object graph. Equipment, utilities, documentation and inventory
    remain in the source model for later integration slices.
    """
    source = Path(path) if path is not None else canonical_model_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ShipModelError(f"Unable to read Ox ship model {source}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ShipModelError("Ship model root must be an object")
    missing = [key for key in REQUIRED_TOP_LEVEL if key not in payload]
    if missing:
        raise ShipModelError(f"Ship model missing required sections: {', '.join(missing)}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ShipModelError(
            f"Unsupported ship schema {payload['schema_version']!r}; expected {SCHEMA_VERSION!r}"
        )
    if not isinstance(payload["model_version"], str) or not payload["model_version"].strip():
        raise ShipModelError("model_version must be a non-empty string")
    if not isinstance(payload["principal"], dict):
        raise ShipModelError("principal must be an object")

    space_records = _record_list(payload, "spaces")
    spaces: list[SpaceSpec] = []
    seen_space_ids: set[str] = set()
    for index, record in enumerate(space_records):
        space_id = _required_text(record, "id", "spaces", index)
        if space_id in seen_space_ids:
            raise ShipModelError(f"Duplicate space id {space_id!r}")
        seen_space_ids.add(space_id)
        known = {"id", "name", "kind", "frame", "zone", "current_condition"}
        spaces.append(
            SpaceSpec(
                id=space_id,
                name=_required_text(record, "name", "spaces", index),
                kind=_required_text(record, "kind", "spaces", index),
                frame=_required_text(record, "frame", "spaces", index),
                zone=_required_text(record, "zone", "spaces", index),
                current_condition=_required_text(record, "current_condition", "spaces", index),
                metadata={key: value for key, value in record.items() if key not in known},
            )
        )

    link_records = _record_list(payload, "access_links")
    links: list[AccessLinkSpec] = []
    seen_link_ids: set[str] = set()
    for index, record in enumerate(link_records):
        link_id = _required_text(record, "id", "access_links", index)
        if link_id in seen_link_ids:
            raise ShipModelError(f"Duplicate access-link id {link_id!r}")
        seen_link_ids.add(link_id)
        from_id = _required_text(record, "from", "access_links", index)
        to_id = _required_text(record, "to", "access_links", index)
        if from_id not in seen_space_ids or to_id not in seen_space_ids:
            raise ShipModelError(
                f"Access link {link_id!r} references unknown space {from_id!r}->{to_id!r}"
            )
        if from_id == to_id:
            raise ShipModelError(f"Access link {link_id!r} cannot connect a space to itself")
        known = {"id", "from", "to", "kind"}
        links.append(
            AccessLinkSpec(
                id=link_id,
                from_id=from_id,
                to_id=to_id,
                kind=_required_text(record, "kind", "access_links", index),
                metadata={key: value for key, value in record.items() if key not in known},
            )
        )

    # Validate the remaining required arrays now, even though later integration
    # slices will be responsible for their runtime semantics.
    for section in REQUIRED_TOP_LEVEL[5:]:
        _record_list(payload, section)

    return ShipWorldModel(
        schema_version=payload["schema_version"],
        model_version=payload["model_version"],
        principal=dict(payload["principal"]),
        spaces=tuple(spaces),
        access_links=tuple(links),
    )
