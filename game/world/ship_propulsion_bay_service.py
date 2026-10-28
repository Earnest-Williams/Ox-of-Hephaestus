"""G19 original PROP-SVC rated-hatch entry, local gas and maintenance permit.

This is the gas previously *unclassified* in the original 48 x 7 x 3.8 m
propulsion bay. A positive first survey discovers existing, isolated gas;
subsequent surveys must agree with that finite ledger, never reset it.
The original ACC-PROP-SVC hatch equalisation tapping can transfer gas from
the real TRUNK-B-AFT pressure cell, with debit/credit of both gas ledgers.
No fictional extra room, main pressure cell, powered airlock or free gas.
"""
from __future__ import annotations

import copy
import math
import re

HATCH = "ACC-PROP-SVC"
FREIGHT_HATCH = "ACC-LOGI-AFT-PROP-SVC"
TRUNK = "TRUNK-B-AFT"
BAY = "PROP-SVC"
TRUNK_ZONE = "PZ-TRUNK-B-AFT"
PANEL = "LP-PROP-SVC"
CONTROLLER = "LCS-PROP"
FEEDER = "ISO-LP-PROP-SVC"
VOLUME_MAX_M3 = 48.0 * 7.0 * 3.8
VOLUME_MIN_M3 = 400.0
R_AIR = 287.05
MAX_DELTA_PA = 2000.0
MAX_BLEED_KG = 20.0
SURVEY_FRESH_S = 600.0
MAX_REPAIR_HEAT_KJ = 2_500_000.0
EPS = 1e-7


class BayAccessError(ValueError):
    """PROP-SVC gas, pressure, machinery and service cannot be proved."""


def _num(x, lo=0.0, hi=math.inf):
    if type(x) not in (int, float) or not math.isfinite(x) or not lo <= x <= hi:
        raise BayAccessError("Unmeasured or unphysical propulsion-bay quantity")
    return float(x)


def _actor(x):
    return isinstance(x, str) and re.fullmatch(r"#[0-9]+", x) is not None


def initial_bay_service():
    return {
        "version": 1, "gas": None,
        "initial_survey_kg": 0.0,
        "trunk_to_bay_kg": 0.0,
        "permit": None, "entries": 0,
        "inspections": 0,
    }


def bay_pressure(gas):
    if gas is None:
        raise BayAccessError("No positive pressure measurement of the original bay")
    return _num(gas["mass_kg"]) * R_AIR * _num(
        gas["temperature_k"], 1.0) / _num(gas["volume_m3"], 1.0)


def _moles_oxygen_pressure(gas):
    mass = gas["mass_kg"]
    o2 = gas["oxygen_kg"] / 0.032
    rest = max(0, mass-gas["oxygen_kg"]) / 0.029
    return bay_pressure(gas)*o2/(o2+rest) if o2+rest else 0


def bay_gas_safe(gas):
    if gas is None:
        return False
    p = bay_pressure(gas)
    return bool(
        80000 <= p <= 120000
        and 16000 <= _moles_oxygen_pressure(gas) <= 26000
        and 278.15 <= gas["temperature_k"] <= 313.15
        and gas["co2_kg"] <= .005 * gas["mass_kg"]
        and gas["smoke_kg"] <= .00001 * gas["mass_kg"])


def validate_bay(ledger):
    if (not isinstance(ledger, dict) or set(ledger) !=
            set(initial_bay_service()) or ledger["version"] != 1
            or type(ledger["entries"]) is not int
            or type(ledger["inspections"]) is not int
            or ledger["entries"] < 0 or ledger["inspections"] < 0):
        raise BayAccessError("Unknown or corrupted fitted PROP-SVC register")
    for k in ("initial_survey_kg", "trunk_to_bay_kg"):
        _num(ledger[k])
    gas = ledger["gas"]
    if gas is None:
        if ledger["permit"] is not None or any(ledger[k] != 0 for k in (
                "initial_survey_kg", "trunk_to_bay_kg", "entries")):
            raise BayAccessError("Unsampled bay has fabricated gas or access")
    else:
        if (not isinstance(gas, dict) or set(gas) != {
                "volume_m3", "mass_kg", "oxygen_kg", "co2_kg",
                "smoke_kg", "temperature_k", "sample_s"}
                or not VOLUME_MIN_M3 <= _num(gas["volume_m3"]) <= VOLUME_MAX_M3
                or not 250 <= _num(gas["temperature_k"]) <= 330):
            raise BayAccessError("Original bay geometry or temperature unverified")
        for k in ("mass_kg", "oxygen_kg", "co2_kg", "smoke_kg", "sample_s"):
            _num(gas[k])
        if (gas["oxygen_kg"]+gas["co2_kg"]+gas["smoke_kg"] >
                gas["mass_kg"] + EPS or
                not math.isclose(
                    ledger["initial_survey_kg"]+ledger["trunk_to_bay_kg"],
                    gas["mass_kg"], abs_tol=1e-5, rel_tol=1e-10)):
            raise BayAccessError("PROP-SVC gas moved without measured hatch transfer")
        if not 0 <= bay_pressure(gas) <= 130000:
            raise BayAccessError("Impossible bay pressure")
    permit = ledger["permit"]
    if permit is not None:
        if (gas is None or not isinstance(permit, dict)
                or set(permit) != {"holder", "issued_s"}
                or not _actor(permit["holder"])):
            raise BayAccessError("Original access permit has no qualified holder")
        _num(permit["issued_s"])
    return True


