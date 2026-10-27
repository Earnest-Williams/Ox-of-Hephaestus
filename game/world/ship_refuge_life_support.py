"""G19 measured HAB refuge scrubber media coupled to finite local electricity.

Installed refuge-air packages are real, but neither an unsurveyed battery nor
an unsurveyed CO2 receiver provides a working emergency air service. Captured
CO2 is retained aboard in finite sorbent; this creates no oxygen or fresh gas.
"""
from __future__ import annotations

import copy
import math

from world.ship_crew_exposure import OXYGEN_KG_S

REFUGE_PACKS = {
    "HAB-04-REFUGE-AIR": ("HAB-04-REFUGE", "HAB-04-REFUGE-BAT"),
    "HAB-08-REFUGE-AIR": ("HAB-08-REFUGE", "HAB-08-REFUGE-BAT"),
}
DESIGN_PEOPLE = 40
DESIGN_DURATION_H = 72
# Bounded fictional design capacity derived from the existing registered
# crew oxygen/CO2 mass proxy and the fitted 40-person, 72-hour package.
NOMINAL_CAPTURE_KG = DESIGN_PEOPLE * DESIGN_DURATION_H * 3600 * OXYGEN_KG_S
CAPTURE_RATE_KG_S = DESIGN_PEOPLE * OXYGEN_KG_S
CP_GAS_KJ_KG_K = 1.0
MIN_PRESSURE_PA = 40000.0
AIR_R_J_KG_K = 287.05


class RefugeAirError(ValueError):
    """No gas cleaning without a real powered appliance and measured medium."""


def _nonnegative(value):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < 0):
        raise RefugeAirError("Invalid measured refuge air quantity")
    return float(value)


def initial_refuge_scrubbers():
    return {"version": 1, "units": {}, "meter": {"captured_kg": 0.0},
            "last": {}}


def validate_refuge_scrubbers(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"version", "units", "meter", "last"}
            or ledger["version"] != 1 or not isinstance(ledger["units"], dict)
            or not set(ledger["units"]) <= set(REFUGE_PACKS)
            or not isinstance(ledger["meter"], dict)
            or set(ledger["meter"]) != {"captured_kg"}
            or not isinstance(ledger["last"], dict)):
        raise RefugeAirError("Unrecognised refuge scrubber ledger")
    accounted = 0.0
    for pack, unit in ledger["units"].items():
        if not isinstance(unit, dict) or set(unit) != {"capacity_kg", "captured_kg"}:
            raise RefugeAirError("Corrupt refuge sorbent survey")
        capacity = _nonnegative(unit["capacity_kg"])
        captured = _nonnegative(unit["captured_kg"])
        if (capacity > NOMINAL_CAPTURE_KG + 1e-7
                or captured > capacity + 1e-8):
            raise RefugeAirError("Refuge CO2 sequestration exceeds physical media")
        accounted += captured
    if not math.isclose(_nonnegative(ledger["meter"]["captured_kg"]),
                        accounted, rel_tol=1e-10, abs_tol=1e-8):
        raise RefugeAirError("Refuge CO2 mass ledger does not reconcile")
    return True


def survey_refuge_scrubber(ledger, pack, *, remaining_capacity_kg):
    """Record verified installed media, never assume full/renew it on restart."""
    validate_refuge_scrubbers(ledger)
    if pack not in REFUGE_PACKS or pack in ledger["units"]:
        raise RefugeAirError("No unsurveyed fitted refuge sorbent package")
    remaining = _nonnegative(remaining_capacity_kg)
    if remaining <= 0 or remaining > NOMINAL_CAPTURE_KG + 1e-7:
        raise RefugeAirError("Unverified refuge medium exceeds fitted envelope")
    updated = copy.deepcopy(ledger)
    updated["units"][pack] = {"capacity_kg": remaining, "captured_kg": 0.0}
    validate_refuge_scrubbers(updated)
    return updated


def step_refuge_scrubbers(ledger, seconds, *, powered_consumers,
                         equipment, room_zones, cells):
    """Conserve actual pressure-cell CO2 into at most two finite receivers.

    The caller must independently verify the normal power endpoint or an
    actual live, fully supplied local emergency battery output. An open bus
    and an unmeasured battery are never evidence of running fans/sorbent.
    Does not provide oxygen, smoke removal, cooling or pressure support.
    """
    validate_refuge_scrubbers(ledger)
    dt = _nonnegative(seconds)
    if dt > 10:
        raise RefugeAirError("Unbounded refuge atmosphere step")
    updated = copy.deepcopy(ledger)
    gas = copy.deepcopy(cells)
    ready, captured_tick, blocked = [], {}, {}
    live = set(powered_consumers)
    if not live <= set(REFUGE_PACKS):
        raise RefugeAirError("Unfitted refuge air appliance supplied")
    for pack, (room, battery) in REFUGE_PACKS.items():
        if pack not in updated["units"]:
            blocked[pack] = "sorbent_unsurveyed"
            continue
        unit = equipment.get(pack)
        if (unit is None or unit.space_id != room
                or unit.condition in {"faulted", "failed", "severed",
                                      "jammed", "destroyed"}):
            blocked[pack] = "refuge_air_equipment_failed"
            continue
        if pack not in live:
            blocked[pack] = "normal_and_local_electricity_unavailable"
            continue
        zone = room_zones.get(room)
        cell = gas.get(zone)
        if cell is None:
            blocked[pack] = "no_qualified_pressurised_envelope"
            continue
        for field in ("mass", "co2", "energy", "temperature", "capacity", "volume"):
            if field not in cell:
                raise RefugeAirError("Missing actual refuge gas measurement")
            _nonnegative(cell[field])
        if (cell["mass"] <= 0 or cell["volume"] <= 0
                or cell["capacity"] <= 0 or cell["temperature"] <= 0
                or cell["co2"] > cell["mass"] + 1e-8):
            raise RefugeAirError("Impossible refuge atmosphere")
        pressure_pa = (cell["mass"] * AIR_R_J_KG_K
                       * cell["temperature"] / cell["volume"])
        if pressure_pa < MIN_PRESSURE_PA:
            blocked[pack] = "unpressurised_refuge"
            continue
        ready.append(pack)
        remaining = max(0.0, updated["units"][pack]["capacity_kg"]
                        - updated["units"][pack]["captured_kg"])
        removal = min(cell["co2"], CAPTURE_RATE_KG_S * dt, remaining)
        if removal <= 0:
            if remaining <= 0:
                blocked[pack] = "sorbent_exhausted"
            continue
        cell["co2"] -= removal
        cell["mass"] -= removal
        cell["energy"] -= removal * CP_GAS_KJ_KG_K * cell["temperature"]
        if cell["mass"] <= 0 or cell["energy"] <= 0:
            raise RefugeAirError("Refuge scrubber violated finite gas energy")
        cell["temperature"] = (cell["energy"] /
                               (cell["capacity"] + cell["mass"] * CP_GAS_KJ_KG_K))
        updated["units"][pack]["captured_kg"] += removal
        updated["meter"]["captured_kg"] += removal
        captured_tick[pack] = removal
    updated["last"] = {
        "powered": ready,
        "captured_this_step_kg": captured_tick,
        "blocked": blocked,
    }
    validate_refuge_scrubbers(updated)
    return updated, gas
