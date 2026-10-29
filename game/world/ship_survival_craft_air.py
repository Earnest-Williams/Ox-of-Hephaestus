"""G19 fitted independent survival-craft air cleanup, with finite media.

Two original RESCUE-FWD/AFT life-support packages each have a separately
sealed rated compartment. Their authored rating is 40 occupants/30 days,
but the design does not provide an itemised as-found battery or cartridge
fill. Operator must therefore attest the FINITE remaining operating time
and installed CO2 media capacity before any useful output is credited.

The appliance may run independent of the main ship generator only while its
original access hatch is physically shut and the independently surveyed
package is sound. It removes CO2 mass from the *existing* pressure cell
into the retained installed filter, never creates oxygen/air or additional
pressure cells. Crew may switch it on/off only at its real local room.
"""
from __future__ import annotations

import copy
import math

from world.ship_crew_exposure import OXYGEN_KG_S

PACKS = {
    "RESCUE-FWD-LSS": ("RESCUE-FWD", "PZ-BOW-RESCUE", "ACC-RESCUE-FWD"),
    "RESCUE-AFT-LSS": ("RESCUE-AFT", "PZ-AFT-RESCUE", "ACC-RESCUE-AFT"),
}
PEOPLE_RATED = 40
DURATION_RATED_S = 30 * 86400.0
CAPTURE_RATE_KG_S = PEOPLE_RATED * OXYGEN_KG_S
MAX_RETAINED_KG = CAPTURE_RATE_KG_S * DURATION_RATED_S
MAX_STEP_S = 10.0
GAS_CP_KJ_KG_K = 1.0
R_AIR = 287.05
EPS = 1e-7
BROKEN = frozenset({"failed", "faulted", "jammed", "severed", "destroyed"})


class SurvivalAirError(ValueError):
    """No finite, local, surveyed and operable survival-craft air service."""


def _finite(v, low=0.0):
    if type(v) not in (int, float) or not math.isfinite(v) or v < low:
        raise SurvivalAirError("Invalid finite survival-craft air custody")
    return float(v)


def initial_survival_air():
    return {"version": 1,
            "units": {
                name: {"mode": "off", "charge": None, "captured_kg": 0.0,
                       "last_capture_kg": 0.0, "last_s": None}
                for name in PACKS},
            "meter": {"captured_kg": 0.0},
            "last": {"captured_kg": 0.0, "running": []}}


def validate_survival_air(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"version", "units", "meter", "last"}
            or type(ledger["version"]) is not int or ledger["version"] != 1
            or not isinstance(ledger["units"], dict)
            or set(ledger["units"]) != set(PACKS)
            or set(ledger.get("meter", {})) != {"captured_kg"}
            or set(ledger.get("last", {})) != {"captured_kg", "running"}):
        raise SurvivalAirError("Original dual survival-craft LSS roster lost")
    total = 0.0
    for name, row in ledger["units"].items():
        if not isinstance(row, dict) or set(row) != {
                "mode", "charge", "captured_kg",
                "last_capture_kg", "last_s"} or row["mode"] not in ("off", "scrub"):
            raise SurvivalAirError("Invalid original survival-craft machine state")
        captured = _finite(row["captured_kg"])
        previous = _finite(row["last_capture_kg"])
        if captured + EPS < previous:
            raise SurvivalAirError("Recovery meter exceeds cumulative capture")
        charge = row["charge"]
        if charge is None:
            if row["mode"] != "off" or captured != 0 or previous != 0:
                raise SurvivalAirError("Unsurveyed survival-craft package operating")
        else:
            if not isinstance(charge, dict) or set(charge) != {
                    "capacity_kg", "runtime_initial_s", "runtime_remaining_s"}:
                raise SurvivalAirError("No intact finite LSS survey record")
            capacity = _finite(charge["capacity_kg"])
            initial = _finite(charge["runtime_initial_s"])
            remaining = _finite(charge["runtime_remaining_s"])
            if (capacity <= 0 or capacity > MAX_RETAINED_KG + EPS
                    or initial <= 0 or initial > DURATION_RATED_S + EPS
                    or remaining > initial + EPS or captured > capacity + EPS):
                raise SurvivalAirError("LSS output exceeds finite installed charge")
        if (row["last_s"] is not None and
                type(row["last_s"]) not in (int, float)):
            raise SurvivalAirError("Invalid clock origin for LSS report")
        if row["last_s"] is not None:
            _finite(row["last_s"])
        elif captured or previous:
            raise SurvivalAirError("Unrecorded elapsed time for LSS effect")
        total += captured
    if not math.isclose(_finite(ledger["meter"]["captured_kg"]), total,
                        abs_tol=1e-6, rel_tol=1e-10):
        raise SurvivalAirError("Captured craft CO2 escaped the installed receiver")
    if (not isinstance(ledger["last"]["running"], list)
            or len(ledger["last"]["running"]) !=
                len(set(ledger["last"]["running"]))
            or any(n not in PACKS for n in ledger["last"]["running"])):
        raise SurvivalAirError("Nonexistent independent survival-air package ran")
    if (_finite(ledger["last"]["captured_kg"]) >
            _finite(ledger["meter"]["captured_kg"]) + EPS):
        raise SurvivalAirError("Last-step capture exceeds retained receiver")
    return True


