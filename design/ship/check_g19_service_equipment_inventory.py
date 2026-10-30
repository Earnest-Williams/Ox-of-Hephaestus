"""Audit 26 G19 powered crop, cargo-environment and workshop endpoints.

Reads only the immutable v0.5 authored inventory. Never invents parent panel
IDs, rooms or operating equipment that the candidate ship lacks.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "game"))

from world.ship_equipment_services import (
    SERVICE_LOADS, MANUAL_RESTART, service_ids, service_specs,
    SOURCE_MODEL,
)

CANDIDATE = ROOT / "design" / "ship" / "ox_full_ship_v0.5_candidate.json"
FAMILIES = {
    "cultivation_controller", "crop_process_skid",
    "cargo_thermal_skid", "cargo_atmosphere_pack",
    "machine_tool", "fabrication_cell",
}


def audit():
    reference = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    if (reference.get("schema_version") != "ox.ship-world/0.1"
            or reference.get("model_version") != "0.5-candidate"):
        raise AssertionError("Operating equipment has no authored ship reference")
    equipment = {row["id"]: row for row in reference["equipment"]}
    nodes = {row["id"]: row for row in reference["service_nodes"]}
    source = {item for item, row in equipment.items() if row["kind"] in FAMILIES}
    if len(equipment) != 808 or len(source) != 26 or source != set(SERVICE_LOADS):
        raise AssertionError("Installed powered equipment family inventory drift")
    if len(service_specs()) != 3 * len(source):
        raise AssertionError("Operating equipment missing independent branch hardware")
    original = {
        category: {x["id"] for x in reference[plural]
                   if x["network"] == "power"}
        for category, plural in (
            ("node", "service_nodes"), ("edge", "service_edges"),
            ("isolator", "isolation_points"))
    }
    if tuple(len(original[k]) for k in ("node", "edge", "isolator")) != (
            438, 450, 466):
        raise AssertionError("Original electrical sources were changed")
    specs = service_specs()
    for name, (room, parent) in SERVICE_LOADS.items():
        target = equipment[name]
        upstream = nodes.get(parent)
        if (target["space_id"] != room or upstream is None
                or upstream.get("network") != "power"
                or upstream.get("owner_type") != "equipment"
                or equipment[upstream["owner_id"]]["space_id"] != room):
            raise AssertionError("No actual co-located power source for " + name)
        node, edge, breaker = service_ids(name)
        if (specs["node:" + node]["reference"]["owner_id"] != name
                or specs["edge:" + edge]["reference"]["from_node"] != parent
                or specs["edge:" + edge]["reference"]["to_node"] != node
                or specs["edge:" + edge]["reference"]["isolator_ids"] != [breaker]
                or specs["isolator:" + breaker]["reference"]["kind"] != "breaker"):
            raise AssertionError("Unverified dedicated feeder geometry: " + name)
    for key, row in specs.items():
        category, identifier = key.split(":", 1)
        if (identifier in original[category]
                or row["source_model"] != SOURCE_MODEL
                or row["reference"]["network"] != "g19_equipment_service"):
            raise AssertionError("Second-stage retrofit overwrites original power")
    return {
        "status": "PASS_ORIGINAL_POWERED_SERVICE_FAMILIES",
        "original_equipment": len(equipment),
        "new_individual_feeders": len(SERVICE_LOADS),
        "new_persistent_circuit_objects": len(specs),
        "grow_controllers_and_nutrient_skids": 6,
        "cargo_heat_and_atmosphere_packs": 12,
        "shop_and_fabrication_machines": 8,
        "shop_units_require_attended_restart": len(MANUAL_RESTART),
        "original_power_graph": {
            name: len(original[name]) for name in ("node", "edge", "isolator")},
        "by_equipment_kind": dict(sorted(Counter(
            equipment[name]["kind"] for name in SERVICE_LOADS).items())),
        "remaining_scope": ("Equipment power and operating states are fitted; "
                            "per-machine process yield and calibration remain separately "
                            "bounded by existing aggregate schedules."),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True, indent=2))
