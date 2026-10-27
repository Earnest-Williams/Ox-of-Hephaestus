"""G19 fitted auxiliary motor feeders and local emergency DC circuits.

These are explicit extensions of the installed 0.5 vessel, not extra sources
in its 438-node main power graph. Source/load/isolator objects have their own
durable world identities. No local battery can backfeed an upstream bus.
"""
from __future__ import annotations

import copy
import math

from world.ship_electrical_power import _live_edge, ElectricalError, MW_SECONDS_PER_KWH

BROKEN = frozenset({"faulted", "failed", "severed", "jammed", "destroyed"})
SOURCE_MODEL = "g19-electrical-aux/1"

MOTORS = {
    # Independently fused fire-main and thermal plant motors.
    "LT-PLANT": ("ROTARY-UTIL-A", "NODE-LP-ROTARY-UTIL-A"),
    "FIRE-PUMP-FWD": ("WATER-FWD", "NODE-LP-WATER-FWD"),
    "FIRE-PUMP-AFT": ("ENV-AFT", "NODE-LP-ENV-AFT"),
    # Both independently maintainable bearing-lubrication skids at each
    # drum station. The existing local room panel supplies the new fuse.
    **{
        f"BE-{n:02d}-LUBE-{side}":
            (f"BE-{n:02d}-SVC", f"NODE-LP-BE-{n:02d}-SVC")
        for n in range(1, 13) for side in "NS"
    },
    # Each fitted ECLSS/process module has its own local disconnect. The
    # original HAB-06/08 ECLSS panels remain the upstream truth.
    **{
        f"{family}-{side}":
            (f"HAB-{'06-ECLSS-A' if side == 'A' else '08-ECLSS-B'}",
             f"NODE-HAB-{'06-ECLSS-A' if side == 'A' else '08-ECLSS-B'}-LP")
        for family in ("ECLSS", "WATER-PROC", "WASTE-PROC") for side in "AB"
    },
    # HAB rotation and phase-matched passenger indexers are independent
    # motors, and must not inherit the room panel's healthy indication.
    "HAB-DRIVE-FORE": ("HUB-FIXED-A", "NODE-LP-HUB-FIXED-A"),
    "HAB-DRIVE-AFT": ("HUB-FIXED-B", "NODE-LP-HUB-FIXED-B"),
    "IX-A-DRIVE": ("HUB-FIXED-A", "NODE-LP-HUB-FIXED-A"),
    "IX-B-DRIVE": ("HUB-FIXED-B", "NODE-LP-HUB-FIXED-B"),
    # The drum service-gallery DB and the separate service-lock panel
    # feed different machines. One trip cannot be substituted for another.
    **{
        f"DR-{n:02d}-RADIAL-FREIGHT-HANDLER":
            (f"DR-{n:02d}-GALLERY", f"NODE-DR-{n:02d}-SVC-DB")
        for n in range(1, 7)
    },
    **{
        f"DR-{n:02d}-PERSONNEL-INDEXER":
            (f"DR-{n:02d}-SERVICE-LOCK", f"NODE-LP-DR-{n:02d}-SERVICE-LOCK")
        for n in range(1, 7)
    },
}

# Explicitly fitted, short local battery-to-appliance harnesses. These are
# intentionally independent of the original vessel-wide power graph.
# BE units back up their *control/rescue stations*, not the drum motors;
# IX batteries protect local recovery collars, not phase-matching drives;
# refuge batteries support their actual emergency-air equipment.
LOCAL_LOADS = {
    **{
        f"BE-{n:02d}-BAT": (
            f"BE-{n:02d}-SVC", f"LCS-BE-{n:02d}",
            f"NODE-LP-BE-{n:02d}-SVC", 80.0, 1.0)
        for n in range(1, 13)
    },
    **{
        f"IX-{side}-LOCAL-BAT": (
            f"HUB-FIXED-{side}", f"IX-{side}-FIXED-COLLAR",
            f"NODE-LP-HUB-FIXED-{side}", 80.0, 2.0)
        for side in "AB"
    },
    **{
        f"HAB-{n:02d}-REFUGE-BAT": (
            f"HAB-{n:02d}-REFUGE", f"HAB-{n:02d}-REFUGE-AIR",
            f"NODE-HAB-{n:02d}-REFUGE-LP", 750.0, 10.0)
        for n in (4, 8)
    },
}


