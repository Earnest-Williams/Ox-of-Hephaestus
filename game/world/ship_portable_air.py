"""G19: four original movable emergency CO2 scrubbers.

The original machine record remains at its as-built stowage address. A separate
durable possession ledger follows the physical unit when its carrying engineer
moves through existing Evennia exits. The battery and fitted sorbent must be
surveyed ONCE as-found; neither refills from the ship's bus.
"""
from __future__ import annotations

import copy
import math

from world.ship_crew_exposure import OXYGEN_KG_S

STOWAGE = {
    "PORT-SCRUB-01": "TRUNK-A-BOW",
    "PORT-SCRUB-02": "ENG-LOCKER",
    "PORT-SCRUB-03": "F2-BAY",
    "PORT-SCRUB-04": "TRUNK-B-AFT",
}
BROKEN = frozenset({"failed", "faulted", "jammed", "severed", "destroyed"})
MAX_MEDIA_KG = 100.0
MAX_BATTERY_S = 24 * 3600.0
MAX_STEP_S = 10.0
CO2_CAPTURE_KG_S = 2 * OXYGEN_KG_S
GAS_CP = 1.0
R_AIR = 287.05
EPS = 1e-7


class PortableAirError(ValueError):
    """Portable appliance identity, custody, energy or gas is unsafe."""


def finite(value, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise PortableAirError("Invalid finite portable-air quantity")
    return float(value)


def initial_portable_air():
    return {
        "version": 1,
        "units": {
            name: {"room": home, "carrier": None, "mode": "off",
                   "survey": None, "captured_kg": 0.0,
                   "last_capture_kg": 0.0, "last_s": None}
            for name, home in STOWAGE.items()
        },
        "meter": {"captured_kg": 0.0},
        "last": {"captured_kg": 0.0, "running": []},
    }


def validate_portable_air(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"version", "units", "meter", "last"}
            or ledger["version"] != 1 or type(ledger["version"]) is not int
            or not isinstance(ledger["units"], dict)
            or set(ledger["units"]) != set(STOWAGE)
            or set(ledger["meter"]) != {"captured_kg"}
            or set(ledger["last"]) != {"captured_kg", "running"}):
        raise PortableAirError("Four original portable scrubber identities lost")
    carriers = set()
    total = 0.0
    for name, unit in ledger["units"].items():
        if (not isinstance(unit, dict) or set(unit) != {
                "room", "carrier", "mode", "survey", "captured_kg",
                "last_capture_kg", "last_s"} or unit["mode"] not in ("off", "on")):
            raise PortableAirError("Invalid original portable scrubber state")
        room, carrier = unit["room"], unit["carrier"]
        if (room is None) == (carrier is None):
            raise PortableAirError("Portable equipment neither deployed nor carried")
        if room is not None and (not isinstance(room, str) or not room):
            raise PortableAirError("Invalid portable stowage destination")
        if carrier is not None:
            if (not isinstance(carrier, str) or not carrier
                    or carrier in carriers or unit["mode"] != "off"):
                raise PortableAirError("One worker cannot carry multiple running units")
            carriers.add(carrier)
        captured = finite(unit["captured_kg"])
        last_capture = finite(unit["last_capture_kg"])
        if captured + EPS < last_capture:
            raise PortableAirError("Portable receiver history exceeds captured mass")
        survey = unit["survey"]
        if survey is None:
            if captured or last_capture or unit["mode"] != "off":
                raise PortableAirError("Unsurveyed portable media credited")
        else:
            if not isinstance(survey, dict) or set(survey) != {
                    "media_kg", "battery_initial_s", "battery_remaining_s"}:
                raise PortableAirError("Portable battery/media survey missing")
            media = finite(survey["media_kg"])
            capacity = finite(survey["battery_initial_s"])
            runtime = finite(survey["battery_remaining_s"])
            if (media <= 0 or media > MAX_MEDIA_KG or capacity <= 0
                    or capacity > MAX_BATTERY_S or runtime > capacity + EPS
                    or captured > media + EPS):
                raise PortableAirError("Sorbent or battery output exceeds as-found charge")
        if unit["last_s"] is not None:
            finite(unit["last_s"])
        elif captured or last_capture:
            raise PortableAirError("Portable capture has no elapsed-time provenance")
        total += captured
    if not math.isclose(finite(ledger["meter"]["captured_kg"]), total,
                        abs_tol=1e-6, rel_tol=1e-10):
        raise PortableAirError("Portable CO2 mass not retained in its receivers")
    if (not isinstance(ledger["last"]["running"], list)
            or len(ledger["last"]["running"]) != len(set(ledger["last"]["running"]))
            or any(name not in STOWAGE for name in ledger["last"]["running"])
            or finite(ledger["last"]["captured_kg"]) >
               ledger["meter"]["captured_kg"] + EPS):
        raise PortableAirError("Portable work meter inconsistent")
    return True


