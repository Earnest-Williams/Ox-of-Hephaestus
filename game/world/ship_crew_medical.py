"""Finite, located medical care for the installed HAB-04 clinic.

The original HAB-04-MED-PHARM and HAB-04-MED-TREAT are different real
rooms. Attested pharmacy stock has to be physically carried to treatment.
The installed clock owns patient presence, air, electricity and elapsed time.
"""
from __future__ import annotations

import copy
import math
import re

from world.ship_crew_physiology import validate_crew_health

TREATMENT_ROOM = "HAB-04-MED-TREAT"
PHARMACY_ROOM = "HAB-04-MED-PHARM"
OBSERVATION_ROOM = "HAB-04-MED-OBS"
TREATMENT_PANEL = "HAB-04-MED-TREAT-LP"
TREATMENT_FEEDER = "ISO-HAB-04-MED-TREAT-LP"
TREATMENT_POWER_NODE = "NODE-HAB-04-MED-TREAT-LP"
CLINIC_ZONE = "PZ-HAB-04"
MEDICAL_ROLES = frozenset({"medic", "medical_officer", "environment_tech"})

MAX_DRESSINGS = 24
MAX_FLUID_KG = 12.0
DRESSING_PER_CASE = 1
FLUID_PER_CASE_KG = 0.5
MAX_CARRIED_CASES = 4
MAX_CASES = 16
MAX_STEP_S = 10.0
STABILISE_S = 300.0
RECOVERY_RATE_PER_S = 0.00001
# Attended clinical convalescence is separate from emergency stabilisation.
OBSERVATION_S = 7200.0
OBSERVATION_HEAL_PER_S = 0.000003
MAX_OBSERVATIONS = 2


class MedicalError(ValueError):
    pass


def _nonnegative(value, *, integer=False):
    if (isinstance(value, bool) or
            not isinstance(value, int if integer else (int, float)) or
            not math.isfinite(value) or value < 0):
        raise MedicalError("Medical stock or elapsed time is not finite")
    return int(value) if integer else float(value)


def _ref(value):
    return isinstance(value, str) and re.fullmatch(r"#[0-9]+", value) is not None


def initial_medical(*, dressings=0, fluid_kg=0.0):
    """Operator-attested *existing* pharmacy stock, not new ship cargo.

    Zero is the default. Commissioning must provide its actual local count,
    capped by the current bounded treatment model; no replenishment is
    implied by reload, crew movement or completion of care.
    """
    d = _nonnegative(dressings, integer=True)
    f = _nonnegative(fluid_kg)
    if d > MAX_DRESSINGS or f > MAX_FLUID_KG:
        raise MedicalError("Pharmacy survey exceeds bounded fitted stock")
    result = {
        "surveyed_dressings": d, "surveyed_fluid_kg": f,
        "pharmacy_dressings": d, "pharmacy_fluid_kg": f,
        "dressings": 0, "fluid_kg": 0.0,
        "carried": {}, "used_dressings": 0, "used_fluid_kg": 0.0,
        "cases": {}, "completed": 0,
        "observations": {}, "observation_completed": 0,
        "obs_dressings": 0, "obs_fluid_kg": 0.0,
    }
    validate_medical(result)
    return result