def auxiliary_ids(name, *, motor=False):
    prefix = "G19-MOTOR" if motor else "G19-LOCAL"
    return (f"NODE-{prefix}-" + name,
            f"EDGE-{prefix}-" + name,
            f"ISO-{prefix}-" + name)


def charger_ids(name):
    return ("EDGE-G19-CHARGE-" + name, "ISO-G19-CHARGE-" + name)


def _specs():
    """Construct the exact authored extension identities once, deterministically."""
    rows = {}
    def add(category, identifier, room, reference, setting="unverified"):
        rows[category + ":" + identifier] = {
            "key": category + ":" + identifier,
            "category": category, "source_id": identifier,
            "source_model": SOURCE_MODEL, "space_id": room,
            "condition": "serviceable", "setting": setting,
            "reference": reference, "details": {},
        }
    for name, (room, panel) in MOTORS.items():
        terminal, edge, switch = auxiliary_ids(name, motor=True)
        add("node", terminal, room, {
            "id": terminal, "network": "g19_motor", "kind": "motor_terminal",
            "owner_type": "equipment", "owner_id": name,
        })
        add("edge", edge, room, {
            "id": edge, "network": "g19_motor", "kind": "dedicated_motor_feeder",
            "from_node": panel, "to_node": terminal,
            "isolator_ids": [switch], "route_spaces": [room],
        }, "available")
        add("isolator", switch, room, {
            "id": switch, "network": "g19_motor", "kind": "breaker",
            "manual_operation": True, "remote_operable": False,
            "current_state": "closed",
        }, "closed")
    for name, (room, consumer, panel, cap, draw) in LOCAL_LOADS.items():
        terminal, edge, switch = auxiliary_ids(name)
        source_node = "NODE-G19-BAT-" + name
        add("node", source_node, room, {
            "id": source_node, "network": "g19_local_dc",
            "kind": "battery_terminal", "owner_type": "equipment",
            "owner_id": name,
        })
        add("node", terminal, room, {
            "id": terminal, "network": "g19_local_dc", "kind": "local_load",
            "owner_type": "equipment", "owner_id": consumer,
        })
        add("edge", edge, room, {
            "id": edge, "network": "g19_local_dc",
            "kind": "short_local_emergency_harness",
            "from_node": source_node, "to_node": terminal,
            "isolator_ids": [switch], "route_spaces": [room],
            "parent_panel": panel,
        }, "available")
        add("isolator", switch, room, {
            "id": switch, "network": "g19_local_dc", "kind": "breaker",
            "manual_operation": True, "remote_operable": False,
            "current_state": "closed",
        }, "closed")
        # Local AC input is a different physical cable and isolator from
        # the one-way battery-to-appliance emergency conductor.
        charge_edge, charge_iso = charger_ids(name)
        add("edge", charge_edge, room, {
            "id": charge_edge, "network": "g19_local_charger",
            "kind": "bounded_local_battery_charger",
            "from_node": panel, "to_node": source_node,
            "isolator_ids": [charge_iso], "route_spaces": [room],
        }, "available")
        add("isolator", charge_iso, room, {
            "id": charge_iso, "network": "g19_local_charger",
            "kind": "breaker", "manual_operation": True,
            "remote_operable": False, "current_state": "closed",
        }, "closed")
    return rows


