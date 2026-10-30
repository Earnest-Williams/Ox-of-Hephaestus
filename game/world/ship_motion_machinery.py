"""Persistent, bounded rotary machinery for the installed Ox freighter.

Drums, habitation ring and independent workshop are independent mechanisms.
All state belongs to the canonical physics clock. Controls are mediated through
receipted physical actions; pure stepping never consults model predictions.
"""
from __future__ import annotations

import math

DRUMS = tuple(f"DR-{i:02d}" for i in range(1, 7))
ROTORS = DRUMS + ("HAB", "WR-01")
NOMINAL_RPM = {**{name: 2.0 for name in DRUMS}, "HAB": 3.45, "WR-01": 3.45}
MAX_RPM = {**{name: 3.0 for name in DRUMS}, "HAB": 3.6, "WR-01": 4.0}
RAMP_RPM_S = {**{name: 0.003 for name in DRUMS}, "HAB": 0.001, "WR-01": 0.006}
ROTOR_MW = {**{name: 0.045 for name in DRUMS}, "HAB": 0.13, "WR-01": 0.09}
GRAVITY_M_S2 = 9.80665
WORK_RADIUS_M = 60.0
HAB_RADIUS_M = 73.15
MAX_IMBALANCE_KGM = 15_000.0


class RotorError(ValueError):
    """Rotary state, command, or physical interlock is invalid."""


def initial_rotors():
    return {
        key: {
            "rpm": 0.0, "target_rpm": 0.0, "phase_rad": 0.0,
            "brake": True, "hardlock": True, "indexing": False,
            "freight_collar": False,
            "passenger_indexer": False, "passenger_station": None,
            "condition": "serviceable",
            "imbalance_kg_m": 0.0, "bearing_temperature_k": 293.15,
            "mode": "PARKED", "bearing_hours": 0.0,
            "work_radius_m": WORK_RADIUS_M if key == "WR-01" else None,
            "work_target_radius_m": WORK_RADIUS_M if key == "WR-01" else None,
        }
        for key in ROTORS
    }


def motion_power_mw(rotors):
    """Bound electric demand using actual rotary movement or braking release."""
    return sum(
        ROTOR_MW[name] for name, row in rotors.items()
        if abs(row["rpm"]) > 0.0001 or row["target_rpm"] > 0 or row["indexing"]
    )


def set_rotor_command(rotors, name, command):
    """Apply a command only after all local/role/world checks have passed."""
    if name not in ROTORS or name not in rotors:
        raise RotorError("Uninstalled rotor")
    rows = {k: dict(v) for k, v in rotors.items()}
    state = rows[name]
    if state["condition"] not in {"serviceable", "worn"}:
        if command != "stop":
            raise RotorError("Damaged rotor must remain inhibited")
    if name == "WR-01" and command.startswith("radius:"):
        try:
            radius = float(command.split(":", 1)[1])
        except (ValueError, TypeError) as exc:
            raise RotorError("Invalid workshop radius") from exc
        if (not math.isfinite(radius) or radius < 24 or radius > 75
                or abs(state["rpm"]) > 0.001 or state["target_rpm"] != 0
                or state["freight_collar"] or state["passenger_indexer"]):
            raise RotorError("Workshop carriage needs stopped, isolated and 24-75 m")
        state["work_target_radius_m"] = radius
    elif command == "stop":
        state["target_rpm"] = 0.0
        state["indexing"] = False
        state["brake"] = False
        state["hardlock"] = False if state["rpm"] > 0.005 else state["hardlock"]
    elif command == "start":
        if (state["freight_collar"] or state["passenger_indexer"] or
                state["imbalance_kg_m"] > MAX_IMBALANCE_KGM):
            raise RotorError("Rotary transfer extended or excessive imbalance")
        state["target_rpm"] = NOMINAL_RPM[name]
        state["brake"] = False
        state["hardlock"] = False
    elif command == "hardlock":
        if abs(state["rpm"]) > 0.001 or state["target_rpm"] != 0:
            raise RotorError("Cannot hard-lock a turning drum")
        if min(state["phase_rad"], 2 * math.pi - state["phase_rad"]) > 0.01:
            raise RotorError("Rotor is not indexed to freight datum")
        state["hardlock"] = True
        state["brake"] = True
        state["indexing"] = False
    elif command == "index":
        if abs(state["rpm"]) > 0.001 or state["target_rpm"] != 0:
            raise RotorError("Stop rotor before indexing")
        if state["freight_collar"] or state["passenger_indexer"]:
            raise RotorError("Retract transfer hardware before indexing")
        state["brake"] = False
        state["hardlock"] = False
        state["indexing"] = True
    elif command == "release":
        if state["freight_collar"] or state["passenger_indexer"]:
            raise RotorError("Retract moving transfer hardware before brake release")
        state["hardlock"] = False
        state["brake"] = False
        state["indexing"] = False
    elif command == "freight_extend":
        if name not in DRUMS and name != "WR-01":
            raise RotorError("No full-sled freight collar at this rotor")
        if (not state["hardlock"] or not state["brake"] or
                abs(state["rpm"]) > 0.001 or state["target_rpm"] != 0 or
                state["passenger_indexer"]):
            raise RotorError("Freight needs stopped, braked hardlock without passenger movement")
        if (name == "WR-01" and
                (abs(state["work_radius_m"] - 24.0) > 0.05 or
                 abs(state["work_target_radius_m"] - 24.0) > 0.05)):
            raise RotorError("Workshop freight requires retracted 24 m carriage")
        state["freight_collar"] = True
    elif command == "freight_retract":
        state["freight_collar"] = False
    elif command == "passenger_extend" or command in {
            "passenger_extend:A", "passenger_extend:B"}:
        if name == "HAB":
            if command not in {"passenger_extend:A", "passenger_extend:B"}:
                raise RotorError("Habitation indexer needs explicit A or B station")
            station = command.rsplit(":", 1)[1]
        elif command == "passenger_extend":
            station = None
        else:
            raise RotorError("Only HAB has individually selected indexer stations")
        if (state["freight_collar"] or state["indexing"]
                or not state["hardlock"] or not state["brake"]
                or state["target_rpm"] != 0 or abs(state["rpm"]) >= 0.001
                or min(state["phase_rad"] % (2 * math.pi),
                       (2 * math.pi - state["phase_rad"]) % (2 * math.pi)) > 0.01):
            raise RotorError("Passenger carriage needs indexed stationary hardlock")
        if state["passenger_indexer"] and state.get("passenger_station") != station:
            raise RotorError("Different passenger station already captured")
        state["passenger_indexer"] = True
        state["passenger_station"] = station
    elif command == "passenger_retract":
        state["passenger_indexer"] = False
        state["passenger_station"] = None
    else:
        raise RotorError("Unknown rotary command")
    return rows


