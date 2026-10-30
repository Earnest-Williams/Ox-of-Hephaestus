"""G19 evidence-bound local machinery diagnosis and maintenance restart.

A case records what a worker physically saw; it never scans unvisited rooms.
Only the 72 authored auxiliary motors and 26 separately breakered secondary
services have sufficient individual feeder evidence for this generic protocol.
Specialist flywheel, exterior and hull permits remain independently mandatory.
"""
from __future__ import annotations

import copy
import math

from world.ship_auxiliary_electrical import (
    MOTORS, PROTECTED_FIRE_MOTORS, auxiliary_ids, protected_fire_ids,
)
from world.ship_equipment_services import SERVICE_LOADS, service_ids

BROKEN = frozenset({"degraded", "faulted", "failed", "jammed", "severed"})
STAGES = frozenset({
    "inspected", "isolated", "repairing", "repaired", "checked",
    "authorized", "verified",
})
LIMIT = 256


class FaultRecoveryError(ValueError):
    """An observed fault lacks current, physical maintenance evidence."""


def feeders_for(name):
    """Only exact separately fitted circuit identities, not inferred fuses."""
    if name in SERVICE_LOADS:
        return (service_ids(name)[2],)
    if name in MOTORS:
        ids = [auxiliary_ids(name, motor=True)[2]]
        if name in PROTECTED_FIRE_MOTORS:
            ids.append(protected_fire_ids(name)[1])
        return tuple(ids)
    raise FaultRecoveryError("No audited individually isolatable machinery circuit")


def verified_open_feeders(name, fitted_breakers):
    """Each original retrofit breaker must exist *at its machine's worksite*.

    An open label on a missing/damaged/wrong-network switch does not establish
    a physical isolation. Fire pumps have two separately routed feeders.
    """
    expected = feeders_for(name)
    if not isinstance(fitted_breakers, dict) or set(fitted_breakers) != set(expected):
        return False
    room = (SERVICE_LOADS[name] if name in SERVICE_LOADS else MOTORS[name])[0]
    for key in expected:
        row = fitted_breakers[key]
        net = ("g19_equipment_service" if name in SERVICE_LOADS else
               "g19_motor_protected" if key.startswith("ISO-G19-PROT-")
               else "g19_motor")
        if (row is None or getattr(row, "category", None) != "isolator"
                or getattr(row, "source_id", None) != key
                or getattr(row, "space_id", None) != room
                or getattr(row, "condition", None) != "serviceable"
                or getattr(row, "setting", None) != "open"
                or not isinstance(getattr(row, "reference", None), dict)
                or row.reference.get("network") != net
                or row.reference.get("kind") != "breaker"
                or row.reference.get("manual_operation") is not True):
            return False
    return True


def verified_restored_feeders(name, fitted_breakers, *, checked_s, last_good_s):
    """Evidence of real crew reconnection and a *subsequent* live panel sample.

    This is a positive test of the fitted electrical identity and source age;
    it does not bypass the independent circuit power or alarm interlocks.
    """
    _number(checked_s)
    if last_good_s is None:
        return False
    _number(last_good_s)
    expected = feeders_for(name)
    if not isinstance(fitted_breakers, dict) or set(fitted_breakers) != set(expected):
        return False
    room = (SERVICE_LOADS[name] if name in SERVICE_LOADS else MOTORS[name])[0]
    for key in expected:
        row = fitted_breakers[key]
        net = ("g19_equipment_service" if name in SERVICE_LOADS else
               "g19_motor_protected" if key.startswith("ISO-G19-PROT-")
               else "g19_motor")
        if (row is None or getattr(row, "category", None) != "isolator"
                or getattr(row, "source_id", None) != key
                or getattr(row, "space_id", None) != room
                or getattr(row, "condition", None) != "serviceable"
                or getattr(row, "setting", None) != "closed"
                or not isinstance(getattr(row, "reference", None), dict)
                or row.reference.get("network") != net
                or row.reference.get("kind") != "breaker"
                or row.reference.get("manual_operation") is not True
                or not isinstance(getattr(row, "details", None), dict)
                or row.details.get("physics_power_trip_latched")):
            return False
        closed_s = row.details.get("physics_manual_close_game_s")
        if (type(closed_s) not in (int, float) or not math.isfinite(closed_s)
                or closed_s < checked_s or last_good_s <= closed_s):
            return False
    return True


def initial_fault_cases():
    return {"version": 1, "cases": {}, "verified": 0}


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise FaultRecoveryError("Unmeasured or negative maintenance datum")
    return float(value)


def _actor(actor):
    if not isinstance(actor, str) or not actor.startswith("#") or not actor[1:].isdigit():
        raise FaultRecoveryError("Physical crew identity required")
    return actor