def validate_medical(m):
    original = {"surveyed_dressings", "surveyed_fluid_kg",
                "pharmacy_dressings", "pharmacy_fluid_kg",
                "dressings", "fluid_kg", "carried",
                "used_dressings", "used_fluid_kg", "cases", "completed"}
    extended = original | {"observations", "observation_completed"}
    stationed = extended | {"obs_dressings", "obs_fluid_kg"}
    if not isinstance(m, dict) or set(m) not in (original, extended, stationed):
        raise MedicalError("Incomplete medical stock and care custody")
    if set(m) == extended:
        _nonnegative(m["observation_completed"], integer=True)
    for key in ("surveyed_dressings", "pharmacy_dressings",
                "dressings", "used_dressings", "completed") + (
                    ("obs_dressings",) if "obs_dressings" in m else ()):
        _nonnegative(m[key], integer=True)
    for key in ("surveyed_fluid_kg", "pharmacy_fluid_kg",
                "fluid_kg", "used_fluid_kg") + (
                    ("obs_fluid_kg",) if "obs_fluid_kg" in m else ()):
        _nonnegative(m[key])
    if (m["surveyed_dressings"] > MAX_DRESSINGS or
            m["surveyed_fluid_kg"] > MAX_FLUID_KG or
            not isinstance(m["carried"], dict) or
            len(m["carried"]) > 40):
        raise MedicalError("Invalid surveyed medical capacity")
    carried_d = 0
    carried_f = 0.0
    for actor, load in m["carried"].items():
        if not _ref(actor) or not isinstance(load, dict) or set(load) != {
                "dressings", "fluid_kg"}:
            raise MedicalError("Unknown physical medical-supply custodian")
        d = _nonnegative(load["dressings"], integer=True)
        f = _nonnegative(load["fluid_kg"])
        if d < 1 or d > MAX_CARRIED_CASES or not math.isclose(
                f, d * FLUID_PER_CASE_KG, abs_tol=1e-8, rel_tol=0):
            raise MedicalError("Inconsistent portable medical kit")
        carried_d += d
        carried_f += f
    if (m["pharmacy_dressings"] + m["dressings"]
            + m.get("obs_dressings", 0)
            + m["used_dressings"] + carried_d != m["surveyed_dressings"] or
            not math.isclose(
                m["pharmacy_fluid_kg"] + m["fluid_kg"]
                + m.get("obs_fluid_kg", 0.0)
                + m["used_fluid_kg"] + carried_f,
                m["surveyed_fluid_kg"], abs_tol=1e-7, rel_tol=0)):
        raise MedicalError("Medical supplies duplicated or lost")
    if not isinstance(m["cases"], dict) or len(m["cases"]) > MAX_CASES:
        raise MedicalError("Medical treatment caseload exceeds actual capacity")
    busy = set()
    for patient, case in m["cases"].items():
        if (not _ref(patient) or not isinstance(case, dict)
                or set(case) != {"caregiver", "remaining_s"} or
                not _ref(case["caregiver"]) or case["caregiver"] == patient
                or case["caregiver"] in busy
                or _nonnegative(case["remaining_s"]) > STABILISE_S):
            raise MedicalError("Unstaffed or invalid individual treatment order")
        busy.add(case["caregiver"])
    observations = m.get("observations", {})
    if not isinstance(observations, dict) or len(observations) > MAX_OBSERVATIONS:
        raise MedicalError("Unknown occupied clinical observation capacity")
    for patient, course in observations.items():
        if (not _ref(patient) or patient in m["cases"] or
                not isinstance(course, dict) or
                set(course) not in (
                    {"caregiver", "remaining_s", "observed_s"},
                    {"caregiver", "remaining_s", "observed_s", "room"}) or
                course.get("room", TREATMENT_ROOM) not in {
                    TREATMENT_ROOM, OBSERVATION_ROOM} or
                not _ref(course["caregiver"]) or patient == course["caregiver"] or
                course["caregiver"] in busy or
                _nonnegative(course["remaining_s"]) > OBSERVATION_S or
                _nonnegative(course["observed_s"]) > OBSERVATION_S or
                not math.isclose(course["remaining_s"] + course["observed_s"],
                                 OBSERVATION_S, abs_tol=1e-6, rel_tol=0)):
            raise MedicalError("Invalid clinical observation assignment")
        busy.add(course["caregiver"])
    return True


