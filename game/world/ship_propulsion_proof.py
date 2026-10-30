"""Original main-drive witness: actual burn and delta-v, not an ON flag.

Physical drive operations remain in continuous_ship_physics. This ledger
only records a signed local witness of a real subsequent drive burn. It
never commands thrust, mints propellant or licenses unsafe restart.
"""
from __future__ import annotations

import copy
import math

class DriveProofError(ValueError):
    pass

def _num(n):
    if type(n) not in (int, float) or not math.isfinite(n) or n < 0:
        raise DriveProofError("Unmeasured physical main-drive quantity")
    return float(n)

def _vector(v):
    if not isinstance(v, (tuple, list)) or len(v) != 3:
        raise DriveProofError("Missing three-axis inertial velocity")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in v):
        raise DriveProofError("Invalid measured inertial velocity")
    return [float(x) for x in v]

def _sample(motion, game_time):
    if not isinstance(motion, dict):
        raise DriveProofError("No installed real ship motion state")
    return {"elapsed_s": _num(game_time),
            "spent_kg": _num(motion["expended_propellant_kg"]),
            "velocity_m_s": _vector(motion["velocity_m_s"])}

def initial_drive_proof():
    return {"pending": None, "last_verified": None, "completed": 0}

def validate_drive_proof(ledger):
    if (not isinstance(ledger, dict) or set(ledger) !=
            {"pending", "last_verified", "completed"}
            or type(ledger["completed"]) is not int or ledger["completed"] < 0):
        raise DriveProofError("Missing physical drive witness history")
    for key in ("pending", "last_verified"):
        v = ledger[key]
        if v is None:
            continue
        if (not isinstance(v, dict) or
                set(v) != ({"actor", "sample"} if key == "pending" else
                            {"actor", "before", "after", "delta_v_m_s", "propellant_kg"})):
            raise DriveProofError("Invalid signed propulsion proof")
        if not isinstance(v["actor"], str) or not v["actor"].startswith("#"):
            raise DriveProofError("Unidentified witness")
        samples = [v["sample"]] if key == "pending" else [v["before"], v["after"]]
        for sample in samples:
            if not isinstance(sample, dict) or set(sample) != {
                    "elapsed_s", "spent_kg", "velocity_m_s"}:
                raise DriveProofError("Incomplete measured burn source")
            _num(sample["elapsed_s"])
            _num(sample["spent_kg"])
            _vector(sample["velocity_m_s"])
        if key == "last_verified":
            if _num(v["delta_v_m_s"]) <= 0 or _num(v["propellant_kg"]) <= 0:
                raise DriveProofError("No positive mechanical output")
    return True

def start_drive_proof(ledger, *, actor, motion, game_time):
    validate_drive_proof(ledger)
    if ledger["pending"] is not None or motion.get("command") != "coast" or (
            motion.get("drive_condition") != "operational" or motion.get("drive_firing")
            or (motion.get("ftl_leg") or {}).get("status") == "engaged"):
        raise DriveProofError("Start the local witness with a released but coasting drive")
    result = copy.deepcopy(ledger)
    result["pending"] = {"actor": actor, "sample": _sample(motion, game_time)}
    validate_drive_proof(result)
    return result

def verify_drive_proof(ledger, *, actor, motion, game_time):
    validate_drive_proof(ledger)
    prior = ledger["pending"]
    if (prior is None or prior["actor"] != actor or
            motion.get("command") != "coast" or motion.get("drive_firing")
            or motion.get("drive_condition") != "operational"):
        raise DriveProofError("No matching completed, safed local engine run")
    now = _sample(motion, game_time)
    old = prior["sample"]
    delta_time = now["elapsed_s"] - old["elapsed_s"]
    delta_prop = now["spent_kg"] - old["spent_kg"]
    delta_v = math.sqrt(sum((a-b)**2 for a,b in zip(
        now["velocity_m_s"],old["velocity_m_s"])))
    if not 0 < delta_time <= 3600 or delta_prop <= 0 or delta_v <= 1e-9:
        raise DriveProofError("Real elapsed burn, expended propellant and delta-v required")
    result = copy.deepcopy(ledger)
    result["pending"] = None
    result["last_verified"] = {
        "actor": actor, "before": old, "after": now,
        "delta_v_m_s": delta_v, "propellant_kg": delta_prop}
    result["completed"] += 1
    validate_drive_proof(result)
    return result
