"""G19 ten ORIGINAL portable pumps and smoke-control fans.

An original fitted hardware record stays at its immutable home. The portable
ledger tracks separately who actually carries a device and where it was placed.
No new liquid tank, pressure cell, inter-compartment duct or electrical feeder.

Four pumps may only move already-enclosed A/B local grey/black wastewater to
the EXISTING fixed receiver, through the positively open rated wet crossing.
Six smoke fans recirculate existing pressurised-room gas and capture actual
smoke in a finite, individually surveyed onboard filter. They cannot vent
gas into space or create breathable oxygen.
"""
from __future__ import annotations

import copy
import math

PUMPS = {
    "DC-PUMP-01": "TRUNK-A-BOW",
    "DC-PUMP-02": "ENG-LOCKER",
    "DC-PUMP-03": "F2-BAY",
    "DC-PUMP-04": "TRUNK-B-AFT",
}
FANS = {
    "DC-SMOKE-FAN-01": "TRUNK-A-BOW",
    "DC-SMOKE-FAN-02": "BE-05-SVC",
    "DC-SMOKE-FAN-03": "ENG-LOCKER",
    "DC-SMOKE-FAN-04": "F2-BAY",
    "DC-SMOKE-FAN-05": "BE-11-SVC",
    "DC-SMOKE-FAN-06": "TRUNK-B-AFT",
}
FITTED = {**PUMPS, **FANS}
BROKEN = frozenset({"failed", "faulted", "jammed", "severed", "destroyed"})
LOCAL_CAPACITY_KG = {"grey": 500.0, "black": 250.0}
FIXED_CAPACITY_KG = {"grey": 10000.0, "black": 2000.0}
PUMP_FLOW_KG_S = 0.25
FAN_AIRFLOW_M3_S = 0.35
FAN_SMOKE_CAPTURE_KG_S = 0.002
MAX_FAN_FILTER_KG = 12.0
MAX_BATTERY_S = 24 * 3600.0
MAX_TICK_S = 10.0
GAS_CP = 1.0
AIR_R = 287.05
EPS = 1e-7


class PortableDamageError(ValueError):
    """An original portable machine has no valid physical work path."""


def quantity(v):
    if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
        raise PortableDamageError("Nonfinite or negative portable machinery quantity")
    return float(v)


def initial_portable_damage():
    return {
        "version": 1,
        "units": {
            name: {"room": home, "carrier": None, "mode": "off",
                   "survey": None, "route": None,
                   "cumulative_kg": 0.0, "cumulative_m3": 0.0,
                   "last_kg": 0.0, "last_m3": 0.0, "last_s": None}
            for name, home in FITTED.items()
        },
        "meter": {"pumped_kg": 0.0, "smoke_captured_kg": 0.0,
                  "recirculated_m3": 0.0},
        "last": {"pumped_kg": 0.0, "smoke_captured_kg": 0.0,
                 "recirculated_m3": 0.0, "running": []},
    }


