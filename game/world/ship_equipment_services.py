"""G19 installed secondary powered-equipment service and run/restart contracts.

These circuits extend, rather than replace, the original 438-node main
distribution and the 72 individually protected primary machinery feeders.
Each selected controller/tool/cargo unit is wired to its REAL local panel.
The common operating load schedule bounds aggregate electricity; no
unsupported per-device kW ratings or free grid generation are assumed.
"""
from __future__ import annotations

import copy
import math

from world.ship_electrical_power import _live_edge, ElectricalError

SOURCE_MODEL = "g19-operating-equipment/1"
NETWORK = "g19_equipment_service"
BROKEN = frozenset({"faulted", "failed", "severed", "jammed", "destroyed"})

GROW_BAYS = {1: "HAB-02-GROW", 2: "HAB-06-GROW",
             3: "HAB-08-GROW"}
CARGO_DRUMS = tuple(f"DR-{i:02d}" for i in range(1, 7))
SHOP_TOOLS = ("SHOP-CNC-LATHE", "SHOP-CNC-MILL", "SHOP-MANUAL-LATHE",
              "SHOP-PRESS", "SHOP-GRINDER", "SHOP-BALANCER")
WELD_CELLS = ("WELD-CELL-A", "WELD-CELL-B")
# All 26 exact original v0.5 equipment IDs and co-located source panels.
SERVICE_LOADS = {
    **{
        f"GROW-{n}-{kind}": (room, "NODE-" + room + "-LP")
        for n, room in GROW_BAYS.items()
        for kind in ("CTRL", "NUTRIENT")
    },
    **{
        f"{drum}-{kind}": (drum + "-GALLERY", "NODE-" + drum + "-SVC-DB")
        for drum in CARGO_DRUMS for kind in ("CARGO-HX", "CARGO-GAS")
    },
    **{name: ("SHOP-MECH", "NODE-LP-SHOP-MECH") for name in SHOP_TOOLS},
    **{name: ("SHOP-WELD", "NODE-LP-SHOP-WELD") for name in WELD_CELLS},
}
MANUAL_RESTART = frozenset((*SHOP_TOOLS, *WELD_CELLS))
AUTO_SERVICE = frozenset(SERVICE_LOADS) - MANUAL_RESTART


def service_ids(name):
    if name not in SERVICE_LOADS:
        raise ElectricalError("Unknown installed independent equipment feed")
    return ("NODE-G19-SVC-" + name,
            "EDGE-G19-SVC-" + name,
            "ISO-G19-SVC-" + name)


def service_specs():
    rows = {}
    for name, (room, parent) in sorted(SERVICE_LOADS.items()):
        terminal, edge_id, breaker_id = service_ids(name)
        for category, identifier, reference, setting in (
            ("node", terminal, {
                "id": terminal, "network": NETWORK, "kind": "equipment_terminal",
                "owner_type": "equipment", "owner_id": name,
            }, "unverified"),
            ("edge", edge_id, {
                "id": edge_id, "network": NETWORK,
                "kind": "dedicated_equipment_feeder",
                "from_node": parent, "to_node": terminal,
                "isolator_ids": [breaker_id], "route_spaces": [room],
            }, "available"),
            ("isolator", breaker_id, {
                "id": breaker_id, "network": NETWORK, "kind": "breaker",
                "current_state": "closed", "manual_operation": True,
                "remote_operable": False,
            }, "closed"),
        ):
            key = category + ":" + identifier
            if key in rows:
                raise ElectricalError("Duplicate fitted operating-equipment circuit")
            rows[key] = {
                "key": key, "category": category, "source_id": identifier,
                "source_model": SOURCE_MODEL, "space_id": room,
                "condition": "serviceable", "setting": setting,
                "reference": reference, "details": {},
            }
    return rows


def install_service_circuits(world_state):
    """Author 26 equipment branches on real source and room IDs, idempotently."""
    for name, (room, panel) in SERVICE_LOADS.items():
        target = world_state.objects.get(pk="equipment:" + name)
        source = world_state.objects.get(pk="node:" + panel)
        owner = world_state.objects.get(
            pk="equipment:" + source.reference.get("owner_id", ""))
        if (target.space_id != room or source.reference.get("network") != "power"
                or source.reference.get("owner_type") != "equipment"
                or owner.space_id != room):
            raise ElectricalError("Equipment feeder lacks an authentic local panel")
    rows = service_specs()
    created_count = 0
    for key, record in sorted(rows.items()):
        item, created = world_state.objects.get_or_create(
            key=key, defaults=record)
        if not created and (
                item.category != record["category"]
                or item.source_model != SOURCE_MODEL
                or item.space_id != record["space_id"]
                or item.reference != record["reference"]):
            raise ElectricalError("Equipment retrofit identity or provenance changed")
        created_count += int(created)
    return {"created": created_count, "total": len(rows),
            "separately_isolated_units": len(SERVICE_LOADS)}


