"""G19 finite crew transfers through *installed* indexed rotary mechanisms.

The eight existing rated access links, two independent HAB indexer stations
and six drum personnel carriers are the only supported links. Persistent job
state belongs to the canonical physics clock, never to a character's intent.
This pure module neither creates rooms nor moves characters or gas.
"""
from __future__ import annotations

import copy
import math
import re

BROKEN = frozenset({"faulted", "failed", "destroyed", "severed", "jammed"})
MAX_TICK_S = 60.0
PRESSURE_DELTA_PA = 2000.0


class IndexedTransferError(ValueError):
    """Invalid indexed personnel machinery state or transfer order."""


def link_contract(link_id):
    if isinstance(link_id, str) and re.fullmatch(
            r"ACC-DR-0[1-6]-LOCK-ROT", link_id):
        drum = link_id[4:9]
        return {
            "link": link_id, "rotor": drum,
            "from": drum + "-SERVICE-LOCK", "to": drum + "-HUB",
            "fixed_hatch": "ACC-" + drum + "-LOCK-FIX",
            "station": None, "seconds": 180.0,
            "hardware": (drum + "-PERSONNEL-INDEXER", drum + "-ROT-PWR"),
        }
    if link_id in {"ACC-IX-A-ROT", "ACC-IX-B-ROT"}:
        station = link_id[7]
        return {
            "link": link_id, "rotor": "HAB",
            "from": "IX-" + station + "-CAPSULE",
            "to": "IX-" + station + "-ROT-VEST",
            "fixed_hatch": "ACC-IX-" + station + "-FIX",
            "station": station, "seconds": 300.0,
            "hardware": tuple("IX-" + station + "-" + suffix for suffix in (
                "DRIVE", "CARRIER", "FIXED-COLLAR", "ROT-COLLAR")),
        }
    raise IndexedTransferError("No installed indexed personnel mechanism at this access")


def initial_personnel_transfers():
    return {"jobs": {}, "completed": 0, "aborted": 0}


def validate_personnel_transfers(value):
    if not isinstance(value, dict) or set(value) != {"jobs", "completed", "aborted"}:
        raise IndexedTransferError("Uncommissioned or corrupt transfer state")
    if not isinstance(value["jobs"], dict) or len(value["jobs"]) > 7:
        raise IndexedTransferError("Too many concurrent installed indexers")
    for key in ("completed", "aborted"):
        if (isinstance(value[key], bool)
                or not isinstance(value[key], int) or value[key] < 0):
            raise IndexedTransferError("Invalid transfer counter")
    actors = set()
    for rotor, job in value["jobs"].items():
        if not isinstance(job, dict) or set(job) != {
                "link", "rotor", "from", "to", "actor", "request_id",
                "remaining_s", "total_s"}:
            raise IndexedTransferError("Incomplete physical transfer job")
        contract = link_contract(job["link"])
        if rotor != contract["rotor"] or job["rotor"] != rotor:
            raise IndexedTransferError("Indexed transfer assigned wrong rotor")
        if {job["from"], job["to"]} != {contract["from"], contract["to"]}:
            raise IndexedTransferError("Uninstalled transfer endpoint")
        if (not isinstance(job["actor"], str)
                or re.fullmatch(r"#[0-9]+", job["actor"]) is None
                or job["actor"] in actors):
            raise IndexedTransferError("Crew carrier allocation duplicated")
        actors.add(job["actor"])
        if (not isinstance(job["request_id"], str) or re.fullmatch(
                r"[0-9a-f]{32}", job["request_id"]) is None):
            raise IndexedTransferError("Transfer has no valid unique request")
        for name in ("remaining_s", "total_s"):
            x = job[name]
            if isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x):
                raise IndexedTransferError("Nonphysical transfer interval")
        if (not 0 <= job["remaining_s"] <= job["total_s"]
                or job["total_s"] != contract["seconds"]):
            raise IndexedTransferError("Unrated transfer duration")
    return True


def begin_personnel_transfer(transfers, *, link, actor, origin, destination, request_id):
    """Queue one worker at an already verified sealed/captured rotary link."""
    validate_personnel_transfers(transfers)
    contract = link_contract(link)
    if (origin, destination) not in {
            (contract["from"], contract["to"]),
            (contract["to"], contract["from"])}:
        raise IndexedTransferError("Worker cannot board from another compartment")
    if contract["rotor"] in transfers["jobs"] or any(
            j["actor"] == actor for j in transfers["jobs"].values()):
        raise IndexedTransferError("Carrier occupied or worker already transferring")
    result = copy.deepcopy(transfers)
    result["jobs"][contract["rotor"]] = {
        "link": link, "rotor": contract["rotor"], "from": origin,
        "to": destination, "actor": actor, "request_id": request_id,
        "remaining_s": contract["seconds"], "total_s": contract["seconds"],
    }
    validate_personnel_transfers(result)
    return result


