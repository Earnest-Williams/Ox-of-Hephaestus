"""G19 fitted EXT-PROP-AFT external nozzle survey and safe EVA work permit.

The original ship has a 120-second external work platform but does not have
a separately authored external propulsion repairable machine identity. This
is therefore an *inspection* and plume-exclusion access mechanism, not a
shortcut to the unknown-atmosphere PROP-SVC room or a fabricated engine.
"""
from __future__ import annotations

import copy
import math
import re

FACE = "EXT-PROP-AFT"
BASE = "EXT-AFT"
LINK = "ACC-EXT-AFT-EXT-PROP-AFT"
STATION = "PROP-CTRL"
GATE_S = 120.0
MAX_SKIN_K = 315.15
MIN_SKIN_K = 180.0
MAX_SURVEY_K = 800.0
MAX_DRIVE_HEAT_KJ = 2_500_000.0


class PlumeAccessError(ValueError):
    pass


def _finite(x, *, minimum=0, maximum=math.inf):
    if (isinstance(x, bool) or not isinstance(x, (float, int))
            or not math.isfinite(x) or not minimum <= x <= maximum):
        raise PlumeAccessError("Unphysical aft plume measurement")
    return float(x)


def _actor(value):
    return isinstance(value, str) and re.fullmatch(r"#[0-9]+", value) is not None


def _signature(motion):
    if not isinstance(motion, dict):
        raise PlumeAccessError("No commissioned ship motion")
    # Both propel/FTL fuel counters preserve a fired-since-survey witness.
    return [
        _finite(motion.get("expended_propellant_kg", 0)),
        _finite(motion.get("expended_ftl_fuel_kg", 0)),
    ]


def initial_propulsion_exterior():
    return {"survey": None, "permit": None,
            "issued": 0, "released": 0, "inspected": 0}


def validate_propulsion_exterior(ledger):
    if not isinstance(ledger, dict) or set(ledger) != {
            "survey", "permit", "issued", "released", "inspected"}:
        raise PlumeAccessError("Unknown original aft plume worksite contract")
    for key in ("issued", "released", "inspected"):
        if type(ledger[key]) is not int or ledger[key] < 0:
            raise PlumeAccessError("Nonphysical propulsion service receipt count")
    if ledger["issued"] - ledger["released"] != int(
            ledger["permit"] is not None):
        raise PlumeAccessError("Lost or fabricated external nozzle work permit")
    survey = ledger["survey"]
    if survey is not None:
        if not isinstance(survey, dict) or set(survey) != {
                "skin_k", "plume_clear", "observed_game_time",
                "fuel_signature"}:
            raise PlumeAccessError("Unrecognised measured exhaust condition")
        _finite(survey["skin_k"], minimum=MIN_SKIN_K, maximum=MAX_SURVEY_K)
        _finite(survey["observed_game_time"])
        if type(survey["plume_clear"]) is not bool or (
                not isinstance(survey["fuel_signature"], list) or
                len(survey["fuel_signature"]) != 2):
            raise PlumeAccessError("Unknown plume clearance or burn signature")
        for x in survey["fuel_signature"]:
            _finite(x)
    permit = ledger["permit"]
    if permit is not None:
        if (not isinstance(permit, dict)
                or set(permit) != {
                    "actor", "issued_game_time", "fuel_signature"}
                or not _actor(permit["actor"])
                or not isinstance(permit["fuel_signature"], list)
                or len(permit["fuel_signature"]) != 2
                or survey is None or not survey["plume_clear"]
                or survey["skin_k"] > MAX_SKIN_K
                or permit["fuel_signature"] != survey["fuel_signature"]):
            raise PlumeAccessError("Unsafe or unowned original nozzle permit")
        _finite(permit["issued_game_time"])
    return True


def survey_propulsion_exterior(ledger, *, temperature_k, plume_clear,
                               motion, game_time):
    validate_propulsion_exterior(ledger)
    if ledger["permit"] is not None or type(plume_clear) is not bool:
        raise PlumeAccessError("Workface occupied or plume clearance not positively attested")
    now = _finite(game_time)
    if (ledger["survey"] is not None and now <
            ledger["survey"]["observed_game_time"]):
        raise PlumeAccessError("Old exhaust survey cannot replace new measurement")
    out = copy.deepcopy(ledger)
    out["survey"] = {
        "skin_k": _finite(
            temperature_k, minimum=MIN_SKIN_K, maximum=MAX_SURVEY_K),
        "plume_clear": plume_clear,
        "observed_game_time": now,
        "fuel_signature": _signature(motion),
    }
    validate_propulsion_exterior(out)
    return out


def propulsion_face_safe(ledger, *, motion, hardware_ready):
    validate_propulsion_exterior(ledger)
    observed = ledger["survey"]
    if observed is None or not observed["plume_clear"] or (
            observed["skin_k"] > MAX_SKIN_K or not hardware_ready):
        return False
    if observed["fuel_signature"] != _signature(motion):
        return False
    for key, needed in (
            ("command", "coast"), ("attitude_command", "hold"),
            ("drive_condition", "inhibited"),
            ("rcs_condition", "inhibited")):
        if motion.get(key) != needed:
            return False
    if motion.get("drive_firing") or motion.get("attitude_firing") or (
            motion.get("ftl_leg") or {}).get("status") == "engaged":
        return False
    if _finite(motion.get("drive_heat_kj", -1)) > MAX_DRIVE_HEAT_KJ:
        return False
    omega = motion.get("angular_velocity_rad_s")
    if (not isinstance(omega, (tuple, list)) or len(omega) != 3
            or any(abs(_finite(v, minimum=-1e30, maximum=1e30)) > 0.0001
                   for v in omega)):
        return False
    return True


def issue_propulsion_permit(ledger, *, actor, game_time,
                            motion, hardware_ready):
    if not _actor(actor) or ledger["permit"] is not None or (
            not propulsion_face_safe(ledger, motion=motion,
                                     hardware_ready=hardware_ready)):
        raise PlumeAccessError("Exhaust is not positively cleared and physically inhibited")
    out = copy.deepcopy(ledger)
    out["permit"] = {
        "actor": actor, "issued_game_time": _finite(game_time),
        "fuel_signature": _signature(motion),
    }
    out["issued"] += 1
    validate_propulsion_exterior(out)
    return out


def inspect_propulsion(ledger, *, actor, motion, hardware_ready):
    if (ledger["permit"] is None or ledger["permit"]["actor"] != actor
            or not propulsion_face_safe(
                ledger, motion=motion, hardware_ready=hardware_ready)):
        raise PlumeAccessError("Only issued suited nozzle work party can inspect safe exterior")
    out = copy.deepcopy(ledger)
    out["inspected"] += 1
    validate_propulsion_exterior(out)
    return out


def release_propulsion_permit(ledger, *, actor, occupied=False,
                              transit_active=False):
    validate_propulsion_exterior(ledger)
    if (ledger["permit"] is None or ledger["permit"]["actor"] != actor
            or occupied or transit_active):
        raise PlumeAccessError("Cannot release nozzle permit with exterior workers or moving suits")
    out = copy.deepcopy(ledger)
    out["permit"] = None
    out["released"] += 1
    validate_propulsion_exterior(out)
    return out
