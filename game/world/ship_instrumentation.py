"""G19 instrument evidence and attended fault recovery over ORIGINAL ship panels.

No new sensor, conductor, room, source, or invisible remote telemetry is
commissioned. Readings originate at installed powered local panels, with
independent source/status/age/quality. Incident history survives restart;
acknowledgement cannot repair a machine, dismiss an active fault, reset a
breaker, or fill a consumable.
"""
from __future__ import annotations

import copy
import math
import re

MAX_HISTORY = 2048
MAX_ALARMS = 4096
MAX_PANEL_HISTORY = 24
MAX_SAMPLE_SECONDS = 60.0
EPS = 1e-8
BROKEN = frozenset({"faulted", "failed", "jammed", "destroyed", "severed"})
FAULT_CODES = frozenset({
    "MACHINE_FAULT", "MACHINE_DEGRADED", "SERVICE_OUTAGE",
    "BREAKER_TRIP", "MOTOR_TRIP", "FIRE_LOOP_FAULT",
    "WATER_QUARANTINE", "WATER_RESERVE_LOW", "NUTRIENT_EXHAUSTED",
    "FOOD_SPOILAGE", "CARGO_CLIMATE", "ROTOR_FAULT", "DRIVE_INHIBITED",
})
LEVELS = {
    "FIRE": "critical", "PRESSURE_LOW": "critical",
    "RAPID_DECOMPRESSION": "critical", "TEMPERATURE_RISE_RATE": "warning",
    "INSTRUMENT_UNRELIABLE": "warning",
    "PRESSURE_HIGH": "critical", "OXYGEN_LOW": "critical",
    "OXYGEN_HIGH": "warning", "CO2_HIGH": "critical",
    "SMOKE": "critical", "LEAK": "critical",
    "TEMPERATURE_HIGH": "warning", "TEMPERATURE_LOW": "warning",
    "CELL_DAMAGE": "warning", "BREAKER_TRIP": "warning",
    "MOTOR_TRIP": "warning", "MACHINE_FAULT": "warning",
    "MACHINE_DEGRADED": "advisory", "SERVICE_OUTAGE": "warning",
    "FIRE_LOOP_FAULT": "warning", "INSTRUMENT_LOST": "warning",
    "WATER_QUARANTINE": "critical", "WATER_RESERVE_LOW": "warning",
    "NUTRIENT_EXHAUSTED": "warning", "FOOD_SPOILAGE": "advisory",
    "CARGO_CLIMATE": "warning", "ROTOR_FAULT": "warning",
    "DRIVE_INHIBITED": "advisory",
}
METRICS = frozenset({
    "pressure_kpa", "oxygen_kpa", "temperature_k", "co2_fraction",
    "smoke_fraction", "burn_kg_s", "leak_kg_s", "cell_damage",
    "water_working_kg", "nutrient_kg", "spoiled_food_kg",
})
GUIDANCE = {
    "FIRE": ("fire", "Attend local smoke/heat indication; inspect affected "
             "cell and operate installed mist and air isolation"),
    "SMOKE": ("fire", "Check the local fire loop, smoke source, dampers "
              "and fitted fire-pump water supply"),
    "RAPID_DECOMPRESSION": (
        "pressure", "Two live samples show rapidly falling pressure; "
        "verify local hull boundary, rated isolation and leaks immediately"),
    "TEMPERATURE_RISE_RATE": (
        "thermal", "Two consecutive local samples show rapid heating; "
        "inspect actually running coolant, power and fire protection"),
    "INSTRUMENT_UNRELIABLE": (
        "instrumentation", "Original panel is physically degraded. "
        "Do not trust old gauges; inspect its feeder and repair the panel"),
    "PRESSURE_LOW": ("pressure", "Verify local pressure boundary, rated "
                     "hatches and existing hull containment work"),
    "PRESSURE_HIGH": ("pressure", "Check local gas admission regulators "
                      "and pressure isolation rather than venting blindly"),
    "OXYGEN_LOW": ("life_support", "Check local atmosphere manifold, "
                   "powered ECLSS and independent stored breathing reserves"),
    "OXYGEN_HIGH": ("life_support", "Check ECLSS oxygen generator and "
                    "isolation before any hot work"),
    "CO2_HIGH": ("life_support", "Check powered circulation and finite "
                 "scrubber media; do not assume automatic capture"),
    "LEAK": ("pressure", "Inspect existing pressure boundary and local "
              "isolation; use suited damage-control procedure if required"),
    "TEMPERATURE_HIGH": ("thermal", "Inspect running cooling machinery, "
                         "LT/HT valves, radiator heat rejection and supply"),
    "TEMPERATURE_LOW": ("thermal", "Inspect heating, coolant flow and "
                        "loss of ECLSS power"),
    "CELL_DAMAGE": ("damage_control", "Survey existing hull restoration "
                    "and physical damage-control access"),
    "BREAKER_TRIP": ("electrical", "Verify source, branch isolation, "
                     "short/overload clearance and local manual reset"),
    "MOTOR_TRIP": ("electrical", "Inspect motor, fuse, source supply "
                   "and any required attended restart"),
    "MACHINE_FAULT": ("maintenance", "Examine physically fitted machine; "
                      "use existing finite-spares repair and toolkit work"),
    "MACHINE_DEGRADED": ("maintenance", "Schedule attended inspection and "
                         "finite-spares service before loss of capacity"),
    "SERVICE_OUTAGE": ("electrical", "Check original machine feeder, "
                       "manual-restart latch and upstream branch state"),
    "INSTRUMENT_LOST": ("instrumentation", "Verify this actual local "
                        "panel, its original power breaker and panel condition"),
    "FIRE_LOOP_FAULT": ("fire", "Inspect existing detector loop and "
                        "its protected distribution; loss of monitoring is not all-clear"),
    "WATER_QUARANTINE": ("water", "Sample and filter existing water "
                         "inventory using finite original consumables"),
    "WATER_RESERVE_LOW": ("water", "Review protected reserve release, "
                          "recycling and currently operating treatment trains"),
    "NUTRIENT_EXHAUSTED": ("food", "Carry genuine inventory-debited nutrient "
                           "spares to the original growing room"),
    "FOOD_SPOILAGE": ("food", "Move genuine spoiled goods to fitted "
                      "sanitation receiver and correct room conditions"),
    "CARGO_CLIMATE": ("cargo", "Inspect cargo drum atmosphere and thermal "
                      "skids and local power/temperature settings"),
    "ROTOR_FAULT": ("rotary", "Check actual bearing/drive isolation, "
                    "RPM, brakes and service lock before intervention"),
    "DRIVE_INHIBITED": ("propulsion", "Inspect original drives, "
                        "thermal sinks and current authorised work permits"),
}


