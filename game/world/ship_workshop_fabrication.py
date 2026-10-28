"""Finite machining from surveyed, already-owned spare/blank material.

No new inventory, machinery or workshop room. The original INV-SPARES
stores contain operator-classified bar/blanks. An engineer hand-carries them
to an actually running original lathe/mill; time advances only when its
independent physical spindle gauge proves fresh motor-driven output.

Completed parts enter the SAME finite repair-worker stock ledger. Offcuts
stay at SHOP-MECH until physically hand-carried to an original industrial
waste receiver; they never disappear or turn into a second material source.
"""
from __future__ import annotations

import copy
import math
import re

from world.ship_equipment_repair import (
    MAX_HAND_PARTS_KG, validate_repairs,
)
from world.ship_water_recycling import (
    WaterError, CASSETTE_KG, validate_water,
)

WORKROOM = "SHOP-MECH"
MACHINES = frozenset({
    "SHOP-CNC-MILL", "SHOP-CNC-LATHE", "SHOP-MANUAL-LATHE"})
YIELD = 0.75
SECONDS_PER_KG = 90.0
MAX_BLANK_KG = 8.0
MAX_OFFCUT_CARRY_KG = 5.0
MAX_SHOP_OFFCUTS_KG = 40.0
MAX_JOBS = 3
MAX_RECEIPTS = 128
EPS = 1e-7


class FabricationError(ValueError):
    pass


def _mass(value):
    if (type(value) not in (int, float) or
            not math.isfinite(value) or value < 0):
        raise FabricationError("Unknown or negative workshop material")
    return float(value)


def _actor(ref):
    return isinstance(ref, str) and re.fullmatch(r"#[0-9]+", ref) is not None


def initial_fabrication():
    return {
        "version": 1, "certified_kg": {}, "drawn_kg": 0.0,
        "raw_carried_kg": {}, "jobs": {}, "finished_kg": 0.0,
        "shop_offcuts_kg": 0.0, "offcuts_carried_kg": {},
        "offcuts_deposited_kg": 0.0,
        "completed": 0, "receipts": [],
    }


def validate_fabrication(ledger):
    if (not isinstance(ledger, dict) or
            set(ledger) != set(initial_fabrication()) or
            ledger["version"] != 1):
        raise FabricationError("Missing physical machine-shop custody ledger")
    for field in ("drawn_kg", "finished_kg", "shop_offcuts_kg",
                  "offcuts_deposited_kg"):
        _mass(ledger[field])
    if (type(ledger["completed"]) is not int or ledger["completed"] < 0
            or not isinstance(ledger["certified_kg"], dict)
            or not isinstance(ledger["raw_carried_kg"], dict)
            or not isinstance(ledger["offcuts_carried_kg"], dict)
            or not isinstance(ledger["jobs"], dict)
            or len(ledger["jobs"]) > MAX_JOBS
            or not isinstance(ledger["receipts"], list)
            or len(ledger["receipts"]) > MAX_RECEIPTS):
        raise FabricationError("Unknown workshop batch, output or survey")
    for room, amount in ledger["certified_kg"].items():
        if not isinstance(room, str) or not room:
            raise FabricationError("Unlocated operator-certified machinable stock")
        _mass(amount)
    for category, limit in (
            ("raw_carried_kg", MAX_BLANK_KG),
            ("offcuts_carried_kg", MAX_OFFCUT_CARRY_KG)):
        for ref, amount in ledger[category].items():
            if not _actor(ref) or _mass(amount) > limit + EPS:
                raise FabricationError("Workshop material has no bounded carrier")
    for machine, work in ledger["jobs"].items():
        if (machine not in MACHINES or not isinstance(work, dict)
                or set(work) != {"worker", "blank_kg", "remaining_s",
                                 "previous_output", "request_id"}
                or not _actor(work["worker"])
                or not isinstance(work["request_id"], str)
                or re.fullmatch(r"[0-9a-f]{32}", work["request_id"]) is None
                or not 0 < _mass(work["blank_kg"]) <= MAX_BLANK_KG
                or _mass(work["remaining_s"]) >
                    work["blank_kg"] * SECONDS_PER_KG + EPS
                or work["worker"] in [job["worker"] for name, job
                                      in ledger["jobs"].items() if name != machine]):
            raise FabricationError("Machining order has missing physical custody")
        _mass(work["previous_output"])
    if ledger["shop_offcuts_kg"] > MAX_SHOP_OFFCUTS_KG + EPS:
        raise FabricationError("Unbounded workshop chip tray")
    balance = (
        sum(ledger["raw_carried_kg"].values())
        + sum(work["blank_kg"] for work in ledger["jobs"].values())
        + ledger["finished_kg"] + ledger["shop_offcuts_kg"]
        + sum(ledger["offcuts_carried_kg"].values())
        + ledger["offcuts_deposited_kg"])
    if not math.isclose(ledger["drawn_kg"], balance,
                        abs_tol=1e-6, rel_tol=1e-10):
        raise FabricationError("Machined stock, finished parts and offcuts do not conserve mass")
    if ledger["completed"] < len(ledger["receipts"]):
        raise FabricationError("Fabrication receipts exceed completed work")
    for receipt in ledger["receipts"]:
        if (not isinstance(receipt, dict)
                or set(receipt) != {"request_id", "worker", "machine",
                                  "input_kg", "part_kg", "offcuts_kg"}
                or receipt["machine"] not in MACHINES
                or not _actor(receipt["worker"])
                or not isinstance(receipt["request_id"], str)
                or re.fullmatch(r"[0-9a-f]{32}", receipt["request_id"]) is None):
            raise FabricationError("Untraceable workshop finish receipt")
        if (not math.isclose(
                    _mass(receipt["part_kg"]) + _mass(receipt["offcuts_kg"]),
                    _mass(receipt["input_kg"]), abs_tol=EPS, rel_tol=0)
                or receipt["part_kg"] <= 0):
            raise FabricationError("Fabrication finish creates or loses material")
    return True