def enrol_service_plant_controls(world_state):
    """Nonresetting equipment control migration for already-armed older ships.

    An existing plant command, restart delay, trip, damage and service history
    are never overwritten. Only previously absent controls are seeded from
    the selected original automatic-service/manual-workshop roles.
    """
    changed = []
    for name in sorted(SERVICE_LOADS):
        unit = world_state.objects.select_for_update().get(
            pk="equipment:" + name)
        old = dict(unit.details)
        details = dict(old)
        if "physics_commanded_on" not in details:
            details["physics_commanded_on"] = (
                name in AUTO_SERVICE and unit.condition not in BROKEN)
        if "physics_online" not in details:
            details["physics_online"] = (
                name in AUTO_SERVICE and unit.condition not in BROKEN
                and details["physics_commanded_on"] is True)
        if "physics_startup_s" not in details:
            details["physics_startup_s"] = 0.0
        if details != old:
            unit.details = details
            unit.revision += 1
            changed.append(unit)
    if changed:
        world_state.objects.bulk_update(
            changed, ["details", "revision"], batch_size=26)
    return len(changed)


def service_power(name, *, nodes, equipment, edges, switches):
    """A remote switchboard cannot override one local failed appliance feed."""
    room, panel = SERVICE_LOADS[name]
    terminal, edge_id, breaker_id = service_ids(name)
    machine = equipment.get(name)
    cable = edges.get(edge_id)
    if (machine is None or machine.space_id != room
            or machine.condition in BROKEN or cable is None
            or cable.reference.get("network") != NETWORK
            or cable.reference.get("from_node") != panel
            or cable.reference.get("to_node") != terminal
            or cable.reference.get("isolator_ids") != [breaker_id]):
        return False
    return bool(panel in nodes and _live_edge(cable, switches))


def initial_service_operations():
    return {
        "version": 1,
        "units": {name: {"runtime_s": 0.0, "outage_s": 0.0,
                          "operating": False, "restart_latched": False}
                  for name in sorted(SERVICE_LOADS)},
        "last": {"operating": [], "unserved": [], "restart_required": []},
    }


def validate_service_operations(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"version", "units", "last"}
            or ledger["version"] != 1
            or not isinstance(ledger["units"], dict)
            or set(ledger["units"]) != set(SERVICE_LOADS)
            or not isinstance(ledger["last"], dict)
            or set(ledger["last"]) != {"operating", "unserved",
                                      "restart_required"}):
        raise ElectricalError("Invalid operating-equipment state")
    for name, unit in ledger["units"].items():
        if not isinstance(unit, dict) or set(unit) != {
                "runtime_s", "outage_s", "operating", "restart_latched"}:
            raise ElectricalError("Missing fitted equipment service history")
        for key in ("runtime_s", "outage_s"):
            value = unit[key]
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or value < 0):
                raise ElectricalError("Invalid service duration")
        if (type(unit["operating"]) is not bool
                or type(unit["restart_latched"]) is not bool
                or (unit["restart_latched"] and name not in MANUAL_RESTART)
                or (unit["operating"] and unit["restart_latched"])):
            raise ElectricalError("Impossible local machinery restart latch")
    for key, entries in ledger["last"].items():
        if (not isinstance(entries, list) or entries != sorted(set(entries))
                or not set(entries) <= set(SERVICE_LOADS)):
            raise ElectricalError("Malformed local equipment service telemetry")
        if key == "restart_required" and not set(entries) <= MANUAL_RESTART:
            raise ElectricalError("Automatic-service circuit cannot latch restart")
    return True


def rearm_service_machine(ledger, name):
    """Qualified engineer commands a fresh supervised machine-tool startup."""
    validate_service_operations(ledger)
    if name not in MANUAL_RESTART:
        raise ElectricalError("Automatic-service equipment needs no manual rearm")
    updated = copy.deepcopy(ledger)
    updated["units"][name]["restart_latched"] = False
    # Do not instantly run the machine. The real plant controller still
    # requires its own start delay before the next physical operating tick.
    updated["units"][name]["operating"] = False
    updated["last"] = {"operating": [], "unserved": [],
                       "restart_required": []}
    validate_service_operations(updated)
    return updated


def step_service_operations(ledger, seconds, *, nodes, equipment,
                            edges, switches, supply_assured):
    validate_service_operations(ledger)
    if (type(seconds) not in (int, float) or not math.isfinite(seconds)
            or seconds < 0 or seconds > 10
            or type(supply_assured) is not bool):
        raise ElectricalError("Unbounded equipment-operation integration")
    result = copy.deepcopy(ledger)
    active, missed, latched = [], [], []
    for name, unit in sorted(result["units"].items()):
        machine = equipment.get(name)
        if machine is None or not isinstance(machine.details, dict):
            raise ElectricalError("Installed operating machine disappeared")
        commanded = machine.details.get("physics_commanded_on") is True
        running = machine.details.get("physics_online") is True
        energized = bool(supply_assured and service_power(
            name, nodes=nodes, equipment=equipment,
            edges=edges, switches=switches))
        if (name in MANUAL_RESTART and unit["operating"]
                and commanded and not energized):
            unit["restart_latched"] = True
        if not commanded:
            # An explicit OFF order ends running status; a subsequently
            # attended ON order still goes through the real startup delay.
            unit["operating"] = False
            continue
        operational = running and energized and not unit["restart_latched"]
        unit["operating"] = operational
        if operational:
            unit["runtime_s"] += seconds
            active.append(name)
        else:
            unit["outage_s"] += seconds
            missed.append(name)
            if unit["restart_latched"]:
                latched.append(name)
    result["last"] = {
        "operating": active,
        "unserved": missed,
        "restart_required": latched,
    }
    validate_service_operations(result)
    return result