class InstrumentError(ValueError):
    """A sensor, sample or acknowledgement violates physical instrumentation."""


def _num(x, lower=0.0, upper=math.inf):
    if type(x) not in (int, float) or not math.isfinite(x) or not lower <= x <= upper:
        raise InstrumentError("Invalid or unbounded measured instrument value")
    return float(x)


def _panel_name(name):
    if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9_-]{3,90}", name) is None:
        raise InstrumentError("Only actual installed panel identity is accepted")
    return name


def alarm_key(panel, code, subject):
    _panel_name(panel)
    if code not in LEVELS or not isinstance(subject, str) or not subject:
        raise InstrumentError("Unknown alarm subject or class")
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,90}", subject) is None:
        raise InstrumentError("Invalid alarm source identity")
    return f"{panel}|{code}|{subject}"


def initial_instrumentation(panel_rooms, panel_zones, *, start_s):
    """The original panel and pressure-zone identities are all mandatory."""
    time = _num(start_s)
    if (not isinstance(panel_rooms, dict) or not isinstance(panel_zones, dict)
            or not panel_rooms or set(panel_rooms) != set(panel_zones)
            or len(panel_rooms) > 200):
        raise InstrumentError("Missing or invented original panel inventory")
    if any(not isinstance(room, str) or not room for room in panel_rooms.values()):
        raise InstrumentError("Unfitted instrument room")
    for ident in panel_rooms:
        _panel_name(ident)
        if not (ident.startswith("LP-") or ident.endswith("-LP")):
            raise InstrumentError("Survey uses only original powered local panels")
        if panel_zones[ident] is not None and not isinstance(panel_zones[ident], str):
            raise InstrumentError("Unidentified physical pressure zone")
    return {
        "version": 1, "panels": {
            key: {"room": panel_rooms[key], "zone": panel_zones[key],
                  "status": "unobserved", "last_sample_s": None,
                  "last_good_s": None, "metrics": {}}
            for key in sorted(panel_rooms)
        },
        "alarms": {}, "history": [], "sequence": 0,
        "last_s": time, "sample_count": 0,
    }


