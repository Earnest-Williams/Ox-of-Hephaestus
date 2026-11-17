"""One bounded event-time watch predicate for the enrolled, bodiless ship mind.

A watch notices *delivered* observations of the surveyed drum-3 contact.
It neither advances/pulls the physics clock nor predicts hidden activity.
"""

from __future__ import annotations

import math
import re

from world.ship_access_contact import LINK, SENSOR
from world.ship_network_access import DELIVERED, PRINCIPAL, present_delivery, NetworkAccessError

SCHEMA = "ox.ship-mind-watch/1"
KEY = "control:OX-DR03-WATCH"
SOURCE = "OX-DR03-WATCH"
ARMED = "g19_ship_watch_armed"
CANCELLED = "g19_ship_watch_cancelled"
FIRED = "g19_ship_watch_fired"
FIELDS = frozenset({
    "generation", "request_id", "owner_pk", "epoch", "desired",
    "after_sequence", "delivery_sequence", "source_time",
})


class ShipWatchError(ValueError):
    """Watch state or source evidence fails the narrow trust contract."""


def require(value, message):
    if not value:
        raise ShipWatchError(message)


def valid_request_id(request_id):
    require(isinstance(request_id, str) and
            re.fullmatch(r"[0-9a-f]{32}", request_id) is not None,
            "Expected a lowercase 32-hex request ID")
    return request_id


def reference():
    return {
        "schema_version": SCHEMA, "source": "account_network_delivery",
        "principal": PRINCIPAL, "reader": SENSOR, "link": LINK,
        "automatic_physical_action": False, "controls_time": False,
    }


def empty_details(generation=0):
    return {
        "generation": generation,
        "request_id": None, "owner_pk": None, "epoch": None,
        "desired": None, "after_sequence": None,
        "delivery_sequence": None, "source_time": None,
    }


def validate_watch(row):
    require(
        row is not None and row.key == KEY and row.category == "control"
        and row.source_id == SOURCE and row.source_model == SCHEMA
        and row.space_id is None and row.condition == "serviceable"
        and row.reference == reference()
        and row.setting in {"idle", "armed", "fired"}
        and isinstance(row.details, dict)
        and set(row.details) == FIELDS
        and type(row.details["generation"]) is int
        and row.details["generation"] >= 0,
        "Invalid world-owned first-watch record",
    )
    details = row.details
    if row.setting == "idle":
        require(details == empty_details(details["generation"]),
                "Idle watch must not carry a phantom trigger")
    else:
        valid_request_id(details["request_id"])
        require(
            type(details["owner_pk"]) is int and details["owner_pk"] > 0
            and isinstance(details["epoch"], str)
            and re.fullmatch(r"[0-9a-f]{32}", details["epoch"]) is not None
            and details["desired"] in {"open", "closed"}
            and type(details["after_sequence"]) is int
            and details["after_sequence"] > 0
            and details["generation"] > 0,
            "Armed watch lacks enrolled ownership or a starting event",
        )
        if row.setting == "armed":
            require(details["delivery_sequence"] is None
                    and details["source_time"] is None,
                    "An armed watch must not claim a delivery")
        else:
            require(
                type(details["delivery_sequence"]) is int
                and details["delivery_sequence"] > details["after_sequence"]
                and type(details["source_time"]) in (int, float)
                and math.isfinite(details["source_time"])
                and details["source_time"] >= 0,
                "Fired watch has no valid recorded delivery",
            )
    return True


def arm_details(row, *, request_id, owner_pk, epoch, desired, after_sequence):
    validate_watch(row)
    valid_request_id(request_id)
    require(row.setting != "armed", "A first-watch trigger is already armed")
    require(type(owner_pk) is int and owner_pk > 0
            and isinstance(epoch, str)
            and re.fullmatch(r"[0-9a-f]{32}", epoch) is not None
            and desired in {"open", "closed"}
            and type(after_sequence) is int and after_sequence > 0,
            "Cannot arm watch without valid source/owner evidence")
    return {
        **empty_details(row.details["generation"] + 1),
        "request_id": request_id, "owner_pk": owner_pk,
        "epoch": epoch, "desired": desired,
        "after_sequence": after_sequence,
    }


