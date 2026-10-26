"""Evidence gates for real G19 waste haul routes and finite shared repairs.

These functions look at installed Evennia world state, never construct new
rooms, ports, spares or safety ratings. Work scripts are coarse mechanical
operations over the original rated accesses, not free character teleports.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque

from world.full_ship_operations import _BROKEN
from world.ship_water_recycling import WaterError


def selected_waste_route(source_room, freight_lock, access_rows, zones):
    """Find a real continuous internal freight path; no vacuum/exterior hops.

    A survey is an operator action. This deterministic path discovery is
    only a proposal: the operator must positively commission the chosen
    route, and all live damage/air/rotary gates are checked again per tick.
    """
    if source_room == freight_lock or not isinstance(source_room, str):
        raise WaterError("Waste movement requires distinct installed compartments")
    graph = defaultdict(list)
    for door in access_rows:
        spec = door.reference
        a, b = spec.get("from"), spec.get("to")
        kind = str(spec.get("kind", "")).lower()
        if (not a or not b
                or not all(isinstance(zones.get(room), str) and
                           zones[room].startswith("PZ-")
                           for room in (a, b))
                or any(word in kind for word in (
                    "eva", "exterior", "external", "cargo_portal",
                    "indexed_freight_transfer", "indexed_rotary_transfer",
                    "airlock"))):
            continue
        for frm, to in ((a, b), (b, a)):
            graph[frm].append((to, door.source_id))
    seen = {source_room}
    work = deque([(source_room, ())])
    while work:
        room, route = work.popleft()
        if room == freight_lock:
            if not 0 < len(route) <= 64:
                break
            return list(route)
        if len(route) >= 64:
            continue
        for destination, link in sorted(graph[room]):
            if destination not in seen:
                seen.add(destination)
                work.append((destination, route + (link,)))
    raise WaterError("No verified internal, non-exterior waste freight route")


def live_waste_route(route, *, source_room, freight_lock, doors,
                     zones, pressure_rows, rotors):
    """Check every surveyed link and live compartment before moving cassettes.

    Closed intact rated freight/pressure doors cycle SEQUENTIALLY during the
    timed haul; they are not magically held open at the same time. A damaged
    or explicitly locked access cannot be cycled, nor can unverified air,
    a rotary store spinning across the route or a vacuum-side boundary.
    """
    if not route or len(route) > 64:
        return False
    room = source_room
    crossed_work_rotor = False
    for link in route:
        door = doors.get(link)
        if door is None or door.condition in _BROKEN:
            return False
        kind = str(door.reference.get("kind", "")).lower()
        if any(x in kind for x in (
                "eva", "exterior", "external", "cargo_portal", "airlock",
                "indexed_freight_transfer", "indexed_rotary_transfer")):
            return False
        a, b = door.reference.get("from"), door.reference.get("to")
        if room == a:
            destination = b
        elif room == b:
            destination = a
        else:
            return False
        if door.setting not in {"open", "closed", "closed_or_auto"}:
            return False
        if door.setting == "closed" and not any(x in kind for x in (
                "door", "tunnel", "freight", "service", "cargo", "pressure")):
            return False
        za, zb = zones.get(room), zones.get(destination)
        if not isinstance(za, str) or not isinstance(zb, str):
            return False
        if not za.startswith("PZ-") or not zb.startswith("PZ-"):
            return False
        if za not in pressure_rows or zb not in pressure_rows:
            return False
        # A mechanical freight cart is not automatically an oxygen-safe crew
        # route, but this design explicitly requires safe known pressure on
        # both sides rather than moving open toxic cargo into protected air.
        from world.continuous_ship_physics import _air_safe, R_SPECIFIC_AIR
        a_cell, b_cell = pressure_rows[za], pressure_rows[zb]
        if not _air_safe(a_cell) or not _air_safe(b_cell):
            return False
        pa = (a_cell.quantity * R_SPECIFIC_AIR * a_cell.details["temperature_k"]
              / a_cell.details["gas_volume_m3"])
        pb = (b_cell.quantity * R_SPECIFIC_AIR * b_cell.details["temperature_k"]
              / b_cell.details["gas_volume_m3"])
        if not math.isfinite(pa) or not math.isfinite(pb) or abs(pa - pb) > 2000:
            return False
        if room.startswith("WR-") or destination.startswith("WR-"):
            crossed_work_rotor = True
        room = destination
    if room != freight_lock:
        return False
    if crossed_work_rotor:
        wr = rotors.get("WR-01")
        if not wr or not (
                wr["hardlock"] and wr["brake"] and wr["target_rpm"] == 0
                and abs(wr["rpm"]) < 0.001
                and not wr["passenger_indexer"]):
            return False
    return True


def safe_repair_target(item, *, pressure_rows, zones, rotors, motion,
                       water, cargo, equipment, isolators,
                       workroom=None, surveyed_suit_work=False):
    """A machinery repair is allowed only when real conditions permit it."""
    from world.continuous_ship_physics import PLANTS, _air_safe

    if item.category not in {"equipment", "access", "isolator"}:
        return False
    room = item.space_id if workroom is None else workroom
    if item.category == "access":
        if room not in {item.reference.get("from"), item.reference.get("to")}:
            return False
    elif room != item.space_id:
        return False
    zone = zones.get(room)
    if zone in pressure_rows:
        if not _air_safe(pressure_rows[zone]):
            return False
    elif not (surveyed_suit_work and zone in {None, "VACUUM"}):
        # Unclassified generator service bays cannot be treated as breathable.
        # A separate positive operator survey and VERIFIED suited worker are
        # required before work; air is never invented by this exemption.
        return False
    if item.condition not in {"degraded", "faulted", "failed", "jammed", "severed"}:
        return False
    if item.details.get("physics_trip_reason"):
        # Thermal protection is a separate isolated, cooled LOCAL reset.
        # A spare replacement may not defeat this protection latch.
        return False
    if item.category == "isolator":
        kind = str(item.reference.get("kind", "")).lower()
        return item.setting == ("open" if kind.startswith("breaker") else "closed")
    if item.category == "access":
        return item.setting in {"closed", "closed_or_auto"}
    if item.source_id in PLANTS and (
            item.details.get("physics_online", False) or
            item.details.get("physics_commanded_on", False) or
            item.details.get("physics_startup_s", 0) > 0):
        return False
    if item.source_id in {"GEN-M", "GEN-A", "GEN-B"}:
        feeder = isolators.get("ISO-" + item.source_id)
        if not feeder or feeder.setting != "open":
            return False
    if item.source_id.startswith(("WATER-PROC-", "WASTE-PROC-")):
        if water is None:
            return False
        side = item.source_id[-1]
        family = "water_train" if item.source_id.startswith("WATER-") else "waste_train"
        if water[family][side] != "off":
            return False
    if item.source_id.startswith(("WASTE-RESIDUE-HOLD-", "IND-SCRAP-HOLD-",
                                 "HAZ-ISO-HOLD-")):
        if water is None:
            return False
        cat = ("sanitary" if item.source_id.startswith("WASTE-") else
               "industrial" if item.source_id.startswith("IND-") else "hazardous")
        side = item.source_id[-1]
        if (water["cassettes"][cat][side] > 1e-7 or
                item.source_id in water.get("waste_offload", {}).get("jobs", {})):
            return False
    if item.source_id.startswith("DR-"):
        drum = item.source_id[:5]
        rotor = rotors.get(drum)
        if not rotor or not (rotor["hardlock"] and rotor["brake"]
                             and rotor["target_rpm"] == 0
                             and abs(rotor["rpm"]) < 0.001
                             and not rotor["passenger_indexer"]
                             and not rotor["freight_collar"]):
            return False
        if any(key.startswith(drum) for key in cargo.get("port_jobs", {})):
            return False
    if item.source_id.startswith(("WR-", "HAB-BEARING", "HAB-DRIVE")):
        rotor = rotors.get("WR-01" if item.source_id.startswith("WR-") else "HAB")
        if not rotor or not (rotor["hardlock"] and rotor["brake"]
                             and rotor["target_rpm"] == 0
                             and abs(rotor["rpm"]) < 0.001):
            return False
    if item.source_id.startswith(("LCS-PROP", "LP-PROP", "FTL-")):
        if (motion.get("command") != "coast"
                or motion.get("attitude_command") != "hold"
                or (motion.get("ftl_leg") or {}).get("status") == "engaged"):
            return False
    return True