def _validate_event(row):
    if (not isinstance(row, dict) or set(row) !=
            {"seq", "time_s", "alarm", "transition", "level"}
            or type(row["seq"]) is not int or row["seq"] < 1
            or not isinstance(row["alarm"], str)
            or row["transition"] not in {"raised", "acknowledged", "resolved", "reasserted"}
            or row["level"] not in {"critical", "warning", "advisory"}):
        raise InstrumentError("Corrupt instrument history")
    _num(row["time_s"])


def validate_instrumentation(ledger, *, panel_rooms=None):
    if (not isinstance(ledger, dict) or set(ledger) != {
            "version", "panels", "alarms", "history", "sequence",
            "last_s", "sample_count"}
            or ledger["version"] != 1 or not isinstance(ledger["panels"], dict)
            or not ledger["panels"] or len(ledger["panels"]) > 200
            or not isinstance(ledger["alarms"], dict)
            or len(ledger["alarms"]) > MAX_ALARMS
            or not isinstance(ledger["history"], list)
            or len(ledger["history"]) > MAX_HISTORY
            or type(ledger["sequence"]) is not int or ledger["sequence"] < 0
            or type(ledger["sample_count"]) is not int or ledger["sample_count"] < 0):
        raise InstrumentError("Missing instrumentation history or physical panel roster")
    _num(ledger["last_s"])
    if panel_rooms is not None:
        if set(ledger["panels"]) != set(panel_rooms) or any(
                row.get("room") != panel_rooms[name] for name, row
                in ledger["panels"].items()):
            raise InstrumentError("Instrumentation layout drift from original equipment")
    for name, row in ledger["panels"].items():
        _panel_name(name)
        if (not isinstance(row, dict) or set(row) != {
                "room", "zone", "status", "last_sample_s", "last_good_s", "metrics"}
                or not isinstance(row["room"], str) or not row["room"]
                or row["status"] not in {"unobserved", "online", "dark", "damaged", "degraded"}
                or not isinstance(row["metrics"], dict)
                or set(row["metrics"]) - METRICS):
            raise InstrumentError("Invented or corrupted panel instrumentation")
        for key in ("last_sample_s", "last_good_s"):
            if row[key] is not None and _num(row[key]) > ledger["last_s"] + EPS:
                raise InstrumentError("Instrumentation measurement from the future")
        if row["status"] == "online" and row["last_good_s"] is None:
            raise InstrumentError("Live indication with no sample")
        for value in row["metrics"].values():
            _num(value)
    for key, alarm in ledger["alarms"].items():
        if not isinstance(alarm, dict) or set(alarm) != {
                "panel", "code", "subject", "level", "active",
                "ack_by", "ack_s", "first_s", "last_s", "clear_samples",
                "occurrences"}:
            raise InstrumentError("Unknown alarm entry")
        if (alarm["panel"] not in ledger["panels"] or
                key != alarm_key(alarm["panel"], alarm["code"], alarm["subject"])
                or alarm["level"] != LEVELS[alarm["code"]]
                or type(alarm["active"]) is not bool
                or type(alarm["clear_samples"]) is not int
                or not 0 <= alarm["clear_samples"] <= 2
                or type(alarm["occurrences"]) is not int
                or alarm["occurrences"] < 1):
            raise InstrumentError("Alarm forged or not linked to a real panel")
        if alarm["ack_by"] is not None and (
                not isinstance(alarm["ack_by"], str) or
                re.fullmatch(r"#[0-9]+", alarm["ack_by"]) is None):
            raise InstrumentError("Unknown human alarm acknowledgement")
        for field in ("ack_s", "first_s", "last_s"):
            if alarm[field] is not None and _num(alarm[field]) > ledger["last_s"] + EPS:
                raise InstrumentError("Alarm acknowledgement or detection from future")
    prior = 0
    for event in ledger["history"]:
        _validate_event(event)
        if event["seq"] <= prior or event["seq"] > ledger["sequence"]:
            raise InstrumentError("Duplicate or reordered durable instrument event")
        prior = event["seq"]
    return True


