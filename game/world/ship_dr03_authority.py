"""First G19 drum-3 remote authority: one LT isolator, local-first arbitration.

This contract deliberately grants no ship-wide remote-isolator capability.
The physically fitted local station is authoritative on takeover, whether
or not the central backbone is usable.
"""

from __future__ import annotations

import re

SCHEMA = "ox.dr03-control/1"
KEY = "control:DR-03-LT-IF"
TARGET = "ISO-DR-03-LT-IF"
STATION = "LCS-DR-03"
ROOM = "BE-05-SVC"
GATEWAY = "GW-LCS-DR-03"
OPERATIONS = frozenset({"takeover", "handback", "switch"})


class DrumControlError(ValueError):
    """Remote or local control is absent, unsafe, or held by crew."""


def require(ok, reason):
    if not ok:
        raise DrumControlError(reason)


def request_id_valid(request_id):
    require(isinstance(request_id, str)
            and re.fullmatch(r"[0-9a-f]{32}", request_id) is not None,
            "Expected 32 lowercase hex request ID")
    return request_id


def control_ref():
    return {
        "schema_version": SCHEMA, "station": STATION,
        "station_room": ROOM, "gateway": GATEWAY,
        "target": TARGET, "allowed_actions": ["open", "closed"],
        "local_priority": True, "other_isolators_enabled": False,
    }


def validate_control(row):
    require(row is not None and row.key == KEY
            and row.category == "control" and row.source_id == "DR-03-LT-IF"
            and row.source_model == SCHEMA
            and row.space_id == ROOM
            and row.reference == control_ref()
            and row.condition == "serviceable"
            and row.setting in {"remote", "local"}
            and isinstance(row.details, dict)
            and set(row.details) == {"holder", "epoch"}
            and type(row.details["epoch"]) is int
            and row.details["epoch"] >= 0
            and (
                (row.setting == "remote" and row.details["holder"] is None)
                or (row.setting == "local"
                    and isinstance(row.details["holder"], str)
                    and row.details["holder"].startswith("#"))
            ), "No valid, as-fitted drum-3 authority state")
    return True


def next_authority(mode, holder, actor, operation):
    """Pure state transition; a local holder excludes all remote operation."""
    require(mode in {"remote", "local"}
            and (holder is None if mode == "remote"
                 else isinstance(holder, str) and holder.startswith("#")),
            "Malformed drum-3 arbitration state")
    require(isinstance(actor, str) and actor.startswith("#"),
            "A physical crew principal is required")
    require(operation in {"takeover", "handback"}, "Unknown local action")
    if operation == "takeover":
        require(mode == "remote" or holder == actor,
                "A different crew member holds local control")
        return ("local", actor, mode != "local")
    require(mode == "local" and holder == actor,
            "Only the physical holder can hand control back")
    return ("remote", None, True)


def check_lt_interlocks(item, clock_details, *, value):
    """Shared G19 target-specific physical barriers for local and remote."""
    require(value in {"open", "closed"}, "Unknown valve position")
    require(item.source_id == TARGET
            and item.category == "isolator"
            and item.reference.get("remote_operable") is True
            and item.reference.get("manual_operation") is True,
            "No fitted remotely controllable drum-3 LT valve")
    require(item.condition not in {
        "faulted", "failed", "destroyed", "severed", "jammed"},
        "Drum-3 LT valve damaged")
    if value == "closed":
        require(not item.details.get("physics_power_trip_latched"),
                "Physical trip requires attended reset")
        repairs = (clock_details.get("repairs") or {}).get("jobs", {})
        for work in repairs:
            # No remote closure around a locally held target.
            require(work not in {
                "isolator:" + TARGET, "equipment:" + TARGET},
                "Attended target maintenance padlock")
        fault_cases = (clock_details.get("fault_cases") or {}).get("cases", {})
        for case in fault_cases.values():
            if TARGET in case.get("feeders", ()) and case.get("stage") in {
                "isolated", "repairing", "repaired"}:
                raise DrumControlError("Fault case locks out valve restoration")
    return True