def certify_blanks(ledger, *, room, kg, surveyed_available_kg):
    """One positive classification of previously surveyed located INV-SPARES."""
    validate_fabrication(ledger)
    amount = _mass(kg)
    available = _mass(surveyed_available_kg)
    if not isinstance(room, str) or not room or not 0 < amount <= available + EPS:
        raise FabricationError("Machinable bar stock must actually exist at this store")
    if room in ledger["certified_kg"]:
        raise FabricationError("Cannot certify the same local blank stock twice")
    result = copy.deepcopy(ledger)
    result["certified_kg"][room] = amount
    validate_fabrication(result)
    return result


def pick_blank(ledger, *, actor, room, kg, stock_kg,
               surveyed_available_kg):
    """Issuer must debit the original stock row and local survey atomically."""
    validate_fabrication(ledger)
    amount = _mass(kg)
    if (not _actor(actor) or not 0 < amount <= MAX_BLANK_KG
            or amount > _mass(stock_kg) + EPS
            or amount > _mass(surveyed_available_kg) + EPS
            or amount > ledger["certified_kg"].get(room, 0.0) + EPS
            or ledger["raw_carried_kg"].get(actor, 0.0) + amount >
               MAX_BLANK_KG + EPS):
        raise FabricationError("No separately certified hand-portable stock at this store")
    result = copy.deepcopy(ledger)
    result["certified_kg"][room] -= amount
    result["raw_carried_kg"][actor] = (
        result["raw_carried_kg"].get(actor, 0.0) + amount)
    result["drawn_kg"] += amount
    validate_fabrication(result)
    return result, stock_kg - amount


def start_batch(ledger, *, actor, machine, kg, request_id,
                previous_output, current_repair_kg):
    """Reserve a distinct actual motor and one worker's original blank."""
    validate_fabrication(ledger)
    amount = _mass(kg)
    old = _mass(previous_output)
    current = _mass(current_repair_kg)
    if (not _actor(actor) or machine not in MACHINES
            or not isinstance(request_id, str)
            or re.fullmatch(r"[0-9a-f]{32}", request_id) is None
            or not 0 < amount <= MAX_BLANK_KG
            or amount > ledger["raw_carried_kg"].get(actor, 0.0) + EPS
            or machine in ledger["jobs"] or len(ledger["jobs"]) >= MAX_JOBS
            or any(j["worker"] == actor for j in ledger["jobs"].values())
            or current + YIELD * amount > MAX_HAND_PARTS_KG + EPS
            or ledger["shop_offcuts_kg"] + (1-YIELD) * amount >
               MAX_SHOP_OFFCUTS_KG + EPS):
        raise FabricationError("No free machine, blank, operator or output receiver")
    result = copy.deepcopy(ledger)
    result["raw_carried_kg"][actor] -= amount
    result["jobs"][machine] = {
        "worker": actor, "blank_kg": amount,
        "remaining_s": amount * SECONDS_PER_KG,
        "previous_output": old, "request_id": request_id}
    validate_fabrication(result)
    return result