def carry_medical_kit(m, *, actor, verb, cases=1, destination=TREATMENT_ROOM):
    """One finite hand-carried kit per case: dressing plus 0.5 kg fluid.

    The Evennia adapter must prove pickup at the original pharmacy and
    delivery in the original treatment room; neither action teleports a kit.
    """
    validate_medical(m)
    if not _ref(actor):
        raise MedicalError("Medical kit has no individual carrier")
    result = copy.deepcopy(m)
    if verb == "pickup":
        n = _nonnegative(cases, integer=True)
        if not 1 <= n <= MAX_CARRIED_CASES:
            raise MedicalError("Portable medical kit limited to four cases")
        if actor in result["carried"]:
            raise MedicalError("Deliver existing carried kit before another pickup")
        if (result["pharmacy_dressings"] < n
                or result["pharmacy_fluid_kg"] + 1e-8 < n * FLUID_PER_CASE_KG):
            raise MedicalError("Pharmacy has insufficient surveyed dressings or fluid")
        result["pharmacy_dressings"] -= n
        result["pharmacy_fluid_kg"] -= n * FLUID_PER_CASE_KG
        result["carried"][actor] = {
            "dressings": n, "fluid_kg": n * FLUID_PER_CASE_KG}
    elif verb == "deliver":
        if actor not in result["carried"] or destination not in {
                TREATMENT_ROOM, OBSERVATION_ROOM}:
            raise MedicalError("A real personal kit must be delivered at fitted treatment or observation")
        load = result["carried"].pop(actor)
        if destination == OBSERVATION_ROOM:
            result.setdefault("obs_dressings", 0)
            result.setdefault("obs_fluid_kg", 0.0)
            result["obs_dressings"] += load["dressings"]
            result["obs_fluid_kg"] += load["fluid_kg"]
        else:
            result["dressings"] += load["dressings"]
            result["fluid_kg"] += load["fluid_kg"]
    else:
        raise MedicalError("Only pharmacy pickup or treatment delivery")
    validate_medical(result)
    return result


def begin_care(m, *, patient, caregiver, health, patient_room,
               caregiver_room, equipment_ok, breathable):
    validate_medical(m)
    validate_crew_health(health)
    if (health["condition"] in {"dead", "fit"} or patient == caregiver
            or not _ref(patient) or not _ref(caregiver)
            or patient_room != TREATMENT_ROOM or caregiver_room != TREATMENT_ROOM
            or not equipment_ok or not breathable):
        raise MedicalError("Injured patient and caregiver must attend powered safe HAB-04 treatment")
    if (patient in m["cases"] or any(
            row["caregiver"] == caregiver for row in m["cases"].values())
            or caregiver in {row["caregiver"] for row in m.get("observations", {}).values()}
            or len(m["cases"]) >= MAX_CASES
            or m["dressings"] < DRESSING_PER_CASE
            or m["fluid_kg"] < FLUID_PER_CASE_KG):
        raise MedicalError("Care station occupied or finite treatment supplies missing")
    result = copy.deepcopy(m)
    result["dressings"] -= DRESSING_PER_CASE
    result["used_dressings"] += DRESSING_PER_CASE
    result["fluid_kg"] -= FLUID_PER_CASE_KG
    result["used_fluid_kg"] += FLUID_PER_CASE_KG
    result["cases"][patient] = {
        "caregiver": caregiver, "remaining_s": STABILISE_S}
    validate_medical(result)
    return result


def _condition_after_care(h):
    """Keep the same physiologic incapacity thresholds as exposure."""
    if h["injury"] >= 1.0 or h["hypoxia_s"] >= 1200:
        return "dead"
    if h["injury"] >= 0.95 or h["hypoxia_s"] >= 600:
        return "critical"
    if h["injury"] >= 0.5 or h["hypoxia_s"] >= 180:
        return "incapacitated"
    if (h["injury"] >= 0.15 or h["hypoxia_s"] >= 40 or
            h["water_deficit_kg"] > 2):
        return "impaired"
    return "fit"


def begin_observation(m, *, patient, caregiver, health, patient_room,
                      caregiver_room, equipment_ok, breathable):
    """Reserve one of two attended HAB-04 clinical slots for finite follow-up.

    A further real treatment kit is spent at enrollment. The patient must
    be alive, injured, registered and physically present in the powered room.
    Past courses do not mint free replenishment or erase cumulative exposure.
    """
    validate_medical(m)
    validate_crew_health(health)
    active = m.get("observations", {})
    workers = {v["caregiver"] for v in m["cases"].values()}
    workers.update(v["caregiver"] for v in active.values())
    attended_room = patient_room in {TREATMENT_ROOM, OBSERVATION_ROOM}
    bedside_dressings = ("obs_dressings" if patient_room == OBSERVATION_ROOM
                          else "dressings")
    bedside_fluid = ("obs_fluid_kg" if patient_room == OBSERVATION_ROOM
                     else "fluid_kg")
    if (not _ref(patient) or not _ref(caregiver) or patient == caregiver
            or health["condition"] in {"dead", "fit"}
            or health["injury"] <= 0 or patient in m["cases"]
            or patient in active or caregiver in workers
            or len(active) >= MAX_OBSERVATIONS
            or not attended_room or caregiver_room != patient_room
            or not equipment_ok or not breathable
            or m.get(bedside_dressings, 0) < 1
            or m.get(bedside_fluid, 0.0) < FLUID_PER_CASE_KG):
        raise MedicalError("Follow-up requires injured patient, qualified attendant, safe clinic and real kit")
    out = copy.deepcopy(m)
    out.setdefault("observations", {})
    out.setdefault("observation_completed", 0)
    out[bedside_dressings] -= 1
    out["used_dressings"] += 1
    out[bedside_fluid] -= FLUID_PER_CASE_KG
    out["used_fluid_kg"] += FLUID_PER_CASE_KG
    out["observations"][patient] = {
        "caregiver": caregiver, "remaining_s": OBSERVATION_S,
        "observed_s": 0.0, "room": patient_room}
    validate_medical(out)
    return out