def step_rotors(rotors, dt, *, powered, equipment_ok=None, extension_ok=True):
    """Integrate separate rotor ramp, coasting, alignment and heat exposure."""
    if not math.isfinite(dt) or dt < 0 or dt > 60:
        raise RotorError("Invalid bounded rotary step")
    equipment_ok = equipment_ok or {}
    result = {}
    for name in ROTORS:
        row = dict(rotors[name])
        rpm = float(row["rpm"])
        target = float(row["target_rpm"])
        phase = float(row["phase_rad"])
        if (not all(math.isfinite(x) for x in (rpm, target, phase))
                or rpm < 0 or target < 0 or target > MAX_RPM[name]):
            raise RotorError("Invalid rotary state")
        serviceable = equipment_ok.get(name, True) and row["condition"] in {"serviceable", "worn"}
        locally_powered = powered.get(name, False) if isinstance(powered, dict) else powered
        if not serviceable:
            row["target_rpm"] = 0.0
            target = 0.0
        if not locally_powered:
            # No electrically driven holding torque. Bearings and drag
            # dissipate rotation slowly instead of freezing the rotor in place.
            target = 0.0
        delta = RAMP_RPM_S[name] * dt * (1.0 if locally_powered and serviceable else 0.25)
        next_rpm = max(rpm - delta, min(rpm + delta, target))
        if row["brake"] or row["hardlock"] or row["freight_collar"]:
            if rpm > 0.001:
                raise RotorError("Brake or freight collar engaged on moving rotor")
            next_rpm = 0.0
        if name == "WR-01":
            radius = row["work_radius_m"]
            target_radius = row["work_target_radius_m"]
            if not 24 <= radius <= 75 or not 24 <= target_radius <= 75:
                raise RotorError("Invalid workshop carriage extension")
            if locally_powered and serviceable and extension_ok and rpm < 0.001 and not row["freight_collar"]:
                travel = 0.05 * dt
                row["work_radius_m"] = max(radius - travel,
                                           min(radius + travel, target_radius))
            row["stores_radius_m"] = row["work_radius_m"] / 3.0
        row["rpm"] = next_rpm
        row["phase_rad"] = (phase + (rpm + next_rpm) * math.pi / 60.0 * dt) % (2 * math.pi)
        if row["indexing"] and next_rpm < 0.001 and locally_powered and serviceable:
            distance = (2 * math.pi - row["phase_rad"]) % (2 * math.pi)
            if distance <= 0.02 * dt:
                row["phase_rad"] = 0.0
                row["indexing"] = False
            else:
                row["phase_rad"] = (row["phase_rad"] + 0.02 * dt) % (2 * math.pi)
        row["mode"] = (
            "INDEXING" if row["indexing"] else
            "TRIPPED" if not serviceable else
            "BRAKED" if row["brake"] else
            "PARKED" if next_rpm < 0.001 else
            "SPINDOWN" if next_rpm < rpm - 1e-9 else
            "RELEASING" if next_rpm > rpm + 1e-9 else "ROTATING"
        )
        ambient = 293.15
        ratio = next_rpm / MAX_RPM[name]
        load_heat = ((0.001 + 0.02 * ratio ** 2) * (1 + 5 *
                     row["imbalance_kg_m"] / MAX_IMBALANCE_KGM)
                     if next_rpm else 0.0)
        heat = (load_heat - 0.001 * (row["bearing_temperature_k"] - ambient)) * dt
        row["bearing_hours"] += dt / 3600 if next_rpm else 0.0
        row["bearing_temperature_k"] = max(ambient, row["bearing_temperature_k"] + heat)
        if row["bearing_temperature_k"] >= 365.0:
            row["condition"] = "faulted"
            row["target_rpm"] = 0.0
        result[name] = row
    return result


def rotor_gravity(rotors, name):
    row = rotors[name]
    radius = (row["work_radius_m"] if name == "WR-01"
              else HAB_RADIUS_M if name == "HAB" else 30.0)
    return (row["rpm"] * 2 * math.pi / 60) ** 2 * radius / GRAVITY_M_S2
