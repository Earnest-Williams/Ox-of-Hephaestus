"""Game-scaled FTL passage contract, sourced from Ox v0.5 design.

This module does not pretend to solve cosmological navigation. Route distances
are world-commissioned; the navigation state conserves actual bunker mass,
progresses in game time, and fails without free arrival on an actual fault.
"""
from __future__ import annotations

import math
import re

SECONDS_PER_LY_AT_C = 365.25 * 86400.0
BASE_T_PER_LY = 400.0
REFERENCE_SHIP_T = 1_200_000.0
MIN_SPEED_C = 5.0
MAX_SPEED_C = 100.0
PROTECTED_FTL_KG = 1_200_000.0
AUXILIARY_MW = 0.20
FIELD_HEAT_KW = 150.0


class NavigationError(ValueError):
    pass


def _finite(number):
    if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
        raise NavigationError("Invalid FTL physical quantity")
    return float(number)


def leg_fuel_kg(distance_ly, speed_c, frozen_departure_mass_kg):
    distance, speed, mass = map(_finite, (
        distance_ly, speed_c, frozen_departure_mass_kg))
    if distance <= 0 or not MIN_SPEED_C <= speed <= MAX_SPEED_C or mass <= 0:
        raise NavigationError("Route outside selected FTL envelope")
    return (distance * BASE_T_PER_LY * 1000.0
            * (mass / (REFERENCE_SHIP_T * 1000.0))
            * (1.0 + 4.0 * math.log(speed / MIN_SPEED_C)))


def prepare_leg(motion, *, route_id, destination, distance_ly, speed_c):
    """World-issued leg; refuses spending protected bunkers on routine travel."""
    if (not isinstance(route_id, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", route_id) is None
            or not isinstance(destination, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", destination) is None):
        raise NavigationError("Route and destination need finite canonical identifiers")
    if motion.get("ftl_leg", {}).get("status") in {"planned", "engaged"}:
        raise NavigationError("Existing FTL route must conclude or be abandoned")
    duration = _finite(distance_ly) * SECONDS_PER_LY_AT_C / _finite(speed_c)
    if duration <= 0 or not math.isfinite(duration):
        raise NavigationError("Invalid FTL travel duration")
    departure = sum(motion[key] for key in (
        "dry_mass_kg", "cargo_mass_kg", "ftl_fuel_kg",
        "mission_fluids_kg", "propellant_kg"))
    fuel = leg_fuel_kg(distance_ly, speed_c, departure)
    if motion["ftl_fuel_kg"] - fuel < PROTECTED_FTL_KG:
        raise NavigationError("Selected voyage would spend protected FTL reserve")
    result = dict(motion)
    result["ftl_leg"] = {
        "route_id": route_id, "destination": destination,
        "distance_ly": float(distance_ly), "cruise_c": float(speed_c),
        "duration_s": duration, "remaining_s": duration,
        "total_fuel_kg": fuel, "consumed_fuel_kg": 0.0,
        "departure_mass_kg": departure, "status": "planned", "reason": None,
    }
    return result


def command_leg(motion, route_id, command):
    result = dict(motion)
    leg = result.get("ftl_leg")
    if not leg or leg["route_id"] != route_id:
        raise NavigationError("No commissioned FTL route")
    leg = dict(leg)
    if command == "engage":
        if leg["status"] != "planned":
            raise NavigationError("FTL passage not prepared")
        if (result["command"] != "coast"
                or result["attitude_command"] != "hold"
                or any(abs(v) > 0.0001 for v in result["angular_velocity_rad_s"])):
            raise NavigationError("Stable coast and attitude required to translate")
        leg["status"] = "engaged"
    elif command == "abort":
        if leg["status"] not in {"planned", "engaged"}:
            raise NavigationError("Route is not active")
        leg["status"] = "aborted"
        leg["reason"] = "crew_abort"
    else:
        raise NavigationError("Only engage or abort are FTL crew commands")
    result["ftl_leg"] = leg
    return result


def advance_leg(motion, dt, *, field_healthy, power_headroom_mw):
    result = dict(motion)
    leg = result.get("ftl_leg")
    if not leg or leg["status"] != "engaged":
        return result, 0.0
    if not math.isfinite(dt) or dt < 0 or dt > 60:
        raise NavigationError("Invalid FTL tick")
    leg = dict(leg)
    if not field_healthy or power_headroom_mw + 1e-9 < AUXILIARY_MW:
        leg["status"] = "aborted"
        leg["reason"] = "field_failure" if not field_healthy else "electrical_shortfall"
        result["ftl_leg"] = leg
        return result, 0.0
    elapsed = min(dt, leg["remaining_s"])
    # Compute cumulative burn from elapsed fraction to avoid multiplying
    # already-spent fuel and introducing per-tick rounding drift.
    remaining = max(0.0, leg["remaining_s"] - elapsed)
    total_due = leg["total_fuel_kg"] * (1.0 - remaining / leg["duration_s"])
    spent = max(0.0, total_due - leg["consumed_fuel_kg"])
    if spent > result["ftl_fuel_kg"] + 1e-6:
        raise NavigationError("FTL bunker has been depleted unexpectedly")
    result["ftl_fuel_kg"] -= spent
    result["expended_ftl_fuel_kg"] += spent
    leg["consumed_fuel_kg"] += spent
    leg["remaining_s"] = remaining
    if remaining <= 1e-8:
        leg["status"] = "arrived"
        result["nav_location"] = leg["destination"]
    result["ftl_leg"] = leg
    return result, AUXILIARY_MW