def survey_existing_gas(ledger, *, volume_m3, pressure_pa,
                        temperature_k, oxygen_mass_fraction,
                        co2_mass_fraction, smoke_mass_fraction,
                        now_s, hatch_closed):
    """Operator physically measures the as-found sealed bay gas once.

    This does *not* move any material from trunk. Later measurements cannot
    rewrite the conserved existing mass, oxygen or temperature behind a repair.
    """
    validate_bay(ledger)
    volume = _num(volume_m3, VOLUME_MIN_M3, VOLUME_MAX_M3)
    pressure = _num(pressure_pa, 0.0, 130000.0)
    temp = _num(temperature_k, 250, 330)
    o2 = _num(oxygen_mass_fraction, 0, 1)
    co2 = _num(co2_mass_fraction, 0, 1)
    smoke = _num(smoke_mass_fraction, 0, 1)
    now = _num(now_s)
    if (not hatch_closed or o2+co2+smoke > 1 or
            ledger["permit"] is not None):
        raise BayAccessError("Bay sensor sampling needs isolated, untouched, closed hatch")
    mass = pressure*volume/(R_AIR*temp)
    result = copy.deepcopy(ledger)
    if result["gas"] is None:
        result["gas"] = {
            "volume_m3": volume, "mass_kg": mass,
            "oxygen_kg": mass*o2, "co2_kg": mass*co2,
            "smoke_kg": mass*smoke, "temperature_k": temp,
            "sample_s": now,
        }
        result["initial_survey_kg"] = mass
    else:
        measured = result["gas"]
        if (not math.isclose(measured["volume_m3"], volume, abs_tol=1e-4)
                or abs(bay_pressure(measured)-pressure) > 150
                or abs(measured["temperature_k"]-temp) > 1
                or abs(measured["oxygen_kg"]/max(measured["mass_kg"], EPS)-o2) > .002
                or abs(measured["co2_kg"]/max(measured["mass_kg"], EPS)-co2) > .002
                or abs(measured["smoke_kg"]/max(measured["mass_kg"], EPS)-smoke) > .00001):
            raise BayAccessError("New gauge does not agree with original finite gas ledger")
        result["gas"]["sample_s"] = now
    validate_bay(result)
    return result


def safe_motion(motion):
    return bool(
        motion and motion.get("command") == "coast"
        and motion.get("attitude_command") == "hold"
        and motion.get("drive_condition") == "inhibited"
        and motion.get("rcs_condition") == "inhibited"
        and not motion.get("drive_firing")
        and not motion.get("attitude_firing")
        and (motion.get("ftl_leg") or {}).get("status") != "engaged"
        and _num(motion.get("drive_heat_kj", 0.0)) <= MAX_REPAIR_HEAT_KJ)


def source_pressure(source):
    return _num(source["mass_kg"])*R_AIR*_num(
        source["temperature_k"], 250, 330)/_num(source["volume_m3"], 1)