def _append(out, alarm, transition, now_s):
    out["sequence"] += 1
    out["history"].append({
        "seq": out["sequence"], "time_s": now_s, "alarm": alarm,
        "transition": transition, "level": out["alarms"][alarm]["level"]})
    if len(out["history"]) > MAX_HISTORY:
        out["history"] = out["history"][-MAX_HISTORY:]


def _metric_faults(metrics, subject):
    # A physically measured pressure cell is not necessarily monitored.
    # Only the live installed PANEL samples are ever examined by this function.
    alarms = set()
    if not metrics:
        return alarms
    def present(metric):
        return metric in metrics
    def emit(code):
        alarms.add((code, subject))
    if present("pressure_kpa") and metrics["pressure_kpa"] < 80.0: emit("PRESSURE_LOW")
    if present("pressure_kpa") and metrics["pressure_kpa"] > 125.0: emit("PRESSURE_HIGH")
    if present("oxygen_kpa") and metrics["oxygen_kpa"] < 16.0: emit("OXYGEN_LOW")
    if present("oxygen_kpa") and metrics["oxygen_kpa"] > 26.0: emit("OXYGEN_HIGH")
    if present("co2_fraction") and metrics["co2_fraction"] > 0.008: emit("CO2_HIGH")
    if present("smoke_fraction") and metrics["smoke_fraction"] > 0.00001: emit("SMOKE")
    if present("burn_kg_s") and metrics["burn_kg_s"] > EPS: emit("FIRE")
    if present("leak_kg_s") and metrics["leak_kg_s"] > EPS: emit("LEAK")
    if present("temperature_k") and metrics["temperature_k"] > 313.15: emit("TEMPERATURE_HIGH")
    if present("temperature_k") and metrics["temperature_k"] < 278.15: emit("TEMPERATURE_LOW")
    if present("cell_damage") and metrics["cell_damage"] >= .2: emit("CELL_DAMAGE")
    if present("water_working_kg") and metrics["water_working_kg"] < 3000.0:
        emit("WATER_RESERVE_LOW")
    if present("nutrient_kg") and metrics["nutrient_kg"] <= EPS:
        emit("NUTRIENT_EXHAUSTED")
    if present("spoiled_food_kg") and metrics["spoiled_food_kg"] >= 10.0:
        emit("FOOD_SPOILAGE")
    return alarms


def _rate_faults(prior, current, seconds, subject):
    """Trend ONLY two consecutive credible local samples, never a blackout."""
    dt = _num(seconds)
    if dt <= EPS or dt > MAX_SAMPLE_SECONDS + EPS:
        raise InstrumentError("No independent bounded local sample pair")
    result = set()
    if "pressure_kpa" in prior and "pressure_kpa" in current:
        fall = (prior["pressure_kpa"] - current["pressure_kpa"]) / dt
        if fall > 0.12:
            result.add(("RAPID_DECOMPRESSION", subject))
    if "temperature_k" in prior and "temperature_k" in current:
        rise = (current["temperature_k"] - prior["temperature_k"]) / dt
        if rise > 0.30:
            result.add(("TEMPERATURE_RISE_RATE", subject))
    return result


