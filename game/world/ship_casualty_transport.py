"""G19 assisted casualty transport: deterministic durable manual carry orders.

Only the installed Evennia adapter may prove real people, doorway, pressure
and current location. This pure state machine never moves or heals a character.
"""
from __future__ import annotations

import copy
import math
import re

MAX_JOBS = 4
MIN_TRAVEL_S = 30.0
MAX_TRAVEL_S = 240.0
MAX_TICK_S = 60.0

# No suits, industrial freight passage, detached rotary collar or exterior EVA.
INTERIOR_CARRY_KINDS = frozenset({
    "door", "pressure_door", "service_door", "cabin_door",
    "store_door", "fire_door", "cargo_service_door",
    "pressure_hatch", "service_hatch",
})


class RescueError(ValueError):
    """Impossible physical casualty transport, or corrupted durable order."""


def _ref(value):
    return isinstance(value, str) and re.fullmatch(r"#[0-9]+", value) is not None


def _time(value, maximum):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 <= value <= maximum):
        raise RescueError("Invalid finite casualty transport interval")
    return float(value)


def initial_rescue():
    return {"jobs": {}, "completed": 0, "cancelled": 0}


def validate_rescue(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"jobs", "completed", "cancelled"}
            or not isinstance(ledger["jobs"], dict)
            or len(ledger["jobs"]) > MAX_JOBS):
        raise RescueError("Incomplete casualty transport custody")
    for counter in ("completed", "cancelled"):
        if type(ledger[counter]) is not int or ledger[counter] < 0:
            raise RescueError("Invalid completed transport accounting")
    busy = set()
    ids = set()
    for patient, job in ledger["jobs"].items():
        if (not _ref(patient) or not isinstance(job, dict)
                or set(job) != {
                    "lead", "helper", "link", "direction",
                    "origin", "destination", "remaining_s", "total_s",
                    "request_id"}):
            raise RescueError("Malformed transport order")
        people = (patient, job["lead"], job["helper"])
        if (not all(_ref(ref) for ref in people)
                or len(set(people)) != 3 or busy.intersection(people)):
            raise RescueError("Transport personnel duplicated between active jobs")
        busy.update(people)
        if (not isinstance(job["link"], str)
                or not re.fullmatch(r"ACC-[A-Z0-9-]+", job["link"])
                or job["direction"] not in {"forward", "reverse"}
                or not isinstance(job["origin"], str) or not job["origin"]
                or not isinstance(job["destination"], str)
                or not job["destination"]
                or job["origin"] == job["destination"]
                or not isinstance(job["request_id"], str)
                or not re.fullmatch(r"[0-9a-f]{32}", job["request_id"])
                or job["request_id"] in ids):
            raise RescueError("Transport lacks unique real passage and receipt")
        ids.add(job["request_id"])
        total = _time(job["total_s"], MAX_TRAVEL_S)
        if total < MIN_TRAVEL_S:
            raise RescueError("Carrier transport time is too short")
        if _time(job["remaining_s"], MAX_TRAVEL_S) > total:
            raise RescueError("Casualty transfer time grew unexpectedly")
    return True


def begin_rescue(ledger, *, patient, lead, helper, link, direction,
                 origin, destination, seconds, request_id):
    validate_rescue(ledger)
    duration = _time(seconds, MAX_TRAVEL_S)
    if duration < MIN_TRAVEL_S:
        raise RescueError("Two-person manual transfer needs real elapsed time")
    if patient in ledger["jobs"] or len(ledger["jobs"]) >= MAX_JOBS:
        raise RescueError("Patient already being moved or rescue team full")
    out = copy.deepcopy(ledger)
    out["jobs"][patient] = {
        "lead": lead, "helper": helper,
        "link": link, "direction": direction,
        "origin": origin, "destination": destination,
        "remaining_s": duration, "total_s": duration,
        "request_id": request_id,
    }
    validate_rescue(out)
    return out


def step_rescue(ledger, seconds, *, ready_patients):
    """Advance only transports whose actual workers and door remain safe."""
    validate_rescue(ledger)
    dt = _time(seconds, MAX_TICK_S)
    if not isinstance(ready_patients, (set, frozenset)):
        raise RescueError("Missing independently verified passage readiness")
    out = copy.deepcopy(ledger)
    finished = []
    for patient, job in sorted(out["jobs"].items()):
        if patient not in ready_patients:
            continue
        job["remaining_s"] = max(0.0, job["remaining_s"] - dt)
        if job["remaining_s"] < 1e-8:
            finished.append((patient, copy.deepcopy(job)))
    validate_rescue(out)
    return out, tuple(finished)


def finish_rescue(ledger, *, patient, request_id, cancelled=False):
    validate_rescue(ledger)
    job = ledger["jobs"].get(patient)
    if (job is None or job["request_id"] != request_id
            or not cancelled and job["remaining_s"] > 1e-8):
        raise RescueError("Patient has no completed matching transport")
    out = copy.deepcopy(ledger)
    del out["jobs"][patient]
    out["cancelled" if cancelled else "completed"] += 1
    validate_rescue(out)
    return out