def equalize_from_trunk(ledger, *, requested_kg, source,
                        now_s, source_safe, hatch_closed, other_closed):
    """Meter one bounded real hatch bleed from the known pressure cell.

    The source cell's mass/O2/CO2 decrease exactly by the target's gains.
    This first slice only supports CLEAN TRUNK -> LOWER PRESSURE BAY flow;
    venting potentially contaminated bay gas back to crew trunks is forbidden.
    """
    validate_bay(ledger)
    kg = _num(requested_kg, EPS, MAX_BLEED_KG)
    now = _num(now_s)
    if (ledger["gas"] is None or ledger["permit"] is not None
            or not source_safe or not hatch_closed or not other_closed):
        raise BayAccessError("No safe rated hatch bleed to unsurveyed machinery")
    g = ledger["gas"]
    if now < g["sample_s"] or now-g["sample_s"] > SURVEY_FRESH_S:
        raise BayAccessError("Bay gas sample too old for measured equalization")
    src = {k: _num(source[k]) for k in (
        "mass_kg", "oxygen_kg", "co2_kg", "temperature_k", "volume_m3")}
    if src["oxygen_kg"]+src["co2_kg"] > src["mass_kg"]+EPS:
        raise BayAccessError("Source gas composition corrupt")
    before = source_pressure(src)-bay_pressure(g)
    if before <= MAX_DELTA_PA:
        raise BayAccessError("No verified source-to-bay differential for a bleed")
    # Never overshoot matched pressure or deplete source gas.
    equilibrium = before/(R_AIR*(
        src["temperature_k"]/src["volume_m3"] +
        g["temperature_k"]/g["volume_m3"]))
    if kg > equilibrium + 1e-7 or kg >= src["mass_kg"]*.1:
        raise BayAccessError("Bleed requested beyond real differential or source charge")
    moved_o2 = kg*src["oxygen_kg"]/src["mass_kg"]
    moved_co2 = kg*src["co2_kg"]/src["mass_kg"]
    moved = copy.deepcopy(ledger)
    gas = moved["gas"]
    new_mass = gas["mass_kg"]+kg
    gas["temperature_k"] = (
        gas["temperature_k"]*gas["mass_kg"] +
        src["temperature_k"]*kg)/new_mass
    gas["mass_kg"] = new_mass
    gas["oxygen_kg"] += moved_o2
    gas["co2_kg"] += moved_co2
    gas["sample_s"] = now
    moved["trunk_to_bay_kg"] += kg
    src["mass_kg"] -= kg
    src["oxygen_kg"] -= moved_o2
    src["co2_kg"] -= moved_co2
    validate_bay(moved)
    return moved, src


def bay_entry_ready(ledger, *, source_pa, source_safe, motion,
                    feeder_open, hatch_sound, other_closed, now_s,
                    require_permit=True):
    validate_bay(ledger)
    gas=ledger["gas"]
    if gas is None:
        return False
    if (not source_safe or not feeder_open or not hatch_sound
            or not other_closed or not bay_gas_safe(gas)
            or not safe_motion(motion)
            or not math.isfinite(source_pa)
            or abs(source_pa-bay_pressure(gas)) > MAX_DELTA_PA
            or _num(now_s) < gas["sample_s"]):
        return False
    if require_permit:
        return ledger["permit"] is not None
    return _num(now_s)-gas["sample_s"] <= SURVEY_FRESH_S


def permit_entry(ledger, *, worker, now_s):
    validate_bay(ledger)
    if ledger["permit"] is not None or not _actor(worker):
        raise BayAccessError("An original propulsion bay permit is already held")
    result=copy.deepcopy(ledger)
    result["permit"]={"holder":worker,"issued_s":_num(now_s)}
    validate_bay(result)
    return result


def finish_entry(ledger, *, worker):
    validate_bay(ledger)
    if ledger["permit"] is None or ledger["permit"]["holder"] != worker:
        raise BayAccessError("Unpermitted work party crossing")
    result=copy.deepcopy(ledger)
    result["entries"]+=1
    validate_bay(result)
    return result


def inspect_bay(ledger, *, worker):
    """Record an actual physically attended inspection only after outer gates."""
    validate_bay(ledger)
    if ledger["permit"] is None or ledger["permit"]["holder"] != worker:
        raise BayAccessError("An unsuited or unpermitted worker cannot inspect local propulsion")
    result = copy.deepcopy(ledger)
    result["inspections"] += 1
    validate_bay(result)
    return result


def release_entry(ledger, *, worker, hatch_closed, bay_empty,
                  repairs_active):
    validate_bay(ledger)
    if (ledger["permit"] is None or ledger["permit"]["holder"] != worker
            or not hatch_closed or not bay_empty or repairs_active):
        raise BayAccessError("Work party, open hatch or active repair still occupies bay")
    result=copy.deepcopy(ledger)
    result["permit"]=None
    validate_bay(result)
    return result