def panel_selftest(ledger, panel_id, *, now_s, condition, powered):
    """Live source and last-sample check, NOT sensor calibration or repair."""
    validate_instrumentation(ledger)
    now = _num(now_s)
    if now != ledger["last_s"] or panel_id not in ledger["panels"]:
        raise InstrumentError("Self-test needs current fitted panel epoch")
    if not isinstance(powered, bool) or not isinstance(condition, str):
        raise InstrumentError("Self-test requires physical hardware condition")
    p = ledger["panels"][panel_id]
    age = now - p["last_good_s"] if p["last_good_s"] is not None else None
    passed = bool(powered and condition == "serviceable"
                  and p["status"] == "online" and age is not None
                  and age <= MAX_SAMPLE_SECONDS)
    return {
        "panel": panel_id, "original_room": p["room"],
        "current_condition": condition, "current_panel_power": powered,
        "last_sample_status": p["status"], "last_good_age_s": age,
        "passed_last_known_channel_and_power_check": passed,
        "requires_physical_service": condition != "serviceable",
        "qualification": "source_and_last_measured_data_only_not_sensor_calibration",
        "does_not_acknowledge_clear_isolate_or_repair": True,
    }


def sample_instrumentation(ledger, now_s, readings):
    """Advance once, from the measured panel->power->sensor evidence.

    A DARK panel does not emit current fire/pressure truth and cannot clear
    the last observed incident. It records signal loss, preserving its last
    known observations with age. One good sample is insufficient to clear
    latched faults: require two independent succeeding ship-time samples.
    """
    validate_instrumentation(ledger)
    now = _num(now_s)
    if (now <= ledger["last_s"] + EPS or
            now - ledger["last_s"] > MAX_SAMPLE_SECONDS + EPS):
        raise InstrumentError("Non-monotonic or skipped instrumentation physics interval")
    if not isinstance(readings, dict) or set(readings) != set(ledger["panels"]):
        raise InstrumentError("Missing a physical installed panel sample")
    out = copy.deepcopy(ledger)
    out["last_s"] = now
    out["sample_count"] += 1
    signalled = {}
    for panel, evidence in sorted(readings.items()):
        if (not isinstance(evidence, dict) or set(evidence) !=
                {"status", "metrics", "faults"}
                or evidence["status"] not in {"online", "dark", "damaged", "degraded"}
                or not isinstance(evidence["metrics"], dict)
                or set(evidence["metrics"]) - METRICS
                or not isinstance(evidence["faults"], (list, tuple))):
            raise InstrumentError("Unknown or incomplete fitted panel reading")
        old = out["panels"][panel]
        previous_status = old["status"]
        previous_good_s = old["last_good_s"]
        previous_metrics = dict(old["metrics"])
        status = evidence["status"]
        old["status"] = status
        old["last_sample_s"] = now
        active = set()
        if status == "online":
            for value in evidence["metrics"].values():
                _num(value)
            old["metrics"] = dict(evidence["metrics"])
            old["last_good_s"] = now
            zone = old["zone"] or old["room"]
            active.update(_metric_faults(old["metrics"], zone))
            if (previous_status == "online" and previous_good_s is not None
                    and 0 < now - previous_good_s <= MAX_SAMPLE_SECONDS):
                active.update(_rate_faults(
                    previous_metrics, old["metrics"], now - previous_good_s, zone))
            for fault in evidence["faults"]:
                if (not isinstance(fault, (tuple, list)) or len(fault) != 2
                        or fault[0] not in FAULT_CODES):
                    raise InstrumentError("No identified actual machine fault")
                active.add((fault[0], fault[1]))
        else:
            if evidence["metrics"] or evidence["faults"]:
                raise InstrumentError("Unpowered panel cannot report a fresh signal")
            active.add((
                "INSTRUMENT_UNRELIABLE" if status == "degraded"
                else "INSTRUMENT_LOST", panel))
        keys = {alarm_key(panel, code, subject) for code, subject in active}
        signalled[panel] = keys
        for code, subject in sorted(active):
            key = alarm_key(panel, code, subject)
            previous = out["alarms"].get(key)
            if previous is None:
                if len(out["alarms"]) >= MAX_ALARMS:
                    retired = next((k for k, a in out["alarms"].items()
                                    if not a["active"]), None)
                    if retired is None:
                        raise InstrumentError("Active alarm capacity exhausted")
                    del out["alarms"][retired]
                out["alarms"][key] = {
                    "panel": panel, "code": code, "subject": subject,
                    "level": LEVELS[code], "active": True,
                    "ack_by": None, "ack_s": None,
                    "first_s": now, "last_s": now,
                    "clear_samples": 0, "occurrences": 1}
                _append(out, key, "raised", now)
            else:
                if not previous["active"]:
                    previous["active"] = True
                    previous["occurrences"] += 1
                    previous["ack_by"] = None
                    previous["ack_s"] = None
                    _append(out, key, "reasserted", now)
                previous["clear_samples"] = 0
                previous["last_s"] = now
        # On instrument blackout, retain all previous hazard alarms: the
        # absence of data is NOT evidence of pressure/fire recovery.
        if status != "online":
            continue
        for key, old_alarm in list(out["alarms"].items()):
            if (old_alarm["panel"] == panel and old_alarm["active"]
                    and key not in keys):
                old_alarm["clear_samples"] += 1
                if old_alarm["clear_samples"] >= 2:
                    old_alarm["active"] = False
                    old_alarm["clear_samples"] = 2
                    _append(out, key, "resolved", now)
    validate_instrumentation(out)
    return out


