"""G19 finite suit, gas-recovery airlocks and EVA transit state machines.

The Ox has two *existing* airlocks, their distinct 2x air dampers and
electrical breakers, two real crawlers, and 24 external spaces. This model
does not create a vacuum room, consumable stock or astronaut by inference.
All actions and inventory transfers are adopted by the canonical world.
"""
from __future__ import annotations

import copy
import math
import re

from world.ship_crew_exposure import (
    OXYGEN_KG_S, initial_exposure, step_exposure, ExposureError,
)

LOCKS = ("EVA-FWD", "EVA-AFT")
SUIT_O2_KG = 0.75
CYCLE_S = 90.0
MAX_GAS_BUFFER_KG = 350.0
MAX_STEP_S = 10.0


class EVAError(ValueError):
    pass


def _num(x, low=0.0, high=None):
    if (isinstance(x, bool) or not isinstance(x, (float, int))
            or not math.isfinite(x) or x < low
            or high is not None and x > high):
        raise EVAError("Invalid finite EVA resource")
    return float(x)


def lock_contract(room):
    if room not in LOCKS:
        raise EVAError("No installed primary EVA airlock at that room")
    end = "FWD" if room == "EVA-FWD" else "AFT"
    return {
        "room": room, "zone": "PZ-BOW-EVA" if end == "FWD" else "PZ-AFT-EVA",
        "inner": "ACC-EVA-" + end, "outer": "ACC-EVA-" + end + "-EXT",
        "outside": "EXT-BOW" if end == "FWD" else "EXT-AFT",
        "damper": "ISO-AIR-FIXED-EVA-" + end,
        "breaker": "ISO-LP-EVA-" + end,
        "panel": "LP-EVA-" + end,
        "crawler": "EVA-CRAWLER-1" if end == "FWD" else "EVA-CRAWLER-2",
        "trunk": "TRUNK-B-BOW" if end == "FWD" else "TRUNK-B-AFT",
    }


def initial_eva():
    suits = {}
    for lock in LOCKS:
        for n in (1, 2):
            key = lock + "-SUIT-" + str(n)
            suits[key] = {"home": lock, "holder": None,
                          "exposure": initial_exposure(), "integrity": 1.0}
    return {
        "suits": suits,
        "locks": {lock: {
            "mode": "pressurised", "remaining_s": 0.0,
            "buffer": {"mass": 0.0, "oxygen": 0.0, "co2": 0.0, "smoke": 0.0},
            "cycles": 0,
        } for lock in LOCKS},
        "transits": {}, "staged_kg": {}, "issued_kg": 0.0,
        "charged_kg": 0.0,
        "consumed_oxygen_kg": 0.0, "completed_transits": 0,
    }


