"""G19 finite food custody, real room logistics, kitchen, waste and nutrition.

The installed INV-FOOD-LONG-LEG remains the authority for ALL unconsumed
departure provisions, including cooked portions and crew-carried packages.
Fresh food is sourced only from the individually metered cultivation ledger.
Every transition returns new copies and leaves the authoritative transaction
and crew's physical location checks to continuous_ship_physics.
"""
from __future__ import annotations

import copy
import math
import re

from world.ship_equipment_services import GROW_BAYS

DAY = 86400.0
STORES = {
    "STORE-FOOD-AFT": 33790.0,
    **{f"HAB-{i:02d}-FOOD-STORES": 5750.0 for i in (1, 3, 5, 7)},
}
NUTRIENT_STORES = frozenset({
    "SPARES-CENTRAL", "HAB-01-SPARES", "HAB-03-SPARES",
    "HAB-05-SPARES", "HAB-07-SPARES", "HAB-08-SPARES",
    "STORE-CRIT-SPARES", "TOOL-CRIB", "SHOP-IMMEDIATE-STOCK",
})
GALLEY = "HAB-02-GALLEY"
MESS = "HAB-02-MESS"
WASTE_RECEIVERS = {"HAB-06-ECLSS-A": "A", "HAB-08-ECLSS-B": "B"}
KINDS = ("dry", "conventional", "fresh")
CALORIES = {"dry": 3000.0, "conventional": 1165.0, "fresh": 1000.0}
RECIPES = {
    "mixed": {"dry": 0.08, "conventional": 0.40, "fresh": 0.20,
              "water": 0.12},
    "stored": {"dry": 0.10, "conventional": 0.52, "fresh": 0.0,
               "water": 0.12},
    "emergency": {"dry": 0.30, "conventional": 0.0, "fresh": 0.0,
                  "water": 0.50},
    "vegetable": {"dry": 0.12, "conventional": 0.22, "fresh": 0.32,
                  "water": 0.08},
}
PREPARATION_LOSS = 0.04
MAX_CARRY_KG = 5.0
MAX_MEALS_PER_SITE = 160
MAX_STORED_MEAL_HOURS = 36.0
MAX_CROP_HOLD_HOURS = 96.0
INITIAL_DRY_KG = 24820.0
INITIAL_CONVENTIONAL_KG = 31970.0
EPS = 1e-6
CREW_DAILY_KCAL = 2550.0
MAX_ENERGY_KCAL = 2.0 * CREW_DAILY_KCAL


class FoodError(ValueError):
    """Missing food, unsafe custody, impossible conservation or local service."""


def _q(value, maximum=math.inf):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < 0 or value > maximum):
        raise FoodError("Nonphysical food or nutrient quantity")
    return float(value)


def _actor(dbref):
    if not isinstance(dbref, str) or re.fullmatch(r"#[0-9]+", dbref) is None:
        raise FoodError("Food must be carried or eaten by a real crew identity")
    return dbref


def _ingredients():
    return {k: 0.0 for k in KINDS}


def _carrier():
    return {"food": _ingredients(), "nutrient_kg": 0.0,
            "waste_kg": 0.0, "meal": None}


def _mass(food):
    return sum(food.values())


def _meal_mass(meal):
    return sum(meal["food"].values()) + meal["water_kg"]


def _waste_rooms():
    return sorted(set(STORES) | {GALLEY, MESS} |
                  set(GROW_BAYS.values()))


def initial_food(*, inventory_kg=INITIAL_DRY_KG + INITIAL_CONVENTIONAL_KG):
    if abs(_q(inventory_kg) - INITIAL_DRY_KG -
           INITIAL_CONVENTIONAL_KG) > EPS:
        raise FoodError("Initial food survey differs from original finite manifest")
    total = INITIAL_DRY_KG + INITIAL_CONVENTIONAL_KG
    return {
        "version": 1,
        "stores": {
            room: {
                "dry": mass * INITIAL_DRY_KG / total,
                "conventional": mass * INITIAL_CONVENTIONAL_KG / total,
            } for room, mass in STORES.items()
        },
        "carried": {}, "galley_raw": _ingredients(),
        "meals": {GALLEY: [], MESS: []},
        "waste": {room: 0.0 for room in _waste_rooms()},
        "nutrient_certified": {},
        "crew": {},
        "meter": {
            "stored_eaten_kg": 0.0, "stored_wasted_kg": 0.0,
            "fresh_collected_kg": 0.0, "fresh_eaten_kg": 0.0,
            "fresh_wasted_kg": 0.0, "waste_deposited_kg": 0.0,
            "water_used_kg": 0.0, "water_eaten_kg": 0.0,
            "water_wasted_kg": 0.0,
            "nutrient_issued_kg": 0.0, "nutrient_installed_kg": 0.0,
            "calories_eaten": 0.0, "meals_prepared": 0,
            "meals_consumed": 0, "meals_spoiled": 0,
        },
        "last": {"spoilage_kg": 0.0, "hungry": [], "impaired": [],
                 "incapacitated": []},
    }


