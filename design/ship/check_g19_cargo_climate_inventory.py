"""Audit G19 six-drum cargo cooling against original v0.5 utility geometry."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "game"))

from world.ship_cargo_manifest import DRUMS
from world.ship_cargo_environment import COOLER_LIMIT_KW
from world.ship_equipment_services import SERVICE_LOADS

FILE = ROOT / "design" / "ship" / "ox_full_ship_v0.5_candidate.json"


def audit():
    candidate = json.loads(FILE.read_text(encoding="utf8"))
    e = {x["id"]: x for x in candidate["equipment"]}
    rooms = {x["id"]: x for x in candidate["spaces"]}
    nodes = {x["id"]: x for x in candidate["service_nodes"]}
    edges = {x["id"]: x for x in candidate["service_edges"]}
    contacts = {x["id"]: x for x in candidate["isolation_points"]}
    if len(DRUMS) != 6:
        raise AssertionError("Original cargo drum complement changed")
    for drum in DRUMS:
        gallery = drum + "-GALLERY"
        zone = "PZ-" + drum + "-SVC"
        actual = rooms.get(gallery)
        if not actual or actual.get("pressure_zone") != zone:
            raise AssertionError("No measured service-gallery pressure cell: " + drum)
        for kind, equipment_kind in (
                ("CARGO-HX", "cargo_thermal_skid"),
                ("CARGO-GAS", "cargo_atmosphere_pack")):
            name = drum + "-" + kind
            if (name not in e or e[name]["kind"] != equipment_kind
                    or e[name]["space_id"] != gallery
                    or SERVICE_LOADS[name] != (
                        gallery, "NODE-" + drum + "-SVC-DB")):
                raise AssertionError("False powered cargo environmental pair: " + drum)
        interface = drum + "-LT-IF"
        if interface not in e or e[interface]["space_id"] != gallery:
            raise AssertionError("Uninstalled cargo LT rotary exchanger: " + drum)
        terminal = nodes.get("NODE-" + interface)
        cooling = edges.get("EDGE-" + interface)
        valve = contacts.get("ISO-" + interface)
        if (terminal is None or terminal.get("network") != "lt_cooling"
                or terminal.get("owner_id") != interface
                or cooling is None
                or cooling.get("network") != "lt_cooling"
                or cooling.get("from_node") != "NODE-LT-PLANT"
                or cooling.get("to_node") != terminal["id"]
                or cooling.get("isolator_ids") != ["ISO-" + interface]
                or valve is None or valve.get("kind") != "valve"
                or valve.get("network") != "lt_cooling"):
            raise AssertionError("Cargo cooling has no valved physical LT branch: " + drum)
    return {
        "result": "G19_ORIGINAL_CARGO_COOLING_TOPOLOGY_PASS",
        "original_cargo_drums": len(DRUMS),
        "conditioned_cargo_machine_pairs": len(DRUMS),
        "individually_fused_cargo_appliances": 2 * len(DRUMS),
        "actual_rotary_lt_interfaces": len(DRUMS),
        "each_cooling_skid_max_kw_equivalent": COOLER_LIMIT_KW,
        "total_cargo_skid_limit_kw": len(DRUMS) * COOLER_LIMIT_KW,
        "cargo_claim": "surveyed packaged freight microclimate, not breathable bulk hold",
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
