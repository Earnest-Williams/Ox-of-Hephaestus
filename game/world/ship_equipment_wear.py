"""G19 continuous wear of the 26 already powered cargo, crop and shop units.

A fitted old freighter has an uneven maintenance history. Existing run-hour
meters provide known *new* service since this installation. An operator may
attest older remaining service life independently; commissioning never
pretends every inherited machine was rebuilt. Two calibrated deterministic
stages create actual repairable degraded and faulted condition transitions.
Repair completion must carry its original journalled hardware timestamp;
a cosmetic command cannot renew exhausted wear.
"""
from __future__ import annotations

import copy
import math

from world.ship_equipment_services import (
    SERVICE_LOADS, MANUAL_RESTART, validate_service_operations)
from world.ship_electrical_power import ElectricalError

# Game-calibrated inspection intervals; not a claim of OEM ratings.
SERVICE_INTERVAL_S = {
    name: (30 * 86400.0 if name in MANUAL_RESTART
           else 90 * 86400.0 if "-CARGO-" in name
           else 60 * 86400.0)
    for name in SERVICE_LOADS
}
FAILURE_MULTIPLIER = 1.25
STAGES = ("normal", "degraded", "faulted")


def _finite(number, low=0.0, high=None):
    if (type(number) not in (int, float) or not math.isfinite(number)
            or number < low or (high is not None and number > high)):
        raise ElectricalError("Invalid finite secondary-machinery wear state")
    return float(number)


def initial_equipment_wear(service_operations):
    """Seed from existing runtime so upgrading an old world loses no history."""
    validate_service_operations(service_operations)
    return {
        "version": 1,
        "units": {
            name: {
                "wear_s": 0.0,
                "seen_runtime_s": service_operations["units"][name]["runtime_s"],
                "last_repair_game_time": None,
                "stage": "normal", "surveyed": False,
                "wear_faults": 0,
            }
            for name in sorted(SERVICE_LOADS)
        },
        "last": {"maintenance_due": [], "faulted": [],
                 "new_faults": []},
    }


def validate_equipment_wear(ledger, services):
    validate_service_operations(services)
    if (not isinstance(ledger, dict)
            or set(ledger) != {"version", "units", "last"}
            or ledger["version"] != 1 or not isinstance(ledger["units"], dict)
            or set(ledger["units"]) != set(SERVICE_LOADS)
            or not isinstance(ledger["last"], dict)
            or set(ledger["last"]) != {
                "maintenance_due", "faulted", "new_faults"}):
        raise ElectricalError("Unknown fitted equipment wear ledger")
    for name, row in ledger["units"].items():
        if not isinstance(row, dict) or set(row) != {
                "wear_s", "seen_runtime_s", "last_repair_game_time",
                "stage", "surveyed", "wear_faults"}:
            raise ElectricalError("Incomplete maintenance history")
        _finite(row["wear_s"])
        _finite(row["seen_runtime_s"], high=services["units"][name]["runtime_s"])
        stamp = row["last_repair_game_time"]
        if stamp is not None:
            _finite(stamp)
        if (row["stage"] not in STAGES or
                type(row["surveyed"]) is not bool or
                type(row["wear_faults"]) is not int or row["wear_faults"] < 0):
            raise ElectricalError("Impossible maintenance fault stage")
    for key in ledger["last"]:
        items = ledger["last"][key]
        if (not isinstance(items, list) or items != sorted(set(items))
                or not set(items) <= set(SERVICE_LOADS)):
            raise ElectricalError("Unfitted maintenance instrument ID")
    return True


def survey_existing_wear(ledger, services, name, *, equivalent_hours):
    """One operator attestation of historical wear before a first new failure."""
    validate_equipment_wear(ledger, services)
    if name not in SERVICE_LOADS:
        raise ElectricalError("No actual secondary machinery to survey")
    amount = _finite(
        equivalent_hours, high=SERVICE_INTERVAL_S[name] *
        FAILURE_MULTIPLIER / 3600.0)
    original = ledger["units"][name]
    if original["surveyed"] or original["stage"] != "normal":
        raise ElectricalError("Machine wear already surveyed or faulted")
    result = copy.deepcopy(ledger)
    result["units"][name]["wear_s"] = amount * 3600.0
    result["units"][name]["surveyed"] = True
    validate_equipment_wear(result, services)
    return result


def step_equipment_wear(ledger, services, equipment):
    """Advance only real accumulated running hours and report actual faults.

    Returns (new_ledger, [(unit, condition)]). Caller changes canonical
    equipment rows atomically. No uniform random damage, auto-repairs or
    work-order bypasses. A completed original repair replaces the worn
    service part and resets the post-service clock exactly once.
    """
    validate_equipment_wear(ledger, services)
    result = copy.deepcopy(ledger)
    due, faulted, new_faults = [], [], []
    changes = []
    for name, row in sorted(result["units"].items()):
        item = equipment.get(name)
        if item is None or not isinstance(item.details, dict):
            raise ElectricalError("Maintained machine disappeared from fitted ship")
        current = services["units"][name]["runtime_s"]
        delta = current - row["seen_runtime_s"]
        if delta < -1e-7 or delta > 10.00001:
            raise ElectricalError("Machine wear cannot jump outside one physics substep")
        last_repair = item.details.get("repair_completed_game_time")
        if last_repair is not None:
            _finite(last_repair)
        if last_repair is not None and (
                row["last_repair_game_time"] is None
                or last_repair > row["last_repair_game_time"]):
            # A real repaired part has a durable, authoritatively logged
            # completion timestamp in the equipment row. Retire all wear,
            # but retain the cumulative number of previous failures.
            if item.condition == "serviceable":
                row["wear_s"] = 0.0
                row["stage"] = "normal"
                row["last_repair_game_time"] = last_repair
        row["seen_runtime_s"] = current
        row["wear_s"] += max(0.0, delta)
        warn = SERVICE_INTERVAL_S[name]
        if row["wear_s"] >= warn:
            due.append(name)
        old_stage = row["stage"]
        if row["wear_s"] >= warn * FAILURE_MULTIPLIER:
            row["stage"] = "faulted"
        elif row["wear_s"] >= warn:
            if old_stage == "normal":
                row["stage"] = "degraded"
        # A recorded wear fault cannot be erased by later state edits.
        # Only a real completed shared-equipment repair can restore it.
        if row["stage"] == "faulted":
            faulted.append(name)
        if row["stage"] != old_stage:
            if row["stage"] == "faulted":
                row["wear_faults"] += 1
            if (item.condition in {"serviceable", "degraded"}
                    and row["stage"] == "faulted"):
                changes.append((name, "faulted"))
                new_faults.append(name)
            elif item.condition == "serviceable" and row["stage"] == "degraded":
                changes.append((name, "degraded"))
        elif row["stage"] == "faulted" and item.condition in {
                "serviceable", "degraded"}:
            # Externally restoring an item without a repair receipt does
            # not bypass a latched mechanical wear failure.
            changes.append((name, "faulted"))
            new_faults.append(name)
    result["last"] = {
        "maintenance_due": due, "faulted": faulted,
        "new_faults": new_faults,
    }
    validate_equipment_wear(result, services)
    return result, changes
