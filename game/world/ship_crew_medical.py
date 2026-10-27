"""G19 finite, site-bound medical stabilisation kernel.

Pure transitions: installed-world adapter must prove patient/caregiver locations,
HAB-04 equipment operability, breathable conditions, and elapsed authoritative
world time before adopting a state. Not a global cure or voyage simulation.
"""
from __future__ import annotations
import copy
import math
from world.ship_crew_physiology import validate_crew_health

class MedicalError(ValueError):
    pass

TREATMENT_ROOM = "HAB-04"
MAX_STEP_S = 10.0
MAX_CASES = 16
INITIAL_DRESSINGS = 24
INITIAL_FLUID_KG = 12.0
DRESSING_PER_CASE = 1
FLUID_PER_CASE_KG = 0.5
STABILISE_S = 300.0
RECOVERY_RATE_PER_S = 0.00001

def initial_medical():
    return {"dressings": INITIAL_DRESSINGS, "fluid_kg": INITIAL_FLUID_KG,
            "used_dressings": 0, "used_fluid_kg": 0.0,
            "cases": {}, "completed": 0}

def _quantity(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0:
        raise MedicalError("Invalid finite medical quantity")
    return float(x)

def validate_medical(m):
    if not isinstance(m, dict) or set(m) != {
            "dressings", "fluid_kg", "used_dressings", "used_fluid_kg",
            "cases", "completed"}:
        raise MedicalError("Incomplete medical stores or custody")
    if any(isinstance(m[k], bool) or not isinstance(m[k], int) or m[k] < 0
           for k in ("dressings", "used_dressings", "completed")):
        raise MedicalError("Invalid dressing count")
    if m["dressings"] + m["used_dressings"] != INITIAL_DRESSINGS:
        raise MedicalError("Medical dressings created or lost")
    if abs(_quantity(m["fluid_kg"]) + _quantity(m["used_fluid_kg"])
           - INITIAL_FLUID_KG) > 1e-7:
        raise MedicalError("Medical fluid custody does not reconcile")
    if not isinstance(m["cases"], dict) or len(m["cases"]) > MAX_CASES:
        raise MedicalError("Invalid active patient set")
    for patient, case in m["cases"].items():
        if (not isinstance(patient, str) or not patient.startswith("#")
                or not patient[1:].isdigit() or
                set(case) != {"caregiver", "remaining_s"} or
                not isinstance(case["caregiver"], str)
                or not case["caregiver"].startswith("#")
                or not case["caregiver"][1:].isdigit()
                or case["caregiver"] == patient
                or _quantity(case["remaining_s"]) > STABILISE_S):
            raise MedicalError("Invalid physical medical work order")
    return True

def begin_care(m, *, patient, caregiver, health, patient_room,
               caregiver_room, equipment_ok, breathable):
    validate_medical(m)
    validate_crew_health(health)
    if (health["condition"] == "dead" or patient == caregiver
            or not isinstance(patient, str) or not patient.startswith("#")
            or not patient[1:].isdigit() or not isinstance(caregiver, str)
            or not caregiver.startswith("#") or not caregiver[1:].isdigit()
            or patient_room != TREATMENT_ROOM or caregiver_room != TREATMENT_ROOM
            or not equipment_ok or not breathable):
        raise MedicalError("Patient, staffed treatment room and safe equipment required")
    if health["condition"] == "fit":
        raise MedicalError("No indicated injury or disabling exposure")
    if (patient in m["cases"] or len(m["cases"]) >= MAX_CASES
            or m["dressings"] < DRESSING_PER_CASE
            or m["fluid_kg"] < FLUID_PER_CASE_KG):
        raise MedicalError("Occupied care station or insufficient finite supplies")
    result = copy.deepcopy(m)
    result["dressings"] -= DRESSING_PER_CASE
    result["used_dressings"] += DRESSING_PER_CASE
    result["fluid_kg"] -= FLUID_PER_CASE_KG
    result["used_fluid_kg"] += FLUID_PER_CASE_KG
    result["cases"][patient] = {
        "caregiver": caregiver, "remaining_s": STABILISE_S}
    validate_medical(result)
    return result

def step_care(m, health_rows, seconds, *, occupants, equipment_ok, breathable):
    """Progress only proven co-located cases; never revive dead patients.

    Existing physiological exposure ticks remain authoritative; treatment only
    reduces lasting injury after the staffed stabilisation period.
    """
    validate_medical(m)
    dt = _quantity(seconds)
    if dt > MAX_STEP_S:
        raise MedicalError("Unbounded medical time advance")
    result, health = copy.deepcopy(m), copy.deepcopy(health_rows)
    completed = []
    for patient, case in sorted(result["cases"].items()):
        if patient not in health:
            raise MedicalError("Patient has no authoritative physiology record")
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
            # No instant hypoxia reversal: ongoing exposure physics samples air.
            if h["injury"] >= 0.95 or h["hypoxia_s"] >= 600:
                h["condition"] = "critical"
            elif h["injury"] >= 0.5 or h["hypoxia_s"] >= 180:
                h["condition"] = "incapacitated"
            elif h["injury"] >= 0.15 or h["hypoxia_s"] >= 40 or h["water_deficit_kg"] > 2:
                h["condition"] = "impaired"
            else:
                h["condition"] = "fit"
            validate_crew_health(h)
            result["completed"] += 1
            completed.append(patient)
            del result["cases"][patient]
    validate_medical(result)
    return result, health, tuple(completed)
