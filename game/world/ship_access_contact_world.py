"""Evennia-owned fitting and event-time custody for the passive access contact."""

from __future__ import annotations

from django.db import transaction
from world.models import CanonicalShipEvent, CanonicalShipState
from world.ship_model import load_ship_model
from world.ship_access_contact import (
    SCHEMA, SENSOR, CABLE, LINK, GATEWAY, OBSERVED, ROUTE, FAILED,
    POWER_KEYS, AccessContactError, _check, reference_hash,
    contact_specifications, contact_transition, certificate_valid,
)

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
    try:
        specs = contact_specifications(load_ship_model())
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
