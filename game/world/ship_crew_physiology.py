"""G19 human exposure coupled to the real pressure-cell gas and heat ledger.

Pure, bounded transitions. Only an explicitly registered real crew object may
be sampled by the installed Evennia world. Breathing transforms available
oxygen into equal *accounted gas mass* of CO2. The equal-mass gas proxy
avoids creating atmospheric mass from an unmodelled food-carbon inventory;
food/water physiology can subsequently refine the chemistry. Human waste heat
adds a bounded local load to the existing compartment energy store.
"""
from __future__ import annotations

import copy
import math

from world.ship_crew_exposure import (
    ExposureError, initial_exposure, step_exposure,
)

MAX_STEP_S = 10.0
GAS_CP_KJ_KG_K = 1.005
AIR_R_J_KG_K = 287.05
RESTING_HEAT_KW = 0.080
SMOKE_HAZARD_SCALE = 100.0


class CrewPhysiologyError(ValueError):
    """Reject impossible crew or gas state rather than assuming safety."""


def _nonnegative(value):
    if (isinstance(value, bool) or not isinstance(value, (float, int))
            or not math.isfinite(value) or value < 0):
        raise CrewPhysiologyError("Nonphysical gas or physiology measurement")
    return float(value)


def validate_crew_health(health):
    """The canonical crew-health row uses the exact pure exposure schema."""
    required = initial_exposure()
    if not isinstance(health, dict) or set(health) != set(required):
        raise CrewPhysiologyError("Crew injury history is incomplete")
    for name in required:
        if name == "condition":
            if health[name] not in {
                    "fit", "impaired", "incapacitated", "critical", "dead"}:
                raise CrewPhysiologyError("Unknown physically recorded crew condition")
        else:
            _nonnegative(health[name])
    if health["injury"] > 1:
        raise CrewPhysiologyError("Injury severity exceeds finite scale")
    return True


def measured_environment(cell):
    """Sample one authoritative existing pressure cell, or None for vacuum."""
    if cell is None:
        return {
            "pressure_pa": 0.0, "oxygen_fraction": 0.0,
            "co2_fraction": 0.0, "smoke_density": 0.0,
            "temperature_k": 294.0,
        }
    required = {
        "mass", "oxygen", "co2", "smoke", "volume",
        "temperature", "capacity", "energy",
    }
    if not isinstance(cell, dict) or not required <= set(cell):
        raise CrewPhysiologyError("Missing real pressure-cell measurements")
    for name in required:
        _nonnegative(cell[name])
    if not cell["volume"] or not cell["temperature"] or not cell["capacity"]:
        raise CrewPhysiologyError("Unmeasured or impossible occupied gas envelope")
    if (cell["oxygen"] + cell["co2"] + cell["smoke"] > cell["mass"] + 1e-7):
        raise CrewPhysiologyError("Breathing gas species do not reconcile")
    mass = cell["mass"]
    return {
        "pressure_pa": mass * AIR_R_J_KG_K * cell["temperature"] / cell["volume"],
        "oxygen_fraction": cell["oxygen"] / mass if mass else 0.0,
        "co2_fraction": cell["co2"] / mass if mass else 0.0,
        "smoke_density": min(1000.0, cell["smoke"] /
                             mass * SMOKE_HAZARD_SCALE) if mass else 0.0,
        "temperature_k": cell["temperature"],
    }


def step_crew_in_space(health, cell, seconds):
    """Advance one unsuited human and the same compartment's *finite* gas.

    Returns (health, updated_gas_or_None, receipt). Never consumes oxygen that
    is absent. The original compartment's total gas mass stays unchanged:
    oxygen used is converted into the same accounted mass of carbon dioxide.
    """
    validate_crew_health(health)
    dt_total = _nonnegative(seconds)
    if dt_total > MAX_STEP_S:
        raise CrewPhysiologyError("Crew tick must be at most ten seconds")
    current = copy.deepcopy(health)
    gas = copy.deepcopy(cell)
    environment = measured_environment(gas)
    try:
        updated, spent = step_exposure(current, environment, dt_total)
    except ExposureError as exc:
        raise CrewPhysiologyError(str(exc)) from exc
    breathed = _nonnegative(spent["o2_kg"])
    if gas is None:
        if breathed:
            raise CrewPhysiologyError("Crew cannot inhale absent air")
    else:
        if breathed > gas["oxygen"] + 1e-9:
            raise CrewPhysiologyError("Crew attempted to breathe nonexistent oxygen")
        gas["oxygen"] = max(0.0, gas["oxygen"] - breathed)
        gas["co2"] += breathed
        # Metabolic heat is an explicit 80 W per actually living person.
        if current["condition"] != "dead":
            gas["energy"] += RESTING_HEAT_KW * dt_total
            gas["temperature"] = gas["energy"] / (
                gas["capacity"] + gas["mass"] * GAS_CP_KJ_KG_K)
        measured_environment(gas)
    validate_crew_health(updated)
    return updated, gas, {
        "o2_used_kg": breathed,
        "co2_added_kg": breathed,
        "metabolic_heat_kj": RESTING_HEAT_KW * dt_total
                             if current["condition"] != "dead" and gas is not None
                             else 0.0,
    }
