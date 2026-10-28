"""G19: finite, per-bed production by the three installed HAB grow systems.

A bed cannot make food from its 'online' indicator. This is a deliberately
bounded game-world conversion of *actually consumed* cultivation water and
one operator-surveyed, already-fitted nutrient charge into wet edible crop.
Water and nutrient masses remain inside the existing mission/dry mass
envelope; staged crop is an internal mass classification, not new ship mass
or a second copy of INV-FOOD-LONG-LEG. No autonomous eating is implied.
"""
from __future__ import annotations

import copy
import math

from world.ship_equipment_services import GROW_BAYS

DAY = 86400.0
MAX_STEP_S = 10.0
YIELD_KG_DAY = 8.5
WATER_KG_PER_CROP_KG = 1.8
NUTRIENT_KG_PER_CROP_KG = 0.012
MAX_COMMISSIONED_NUTRIENT_KG = 10.0
MAX_STANDING_KG = 30.0
MAX_STAGED_KG = 80.0
MAX_SINGLE_HARVEST_KG = 5.0
NOMINAL_WATER_KG_DAY = 35000.0 / 730.0
EPS = 1e-7


class CultivationError(ValueError):
    """The original crop station cannot safely do the requested work."""


def _number(value, lower=0.0, upper=math.inf):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not lower <= value <= upper):
        raise CultivationError("Non-finite or unbounded cultivation quantity")
    return float(value)


def _bed_id(number):
    name = "GROW-" + str(number)
    if type(number) is not int or number not in GROW_BAYS:
        raise CultivationError("Only the three original cultivated HAB bays exist")
    return name


def initial_cultivation():
    return {
        "version": 1,
        "beds": {
            _bed_id(i): {
                "surveyed": False, "initial_nutrient_kg": 0.0,
                "nutrient_kg": 0.0, "nutrient_consumed_kg": 0.0,
                "standing_kg": 0.0, "staged_kg": 0.0,
                "grown_kg": 0.0, "harvested_kg": 0.0,
                "water_applied_kg": 0.0,
            } for i in GROW_BAYS
        },
        "last": {"productive": [], "grown_kg": 0.0,
                 "water_applied_kg": 0.0},
    }


def validate_cultivation(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"version", "beds", "last"}
            or ledger["version"] != 1
            or not isinstance(ledger["beds"], dict)
            or set(ledger["beds"]) != {_bed_id(i) for i in GROW_BAYS}
            or not isinstance(ledger["last"], dict)
            or set(ledger["last"]) != {
                "productive", "grown_kg", "water_applied_kg"}):
        raise CultivationError("Uncommissioned or incompatible cultivated beds")
    for name, bed in ledger["beds"].items():
        if not isinstance(bed, dict) or set(bed) != {
                "surveyed", "initial_nutrient_kg", "nutrient_kg",
                "nutrient_consumed_kg", "standing_kg", "staged_kg",
                "grown_kg", "harvested_kg", "water_applied_kg"}:
            raise CultivationError("Missing one installed grow-bed material account")
        if type(bed["surveyed"]) is not bool:
            raise CultivationError("Unknown physical grow-bed survey")
        for key in ("initial_nutrient_kg", "nutrient_kg",
                    "nutrient_consumed_kg", "standing_kg", "staged_kg",
                    "grown_kg", "harvested_kg", "water_applied_kg"):
            _number(bed[key])
        if (bed["initial_nutrient_kg"] > MAX_COMMISSIONED_NUTRIENT_KG + EPS
                or bed["standing_kg"] > MAX_STANDING_KG + EPS
                or bed["staged_kg"] > MAX_STAGED_KG + EPS
                or (not bed["surveyed"] and any(bed[k] > EPS for k in (
                    "initial_nutrient_kg", "nutrient_kg", "grown_kg")))):
            raise CultivationError("Grow bed exceeds its surveyed physical stores")
        if (not math.isclose(bed["initial_nutrient_kg"],
                             bed["nutrient_kg"] + bed["nutrient_consumed_kg"],
                             rel_tol=1e-9, abs_tol=EPS)
                or not math.isclose(bed["grown_kg"],
                                    bed["standing_kg"] + bed["staged_kg"],
                                    rel_tol=1e-9, abs_tol=EPS)
                or not math.isclose(bed["harvested_kg"], bed["staged_kg"],
                                    rel_tol=1e-9, abs_tol=EPS)
                or not math.isclose(
                    bed["nutrient_consumed_kg"],
                    bed["grown_kg"] * NUTRIENT_KG_PER_CROP_KG,
                    rel_tol=1e-8, abs_tol=EPS)
                or bed["water_applied_kg"] + EPS <
                    bed["grown_kg"] * WATER_KG_PER_CROP_KG):
            raise CultivationError("Crop, nutrient or irrigation custody has diverged")
    last = ledger["last"]
    if (not isinstance(last["productive"], list)
            or last["productive"] != sorted(set(last["productive"]))
            or not set(last["productive"]) <= set(ledger["beds"])):
        raise CultivationError("Nonlocal or uninstalled grow-bed telemetry")
    _number(last["grown_kg"])
    _number(last["water_applied_kg"])
    return True