def unconsumed_stored_kg(food):
    total = sum(_mass(row) for row in food["stores"].values())
    total += food["galley_raw"]["dry"] + food["galley_raw"]["conventional"]
    for carrier in food["carried"].values():
        total += carrier["food"]["dry"] + carrier["food"]["conventional"]
        if carrier["meal"] is not None:
            total += sum(carrier["meal"]["food"][k]
                         for k in ("dry", "conventional"))
    for meals in food["meals"].values():
        total += sum(m["food"]["dry"] + m["food"]["conventional"]
                     for m in meals)
    return total


def _fresh_held(food):
    total = food["galley_raw"]["fresh"]
    for carrier in food["carried"].values():
        total += carrier["food"]["fresh"]
        if carrier["meal"] is not None:
            total += carrier["meal"]["food"]["fresh"]
    total += sum(m["food"]["fresh"] for ms in food["meals"].values()
                 for m in ms)
    return total


def _meal_water_held(food):
    return (sum(m["water_kg"] for ms in food["meals"].values()
                for m in ms)
            + sum(c["meal"]["water_kg"] for c in food["carried"].values()
                  if c["meal"] is not None))


def validate_food(food, *, inventory_kg=None):
    if (not isinstance(food, dict) or set(food) != {
            "version", "stores", "carried", "galley_raw", "meals",
            "waste", "nutrient_certified", "crew", "meter", "last"}
            or food["version"] != 1 or set(food["stores"]) != set(STORES)
            or set(food["meals"]) != {GALLEY, MESS}
            or set(food["waste"]) != set(_waste_rooms())
            or set(food["galley_raw"]) != set(KINDS)):
        raise FoodError("Unknown original food store or incomplete food ledger")
    for room, row in food["stores"].items():
        if set(row) != {"dry", "conventional"}:
            raise FoodError("Unclassified stored provisions")
        if sum(_q(v) for v in row.values()) > STORES[room] + EPS:
            raise FoodError("Original food compartment overfilled")
    for amount in food["galley_raw"].values():
        _q(amount)
    for room, amount in food["waste"].items():
        _q(amount)
    for actor, carrier in food["carried"].items():
        _actor(actor)
        if set(carrier) != {"food", "nutrient_kg", "waste_kg", "meal"} or (
                set(carrier["food"]) != set(KINDS)):
            raise FoodError("Unknown issued food package")
        for amount in carrier["food"].values():
            _q(amount)
        _q(carrier["nutrient_kg"])
        _q(carrier["waste_kg"])
        if carrier["meal"] is not None:
            _validate_meal(carrier["meal"])
        if (_mass(carrier["food"]) + carrier["nutrient_kg"] +
                carrier["waste_kg"] + (
                    _meal_mass(carrier["meal"])
                    if carrier["meal"] else 0.0) > MAX_CARRY_KG + EPS):
            raise FoodError("Person cannot carry excessive food or refuse")
    for site, meals in food["meals"].items():
        if not isinstance(meals, list) or len(meals) > MAX_MEALS_PER_SITE:
            raise FoodError("Installed galley or mess rack full")
        for meal in meals:
            _validate_meal(meal)
    if not isinstance(food["nutrient_certified"], dict) or (
            not set(food["nutrient_certified"]) <= NUTRIENT_STORES):
        raise FoodError("Unverified or imaginary nutrient supply room")
    for amount in food["nutrient_certified"].values():
        _q(amount)
    for ref, row in food["crew"].items():
        _actor(ref)
        if set(row) != {"balance_kcal", "eaten_kcal", "meals"}:
            raise FoodError("Unrecognised individual nutritional history")
        _q(row["eaten_kcal"])
        if type(row["meals"]) is not int or row["meals"] < 0:
            raise FoodError("Impossible individual meal count")
        energy = row["balance_kcal"]
        if (type(energy) not in (float, int) or not math.isfinite(energy)
                or not -CREW_DAILY_KCAL * 100 <= energy <= MAX_ENERGY_KCAL):
            raise FoodError("Impossible hunger history")
    m = food["meter"]
    if set(m) != {
            "stored_eaten_kg", "stored_wasted_kg", "fresh_collected_kg",
            "fresh_eaten_kg", "fresh_wasted_kg", "waste_deposited_kg",
            "water_used_kg", "water_eaten_kg", "water_wasted_kg",
            "nutrient_issued_kg", "nutrient_installed_kg",
            "calories_eaten", "meals_prepared", "meals_consumed",
            "meals_spoiled"}:
        raise FoodError("Missing finite mass or meal accounting")
    for key, amount in m.items():
        if key in {"meals_prepared", "meals_consumed", "meals_spoiled"}:
            if type(amount) is not int or amount < 0:
                raise FoodError("Invalid meal count")
        else:
            _q(amount)
    if (m["meals_consumed"] + m["meals_spoiled"] >
            m["meals_prepared"]):
        raise FoodError("More meals consumed or spoiled than prepared")
    if not math.isclose(
            INITIAL_DRY_KG + INITIAL_CONVENTIONAL_KG,
            unconsumed_stored_kg(food) + m["stored_eaten_kg"] +
            m["stored_wasted_kg"], abs_tol=0.0003):
        raise FoodError("Original stored food was duplicated or destroyed")
    if not math.isclose(
            m["fresh_collected_kg"],
            _fresh_held(food) + m["fresh_eaten_kg"] +
            m["fresh_wasted_kg"], abs_tol=0.0003):
        raise FoodError("Wet crop cannot appear without a real harvest")
    if not math.isclose(
            m["stored_wasted_kg"] + m["fresh_wasted_kg"],
            sum(food["waste"].values()) +
            sum(c["waste_kg"] for c in food["carried"].values()) +
            m["waste_deposited_kg"], abs_tol=0.0003):
        raise FoodError("Discarded food has no classified physical receiver")
    if not math.isclose(
            m["water_used_kg"], _meal_water_held(food) +
            m["water_eaten_kg"] + m["water_wasted_kg"], abs_tol=0.0003):
        raise FoodError("Kitchen rehydration water has disappeared")
    if not math.isclose(
            m["nutrient_issued_kg"],
            m["nutrient_installed_kg"] +
            sum(c["nutrient_kg"] for c in food["carried"].values()),
            abs_tol=0.0003):
        raise FoodError("Issued nutrient pack is duplicated or lost")
    if inventory_kg is not None and not math.isclose(
            _q(inventory_kg), unconsumed_stored_kg(food),
            abs_tol=0.0003):
        raise FoodError("Canonical stored-food inventory disagrees with physical custody")
    last = food["last"]
    if set(last) != {"spoilage_kg", "hungry", "impaired", "incapacitated"}:
        raise FoodError("Unknown last food casualty reading")
    _q(last["spoilage_kg"])
    for name in ("hungry", "impaired", "incapacitated"):
        if (not isinstance(last[name], list) or
                last[name] != sorted(set(last[name])) or
                not set(last[name]) <= set(food["crew"])):
            raise FoodError("Unfitted nutritional casualty")
    return True


