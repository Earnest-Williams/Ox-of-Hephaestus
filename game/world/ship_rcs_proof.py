"""Signed positive mechanical output proof of the existing original RCS.

The real ship's attitude physics already spends finite reaction mass and
changes measured angular velocity. This is only an attended before/after
witness, not a thruster command, free reaction mass or new subsystem.
"""
from __future__ import annotations

import copy
import math
import re


class RCSProofError(ValueError):
    pass


def _number(x):
    if type(x) not in (int, float) or not math.isfinite(x) or x < 0:
        raise RCSProofError("Unmeasured or negative reaction-control quantity")
    return float(x)


def _vector(v):
    if (not isinstance(v, (list, tuple)) or len(v) != 3
            or any(type(x) not in (int, float) or not math.isfinite(x)
                   for x in v)):
        raise RCSProofError("Unknown three-axis inertial angular rate")
    return [float(x) for x in v]


def _sample(motion, now_s):
    if not isinstance(motion, dict):
        raise RCSProofError("No real installed attitude measurement")
    return {
        "time_s": _number(now_s),
        "spent_reaction_kg": _number(motion["expended_propellant_kg"]),
        "angular_velocity_rad_s": _vector(motion["angular_velocity_rad_s"]),
    }


def initial_rcs_proof():
    return {"pending": None, "last_verified": None, "completed": 0}


def validate_rcs_proof(ledger):
    if (not isinstance(ledger, dict) or
            set(ledger) != {"pending", "last_verified", "completed"}
            or type(ledger["completed"]) is not int or
            ledger["completed"] < 0):
        raise RCSProofError("Unknown original RCS witness register")
    for key in ("pending", "last_verified"):
        rec = ledger[key]
        if rec is None:
            continue
        fields = ({"actor", "sample"} if key == "pending" else
                  {"actor", "before", "after", "delta_omega_rad_s", "spent_kg"})
        if (not isinstance(rec, dict) or set(rec) != fields or
                not isinstance(rec["actor"], str) or
                re.fullmatch(r"#[0-9]+", rec["actor"]) is None):
            raise RCSProofError("Unauthenticated RCS field observation")
        samples = [rec["sample"]] if key == "pending" else [
            rec["before"], rec["after"]]
        for sample in samples:
            if not isinstance(sample, dict) or set(sample) != {
                    "time_s", "spent_reaction_kg", "angular_velocity_rad_s"}:
                raise RCSProofError("Incomplete actual RCS motion source")
            _number(sample["time_s"])
            _number(sample["spent_reaction_kg"])
            _vector(sample["angular_velocity_rad_s"])
        if key == "last_verified" and (
                _number(rec["delta_omega_rad_s"]) <= 0 or
                _number(rec["spent_kg"]) <= 0):
            raise RCSProofError("No positive RCS torque and fuel expenditure")
    return True


def _safed(motion):
    return bool(
        isinstance(motion, dict) and
        motion.get("command") == "coast" and
        motion.get("attitude_command") == "hold" and
        motion.get("rcs_condition") == "operational" and
        motion.get("drive_condition") == "operational" and
        not motion.get("drive_firing") and
        not motion.get("attitude_firing") and
        (motion.get("ftl_leg") or {}).get("status") != "engaged")


def start_rcs_proof(ledger, *, actor, motion, game_time):
    validate_rcs_proof(ledger)
    if ledger["pending"] is not None or not _safed(motion) or (
            not isinstance(actor, str) or
            re.fullmatch(r"#[0-9]+", actor) is None):
        raise RCSProofError("Begin a physically coasting, released and quiet RCS witness")
    result = copy.deepcopy(ledger)
    result["pending"] = {"actor": actor, "sample": _sample(motion, game_time)}
    validate_rcs_proof(result)
    return result


def verify_rcs_proof(ledger, *, actor, motion, game_time):
    validate_rcs_proof(ledger)
    record = ledger["pending"]
    if record is None or record["actor"] != actor or not _safed(motion):
        raise RCSProofError("No matched complete and returned-to-hold attitude run")
    current = _sample(motion, game_time)
    previous = record["sample"]
    elapsed = current["time_s"] - previous["time_s"]
    fuel = current["spent_reaction_kg"] - previous["spent_reaction_kg"]
    delta_omega = math.sqrt(sum((a-b)**2 for a, b in zip(
        current["angular_velocity_rad_s"],
        previous["angular_velocity_rad_s"])))
    if not 0 < elapsed <= 3600 or fuel <= 0 or delta_omega <= 1e-12:
        raise RCSProofError("Actual expended reaction mass and measured three-axis angular acceleration required")
    result = copy.deepcopy(ledger)
    result["pending"] = None
    result["last_verified"] = {
        "actor": actor, "before": previous, "after": current,
        "delta_omega_rad_s": delta_omega, "spent_kg": fuel,
    }
    result["completed"] += 1
    validate_rcs_proof(result)
    return result
