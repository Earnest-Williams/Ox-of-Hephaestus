"""G19 original 40 cabin fan-coils: individually wired, finite LT heat transfer.

The four residential HAB arcs each have ten fitted cabin terminals. Their
power and low-temperature cooling circuits already exist in v0.5. A cabin
has no private invented pressure cell: each terminal removes heat from the
arc's original finite PZ-HAB gas/thermal account. The source LT radiator
budget is charged ONCE and no terminal creates refrigerant, power, or air.

Each original machine has a durable local ON/OFF command, live 10-second
output evidence, independent feeder/coolant eligibility, and cumulative
heat-removal accounting. Simulated coil capacity (0.35 kW) is a deliberately
bounded game tuning constant, not a claim about a manufacturer's data plate.
"""
from __future__ import annotations

import copy
import math

BROKEN = frozenset({"faulted", "failed", "severed", "jammed", "destroyed"})
RESIDENTIAL_ARCS = (1, 3, 5, 7)
FANCOILS = {
    f"HAB-{arc:02d}-CAB-{cabin:02d}-FANCOIL":
        (f"HAB-{arc:02d}-CAB-{cabin:02d}", f"PZ-HAB-{arc:02d}")
    for arc in RESIDENTIAL_ARCS for cabin in range(1, 11)
}
MAX_UNIT_KW = 0.35
COOLING_TARGET_K = 293.15
GAS_CP_KJ_KG_K = 1.0
MAX_STEP_S = 10.0
EPS = 1e-7


class CabinCoilError(ValueError):
    """Unverified original cabin circuit or inconsistent thermal ledger."""


def _finite(number, *, low=0.0):
    if (type(number) not in (int, float) or not math.isfinite(number)
            or number < low):
        raise CabinCoilError("Nonfinite cabin heat, time or cooling budget")
    return float(number)


def coil_power_node(name):
    if name not in FANCOILS:
        raise CabinCoilError("No original fitted residential cabin terminal")
    return "NODE-PWR-" + name


def coil_coolant_node(name):
    if name not in FANCOILS:
        raise CabinCoilError("No original fitted LT cabin branch")
    return "NODE-LT-" + FANCOILS[name][0]


def initial_cabin_coils():
    return {
        "version": 1,
        "units": {
            name: {"command": "off", "cumulative_kj": 0.0,
                   "last_kj": 0.0, "last_s": None}
            for name in sorted(FANCOILS)
        },
        "meter": {"removed_kj": 0.0},
        "last": {"removed_kj": 0.0, "reserved_kj": 0.0,
                 "operating": []},
    }


def validate_cabin_coils(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"version", "units", "meter", "last"}
            or type(ledger["version"]) is not int or ledger["version"] != 1
            or not isinstance(ledger["units"], dict)
            or set(ledger["units"]) != set(FANCOILS)
            or not isinstance(ledger["meter"], dict)
            or set(ledger["meter"]) != {"removed_kj"}
            or not isinstance(ledger["last"], dict)
            or set(ledger["last"]) != {
                "removed_kj", "reserved_kj", "operating"}):
        raise CabinCoilError("Original 40-terminal roster or custody is corrupt")
    cumulative = 0.0
    for name, row in ledger["units"].items():
        if (not isinstance(row, dict)
                or set(row) != {"command", "cumulative_kj",
                               "last_kj", "last_s"}
                or row["command"] not in ("on", "off")
                or (row["last_s"] is not None
                    and type(row["last_s"]) not in (int, float))):
            raise CabinCoilError("Unrecognised individual cabin terminal state")
        amount = _finite(row["cumulative_kj"])
        last = _finite(row["last_kj"])
        if last > amount + EPS:
            raise CabinCoilError("Cabin terminal output exceeds cumulative meter")
        if row["last_s"] is not None:
            _finite(row["last_s"])
        elif last != 0 or amount != 0:
            raise CabinCoilError("No physical time for nonzero delivered cooling")
        cumulative += amount
    if not math.isclose(_finite(ledger["meter"]["removed_kj"]), cumulative,
                        abs_tol=1e-6, rel_tol=1e-10):
        raise CabinCoilError("Installed cabin LT heat output escaped its ledger")
    last = ledger["last"]
    removed, reserved = (_finite(last[k])
                         for k in ("removed_kj", "reserved_kj"))
    if removed > reserved + EPS or removed > cumulative + EPS:
        raise CabinCoilError("No finite radiator budget for reported cabin cooling")
    if (not isinstance(last["operating"], list)
            or len(last["operating"]) != len(set(last["operating"]))
            or any(name not in FANCOILS for name in last["operating"])):
        raise CabinCoilError("Invented operating cabin terminal")
    return True