def validate_portable_damage(ledger):
    if (not isinstance(ledger, dict) or set(ledger) !=
            {"version", "units", "meter", "last"}
            or type(ledger["version"]) is not int or ledger["version"] != 1
            or not isinstance(ledger["units"], dict)
            or set(ledger["units"]) != set(FITTED)
            or set(ledger["meter"]) !=
            {"pumped_kg", "smoke_captured_kg", "recirculated_m3"}
            or set(ledger["last"]) !=
            {"pumped_kg", "smoke_captured_kg", "recirculated_m3", "running"}):
        raise PortableDamageError("Original ten portable machines lost")
    carriers = set()
    pump_total = fan_total = air_total = 0.0
    for name, record in ledger["units"].items():
        if (not isinstance(record, dict) or set(record) !=
                {"room", "carrier", "mode", "survey", "route",
                 "cumulative_kg", "cumulative_m3", "last_kg",
                 "last_m3", "last_s"} or record["mode"] not in {"off", "on"}):
            raise PortableDamageError("Invalid portable device record")
        room, carrier = record["room"], record["carrier"]
        if (room is None) == (carrier is None):
            raise PortableDamageError("Portable unit is lost or duplicated")
        if room is not None and (not isinstance(room, str) or not room):
            raise PortableDamageError("Unrecognised portable destination")
        if carrier is not None:
            if (not isinstance(carrier, str) or not carrier
                    or carrier in carriers or record["mode"] != "off"):
                raise PortableDamageError("Carried live or duplicate portable device")
            carriers.add(carrier)
        media = record["survey"]
        if media is not None:
            if (not isinstance(media, dict) or set(media) !=
                    {"battery_initial_s", "battery_remaining_s", "filter_kg"}):
                raise PortableDamageError("Unverified portable power/filter survey")
            initial, remaining = quantity(media["battery_initial_s"]), quantity(
                media["battery_remaining_s"])
            if (not 0 < initial <= MAX_BATTERY_S or remaining > initial + EPS
                    or quantity(media["filter_kg"]) >
                    (MAX_FAN_FILTER_KG if name in FANS else 0)):
                raise PortableDamageError("Battery or filter exceeds original surveyed bounds")
        elif record["mode"] == "on":
            raise PortableDamageError("Unsurveyed unit cannot be powered")
        route = record["route"]
        if name in PUMPS:
            if route is not None and (
                    not isinstance(route, list) or len(route) != 2
                    or route[0] not in {"A", "B"}
                    or route[1] not in {"grey", "black"}):
                raise PortableDamageError("Pump route is not an existing wet circuit")
            if record["mode"] == "on" and route is None:
                raise PortableDamageError("Portable pump has no attached source/discharge")
        elif route is not None:
            raise PortableDamageError("Portable fan cannot acquire a liquid route")
        gross = quantity(record["cumulative_kg"])
        volume = quantity(record["cumulative_m3"])
        if media is None and (gross > EPS or volume > EPS):
            raise PortableDamageError("Unsurveyed portable cannot have produced work")
        if name in FANS and media is not None and gross > media["filter_kg"] + EPS:
            raise PortableDamageError("Portable smoke receiver exceeded its filter")
        if (quantity(record["last_kg"]) > gross + EPS
                or quantity(record["last_m3"]) > volume + EPS):
            raise PortableDamageError("Portable meter exceeds its lifetime")
        if record["last_s"] is not None:
            quantity(record["last_s"])
        elif gross or volume:
            raise PortableDamageError("Portable measured output has no time source")
        if name in PUMPS:
            if volume or record["last_m3"]:
                raise PortableDamageError("Liquid pump reports invented gas airflow")
            pump_total += gross
        else:
            fan_total += gross
            air_total += volume
    for key, expected in (("pumped_kg", pump_total),
                          ("smoke_captured_kg", fan_total),
                          ("recirculated_m3", air_total)):
        if not math.isclose(quantity(ledger["meter"][key]), expected,
                            abs_tol=1e-6, rel_tol=1e-10):
            raise PortableDamageError("Portable mass or airflow meter drift")
        if quantity(ledger["last"][key]) > ledger["meter"][key] + EPS:
            raise PortableDamageError("Last portable work receipt exceeds total")
    running = ledger["last"]["running"]
    if (not isinstance(running, list) or len(running) != len(set(running))
            or any(name not in FITTED for name in running)):
        raise PortableDamageError("Spurious original portable device operated")
    return True


def survey_portable_damage(ledger, name, *, battery_s, filter_kg=0):
    validate_portable_damage(ledger)
    if name not in FITTED or ledger["units"][name]["survey"] is not None:
        raise PortableDamageError("Original device missing or already surveyed")
    runtime, filt = quantity(battery_s), quantity(filter_kg)
    if (runtime <= 0 or runtime > MAX_BATTERY_S
            or (name in PUMPS and filt != 0)
            or (name in FANS and not 0 < filt <= MAX_FAN_FILTER_KG)):
        raise PortableDamageError("As-found battery or smoke filter invalid")
    result = copy.deepcopy(ledger)
    result["units"][name]["survey"] = {
        "battery_initial_s": runtime, "battery_remaining_s": runtime,
        "filter_kg": filt}
    validate_portable_damage(result)
    return result


def command_portable_damage(ledger, name, action, *, actor, room,
                            known_rooms, pump_stations):
    """Action is take/place/on/off or route:A:grey etc; outer caller checks crew."""
    validate_portable_damage(ledger)
    if name not in FITTED or room not in known_rooms or (
            not isinstance(actor, str) or not actor):
        raise PortableDamageError("No actual portable worksite or operator")
    result = copy.deepcopy(ledger)
    unit = result["units"][name]
    if action == "take":
        if unit["room"] != room or unit["mode"] != "off":
            raise PortableDamageError("Portable must be stopped and physically present")
        if any(u["carrier"] == actor for u in result["units"].values()):
            raise PortableDamageError("Worker already carries a pump or smoke fan")
        unit["room"], unit["carrier"] = None, actor
        unit["route"] = None  # Disconnect hose before moving the pump.
    elif action == "place":
        if unit["carrier"] != actor:
            raise PortableDamageError("Only actual carrier may deploy the unit")
        unit["room"], unit["carrier"] = room, None
    elif action == "off":
        if unit["room"] != room:
            raise PortableDamageError("Local portable unit not present")
        unit["mode"] = "off"
    elif action.startswith("route:"):
        fields = action.split(":")
        if (name not in PUMPS or len(fields) != 3
                or fields[1] not in {"A", "B"}
                or fields[2] not in {"grey", "black"}
                or unit["room"] != room or unit["mode"] != "off"
                or pump_stations.get(fields[1]) != room):
            raise PortableDamageError("Only an attended source wet-work station may attach an isolated pump")
        unit["route"] = fields[1:]
    elif action == "on":
        if unit["room"] != room or unit["carrier"] is not None:
            raise PortableDamageError("No locally deployed portable machine")
        charge = unit["survey"]
        if charge is None or charge["battery_remaining_s"] <= 0:
            raise PortableDamageError("No surveyed residual portable energy")
        if name in PUMPS:
            if (unit["route"] is None
                    or pump_stations.get(unit["route"][0]) != room):
                raise PortableDamageError("No fitted source/discharge hose route")
        elif unit["cumulative_kg"] >= charge["filter_kg"] - EPS:
            raise PortableDamageError("Smoke filter exhausted")
        unit["mode"] = "on"
    else:
        raise PortableDamageError("Unknown portable equipment operation")
    validate_portable_damage(result)
    return result