def validate_fault_cases(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"version", "cases", "verified"}
            or ledger["version"] != 1
            or not isinstance(ledger["cases"], dict)
            or len(ledger["cases"]) > LIMIT
            or type(ledger["verified"]) is not int or ledger["verified"] < 0):
        raise FaultRecoveryError("Corrupt or oversized equipment fault register")
    required = {
        "machine", "room", "stage", "fault_type", "source_alarm",
        "source_panel", "observed_condition", "inspected_by",
        "inspected_s", "inspected_revision", "repair_stamp_before",
        "spares_before_kg", "feeders", "isolation_s", "repair_stamp_s",
        "repaired_spares_kg", "checked_by", "checked_s", "authorized_by",
        "authorized_s", "authorized_samples",
        "restart_consecutive_good", "restart_observation_s",
        "verified_by", "verified_s",
    }
    for name, case in ledger["cases"].items():
        if not isinstance(case, dict) or set(case) != required:
            raise FaultRecoveryError("Corrupt individual equipment investigation")
        if (name not in (set(SERVICE_LOADS) | set(MOTORS))
                or case["machine"] != name or case["feeders"] != list(feeders_for(name))
                or not isinstance(case["room"], str) or not case["room"]
                or case["stage"] not in STAGES
                or case["fault_type"] not in {"hardware", "protection", "restart", "outage"}
                or case["observed_condition"] not in (
                    "serviceable", "degraded", "faulted", "failed", "jammed", "severed")
                or case["source_alarm"] is not None and
                    not isinstance(case["source_alarm"], str)
                or case["source_panel"] is not None and
                    not isinstance(case["source_panel"], str)):
            raise FaultRecoveryError("Inconsistent machine and diagnostic evidence")
        for name_field in ("inspected_by", "checked_by", "authorized_by", "verified_by"):
            if case[name_field] is not None:
                _actor(case[name_field])
        for time_field in ("inspected_s", "isolation_s", "repair_stamp_s",
                           "checked_s", "authorized_s", "verified_s",
                           "repair_stamp_before", "spares_before_kg", "repaired_spares_kg",
                           "restart_observation_s"):
            if case[time_field] is not None:
                _number(case[time_field])
        if (type(case["inspected_revision"]) is not int
                or case["inspected_revision"] < 0
                or type(case["authorized_samples"]) not in (int, type(None))
                or case["authorized_samples"] is not None
                    and case["authorized_samples"] < 0
                or type(case["restart_consecutive_good"]) is not int
                or not 0 <= case["restart_consecutive_good"] <= 2
                or case["restart_consecutive_good"] and
                    case["restart_observation_s"] is None):
            raise FaultRecoveryError("Invalid revision or independent sample count")
        if (case["inspected_by"] is None or case["inspected_s"] is None
                or case["stage"] in {"isolated", "repairing", "repaired", "checked",
                                     "authorized", "verified"}
                and case["isolation_s"] is None):
            raise FaultRecoveryError("Missing physical inspection or isolation")
        if case["stage"] in {"repaired", "checked", "authorized", "verified"} and (
                case["fault_type"] == "hardware"
                and (case["repair_stamp_s"] is None
                     or case["repaired_spares_kg"] is None)):
            raise FaultRecoveryError("Hardware allegedly restored without completed finite work")
        if case["stage"] in {"checked", "authorized", "verified"} and (
                case["checked_s"] is None or case["checked_by"] is None):
            raise FaultRecoveryError("Missing post-repair inspection")
        if case["stage"] in {"authorized", "verified"} and (
                case["authorized_s"] is None or case["authorized_by"] is None
                or case["authorized_samples"] is None):
            raise FaultRecoveryError("Missing local restart release")
        if case["stage"] == "verified" and (
                case["verified_s"] is None or case["verified_by"] is None
                or case["restart_consecutive_good"] != 2):
            raise FaultRecoveryError("Unverified machine marked operating")
        for earlier, later in (
                ("inspected_s", "isolation_s"),
                ("isolation_s", "repair_stamp_s"),
                ("isolation_s", "checked_s"),
                ("checked_s", "authorized_s"),
                ("authorized_s", "restart_observation_s"),
                ("authorized_s", "verified_s")):
            if (case[earlier] is not None and case[later] is not None
                    and case[later] < case[earlier]):
                raise FaultRecoveryError("Machine case chronology contradicts physical work")
        if case["stage"] in {"inspected", "isolated", "repairing",
                             "repaired", "checked"} and (
                case["restart_consecutive_good"] != 0
                or case["restart_observation_s"] is not None):
            raise FaultRecoveryError("Restart evidence before its authorisation")
    return True


