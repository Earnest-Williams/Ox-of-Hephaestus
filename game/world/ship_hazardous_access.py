"""Timed suited transfer through the Ox's TWO original flywheel airlocks.

The original service-airlock assembly is a single authored access boundary:
its inner/outer seals are abstracted as a sealed machine cycle. The existing
corridor gas ledger retains its contained, recovered chamber gas throughout
the sealed cycle. No guessed breathable gas is assigned to the unsurveyed
flywheel bays; the worker consumes only a physically issued EVA suit.
"""
from __future__ import annotations

import copy
import math
import re

LOCKS = {
    "ACC-F1-BAY": ("TRUNK-A-F1", "F1-BAY", "LP-F1-BAY"),
    "ACC-F2-BAY": ("TRUNK-A-F2", "F2-BAY", "LP-F2-BAY"),
}
CYCLE_S = 180.0
MAX_STEP_S = 60.0


class BayAccessError(ValueError):
    pass


def _ref(value):
    return isinstance(value, str) and re.fullmatch(r"#[0-9]+", value) is not None


def initial_bay_access():
    return {"surveyed_bays": [], "jobs": {}, "completed": 0}


def validate_bay_access(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"surveyed_bays", "jobs", "completed"}
            or not isinstance(ledger["surveyed_bays"], list)
            or len(ledger["surveyed_bays"]) != len(set(ledger["surveyed_bays"]))
            or not set(ledger["surveyed_bays"]) <= {v[1] for v in LOCKS.values()}
            or not isinstance(ledger["jobs"], dict) or len(ledger["jobs"]) > 2
            or type(ledger["completed"]) is not int or ledger["completed"] < 0):
        raise BayAccessError("Invalid commissioned flywheel service assembly")
    seen_links = set()
    for actor, job in ledger["jobs"].items():
        if (not _ref(actor) or not isinstance(job, dict)
                or set(job) != {"link", "from", "to", "direction",
                               "remaining_s", "request_id"}):
            raise BayAccessError("Service transfer has unknown occupant")
        link = job["link"]
        if link not in LOCKS or link in seen_links:
            raise BayAccessError("One physical occupant at a time per fitted lock")
        seen_links.add(link)
        corridor, bay, _ = LOCKS[link]
        src, dest = ((corridor, bay) if job["direction"] == "forward"
                     else (bay, corridor) if job["direction"] == "reverse"
                     else (None, None))
        if (job["from"], job["to"]) != (src, dest):
            raise BayAccessError("Flywheel service worker is routed through a false room")
        if (bay not in ledger["surveyed_bays"]
                or not isinstance(job["request_id"], str)
                or re.fullmatch(r"[0-9a-f]{32}", job["request_id"]) is None
                or isinstance(job["remaining_s"], bool)
                or not isinstance(job["remaining_s"], (int, float))
                or not math.isfinite(job["remaining_s"])
                or not 0 <= job["remaining_s"] <= CYCLE_S):
            raise BayAccessError("Unsighted lock, timing or receipt corrupted")
    if len({j["request_id"] for j in ledger["jobs"].values()}) != len(ledger["jobs"]):
        raise BayAccessError("Duplicate fitted airlock cycle request")
    return True


def survey_bay(ledger, bay):
    validate_bay_access(ledger)
    if bay not in {entry[1] for entry in LOCKS.values()}:
        raise BayAccessError("No original rated flywheel service bay")
    out = copy.deepcopy(ledger)
    if bay not in out["surveyed_bays"]:
        out["surveyed_bays"].append(bay)
        out["surveyed_bays"].sort()
    validate_bay_access(out)
    return out


def begin_bay_transit(ledger, *, actor, link, direction, source,
                      destination, request_id):
    validate_bay_access(ledger)
    if not _ref(actor) or link not in LOCKS:
        raise BayAccessError("Real suited worker and original fitted lock required")
    corridor, bay, _ = LOCKS[link]
    origin, dest = ((corridor, bay) if direction == "forward"
                    else (bay, corridor) if direction == "reverse"
                    else (None, None))
    if (bay not in ledger["surveyed_bays"]
            or (source, destination) != (origin, dest)
            or actor in ledger["jobs"]
            or len(ledger["jobs"]) == len(LOCKS)
            or any(j["link"] == link for j in ledger["jobs"].values())
            or not isinstance(request_id, str)
            or re.fullmatch(r"[0-9a-f]{32}", request_id) is None):
        raise BayAccessError("Service airlock occupied, unverified or unready")
    out = copy.deepcopy(ledger)
    out["jobs"][actor] = {
        "link": link, "from": source, "to": destination,
        "direction": direction, "remaining_s": CYCLE_S,
        "request_id": request_id,
    }
    validate_bay_access(out)
    return out


def step_bay_transits(ledger, seconds, *, ready_links):
    validate_bay_access(ledger)
    if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds) or not 0 <= seconds <= MAX_STEP_S
            or not isinstance(ready_links, (set, frozenset))):
        raise BayAccessError("Invalid physical airlock progress sample")
    out = copy.deepcopy(ledger)
    finished = []
    for actor, job in sorted(out["jobs"].items()):
        if job["link"] not in ready_links:
            continue
        job["remaining_s"] = max(0.0, job["remaining_s"] - seconds)
        if job["remaining_s"] <= 1e-8:
            finished.append((actor, copy.deepcopy(job)))
    validate_bay_access(out)
    return out, tuple(finished)


def finish_bay_transit(ledger, *, actor, request_id):
    validate_bay_access(ledger)
    job = ledger["jobs"].get(actor)
    if (job is None or job["request_id"] != request_id
            or job["remaining_s"] > 1e-8):
        raise BayAccessError("Sealed service airlock cycle has not completed")
    out = copy.deepcopy(ledger)
    del out["jobs"][actor]
    out["completed"] += 1
    validate_bay_access(out)
    return out
