"""G19 finite hull breach, temporary sealing and permanent restoration.

A registered breach belongs to an installed pressure cell and an operator-
surveyed repair face in a real ship room. This library does not invent rooms,
labour, parts or breathable air; shared Evennia maintenance owns work orders,
finite spares, crew positions and persistent receipts.
"""
from __future__ import annotations

import copy
import math

MAX_BREACHES = 64
MAX_LEAK_KG_S = 10.0
TEMPORARY_REMAINING_FRACTION = 0.10
PHASE_CONDITION = {"open": "jammed", "patched": "severed"}


class HullError(ValueError):
    """Bad or inconsistent persistent hull state."""


def _number(x, *, positive=False, maximum=None):
    if (isinstance(x, bool) or not isinstance(x, (int, float))
            or not math.isfinite(x) or x < 0
            or (positive and x == 0)
            or (maximum is not None and x > maximum)):
        raise HullError("Nonphysical hull quantity")
    return float(x)


def initial_hull():
    return {"breaches": {}, "patches_completed": 0,
            "restorations_completed": 0}


def effective_leak(breach):
    if breach["phase"] == "open":
        return breach["original_leak_kg_s"]
    if breach["phase"] == "patched":
        return breach["original_leak_kg_s"] * TEMPORARY_REMAINING_FRACTION
    if breach["phase"] == "restored":
        return 0.0
    raise HullError("Unknown physical hull condition")


def validate_hull(hull):
    if not isinstance(hull, dict) or set(hull) != {
            "breaches", "patches_completed", "restorations_completed"}:
        raise HullError("Invalid G19 hull registry")
    breaches = hull["breaches"]
    if not isinstance(breaches, dict) or len(breaches) > MAX_BREACHES:
        raise HullError("Unbounded hull damage registry")
    for key in ("patches_completed", "restorations_completed"):
        x = hull[key]
        if isinstance(x, bool) or not isinstance(x, int) or x < 0:
            raise HullError("Invalid hull repair counter")
    if hull["restorations_completed"] > hull["patches_completed"]:
        raise HullError("Hull restoration without a temporary seal")
    patched = restored = 0
    for zone, breach in breaches.items():
        if not isinstance(zone, str) or not zone.startswith("PZ-"):
            raise HullError("Hull breach is not bound to a named pressure cell")
        if not isinstance(breach, dict) or set(breach) != {
                "site_room", "phase", "original_leak_kg_s",
                "installed_spares_kg"}:
            raise HullError("Unidentified hull repair face")
        if not isinstance(breach["site_room"], str) or not breach["site_room"]:
            raise HullError("Hull breach has no real repair room")
        if breach["phase"] not in {"open", "patched", "restored"}:
            raise HullError("Invalid hull restoration phase")
        _number(breach["original_leak_kg_s"], positive=True,
                maximum=MAX_LEAK_KG_S)
        _number(breach["installed_spares_kg"])
        if breach["phase"] != "open":
            patched += 1
        if breach["phase"] == "restored":
            restored += 1
        # Each stage spends the already issued parts from the shared ledger.
        expected = (0.0 if breach["phase"] == "open"
                    else 2.0 if breach["phase"] == "patched" else 6.0)
        if not math.isclose(breach["installed_spares_kg"], expected,
                            rel_tol=0, abs_tol=1e-7):
            raise HullError("Hull service material does not match repair phase")
    if (patched != hull["patches_completed"]
            or restored != hull["restorations_completed"]):
        raise HullError("Hull repair counters do not reconcile")
    return True


def register_breach(hull, *, zone, site_room, leak_kg_s):
    validate_hull(hull)
    if not isinstance(zone, str) or not zone.startswith("PZ-"):
        raise HullError("Breach requires an existing named pressure zone")
    if not isinstance(site_room, str) or not site_room:
        raise HullError("Breach repair face requires an installed room")
    rate = _number(leak_kg_s, positive=True, maximum=MAX_LEAK_KG_S)
    if zone in hull["breaches"] or len(hull["breaches"]) >= MAX_BREACHES:
        raise HullError("Breach exists or hull casualty capacity exceeded")
    result = copy.deepcopy(hull)
    result["breaches"][zone] = {
        "site_room": site_room,
        "phase": "open",
        "original_leak_kg_s": rate,
        "installed_spares_kg": 0.0,
    }
    validate_hull(result)
    return result


def expected_repair_condition(hull, zone):
    validate_hull(hull)
    breach = hull["breaches"].get(zone)
    return PHASE_CONDITION.get(breach["phase"]) if breach else None


def finish_hull_work(hull, *, zone, condition, installed_kg):
    """Complete work only after an already material-backed shared repair."""
    validate_hull(hull)
    breach = hull["breaches"].get(zone)
    if not breach or condition != expected_repair_condition(hull, zone):
        raise HullError("Hull phase changed while repair work was underway")
    required = 2.0 if condition == "jammed" else 4.0
    if not math.isclose(_number(installed_kg), required,
                        abs_tol=1e-7, rel_tol=0):
        raise HullError("Hull service completed without its specified parts")
    result = copy.deepcopy(hull)
    work = result["breaches"][zone]
    work["installed_spares_kg"] += required
    if condition == "jammed":
        work["phase"] = "patched"
        result["patches_completed"] += 1
    else:
        work["phase"] = "restored"
        result["restorations_completed"] += 1
    validate_hull(result)
    return result, effective_leak(work)