def _validate_meal(meal):
    if set(meal) != {"food", "water_kg", "kcal", "age_s"} or (
            set(meal["food"]) != set(KINDS)):
        raise FoodError("Nonphysical prepared meal")
    for value in meal["food"].values():
        _q(value)
    _q(meal["water_kg"])
    _q(meal["kcal"])
    _q(meal["age_s"])
    if not math.isclose(
            meal["kcal"], sum(meal["food"][k] * CALORIES[k]
                              for k in KINDS), abs_tol=0.001):
        raise FoodError("Prepared calories differ from actual ingredients")


def _ensure_carrier(food, actor):
    return food["carried"].setdefault(_actor(actor), _carrier())


def _capacity(carrier):
    return MAX_CARRY_KG - (_mass(carrier["food"]) +
                           carrier["nutrient_kg"] + carrier["waste_kg"] +
                           (_meal_mass(carrier["meal"]) if carrier["meal"] else 0))


def take_stored(food, *, actor, room, kind, kg):
    validate_food(food)
    amount = _q(kg, MAX_CARRY_KG)
    if room not in STORES or kind not in {"dry", "conventional"} or amount <= 0:
        raise FoodError("Only the original food store can issue this ration")
    out = copy.deepcopy(food)
    carrier = _ensure_carrier(out, actor)
    if (amount > _capacity(carrier) + EPS or
            out["stores"][room][kind] + EPS < amount):
        raise FoodError("No finite stock or personal carrying capacity")
    out["stores"][room][kind] -= amount
    carrier["food"][kind] += amount
    validate_food(out)
    return out


