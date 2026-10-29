"""G19 four original EVA rail crawlers and drum-inspection robots.

Pure state transition. Authoritative rooms/access/rotor/conditions supplied by
the installed world clock; there is no invented exterior rail or power socket.
A queued rail move takes measured finite time and battery. Loss of drive,
power or track pauses it in place; no teleport/recharge from a software command.
"""
from __future__ import annotations

import copy
import math
import re

CRAWLERS = {"EVA-CRAWLER-1": "EVA-FWD", "EVA-CRAWLER-2": "EVA-AFT"}
ROBOTS = {"DRUM-INSPECT-ROBOT-1": "EVA-FWD",
          "DRUM-INSPECT-ROBOT-2": "EVA-AFT"}
FITTED = {**CRAWLERS, **ROBOTS}
ANCHORS = {"EVA-FWD": "EXT-BOW", "EVA-AFT": "EXT-AFT"}
EXTERIOR = frozenset({"EXT-BOW", "EXT-AFT"})
BROKEN = frozenset({"faulted", "failed", "severed", "jammed", "destroyed"})
TICK_LIMIT_S = 10.0
RAIL_TRAVEL_S = 30.0
AIRLOCK_TRAVEL_S = 45.0
SCAN_S = 20.0
# Game-balance service power rates, not claimed engineering nameplate ratings.
DRIVE_KW = {"crawler": 12.0, "robot": 4.0}
SCAN_KW = 2.0
MAX_BATTERY_KWH = {"crawler": 50.0, "robot": 12.0}
EPS = 1e-8


class MobileExteriorError(ValueError):
    """One original exterior apparatus cannot safely execute its request."""


def _num(x, high=None):
    if (type(x) not in (float, int) or not math.isfinite(x) or x < 0
            or high is not None and x > high):
        raise MobileExteriorError("Invalid finite mobile apparatus quantity")
    return float(x)


def _kind(name):
    if name in CRAWLERS:
        return "crawler"
    if name in ROBOTS:
        return "robot"
    raise MobileExteriorError("Unknown original exterior mobile machine")


def original_routes(reference):
    """Only rated original EVA rail sections, never EVA work platforms."""
    spaces = {x["id"]: x for x in reference["spaces"]}
    routes = {}
    for link in reference["access_links"]:
        if link["kind"] != "eva_rail":
            continue
        start, end = link["from"], link["to"]
        if (start not in spaces or end not in spaces
                or spaces[start].get("pressure_zone") != "VACUUM"
                or spaces[end].get("pressure_zone") != "VACUUM"
                or not start.startswith("EXT-") or not end.startswith("EXT-")):
            raise MobileExteriorError("Unrated or unassigned original rail")
        routes[(start, end)] = link["id"]
        routes[(end, start)] = link["id"]
    if not routes or any(endpoint not in {a for a, _ in routes}
                         for endpoint in ANCHORS.values()):
        raise MobileExteriorError("Original rail lacks a fitted exterior anchor")
    return routes


def _destination_drum(room):
    match = re.fullmatch(r"EXT-DR(0[1-6])-SKIN", room or "")
    return "DR-" + match.group(1) if match else None


def _safe_drum(rotors, room):
    name = _destination_drum(room)
    if name is None:
        return True
    item = rotors.get(name)
    return bool(item and item.get("condition") in {"serviceable", "worn"}
                and item.get("hardlock") and item.get("brake")
                and item.get("target_rpm") == 0 and not item.get("indexing")
                and not item.get("freight_collar")
                and not item.get("passenger_indexer")
                and type(item.get("rpm")) in (float, int)
                and math.isfinite(item["rpm"]) and abs(item["rpm"]) < .001)


def initial_exterior_mobile():
    return {"version": 1,
            "units": {
                name: {"home": home, "position": home, "charge": None,
                       "job": None, "held": False, "fault_latched": False,
                       "distance_sections": 0, "scans": 0,
                       "used_kwh": 0.0, "sample": None, "last_s": None}
                for name, home in FITTED.items()},
            "meter": {"energy_kwh": 0.0, "sections": 0, "scans": 0},
            "last": {"energy_kwh": 0.0, "finished": [], "blocked": []}}


