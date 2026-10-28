"""Adapter from current installed Evennia ship states to G19 panel evidence.

This is deliberately NOT a global failure oracle. A given live local panel
reads only its physical pressure zone and co-located equipment/switchgear.
An unpowered/destroyed panel reports no fresh environmental measurements.
"""
from __future__ import annotations

import math

from world.ship_food_cultivation import GROW_BAYS
from world.ship_instrumentation import InstrumentError, BROKEN


def original_panel_roster(installed_model):
    if not isinstance(installed_model, dict):
        raise InstrumentError("Original world reference missing")
    zones = {room["id"]: room.get("pressure_zone")
             for room in installed_model["spaces"]}
    panels = [e for e in installed_model["equipment"]
              if e["kind"] == "local_panel"]
    nodes = {n["id"]: n for n in installed_model["service_nodes"]}
    rooms = {}
    panel_zones = {}
    for row in panels:
        name, room = row["id"], row["space_id"]
        node = nodes.get("NODE-" + name)
        if (name in rooms or room not in zones or node is None
                or node["network"] != "power"
                or node["owner_type"] != "equipment"
                or node["owner_id"] != name):
            raise InstrumentError("No actual locally supplied instrument panel")
        rooms[name] = room
        panel_zones[name] = zones[room] if str(zones[room]).startswith("PZ-") else None
    if len(rooms) != 116:
        raise InstrumentError("Original instrument inventory is no longer 116 panels")
    return rooms, panel_zones


def _zone_metrics(cell):
    if cell is None:
        return {}
    mass = cell["mass"]
    oxy = cell["oxygen"]
    if mass <= 0:
        return {"pressure_kpa": 0, "oxygen_kpa": 0,
                "temperature_k": cell["temperature"],
                "co2_fraction": 0, "smoke_fraction": 0,
                "burn_kg_s": cell["burn"], "leak_kg_s": cell["leak"],
                "cell_damage": cell["damage"]}
    if cell["volume"] <= 0:
        raise InstrumentError("Existing pressure cell volume cannot be zero")
    pressure_kpa = (mass * 287.05 * cell["temperature"] /
                    cell["volume"] / 1000.0)
    oxygen_moles = oxy / 0.032
    others = max(0.0, mass - oxy) / 0.029
    oxygen_kpa = (pressure_kpa * oxygen_moles /
                  (oxygen_moles + others) if oxygen_moles + others else 0)
    return {
        "pressure_kpa": max(0., pressure_kpa),
        "oxygen_kpa": max(0., oxygen_kpa),
        "temperature_k": cell["temperature"],
        "co2_fraction": cell["co2"] / mass,
        "smoke_fraction": cell["smoke"] / mass,
        "burn_kg_s": cell["burn"],
        "leak_kg_s": cell["leak"],
        "cell_damage": cell["damage"],
    }


