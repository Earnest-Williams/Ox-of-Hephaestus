"""G19 as-fitted generator-room isolation, finite gas and attended service.

The original rated doors are real pressure boundaries, not new airlocks.
Each previously unclassified generator enclosure retains its own positive,
operator-measured gas charge, outside the canonical 133 pressure cells.
"""
from __future__ import annotations

import copy
import math
import re

from world.ship_propulsion_bay_service import (
    R_AIR, bay_pressure, bay_gas_safe, source_pressure,
)

# Gross as-fitted envelopes from fixed_spine_relayout_v0.5.json.
ROOMS = {
    "GEN-M-ROOM": ("GEN-M", "ACC-GEN-M-ROOM", "TRUNK-A-AFT",
                   "PZ-TRUNK-A-AFT", "ISO-GEN-M", 21 * 7 * 3.8),
    "GEN-A-ROOM": ("GEN-A", "ACC-GEN-A-ROOM", "TRUNK-A-AFT",
                   "PZ-TRUNK-A-AFT", "ISO-GEN-A", 16 * 6.5 * 3.6),
    "GEN-B-ROOM": ("GEN-B", "ACC-GEN-B-ROOM", "TRUNK-B-AFT",
                   "PZ-TRUNK-B-AFT", "ISO-GEN-B", 15 * 6.5 * 3.6),
}
DOORS = {spec[1]: room for room, spec in ROOMS.items()}
MACHINES = {spec[0]: room for room, spec in ROOMS.items()}
FEEDERS = {spec[4]: room for room, spec in ROOMS.items()}
SURVEY_AGE_S = 600.0
MAX_BLEED_KG = 20.0
MAX_DELTA_PA = 2000.0
EPS = 1e-7


class GeneratorBayError(ValueError):
    """An original industrial enclosure is unsurveyed or unfit to enter."""


def _number(value, low=0.0, high=math.inf):
    if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
        raise GeneratorBayError("Unmeasured or impossible generator-room value")
    return float(value)


def initial_generator_bays():
    return {"version": 1, "rooms": {
        room: {"gas": None, "initial_kg": 0.0, "received_kg": 0.0,
               "skin_k": None, "permit": None, "entries": 0,
               "inspections": 0}
        for room in ROOMS}}


def validate_generator_bays(ledger):
    if (not isinstance(ledger, dict) or set(ledger) != {"version", "rooms"}
            or ledger["version"] != 1 or not isinstance(ledger["rooms"], dict)
            or set(ledger["rooms"]) != set(ROOMS)):
        raise GeneratorBayError("Original generator-room custody register corrupted")
    for room, bay in ledger["rooms"].items():
        if (not isinstance(bay, dict) or set(bay) != {
                "gas", "initial_kg", "received_kg", "skin_k",
                "permit", "entries", "inspections"} or any(
                type(bay[k]) is not int or bay[k] < 0
                for k in ("entries", "inspections"))):
            raise GeneratorBayError("Malformed fitted generator-room account")
        _number(bay["initial_kg"])
        _number(bay["received_kg"])
        if bay["gas"] is None:
            if (bay["initial_kg"] != 0 or bay["received_kg"] != 0
                    or bay["skin_k"] is not None or bay["permit"] is not None
                    or bay["entries"] or bay["inspections"]):
                raise GeneratorBayError("Unmeasured bay cannot own gas or a permit")
            continue
        g = bay["gas"]
        if not isinstance(g, dict) or set(g) != {
                "volume_m3", "mass_kg", "oxygen_kg", "co2_kg", "smoke_kg",
                "temperature_k", "sample_s"}:
            raise GeneratorBayError("Unknown measured original gas fields")
        _number(g["volume_m3"], 1.0, ROOMS[room][5])
        _number(g["mass_kg"])
        _number(g["oxygen_kg"])
        _number(g["co2_kg"])
        _number(g["smoke_kg"])
        _number(g["sample_s"])
        _number(g["temperature_k"], 250, 330)
        _number(bay["skin_k"], 250, 400)
        if (g["oxygen_kg"] + g["co2_kg"] + g["smoke_kg"] >
                g["mass_kg"] + EPS or not math.isclose(
                    g["mass_kg"], bay["initial_kg"] + bay["received_kg"],
                    abs_tol=1e-5, rel_tol=1e-10)
                or bay_pressure(g) > 130000):
            raise GeneratorBayError("Generator air mass or composition does not reconcile")
        permit = bay["permit"]
        if permit is not None and (not isinstance(permit, dict)
                                   or set(permit) != {"holder", "issued_s"}
                                   or not isinstance(permit["holder"], str)
                                   or re.fullmatch(r"#[0-9]+", permit["holder"]) is None):
            raise GeneratorBayError("Unidentified person holds generator lockout")
        if permit is not None:
            _number(permit["issued_s"])
    return True