def install_auxiliary_circuits(world_state):
    """Install inspected in-room wiring, once; never reset existing contacts.

    world_state must be the real CanonicalShipState model. Caller owns the
    enclosing transaction and serialized ship-clock lock.
    """
    intended = _specs()
    def panel_in_room(node, room):
        owner_id = node.reference.get("owner_id")
        if (node.reference.get("network") != "power"
                or node.reference.get("owner_type") != "equipment"
                or not isinstance(owner_id, str)):
            return False
        owner = world_state.objects.filter(pk="equipment:" + owner_id).first()
        return bool(owner and owner.space_id == room)
    for name, (room, panel) in MOTORS.items():
        target = world_state.objects.get(pk="equipment:" + name)
        parent = world_state.objects.get(pk="node:" + panel)
        if (target.space_id != room or not panel_in_room(parent, room)):
            raise ElectricalError("Motor retrofit does not match real installed plant or panel")
    for name, (room, consumer, panel, limit, draw) in LOCAL_LOADS.items():
        battery = world_state.objects.get(pk="equipment:" + name)
        load = world_state.objects.get(pk="equipment:" + consumer)
        parent = world_state.objects.get(pk="node:" + panel)
        if (battery.space_id != room or load.space_id != room
                or not panel_in_room(parent, room)):
            raise ElectricalError("Emergency DC harness crosses an unverified physical site")
        nominal = battery.reference.get("attributes", {}).get("MWh")
        if nominal is not None and (
                isinstance(nominal, bool) or not isinstance(nominal, (int, float))
                or not math.isclose(nominal * 1000, limit, abs_tol=1e-8)):
            raise ElectricalError("Local battery nameplate differs from fitted contract")
    count = 0
    for key, values in sorted(intended.items()):
        obj, created = world_state.objects.get_or_create(
            key=key, defaults=values)
        if not created:
            if (obj.source_model != SOURCE_MODEL or obj.category != values["category"]
                    or obj.space_id != values["space_id"]
                    or obj.reference != values["reference"]):
                raise ElectricalError("Auxiliary circuit identity or provenance changed")
        count += int(created)
    return {"created": count, "total": len(intended),
            "local_dc_circuits": len(LOCAL_LOADS), "motor_feeders": len(MOTORS)}


def initial_local_backup():
    return {"version": 2, "units": {}, "meter": {
        "delivered_kwh": 0.0, "charged_kwh": 0.0,
        "unserved_kwh": 0.0}, "last": {}}


def validate_local_backup(ledger):
    if not isinstance(ledger, dict) or set(ledger) != {
            "version", "units", "meter", "last"} or ledger["version"] != 2:
        raise ElectricalError("Unknown local emergency electrical ledger")
    if not isinstance(ledger["units"], dict) or not set(ledger["units"]) <= set(LOCAL_LOADS):
        raise ElectricalError("Unfitted local battery")
    if not isinstance(ledger["meter"], dict) or set(ledger["meter"]) != {
            "delivered_kwh", "charged_kwh", "unserved_kwh"
            } or not isinstance(ledger["last"], dict):
        raise ElectricalError("Corrupt local electrical meters")
    for x in ledger["meter"].values():
        if type(x) not in (int, float) or not math.isfinite(x) or x < 0:
            raise ElectricalError("Corrupt local electrical energy measurement")
    for name, bank in ledger["units"].items():
        if not isinstance(bank, dict) or set(bank) != {
                "capacity_kwh", "charge_kwh", "initial_kwh",
                "delivered_kwh", "charged_kwh", "mode"}:
            raise ElectricalError("Unknown local electrical store account")
        for value in [bank[k] for k in ("capacity_kwh", "charge_kwh",
                   "initial_kwh", "delivered_kwh", "charged_kwh")]:
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ElectricalError("Invalid local battery quantity")
        if (bank["capacity_kwh"] > LOCAL_LOADS[name][3] + 1e-8
                or bank["capacity_kwh"] <= 0
                or bank["initial_kwh"] > bank["capacity_kwh"]
                or bank["charge_kwh"] > bank["capacity_kwh"] + 1e-8
                or bank["mode"] not in {"standby", "reserve", "charge"}
                or not math.isclose(
                    bank["initial_kwh"] + bank["charged_kwh"]
                    - bank["delivered_kwh"],
                    bank["charge_kwh"], abs_tol=1e-7, rel_tol=1e-10)):
            raise ElectricalError("Local emergency battery energy created or lost")
    for field, unit_field in (("delivered_kwh", "delivered_kwh"),
                              ("charged_kwh", "charged_kwh")):
        if not math.isclose(sum(x[unit_field] for x in ledger["units"].values()),
                            ledger["meter"][field], abs_tol=1e-6, rel_tol=1e-10):
            raise ElectricalError("Local power aggregate meter does not reconcile")
    return True