def command_cabin_coil(ledger, name, command):
    validate_cabin_coils(ledger)
    if name not in FANCOILS or command not in ("on", "off"):
        raise CabinCoilError("Uninstalled terminal or unsupported crew command")
    updated = copy.deepcopy(ledger)
    updated["units"][name]["command"] = command
    validate_cabin_coils(updated)
    return updated


def step_cabin_coils(ledger, seconds, *, now_s, powered_nodes,
                     coolant_nodes, equipment, cells, cooling_budget_kw):
    """Actual bounded LT heat output, not mere command/panel indication.

    The heat is withdrawn from the REAL arc thermal account; caller must
    withhold reserved_kj/dt from the existing general environment cooler.
    A closed feeder, isolated LT valve, failed mechanism, no available
    radiator capacity or already cool arc earns zero positive output.
    """
    validate_cabin_coils(ledger)
    dt = _finite(seconds)
    now = _finite(now_s)
    budget_kw = _finite(cooling_budget_kw)
    if not 0 < dt <= MAX_STEP_S:
        raise CabinCoilError("Cabin output requires one bounded live substep")
    if not isinstance(powered_nodes, (set, frozenset)):
        raise CabinCoilError("No verifiable powered electrical endpoints")
    if not isinstance(coolant_nodes, (set, frozenset)):
        raise CabinCoilError("No verifiable physical LT branches")
    if not isinstance(equipment, dict) or not isinstance(cells, dict):
        raise CabinCoilError("Installed machine/pressure-cell context absent")
    updated = copy.deepcopy(ledger)
    operating = []
    for name in sorted(FANCOILS):
        row = updated["units"][name]
        machine = equipment.get(name)
        room, zone = FANCOILS[name]
        if machine is None or getattr(machine, "space_id", None) != room:
            raise CabinCoilError("Original cabin machine disappeared or moved")
        if zone not in cells:
            raise CabinCoilError("Original arc pressure and sensible heat are absent")
        previously = row["last_s"]
        if previously is not None and now < previously + dt - EPS:
            raise CabinCoilError("Cabin coil ran twice in one ship-time interval")
        if (row["command"] == "on" and machine.condition not in BROKEN
                and coil_power_node(name) in powered_nodes
                and coil_coolant_node(name) in coolant_nodes):
            operating.append(name)
    total_reserved_kj = min(dt * budget_kw,
                            dt * MAX_UNIT_KW * len(operating))
    share_kj = min(MAX_UNIT_KW * dt,
                   total_reserved_kj / len(operating)) if operating else 0.0
    moved_total = 0.0
    for name in sorted(FANCOILS):
        row = updated["units"][name]
        zone = FANCOILS[name][1]
        actual = 0.0
        if name in operating:
            cell = cells[zone]
            mass = _finite(cell["mass"])
            thermal_capacity = _finite(cell["capacity"], low=EPS)
            energy = _finite(cell["energy"])
            current = _finite(cell["temperature"], low=EPS)
            if mass > 0 and current > COOLING_TARGET_K:
                excess = max(0.0, (current - COOLING_TARGET_K) * (
                    thermal_capacity + mass * GAS_CP_KJ_KG_K))
                actual = min(share_kj, excess, energy - EPS)
                if actual > 0:
                    cell["energy"] = energy - actual
                    cell["temperature"] = cell["energy"] / (
                        thermal_capacity + mass * GAS_CP_KJ_KG_K)
        row["last_kj"] = actual
        row["cumulative_kj"] += actual
        row["last_s"] = now
        moved_total += actual
    updated["meter"]["removed_kj"] += moved_total
    updated["last"] = {
        "removed_kj": moved_total, "reserved_kj": total_reserved_kj,
        "operating": operating,
    }
    validate_cabin_coils(updated)
    if moved_total > total_reserved_kj + EPS:
        raise CabinCoilError("Cabin cooling outran the actual LT radiator budget")
    return updated, cells, total_reserved_kj