def step_batches(ledger, seconds, *, observed, present, free_part_kg):
    """A live spindle must prove new actual shaft output in EACH work step.

    The outer world controls the truthful machine gauge and location. Result
    is (new ledger, tuple of finished [worker, part kg, provenance] records).
    Caller must atomically credit these to the existing repair custody ledger.
    """
    validate_fabrication(ledger)
    dt = _mass(seconds)
    if dt > 10 or not isinstance(observed, dict) or not isinstance(
            present, (set, frozenset)) or not isinstance(free_part_kg, dict):
        raise FabricationError("Unbounded or unauthorised machining clock")
    result = copy.deepcopy(ledger)
    finished = []
    for machine, job in sorted(tuple(result["jobs"].items())):
        measured = observed.get(machine)
        if (not isinstance(measured, dict) or set(measured) !=
                {"operating", "cumulative_output"} or
                type(measured["operating"]) is not bool):
            continue
        output = _mass(measured["cumulative_output"])
        # Do not bank production during absent-worker or unpowered intervals.
        increased = output > job["previous_output"] + EPS
        job["previous_output"] = max(job["previous_output"], output)
        if (job["worker"] not in present or not measured["operating"]
                or not increased):
            continue
        new_remaining = max(0.0, job["remaining_s"] - dt)
        part = job["blank_kg"] * YIELD
        offcuts = job["blank_kg"] - part
        if new_remaining <= EPS and (
                _mass(free_part_kg.get(job["worker"], 0.0)) + EPS < part or
                result["shop_offcuts_kg"] + offcuts >
                MAX_SHOP_OFFCUTS_KG + EPS):
            continue
        job["remaining_s"] = new_remaining
        if new_remaining <= EPS:
            result["finished_kg"] += part
            result["shop_offcuts_kg"] += offcuts
            result["completed"] += 1
            provenance = {
                "request_id": job["request_id"], "worker": job["worker"],
                "machine": machine, "input_kg": job["blank_kg"],
                "part_kg": part, "offcuts_kg": offcuts,
            }
            result["receipts"] = (result["receipts"] +
                                  [provenance])[-MAX_RECEIPTS:]
            finished.append((job["worker"], part, provenance))
            del result["jobs"][machine]
    validate_fabrication(result)
    return result, tuple(finished)


def credit_repair_parts(repairs, *, actor, kg):
    """Put a made, actually delivered part in existing carried-repair custody."""
    validate_repairs(repairs)
    amount = _mass(kg)
    if (not _actor(actor) or amount <= 0 or
            repairs["carried_kg"].get(actor, 0.0) + amount >
            MAX_HAND_PARTS_KG + EPS):
        raise FabricationError("Fabricated part does not fit real worker's hands")
    result = copy.deepcopy(repairs)
    result["carried_kg"][actor] = result["carried_kg"].get(actor, 0.0) + amount
    result["delivered_spares_kg"] += amount
    validate_repairs(result)
    return result


def take_offcuts(ledger, *, actor, kg):
    """Only a worker at the original SHOP-MECH chip tray may collect waste."""
    validate_fabrication(ledger)
    mass = _mass(kg)
    if (not _actor(actor) or not 0 < mass <= MAX_OFFCUT_CARRY_KG
            or mass > ledger["shop_offcuts_kg"] + EPS
            or ledger["offcuts_carried_kg"].get(actor, 0.0) + mass >
               MAX_OFFCUT_CARRY_KG + EPS):
        raise FabricationError("No available portable chip tray load")
    result = copy.deepcopy(ledger)
    result["shop_offcuts_kg"] -= mass
    result["offcuts_carried_kg"][actor] = (
        result["offcuts_carried_kg"].get(actor, 0.0) + mass)
    validate_fabrication(result)
    return result


def deposit_offcuts(ledger, water, stocks, *, actor, kg, side,
                    receiver_ready):
    """Into fitted sealed industrial receiver, not an invented scrap dump.

    Workshop material was already debited from INV-SPARES at blank pickup.
    Therefore credit only the original industrial cassette and waste inventory;
    never debit spare stock again or create extra external cargo.
    """
    validate_fabrication(ledger)
    validate_water(water, stocks)
    mass = _mass(kg)
    if (not _actor(actor) or side not in "AB" or len(side) != 1
            or type(receiver_ready) is not bool or not receiver_ready
            or not 0 < mass <= MAX_OFFCUT_CARRY_KG
            or mass > ledger["offcuts_carried_kg"].get(actor, 0.0) + EPS
            or not water["cassette_sealed"]["industrial"][side]
            or water["cassettes"]["industrial"][side] + mass >
                CASSETTE_KG["industrial"][side] + EPS):
        raise FabricationError("Unsealed, full or unverified real industrial cassette")
    result = copy.deepcopy(ledger)
    wet = copy.deepcopy(water)
    balances = copy.deepcopy(stocks)
    result["offcuts_carried_kg"][actor] -= mass
    result["offcuts_deposited_kg"] += mass
    wet["cassettes"]["industrial"][side] += mass
    wet["cumulative"]["industrial_waste_kg"] += mass
    balances["industrial"] += mass
    validate_fabrication(result)
    validate_water(wet, balances)
    return result, wet, balances
