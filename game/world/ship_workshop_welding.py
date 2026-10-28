"""Finite independently powered G19 original WELD-CELL-A/B weldments.

A real engineer supplies *existing* carried base repair stock and purchased
filler from operator-surveyed INV-SPARES. A physically running cell plus
present worker produces a measured arc/heat witness. Finished weldment
returns to the existing repair-spare custody ledger; slag is retained in
SHOP-WELD until carried to a real sealed industrial cassette.
"""
from __future__ import annotations

import copy
import math
import re

from world.ship_equipment_repair import validate_repairs, MAX_HAND_PARTS_KG
from world.ship_water_recycling import validate_water, CASSETTE_KG
from world.ship_workshop_fabrication import credit_repair_parts

CELLS = frozenset({"WELD-CELL-A", "WELD-CELL-B"})
ROOM = "SHOP-WELD"
ARC_KW = 15.0
FILLER_YIELD = 0.85
MAX_CARRY_FILLER_KG = 3.0
MAX_CARRY_SLAG_KG = 5.0
MAX_WELD_SLAG_KG = 20.0
MAX_RECEIPTS = 128
EPS = 1e-7


class WeldError(ValueError):
    pass


def _num(x):
    if type(x) not in (float, int) or not math.isfinite(x) or x < 0:
        raise WeldError("Unphysical original welding material or elapsed time")
    return float(x)


def _crew(ref):
    return isinstance(ref, str) and re.fullmatch(r"#[0-9]+", ref) is not None


def initial_welding():
    return {
        "version": 1,
        "certified_kg": {}, "filler_issued_kg": 0.0,
        "base_borrowed_kg": 0.0, "filler_carried_kg": {},
        "jobs": {}, "welded_returned_kg": 0.0,
        "slag_shop_kg": 0.0, "slag_carried_kg": {},
        "slag_deposited_kg": 0.0, "arc_kj": 0.0,
        "completed": 0, "receipts": [],
    }


def validate_welding(w):
    if (not isinstance(w, dict) or set(w) != set(initial_welding())
            or w["version"] != 1 or not isinstance(w["certified_kg"], dict)
            or not isinstance(w["filler_carried_kg"], dict)
            or not isinstance(w["slag_carried_kg"], dict)
            or not isinstance(w["jobs"], dict)
            or not isinstance(w["receipts"], list)
            or len(w["receipts"]) > MAX_RECEIPTS
            or len(w["jobs"]) > len(CELLS)
            or type(w["completed"]) is not int or w["completed"] < 0):
        raise WeldError("Uncommissioned original welding cell custody")
    for key in ("filler_issued_kg", "base_borrowed_kg",
                "welded_returned_kg", "slag_shop_kg",
                "slag_deposited_kg", "arc_kj"):
        _num(w[key])
    if w["slag_shop_kg"] > MAX_WELD_SLAG_KG + EPS:
        raise WeldError("Unbounded original welding bay slag receiver")
    for room, qty in w["certified_kg"].items():
        if not isinstance(room, str) or not room:
            raise WeldError("Unlocated certified electrode source")
        _num(qty)
    for kind, limit in (
            ("filler_carried_kg", MAX_CARRY_FILLER_KG),
            ("slag_carried_kg", MAX_CARRY_SLAG_KG)):
        for worker, qty in w[kind].items():
            if not _crew(worker) or _num(qty) > limit + EPS:
                raise WeldError("Invalid welding consumables custody")
    workers = set()
    for machine, job in w["jobs"].items():
        if (machine not in CELLS or not isinstance(job, dict)
                or set(job) != {"worker", "base_kg", "filler_kg",
                                "remaining_s", "request_id"}
                or not _crew(job["worker"]) or job["worker"] in workers
                or not isinstance(job["request_id"], str)
                or re.fullmatch(r"[0-9a-f]{32}", job["request_id"]) is None
                or not 0 < _num(job["base_kg"]) <= MAX_HAND_PARTS_KG
                or not 0 < _num(job["filler_kg"]) <= MAX_CARRY_FILLER_KG
                or _num(job["remaining_s"]) >
                   60 * job["base_kg"] + 120 * job["filler_kg"] + EPS):
            raise WeldError("Unidentified live physical welding order")
        workers.add(job["worker"])
    if w["completed"] < len(w["receipts"]):
        raise WeldError("Welding output history out of order")
    for row in w["receipts"]:
        if (not isinstance(row, dict) or set(row) != {
                "machine", "worker", "request_id",
                "base_kg", "filler_kg", "output_kg", "slag_kg"}
                or row["machine"] not in CELLS or not _crew(row["worker"])
                or not isinstance(row["request_id"], str)
                or re.fullmatch(r"[0-9a-f]{32}", row["request_id"]) is None):
            raise WeldError("Unknown completed weld source")
        if not math.isclose(
                _num(row["base_kg"]) + _num(row["filler_kg"]),
                _num(row["output_kg"]) + _num(row["slag_kg"]),
                rel_tol=0, abs_tol=EPS):
            raise WeldError("Welding material output is not conserved")
    mass = (sum(w["filler_carried_kg"].values()) +
            sum(job["base_kg"] + job["filler_kg"]
                for job in w["jobs"].values()) +
            w["welded_returned_kg"] + w["slag_shop_kg"] +
            sum(w["slag_carried_kg"].values()) +
            w["slag_deposited_kg"])
    if not math.isclose(w["filler_issued_kg"] + w["base_borrowed_kg"],
                        mass, rel_tol=1e-10, abs_tol=1e-6):
        raise WeldError("Welding part, filler and slag mass do not reconcile")
    return True


