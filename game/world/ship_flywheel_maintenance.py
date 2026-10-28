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
            "interrupted_ticks": 0, "recovered_ticks": 0,
            "rundowns": {}, "rundown_started": 0, "rundown_finished": 0,
            "rundown_halted": 0, "rundown_delivered_kwh": 0.0}


def validate_flywheel_service(ledger):
    if not isinstance(ledger, dict) or set(ledger) != {
            "permits", "issued", "released", "interrupted_ticks", "recovered_ticks",
            "rundowns", "rundown_started", "rundown_finished",
            "rundown_halted", "rundown_delivered_kwh"
    } or not isinstance(ledger["permits"], dict):
        raise FlywheelServiceError("Unrecognised persistent flywheel lockout ledger")
    if len(ledger["permits"]) > 64:
        raise FlywheelServiceError("Unknown maintenance population")
    for key in ("issued", "released", "interrupted_ticks", "recovered_ticks",
                "rundown_started", "rundown_finished", "rundown_halted"):
        if type(ledger[key]) is not int or ledger[key] < 0:
            raise FlywheelServiceError("Invalid maintenance permit counts")
    if ledger["issued"] - ledger["released"] != len(ledger["permits"]):
        raise FlywheelServiceError("A lockout permit was fabricated or lost")
    if (not isinstance(ledger["rundowns"], dict)
            or len(ledger["rundowns"]) > 64
            or ledger["rundown_started"] - ledger["rundown_finished"]
               - ledger["rundown_halted"] != len(ledger["rundowns"])
            or isinstance(ledger["rundown_delivered_kwh"], bool)
            or not isinstance(ledger["rundown_delivered_kwh"], (int, float))
            or not math.isfinite(ledger["rundown_delivered_kwh"])
            or ledger["rundown_delivered_kwh"] < 0):
        raise FlywheelServiceError("Flywheel energy rundown custody corrupted")
    if set(ledger["rundowns"]) & set(ledger["permits"]):
        raise FlywheelServiceError("A spinning rundown has a maintenance padlock")
    for module, job in ledger["rundowns"].items():
        _name(module)
        if not isinstance(job, dict) or set(job) != {
                "worker", "room", "starting_kwh", "remaining_kwh",
                "delivered_kwh", "started_game_time"}:
            raise FlywheelServiceError("Corrupt individually metered rundown")
        if not _ref(job["worker"]) or job["room"] != module_room(module):
            raise FlywheelServiceError("Rundown worker and original bay disagree")
        for field in ("starting_kwh", "remaining_kwh",
                      "delivered_kwh", "started_game_time"):
            val = job[field]
            if (isinstance(val, bool) or
                    not isinstance(val, (float, int)) or
                    not math.isfinite(val) or val < 0):
                raise FlywheelServiceError("Flywheel rundown contains false energy")
        if (job["starting_kwh"] <= ZERO_KWH
                or not math.isclose(
                    job["remaining_kwh"] + job["delivered_kwh"],
                    job["starting_kwh"], rel_tol=1e-9, abs_tol=1e-6)):
            raise FlywheelServiceError("Rundown energy custody does not reconcile")
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
    if (not _ref(worker) or module in ledger["permits"]
            or module in ledger["rundowns"]):
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


def migrate_flywheel_service_v1(ledger):
    """Add rundown bookkeeping to old padlock ledgers without erasing work."""
    if not isinstance(ledger, dict):
        raise FlywheelServiceError("No historical flywheel maintenance ledger")
    if "rundowns" in ledger:
        validate_flywheel_service(ledger)
        return copy.deepcopy(ledger)
    if set(ledger) != {
            "permits", "issued", "released",
            "interrupted_ticks", "recovered_ticks"}:
        raise FlywheelServiceError("Unrecognised pre-rundown repair custody")
    out = copy.deepcopy(ledger)
    out.update(rundowns={}, rundown_started=0, rundown_finished=0,
               rundown_halted=0, rundown_delivered_kwh=0.0)
    validate_flywheel_service(out)
    return out


def begin_rundown(ledger, *, module, worker, charge_kwh, game_time):
    """Start natural electrical discharge of existing measured rotor energy.

    Energy itself stays entirely in the original electrical ledger. This
    work order is only a durable promise to supervise that source.
    """
    validate_flywheel_service(ledger)
    _name(module)
    if (not _ref(worker) or module in ledger["rundowns"]
            or module in ledger["permits"] or
            isinstance(charge_kwh, bool) or
            not isinstance(charge_kwh, (int, float)) or
            not math.isfinite(charge_kwh) or charge_kwh <= ZERO_KWH
            or isinstance(game_time, bool) or
            not isinstance(game_time, (int, float)) or
            not math.isfinite(game_time) or game_time < 0):
        raise FlywheelServiceError("No measured charged rotor available for rundown")
    out = copy.deepcopy(ledger)
    out["rundowns"][module] = {
        "worker": worker, "room": module_room(module),
        "starting_kwh": float(charge_kwh),
        "remaining_kwh": float(charge_kwh),
        "delivered_kwh": 0.0,
        "started_game_time": float(game_time),
    }
    out["rundown_started"] += 1
    validate_flywheel_service(out)
    return out


def advance_rundowns(ledger, *, before_electrical, after_electrical):
    """Reconcile ONLY kWh already discharged by real ship source dispatch."""
    validate_flywheel_service(ledger)
    out = copy.deepcopy(ledger)
    delivered_total = 0.0
    finished = []
    for module, job in sorted(list(out["rundowns"].items())):
        before = before_electrical.get("flywheels", {}).get(module, {}).get(
            "charge_kwh")
        after = after_electrical.get("flywheels", {}).get(module, {}).get(
            "charge_kwh")
        if (not all(isinstance(x, (int, float)) and not isinstance(x, bool)
                    and math.isfinite(x) for x in (before, after))
                or before < -ZERO_KWH or after < -ZERO_KWH
                or not math.isclose(before, job["remaining_kwh"],
                                    rel_tol=1e-9, abs_tol=1e-6)
                or after > before + 1e-6):
            raise FlywheelServiceError("Flywheel rundown has unmetered recharging or lost custody")
        delta = max(0.0, before - after)
        delivered_total += delta
        job["remaining_kwh"] = max(0.0, after)
        job["delivered_kwh"] += delta
        if after <= ZERO_KWH:
            finished.append(module)
            out["rundown_delivered_kwh"] += job["delivered_kwh"]
            out["rundown_finished"] += 1
            del out["rundowns"][module]
    metered = (after_electrical.get("meter", {}).get(
        "flywheel_discharge_kwh", 0.0)
        - before_electrical.get("meter", {}).get(
            "flywheel_discharge_kwh", 0.0))
    if (not isinstance(metered, (int, float)) or
            not math.isfinite(metered) or metered < -1e-6 or
            delivered_total > metered + 1e-5):
        raise FlywheelServiceError("Flywheel rundown energy never reached the ship's metered loads")
    validate_flywheel_service(out)
    return out, tuple(finished), delivered_total


def halt_rundown(ledger, *, module, worker):
    """Stop supervised discharge; measured residual energy remains aboard."""
    validate_flywheel_service(ledger)
    job = ledger["rundowns"].get(_name(module))
    if job is None or job["worker"] != worker:
        raise FlywheelServiceError("Only original rundown worker may halt this module")
    out = copy.deepcopy(ledger)
    del out["rundowns"][module]
    out["rundown_halted"] += 1
    out["rundown_delivered_kwh"] += job["delivered_kwh"]
    validate_flywheel_service(out)
    return out