def validate_exterior_mobile(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"version", "units", "meter", "last"}
            or type(ledger["version"]) is not int or ledger["version"] != 1
            or not isinstance(ledger["units"], dict)
            or set(ledger["units"]) != set(FITTED)
            or not isinstance(ledger["meter"], dict)
            or set(ledger["meter"]) != {"energy_kwh", "sections", "scans"}
            or set(ledger["last"]) != {"energy_kwh", "finished", "blocked"}):
        raise MobileExteriorError("Four original mobile machine identities lost")
    consumed = 0.0
    count_sections = count_scans = 0
    for name, row in ledger["units"].items():
        if (not isinstance(row, dict) or set(row) != {
                "home", "position", "charge", "job", "held", "fault_latched",
                "distance_sections", "scans", "used_kwh", "sample", "last_s"}
                or row["home"] != FITTED[name] or type(row["held"]) is not bool
                or type(row["fault_latched"]) is not bool):
            raise MobileExteriorError("Original crawler/robot record corrupt")
        position = row["position"]
        if (not isinstance(position, str) or not position
                or not (position.startswith("EXT-") or position == row["home"])):
            raise MobileExteriorError("Mobile machine escaped fitted site inventory")
        if (type(row["distance_sections"]) is not int
                or row["distance_sections"] < 0
                or type(row["scans"]) is not int or row["scans"] < 0
                or name in CRAWLERS and row["scans"] != 0):
            raise MobileExteriorError("Invalid source-specific travel/scan receipts")
        used = _num(row["used_kwh"])
        charge = row["charge"]
        if charge is None:
            if used or row["distance_sections"] or row["scans"] or row["job"]:
                raise MobileExteriorError("Unsurveyed mobile produced work")
        else:
            if not isinstance(charge, dict) or set(charge) != {
                    "initial_kwh", "remaining_kwh"}:
                raise MobileExteriorError("Missing surveyed battery custody")
            initial = _num(charge["initial_kwh"], MAX_BATTERY_KWH[_kind(name)])
            remaining = _num(charge["remaining_kwh"], initial)
            if initial <= 0 or not math.isclose(initial, used + remaining,
                                               abs_tol=1e-6, rel_tol=1e-9):
                raise MobileExteriorError("Mobile battery not conserved")
        if row["last_s"] is not None:
            _num(row["last_s"])
        elif used:
            raise MobileExteriorError("Powered mobile work has no clock")
        job = row["job"]
        if job is not None:
            if (not isinstance(job, dict) or set(job) != {
                    "kind", "from", "to", "link", "remaining_s", "total_s"}
                    or job["kind"] not in {"move", "scan"}
                    or job["from"] != position):
                raise MobileExteriorError("Invalid original mobile movement job")
            duration = _num(job["total_s"], AIRLOCK_TRAVEL_S)
            remaining = _num(job["remaining_s"], duration)
            if duration <= 0 or remaining <= 0:
                raise MobileExteriorError("Completed mobile job retained as active")
            if job["kind"] == "scan":
                if name not in ROBOTS or job["to"] != position or job["link"] is not None:
                    raise MobileExteriorError("Only original robot may inspect while stopped")
            elif (not isinstance(job["to"], str)
                  or not isinstance(job["link"], str)):
                raise MobileExteriorError("Unmapped mobile traverse")
        sample = row["sample"]
        if sample is not None:
            if name not in ROBOTS or not isinstance(sample, dict) or set(sample) != {
                    "site", "drum", "observed_rpm", "observed_condition",
                    "hardlock", "brake", "sample_s", "evidence"}:
                raise MobileExteriorError("Invented or corrupted remote inspection receipt")
            if sample["site"] != "EXT-" + sample["drum"].replace("DR-", "DR") + "-SKIN":
                raise MobileExteriorError("Remote inspection has wrong fitted skin")
            _num(sample["sample_s"])
            _num(sample["observed_rpm"])
        if job is not None and row["fault_latched"] and not row["held"]:
            raise MobileExteriorError("Faulted actuator still running")
        consumed += used
        count_sections += row["distance_sections"]
        count_scans += row["scans"]
    if (not math.isclose(_num(ledger["meter"]["energy_kwh"]), consumed,
                         abs_tol=1e-6, rel_tol=1e-9)
            or type(ledger["meter"]["sections"]) is not int
            or ledger["meter"]["sections"] != count_sections
            or type(ledger["meter"]["scans"]) is not int
            or ledger["meter"]["scans"] != count_scans
            or not isinstance(ledger["last"]["finished"], list)
            or not isinstance(ledger["last"]["blocked"], list)
            or _num(ledger["last"]["energy_kwh"]) > consumed + EPS):
        raise MobileExteriorError("Mobile fleet meters do not reconcile")
    return True