def observed_panel_evidence(
        ledger, *, cells, equipment, isolators, nodes_energised,
        electrical=None, water=None, cultivation=None, food=None,
        services=None, motion=None, fire_loops=None):
    """One corroborated sample of every *original* local powered panel.

    Equipment and panel identities come from installed model objects, not
    guesses. Fitted protected HAB fire detectors and central detection
    loops supply health evidence when they share this panel's physical site.
    """
    if not isinstance(nodes_energised, (set, frozenset)):
        raise InstrumentError("Require current measured powered nodes")
    source = {name: [] for name in ledger["panels"]}
    onsite = {}
    for item in equipment.values():
        onsite.setdefault(item.space_id, []).append(item)
    switchgear = {}
    for iso in isolators.values():
        switchgear.setdefault(iso.space_id, []).append(iso)
    breaker_faults = ((electrical or {}).get("faults") or {})
    missed = set(((services or {}).get("last") or {}).get("unserved") or ())
    result = {}
    for panel_id, row in sorted(ledger["panels"].items()):
        equip = equipment.get(panel_id)
        if equip is None or equip.space_id != row["room"]:
            raise InstrumentError("Original local panel has vanished or moved")
        if equip.condition in BROKEN:
            result[panel_id] = {"status": "damaged", "metrics": {}, "faults": []}
            continue
        if "NODE-" + panel_id not in nodes_energised:
            result[panel_id] = {"status": "dark", "metrics": {}, "faults": []}
            continue
        room = row["room"]
        metrics = _zone_metrics(cells.get(row["zone"])) if row["zone"] else {}
        faults = []
        for unit in onsite.get(room, ()):
            if unit.source_id == panel_id:
                continue
            if unit.condition in BROKEN:
                faults.append(("MACHINE_FAULT", unit.source_id))
            elif unit.condition == "degraded":
                faults.append(("MACHINE_DEGRADED", unit.source_id))
            if unit.source_id in missed:
                faults.append(("SERVICE_OUTAGE", unit.source_id))
        for iso in switchgear.get(room, ()):
            if breaker_faults.get(iso.source_id, {}).get("latched"):
                faults.append(("BREAKER_TRIP", iso.source_id))
        if room in {"WATER-FWD", "HAB-06-ECLSS-A", "HAB-08-ECLSS-B"} and water is not None:
            if water["potable_quarantined"]:
                faults.append(("WATER_QUARANTINE", "POTABLE-TANK-MAIN"))
            metrics["water_working_kg"] = water["working_kg"]
        if cultivation is not None:
            for number, grow_room in GROW_BAYS.items():
                if grow_room == room and cultivation["beds"][
                        f"GROW-{number}"]["surveyed"]:
                    metrics["nutrient_kg"] = cultivation["beds"][
                        f"GROW-{number}"]["nutrient_kg"]
        if food is not None and room in food["waste"]:
            metrics["spoiled_food_kg"] = food["waste"][room]
        if fire_loops is not None:
            for original_id in fire_loops:
                loop = equipment.get(original_id)
                if loop is not None and loop.space_id == room and loop.condition in BROKEN:
                    faults.append(("FIRE_LOOP_FAULT", original_id))
        # The original protected HAB fire detector is a separate real
        # machine and circuit. Report its loss at only one active local
        # panel per arc, not on all thirty adjacent panels.
        if room.startswith("HAB-"):
            arc = room[0:6]
            fire_name = arc + "-FIRE-DETECT"
            if panel_id == next((k for k in ledger["panels"]
                                if ledger["panels"][k]["room"].startswith(arc)), None):
                detector = equipment.get(fire_name)
                if detector and (detector.condition in BROKEN or
                                 "NODE-" + fire_name not in nodes_energised):
                    faults.append(("FIRE_LOOP_FAULT", fire_name))
        result[panel_id] = {
            "status": "online", "metrics": metrics,
            "faults": sorted(set(faults)),
        }
    return result


def local_relay_summary(ledger, *, room, powered_nodes, equipment):
    """Only original HAB fire loops + comm nodes relay to ENG-CONTROL.

    This is NOT full telemetry aggregation, and no current reading for an
    unpowered, failed or undispatched source is available here.
    """
    if room not in {"ENG-CONTROL", "CMD-PRIMARY", "CMD-EMERG"}:
        raise InstrumentError("Bridge alarm relay has no original console here")
    local = "LP-" + room
    if (local not in ledger["panels"] or
            "NODE-" + local not in powered_nodes or
            equipment[local].condition in BROKEN):
        raise InstrumentError("Original bridge alarm panel has lost real power")
    relayed = {}
    lost = []
    for arc in range(1, 9):
        prefix = f"HAB-{arc:02d}"
        detector = prefix + "-FIRE-DETECT"
        comms = prefix + "-COMMS-NODE"
        if (detector not in equipment or comms not in equipment
                or equipment[detector].condition in BROKEN
                or equipment[comms].condition in BROKEN
                or "NODE-" + detector not in powered_nodes
                or "NODE-" + comms not in powered_nodes):
            lost.append(prefix)
            continue
        zone = f"PZ-{prefix}"
        alerts = [
            entry for entry in ledger["alarms"].values()
            if (entry["active"] and entry["subject"] == zone
                and entry["code"] in {"FIRE", "SMOKE", "PRESSURE_LOW"})
        ]
        # Every alarm source must ALSO have a currently reporting
        # powered local sensor panel. Otherwise report COMM LOSS.
        alerts = [e for e in alerts if ledger["panels"][
            e["panel"]]["status"] == "online"]
        relayed[prefix] = sorted(set(e["code"] for e in alerts))
    return {
        "relay_scope": "eight_original_HAB_protected_detector_and_comms_pairs",
        "alerts_by_arc": relayed, "lost_protected_links": lost,
        "withheld": "unwired_foreign_equipment_and_dark_panel_telemetry",
    }
