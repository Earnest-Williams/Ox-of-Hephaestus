"""G19 major hull containment: as-built pressure bulkheads and EVA repair face.

Only a registered real hull breach can become a major casualty. A powered
local damage-control panel runs a *timed* all-boundary isolation; one broken
bulkhead prevents false containment. The external patch then uses the same
finite tool/spare ledger and existing hull phase transition as minor repairs.
"""
from __future__ import annotations

import copy
import math
import re

ISOLATE_SECONDS = 120.0
MIN_MAJOR_KG_S = 0.05
MAX_SITES = 12


class MajorDamageError(ValueError):
    pass


def exterior_face_for(zone):
    if not isinstance(zone, str):
        raise MajorDamageError("Unknown physical damaged pressure cell")
    match = re.fullmatch(r"PZ-DR-(0[1-6])-SVC", zone)
    if match:
        return "EXT-DR" + match.group(1) + "-SKIN"
    if zone == "PZ-BOW-SHIELD":
        return "EXT-BOW-SHIELD"
    if zone == "PZ-AFT-PROP":
        return "EXT-PROP-AFT"
    raise MajorDamageError("No surveyed external patch face at this installed shell")


def initial_major_damage():
    return {"sites": {}, "containments_completed": 0}


def validate_major_damage(value):
    if (not isinstance(value, dict) or set(value) != {
            "sites", "containments_completed"} or
            type(value["containments_completed"]) is not int
            or value["containments_completed"] < 0
            or not isinstance(value["sites"], dict)
            or len(value["sites"]) > MAX_SITES):
        raise MajorDamageError("Invalid durable hull containment registry")
    for zone, row in value["sites"].items():
        if (not isinstance(row, dict) or set(row) != {
                "external_face", "boundaries", "isolated",
                "remaining_s", "operator"}):
            raise MajorDamageError("Incomplete large-breach survey")
        if row["external_face"] != exterior_face_for(zone):
            raise MajorDamageError("Exterior site not physically adjacent to breach")
        if (not isinstance(row["boundaries"], list)
                or not row["boundaries"]
                or len(row["boundaries"]) > 64
                or len(row["boundaries"]) != len(set(row["boundaries"]))
                or not all(isinstance(x, str) and x.startswith("ACC-")
                           for x in row["boundaries"])):
            raise MajorDamageError("No classified intact rated boundaries")
        if type(row["isolated"]) is not bool:
            raise MajorDamageError("Invalid containment interlock")
        n = row["remaining_s"]
        if (isinstance(n, bool) or not isinstance(n, (float, int))
                or not math.isfinite(n) or not 0 <= n <= ISOLATE_SECONDS):
            raise MajorDamageError("Invalid bounded isolation progress")
        if (row["operator"] is not None and not re.fullmatch(
                r"#[0-9]+", row["operator"])):
            raise MajorDamageError("Containment has no real assigned operator")
        if row["isolated"] and (n != 0 or row["operator"] is not None):
            raise MajorDamageError("Closed bulkheads still claim a running isolation job")
    return True


def register_major_site(registry, hull, *, zone, exterior_room, boundaries):
    validate_major_damage(registry)
    breach = hull["breaches"].get(zone)
    if (breach is None or breach["phase"] == "restored"
            or breach["original_leak_kg_s"] < MIN_MAJOR_KG_S):
        raise MajorDamageError("No large registered open shell leak here")
    if exterior_face_for(zone) != exterior_room:
        raise MajorDamageError("Exterior surface does not belong to damaged shell")
    if (zone in registry["sites"] or len(registry["sites"]) >= MAX_SITES):
        raise MajorDamageError("Duplicate or excessive structural casualty")
    b = sorted(set(boundaries))
    if not b:
        raise MajorDamageError("No rated bulkheads to isolate")
    out = copy.deepcopy(registry)
    out["sites"][zone] = {
        "external_face": exterior_room, "boundaries": b,
        "isolated": False, "remaining_s": 0.0, "operator": None,
    }
    validate_major_damage(out)
    return out


def start_containment(registry, *, zone, actor):
    validate_major_damage(registry)
    if (zone not in registry["sites"]
            or registry["sites"][zone]["isolated"]
            or registry["sites"][zone]["remaining_s"] > 0):
        raise MajorDamageError("No free, unisolated physical damage-control operation")
    if not isinstance(actor, str) or not re.fullmatch(r"#[0-9]+", actor):
        raise MajorDamageError("No named damage-control operator")
    out = copy.deepcopy(registry)
    out["sites"][zone]["remaining_s"] = ISOLATE_SECONDS
    out["sites"][zone]["operator"] = actor
    validate_major_damage(out)
    return out


def step_containments(registry, seconds, *, ready_zones):
    validate_major_damage(registry)
    if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds) or not 0 <= seconds <= 60):
        raise MajorDamageError("Invalid isolation tick")
    out = copy.deepcopy(registry)
    completed = []
    for zone, row in out["sites"].items():
        if row["remaining_s"] <= 0 or zone not in ready_zones:
            continue
        row["remaining_s"] = max(0.0, row["remaining_s"] - seconds)
        if row["remaining_s"] <= 1e-8:
            row["operator"] = None
            row["isolated"] = True
            out["containments_completed"] += 1
            completed.append(zone)
    validate_major_damage(out)
    return out, tuple(completed)


def external_repair_ready(registry, *, zone, room, suit_valid,
                          actual_closed_boundaries):
    validate_major_damage(registry)
    site = registry["sites"].get(zone)
    return bool(site and site["isolated"]
                and site["external_face"] == room and suit_valid
                and set(site["boundaries"]) <= set(actual_closed_boundaries))