def step_personnel_transfers(transfers, seconds, *, ready_links):
    """Advance *only* mechanically proved links; return zero-time finish candidates."""
    validate_personnel_transfers(transfers)
    if (isinstance(seconds, bool) or not isinstance(seconds, (float, int))
            or not math.isfinite(seconds) or not 0 <= seconds <= MAX_TICK_S):
        raise IndexedTransferError("Invalid bounded transfer clock step")
    result = copy.deepcopy(transfers)
    ready = []
    for rotor, job in sorted(result["jobs"].items()):
        if job["link"] not in ready_links:
            continue
        job["remaining_s"] = max(0.0, job["remaining_s"] - seconds)
        if job["remaining_s"] <= 1e-8:
            ready.append(copy.deepcopy(job))
    validate_personnel_transfers(result)
    return result, tuple(ready)


def finish_personnel_transfer(transfers, *, rotor, request_id, aborted=False):
    validate_personnel_transfers(transfers)
    job = transfers["jobs"].get(rotor)
    if not job or job["request_id"] != request_id:
        raise IndexedTransferError("No matching live transfer to complete")
    if not aborted and job["remaining_s"] > 1e-8:
        raise IndexedTransferError("Transit is still moving")
    result = copy.deepcopy(transfers)
    del result["jobs"][rotor]
    result["aborted" if aborted else "completed"] += 1
    validate_personnel_transfers(result)
    return result


def indexed_mechanism_ready(link, *, rotors, equipment, access,
                            pressure, room_zones, pressure_safe, powered):
    """Conservative *live* check: real capture, intact gear and matched air.

    The double pressure doors stay physically closed during carriage motion.
    The fixed-end hatch must be shut, so the 180/300-second transfer cannot
    directly open the station to an uncontrolled second pressure cell.
    """
    spec = link_contract(link)
    door = access.get(link)
    fixed = access.get(spec["fixed_hatch"])
    if not door or not fixed or not powered:
        return False
    if (door.condition in BROKEN or fixed.condition in BROKEN
            or door.reference.get("kind") != "indexed_rotary_transfer"
            or door.reference.get("pressure_boundary") is not True
            or door.reference.get("from") != spec["from"]
            or door.reference.get("to") != spec["to"]
            or door.reference.get("traverse_time_s") != spec["seconds"]
            or door.setting != "closed" or fixed.setting != "closed"):
        return False
    if any(equipment.get(key) is None or equipment[key].condition in BROKEN
           for key in spec["hardware"]):
        return False
    rotor = rotors.get(spec["rotor"])
    if not rotor or rotor.get("condition") not in {"serviceable", "worn"}:
        return False
    phase = rotor.get("phase_rad")
    if (isinstance(phase, bool) or not isinstance(phase, (int, float))
            or not math.isfinite(phase)):
        return False
    phase %= 2 * math.pi
    if not (rotor.get("passenger_indexer")
            and rotor.get("passenger_station") == spec["station"]
            and rotor.get("hardlock") and rotor.get("brake")
            and not rotor.get("freight_collar") and not rotor.get("indexing")
            and rotor.get("target_rpm") == 0
            and abs(rotor.get("rpm", 1.0)) < 0.001
            and min(phase, 2 * math.pi - phase) < 0.01):
        return False
    a_zone = room_zones.get(spec["from"])
    b_zone = room_zones.get(spec["to"])
    if (not isinstance(a_zone, str) or not a_zone.startswith("PZ-")
            or not isinstance(b_zone, str) or not b_zone.startswith("PZ-")
            or a_zone not in pressure or b_zone not in pressure):
        return False
    a, b = pressure[a_zone], pressure[b_zone]
    if not pressure_safe(a) or not pressure_safe(b):
        return False
    def pascal(cell):
        d = cell.details
        return cell.quantity * 287.05 * d["temperature_k"] / d["gas_volume_m3"]
    pa, pb = pascal(a), pascal(b)
    return (math.isfinite(pa) and math.isfinite(pb)
            and abs(pa - pb) <= PRESSURE_DELTA_PA)
