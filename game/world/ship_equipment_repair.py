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
# Pre-existing fitted toolkit inventory in TOOL-CRIB, counted among selected
# shipboard stores rather than new cargo mass. Each kit is reusable and
# individually assigned; none can service two distant machines at once.
FITTED_TOOLKITS = 6


def initial_repairs():
    return {"carried_kg": {}, "jobs": {}, "installed_kg": 0.0,
            "completed": 0, "delivered_spares_kg": 0.0,
            "site_surveys": {}, "toolkits_at_crib": FITTED_TOOLKITS,
            "toolkit_carriers": []}


def validate_repairs(repairs):
    if not isinstance(repairs, dict) or set(repairs) != {
            "carried_kg", "jobs", "installed_kg", "completed",
            "delivered_spares_kg", "site_surveys",
            "toolkits_at_crib", "toolkit_carriers"}:
        raise WaterError("Invalid commissioned repair state")
    for value in ("installed_kg", "delivered_spares_kg"):
        _quantity(repairs[value])
    carriers = repairs["toolkit_carriers"]
    on_rack = repairs["toolkits_at_crib"]
    if (isinstance(on_rack, bool) or not isinstance(on_rack, int)
            or not isinstance(carriers, list)
            or not all(isinstance(ref, str) and ref.startswith("#")
                       and ref[1:].isdigit() for ref in carriers)
            or len(carriers) != len(set(carriers))
            or on_rack < 0 or on_rack + len(carriers) != FITTED_TOOLKITS):
        raise WaterError("Fitted repair toolkit count or custody inconsistent")
    if (not isinstance(repairs["site_surveys"], dict)
            or any(not isinstance(room, str) or not room
                   or kind != "suited_service"
                   for room, kind in repairs["site_surveys"].items())):
        raise WaterError("Unknown operator-surveyed maintenance environment")
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
        if any(worker not in carriers for worker in job["workers"]):
            raise WaterError("A repair worker has no personally issued real toolkit")


def move_toolkit(repairs, *, actor_dbref, verb):
    """Move one of six *reusable* tool rolls, only at the installed crib.

    The Evennia caller proves the worker is physically at TOOL-CRIB. No
    inventory mass is added: this is a reassignment within fitted ship tools.
    Returning an active worker's toolkit is forbidden until the job ends.
    """
    if (not isinstance(actor_dbref, str) or not actor_dbref.startswith("#")
            or not actor_dbref[1:].isdigit()):
        raise WaterError("Tool custody requires an identifiable crew member")
    r = copy.deepcopy(repairs)
    holders = r["toolkit_carriers"]
    if verb == "pickup_toolkit":
        if actor_dbref in holders or r["toolkits_at_crib"] <= 0:
            raise WaterError("No unassigned toolkit at this physical crib")
        holders.append(actor_dbref)
        r["toolkits_at_crib"] -= 1
    elif verb == "return_toolkit":
        if actor_dbref not in holders or any(
                actor_dbref in job["workers"] for job in r["jobs"].values()):
            raise WaterError("Cannot return a toolkit required by active maintenance")
        holders.remove(actor_dbref)
        r["toolkits_at_crib"] += 1
    else:
        raise WaterError("Maintenance tools require pickup_toolkit or return_toolkit")
    validate_repairs(r)
    return r


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
    if actor_dbref not in r["toolkit_carriers"]:
        raise WaterError("Actual reusable maintenance toolkit required")
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
    if actor_dbref not in r["toolkit_carriers"]:
        raise WaterError("Assistant must bring an actual issued toolkit")
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
            and dbref in r["toolkit_carriers"]
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