def step_portable_damage(ledger, seconds, *, now_s, equipment, cells,
                         room_zones, water, wet_ready, pump_stations):
    """Advance real fluid/smoke effects; no phantom gas, wastewater or power."""
    validate_portable_damage(ledger)
    dt, now = quantity(seconds), quantity(now_s)
    if not 0 < dt <= MAX_TICK_S:
        raise PortableDamageError("Unbounded portable-machine tick")
    result = copy.deepcopy(ledger)
    stats = {"pumped_kg": 0.0, "smoke_captured_kg": 0.0,
             "recirculated_m3": 0.0, "running": []}
    for name, original_home in FITTED.items():
        row = result["units"][name]
        if row["last_s"] is not None and now < row["last_s"] + dt - EPS:
            raise PortableDamageError("Portable work replayed")
        row["last_s"] = now
        row["last_kg"] = row["last_m3"] = 0.0
        if row["mode"] != "on":
            continue
        machine = equipment.get(name)
        if machine is None or machine.space_id != original_home:
            raise PortableDamageError("Original machine record moved or missing")
        if machine.condition in BROKEN:
            row["mode"] = "off"  # Explicit manual restart after actual repair.
            continue
        media = row["survey"]
        if media is None:
            raise PortableDamageError("Portable appliance operating without survey")
        runtime = min(dt, media["battery_remaining_s"])
        if runtime <= 0:
            row["mode"] = "off"
            continue
        if name in PUMPS:
            route = row["route"]
            if (route is None or water is None
                    or row["room"] != pump_stations.get(route[0])
                    or not wet_ready.get(route[0] + "_" + route[1], False)):
                continue  # Closed wet isolation, disconnected hose or no source.
            side, stream = route
            src = quantity(water["local"][side][stream])
            target = quantity(water["fixed"][stream])
            if src > LOCAL_CAPACITY_KG[stream] + EPS or (
                    target > FIXED_CAPACITY_KG[stream] + EPS):
                raise PortableDamageError("Source/receiver outside installed capacity")
            moved = min(src, FIXED_CAPACITY_KG[stream] - target,
                        runtime * PUMP_FLOW_KG_S)
            if moved > EPS:
                water["local"][side][stream] -= moved
                water["fixed"][stream] += moved
                row["cumulative_kg"] += moved
                row["last_kg"] = moved
                stats["pumped_kg"] += moved
                media["battery_remaining_s"] -= runtime
                stats["running"].append(name)
        else:
            zone = room_zones.get(row["room"])
            cell = cells.get(zone)
            if cell is None:  # VACUUM or unsurveyed compartments never receive air.
                continue
            for key in ("mass", "smoke", "co2", "oxygen", "volume",
                        "capacity", "energy", "temperature"):
                quantity(cell[key])
            if (cell["volume"] <= 0 or cell["capacity"] <= 0
                    or cell["temperature"] <= 0
                    or cell["smoke"] > cell["mass"] + EPS
                    or cell["co2"] + cell["oxygen"] + cell["smoke"]
                        > cell["mass"] + EPS):
                raise PortableDamageError("Corrupt fitted gas for fan")
            pressure = cell["mass"] * AIR_R * cell["temperature"] / cell["volume"]
            if pressure < 40000.0:
                continue
            available = max(0.0, media["filter_kg"] - row["cumulative_kg"])
            if available <= EPS:
                row["mode"] = "off"
                continue
            airflow = min(cell["volume"], runtime * FAN_AIRFLOW_M3_S)
            # A finite local fan recirculates only the sampled fraction of this
            # same zone's gas; it is NOT a duct to another cell or to vacuum.
            captured = min(cell["smoke"], available,
                           FAN_SMOKE_CAPTURE_KG_S * runtime,
                           cell["smoke"] * airflow / cell["volume"])
            if captured > 0:
                cell["smoke"] -= captured
                cell["mass"] -= captured
                cell["energy"] -= captured * GAS_CP * cell["temperature"]
                cell["temperature"] = cell["energy"] / (
                    cell["capacity"] + cell["mass"] * GAS_CP)
                row["cumulative_kg"] += captured
                row["last_kg"] = captured
                stats["smoke_captured_kg"] += captured
            row["cumulative_m3"] += airflow
            row["last_m3"] = airflow
            stats["recirculated_m3"] += airflow
            media["battery_remaining_s"] -= runtime
            stats["running"].append(name)
    for key in ("pumped_kg", "smoke_captured_kg", "recirculated_m3"):
        result["meter"][key] += stats[key]
    result["last"] = stats
    validate_portable_damage(result)
    return result, cells, water
