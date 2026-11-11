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

from django.db import transaction

from world.models import CanonicalShipEvent, CanonicalShipState
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


def _rows(specifications: dict, *, lock=False) -> dict:
    query = CanonicalShipState.objects
    if lock:
        query = query.select_for_update()
    rows = {row.key: row for row in query.filter(key__in=list(specifications))}
    _check(set(rows) == set(specifications), "Fitted contact row missing")
    for key, spec in specifications.items():
        row = rows[key]
        _check(all(
            getattr(row, name) == spec[name]
            for name in ("category", "source_id", "source_model", "space_id", "reference")
        ), "Fitted contact identity changed: " + key)
    return rows


def contact_transition(event) -> dict | None:
    """A changed world hatch setting, not a command request or inferred actor."""
    if (event.operation != "crew_hatch"
            or event.component_key != "access:" + LINK):
        return None
    before, after = event.before, event.after
    if not isinstance(before, dict) or not isinstance(after, dict):
        return None
    prior, current = before.get("setting"), after.get("setting")
    if (prior not in {"open", "closed"}
            or current not in {"open", "closed"} or prior == current):
        return None
    return {"setting_before": prior, "setting_after": current}


def _gateway_power_live(clock) -> tuple[bool, dict]:
    account = clock.details.get("mind_gateway")
    if not isinstance(account, dict) or not account.get("last", {}).get("powered"):
        return False, {}
    survey = account.get("power_survey")
    if not isinstance(survey, dict):
        return False, {}
    keys = POWER_KEYS + ("equipment:" + GATEWAY,
                        "equipment:LCS-DR-03", "equipment:LP-BE-05-SVC")
    active = {row.key: row for row in CanonicalShipState.objects.filter(key__in=keys)}
    if set(active) != set(keys) or any(row.condition in FAILED for row in active.values()):
        return False, {}
    if (active["isolator:ISO-PWR-GW-LCS-DR-03"].setting != "closed"
            or active["edge:EDGE-PWR-GW-LCS-DR-03"].setting != "available"
            or active["edge:THERM-GW-LCS-DR-03"].setting != "available"):
        return False, {}
    actual = {key: active[key].revision for key in POWER_KEYS}
    if survey.get("component_revisions") != actual:
        return False, {}
    return True, actual


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


@transaction.atomic
def fit_dr03_contact(*, operator_approved=False):
    """Install two durable hardware rows without resetting prior faults."""
    if not operator_approved:
        raise PermissionError("Physical contact fitting requires an operator")
    from world.full_ship_operations import _require_installed
    from world.continuous_ship_physics import _clock
    from world.ship_control_gateway import fitted_gateway_power
    from world.ship_mind_support import load_support
    from world.full_ship_operations import load_candidate

    _require_installed()
    clock = _clock(lock=True)
    _check(clock.details.get("mind_gateway") is not None,
           "Fit original drum-3 gateway power first")
    fitted_gateway_power(CanonicalShipState, load_support(), load_candidate())
    specs = contact_specifications(load_ship_model())
    created = 0
    for key, spec in specs.items():
        _, added = CanonicalShipState.objects.get_or_create(key=key, defaults=spec)
        created += int(added)
    _rows(specs, lock=True)
    if created:
        CanonicalShipEvent.objects.create(
            component_key="equipment:" + SENSOR,
            operation="g19_access_contact_fitted", before={},
            after={"source_model": SCHEMA, "created": created},
            game_time=float(clock.details["last_game_time"]),
        )
    return {"created": created, "total": len(specs)}


@transaction.atomic
def survey_dr03_contact(
    *, operator_approved=False, evidence_id,
    continuity_verified=False, pressure_penetration_ids=(),
):
    """Attest a physical conductor, without pretending to repair broken kit."""
    if not operator_approved:
        raise PermissionError("Access contact surveys require an operator")
    from world.continuous_ship_physics import _clock
    from world.full_ship_operations import _require_installed

    _require_installed()
    clock = _clock(lock=True)
    specs = contact_specifications(load_ship_model())
    rows = _rows(specs, lock=True)
    sensor, cable = rows["equipment:" + SENSOR], rows["edge:" + CABLE]
    _check(sensor.condition not in FAILED and cable.condition not in FAILED,
           "Cannot survey a failed contact or broken conductor")
    _check(continuity_verified is True, "No verified conductor continuity")
    _check(isinstance(evidence_id, str) and 0 < len(evidence_id) <= 128,
           "Survey evidence must identify the physical measurement")
    _check(type(pressure_penetration_ids) in (tuple, list)
           and list(pressure_penetration_ids)
           == cable.reference["pressure_penetrations"],
           "Pressure penetration evidence disagrees with installed route")
    live, power_revisions = _gateway_power_live(clock)
    _check(live, "Gateway input must be energised and its power survey current")
    if certificate_valid(rows, power_revisions):
        return {"surveyed": False, "idempotent": True}
    # Fitting/recommissioning never resets damage or heat/energy ledgers.
    sensor.setting = "enabled"
    sensor.revision += 1
    cert = {
        "sensor_revision": sensor.revision,
        "cable_revision": cable.revision,
        "sensor_reference_hash": reference_hash(sensor.reference),
        "cable_reference_hash": reference_hash(cable.reference),
        "power_revisions": power_revisions,
        "pressure_penetrations": cable.reference["pressure_penetrations"],
        "evidence_id": evidence_id,
    }
    sensor.details = {**sensor.details, "contact_survey": cert}
    sensor.save(update_fields=["setting", "revision", "details"])
    CanonicalShipEvent.objects.create(
        component_key=sensor.key,
        operation="g19_access_contact_surveyed",
        before={},
        after={"sensor_revision": sensor.revision,
               "cable_revision": cable.revision,
               "power_revisions": power_revisions,
               "penetrations": cert["pressure_penetrations"],
               "evidence_id": evidence_id},
        game_time=float(clock.details["last_game_time"]),
    )
    return {"surveyed": True, "idempotent": False}


def observe_access_contact(sender, instance, created, **kwargs):
    """World-owned on-commit event capture in the same authoritative transaction.

    Django post_save runs in the enclosing physics or crew-work transaction.
    Only a source event *created while* the installed reader is operational
    can produce a local observation. Editing an old event cannot backfill it.
    """
    if not created:
        return
    transition = contact_transition(instance)
    if transition is None:
        return
    specs = contact_specifications(load_ship_model())
    try:
        rows = _rows(specs, lock=True)
    except AccessContactError:
        return  # Never grant evidence if the instrument is absent or altered.
    clock = CanonicalShipState.objects.filter(pk="meta:continuous-physics").first()
    if clock is None:
        return
    live, power_revisions = _gateway_power_live(clock)
    if not live or not certificate_valid(rows, power_revisions):
        return
    if CanonicalShipEvent.objects.filter(
        component_key="equipment:" + SENSOR, operation=OBSERVED,
        source_event_id=str(instance.sequence),
    ).exists():
        return
    CanonicalShipEvent.objects.create(
        component_key="equipment:" + SENSOR, operation=OBSERVED,
        before={"setting": transition["setting_before"]},
        after={
            "setting": transition["setting_after"], "link_id": LINK,
            "sensor_revision": rows["equipment:" + SENSOR].revision,
            "cable_revision": rows["edge:" + CABLE].revision,
            "evidence_id": rows["equipment:" + SENSOR].details[
                "contact_survey"]["evidence_id"],
        },
        source_event_id=str(instance.sequence),
        # A mechanical contact sees a changed door, not a person or an ID.
        actor_dbref=None, request_id=None, game_time=instance.game_time,
    )
