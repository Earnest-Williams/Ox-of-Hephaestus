"""World-owned, local-first handover for one passive drum-3 hatch contact.

This is a request/decision channel, not a powered hatch actuator. Physical
hatch movement continues exclusively through crew_physical_action("hatch").
All writes use the physics clock and PostgreSQL row-lock transaction.
"""

from __future__ import annotations

from django.db import transaction

from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_access_contact import (
    AccessContactError, certificate_valid, contact_specifications,
)
from world.ship_access_contact_world import _gateway_power_live, _rows
from world.ship_dr03_hatch_policy import (
    BAD, DECIDED, KEY, LINK, REQUESTED, ROOM, SCHEMA, SENSOR, SOURCE,
    STATION, HatchHandoverError, clear_pending, pending_state,
    reference, request_id_valid, require, validate_control,
)
from world.ship_model import load_ship_model
from world.ship_network_access_world import _principal, network_reachable

RECEIPT_TARGET = "dr03_hatch_handover"


def _contact_ready(clock):
    """A current certificate for the genuine passive source, not cached data."""
    try:
        specs = contact_specifications(load_ship_model())
        rows = _rows(specs)
    except (AccessContactError, KeyError, ValueError, TypeError) as exc:
        raise HatchHandoverError("Drum-3 hatch contact is not installed") from exc
    powered, revisions = _gateway_power_live(clock)
    require(powered and certificate_valid(rows, revisions),
            "Drum-3 hatch contact or physical gateway survey is unavailable")
    return rows


def _control_locked():
    row = CanonicalShipState.objects.select_for_update().filter(pk=KEY).first()
    validate_control(row)
    return row


def _existing(request_id, identity, kind, value, original_request_id=None):
    receipt = WorkReceipt.objects.select_for_update().filter(
        pk=request_id).first()
    if receipt is not None:
        require(receipt.target == RECEIPT_TARGET
                and receipt.actor_dbref == identity
                and receipt.operation == kind
                and receipt.arguments == {
                    "link": LINK, "value": value,
                    "original_request_id": original_request_id,
                }, "Request ID already belongs to a different operation")
        return dict(receipt.outcome)
    require(not CanonicalShipEvent.objects.filter(
        request_id=request_id).exists(),
        "Request ID already belongs to a ship event")
    return None


def _record(clock, request_id, identity, kind, value, *,
            original_request_id=None, before, after, status,
            source_event_id=None, changed):
    event = CanonicalShipEvent.objects.create(
        component_key=KEY,
        operation=REQUESTED if kind == "request" else DECIDED,
        before=before,
        after={**after, "status": status, "physical_actuation": False},
        actor_dbref=identity if identity.startswith("#") else None,
        request_id=request_id, source_event_id=source_event_id,
        game_time=float(clock.details["last_game_time"]),
    )
    outcome = {
        "request_id": request_id, "operation": kind,
        "link": LINK, "status": status,
        "changed": changed, "physical_actuation": False,
        "source_event_id": str(event.sequence),
    }
    WorkReceipt.objects.create(
        request_id=request_id, actor_dbref=identity,
        target=RECEIPT_TARGET, operation=kind,
        arguments={
            "link": LINK, "value": value,
            "original_request_id": original_request_id,
        },
        outcome=outcome, game_time=event.game_time,
    )
    return event, outcome


@transaction.atomic
def commission_dr03_hatch_handover(*, operator_approved=False):
    """Commission only after the genuine pressure hatch/contact is surveyed."""
    if not operator_approved:
        raise PermissionError("Only a world operator can fit hatch handover")
    from world.continuous_ship_physics import _clock
    from world.full_ship_operations import _require_installed, state

    _require_installed()
    clock = _clock(lock=True)
    _contact_ready(clock)
    hatch = state("access", LINK)
    console = state("equipment", STATION)
    panel = state("equipment", "LP-BE-05-SVC")
    require(hatch.reference.get("id") == LINK
            and hatch.condition not in BAD
            and console.space_id == ROOM
            and panel.space_id == ROOM
            and console.condition not in BAD
            and panel.condition not in BAD,
            "Original rated hatch or local console is not serviceable")
    candidate = {
        "key": KEY, "category": "control", "source_id": SOURCE,
        "source_model": SCHEMA, "space_id": ROOM,
        "condition": "serviceable", "setting": "idle",
        "reference": reference(),
        "details": {
            "request_id": None, "request_event": None,
            "desired": None, "requester": None, "epoch": 0,
        },
    }
    row, created = CanonicalShipState.objects.get_or_create(
        pk=KEY, defaults=candidate)
    validate_control(row)
    if created:
        CanonicalShipEvent.objects.create(
            component_key=KEY, operation="g19_dr03_hatch_handover_fitted",
            before={}, after={"link": LINK, "sensor": SENSOR,
                              "remote_door_motor": False},
            game_time=float(clock.details["last_game_time"]),
        )
    return {"commissioned": created, "request_only": True,
            "remote_door_motor": False}