def validate_eva(eva):
    if (not isinstance(eva, dict) or set(eva) != set(initial_eva())
            or not isinstance(eva["suits"], dict)
            or set(eva["suits"]) != set(initial_eva()["suits"])
            or not isinstance(eva["locks"], dict)
            or set(eva["locks"]) != set(LOCKS)
            or not isinstance(eva["transits"], dict)
            or len(eva["transits"]) > 4):
        raise EVAError("Damaged or uncommissioned EVA system")
    for name in ("issued_kg", "charged_kg", "consumed_oxygen_kg"):
        _num(eva[name])
    if not isinstance(eva["staged_kg"], dict) or len(eva["staged_kg"]) > 16:
        raise EVAError("Invalid carrying-custody record")
    for actor, mass in eva["staged_kg"].items():
        if not isinstance(actor, str) or not re.fullmatch(r"#[0-9]+", actor):
            raise EVAError("Breathing gas is not carried by a real worker")
        _num(mass, high=4 * SUIT_O2_KG)
    if abs(sum(eva["staged_kg"].values()) +
           eva["charged_kg"] - eva["issued_kg"]) > 1e-7:
        raise EVAError("Airlock oxygen issue, carriage and suit charge do not reconcile")
    if eva["consumed_oxygen_kg"] > eva["charged_kg"] + 1e-8:
        raise EVAError("Suit breathed oxygen which was never issued")
    if (type(eva["completed_transits"]) is not int
            or eva["completed_transits"] < 0):
        raise EVAError("Invalid EVA transit count")
    held = set()
    for key, suit in eva["suits"].items():
        if (not isinstance(suit, dict) or set(suit) != {
                "home", "holder", "exposure", "integrity"} or
                suit["home"] not in LOCKS or not key.startswith(suit["home"])):
            raise EVAError("Unaccounted installed suit")
        integrity = _num(suit["integrity"], high=1.0)
        if suit["holder"] is not None:
            if (not isinstance(suit["holder"], str)
                    or not re.fullmatch(r"#[0-9]+", suit["holder"])
                    or suit["holder"] in held):
                raise EVAError("Suit assigned to multiple wearers")
            held.add(suit["holder"])
        exp = suit["exposure"]
        if not isinstance(exp, dict) or set(exp) != set(initial_exposure()):
            raise EVAError("Invalid suit physiology")
        for name, val in exp.items():
            if name == "condition":
                if val not in ("fit", "impaired", "incapacitated", "critical", "dead"):
                    raise EVAError("Invalid crew condition")
            else:
                _num(val)
        if exp["suit_oxygen_kg"] > SUIT_O2_KG + 1e-8:
            raise EVAError("Suit overfilled with nonexistent oxygen")
    for lock, row in eva["locks"].items():
        if (not isinstance(row, dict) or set(row) != {
                "mode", "remaining_s", "buffer", "cycles"}
                or row["mode"] not in ("pressurised", "pumpdown",
                                       "vacuum", "repressurise")):
            raise EVAError("Invalid airlock cycle")
        _num(row["remaining_s"], high=CYCLE_S)
        if ((row["mode"] in ("pumpdown", "repressurise")) !=
                (row["remaining_s"] > 0)):
            raise EVAError("Incomplete finite airlock cycle")
        if type(row["cycles"]) is not int or row["cycles"] < 0:
            raise EVAError("Invalid airlock cycle count")
        buf = row["buffer"]
        if not isinstance(buf, dict) or set(buf) != {"mass", "oxygen", "co2", "smoke"}:
            raise EVAError("Invalid recovered gas custody")
        for val in buf.values():
            _num(val, high=MAX_GAS_BUFFER_KG)
        if (buf["mass"] > MAX_GAS_BUFFER_KG
                or buf["oxygen"] + buf["co2"] + buf["smoke"] > buf["mass"] + 1e-7):
            raise EVAError("Recovered gas species do not reconcile")
    for actor, job in eva["transits"].items():
        if (not isinstance(actor, str) or not re.fullmatch(r"#[0-9]+", actor)
                or actor not in held
                or not isinstance(job, dict) or set(job) != {
                    "link", "from", "to", "remaining_s", "total_s",
                    "request_id"} or
                not re.fullmatch(r"[0-9a-f]{32}", job["request_id"])):
            raise EVAError("EVA travel not assigned to real suited worker")
        total = _num(job["total_s"], low=0.0)
        left = _num(job["remaining_s"])
        if total <= 0 or left > total or total > 300:
            raise EVAError("Unrated exterior transit interval")
    return True


def suit_of(eva, actor):
    for ident, row in eva["suits"].items():
        if row["holder"] == actor:
            return ident, row
    return None, None


def stage_suit_oxygen(eva, *, actor, kg):
    """A real worker moves measured DC breathing gas out of source stores."""
    validate_eva(eva)
    if not isinstance(actor, str) or not re.fullmatch(r"#[0-9]+", actor):
        raise EVAError("No verified worker carrying breathing stock")
    mass = _num(kg, high=SUIT_O2_KG)
    if mass <= 0:
        raise EVAError("No breathing gas supplied")
    result = copy.deepcopy(eva)
    result["staged_kg"][actor] = result["staged_kg"].get(actor, 0.0) + mass
    result["issued_kg"] += mass
    validate_eva(result)
    return result