def match_delivery(row, delivery, *, owner_pk, epoch):
    """Match an authoritative capsule; no raw world or crew location fields."""
    validate_watch(row)
    if row.setting != "armed":
        return None
    details = row.details
    if (details["owner_pk"] != owner_pk or details["epoch"] != epoch
            or not isinstance(delivery, object)):
        return None
    try:
        packet = present_delivery(delivery, epoch=epoch)
    except (NetworkAccessError, TypeError, KeyError, ValueError):
        return None
    sequence = getattr(delivery, "sequence", None)
    if (type(sequence) is not int or sequence <= details["after_sequence"]
            or getattr(delivery, "operation", None) != DELIVERED
            or getattr(delivery, "component_key", None) != PRINCIPAL
            or packet["reader_id"] != SENSOR
            or packet["access_link_id"] != LINK
            or packet["setting_after"] != details["desired"]):
        return None
    return {
        "delivery_sequence": sequence,
        "source_time": packet["source_time"],
        "desired": details["desired"],
    }


def source_after_arm(row, physical, observation):
    """A new delivery must cite a hatch *change made after arming*.

    The delivery sequence alone cannot legalize re-publishing an old sensor
    frame after a network outage or after the player chose a new watch.
    """
    validate_watch(row)
    if row.setting != "armed":
        return False
    barrier = row.details["after_sequence"]
    physical_seq = getattr(physical, "sequence", None)
    observed_seq = getattr(observation, "sequence", None)
    return (type(physical_seq) is int and type(observed_seq) is int
            and barrier < physical_seq < observed_seq)


def committed_watch_notice(row, event, *, owner_pk, epoch):
    """Prepare the minimal OOC wake from a committed, matching fired state.

    Pure validation intentionally returns None for a stale enrolment, a
    superseded watch, or any malformed event. Never expose raw event contents,
    actors, character locations, or the physically hidden source journal.
    """
    try:
        validate_watch(row)
    except (ShipWatchError, AttributeError, KeyError, TypeError, ValueError):
        return None
    if row.setting != "fired":
        return None
    details = row.details
    if (type(owner_pk) is not int or owner_pk <= 0
            or details["owner_pk"] != owner_pk
            or details["epoch"] != epoch):
        return None
    after = getattr(event, "after", None)
    before = getattr(event, "before", None)
    seq = getattr(event, "sequence", None)
    fields = {
        "generation", "desired", "delivery_event_id", "source_time",
        "controls_time", "physical_actuation",
    }
    if (type(seq) is not int or seq <= details["delivery_sequence"]
            or getattr(event, "component_key", None) != KEY
            or getattr(event, "operation", None) != FIRED
            or getattr(event, "source_event_id", None) != str(details["delivery_sequence"])
            or getattr(event, "request_id", None) is not None
            or getattr(event, "actor_dbref", None) is not None
            or not isinstance(after, dict) or set(after) != fields
            or not isinstance(before, dict)
            or before != {
                "generation": details["generation"],
                "desired": details["desired"],
            }
            or after["generation"] != details["generation"]
            or after["desired"] != details["desired"]
            or after["delivery_event_id"] !=
                "ox-net-" + str(details["delivery_sequence"])
            or after["source_time"] != details["source_time"]
            or getattr(event, "game_time", None) != details["source_time"]
            or after["controls_time"] is not False
            or after["physical_actuation"] is not False):
        return None
    return {
        "schema_version": "ox.ship-mind-watch-wake/1",
        "status": "fired",
        "request_id": details["request_id"],
        "desired": details["desired"],
        "wake_event_id": "ox-watch-" + str(seq),
        "delivery_event_id": after["delivery_event_id"],
        "source_time": details["source_time"],
        "controls_time": False,
        "physical_actuation": False,
    }
