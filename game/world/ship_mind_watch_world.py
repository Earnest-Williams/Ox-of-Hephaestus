"""Authenticated first ship-mind watch: one predicate on delivered hatch data.

The one-shot watch is an authoritative Evennia record, not a handler timer.
Its trigger is written during a newly delivered source observation only.
No simulation tick, physics operation, catch-up scan, or remote door motion
is performed here. All user actions serialize on the continuous-physics clock.
"""

from __future__ import annotations

from django.db import transaction

from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_access_contact import LINK, OBSERVED, SENSOR
from world.ship_mind_watch import (
    ARMED, CANCELLED, FIRED, KEY, SCHEMA, SOURCE, ShipWatchError,
    arm_details, empty_details, match_delivery, reference, require,
    valid_request_id, validate_watch,
)
from world.ship_network_access import (
    DELIVERED, PRINCIPAL, NetworkAccessError, capture, present_delivery,
)
from world.ship_network_access_world import _principal, network_reachable

RECEIPT_TARGET = "ship_mind_watch"


def _watch_row(*, lock=False, create=False):
    query = CanonicalShipState.objects
    if lock:
        query = query.select_for_update()
    row = query.filter(pk=KEY).first()
    if row is None and create:
        candidate = {
            "key": KEY, "category": "control", "source_id": SOURCE,
            "source_model": SCHEMA, "space_id": None,
            "condition": "serviceable", "setting": "idle",
            "reference": reference(), "details": empty_details(),
        }
        row, _ = CanonicalShipState.objects.get_or_create(
            pk=KEY, defaults=candidate)
    if row is not None:
        validate_watch(row)
    return row


def _existing(request_id, identity, operation, args):
    old = WorkReceipt.objects.select_for_update().filter(
        pk=request_id).first()
    if old is not None:
        if (old.actor_dbref != identity
                or old.target != RECEIPT_TARGET
                or old.operation != operation or old.arguments != args):
            raise PermissionError("Global request ID already belongs to other work")
        return dict(old.outcome)
    if CanonicalShipEvent.objects.filter(request_id=request_id).exists():
        raise PermissionError("Request ID already belongs to a ship event")
    return None


def _write_request(clock, *, request_id, identity, operation, args, before,
                   after, status, source_event_id=None):
    event = CanonicalShipEvent.objects.create(
        component_key=KEY,
        operation=ARMED if operation == "arm" else CANCELLED,
        before=before, after=after,
        actor_dbref=None, request_id=request_id,
        source_event_id=source_event_id,
        game_time=float(clock.details["last_game_time"]),
    )
    outcome = {
        "request_id": request_id, "operation": operation,
        "status": status, "source_event_id": str(event.sequence),
        "controls_time": False, "physical_actuation": False,
    }
    WorkReceipt.objects.create(
        request_id=request_id, actor_dbref=identity,
        target=RECEIPT_TARGET, operation=operation,
        arguments=args, outcome=outcome, game_time=event.game_time,
    )
    return event, outcome


@transaction.atomic
def arm_first_watch(account, request_id, desired):
    """Watch the *next* delivered drum-3 change to one actual position."""
    valid_request_id(request_id)
    require(desired in {"open", "closed"}, "Only fitted hatch positions exist")
    from world.continuous_ship_physics import _clock

    clock = _clock(lock=True)
    principal = _principal(account, lock=True)
    owner_pk = principal.reference["account_pk"]
    identity = "account:" + str(owner_pk)
    prior = _existing(request_id, identity, "arm", {"desired": desired})
    if prior is not None:
        return prior
    require(network_reachable(clock), "No live ship-network channel to arm watch")
    row = _watch_row(lock=True, create=True)
    require(row.setting != "armed", "One ship watch is already armed")
    generation = row.details["generation"] + 1
    event, receipt = _write_request(
        clock, request_id=request_id, identity=identity,
        operation="arm", args={"desired": desired},
        before={"setting": row.setting, "generation": row.details["generation"]},
        after={"desired": desired, "generation": generation,
               "source": "network_delivered_hatch_contact"},
        status="armed_for_next_delivery",
    )
    row.details = arm_details(
        row, request_id=request_id, owner_pk=owner_pk,
        epoch=principal.reference["epoch"], desired=desired,
        after_sequence=event.sequence,
    )
    row.setting = "armed"
    row.revision += 1
    row.save(update_fields=["details", "setting", "revision"])
    return receipt