def collect_crop(food, cultivation, *, actor, bay, kg):
    from world.ship_food_cultivation import validate_cultivation
    validate_food(food)
    validate_cultivation(cultivation)
    amount = _q(kg, MAX_CARRY_KG)
    if type(bay) is not int or bay not in GROW_BAYS or amount <= 0:
        raise FoodError("Only fitted grow-room racks contain harvested crops")
    out, beds = copy.deepcopy(food), copy.deepcopy(cultivation)
    carrier = _ensure_carrier(out, actor)
    name = f"GROW-{bay}"
    bed = beds["beds"][name]
    if amount > _capacity(carrier) + EPS or amount > bed["staged_kg"] + EPS:
        raise FoodError("No staged harvested crop or carrying capacity")
    bed["staged_kg"] -= amount
    bed["released_kg"] += amount
    carrier["food"]["fresh"] += amount
    out["meter"]["fresh_collected_kg"] += amount
    validate_cultivation(beds)
    validate_food(out)
    return out, beds


def deliver_to_galley(food, *, actor):
    validate_food(food)
    out = copy.deepcopy(food)
    carrier = _ensure_carrier(out, actor)
    if _mass(carrier["food"]) <= EPS:
        raise FoodError("No carried real food to deliver")
    for kind in KINDS:
        out["galley_raw"][kind] += carrier["food"][kind]
        carrier["food"][kind] = 0.0
    validate_food(out)
    return out


def prepare_meal(food, *, recipe, water_delivered_kg):
    validate_food(food)
    if recipe not in RECIPES:
        raise FoodError("Unknown recipe or nonexistent galley plant")
    spec = RECIPES[recipe]
    water = _q(water_delivered_kg)
    if not math.isclose(water, spec["water"], abs_tol=EPS):
        raise FoodError("No actual water charge for kitchen preparation")
    out = copy.deepcopy(food)
    if len(out["meals"][GALLEY]) >= MAX_MEALS_PER_SITE:
        raise FoodError("Local galley food rack already full")
    for kind in KINDS:
        if out["galley_raw"][kind] + EPS < spec[kind]:
            raise FoodError("No physical ingredients for selected meal")
    cooked = {}
    for kind in KINDS:
        out["galley_raw"][kind] -= spec[kind]
        eaten = spec[kind] * (1.0 - PREPARATION_LOSS)
        cooked[kind] = eaten
        spoiled = spec[kind] - eaten
        if kind == "fresh":
            out["meter"]["fresh_wasted_kg"] += spoiled
        else:
            out["meter"]["stored_wasted_kg"] += spoiled
        out["waste"][GALLEY] += spoiled
    meal = {
        "food": cooked, "water_kg": water,
        "kcal": sum(cooked[k] * CALORIES[k] for k in KINDS),
        "age_s": 0.0,
    }
    out["meals"][GALLEY].append(meal)
    out["meter"]["meals_prepared"] += 1
    out["meter"]["water_used_kg"] += water
    validate_food(out)
    return out


def take_meal(food, *, actor):
    validate_food(food)
    out = copy.deepcopy(food)
    carrier = _ensure_carrier(out, actor)
    if not out["meals"][GALLEY] or carrier["meal"] is not None:
        raise FoodError("No fitted kitchen serving or hands already full")
    meal = out["meals"][GALLEY][0]
    if _meal_mass(meal) > _capacity(carrier) + EPS:
        raise FoodError("Crew cannot carry the actual serving")
    carrier["meal"] = out["meals"][GALLEY].pop(0)
    validate_food(out)
    return out


