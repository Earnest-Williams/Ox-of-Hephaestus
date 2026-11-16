"""Bounded request-only control for the surveyed drum-3 service hatch.

The existing contact is passive; this module grants no door-motor authority.
An authenticated ship mind may request a change, but an attended crew member
makes the decision and performs any actual hatch operation separately.
"""

from __future__ import annotations

import re

SCHEMA = "ox.dr03-hatch-handover/1"
KEY = "control:DR-03-HATCH-HANDOVER"
SOURCE = "DR-03-HATCH-HANDOVER"
LINK = "ACC-DR-03-LOCK-FIX"
SENSOR = "ACSR-DR-03-FIX"
STATION = "LCS-DR-03"
ROOM = "BE-05-SVC"
REQUESTED = "g19_dr03_hatch_requested"
DECIDED = "g19_dr03_hatch_decided"
BAD = frozenset({"faulted", "failed", "destroyed", "severed", "jammed"})


class HatchHandoverError(ValueError):
    """Unfitted, unavailable, malformed, or unauthorized hatch handover."""


def require(valid, explanation):
    if not valid:
        raise HatchHandoverError(explanation)


def request_id_valid(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value)
            is not None, "Expected a 32-character lowercase hex request ID")
    return value


def reference():
    return {
        "schema_version": SCHEMA,
        "link": LINK,
        "sensor": SENSOR,
        "station": STATION,
        "station_room": ROOM,
        "remote_door_motor": False,
        "remote_role": "request_only",
        "local_decision_required": True,
    }


def validate_control(row):
    require(row is not None and row.key == KEY and row.category == "control"
            and row.source_id == SOURCE and row.source_model == SCHEMA
            and row.space_id == ROOM and row.condition == "serviceable"
            and row.reference == reference()
            and row.setting in {"idle", "pending"}
            and isinstance(row.details, dict)
            and set(row.details) == {
                "request_id", "request_event", "desired", "requester", "epoch"}
            and type(row.details["epoch"]) is int
            and row.details["epoch"] >= 0,
            "Invalid installed drum-3 hatch handover state")
    details = row.details
    if row.setting == "idle":
        require(all(details[field] is None for field in (
            "request_id", "request_event", "desired", "requester")),
            "Idle hatch handover contains a phantom request")
    else:
        request_id_valid(details["request_id"])
        require(type(details["request_event"]) is int
                and details["request_event"] > 0
                and details["desired"] in {"open", "closed"}
                and isinstance(details["requester"], str)
                and re.fullmatch(r"account:[1-9][0-9]*", details["requester"])
                is not None,
                "Pending hatch handover lacks a genuine request")
    return True


def pending_state(row, request_id, desired, requester, event_sequence):
    validate_control(row)
    request_id_valid(request_id)
    require(row.setting == "idle", "An attended hatch request is outstanding")
    require(desired in {"open", "closed"}, "Unknown requested hatch position")
    require(isinstance(requester, str)
            and re.fullmatch(r"account:[1-9][0-9]*", requester) is not None,
            "Remote requester is not an enrolled account")
    require(type(event_sequence) is int and event_sequence > 0,
            "Missing committed request event")
    return {
        "request_id": request_id, "request_event": event_sequence,
        "desired": desired, "requester": requester,
        "epoch": row.details["epoch"] + 1,
    }


def clear_pending(row, request_id):
    validate_control(row)
    request_id_valid(request_id)
    require(row.setting == "pending"
            and row.details["request_id"] == request_id,
            "No matching pending request at the local console")
    return {
        "request_id": None, "request_event": None, "desired": None,
        "requester": None, "epoch": row.details["epoch"] + 1,
    }