def migrate_local_backup(existing):
    """Retain every v1 unit's actual charge and recorded discharges."""
    if existing.get("version") == 2:
        validate_local_backup(existing)
        return copy.deepcopy(existing)
    if not isinstance(existing, dict) or existing.get("version") != 1:
        raise ElectricalError("Unknown historical local emergency ledger")
    if (set(existing) != {"version", "units", "meter", "last"}
            or not isinstance(existing["units"], dict)
            or not set(existing["units"]) <= set(LOCAL_LOADS)
            or set(existing["meter"]) != {"delivered_kwh", "unserved_kwh"}):
        raise ElectricalError("Unverified historical local battery account")
    old = copy.deepcopy(existing)
    if not isinstance(old["last"], dict):
        raise ElectricalError("Invalid historical local battery readout")
    for name, bank in old["units"].items():
        if set(bank) != {"capacity_kwh", "initial_kwh", "charge_kwh",
                         "delivered_kwh", "mode"}:
            raise ElectricalError("Corrupt historical local battery")
        bank["charged_kwh"] = 0.0
    old["version"] = 2
    old["meter"]["charged_kwh"] = 0.0
    validate_local_backup(old)
    return old


def survey_local_backup(ledger, name, *, capacity_kwh, initial_kwh):
    validate_local_backup(ledger)
    if name not in LOCAL_LOADS or name in ledger["units"]:
        raise ElectricalError("No unmeasured installed local emergency battery")
    limit = LOCAL_LOADS[name][3]
    for quantity in (capacity_kwh, initial_kwh):
        if (type(quantity) not in (int, float) or not math.isfinite(quantity)
                or quantity < 0):
            raise ElectricalError("Nonphysical battery survey")
    if capacity_kwh <= 0 or capacity_kwh > limit or initial_kwh > capacity_kwh:
        raise ElectricalError("Local battery exceeds survey envelope")
    result = copy.deepcopy(ledger)
    result["units"][name] = {
        "capacity_kwh": float(capacity_kwh),
        "initial_kwh": float(initial_kwh),
        "charge_kwh": float(initial_kwh),
        "delivered_kwh": 0.0, "charged_kwh": 0.0, "mode": "standby",
    }
    validate_local_backup(result)
    return result


def set_local_mode(ledger, name, mode):
    validate_local_backup(ledger)
    if name not in ledger["units"] or mode not in {"standby", "reserve", "charge"}:
        raise ElectricalError("Unsurveyed or incorrectly selected emergency battery")
    result = copy.deepcopy(ledger)
    result["units"][name]["mode"] = mode
    validate_local_backup(result)
    return result


def motor_power(name, *, nodes, equipment, edges, switches):
    if name not in MOTORS:
        raise ElectricalError("No authored dedicated machinery feeder")
    room, panel = MOTORS[name]
    terminal, edge_id, switch = auxiliary_ids(name, motor=True)
    wire = edges.get(edge_id)
    component = equipment.get(name)
    return bool(panel in nodes and component is not None
                and component.space_id == room and component.condition not in BROKEN
                and wire is not None and wire.reference.get("network") == "g19_motor"
                and wire.reference.get("to_node") == terminal
                and wire.reference.get("from_node") == panel
                and _live_edge(wire, switches))


