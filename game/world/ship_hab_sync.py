"""G19 two-station HAB moving-carrier phase capture; pure mechanics.

An independent inner indexer accelerates to HAB's real ring RPM and seeks
angular phase over game time. It is not a substitute for rotor hardlocking,
nor is phase alignment an instantaneous teleport. A captured mechanical
yoke co-rotates with HAB; power is still required for personnel transfer.
"""
from __future__ import annotations

import copy
import math

ACCEL_RPM_S = 0.065
PHASE_TRIM_RAD_S = 0.090
CAPTURE_RPM_EPS = 0.012
CAPTURE_PHASE_EPS = 0.018
MIN_MOVING_RPM = 0.30
MAX_HAB_RPM = 3.6


class HabSyncError(ValueError):
    pass


def _finite(x, low=0.0, high=None):
    if (isinstance(x, bool) or not isinstance(x, (int, float))
            or not math.isfinite(x) or x < low or (high is not None and x > high)):
        raise HabSyncError("Invalid moving HAB indexer measurement")
    return float(x)


def _phase_delta(target, current):
    return (target - current + math.pi) % (2 * math.pi) - math.pi


def initial_hab_sync():
    return {
        "station": None, "mode": "stowed", "rpm": 0.0,
        "phase_rad": 0.0, "captured": False, "seconds_synchronising": 0.0,
        "captures": 0,
    }


def validate_hab_sync(sync):
    if not isinstance(sync, dict) or set(sync) != set(initial_hab_sync()):
        raise HabSyncError("Invalid HAB moving-indexer register")
    if sync["station"] not in (None, "A", "B"):
        raise HabSyncError("Uninstalled HAB moving station")
    if sync["mode"] not in ("stowed", "seeking", "captured"):
        raise HabSyncError("Invalid phase-capture mode")
    _finite(sync["rpm"], high=MAX_HAB_RPM + 0.1)
    _finite(sync["phase_rad"], high=2 * math.pi)
    _finite(sync["seconds_synchronising"])
    if isinstance(sync["captures"], bool) or not isinstance(sync["captures"], int) or sync["captures"] < 0:
        raise HabSyncError("Invalid capture count")
    if type(sync["captured"]) is not bool or sync["captured"] != (sync["mode"] == "captured"):
        raise HabSyncError("Capture latch inconsistent")
    if (sync["mode"] == "stowed") != (sync["station"] is None):
        raise HabSyncError("Stowed station allocation inconsistent")
    return True


def command_hab_sync(sync, action, *, hab_rpm, parked_indexer=False, occupied=False):
    validate_hab_sync(sync)
    hab_rpm = _finite(hab_rpm, high=MAX_HAB_RPM)
    result = copy.deepcopy(sync)
    if action == "release":
        if occupied:
            raise HabSyncError("Occupied rotating HAB carrier cannot disengage")
        return initial_hab_sync() | {"captures": sync["captures"]}
    if action not in {"sync:A", "sync:B"}:
        raise HabSyncError("Select moving HAB station A or B")
    if parked_indexer:
        raise HabSyncError("Parked and moving HAB collars cannot engage together")
    if hab_rpm <= MIN_MOVING_RPM:
        raise HabSyncError("HAB must actually be rotating for moving capture")
    station = action[-1]
    if sync["station"] not in (None, station):
        raise HabSyncError("Opposite HAB carrier owns the active capture")
    if sync["mode"] in {"seeking", "captured"}:
        return result
    result.update(station=station, mode="seeking", rpm=0.0,
                  phase_rad=0.0, captured=False, seconds_synchronising=0.0)
    validate_hab_sync(result)
    return result


def step_hab_sync(sync, dt, *, hab_rpm, hab_phase_rad, powered, hardware_ok=True):
    """Finite acceleration and phase seek; return a new verified latch state."""
    validate_hab_sync(sync)
    dt = _finite(dt, high=10)
    target = _finite(hab_rpm, high=MAX_HAB_RPM)
    phase = _finite(hab_phase_rad, high=2 * math.pi) % (2 * math.pi)
    if type(powered) is not bool or type(hardware_ok) is not bool:
        raise HabSyncError("No verified motor power or equipment assessment")
    result = copy.deepcopy(sync)
    if result["mode"] == "stowed":
        return result
    if result["mode"] == "captured":
        if target <= MIN_MOVING_RPM or not hardware_ok:
            # A damaged capture stops being safe immediately; transfer pauses.
            result["mode"], result["captured"] = "seeking", False
        else:
            # Physical latch co-rotates even without electric drive.
            result["rpm"], result["phase_rad"] = target, phase
            return result
    if not powered or not hardware_ok or target <= MIN_MOVING_RPM:
        # Unpowered carrier coasts, cannot magically freeze or keep matching.
        result["rpm"] = max(0.0, result["rpm"] - ACCEL_RPM_S * dt * 0.15)
        result["phase_rad"] = (result["phase_rad"] +
                               result["rpm"] * math.pi * dt / 30) % (2 * math.pi)
        return result
    initial_rpm = result["rpm"]
    result["rpm"] = max(initial_rpm - ACCEL_RPM_S * dt,
                        min(initial_rpm + ACCEL_RPM_S * dt, target))
    result["phase_rad"] = (
        result["phase_rad"] +
        (initial_rpm + result["rpm"]) * math.pi * dt / 60) % (2 * math.pi)
    result["seconds_synchronising"] += dt
    if abs(result["rpm"] - target) <= CAPTURE_RPM_EPS:
        error = _phase_delta(phase, result["phase_rad"])
        trim = max(-PHASE_TRIM_RAD_S * dt, min(PHASE_TRIM_RAD_S * dt, error))
        result["phase_rad"] = (result["phase_rad"] + trim) % (2 * math.pi)
        if abs(_phase_delta(phase, result["phase_rad"])) < CAPTURE_PHASE_EPS:
            result["phase_rad"] = phase
            result["mode"], result["captured"] = "captured", True
            result["captures"] += 1
    validate_hab_sync(result)
    return result


def moving_hab_ready(sync, *, station, hab_rpm, hab_phase_rad,
                     hardware_ok, powered):
    validate_hab_sync(sync)
    if not (hardware_ok and powered and sync["mode"] == "captured"
            and sync["station"] == station and sync["captured"]):
        return False
    target = _finite(hab_rpm, high=MAX_HAB_RPM)
    phase = _finite(hab_phase_rad, high=2 * math.pi) % (2 * math.pi)
    return (target > MIN_MOVING_RPM
            and abs(sync["rpm"] - target) <= CAPTURE_RPM_EPS
            and abs(_phase_delta(phase, sync["phase_rad"])) <= CAPTURE_PHASE_EPS)
