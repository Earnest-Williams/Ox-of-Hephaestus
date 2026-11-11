"""Evennia world-owned drum-3 local takeover and account remote control.

All commands use one transaction and the continuous-physics clock lock; the
canonical isolator is the single physical truth. Requests have immutable
receipts in the global WorkReceipt namespace, including refusal receipts.
"""

from __future__ import annotations

from django.db import transaction

from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_dr03_authority import (
    DrumControlError, KEY, ROOM, SCHEMA, STATION, TARGET,
    check_lt_interlocks, control_ref, next_authority, request_id_valid,
    require, validate_control,
)
from world.ship_network_access_world import _principal, network_reachable


@transaction.atomic
def commission_dr03_control(*, operator_approved=False):
    if not operator_approved:
        raise PermissionError("Commissioning the first remote valve requires an operator")
    from world.continuous_ship_physics import _clock
    from world.full_ship_operations import _require_installed, state

    _require_installed()
    clock = _clock(lock=True)
    require(clock.details.get("mind_gateway") is not None
            and clock.details.get("mind_support_last") is not None,
            "Ship gateway and backbone have not been installed")
    iso = state("isolator", TARGET, lock=True)
    require(iso.reference.get("remote_operable") is True
            and iso.reference.get("manual_operation") is True
            and iso.condition not in {
                "faulted", "failed", "destroyed", "severed", "jammed"},
            "Original drum-3 valve has no healthy remote actuator")
    station = state("equipment", STATION)
    require(station.space_id == ROOM, "Drum-3 console in wrong room")
    candidate = {
        "key": KEY, "category": "control", "source_id": "DR-03-LT-IF",
        "source_model": SCHEMA, "space_id": ROOM, "condition": "serviceable",
        "setting": "remote", "reference": control_ref(),
        "details": {"holder": None, "epoch": 0},
    }
    row, created = CanonicalShipState.objects.get_or_create(
        key=KEY, defaults=candidate)
    validate_control(row)
    if created:
        CanonicalShipEvent.objects.create(
            component_key=KEY, operation="g19_dr03_control_fitted",
            before={}, after={"station": STATION, "target": TARGET},
            game_time=float(clock.details["last_game_time"]),
        )
    return {"commissioned": created, "local_priority": True}


def _receipt(old, *, kind, identity, value):
    if old is None:
        return None
    if (old.actor_dbref != identity
            or old.target != "dr03_control"
            or old.operation != kind
            or old.arguments != {"target": TARGET, "value": value}):
        raise PermissionError("Request ID belongs to another ship operation")
    return dict(old.outcome)


def _existing(request_id, kind, identity, value):
    receipt = WorkReceipt.objects.select_for_update().filter(
        pk=request_id).first()
    if receipt is not None:
        return _receipt(receipt, kind=kind, identity=identity, value=value)
    if CanonicalShipEvent.objects.filter(request_id=request_id).exists():
        raise PermissionError("Request ID is already owned by a world event")
    return None


def _record(clock, request_id, identity, kind, value, *, before, after,
            changed, status="succeeded"):
    event = CanonicalShipEvent.objects.create(
        component_key=KEY if kind != "remote_switch" and kind != "local_switch"
                      else "isolator:" + TARGET,
        operation="g19_dr03_" + kind,
        before=before,
        after={**after, "requested_value": value, "status": status},
        actor_dbref=identity if identity.startswith("#") else None,
        request_id=request_id,
        game_time=float(clock.details["last_game_time"]),
    )
    receipt = {
        "request_id": request_id, "operation": kind,
        "target": TARGET, "status": status, "changed": changed,
        "source_event_id": str(event.sequence),
    }
    WorkReceipt.objects.create(
        request_id=request_id, actor_dbref=identity,
        target="dr03_control", operation=kind,
        arguments={"target": TARGET, "value": value},
        outcome=receipt, game_time=event.game_time,
    )
    return receipt


def _control_locked():
    row = CanonicalShipState.objects.select_for_update().filter(pk=KEY).first()
    validate_control(row)
    return row