def step_local_backup(ledger, seconds, *, nodes, equipment, edges, switches,
                      producer_nodes=(), producing_mw=0.0, other_requested_mw=0.0):
    """Advance isolated DC reserves and separately fused grid recharging.

    Local batteries cannot backfeed the grid. Only a verified generator/shore
    path to the real room panel and spare real production can recharge one.
    The requested charging MW must be metered by the same ship physics tick.
    """
    validate_local_backup(ledger)
    for value in (seconds, producing_mw, other_requested_mw):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ElectricalError("Nonphysical local battery integration")
    if seconds > 10:
        raise ElectricalError("Local battery integration must be bounded")
    result = copy.deepcopy(ledger)
    active, blocked, recharging = {}, {}, {}
    headroom_mw = max(0.0, producing_mw - other_requested_mw)
    total_charge_mw = 0.0
    source_nodes = set(producer_nodes)
    for name, bank in sorted(result["units"].items()):
        room, consumer, parent, limit, draw_kw = LOCAL_LOADS[name]
        battery = equipment.get(name)
        battery_ok = bool(battery and battery.space_id == room
                          and battery.condition not in BROKEN)
        if bank["mode"] == "charge":
            edge_id, iso = charger_ids(name)
            wire = edges.get(edge_id)
            ready = (battery_ok and parent in source_nodes
                     and wire is not None
                     and wire.reference.get("network") == "g19_local_charger"
                     and wire.reference.get("from_node") == parent
                     and wire.reference.get("to_node") == "NODE-G19-BAT-" + name
                     and _live_edge(wire, switches))
            if not ready:
                blocked[name] = "charger_or_generator_path_unavailable"
                continue
            if seconds == 0 or headroom_mw <= 0:
                continue
            fill_kw = min(
                draw_kw, headroom_mw * 1000.0,
                (bank["capacity_kwh"] - bank["charge_kwh"]) * 3600.0 / seconds)
            if fill_kw <= 1e-9:
                continue
            energy = fill_kw * seconds / 3600.0
            bank["charge_kwh"] += energy
            bank["charged_kwh"] += energy
            result["meter"]["charged_kwh"] += energy
            headroom_mw -= fill_kw / 1000.0
            total_charge_mw += fill_kw / 1000.0
            recharging[name] = energy
            continue
        if bank["mode"] != "reserve":
            continue
        # The separately breaker-fed refuge air appliance is the normal
        # endpoint; an energised room panel is insufficient proof of power.
        normal_endpoint = ("NODE-PWR-" + consumer
                           if name.endswith("-REFUGE-BAT") else parent)
        if normal_endpoint in nodes:
            continue
        terminal, edge_id, iso = auxiliary_ids(name)
        wire = edges.get(edge_id)
        load = equipment.get(consumer)
        ready = (battery_ok and load is not None and load.space_id == room
                 and load.condition not in BROKEN
                 and wire is not None
                 and wire.reference.get("network") == "g19_local_dc"
                 and wire.reference.get("from_node") == "NODE-G19-BAT-" + name
                 and wire.reference.get("to_node") == terminal
                 and _live_edge(wire, switches))
        requested_kwh = draw_kw * seconds / 3600.0
        if not ready:
            blocked[name] = "local_circuit_or_load_failed"
            result["meter"]["unserved_kwh"] += requested_kwh
            continue
        provided = min(requested_kwh, bank["charge_kwh"])
        bank["charge_kwh"] -= provided
        bank["delivered_kwh"] += provided
        result["meter"]["delivered_kwh"] += provided
        result["meter"]["unserved_kwh"] += requested_kwh - provided
        if provided >= requested_kwh - 1e-10 and requested_kwh > 0:
            active[name] = consumer
        elif requested_kwh > 0:
            blocked[name] = "battery_exhausted"
    result["last"] = {
        "active_local_consumers": active,
        "unserved_local_consumers": blocked,
        "charged_local_units_kwh": recharging,
        "grid_charge_requested_mw": total_charge_mw,
        "available_stored_kwh": sum(
            x["charge_kwh"] for x in result["units"].values()),
    }
    validate_local_backup(result)
    return result