@transaction.atomic
def cancel_first_watch(account, request_id):
    """Cancel an armed request; never act on the physical ship."""
    valid_request_id(request_id)
    from world.continuous_ship_physics import _clock

    clock = _clock(lock=True)
    principal = _principal(account, lock=True)
    owner_pk = principal.reference["account_pk"]
    identity = "account:" + str(owner_pk)
    prior = _existing(request_id, identity, "cancel", {})
    if prior is not None:
        return prior
    require(network_reachable(clock), "No live ship-network channel to cancel watch")
    row = _watch_row(lock=True)
    require(row is not None and row.setting == "armed"
            and row.details["owner_pk"] == owner_pk
            and row.details["epoch"] == principal.reference["epoch"],
            "No matching armed watch")
    previous = dict(row.details)
    _, receipt = _write_request(
        clock, request_id=request_id, identity=identity,
        operation="cancel", args={},
        before={"generation": previous["generation"],
                "request_id": previous["request_id"]},
        after={"generation": previous["generation"],
               "prior_request_id": previous["request_id"]},
        status="cancelled",
        source_event_id=str(previous["after_sequence"]),
    )
    row.setting = "idle"
    row.details = empty_details(previous["generation"])
    row.revision += 1
    row.save(update_fields=["setting", "details", "revision"])
    return receipt


@transaction.atomic
def first_watch_status(account):
    """Show the owner's own watch, only when current transport is verified."""
    from world.continuous_ship_physics import _clock

    clock = _clock(lock=True)
    principal = _principal(account, lock=True)
    require(network_reachable(clock), "Watch status needs a live network path")
    row = _watch_row()
    if row is None or row.setting == "idle":
        return {
            "status": "idle", "request_id": None, "desired": None,
            "delivery_event_id": None, "source_time": None,
            "controls_time": False,
        }
    details = row.details
    require(details["owner_pk"] == principal.reference["account_pk"]
            and details["epoch"] == principal.reference["epoch"],
            "Watch is not bound to this enrollment")
    return {
        "status": row.setting,
        "request_id": details["request_id"],
        "desired": details["desired"],
        "delivery_event_id": (
            "ox-net-" + str(details["delivery_sequence"])
            if details["delivery_sequence"] is not None else None
        ),
        "source_time": details["source_time"],
        "controls_time": False,
    }


def observe_first_watch(sender, instance, created, **kwargs):
    """One-shot signal, triggered only by a *new* delivered contact frame.

    This never backfills old events and never prevents an actual crew hatch
    movement. The existing gateway's live network and power checks already
    ran when the delivery was recorded.
    """
    if (not created or instance.operation != DELIVERED
            or instance.component_key != PRINCIPAL):
        return
    row = CanonicalShipState.objects.select_for_update().filter(pk=KEY).first()
    if row is None:
        return
    try:
        validate_watch(row)
        if row.setting != "armed":
            return
        principal = CanonicalShipState.objects.filter(pk=PRINCIPAL).first()
        if (principal is None or principal.source_model !=
                "ox.network-access/1" or principal.setting != "bound"
                or principal.condition != "serviceable"
                or not isinstance(principal.reference, dict)
                or principal.reference.get("account_pk") != row.details["owner_pk"]
                or principal.reference.get("epoch") != row.details["epoch"]):
            return
        packet = match_delivery(
            row, instance,
            owner_pk=principal.reference["account_pk"],
            epoch=principal.reference["epoch"],
        )
        if packet is None:
            return
        # Independently verify that the delivered capsule cited a real,
        # state-changing physical hatch action and the fitted local contact.
        source = instance.source_event_id
        if not isinstance(source, str) or not source.isdecimal():
            return
        observation = CanonicalShipEvent.objects.filter(
            pk=int(source), component_key="equipment:" + SENSOR,
            operation=OBSERVED,
        ).first()
        if observation is None:
            return
        original = observation.source_event_id
        if not isinstance(original, str) or not original.isdecimal():
            return
        physical = CanonicalShipEvent.objects.filter(
            pk=int(original), operation="crew_hatch",
            component_key="access:" + LINK,
        ).first()
        if physical is None:
            return
        expected = capture(observation)
        presented = present_delivery(instance, epoch=row.details["epoch"])
        if (any(presented.get(name) != value
                for name, value in expected.items())
                or physical.before.get("setting") != expected["setting_before"]
                or physical.after.get("setting") != expected["setting_after"]
                or physical.game_time != expected["source_time"]):
            return
        # This canonical event is not a new delivered capsule; the observer
        # ignores it, and repeated notifications cannot fire an armed watch.
        event = CanonicalShipEvent.objects.create(
            component_key=KEY, operation=FIRED,
            before={"generation": row.details["generation"],
                    "desired": row.details["desired"]},
            after={
                "generation": row.details["generation"],
                "desired": row.details["desired"],
                "delivery_event_id": "ox-net-" + str(instance.sequence),
                "source_time": packet["source_time"],
                "controls_time": False, "physical_actuation": False,
            },
            source_event_id=str(instance.sequence),
            actor_dbref=None, request_id=None,
            game_time=float(instance.game_time),
        )
        row.setting = "fired"
        row.details = {
            **row.details,
            "delivery_sequence": instance.sequence,
            "source_time": packet["source_time"],
        }
        row.revision += 1
        row.save(update_fields=["setting", "details", "revision"])
    except (ShipWatchError, NetworkAccessError, KeyError, TypeError, ValueError):
        return