def _crew_console(actor, clock):
    from world.continuous_ship_physics import _crew_at
    from world.full_ship_operations import state
    from world.ship_crew_access import _health_gate
    from world.ship_access_contact_world import _gateway_power_live

    _crew_at(actor, ROOM)
    _health_gate(actor)
    require(not getattr(actor.db, "ox_terminal_dead", False),
            "Incapacitated operator cannot use the console")
    console = state("equipment", STATION)
    panel = state("equipment", "LP-BE-05-SVC")
    require(console.condition not in {
        "faulted", "failed", "destroyed", "severed", "jammed"}
        and panel.condition not in {
            "faulted", "failed", "destroyed", "severed", "jammed"},
        "Fitted local console or its feeder is damaged")
    # The local console uses the original local panel, not the ship-wide
    # fibre. Read its current electrical node; a dark network is immaterial.
    from world.continuous_ship_physics import _power, PhysicsError
    from world.ship_port_operations import contacts_active
    all_rows = list(CanonicalShipState.objects.all())
    equip = {r.source_id: r for r in all_rows if r.category == "equipment"}
    edges = [r for r in all_rows if r.category == "edge"]
    isolators = {r.source_id: r for r in all_rows if r.category == "isolator"}
    try:
        grid = _power(
            equip, edges, isolators, clock.details["load_profile"],
            ledger=clock.details["electrical"],
            moored=contacts_active(clock.details.get("cargo", {})),
        )
    except (PhysicsError, KeyError, ValueError, TypeError) as exc:
        raise DrumControlError("Local panel supply cannot be verified") from exc
    require("NODE-LP-BE-05-SVC" in grid["nodes"]
            and grid["essential_assured"],
            "Local panel lacks verified live power")


@transaction.atomic
def local_dr03(actor, request_id, operation, value=None):
    """Take local possession, change one valve, or hand back."""
    request_id_valid(request_id)
    require(operation in {"takeover", "handback", "switch"},
            "Unsupported console operation")
    if operation == "switch":
        require(value in {"open", "closed"}, "Bad LT command")
    else:
        require(value is None, "Takeover/handback take no valve setting")
    from world.continuous_ship_physics import _clock
    from world.full_ship_operations import state

    identity = getattr(actor, "dbref", None)
    require(isinstance(identity, str), "Real crew identity required")
    clock = _clock(lock=True)
    kind = "local_" + operation
    old = _existing(request_id, kind, identity, value)
    if old is not None:
        return old
    row = _control_locked()
    _crew_console(actor, clock)
    before = {"mode": row.setting, "holder": row.details["holder"]}
    if operation != "switch":
        mode, holder, changed = next_authority(
            row.setting, row.details["holder"], identity, operation)
        if changed:
            row.setting = mode
            row.details = {
                "holder": holder, "epoch": row.details["epoch"] + 1}
            row.revision += 1
            row.save(update_fields=["setting", "details", "revision"])
        return _record(
            clock, request_id, identity, kind, value,
            before=before, after={
                "mode": row.setting, "holder": row.details["holder"]},
            changed=changed,
        )
    require(row.setting == "local" and row.details["holder"] == identity,
            "Local control has not been taken by this engineer")
    valve = state("isolator", TARGET, lock=True)
    check_lt_interlocks(valve, clock.details, value=value)
    prior = {"setting": valve.setting, "revision": valve.revision}
    changed = valve.setting != value
    if changed:
        valve.setting = value
        valve.revision += 1
        valve.save(update_fields=["setting", "revision"])
    return _record(
        clock, request_id, identity, kind, value,
        before=prior, after={
            "setting": valve.setting, "revision": valve.revision,
            "local_epoch": row.details["epoch"]},
        changed=changed,
    )


@transaction.atomic
def remote_dr03(account, request_id, value):
    """Only enrolled OOC principal over real live gateway gets first actuator."""
    request_id_valid(request_id)
    require(value in {"open", "closed"}, "Bad LT valve request")
    from world.continuous_ship_physics import _clock
    from world.full_ship_operations import state

    clock = _clock(lock=True)
    principal = _principal(account, lock=True)
    identity = "account:" + str(principal.reference["account_pk"])
    kind = "remote_switch"
    old = _existing(request_id, kind, identity, value)
    if old is not None:
        return old
    row = _control_locked()
    gateway = clock.details.get("mind_gateway")
    require(gateway is not None
            and gateway.get("mapping_revision", 0) > 0
            and gateway.get("profile") is not None,
            "Unverified mixed-generation gateway command vocabulary")
    require(network_reachable(clock),
            "No currently powered and surveyed network command path")
    if row.setting == "local":
        return _record(
            clock, request_id, identity, kind, value,
            before={"mode": "local", "holder": "local"},
            after={"mode": "local", "control_epoch": row.details["epoch"]},
            changed=False, status="refused_local_priority",
        )
    valve = state("isolator", TARGET, lock=True)
    check_lt_interlocks(valve, clock.details, value=value)
    prior = {"setting": valve.setting, "revision": valve.revision}
    changed = valve.setting != value
    if changed:
        valve.setting = value
        valve.revision += 1
        valve.save(update_fields=["setting", "revision"])
    return _record(
        clock, request_id, identity, kind, value,
        before=prior, after={
            "setting": valve.setting, "revision": valve.revision,
            "control_epoch": row.details["epoch"]},
        changed=changed,
    )