@transaction.atomic
def request_dr03_hatch(account, request_id, desired):
    """One enrolled ship principal may request, but cannot move, this hatch."""
    request_id_valid(request_id)
    require(desired in {"open", "closed"}, "Unknown desired hatch position")
    from world.continuous_ship_physics import _clock
    from world.full_ship_operations import state

    clock = _clock(lock=True)
    principal = _principal(account, lock=True)
    identity = "account:" + str(principal.reference["account_pk"])
    old = _existing(request_id, identity, "request", desired)
    if old is not None:
        return old
    row = _control_locked()
    require(network_reachable(clock),
            "The ship principal lacks a live surveyed network path")
    _contact_ready(clock)
    hatch = state("access", LINK, lock=True)
    require(hatch.condition not in BAD,
            "The original drum-3 hatch is damaged")
    require(row.setting == "idle", "An attended hatch request is outstanding")
    event, receipt = _record(
        clock, request_id, identity, "request", desired,
        before={"mode": "idle", "hatch_setting": hatch.setting},
        after={"desired": desired, "actual_setting": hatch.setting,
               "awaiting_local_decision": True},
        status="pending_local_decision", changed=False,
    )
    row.details = pending_state(
        row, request_id, desired, identity, event.sequence)
    row.setting = "pending"
    row.revision += 1
    row.save(update_fields=["details", "setting", "revision"])
    return receipt


@transaction.atomic
def decide_dr03_hatch(actor, decision_id, original_request_id, decision):
    """Crew at the original local console accepts or declines, even offline.

    Acceptance means a human has taken responsibility for manual handling.
    It never opens or closes the pressure-rated hatch itself.
    """
    request_id_valid(decision_id)
    request_id_valid(original_request_id)
    require(decision in {"accept", "decline"}, "Unknown local decision")
    from world.continuous_ship_physics import _clock
    from world.ship_dr03_authority_world import _crew_console
    from world.full_ship_operations import state

    identity = getattr(actor, "dbref", None)
    require(isinstance(identity, str) and identity.startswith("#"),
            "Physical crew principal required")
    clock = _clock(lock=True)
    kind = "local_" + decision
    old = _existing(decision_id, identity, kind, decision, original_request_id)
    if old is not None:
        return old
    row = _control_locked()
    _crew_console(actor, clock)  # Actual console/health/power; no fibre needed.
    details = row.details
    cleared = clear_pending(row, original_request_id)
    hatch = state("access", LINK)
    prior = {"mode": "pending", "desired": details["desired"],
             "hatch_setting": hatch.setting}
    status = ("accepted_for_manual_action" if decision == "accept"
              else "declined_by_crew")
    _, receipt = _record(
        clock, decision_id, identity, kind, decision,
        original_request_id=original_request_id,
        before=prior,
        after={"mode": "idle", "original_request_id": original_request_id,
               "desired": details["desired"],
               "hatch_setting": hatch.setting,
               "local_decision": decision},
        status=status, source_event_id=str(details["request_event"]),
        changed=True,
    )
    row.details = cleared
    row.setting = "idle"
    row.revision += 1
    row.save(update_fields=["details", "setting", "revision"])
    return receipt


@transaction.atomic
def local_dr03_hatch_pending(actor):
    """Read the actual pending request at the original powered console.

    This is local console presentation, independent of A/B data-fibre.
    It exposes neither the account binding nor any extra hatch authority.
    """
    from world.continuous_ship_physics import _clock
    from world.ship_dr03_authority_world import _crew_console
    from world.full_ship_operations import state

    clock = _clock(lock=True)
    row = _control_locked()
    _crew_console(actor, clock)
    if row.setting == "idle":
        return {
            "link": LINK, "pending": False, "request_id": None,
            "desired": None, "physical_actuation": False,
        }
    hatch = state("access", LINK)
    return {
        "link": LINK, "pending": True,
        "request_id": row.details["request_id"],
        "desired": row.details["desired"],
        "hatch_setting": hatch.setting,
        "physical_actuation": False,
    }


@transaction.atomic
def dr03_hatch_request_status(account, original_request_id):
    """Only the enrolled requester sees its immutable request/decision pair."""
    request_id_valid(original_request_id)
    from world.continuous_ship_physics import _clock

    clock = _clock(lock=True)
    principal = _principal(account, lock=True)
    require(network_reachable(clock), "No live network status channel")
    identity = "account:" + str(principal.reference["account_pk"])
    receipt = WorkReceipt.objects.filter(pk=original_request_id).first()
    require(receipt is not None
            and receipt.target == RECEIPT_TARGET
            and receipt.operation == "request"
            and receipt.actor_dbref == identity,
            "No request belonging to this ship account")
    decision = CanonicalShipEvent.objects.filter(
        operation=DECIDED,
        source_event_id=receipt.outcome["source_event_id"],
    ).order_by("-sequence").first()
    return {
        "request_id": original_request_id,
        "link": LINK,
        "status": (decision.after["status"] if decision is not None
                   else "pending_local_decision"),
        "physical_actuation": False,
        "decision_event_id": (str(decision.sequence)
                              if decision is not None else None),
    }