def set_meal_in_mess(food, *, actor):
    validate_food(food)
    out = copy.deepcopy(food)
    carrier = _ensure_carrier(out, actor)
    if carrier["meal"] is None or len(out["meals"][MESS]) >= MAX_MEALS_PER_SITE:
        raise FoodError("No served meal or mess serving rack is full")
    out["meals"][MESS].append(carrier["meal"])
    carrier["meal"] = None
    validate_food(out)
    return out


def eat_meal(food, *, actor, room):
    validate_food(food)
    if room not in {GALLEY, MESS}:
        raise FoodError("Only an attended actual mess or galley serves meals")
    out = copy.deepcopy(food)
    carrier = _ensure_carrier(out, actor)
    if carrier["meal"] is not None:
        meal = carrier["meal"]
        carrier["meal"] = None
    elif out["meals"][room]:
        meal = out["meals"][room].pop(0)
    else:
        raise FoodError("No prepared meal physically held at this station")
    for kind in KINDS:
        key = "fresh_eaten_kg" if kind == "fresh" else "stored_eaten_kg"
        out["meter"][key] += meal["food"][kind]
    out["meter"]["water_eaten_kg"] += meal["water_kg"]
    out["meter"]["calories_eaten"] += meal["kcal"]
    out["meter"]["meals_consumed"] += 1
    history = out["crew"].setdefault(
        _actor(actor), {"balance_kcal": 0.0, "eaten_kcal": 0.0, "meals": 0})
    history["balance_kcal"] = min(
        MAX_ENERGY_KCAL, history["balance_kcal"] + meal["kcal"])
    history["eaten_kcal"] += meal["kcal"]
    history["meals"] += 1
    validate_food(out)
    return out, meal["kcal"]


def _spoil_meal(food, room, meal):
    for kind in KINDS:
        key = "fresh_wasted_kg" if kind == "fresh" else "stored_wasted_kg"
        food["meter"][key] += meal["food"][kind]
        food["waste"][room] += meal["food"][kind]
    food["meter"]["water_wasted_kg"] += meal["water_kg"]
    food["meter"]["meals_spoiled"] += 1


def step_food(food, seconds, *, temperatures_k, living_crew=()):
    """Account genuine temperature exposure, cooked shelf life, and hunger.

    No new stock, catering electricity, air or worker is inferred from a timer.
    Only registered living crew accrue hunger; dead/unknown crew are excluded.
    """
    validate_food(food)
    dt = _q(seconds, 10.0)
    if not isinstance(temperatures_k, dict):
        raise FoodError("Real room thermal readings required for spoilage")
    if set(temperatures_k) != set(STORES) | {GALLEY, MESS}:
        raise FoodError("Missing actual food-store temperature")
    crew = set()
    for ref in living_crew:
        crew.add(_actor(ref))
    out = copy.deepcopy(food)
    last_spoiled = 0.0
    for room, store in out["stores"].items():
        temp = _q(temperatures_k[room], 1000.0)
        warm = temp > 303.15 or temp < 270.0
        for kind in ("dry", "conventional"):
            per_day = (0.003 if kind == "dry" else 0.04) if warm else (
                0.000003 if kind == "dry" else 0.000020)
            lost = min(store[kind], store[kind] * per_day * dt / DAY)
            store[kind] -= lost
            out["meter"]["stored_wasted_kg"] += lost
            out["waste"][room] += lost
            last_spoiled += lost
    for room, meals in out["meals"].items():
        hot = _q(temperatures_k[room], 1000.0) > 303.15
        maximum_age = (6 if hot else MAX_STORED_MEAL_HOURS) * 3600
        remaining = []
        for meal in meals:
            meal["age_s"] += dt
            if meal["age_s"] > maximum_age:
                _spoil_meal(out, room, meal)
                last_spoiled += sum(meal["food"].values())
            else:
                remaining.append(meal)
        out["meals"][room] = remaining
    # Carried meals age and become refuse in the worker's custody.
    for carrier in out["carried"].values():
        meal = carrier["meal"]
        if meal is None:
            continue
        meal["age_s"] += dt
        if meal["age_s"] > MAX_STORED_MEAL_HOURS * 3600:
            for kind in KINDS:
                key = "fresh_wasted_kg" if kind == "fresh" else "stored_wasted_kg"
                out["meter"][key] += meal["food"][kind]
                carrier["waste_kg"] += meal["food"][kind]
                last_spoiled += meal["food"][kind]
            out["meter"]["water_wasted_kg"] += meal["water_kg"]
            out["meter"]["meals_spoiled"] += 1
            carrier["meal"] = None
    for ref in crew:
        row = out["crew"].setdefault(
            ref, {"balance_kcal": 0.0, "eaten_kcal": 0.0, "meals": 0})
        row["balance_kcal"] = max(
            -CREW_DAILY_KCAL * 100,
            row["balance_kcal"] - CREW_DAILY_KCAL * dt / DAY)
    out["last"] = {
        "spoilage_kg": last_spoiled,
        "hungry": sorted(r for r in crew
                         if out["crew"][r]["balance_kcal"] < -CREW_DAILY_KCAL),
        "impaired": sorted(r for r in crew
                          if out["crew"][r]["balance_kcal"] < -3 * CREW_DAILY_KCAL),
        "incapacitated": sorted(r for r in crew
                               if out["crew"][r]["balance_kcal"] < -8 * CREW_DAILY_KCAL),
    }
    validate_food(out)
    return out