def survey_room(ledger, room, *, volume_m3, pressure_pa, temperature_k,
                oxygen_fraction, co2_fraction, smoke_fraction, skin_k,
                now_s, hatch_closed):
    """Record as-found gas ONCE; later samples can only confirm the ledger."""
    validate_generator_bays(ledger)
    if room not in ROOMS or not hatch_closed:
        raise GeneratorBayError("An unsealed or fictitious generator room cannot be surveyed")
    v = _number(volume_m3, 1.0, ROOMS[room][5])
    p = _number(pressure_pa, 0, 130000)
    t = _number(temperature_k, 250, 330)
    o = _number(oxygen_fraction, 0, 1)
    c = _number(co2_fraction, 0, 1)
    s = _number(smoke_fraction, 0, 1)
    skin = _number(skin_k, 250, 400)
    now = _number(now_s)
    if o + c + s > 1:
        raise GeneratorBayError("Invalid positively sampled gas composition")
    updated = copy.deepcopy(ledger)
    bay = updated["rooms"][room]
    if bay["permit"] is not None:
        raise GeneratorBayError("Cannot resurvey a bay with a work party inside")
    mass = p * v / (R_AIR * t)
    if bay["gas"] is None:
        bay["gas"] = {"volume_m3": v, "mass_kg": mass,
                      "oxygen_kg": mass * o, "co2_kg": mass * c,
                      "smoke_kg": mass * s, "temperature_k": t,
                      "sample_s": now}
        bay["initial_kg"] = mass
    else:
        original = bay["gas"]
        if (now < original["sample_s"]
                or abs(original["volume_m3"] - v) > 1e-4
                or abs(bay_pressure(original) - p) > 150
                or abs(original["temperature_k"] - t) > 1
                or abs(original["oxygen_kg"] / max(original["mass_kg"], EPS) - o) > .002
                or abs(original["co2_kg"] / max(original["mass_kg"], EPS) - c) > .002
                or abs(original["smoke_kg"] / max(original["mass_kg"], EPS) - s) > .00001):
            raise GeneratorBayError("Observed gas disagrees with conserved original charge")
        original["sample_s"] = now
    bay["skin_k"] = skin
    validate_generator_bays(updated)
    return updated