def acknowledge_alarm(ledger, panel_id, key, *, actor, now_s):
    """An attended, powered panel records human acknowledgement, not repair."""
    validate_instrumentation(ledger)
    now = _num(now_s)
    if now != ledger["last_s"]:
        raise InstrumentError("Alarm acknowledgement must use canonical ship clock")
    if (panel_id not in ledger["panels"] or key not in ledger["alarms"]
            or ledger["alarms"][key]["panel"] != panel_id
            or ledger["panels"][panel_id]["status"] != "online"):
        raise InstrumentError("No available local alarm to acknowledge")
    if not isinstance(actor, str) or re.fullmatch(r"#[0-9]+", actor) is None:
        raise InstrumentError("Human acknowledgement needs real crew identity")
    out = copy.deepcopy(ledger)
    fault = out["alarms"][key]
    if fault["ack_by"] is not None:
        raise InstrumentError("Alarm already acknowledged, not a new repair")
    fault["ack_by"] = actor
    fault["ack_s"] = now
    _append(out, key, "acknowledged", now)
    validate_instrumentation(out)
    return out


def diagnostics(ledger, alarm_id, *, panel_id):
    validate_instrumentation(ledger)
    row = ledger["alarms"].get(alarm_id)
    if row is None or row["panel"] != panel_id:
        raise InstrumentError("No actually witnessed fault at this panel")
    family, instruction = GUIDANCE[row["code"]]
    sample = ledger["panels"][panel_id]
    return {
        "alarm_id": alarm_id, "family": family, "observed_code": row["code"],
        "subject": row["subject"], "level": row["level"],
        "active": row["active"], "acknowledged_by": row["ack_by"],
        "panel_status": sample["status"],
        "age_s": (ledger["last_s"] - sample["last_good_s"]
                  if sample["last_good_s"] is not None else None),
        "next_physical_checks": instruction,
        "certainty": "observed_condition_only_not_proven_root_cause",
        "does_not_isolate_or_repair": True,
    }


def panel_readout(ledger, panel_id, *, now_s, history_limit=MAX_PANEL_HISTORY):
    validate_instrumentation(ledger)
    now = _num(now_s)
    if panel_id not in ledger["panels"]:
        raise InstrumentError("Panel identity not fitted")
    if (type(history_limit) is not int
            or not 1 <= history_limit <= MAX_PANEL_HISTORY):
        raise InstrumentError("Unbounded history read")
    p = ledger["panels"][panel_id]
    alarms = {
        key: copy.deepcopy(alarm)
        for key, alarm in sorted(ledger["alarms"].items())
        if alarm["panel"] == panel_id and alarm["active"]
    }
    history = [copy.deepcopy(e) for e in ledger["history"]
               if e["alarm"].startswith(panel_id + "|")]
    return {
        "panel": panel_id, "room": p["room"], "zone": p["zone"],
        "status": p["status"], "last_good_s": p["last_good_s"],
        "age_s": (now - p["last_good_s"] if p["last_good_s"] is not None
                  else None),
        "measurements": (copy.deepcopy(p["metrics"])
                         if p["status"] == "online" else None),
        "active_alarms": alarms, "recent_events": history[-history_limit:],
        "sample_count": ledger["sample_count"],
        "scope": "physically_attended_original_local_panel_only",
    }