def take_waste(food, *, actor, room, kg):
    validate_food(food)
    amount = _q(kg, MAX_CARRY_KG)
    if room not in food["waste"] or amount <= 0:
        raise FoodError("No surveyed local spoiled food receiver")
    out = copy.deepcopy(food)
    carrier = _ensure_carrier(out, actor)
    if amount > _capacity(carrier) + EPS or amount > out["waste"][room] + EPS:
        raise FoodError("Cannot collect nonexistent food waste")
    out["waste"][room] -= amount
    carrier["waste_kg"] += amount
    validate_food(out)
    return out


def deliver_waste(food, *, actor, kg):
    """Second half of sanitation handoff; caller checks *real* cassette and stock."""
    validate_food(food)
    amount = _q(kg, MAX_CARRY_KG)
    out = copy.deepcopy(food)
    carrier = _ensure_carrier(out, actor)
    if amount <= 0 or amount > carrier["waste_kg"] + EPS:
        raise FoodError("No finite carried kitchen waste to deposit")
    carrier["waste_kg"] -= amount
    out["meter"]["waste_deposited_kg"] += amount
    validate_food(out)
    return out


def certify_nutrients(food, *, room, kg, already_surveyed_kg):
    """Certificate is a CLAIM against existing spares, not a new stock."""
    validate_food(food)
    amount = _q(kg)
    if room not in NUTRIENT_STORES or amount <= 0 or (
            amount > _q(already_surveyed_kg) + EPS):
        raise FoodError("No existing inventoried nutrient-compatible spare supply")
    out = copy.deepcopy(food)
    if room in out["nutrient_certified"]:
        raise FoodError("Previously attested nutrient stock cannot be re-certified")
    out["nutrient_certified"][room] = amount
    validate_food(out)
    return out


def take_nutrients(food, *, actor, room, kg, available_kg):
    """Caller atomically debits INV-SPARES AND its located source survey."""
    validate_food(food)
    amount = _q(kg, MAX_CARRY_KG)
    out = copy.deepcopy(food)
    carrier = _ensure_carrier(out, actor)
    if (room not in NUTRIENT_STORES or amount <= 0
            or amount > _capacity(carrier) + EPS
            or amount > _q(available_kg) + EPS
            or amount > out["nutrient_certified"].get(room, 0.0) + EPS):
        raise FoodError("No verified locally available nutrient packs")
    out["nutrient_certified"][room] -= amount
    out["meter"]["nutrient_issued_kg"] += amount
    carrier["nutrient_kg"] += amount
    validate_food(out)
    return out


def install_nutrients(food, *, actor, kg):
    """Caller simultaneously credits a real GROW-n fitted nutrient skid."""
    validate_food(food)
    amount = _q(kg, MAX_CARRY_KG)
    out = copy.deepcopy(food)
    carrier = _ensure_carrier(out, actor)
    if amount <= 0 or amount > carrier["nutrient_kg"] + EPS:
        raise FoodError("No carried nutrient stock for this growing rack")
    carrier["nutrient_kg"] -= amount
    out["meter"]["nutrient_installed_kg"] += amount
    validate_food(out)
    return out