def survey_portable_air(ledger, name, *, media_kg, battery_s):
    validate_portable_air(ledger)
    if name not in STOWAGE or ledger["units"][name]["survey"] is not None:
        raise PortableAirError("Original portable survey already completed")
    media, runtime = finite(media_kg), finite(battery_s)
    if not (0 < media <= MAX_MEDIA_KG and 0 < runtime <= MAX_BATTERY_S):
        raise PortableAirError("Unsupported finite as-found cartridge or battery")
    updated = copy.deepcopy(ledger)
    updated["units"][name]["survey"] = {
        "media_kg": media, "battery_initial_s": runtime,
        "battery_remaining_s": runtime}
    validate_portable_air(updated)
    return updated


def command_portable_air(ledger, name, action, *, actor, room, known_rooms):
    """One local custody/control action; Evennia verifies the worker's location."""
    validate_portable_air(ledger)
    if name not in STOWAGE or action not in {"take", "place", "on", "off"}:
        raise PortableAirError("No fitted portable scrubber operation")
    if not isinstance(actor, str) or not actor or room not in known_rooms:
        raise PortableAirError("Authenticated worker and installed room required")
    updated = copy.deepcopy(ledger)
    row = updated["units"][name]
    if action == "take":
        if row["room"] != room or row["mode"] != "off":
            raise PortableAirError("Only a switched-off unit at this location can be lifted")
        if any(other["carrier"] == actor for other in updated["units"].values()):
            raise PortableAirError("This worker already carries a portable scrubber")
        row["room"], row["carrier"] = None, actor
    elif action == "place":
        if row["carrier"] != actor:
            raise PortableAirError("Only the unit's actual carrier can deploy it")
        row["room"], row["carrier"] = room, None
    else:
        if row["room"] != room or row["carrier"] is not None:
            raise PortableAirError("The appliance is not at the attended worksite")
        if action == "on":
            charge = row["survey"]
            if (charge is None or charge["battery_remaining_s"] <= 0
                    or row["captured_kg"] >= charge["media_kg"]):
                raise PortableAirError("No surveyed finite usable portable media/charge")
            row["mode"] = "on"
        else:
            row["mode"] = "off"
    validate_portable_air(updated)
    return updated


def step_portable_air(ledger, seconds, *, now_s, equipment, room_zones, cells):
    """Conserve genuine CO2 in finite carried cartridges, on a 10s clock."""
    validate_portable_air(ledger)
    dt, now = finite(seconds), finite(now_s)
    if not 0 < dt <= MAX_STEP_S:
        raise PortableAirError("Portable air requires bounded physical clock steps")
    updated = copy.deepcopy(ledger)
    captured_this_step = 0.0
    running = []
    for name, home in STOWAGE.items():
        unit = updated["units"][name]
        if unit["last_s"] is not None and now < unit["last_s"] + dt - EPS:
            raise PortableAirError("Portable air clock interval replayed")
        unit["last_s"] = now
        unit["last_capture_kg"] = 0.0
        if unit["mode"] != "on":
            continue
        original = equipment.get(name)
        if original is None or original.space_id != home:
            raise PortableAirError("Original as-fitted appliance identity displaced")
        if original.condition in BROKEN:
            continue
        zone = room_zones.get(unit["room"])
        cell = cells.get(zone)
        if cell is None:
            continue  # No invented atmosphere at an unclassified/VACUUM site.
        for key in ("mass", "co2", "oxygen", "volume", "temperature", "energy", "capacity"):
            finite(cell[key])
        if (cell["mass"] <= 0 or cell["volume"] <= 0
                or cell["temperature"] <= 0 or cell["capacity"] <= 0
                or cell["co2"] > cell["mass"] + EPS
                or cell["oxygen"] > cell["mass"] + EPS):
            raise PortableAirError("Invalid original pressure-cell gas")
        pressure = cell["mass"] * R_AIR * cell["temperature"] / cell["volume"]
        if pressure < 40000.0:
            continue
        charge = unit["survey"]
        if charge is None:
            raise PortableAirError("Unsupplied portable appliance operating")
        duration = min(dt, charge["battery_remaining_s"])
        remaining_media = max(0.0, charge["media_kg"] - unit["captured_kg"])
        if duration <= 0 or remaining_media <= 0:
            continue
        captured = min(cell["co2"], remaining_media, CO2_CAPTURE_KG_S * duration)
        if captured:
            cell["co2"] -= captured
            cell["mass"] -= captured
            cell["energy"] -= captured * GAS_CP * cell["temperature"]
            cell["temperature"] = cell["energy"] / (
                cell["capacity"] + cell["mass"] * GAS_CP)
            unit["captured_kg"] += captured
            unit["last_capture_kg"] = captured
            captured_this_step += captured
        charge["battery_remaining_s"] -= duration
        running.append(name)
    updated["meter"]["captured_kg"] += captured_this_step
    updated["last"] = {"captured_kg": captured_this_step, "running": running}
    validate_portable_air(updated)
    return updated, cells
