"""G19 six fitted exterior radiator work pads: temperature and service custody.

This is a bounded game-world skin-temperature approximation, NOT a second
coolant energy account. Heat rejection continues in the original HT/LT
ship machinery; the skin state models delayed thermal access after shutdown.
No radiator valve or new exterior site is invented.
"""
from __future__ import annotations

import copy
import math
import re

RADIATORS = {
    **{f"RAD-LT-{n}": {
        "face": f"EXT-RAD-LT-{n}",
        "station": "ROTARY-UTIL-A" if n <= 2 else "ROTARY-UTIL-B",
        "isolation": ("ISO-LT-ROT-A", "ISO-LT-ROT-B"),
        "near_rotors": ("DR-03", "DR-04"),
        "hot_k": 358.15,
    } for n in range(1, 5)},
    **{f"RAD-HT-{n}": {
        "face": f"EXT-RAD-HT-{n}", "station": "THERM-HT",
        "isolation": (f"ISO-RAD-HT-{n}",),
        "near_rotors": ("DR-06",), "hot_k": 523.15,
    } for n in (1, 2)},
}
FACES = {s["face"]: k for k, s in RADIATORS.items()}
MAX_SKIN_K = 315.15  # 42 C, a deliberate suited-work threshold
SURVEY_MIN_K, SURVEY_MAX_K = 180.0, 700.0
VACUUM_BALANCE_K = 235.0
THERMAL_RESPONSE_S = 1500.0


class ExteriorRadiatorError(ValueError):
    pass


def _read(row, key, default=None):
    return row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)


def _number(x, lower=0.0, upper=float("inf")):
    if (isinstance(x, bool) or not isinstance(x, (int, float))
            or not math.isfinite(x) or not lower <= x <= upper):
        raise ExteriorRadiatorError("Unphysical external radiator measurement")
    return float(x)


def _worker(x):
    return isinstance(x, str) and re.fullmatch(r"#[0-9]+", x) is not None


def initial_exterior_radiators():
    return {
        "faces": {key: {"skin_k": None, "sample_game_time": None}
                  for key in RADIATORS},
        "permits": {}, "issued": 0, "released": 0, "ticks": 0,
    }


def validate_exterior_radiators(ledger):
    if not isinstance(ledger, dict) or set(ledger) != {
            "faces", "permits", "issued", "released", "ticks"}:
        raise ExteriorRadiatorError("Unknown commissioned radiator work ledger")
    if (not isinstance(ledger["faces"], dict)
            or set(ledger["faces"]) != set(RADIATORS)
            or not isinstance(ledger["permits"], dict)
            or not set(ledger["permits"]) <= set(RADIATORS)):
        raise ExteriorRadiatorError("Exterior radiator identities changed")
    for key in ("issued", "released", "ticks"):
        if type(ledger[key]) is not int or ledger[key] < 0:
            raise ExteriorRadiatorError("Invalid thermal survey counter")
    if ledger["issued"] - ledger["released"] != len(ledger["permits"]):
        raise ExteriorRadiatorError("Exterior work permit lost or duplicated")
    for key, value in ledger["faces"].items():
        if not isinstance(value, dict) or set(value) != {
                "skin_k", "sample_game_time"}:
            raise ExteriorRadiatorError("Incomplete local radiator temperature sample")
        if value["skin_k"] is None:
            if value["sample_game_time"] is not None:
                raise ExteriorRadiatorError("Temperature not sampled at an actual time")
        else:
            _number(value["skin_k"], SURVEY_MIN_K, SURVEY_MAX_K)
            _number(value["sample_game_time"])
    for key, item in ledger["permits"].items():
        if (not isinstance(item, dict)
                or set(item) != {"issuer", "face", "station", "issued_game_time"}
                or not _worker(item["issuer"])
                or item["face"] != RADIATORS[key]["face"]
                or item["station"] != RADIATORS[key]["station"]):
            raise ExteriorRadiatorError("Unowned or fictitious radiator service permit")
        _number(item["issued_game_time"])
    return True


def survey_skin(ledger, radiator, *, temp_k, game_time):
    """Operator attests temperature from actual local instrumentation."""
    validate_exterior_radiators(ledger)
    if radiator not in RADIATORS or radiator in ledger["permits"]:
        raise ExteriorRadiatorError("Unknown or occupied external radiator face")
    temperature = _number(temp_k, SURVEY_MIN_K, SURVEY_MAX_K)
    now = _number(game_time)
    previous = ledger["faces"][radiator]["sample_game_time"]
    if previous is not None and now < previous:
        raise ExteriorRadiatorError("Older observation cannot overwrite a newer sample")
    out = copy.deepcopy(ledger)
    out["faces"][radiator] = {
        "skin_k": temperature, "sample_game_time": now}
    validate_exterior_radiators(out)
    return out


