"""G19 finite cross-system equipment repairs: time, on-site crew and spares.

Pure work-order state. A repair never authorises startup, overrides a
pressure/power/rotary interlock, repairs a destroyed hull, or invents stock.
The installed Evennia operation must prove safe isolation at every advance.
"""
from __future__ import annotations

import copy
import math

from world.ship_water_recycling import WaterError, _quantity

# Maintenance times deliberately make repairs an operational crew commitment,
# rather than a single magic command. Mass is scenario spare replacement stock.
REPAIR_CLASSES = {
    "degraded": (0.5, 120.0),
    "faulted": (1.0, 300.0),
    "failed": (3.0, 600.0),
    "jammed": (2.0, 600.0),
    "severed": (4.0, 900.0),
}
MAX_HAND_PARTS_KG = 12.0
MAX_JOBS = 32
MAX_HELPERS = 3


def initial_repairs():
    return {"carried_kg": {}, "jobs": {}, "installed_kg": 0.0,
            "completed": 0, "delivered_spares_kg": 0.0}


def validate_repairs(repairs):
    if not isinstance(repairs, dict) or set(repairs) != {
            "carried_kg", "jobs", "installed_kg", "completed",
            "delivered_spares_kg"}:
        raise WaterError("Invalid commissioned repair state")
    for value in ("installed_kg", "delivered_spares_kg"):
        _quantity(repairs[value])
    if (isinstance(repairs["completed"], bool) or
            not isinstance(repairs["completed"], int) or
            repairs["completed"] < 0):
        raise WaterError("Invalid completed repair count")
    for worker, value in repairs["carried_kg"].items():
        if (not isinstance(worker, str) or not worker.startswith("#")
                or _quantity(value) > MAX_HAND_PARTS_KG + 1e-7):
            raise WaterError("Unknown spare-parts custodian or overburden")
    if not math.isclose(
            repairs["delivered_spares_kg"],
            repairs["installed_kg"]
            + sum(repairs["carried_kg"].values())
            + sum(j["staged_kg"] for j in repairs["jobs"].values()),
            abs_tol=1e-6, rel_tol=1e-10):
        raise WaterError("Maintenance spare custody does not reconcile")
    if not isinstance(repairs["jobs"], dict) or len(repairs["jobs"]) > MAX_JOBS:
        raise WaterError("Unbounded machine maintenance orders")
    for target, job in repairs["jobs"].items():
        if not isinstance(target, str) or ":" not in target:
            raise WaterError("Unidentified installed equipment work")
        if job["condition"] not in REPAIR_CLASSES:
            raise WaterError("Unrepairable condition cannot be cleared")
        if (job["required_kg"] != REPAIR_CLASSES[job["condition"]][0]
                or job["total_s"] != REPAIR_CLASSES[job["condition"]][1]):
            raise WaterError("Invalid physical repair work or spare budget")
        if _quantity(job["remaining_s"]) > job["total_s"] + 1e-7:
            raise WaterError("Repair time was extended beyond declared work")
        if _quantity(job["staged_kg"]) != job["required_kg"]:
            raise WaterError("Repair was started without finite replacement parts")
        if (not isinstance(job["workers"], list) or
                not 1 <= len(job["workers"]) <= MAX_HELPERS or
                len(job["workers"]) != len(set(job["workers"]))):
            raise WaterError("Repair has no valid individual workers")
        if not isinstance(job["room"], str) or not job["room"]:
            raise WaterError("Repair work has no installed physical room")


def take_parts(repairs, *, actor_dbref, kg, stock_kg):
    kg = _quantity(kg)
    stock_kg = _quantity(stock_kg)
    if not 0 < kg <= MAX_HAND_PARTS_KG or kg > stock_kg + 1e-7:
        raise WaterError("Finite physical spare quantity unavailable")
    r = copy.deepcopy(repairs)
    held = r["carried_kg"].get(actor_dbref, 0.0)
    if held + kg > MAX_HAND_PARTS_KG + 1e-7:
        raise WaterError("Maintenance worker exceeds portable spares limit")
    r["carried_kg"][actor_dbref] = held + kg
    r["delivered_spares_kg"] += kg
    validate_repairs(r)
    return r, stock_kg - kg


def begin_repair(repairs, *, target, room, actor_dbref, condition):
    if condition not in REPAIR_CLASSES or ":" not in target:
        raise WaterError("Physical condition is not a repairable defect")
    r = copy.deepcopy(repairs)
    if target in r["jobs"] or len(r["jobs"]) >= MAX_JOBS:
        raise WaterError("Machine repair slot is already occupied")
    kg, duration = REPAIR_CLASSES[condition]
    available = r["carried_kg"].get(actor_dbref, 0.0)
    if kg > available + 1e-7:
        raise WaterError("No physically carried compatible replacement parts")
    r["carried_kg"][actor_dbref] = available - kg
    r["jobs"][target] = {
        "room": room, "condition": condition, "workers": [actor_dbref],
        "required_kg": kg, "staged_kg": kg,
        "total_s": duration, "remaining_s": duration,
    }
    validate_repairs(r)
    return r


def join_repair(repairs, *, target, actor_dbref, room):
    r = copy.deepcopy(repairs)
    job = r["jobs"].get(target)
    if not job or job["room"] != room or actor_dbref in job["workers"]:
        raise WaterError("No active local work order for this worker")
    if len(job["workers"]) >= MAX_HELPERS:
        raise WaterError("Maximum physical repair crew reached")
    job["workers"].append(actor_dbref)
    validate_repairs(r)
    return r


def step_repairs(repairs, seconds, *, present_workers, safe_targets):
    if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds) or not 0 <= seconds <= 60):
        raise WaterError("Invalid bounded maintenance work interval")
    r = copy.deepcopy(repairs)
    completed = []
    for key, job in sorted(list(r["jobs"].items())):
        workers = [
            dbref for dbref in job["workers"]
            if dbref in present_workers.get(job["room"], set())
        ]
        if not workers or key not in safe_targets:
            continue
        # Second and third workers give small diminishing assistance. There
        # must be at least one qualified person physically at the machine.
        speed = 1.0 + 0.4 * min(2, len(workers) - 1)
        job["remaining_s"] = max(0.0, job["remaining_s"] - seconds * speed)
        if job["remaining_s"] <= 1e-7:
            r["installed_kg"] += job["staged_kg"]
            r["completed"] += 1
            completed.append((key, job["condition"], job["staged_kg"]))
            del r["jobs"][key]
    validate_repairs(r)
    return r, tuple(completed)