def survey_exterior_mobile(ledger, name, *, battery_kwh):
    validate_exterior_mobile(ledger)
    if name not in FITTED or ledger["units"][name]["charge"] is not None:
        raise MobileExteriorError("One-time original battery survey required")
    charge = _num(battery_kwh, MAX_BATTERY_KWH[_kind(name)])
    if not charge:
        raise MobileExteriorError("Cannot claim unmeasured discharged mobile")
    out = copy.deepcopy(ledger)
    out["units"][name]["charge"] = {
        "initial_kwh": charge, "remaining_kwh": charge}
    validate_exterior_mobile(out)
    return out


def mobile_move(ledger, name, value, *, routes, rail_access, rotors,
                lock_ready, motion_safe):
    """One local command starts timed motion or inspected output, never teleports."""
    validate_exterior_mobile(ledger)
    if name not in FITTED:
        raise MobileExteriorError("No original mobile exterior machine")
    row = ledger["units"][name]
    if row["charge"] is None:
        raise MobileExteriorError("Original drive battery not attested")
    out = copy.deepcopy(ledger)
    row = out["units"][name]
    if value in {"hold", "continue"}:
        if row["job"] is None:
            raise MobileExteriorError("No running work to hold or resume")
        if value == "continue" and row["fault_latched"]:
            raise MobileExteriorError("Physical fault must be serviced before restart")
        row["held"] = value == "hold"
    elif value == "reset":
        if not row["fault_latched"]:
            raise MobileExteriorError("No latched mobile fault")
        if row["job"] is None:
            raise MobileExteriorError("No interrupted mobile work")
        row["fault_latched"] = False
        row["held"] = True  # Manual continue, NEVER automatic startup.
    else:
        if row["job"] is not None or row["fault_latched"]:
            raise MobileExteriorError("Finish or secure existing mobile job first")
        if not motion_safe:
            raise MobileExteriorError("Ship must coast with fixed attitude for exposed rail work")
        if row["charge"]["remaining_kwh"] <= EPS:
            raise MobileExteriorError("Original autonomous drive battery exhausted")
        position = row["position"]
        home = row["home"]
        anchor = ANCHORS[home]
        if value == "launch":
            if position != home or not lock_ready.get(home):
                raise MobileExteriorError("A genuine pumped-down outer lock is required")
            to, link, seconds = anchor, "ACC-EVA-" + home[-3:] + "-EXT", AIRLOCK_TRAVEL_S
        elif value == "dock":
            if position != anchor or not lock_ready.get(home):
                raise MobileExteriorError("Dock only through own exposed and evacuated EVA lock")
            to, link, seconds = home, "ACC-EVA-" + home[-3:] + "-EXT", AIRLOCK_TRAVEL_S
        elif value.startswith("move:"):
            to = value.partition(":")[2]
            link = routes.get((position, to))
            if position == home or link is None or not rail_access.get(link):
                raise MobileExteriorError("Requested hop is not an actual live fitted EVA rail")
            if not _safe_drum(rotors, to):
                raise MobileExteriorError("Rotating drum or unsecured rotor forbids rail approach")
            seconds = RAIL_TRAVEL_S
        elif value == "scan" and name in ROBOTS:
            drum = _destination_drum(position)
            if drum is None or not _safe_drum(rotors, position):
                raise MobileExteriorError("Inspection requires a stopped and hardlocked actual drum skin")
            to, link, seconds = position, None, SCAN_S
        else:
            raise MobileExteriorError("Unsupported fitted mobile operation")
        required_kwh = ((SCAN_KW if value == "scan" else DRIVE_KW[_kind(name)])
                        * seconds / 3600.0)
        if row["charge"]["remaining_kwh"] + EPS < required_kwh:
            raise MobileExteriorError("Insufficient battery to finish intended operation")
        row["held"] = False
        row["job"] = {"kind": "scan" if value == "scan" else "move",
                      "from": position, "to": to, "link": link,
                      "total_s": seconds, "remaining_s": seconds}
    validate_exterior_mobile(out)
    return out