def discharge_observation(m, *, patient, caregiver):
    """An early local discharge stops work without returning spent supplies."""
    validate_medical(m)
    if (not _ref(patient) or
            m.get("observations", {}).get(patient, {}).get("caregiver") != caregiver):
        raise MedicalError("No personally attended ongoing observation to discharge")
    out = copy.deepcopy(m)
    del out["observations"][patient]
    validate_medical(out)
    return out


def step_care(m, health_rows, seconds, *, occupants, equipment_ok, breathable,
              observer_occupants=None, observer_powered=None,
              observer_breathable=None):
    """A staffed five-minute course advances only in a safe local clinic."""
    validate_medical(m)
    dt = _nonnegative(seconds)
    if dt > MAX_STEP_S:
        raise MedicalError("Unbounded medical time advancement")
    result, health = copy.deepcopy(m), copy.deepcopy(health_rows)
    result.setdefault("observations", {})
    result.setdefault("observation_completed", 0)
    completed = []
    for patient, case in sorted(tuple(result["cases"].items())):
        if patient not in health:
            raise MedicalError("Patient lacks authoritative physiology")
        validate_crew_health(health[patient])
        if health[patient]["condition"] == "dead":
            del result["cases"][patient]
            continue
        if not (equipment_ok and breathable and patient in occupants
                and case["caregiver"] in occupants):
            continue
        case["remaining_s"] = max(0.0, case["remaining_s"] - dt)
        if case["remaining_s"] <= 1e-9:
            h = health[patient]
            h["injury"] = max(0.0, h["injury"] - RECOVERY_RATE_PER_S * STABILISE_S)
            # Stabilisation does not erase measured oxygen debt or old trauma.
            h["condition"] = _condition_after_care(h)
            validate_crew_health(h)
            result["completed"] += 1
            completed.append(patient)
            del result["cases"][patient]
    # Stabilisation never also receives observation credit during the same
    # interval; a new attended follow-up order is a separate signed action.
    for patient, course in sorted(tuple(result["observations"].items())):
        if patient not in health:
            raise MedicalError("Observed patient lacks registered physiology")
        h = health[patient]
        validate_crew_health(h)
        if h["condition"] == "dead":
            del result["observations"][patient]
            continue
        actual_room = course.get("room", TREATMENT_ROOM)
        at_bedside = (occupants if actual_room == TREATMENT_ROOM
                      else observer_occupants if observer_occupants is not None
                      else set())
        powered_here = (equipment_ok if actual_room == TREATMENT_ROOM
                        else bool(observer_powered))
        air_here = (breathable if actual_room == TREATMENT_ROOM
                    else bool(observer_breathable))
        if not (powered_here and air_here and patient in at_bedside
                and course["caregiver"] in at_bedside):
            continue
        h["injury"] = max(0.0, h["injury"] - OBSERVATION_HEAL_PER_S * dt)
        h["condition"] = _condition_after_care(h)
        course["remaining_s"] = max(0.0, course["remaining_s"] - dt)
        course["observed_s"] += dt
        validate_crew_health(h)
        if course["remaining_s"] <= 1e-9:
            result["observation_completed"] += 1
            del result["observations"][patient]
    validate_medical(result)
    return result, health, tuple(completed)
