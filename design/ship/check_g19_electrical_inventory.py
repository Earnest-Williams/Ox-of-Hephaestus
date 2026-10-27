"""Audit G19 priority machinery against the exact original v0.5 installation.

Pure Python: no Evennia, database, world reset, inferred cables, or voyage.
The intentionally scoped 16 live machinery classes are not a claim that
every piece of passive or future-service equipment needs its own power node.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "game"))

from world.ship_auxiliary_electrical import (
    MOTORS, LOCAL_LOADS, PROTECTED_FIRE_MOTORS,
    _specs, auxiliary_ids, protected_fire_ids, charger_ids,
)

AUTHORITATIVE_CANDIDATE = ROOT / "design" / "ship" / "ox_full_ship_v0.5_candidate.json"
ACTIVE_FAMILIES = frozenset({
    "fire_pump", "thermal_plant", "bearing_lube_skid",
    "environmental_train", "water_processor", "waste_processor",
    "main_hab_drive", "indexer_drive", "cargo_handler",
    "indexed_drum_personnel_carrier", "rotor_drive", "linear_drive",
    "oxygen_generation_skid", "carbon_dioxide_recovery_skid",
    "dehumidifier", "air_handler",
})
MAIN_COUNTS = (438, 450, 466)


def audit():
    candidate = json.loads(AUTHORITATIVE_CANDIDATE.read_text(encoding="utf-8"))
    if (candidate.get("schema_version") != "ox.ship-world/0.1"
            or candidate.get("model_version") != "0.5-candidate"):
        raise AssertionError("G19 power audit has no verified v0.5 source")
    equipment = {x["id"]: x for x in candidate["equipment"]}
    nodes = {x["id"]: x for x in candidate["service_nodes"]}
    rooms = {x["id"] for x in candidate["spaces"]}
    original = {
        section: {x["id"] for x in candidate[field] if x["network"] == "power"}
        for section, field in (
            ("node", "service_nodes"), ("edge", "service_edges"),
            ("isolator", "isolation_points"))
    }
    if tuple(map(lambda key: len(original[key]), ("node", "edge", "isolator"))) != MAIN_COUNTS:
        raise AssertionError("Original source-to-load power graph has changed")
    machinery = {name for name, e in equipment.items() if e["kind"] in ACTIVE_FAMILIES}
    if machinery != set(MOTORS) or len(machinery) != 71:
        missing = sorted(machinery - set(MOTORS))
        invented = sorted(set(MOTORS) - machinery)
        raise AssertionError(
            "Priority machinery feeder coverage drift: "
            + json.dumps({"without_feeder": missing, "unknown_motor": invented}))
    extension = _specs()
    if len(extension) != 3 * len(MOTORS) + 6 * len(LOCAL_LOADS) + 2 * len(PROTECTED_FIRE_MOTORS):
        raise AssertionError("Supplementary wiring has duplicate or missing identities")
    for key, row in extension.items():
        cat, identifier = key.split(":", 1)
        if identifier in original.get(cat, set()):
            raise AssertionError("Refit circuit overwrites original power topology: " + identifier)
        if row["reference"]["id"] != identifier or row["source_model"] != "g19-electrical-aux/1":
            raise AssertionError("Refit conductor lost reference provenance")
        if row["space_id"] not in rooms:
            raise AssertionError("Supplementary circuit occupies nonexistent room: " + identifier)
    for name, (room, panel) in MOTORS.items():
        owner = nodes.get(panel, {}).get("owner_id")
        if (equipment[name]["space_id"] != room
                or nodes.get(panel, {}).get("network") != "power"
                or equipment.get(owner, {}).get("space_id") != room):
            raise AssertionError("Motor feeder has no real co-located panel: " + name)
        node, edge, breaker = auxiliary_ids(name, motor=True)
        if extension["edge:" + edge]["reference"]["from_node"] != panel:
            raise AssertionError("Motor branch is not fed from its actual panel: " + name)
        if ("node:" + node not in extension or "isolator:" + breaker not in extension):
            raise AssertionError("Motor branch lacks independent terminal/contact: " + name)
    for name, (room, consumer, panel, max_kwh, draw_kw) in LOCAL_LOADS.items():
        owner = nodes.get(panel, {}).get("owner_id")
        if (name not in equipment or equipment[name]["kind"] != "battery"
                or equipment[name]["space_id"] != room
                or equipment.get(consumer, {}).get("space_id") != room
                or equipment.get(owner, {}).get("space_id") != room):
            raise AssertionError("Emergency battery is not paired to a real local appliance")
        rated = equipment[name].get("attributes", {}).get("MWh")
        if rated is not None and abs(rated * 1000.0 - max_kwh) > 1e-7:
            raise AssertionError("Local battery capacity exceeds fitted nameplate")
        _, output_edge, output_breaker = auxiliary_ids(name)
        charge_edge, charge_breaker = charger_ids(name)
        if (extension["edge:" + output_edge]["reference"]["network"] != "g19_local_dc"
                or extension["edge:" + charge_edge]["reference"]["network"] != "g19_local_charger"
                or "isolator:" + output_breaker not in extension
                or "isolator:" + charge_breaker not in extension):
            raise AssertionError("Battery's independent output and charging cables are missing")
    for name in PROTECTED_FIRE_MOTORS:
        edge, breaker = protected_fire_ids(name)
        ref = extension["edge:" + edge]["reference"]
        if (ref["from_node"] != "PWR-PROT"
                or ref["to_node"] != auxiliary_ids(name, motor=True)[0]
                or not set(ref["route_spaces"]) <= rooms
                or "isolator:" + breaker not in extension):
            raise AssertionError("Fire-pump protected alternate has no physical route")
    independent_original_loads = {
        n["owner_id"] for n in candidate["service_nodes"]
        if n["network"] == "power" and n["owner_type"] == "equipment"
    }
    outstanding = Counter(
        x["kind"] for x in candidate["equipment"]
        if x["id"] not in independent_original_loads
        and x["id"] not in MOTORS and x["id"] not in LOCAL_LOADS
    )
    return {
        "status": "PASS_PRIO_OPERATING_MACHINERY_NOT_ALL_EQUIPMENT",
        "model": candidate["model_version"],
        "installed_equipment_total": len(equipment),
        "original_power_graph": dict(zip(("nodes", "edges", "isolators"), MAIN_COUNTS)),
        "priority_equipment_with_separate_motor_feeders": len(MOTORS),
        "local_battery_backup_appliances": len(LOCAL_LOADS),
        "protected_fire_pump_alternates": len(PROTECTED_FIRE_MOTORS),
        "supplementary_world_rows": len(extension),
        "remaining_without_individual_power_endpoint_by_kind": dict(
            sorted(outstanding.items())),
        "interpretation": (
            "Uncovered includes passive plumbing, structures, portable equipment "
            "and separately planned service families; not proof each requires "
            "electrical feeders."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True, indent=2))
