"""G19 real F1/F2 module isolation and persistent maintenance custody.

Each of the 64 original flywheels retains its energy inside the existing
ship electrical ledger. A lockout NEVER zeros energy, charges a new source,
or turns an open breaker into a permission to touch spinning machinery.
"""
from __future__ import annotations

import copy
import math
import re

from world.ship_electrical_power import FLYWHEELS

ZERO_KWH = 1e-7
MAX_TICK_S = 60.0
MODULES = frozenset(FLYWHEELS)


class FlywheelServiceError(ValueError):
    pass


def _ref(value):
    return isinstance(value, str) and re.fullmatch(r"#[0-9]+", value) is not None


def _name(module):
    if module not in MODULES:
        raise FlywheelServiceError("Not one of the 64 installed F1/F2 modules")
    return module


def module_room(module):
    return _name(module)[:2] + "-BAY"


def module_breaker(module):
    return "ISO-PWR-" + _name(module)


def initial_flywheel_service():
    return {"permits": {}, "issued": 0, "released": 0,
            "interrupted_ticks": 0, "recovered_ticks": 0}


def validate_flywheel_service(ledger):
    if not isinstance(ledger, dict) or set(ledger) != {
            "permits", "issued", "released", "interrupted_ticks", "recovered_ticks"
    } or not isinstance(ledger["permits"], dict):
        raise FlywheelServiceError("Unrecognised persistent flywheel lockout ledger")
    if len(ledger["permits"]) > 64:
        raise FlywheelServiceError("Unknown maintenance population")
    for key in ("issued", "released", "interrupted_ticks", "recovered_ticks"):
        if type(ledger[key]) is not int or ledger[key] < 0:
            raise FlywheelServiceError("Invalid maintenance permit counts")
    if ledger["issued"] - ledger["released"] != len(ledger["permits"]):
        raise FlywheelServiceError("A lockout permit was fabricated or lost")
    for module, permit in ledger["permits"].items():
        _name(module)
        if not isinstance(permit, dict) or set(permit) != {
                "worker", "room", "breaker", "issued_game_time",
                "initial_charge_kwh"}:
            raise FlywheelServiceError("Corrupt individual flywheel work permit")
        if (not _ref(permit["worker"])
                or permit["room"] != module_room(module)
                or permit["breaker"] != module_breaker(module)):
            raise FlywheelServiceError("Lockout not bound to original module and worker")
        for value in ("issued_game_time", "initial_charge_kwh"):
            n = permit[value]
            if (isinstance(n, bool) or not isinstance(n, (int, float))
                    or not math.isfinite(n) or n < 0):
                raise FlywheelServiceError("Invalid recorded energy or work time")
        if permit["initial_charge_kwh"] > ZERO_KWH:
            raise FlywheelServiceError("Maintenance permit issued against stored spin energy")
    return True


def module_dead(module, electrical, switches):
    """Check independently rated, physically isolated, stopped module.

    We cannot infer zero energy from an open breaker. The authoritative,
    individually surveyed kWh store must be at zero, in standby.
    """
    _name(module)
    if (not isinstance(electrical, dict)
            or not isinstance(electrical.get("flywheels"), dict)):
        return False
    store = electrical["flywheels"].get(module)
    if (not isinstance(store, dict)
            or isinstance(store.get("charge_kwh"), bool)
            or not isinstance(store.get("charge_kwh"), (int, float))
            or not math.isfinite(store["charge_kwh"])
            or store["charge_kwh"] < 0
            or store["charge_kwh"] > ZERO_KWH
            or store.get("mode") != "standby"):
        return False
    switch = switches.get(module_breaker(module)) if isinstance(switches, dict) else None
    if switch is None:
        return False
    condition = getattr(switch, "condition", None)
    setting = getattr(switch, "setting", None)
    if isinstance(switch, dict):
        condition, setting = switch.get("condition"), switch.get("setting")
    return bool(setting == "open" and condition == "serviceable")


def permit_live(ledger, module, electrical, switches):
    validate_flywheel_service(ledger)
    return module in ledger["permits"] and module_dead(
        module, electrical, switches)


def issue_permit(ledger, *, module, worker, game_time,
                 electrical, switches):
    validate_flywheel_service(ledger)
    _name(module)
    if not _ref(worker) or module in ledger["permits"]:
        raise FlywheelServiceError("Worker or unique original module lockout invalid")
    if not module_dead(module, electrical, switches):
        raise FlywheelServiceError("Measured flywheel not completely stopped and disconnected")
    if (isinstance(game_time, bool)
            or not isinstance(game_time, (int, float))
            or not math.isfinite(game_time) or game_time < 0):
        raise FlywheelServiceError("Unmeasured local lockout time")
    out = copy.deepcopy(ledger)
    out["permits"][module] = {
        "worker": worker, "room": module_room(module),
        "breaker": module_breaker(module),
        "issued_game_time": float(game_time),
        "initial_charge_kwh": electrical["flywheels"][module]["charge_kwh"],
    }
    out["issued"] += 1
    validate_flywheel_service(out)
    return out


def release_permit(ledger, *, module, worker, repair_active=False):
    validate_flywheel_service(ledger)
    permit = ledger["permits"].get(_name(module))
    if (permit is None or permit["worker"] != worker or repair_active):
        raise FlywheelServiceError(
            "Only original local owner can release after completing machine work")
    out = copy.deepcopy(ledger)
    del out["permits"][module]
    out["released"] += 1
    validate_flywheel_service(out)
    return out


def service_pulse(ledger, *, interrupted, recovered):
    """Accumulate bounded observed safety interruptions, without resetting permits."""
    validate_flywheel_service(ledger)
    if type(interrupted) is not int or type(recovered) is not int or (
            interrupted < 0 or recovered < 0 or
            interrupted > len(ledger["permits"]) or
            recovered > len(ledger["permits"])):
        raise FlywheelServiceError("Unbounded work-safety accounting")
    out = copy.deepcopy(ledger)
    out["interrupted_ticks"] += interrupted
    out["recovered_ticks"] += recovered
    validate_flywheel_service(out)
    return out


def bus_safe(side, switches):
    """Switchboard work needs BOTH incoming lines and all 32 modules open."""
    if side not in {"F1", "F2"} or not isinstance(switches, dict):
        return False
    for identifier in (f"ISO-{side}-BUS-IN-1", f"ISO-{side}-BUS-IN-2",
                       *(module_breaker(m) for m in FLYWHEELS if m[:2] == side)):
        row = switches.get(identifier)
        if row is None:
            return False
        cond = row.get("condition") if isinstance(row, dict) else getattr(row, "condition", None)
        setting = row.get("setting") if isinstance(row, dict) else getattr(row, "setting", None)
        if cond != "serviceable" or setting != "open":
            return False
    return True