def inspect_fault(ledger, name, *, room, actor, now_s, condition,
                  revision, repair_stamp, cumulative_spares_kg,
                  feeder_tripped, restart_latched, alarm=None, panel=None):
    """A worker at the equipment distinguishes hardware, breaker and latch.

    Panel-alarm evidence is optional: looking at a real damaged machine is
    direct evidence even when the local panel is dark. No alarm is invented.
    """
    validate_fault_cases(ledger)
    _actor(actor)
    _number(now_s)
    _number(cumulative_spares_kg)
    if repair_stamp is not None:
        _number(repair_stamp)
    if (not isinstance(room, str) or not room
            or condition not in {"serviceable", *BROKEN}
            or type(revision) is not int or revision < 0
            or type(feeder_tripped) is not bool
            or type(restart_latched) is not bool
            or alarm is not None and not isinstance(alarm, str)
            or panel is not None and not isinstance(panel, str)):
        raise FaultRecoveryError("Invalid contemporaneous physical fault survey")
    feeder_ids = feeders_for(name)
    if condition in BROKEN:
        fault_type = "hardware"
    elif feeder_tripped:
        fault_type = "protection"
    elif restart_latched:
        fault_type = "restart"
    elif alarm is not None:
        fault_type = "outage"
    else:
        raise FaultRecoveryError("No witnessed machinery fault to investigate")
    result = copy.deepcopy(ledger)
    prior = result["cases"].get(name)
    if prior and prior["stage"] not in {"verified", "inspected"}:
        raise FaultRecoveryError("Existing service permit must be completed or resolved")
    if prior and prior["stage"] == "inspected" and prior["inspected_by"] != actor:
        raise FaultRecoveryError("Existing inspection belongs to another attending worker")
    if name not in result["cases"] and len(result["cases"]) == LIMIT:
        raise FaultRecoveryError("Durable maintenance register full")
    result["cases"][name] = {
        "machine": name, "room": room, "stage": "inspected",
        "fault_type": fault_type, "source_alarm": alarm,
        "source_panel": panel, "observed_condition": condition,
        "inspected_by": actor, "inspected_s": float(now_s),
        "inspected_revision": revision, "repair_stamp_before": repair_stamp,
        "spares_before_kg": float(cumulative_spares_kg),
        "feeders": list(feeder_ids), "isolation_s": None,
        "repair_stamp_s": None, "repaired_spares_kg": None,
        "checked_by": None, "checked_s": None, "authorized_by": None,
        "authorized_s": None, "authorized_samples": None,
        "restart_consecutive_good": 0, "restart_observation_s": None,
        "verified_by": None, "verified_s": None,
    }
    validate_fault_cases(result)
    return result


def isolate_fault(ledger, name, *, actor, now_s, open_feeders, stopped,
                  worksite_safe):
    validate_fault_cases(ledger)
    case = ledger["cases"].get(name)
    if not case or case["stage"] != "inspected":
        raise FaultRecoveryError("Inspect the actual failed machine first")
    _actor(actor)
    _number(now_s)
    if (not open_feeders or not stopped or not worksite_safe
            or now_s < case["inspected_s"]):
        raise FaultRecoveryError("Physical breaker lockout and stopped safe machine required")
    result = copy.deepcopy(ledger)
    result["cases"][name]["isolation_s"] = float(now_s)
    result["cases"][name]["stage"] = "isolated"
    validate_fault_cases(result)
    return result


def begin_verified_work(ledger, name, *, isolated):
    validate_fault_cases(ledger)
    case = ledger["cases"].get(name)
    if not case or case["stage"] != "isolated" or case["fault_type"] != "hardware":
        raise FaultRecoveryError("Inspect and isolate this equipment defect before work")
    if not isolated:
        raise FaultRecoveryError("Loss of genuine local lockout forbids starting repair")
    out = copy.deepcopy(ledger)
    out["cases"][name]["stage"] = "repairing"
    validate_fault_cases(out)
    return out


def finished_verified_work(ledger, name, *, stamp, installed_kg):
    validate_fault_cases(ledger)
    case = ledger["cases"].get(name)
    if not case or case["stage"] != "repairing":
        raise FaultRecoveryError("Replacement was not commissioned under an active permit")
    _number(stamp)
    _number(installed_kg)
    if (stamp <= case["inspected_s"]
            or case["repair_stamp_before"] is not None
               and stamp <= case["repair_stamp_before"]
            or installed_kg <= 0):
        raise FaultRecoveryError("Replacement has no new finite work receipt")
    out = copy.deepcopy(ledger)
    out["cases"][name]["stage"] = "repaired"
    out["cases"][name]["repair_stamp_s"] = float(stamp)
    out["cases"][name]["repaired_spares_kg"] = float(installed_kg)
    validate_fault_cases(out)
    return out


