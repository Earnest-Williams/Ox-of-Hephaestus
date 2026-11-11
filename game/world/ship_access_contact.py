"""A fitted, passive drum-3 hatch contact with event-time local custody.

The contact is an unpowered dry-switch input to the already billed 50 W
GW-LCS-DR-03 local gateway. It adds no independent power consumer, no remote
command, no actor-identification capability, and no retroactive surveillance.
A lost gateway feeder or invalidated continuity survey makes it blind.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from world.ship_model import ShipWorldModel, load_ship_model

SCHEMA = "ox.ship-access-contact/1"
SENSOR = "ACSR-DR-03-FIX"
CABLE = "NET-ACSR-DR-03-FIX"
LINK = "ACC-DR-03-LOCK-FIX"
GATEWAY = "GW-LCS-DR-03"
OBSERVED = "g19_access_contact_observed"
ROUTE = (
    "BE-05-SVC", "TRUNK-B-DR-03", "LOGI-STOP-DR-03",
    "TRUNK-A-DR-03", "DR-03-SERVICE-LOCK",
)
FAILED = frozenset({"failed", "faulted", "severed", "destroyed", "jammed"})
POWER_KEYS = (
    "node:NODE-PWR-GW-LCS-DR-03",
    "edge:EDGE-PWR-GW-LCS-DR-03",
    "isolator:ISO-PWR-GW-LCS-DR-03",
    "edge:THERM-GW-LCS-DR-03",
)


class AccessContactError(ValueError):
    """Invalid physical contact installation or survey."""


def _check(ok: bool, message: str) -> None:
    if not ok:
        raise AccessContactError(message)


def reference_hash(reference: dict) -> str:
    return hashlib.sha256(
        json.dumps(reference, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def contact_specifications(model: ShipWorldModel) -> dict[str, dict]:
    """Require the original actual local path and rated hatch identity."""
    links: dict[frozenset[str], list[Any]] = {}
    for link in model.access_links:
        links.setdefault(frozenset((link.from_id, link.to_id)), []).append(link)
    found = []
    for left, right in zip(ROUTE, ROUTE[1:]):
        matches = links.get(frozenset((left, right)), [])
        _check(len(matches) == 1, "No unique physical drum-3 contact-cable route")
        found.append(matches[0])
    _check(found[-1].id == LINK, "Cable terminates on the wrong rated drum hatch")
    penetrations = sorted({
        link.id for link in found
        if link.metadata.get("pressure_boundary") is True
    })
    _check(LINK in penetrations, "Rated drum hatch pressure penetration missing")
    contact_ref = {
        "id": SENSOR,
        "kind": "passive_hatch_contact",
        "link_id": LINK,
        "gateway_id": GATEWAY,
        "room_id": "DR-03-SERVICE-LOCK",
        "topology_version": model.model_version,
        "identity_reader": False,
        "network_commands": False,
        "incremental_power_kw": 0,
    }
    cable_ref = {
        "id": CABLE,
        "network": "ship_access_contact",
        "kind": "gateway_dry_contact_cable",
        "from_room": ROUTE[0],
        "to_room": ROUTE[-1],
        "route_spaces": list(ROUTE),
        "route_link_ids": [link.id for link in found],
        "pressure_penetrations": penetrations,
        "gateway_input": GATEWAY,
    }
    return {
        "equipment:" + SENSOR: {
            "key": "equipment:" + SENSOR,
            "category": "equipment", "source_id": SENSOR,
            "source_model": SCHEMA, "space_id": ROUTE[-1],
            "condition": "serviceable", "setting": "off",
            "reference": contact_ref, "details": {},
        },
        "edge:" + CABLE: {
            "key": "edge:" + CABLE,
            "category": "edge", "source_id": CABLE,
            "source_model": SCHEMA, "space_id": ROUTE[0],
            "condition": "serviceable", "setting": "available",
            "reference": cable_ref, "details": {},
        },
    }


def certificate_valid(rows: dict, source_revisions: dict) -> bool:
    sensor = rows.get("equipment:" + SENSOR)
    cable = rows.get("edge:" + CABLE)
    if (sensor is None or cable is None
            or sensor.condition in FAILED or cable.condition in FAILED
            or sensor.setting != "enabled" or cable.setting != "available"):
        return False
    cert = sensor.details.get("contact_survey")
    if not isinstance(cert, dict) or set(cert) != {
        "sensor_revision", "cable_revision", "sensor_reference_hash",
        "cable_reference_hash", "power_revisions", "evidence_id",
        "pressure_penetrations",
    }:
        return False
    return bool(
        cert["sensor_revision"] == sensor.revision
        and cert["cable_revision"] == cable.revision
        and cert["sensor_reference_hash"] == reference_hash(sensor.reference)
        and cert["cable_reference_hash"] == reference_hash(cable.reference)
        and cert["power_revisions"] == source_revisions
        and cert["pressure_penetrations"]
        == cable.reference.get("pressure_penetrations")
        and isinstance(cert["evidence_id"], str)
        and 0 < len(cert["evidence_id"]) <= 128
    )

