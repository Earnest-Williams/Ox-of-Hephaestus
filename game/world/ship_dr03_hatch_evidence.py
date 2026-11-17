"""Pure proof that an accepted hatch request attained a measured position.

Receipt of a local decision is not physical work. A genuine transition by the
accepting crew member must also be observed by the fitted dry contact and
delivered over the live ship network at event time. Never backfill a sensor
observation that was local-only during a communications failure.
"""

from __future__ import annotations

from world.ship_access_contact import LINK, OBSERVED, SENSOR
from world.ship_dr03_hatch_policy import DECIDED, request_id_valid
from world.ship_network_access import (
    DELIVERED, PRINCIPAL, NetworkAccessError, capture, present_delivery,
)


def _value(row, name):
    return getattr(row, name, None)


def verified_hatch_completion(
    decision, physical, observation, delivery, *,
    original_request_id, desired, principal_epoch,
):
    """Return bounded evidence identifiers, or None without granting truth.

    The physical action is attributed to the accepting crew member; the dry
    contact itself cannot identify a person. The resulting status means that
    the desired position was *observed at source time*, not that the hatch
    remains there now or that future action has been authorised.
    """
    try:
        request_id_valid(original_request_id)
    except ValueError:
        return None
    if desired not in {"open", "closed"}:
        return None
    dseq, pseq, oseq, nseq = (
        _value(row, "sequence")
        for row in (decision, physical, observation, delivery)
    )
    if (any(type(n) is not int or n <= 0 for n in (dseq, pseq, oseq, nseq))
            or not (dseq < pseq < oseq < nseq)):
        return None
    d_after = _value(decision, "after")
    p_before, p_after = _value(physical, "before"), _value(physical, "after")
    o_before, o_after = _value(observation, "before"), _value(observation, "after")
    actor = _value(decision, "actor_dbref")
    if (not all(isinstance(x, dict)
                for x in (d_after, p_before, p_after, o_before, o_after))
            or _value(decision, "operation") != DECIDED
            or d_after.get("original_request_id") != original_request_id
            or d_after.get("local_decision") != "accept"
            or d_after.get("status") != "accepted_for_manual_action"
            or d_after.get("desired") != desired
            or not isinstance(actor, str) or not actor.startswith("#")
            or _value(physical, "operation") != "crew_hatch"
            or _value(physical, "component_key") != "access:" + LINK
            or _value(physical, "actor_dbref") != actor
            or not isinstance(_value(physical, "request_id"), str)
            or p_before.get("setting") not in {"open", "closed"}
            or p_before["setting"] == desired
            or p_after.get("setting") != desired
            or p_after.get("requested_value") != desired
            or _value(observation, "operation") != OBSERVED
            or _value(observation, "component_key") != "equipment:" + SENSOR
            or _value(observation, "source_event_id") != str(pseq)
            or _value(observation, "actor_dbref") is not None
            or _value(observation, "request_id") is not None
            or o_before.get("setting") != p_before["setting"]
            or o_after.get("setting") != desired
            or _value(delivery, "operation") != DELIVERED
            or _value(delivery, "component_key") != PRINCIPAL
            or _value(delivery, "source_event_id") != str(oseq)
            or _value(delivery, "actor_dbref") is not None
            or _value(delivery, "request_id") is not None):
        return None
    try:
        observed = capture(observation)
        delivered = present_delivery(delivery, epoch=principal_epoch)
    except (NetworkAccessError, KeyError, TypeError, ValueError):
        return None
    for name, value in observed.items():
        if name == "sensor_event_id":
            if delivered.get(name) != str(oseq):
                return None
        elif delivered.get(name) != value:
            return None
    if (observed["physical_hatch_event_id"] != str(pseq)
            or observed["setting_after"] != desired
            or _value(physical, "game_time") != observed["source_time"]
            or _value(observation, "game_time") != observed["source_time"]
            or _value(delivery, "game_time") != observed["source_time"]):
        return None
    return {
        "status": "world_confirmed_at_source_time",
        "physical_hatch_event_id": str(pseq),
        "sensor_event_id": str(oseq),
        "delivery_event_id": delivered["delivery_event_id"],
        "source_time": observed["source_time"],
    }