def survey_survival_air(ledger, name, *, capacity_kg, runtime_s):
    """Record as-found media and independent runtime ONCE, never recharge."""
    validate_survival_air(ledger)
    if name not in PACKS or ledger["units"][name]["charge"] is not None:
        raise SurvivalAirError("Survival-craft LSS survey already committed")
    cap, seconds = _finite(capacity_kg), _finite(runtime_s)
    if not 0 < cap <= MAX_RETAINED_KG or not 0 < seconds <= DURATION_RATED_S:
        raise SurvivalAirError("Unverified media or independent operating time")
    updated = copy.deepcopy(ledger)
    updated["units"][name]["charge"] = {
        "capacity_kg": cap, "runtime_initial_s": seconds,
        "runtime_remaining_s": seconds}
    validate_survival_air(updated)
    return updated


def command_survival_air(ledger, name, mode):
    validate_survival_air(ledger)
    if name not in PACKS or mode not in ("off", "scrub"):
        raise SurvivalAirError("No fitted manual survival-air control")
    row = ledger["units"][name]
    if mode == "scrub" and (
            row["charge"] is None
            or row["charge"]["runtime_remaining_s"] <= 0
            or row["captured_kg"] >= row["charge"]["capacity_kg"]):
        raise SurvivalAirError("No verified finite independent LSS capacity")
    updated = copy.deepcopy(ledger)
    updated["units"][name]["mode"] = mode
    validate_survival_air(updated)
    return updated


def step_survival_air(ledger, seconds, *, now_s, equipment,
                      access, cells):
    """Transfer measured CO2 into two retained sorbents under actual doors.

    The package is self-contained only to the extent of its certified
    remaining runtime. Opening its original pressure hatch suspends capture.
    Independent power does not mean an infinite energy supply.
    """
    validate_survival_air(ledger)
    dt = _finite(seconds)
    now = _finite(now_s)
    if not 0 < dt <= MAX_STEP_S:
        raise SurvivalAirError("LSS work requires one bounded physics step")
    if not isinstance(cells, dict) or not isinstance(equipment, dict):
        raise SurvivalAirError("Actual ship gas/plant references are absent")
    updated = copy.deepcopy(ledger)
    running = []
    total = 0.0
    for name, (room, zone, door_id) in PACKS.items():
        row = updated["units"][name]
        prior = row["last_s"]
        if prior is not None and now < prior + dt - EPS:
            raise SurvivalAirError("Replayed independent LSS clock interval")
        row["last_s"] = now
        row["last_capture_kg"] = 0.0
        if row["mode"] != "scrub":
            continue
        unit = equipment.get(name)
        hatch = access.get(door_id)
        if unit is None or getattr(unit, "space_id", None) != room:
            raise SurvivalAirError("Fitted survival-craft machine is displaced")
        if hatch is None:
            raise SurvivalAirError("Original rated rescue hatch disappeared")
        charge = row["charge"]
        if charge is None:
            raise SurvivalAirError("Unsurveyed LSS cannot scrub real gas")
        if (unit.condition in BROKEN or hatch.condition in BROKEN
                or hatch.setting != "closed"):
            continue
        cell = cells.get(zone)
        if cell is None:
            raise SurvivalAirError("Rescue bay has no original finite pressure cell")
        mass = _finite(cell["mass"])
        co2 = _finite(cell["co2"])
        volume = _finite(cell["volume"], EPS)
        temperature = _finite(cell["temperature"], EPS)
        pressure = mass * R_AIR * temperature / volume
        if pressure < 40000 or mass <= 0:
            continue
        runtime = min(dt, charge["runtime_remaining_s"])
        if runtime <= 0:
            continue
        remaining = max(0.0, charge["capacity_kg"] - row["captured_kg"])
        if remaining <= 0:
            continue
        captured = min(CAPTURE_RATE_KG_S * runtime, remaining, co2)
        if captured > 0:
            cell["mass"] -= captured
            cell["co2"] -= captured
            cell["energy"] -= captured * GAS_CP_KJ_KG_K * temperature
            cell["temperature"] = cell["energy"] / (
                cell["capacity"] + cell["mass"] * GAS_CP_KJ_KG_K)
            row["captured_kg"] += captured
            row["last_capture_kg"] = captured
            total += captured
        charge["runtime_remaining_s"] -= runtime
        running.append(name)
    updated["meter"]["captured_kg"] += total
    updated["last"] = {"captured_kg": total, "running": running}
    validate_survival_air(updated)
    return updated, cells