def bleed_room(ledger, room, *, kg, source, now_s, source_safe,
               hatch_closed, generator_stopped, feeder_open):
    """Only a measured, bounded trunk-to-lower-pressure-room equalisation."""
    validate_generator_bays(ledger)
    if room not in ROOMS or not all((source_safe, hatch_closed,
                                    generator_stopped, feeder_open)):
        raise GeneratorBayError("Generator bleed needs physical containment and isolation")
    quantity = _number(kg, EPS, MAX_BLEED_KG)
    now = _number(now_s)
    bay = ledger["rooms"][room]
    if bay["gas"] is None or bay["permit"] is not None:
        raise GeneratorBayError("No safe unattended surveyed generator atmosphere")
    gas = bay["gas"]
    if now < gas["sample_s"] or now - gas["sample_s"] > SURVEY_AGE_S:
        raise GeneratorBayError("Sealed generator-room sample is stale")
    src = {k: _number(source[k]) for k in (
        "mass_kg", "oxygen_kg", "co2_kg", "smoke_kg",
        "temperature_k", "volume_m3")}
    if not (src["mass_kg"] > quantity * 10
            and src["oxygen_kg"] + src["co2_kg"] + src["smoke_kg"] <= src["mass_kg"]):
        raise GeneratorBayError("Trunk has insufficient clean finite breathing gas")
    differential = source_pressure(src) - bay_pressure(gas)
    if differential <= MAX_DELTA_PA:
        raise GeneratorBayError("No physical upstream pressure to meter into generator enclosure")
    equilibrium = differential / (R_AIR * (
        src["temperature_k"] / src["volume_m3"] +
        gas["temperature_k"] / gas["volume_m3"]))
    if quantity > equilibrium + EPS:
        raise GeneratorBayError("Requested gas flow crosses actual pressure equilibrium")
    updated = copy.deepcopy(ledger)
    new_g = updated["rooms"][room]["gas"]
    prior = new_g["mass_kg"]
    new_g["temperature_k"] = (
        new_g["temperature_k"] * prior + src["temperature_k"] * quantity
    ) / (prior + quantity)
    new_g["mass_kg"] += quantity
    for species in ("oxygen", "co2", "smoke"):
        amount = quantity * src[species + "_kg"] / src["mass_kg"]
        new_g[species + "_kg"] += amount
        src[species + "_kg"] -= amount
    src["mass_kg"] -= quantity
    new_g["sample_s"] = now
    updated["rooms"][room]["received_kg"] += quantity
    validate_generator_bays(updated)
    return updated, src


def entry_ready(ledger, room, *, source_pa, source_safe, hatch_sound,
                feeder_open, generator_stopped, now_s, permit_required=True):
    validate_generator_bays(ledger)
    if room not in ROOMS:
        return False
    bay = ledger["rooms"][room]
    gas = bay["gas"]
    if (gas is None or not all((source_safe, hatch_sound,
                               feeder_open, generator_stopped))
            or not bay_gas_safe(gas) or bay["skin_k"] > 315
            or abs(_number(source_pa) - bay_pressure(gas)) > MAX_DELTA_PA
            or _number(now_s) < gas["sample_s"]):
        return False
    return (bay["permit"] is not None if permit_required
            else _number(now_s) - gas["sample_s"] <= SURVEY_AGE_S)


def secure_room(ledger, room, worker, now_s):
    validate_generator_bays(ledger)
    if room not in ROOMS or ledger["rooms"][room]["permit"] is not None or (
            not isinstance(worker, str) or re.fullmatch(r"#[0-9]+", worker) is None):
        raise GeneratorBayError("No exclusive original generator service permit")
    updated = copy.deepcopy(ledger)
    updated["rooms"][room]["permit"] = {"holder": worker, "issued_s": _number(now_s)}
    validate_generator_bays(updated)
    return updated


def enter_or_inspect(ledger, room, worker, *, inspect=False):
    validate_generator_bays(ledger)
    if room not in ROOMS or (ledger["rooms"][room]["permit"] or {}).get("holder") != worker:
        raise GeneratorBayError("Only holder of the actual generator service key may attend")
    updated = copy.deepcopy(ledger)
    updated["rooms"][room]["inspections" if inspect else "entries"] += 1
    validate_generator_bays(updated)
    return updated


def release_room(ledger, room, worker, *, hatch_closed, empty, repairs_active):
    validate_generator_bays(ledger)
    if (room not in ROOMS or not hatch_closed or not empty or repairs_active
            or (ledger["rooms"][room]["permit"] or {}).get("holder") != worker):
        raise GeneratorBayError("Hatch, occupied worker or unfinished repair holds physical lockout")
    updated = copy.deepcopy(ledger)
    updated["rooms"][room]["permit"] = None
    validate_generator_bays(updated)
    return updated