def step_skins(ledger, seconds, *, hot_radiators):
    """Thermal inertia only; original ship cooling owns all heat balances.

    Active circuits drive their radiator surfaces toward the working
    temperature. Completely isolated surfaces approach a passive balance.
    Unknown surveys remain unknown, rather than magically cooling to safe.
    """
    validate_exterior_radiators(ledger)
    dt = _number(seconds, 0, 60)
    if not isinstance(hot_radiators, (set, frozenset)) or (
            not hot_radiators <= set(RADIATORS)):
        raise ExteriorRadiatorError("Radiator thermal activity not sourced from fitted plant")
    out = copy.deepcopy(ledger)
    fraction = 1 - math.exp(-dt / THERMAL_RESPONSE_S)
    for key, face in out["faces"].items():
        if face["skin_k"] is None:
            continue
        goal = (RADIATORS[key]["hot_k"] if key in hot_radiators
                else VACUUM_BALANCE_K)
        face["skin_k"] += (goal - face["skin_k"]) * fraction
        # Sensor time is an original attestation; do not synthesize a new
        # operator measurement for every passive temperature integration.
    out["ticks"] += 1
    validate_exterior_radiators(out)
    return out


def _rotor_parked(rotors, name):
    row = rotors.get(name)
    return bool(
        row and _read(row, "condition") in {"serviceable", "worn"}
        and _read(row, "hardlock") and _read(row, "brake")
        and _read(row, "target_rpm") == 0
        and isinstance(_read(row, "rpm"), (int, float))
        and not isinstance(_read(row, "rpm"), bool)
        and math.isfinite(_read(row, "rpm"))
        and abs(_read(row, "rpm")) < 0.001
        and not _read(row, "indexing") and not _read(row, "freight_collar")
        and not _read(row, "passenger_indexer"))


def isolated_hardware(radiator, *, isolators, equipment):
    if radiator not in RADIATORS:
        return False
    spec = RADIATORS[radiator]
    for name in spec["isolation"]:
        row = isolators.get(name)
        if (row is None or _read(row, "condition") != "serviceable"
                or _read(row, "setting") != "closed"):
            return False
    # LT has no individually fitted wing valve. This is a full-plant
    # maintenance shutdown at BOTH original rotary-LT manifold isolators.
    if radiator.startswith("RAD-LT-"):
        plant = equipment.get("LT-PLANT")
        if plant is None or _read(plant, "condition") != "serviceable":
            return False
        details = _read(plant, "details", {})
        if (details.get("physics_online") is not False
                or details.get("physics_commanded_on") is not False):
            return False
    return True


def work_face_safe(ledger, radiator, *, isolators, equipment,
                   motion, rotors, require_permit=False):
    validate_exterior_radiators(ledger)
    if radiator not in RADIATORS or not isinstance(motion, dict):
        return False
    if require_permit and radiator not in ledger["permits"]:
        return False
    measured = ledger["faces"][radiator]["skin_k"]
    if measured is None or measured > MAX_SKIN_K:
        return False
    if not isolated_hardware(
            radiator, isolators=isolators, equipment=equipment):
        return False
    if (motion.get("command") != "coast"
            or motion.get("attitude_command") != "hold"
            or motion.get("drive_firing") is True
            or (motion.get("ftl_leg") or {}).get("status") == "engaged"):
        return False
    spin = motion.get("angular_velocity_rad_s")
    if (not isinstance(spin, (list, tuple)) or len(spin) != 3
            or any(isinstance(x, bool) or not isinstance(x, (int, float))
                   or not math.isfinite(x) or abs(x) > 0.0001
                   for x in spin)):
        return False
    return all(_rotor_parked(rotors, name)
               for name in RADIATORS[radiator]["near_rotors"])


def issue_service(ledger, *, radiator, actor, game_time):
    validate_exterior_radiators(ledger)
    if radiator not in RADIATORS or radiator in ledger["permits"] or (
            not _worker(actor)):
        raise ExteriorRadiatorError("Exclusive original radiator face already occupied")
    now = _number(game_time)
    if (ledger["faces"][radiator]["skin_k"] is None
            or ledger["faces"][radiator]["skin_k"] > MAX_SKIN_K):
        raise ExteriorRadiatorError("Hot or unsurveyed exterior radiator")
    out = copy.deepcopy(ledger)
    spec = RADIATORS[radiator]
    out["permits"][radiator] = {
        "issuer": actor, "face": spec["face"], "station": spec["station"],
        "issued_game_time": now}
    out["issued"] += 1
    validate_exterior_radiators(out)
    return out


def release_service(ledger, *, radiator, actor, occupied=False,
                    repair_active=False, transit_active=False):
    validate_exterior_radiators(ledger)
    permit = ledger["permits"].get(radiator)
    if (permit is None or permit["issuer"] != actor or occupied
            or transit_active or repair_active):
        raise ExteriorRadiatorError(
            "Original radiator work face remains occupied, in transit or under repair")
    out = copy.deepcopy(ledger)
    del out["permits"][radiator]
    out["released"] += 1
    validate_exterior_radiators(out)
    return out