def check_repair(ledger, name, *, actor, now_s, condition, open_feeders,
                 stopped, tripped, active_work, repair_stamp,
                 cumulative_spares_kg):
    validate_fault_cases(ledger)
    case = ledger["cases"].get(name)
    if not case or case["stage"] not in {"repaired", "isolated"}:
        raise FaultRecoveryError("No completed isolated fault to verify")
    _actor(actor)
    _number(now_s)
    _number(cumulative_spares_kg)
    if (condition != "serviceable" or not open_feeders or not stopped
            or tripped or active_work or now_s < case["isolation_s"]):
        raise FaultRecoveryError("Post-repair inspection requires stopped sound isolated hardware")
    if case["fault_type"] == "hardware":
        if (case["stage"] != "repaired" or repair_stamp is None
                or repair_stamp != case["repair_stamp_s"]
                or cumulative_spares_kg + 1e-7 <
                        case["spares_before_kg"] + case["repaired_spares_kg"]):
            raise FaultRecoveryError("No matching installed spare and real repair completion")
    elif case["stage"] != "isolated":
        raise FaultRecoveryError("Nonhardware protection must remain physically isolated")
    out = copy.deepcopy(ledger)
    out["cases"][name]["stage"] = "checked"
    out["cases"][name]["checked_by"] = actor
    out["cases"][name]["checked_s"] = float(now_s)
    validate_fault_cases(out)
    return out


def authorize_restart(ledger, name, *, actor, now_s, sample_count,
                      sound_hardware, live_feeder, tripped, active_work):
    validate_fault_cases(ledger)
    case = ledger["cases"].get(name)
    _actor(actor)
    _number(now_s)
    if type(sample_count) is not int or sample_count < 0:
        raise FaultRecoveryError("Missing current ship instrument sample count")
    if not case or case["stage"] != "checked":
        raise FaultRecoveryError("No completed local post-repair inspection")
    if now_s < case["checked_s"]:
        raise FaultRecoveryError("Restart permission precedes inspection")
    if active_work:
        raise FaultRecoveryError("An actual maintenance work order is still active")
    if tripped:
        raise FaultRecoveryError("A real incoming feeder remains protection-tripped")
    if not sound_hardware:
        raise FaultRecoveryError("Machine condition or local instrument sample is unverified")
    if not live_feeder:
        raise FaultRecoveryError("No currently conducting, assured physical machine feed")
    result = copy.deepcopy(ledger)
    row = result["cases"][name]
    row["stage"] = "authorized"
    row["authorized_by"] = actor
    row["authorized_s"] = float(now_s)
    row["authorized_samples"] = sample_count
    row["restart_consecutive_good"] = 0
    row["restart_observation_s"] = None
    validate_fault_cases(result)
    return result


def advance_restart_evidence(ledger, *, now_s, observed_good):
    """Count consecutive corroborated *local machine* samples.

    A source blackout, missing panel, stopped rotor/motor, real breaker trip,
    or local alarm resets the count. A repeat for the same physics epoch
    cannot manufacture another observation, including across reloads.
    """
    validate_fault_cases(ledger)
    _number(now_s)
    authorized = {
        name for name, case in ledger["cases"].items()
        if case["stage"] == "authorized"}
    if not isinstance(observed_good, dict) or set(observed_good) != authorized:
        raise FaultRecoveryError("Incomplete fitted machine observation set")
    out = copy.deepcopy(ledger)
    for name, good in sorted(observed_good.items()):
        if type(good) is not bool:
            raise FaultRecoveryError("A machine observation must be physical boolean evidence")
        case = out["cases"][name]
        if (now_s <= case["authorized_s"]
                or (case["restart_observation_s"] is not None
                    and now_s <= case["restart_observation_s"])):
            raise FaultRecoveryError("Duplicate, stale or reordered machine measurement")
        case["restart_consecutive_good"] = (
            min(2, case["restart_consecutive_good"] + 1) if good else 0)
        case["restart_observation_s"] = float(now_s)
    validate_fault_cases(out)
    return out


def verify_restart(ledger, name, *, actor, now_s, sample_count, running,
                   live_feeder, condition, tripped, alarm_active,
                   panel_live, signal_quality_clear):
    validate_fault_cases(ledger)
    case = ledger["cases"].get(name)
    _actor(actor)
    _number(now_s)
    if (not case or case["stage"] != "authorized"
            or type(sample_count) is not int
            or sample_count < case["authorized_samples"] + 2
            or now_s <= case["authorized_s"]
            or case["restart_consecutive_good"] < 2
            or not running or not live_feeder or condition != "serviceable"
            or tripped or alarm_active or not panel_live
            or signal_quality_clear is not True):
        raise FaultRecoveryError(
            "Two real instrument epochs and actual running output required; no remote all-clear")
    result = copy.deepcopy(ledger)
    result["cases"][name]["stage"] = "verified"
    result["cases"][name]["verified_by"] = actor
    result["cases"][name]["verified_s"] = float(now_s)
    result["verified"] += 1
    validate_fault_cases(result)
    return result