def checkout_suit(eva, *, actor, lock, supplied_oxygen_kg):
    """Allocate a distinct suit; source stock is debited by world authority."""
    validate_eva(eva)
    lock_contract(lock)
    if not re.fullmatch(r"#[0-9]+", actor) or suit_of(eva, actor)[1]:
        raise EVAError("Invalid or already suited character")
    eligible = next((k for k, v in sorted(eva["suits"].items())
                     if v["home"] == lock and v["holder"] is None), None)
    if eligible is None:
        raise EVAError("No physical suit remains at this airlock")
    result = copy.deepcopy(eva)
    item = result["suits"][eligible]
    needed = SUIT_O2_KG - item["exposure"]["suit_oxygen_kg"]
    if abs(_num(supplied_oxygen_kg) - needed) > 1e-7:
        raise EVAError("Unbalanced suit oxygen issue")
    if result["staged_kg"].get(actor, 0.0) + 1e-7 < needed:
        raise EVAError("No physically carried breathing canister at this airlock")
    result["staged_kg"][actor] -= needed
    if result["staged_kg"][actor] < 1e-7:
        del result["staged_kg"][actor]
    item["exposure"]["suit_oxygen_kg"] += needed
    item["holder"] = actor
    result["charged_kg"] += needed
    validate_eva(result)
    return result, eligible, needed


def return_suit(eva, *, actor, lock):
    validate_eva(eva)
    key, item = suit_of(eva, actor)
    if not item or item["home"] != lock or actor in eva["transits"]:
        raise EVAError("Return physical suit at original dock after transit")
    result = copy.deepcopy(eva)
    result["suits"][key]["holder"] = None
    validate_eva(result)
    return result


def begin_cycle(eva, *, lock, direction):
    validate_eva(eva)
    lock_contract(lock)
    state = eva["locks"][lock]
    if direction == "pumpdown":
        if state["mode"] != "pressurised" or state["buffer"]["mass"]:
            raise EVAError("Airlock needs pressurised empty recovery buffer")
    elif direction == "repressurise":
        if state["mode"] != "vacuum" or state["buffer"]["mass"] <= 0:
            raise EVAError("No recovered breathable air for re-pressurisation")
    else:
        raise EVAError("Only rated pumpdown or re-pressurisation cycle")
    out = copy.deepcopy(eva)
    out["locks"][lock]["mode"] = direction
    out["locks"][lock]["remaining_s"] = CYCLE_S
    validate_eva(out)
    return out


def step_cycles(eva, seconds, *, ready_locks):
    validate_eva(eva)
    seconds = _num(seconds, high=MAX_STEP_S)
    result = copy.deepcopy(eva)
    events = []
    for lock, row in result["locks"].items():
        if row["mode"] not in ("pumpdown", "repressurise") or lock not in ready_locks:
            continue
        row["remaining_s"] = max(0.0, row["remaining_s"] - seconds)
        if row["remaining_s"] < 1e-8:
            old = row["mode"]
            row["mode"] = "vacuum" if old == "pumpdown" else "pressurised"
            row["cycles"] += 1
            events.append((lock, old))
    validate_eva(result)
    return result, tuple(events)