def step_exterior_mobile(ledger, seconds, *, now_s, equipment, routes,
                         rail_access, lock_ready, rotors, motion_safe):
    """A real tick spends original battery and advances only supported jobs."""
    validate_exterior_mobile(ledger)
    dt, now = _num(seconds, TICK_LIMIT_S), _num(now_s)
    if dt <= 0:
        raise MobileExteriorError("Clock must advance before mobile hardware")
    out = copy.deepcopy(ledger)
    last = {"energy_kwh": 0.0, "finished": [], "blocked": []}
    for name, original_home in FITTED.items():
        row = out["units"][name]
        if row["last_s"] is not None and now < row["last_s"] + dt - EPS:
            raise MobileExteriorError("Mobile tick replayed")
        row["last_s"] = now
        job = row["job"]
        if job is None:
            continue
        source = equipment.get(name)
        if source is None or source.space_id != original_home:
            raise MobileExteriorError("Original crawler or robot record moved")
        if source.condition in BROKEN:
            row["fault_latched"] = row["held"] = True
            last["blocked"].append(name + ":fault")
            continue
        if row["held"] or row["fault_latched"]:
            last["blocked"].append(name + ":held")
            continue
        if not motion_safe:
            last["blocked"].append(name + ":ship_motion")
            continue
        if job["kind"] == "scan":
            if not _safe_drum(rotors, job["from"]):
                last["blocked"].append(name + ":rotor")
                continue
            power_kw = SCAN_KW
        else:
            if job["from"] == original_home or job["to"] == original_home:
                if not lock_ready.get(original_home):
                    last["blocked"].append(name + ":airlock")
                    continue
            elif (routes.get((job["from"], job["to"])) != job["link"]
                  or not rail_access.get(job["link"])
                  or not _safe_drum(rotors, job["to"])):
                last["blocked"].append(name + ":rail")
                continue
            power_kw = DRIVE_KW[_kind(name)]
        charged = row["charge"]
        take = min(dt, job["remaining_s"],
                   charged["remaining_kwh"] * 3600.0 / power_kw)
        if take <= EPS:
            last["blocked"].append(name + ":battery")
            continue
        expense = take * power_kw / 3600.0
        charged["remaining_kwh"] = max(0.0, charged["remaining_kwh"] - expense)
        row["used_kwh"] += expense
        last["energy_kwh"] += expense
        job["remaining_s"] -= take
        if job["remaining_s"] <= EPS:
            row["job"] = None
            if job["kind"] == "scan":
                drum = _destination_drum(row["position"])
                sample = rotors[drum]
                row["sample"] = {
                    "site": row["position"], "drum": drum,
                    "observed_rpm": float(sample["rpm"]),
                    "observed_condition": sample["condition"],
                    "hardlock": bool(sample["hardlock"]),
                    "brake": bool(sample["brake"]),
                    "sample_s": now,
                    "evidence": "observed_existing_rotor_telemetry_at_skin",
                }
                row["scans"] += 1
                out["meter"]["scans"] += 1
            else:
                row["position"] = job["to"]
                row["distance_sections"] += 1
                out["meter"]["sections"] += 1
            last["finished"].append(name)
    out["meter"]["energy_kwh"] += last["energy_kwh"]
    out["last"] = last
    validate_exterior_mobile(out)
    return out