def certify_filler(w, *, room, kg, surveyed_available_kg):
    validate_welding(w)
    mass = _num(kg)
    if (not isinstance(room, str) or not room or room in w["certified_kg"]
            or not 0 < mass <= _num(surveyed_available_kg) + EPS):
        raise WeldError("Welding wire cannot be certified twice or without actual stock")
    result = copy.deepcopy(w)
    result["certified_kg"][room] = mass
    validate_welding(result)
    return result


def issue_filler(w, *, worker, room, kg, stock_kg, surveyed_available_kg):
    validate_welding(w)
    mass = _num(kg)
    if (not _crew(worker) or not 0 < mass <= MAX_CARRY_FILLER_KG
            or mass > _num(stock_kg) + EPS
            or mass > _num(surveyed_available_kg) + EPS
            or mass > w["certified_kg"].get(room, 0.0) + EPS
            or w["filler_carried_kg"].get(worker, 0.0) + mass >
               MAX_CARRY_FILLER_KG + EPS):
        raise WeldError("Electrode spool is not physically located or hand portable")
    result = copy.deepcopy(w)
    result["certified_kg"][room] -= mass
    result["filler_carried_kg"][worker] = (
        result["filler_carried_kg"].get(worker, 0.0) + mass)
    result["filler_issued_kg"] += mass
    validate_welding(result)
    return result, stock_kg - mass


def start_weld(w, repairs, *, worker, machine, base_kg, filler_kg, request_id):
    validate_welding(w)
    validate_repairs(repairs)
    base, filler = _num(base_kg), _num(filler_kg)
    remaining = repairs["carried_kg"].get(worker, 0.0)
    joined = base + filler * FILLER_YIELD
    if (not _crew(worker) or machine not in CELLS or machine in w["jobs"]
            or not 0 < base <= MAX_HAND_PARTS_KG or
            not 0 < filler <= MAX_CARRY_FILLER_KG
            or not isinstance(request_id, str)
            or re.fullmatch(r"[0-9a-f]{32}", request_id) is None
            or remaining + EPS < base
            or w["filler_carried_kg"].get(worker, 0.0) + EPS < filler
            or any(job["worker"] == worker for job in w["jobs"].values())
            or remaining - base + joined > MAX_HAND_PARTS_KG + EPS
            or w["slag_shop_kg"] + (1-FILLER_YIELD)*filler >
               MAX_WELD_SLAG_KG + EPS):
        raise WeldError("Worker lacks original prepared part, electrode, usable cell or safe capacity")
    result = copy.deepcopy(w)
    repaired = copy.deepcopy(repairs)
    repaired["carried_kg"][worker] -= base
    repaired["delivered_spares_kg"] -= base
    result["base_borrowed_kg"] += base
    result["filler_carried_kg"][worker] -= filler
    result["jobs"][machine] = {
        "worker": worker, "base_kg": base, "filler_kg": filler,
        "remaining_s": base*60 + filler*120, "request_id": request_id,
    }
    validate_welding(result)
    validate_repairs(repaired)
    return result, repaired