def transfer_recovered_gas(eva, cells, *, lock, cycle):
    """Move exact real gas species between installed pressure cell and tank.

    Caller must adopt both returned state objects in one world transaction.
    Atmosphere circulation through this lock must already be isolated.
    """
    validate_eva(eva)
    zone = lock_contract(lock)["zone"]
    result = copy.deepcopy(eva)
    gas = copy.deepcopy(cells)
    row = gas[zone]
    buf = result["locks"][lock]["buffer"]
    if cycle == "pumpdown":
        if result["locks"][lock]["mode"] != "vacuum" or buf["mass"]:
            raise EVAError("Pump cycle was not fully completed")
        if row["mass"] > MAX_GAS_BUFFER_KG:
            raise EVAError("Physical recovery bottle cannot hold airlock gas")
        for k in ("mass", "oxygen", "co2", "smoke"):
            buf[k] = row[k]
            row[k] = 0.0
    elif cycle == "repressurise":
        if result["locks"][lock]["mode"] != "pressurised" or not buf["mass"]:
            raise EVAError("Unfinished or unstocked airlock re-pressurisation")
        for k in ("mass", "oxygen", "co2", "smoke"):
            row[k] += buf[k]
            buf[k] = 0.0
    else:
        raise EVAError("Unknown gas movement cycle")
    # Thermal energy stored in the transferred parcel is not invented.
    # Isothermal simplified recovery: installed metal thermal capacity remains.
    row["energy"] = (row["capacity"] +
                     row["mass"] * 1.005) * row["temperature"]
    validate_eva(result)
    return result, gas


def step_suit_metabolism(eva, seconds):
    """Only issued/worn suits consume finite real breathing stock."""
    validate_eva(eva)
    seconds = _num(seconds, high=MAX_STEP_S)
    result = copy.deepcopy(eva)
    vacuum = {
        "pressure_pa": 0.0, "oxygen_fraction": 0.0,
        "co2_fraction": 0.0, "smoke_density": 0.0,
        "temperature_k": 294.0,
    }
    for item in result["suits"].values():
        if item["holder"] is None:
            continue
        try:
            before = item["exposure"]["suit_oxygen_kg"]
            after, _ = step_exposure(
                item["exposure"], vacuum, seconds,
                suited=True, suit_integrity=item["integrity"])
            item["exposure"] = after
            result["consumed_oxygen_kg"] += before - after["suit_oxygen_kg"]
        except ExposureError as exc:
            raise EVAError(str(exc)) from exc
    validate_eva(result)
    return result


def begin_eva_transit(eva, *, actor, link, source, destination,
                      seconds, request_id):
    validate_eva(eva)
    _, suit = suit_of(eva, actor)
    if not suit or suit["integrity"] < .8 or (
            suit["exposure"]["suit_oxygen_kg"] <
            OXYGEN_KG_S * (seconds + 10)):
        raise EVAError("Insufficient physically issued suit life support")
    if actor in eva["transits"] or not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise EVAError("EVA worker already in transit or invalid request")
    duration = _num(seconds, high=300)
    if duration <= 0:
        raise EVAError("Exterior transfer has no rated travel time")
    result = copy.deepcopy(eva)
    result["transits"][actor] = {
        "link": link, "from": source, "to": destination,
        "remaining_s": duration, "total_s": duration,
        "request_id": request_id,
    }
    validate_eva(result)
    return result


def step_eva_transits(eva, seconds, *, ready_links):
    validate_eva(eva)
    seconds = _num(seconds, high=MAX_STEP_S)
    result = copy.deepcopy(eva)
    finished = []
    for actor, row in result["transits"].items():
        _, suit = suit_of(result, actor)
        if (row["link"] not in ready_links or suit["integrity"] < .8
                or suit["exposure"]["condition"] in {
                    "incapacitated", "critical", "dead"}):
            continue
        row["remaining_s"] = max(0.0, row["remaining_s"] - seconds)
        if row["remaining_s"] < 1e-8:
            finished.append((actor, copy.deepcopy(row)))
    validate_eva(result)
    return result, tuple(finished)


def finish_eva_transit(eva, *, actor, request_id, aborted=False):
    validate_eva(eva)
    row = eva["transits"].get(actor)
    if not row or row["request_id"] != request_id or (
            not aborted and row["remaining_s"] > 1e-8):
        raise EVAError("Exterior transfer is not complete")
    result = copy.deepcopy(eva)
    del result["transits"][actor]
    if not aborted:
        result["completed_transits"] += 1
    validate_eva(result)
    return result