def survey_existing_nutrients(ledger, *, bay, charge_kg):
    """One bounded attestation of nutrients already inside the fitted skid.

    No resurvey/refill can add material, even after the first charge is spent.
    A future restock must be a separate inventory-debiting custody operation.
    """
    validate_cultivation(ledger)
    name = _bed_id(bay)
    charge = _number(charge_kg, lower=EPS,
                     upper=MAX_COMMISSIONED_NUTRIENT_KG)
    if ledger["beds"][name]["surveyed"]:
        raise CultivationError("This original nutrient charge is already accounted for")
    out = copy.deepcopy(ledger)
    bed = out["beds"][name]
    bed["surveyed"] = True
    bed["initial_nutrient_kg"] = charge
    bed["nutrient_kg"] = charge
    validate_cultivation(out)
    return out


def plan_irrigation(ledger, seconds, *, operating, air_safe):
    """Calculate water demand before the canonical water ledger spends it."""
    validate_cultivation(ledger)
    dt = _number(seconds, upper=MAX_STEP_S)
    if not isinstance(operating, (set, frozenset)) or not isinstance(
            air_safe, (set, frozenset)):
        raise CultivationError("Measured equipment and atmosphere sets required")
    if not operating <= set(ledger["beds"]) or not air_safe <= set(ledger["beds"]):
        raise CultivationError("Attempt to credit an unfitted grow room")
    requested = {}
    for name, bed in ledger["beds"].items():
        if (name not in operating or name not in air_safe
                or not bed["surveyed"]):
            continue
        possible = min(
            YIELD_KG_DAY * dt / DAY,
            max(0.0, MAX_STANDING_KG - bed["standing_kg"]),
            bed["nutrient_kg"] / NUTRIENT_KG_PER_CROP_KG)
        if possible > EPS:
            requested[name] = possible * WATER_KG_PER_CROP_KG
    if sum(requested.values()) > (
            NOMINAL_WATER_KG_DAY * dt / DAY + EPS):
        raise CultivationError("Crop request exceeds original 35t/730d water budget")
    return requested


def step_cultivation(ledger, seconds, *, planned, water_delivered_kg):
    """Grow only the biomass bought by this tick's *actual* water delivery."""
    validate_cultivation(ledger)
    dt = _number(seconds, upper=MAX_STEP_S)
    water = _number(water_delivered_kg)
    if not isinstance(planned, dict) or not set(planned) <= set(
            ledger["beds"]):
        raise CultivationError("Unfitted irrigation allotment")
    expected = 0.0
    for amount in planned.values():
        expected += _number(amount)
    if water > expected + EPS:
        raise CultivationError("No physical water debit covers claimed irrigation")
    out = copy.deepcopy(ledger)
    active = []
    produced = applied = 0.0
    for name, need in sorted(planned.items()):
        if need <= EPS or expected <= EPS:
            continue
        share = min(need, water * need / expected)
        bed = out["beds"][name]
        growth = min(
            YIELD_KG_DAY * dt / DAY,
            max(0.0, MAX_STANDING_KG - bed["standing_kg"]),
            bed["nutrient_kg"] / NUTRIENT_KG_PER_CROP_KG,
            share / WATER_KG_PER_CROP_KG)
        if growth <= 0:
            continue
        used_water = growth * WATER_KG_PER_CROP_KG
        consumed = growth * NUTRIENT_KG_PER_CROP_KG
        bed["standing_kg"] += growth
        bed["grown_kg"] += growth
        bed["nutrient_kg"] -= consumed
        bed["nutrient_consumed_kg"] += consumed
        bed["water_applied_kg"] += used_water
        produced += growth
        applied += used_water
        active.append(name)
    out["last"] = {
        "productive": active, "grown_kg": produced,
        "water_applied_kg": applied,
    }
    validate_cultivation(out)
    return out


def harvest_cultivation(ledger, *, bay):
    """A locally present worker moves finite mature crop into the same bay rack."""
    validate_cultivation(ledger)
    name = _bed_id(bay)
    old = ledger["beds"][name]
    mass = min(MAX_SINGLE_HARVEST_KG, old["standing_kg"],
               max(0.0, MAX_STAGED_KG - old["staged_kg"]))
    if mass <= EPS:
        raise CultivationError("No ready crop or remaining fitted harvest-rack space")
    out = copy.deepcopy(ledger)
    bed = out["beds"][name]
    bed["standing_kg"] -= mass
    bed["staged_kg"] += mass
    bed["harvested_kg"] += mass
    validate_cultivation(out)
    return out, mass