def step_welds(w, seconds, *, active, present, air_safe, capacity):
    """Every physical epoch must actually strike a staffed, powered arc.

    Returns (ledger, completed weldments, arc_kJ by installed cell).
    The world pays the corresponding heat into the REAL SHOP-WELD pressure
    cell and credits output into existing repair spares atomically.
    """
    validate_welding(w)
    dt = _num(seconds)
    if (dt > 10 or not isinstance(active, (set, frozenset))
            or not isinstance(present, (set, frozenset))
            or type(air_safe) is not bool or not isinstance(capacity, dict)):
        raise WeldError("Unbounded or missing actual welding operation")
    result = copy.deepcopy(w)
    finished, heat = [], {}
    for machine, job in sorted(tuple(result["jobs"].items())):
        if (machine not in active or job["worker"] not in present or
                not air_safe):
            continue
        mass = job["base_kg"] + FILLER_YIELD*job["filler_kg"]
        if (job["remaining_s"] <= dt + EPS and
                (_num(capacity.get(job["worker"], 0.0)) + EPS < mass
                 or result["slag_shop_kg"] + (1-FILLER_YIELD)*job["filler_kg"] >
                    MAX_WELD_SLAG_KG + EPS)):
            continue
        job["remaining_s"] = max(0.0, job["remaining_s"] - dt)
        heat[machine] = ARC_KW * dt
        result["arc_kj"] += ARC_KW * dt
        if job["remaining_s"] <= EPS:
            slag = (1-FILLER_YIELD)*job["filler_kg"]
            result["welded_returned_kg"] += mass
            result["slag_shop_kg"] += slag
            result["completed"] += 1
            provenance = {
                "machine": machine, "worker": job["worker"],
                "request_id": job["request_id"],
                "base_kg": job["base_kg"], "filler_kg": job["filler_kg"],
                "output_kg": mass, "slag_kg": slag,
            }
            result["receipts"] = (result["receipts"] + [provenance])[-MAX_RECEIPTS:]
            finished.append((job["worker"], mass, provenance))
            del result["jobs"][machine]
    validate_welding(result)
    return result, tuple(finished), heat


def take_slag(w, *, worker, kg):
    validate_welding(w)
    mass = _num(kg)
    if (not _crew(worker) or not 0 < mass <= MAX_CARRY_SLAG_KG
            or mass > w["slag_shop_kg"] + EPS
            or w["slag_carried_kg"].get(worker, 0.0) + mass >
               MAX_CARRY_SLAG_KG + EPS):
        raise WeldError("No staged welding slag or qualified physical carrier")
    result = copy.deepcopy(w)
    result["slag_shop_kg"] -= mass
    result["slag_carried_kg"][worker] = (
        result["slag_carried_kg"].get(worker, 0.0) + mass)
    validate_welding(result)
    return result


def deposit_slag(w, water, stocks, *, worker, kg, side, receiver_ready):
    validate_welding(w)
    validate_water(water, stocks)
    mass = _num(kg)
    if (not _crew(worker) or side not in "AB" or len(side) != 1
            or type(receiver_ready) is not bool or not receiver_ready
            or not 0 < mass <= MAX_CARRY_SLAG_KG
            or mass > w["slag_carried_kg"].get(worker, 0.0) + EPS
            or not water["cassette_sealed"]["industrial"][side]
            or water["cassettes"]["industrial"][side] + mass >
                CASSETTE_KG["industrial"][side] + EPS):
        raise WeldError("Welding slag must reach an authentic sealed industrial receiver")
    result, wet, balance = copy.deepcopy(w), copy.deepcopy(water), dict(stocks)
    result["slag_carried_kg"][worker] -= mass
    result["slag_deposited_kg"] += mass
    wet["cassettes"]["industrial"][side] += mass
    wet["cumulative"]["industrial_waste_kg"] += mass
    balance["industrial"] += mass
    validate_welding(result)
    validate_water(wet, balance)
    return result, wet, balance
