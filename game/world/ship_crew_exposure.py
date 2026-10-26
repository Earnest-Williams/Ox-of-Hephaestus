"""G19 deterministic, finite-resource crew exposure transitions.

Pure transition only: never infer a suit, gas source, or installed room from
an actor's declared intentions. The authoritative world must supply sampled
conditions and verified carried protection before adopting the result.
Game-world verisimilitude, not medical or aerospace qualification.
"""
from __future__ import annotations

import math

MAX_STEP_S = 10.0
OXYGEN_KG_S = 0.00001
CO2_KG_S = 0.000011
SUIT_OXYGEN_CAP_KG = 1.8


class ExposureError(ValueError):
    pass


def _finite(value, *, minimum=0.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExposureError("Exposure quantity must be numerical")
    value = float(value)
    if not math.isfinite(value) or value < minimum:
        raise ExposureError("Exposure quantity out of range")
    return value


def initial_exposure():
    return {
        "hypoxia_s": 0.0, "smoke_dose": 0.0, "thermal_dose": 0.0,
        "co2_dose": 0.0, "water_deficit_kg": 0.0,
        "injury": 0.0, "condition": "fit",
        "suit_oxygen_kg": 0.0, "suit_co2_kg": 0.0,
    }


def step_exposure(previous, environment, dt, *, suited=False,
                  suit_integrity=0.0, drinking_kg=0.0):
    """Return next character state and finite consumed/produced respiratory gas.

    Input environment requires measured pressure, O2/CO2 fractions, smoke
    density and temperature. No unmeasured cell is treated as breathable.
    Suited movement requires a positively verified nonzero integrity and
    finite carried oxygen. CO2 is retained in the suit until serviced.
    """
    dt = _finite(dt)
    if dt > MAX_STEP_S:
        raise ExposureError("Exposure integration step exceeds ten seconds")
    state = dict(previous)
    if set(state) != set(initial_exposure()):
        raise ExposureError("Incomplete or unrecognised exposure state")
    for key in initial_exposure():
        if key != "condition":
            state[key] = _finite(state[key])
    if state["condition"] not in {"fit", "impaired", "incapacitated", "critical", "dead"}:
        raise ExposureError("Unrecognised crew condition")
    if state["condition"] == "dead":
        return state, {"o2_kg": 0.0, "co2_kg": 0.0, "water_kg": 0.0}
    needed = {"pressure_pa", "oxygen_fraction", "co2_fraction",
              "smoke_density", "temperature_k"}
    if not isinstance(environment, dict) or set(environment) != needed:
        raise ExposureError("Missing measured environmental conditions")
    env = {key: _finite(environment[key]) for key in needed}
    if (env["oxygen_fraction"] + env["co2_fraction"] > 1.00000001
            or env["oxygen_fraction"] > 1 or env["co2_fraction"] > 1):
        raise ExposureError("Invalid gas composition")
    integrity = _finite(suit_integrity)
    if integrity > 1 or (suited and integrity <= 0):
        raise ExposureError("Unverified or damaged suit")
    drink = _finite(drinking_kg)
    if drink > 0.001 * dt + 1e-9:
        raise ExposureError("Unphysical instant drinking")
    demand = OXYGEN_KG_S * dt
    healthy_suit = suited and integrity >= 0.8
    if suited:
        supplied = min(demand, state["suit_oxygen_kg"]) if healthy_suit else 0.0
        state["suit_oxygen_kg"] -= supplied
        state["suit_co2_kg"] += CO2_KG_S * dt if supplied >= demand - 1e-12 else 0.0
        breathable = supplied >= demand - 1e-12 and state["suit_co2_kg"] <= 0.25
    else:
        supplied = demand if (env["pressure_pa"] >= 60000
                              and env["oxygen_fraction"] * env["pressure_pa"] >= 16000
                              and env["co2_fraction"] <= 0.015) else 0.0
        breathable = supplied >= demand - 1e-12
    if breathable:
        state["hypoxia_s"] = max(0.0, state["hypoxia_s"] - dt * 0.25)
    else:
        state["hypoxia_s"] += dt
    # Suits reduce smoke contact but do not make extreme radiant heat harmless.
    if not suited:
        state["smoke_dose"] += env["smoke_density"] * dt
        state["co2_dose"] += max(0, env["co2_fraction"] - 0.005) * dt
    temperature = env["temperature_k"]
    if temperature < 273 or temperature > 320:
        state["thermal_dose"] += dt * (max(0, 273 - temperature)
                                      + max(0, temperature - 320)) / (20 if suited else 5)
    else:
        state["thermal_dose"] = max(0.0, state["thermal_dose"] - dt * 0.1)
    state["water_deficit_kg"] = max(0.0, state["water_deficit_kg"]
                                   + dt * 2.0 / 86400 - drink)
    # Nonlinear chronic damage; breathing recovery does not instantly heal injury.
    state["injury"] = min(1.0, state["injury"]
        + dt * (0.001 if state["hypoxia_s"] >= 60 else 0.0)
        + dt * 0.00002 * (state["smoke_dose"] > 30)
        + dt * 0.00002 * (state["thermal_dose"] > 100)
        + dt * 0.00002 * (state["co2_dose"] > 1))
    if state["injury"] >= 1.0 or state["hypoxia_s"] >= 1200:
        state["condition"] = "dead"
    elif state["injury"] >= 0.95 or state["hypoxia_s"] >= 600:
        state["condition"] = "critical"
    elif state["injury"] >= 0.5 or state["hypoxia_s"] >= 180:
        state["condition"] = "incapacitated"
    elif state["injury"] >= 0.15 or state["hypoxia_s"] >= 40 or state["water_deficit_kg"] > 2:
        state["condition"] = "impaired"
    elif state["injury"] < 0.15 and state["hypoxia_s"] < 40:
        state["condition"] = "fit"
    return state, {"o2_kg": supplied, "co2_kg": CO2_KG_S * dt if breathable else 0.0,
                   "water_kg": drink}
