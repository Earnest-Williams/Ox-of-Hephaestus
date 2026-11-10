"""Lead-mind power-island candidate: fault domains, finite reserves and world rows.

The 438/450/466 G19 electrical grid is unchanged. This is a *candidate*
extension, not installed plant: the physical A/B cable routes require a
survey and Evennia-owned commissioning before they can supply the lead mind.
Tests here prove the declared topology, never the unverified as-fitted ship.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

SCHEMA = "ox.lead-mind-power/1"
STATUS = "DESIGN_CANDIDATE_NOT_RUNTIME_AUTHORITY"
SOURCE_MODEL = SCHEMA
UPSTREAM = {"A": "PWR-MSB-A", "B": "PWR-MSB-B"}
FORBIDDEN = frozenset({"PWR-PROT", "BAT-COMMON-PROT"})
FAILED = frozenset({"faulted", "failed", "severed", "destroyed"})
MACHINE_COUNT = 9
MIN_SURVIVORS = 7


class MindPowerError(ValueError):
    """Unsafe topology, invented power or corrupt island reserve."""


def _check(value, message):
    if not value:
        raise MindPowerError(message)


def _positive(value, label):
    _check(type(value) in (int, float) and math.isfinite(value) and value > 0,
           "Nonphysical positive value: " + label)
    return float(value)


def default_design_path():
    return Path(__file__).resolve().parents[2] / "design" / "ship" / "lead_mind_power_islands.json"


def load_design(path=None):
    with (Path(path) if path else default_design_path()).open(encoding="utf-8") as stream:
        result = json.load(stream)
    validate_design(result)
    return result


def validate_design(design):
    """Refuse common-mode feeds, repeated apparatus and three-machine islands.

    This checks an authored graph, *not* whether a route is physically fitted.
    Existing G19 source power and real cable surveys must be checked later.
    """
    _check(isinstance(design, dict)
           and design.get("schema_version") == SCHEMA
           and design.get("status") == STATUS
           and design.get("source_nodes") == UPSTREAM,
           "Unsupported or falsely commissioned mind-power model")
    transfer = _positive(design.get("transfer_seconds"), "transfer_seconds")
    endurance = _positive(design.get("required_ride_through_seconds"), "ride-through")
    _check(transfer <= endurance, "Transfer exceeds declared ride-through")
    islands = design.get("islands")
    _check(isinstance(islands, list) and len(islands) >= 5,
           "Nine machines require five isolated power domains")
    seen, machines, regions = set(), set(), {}
    all_routes = set()

    def unique(value):
        _check(isinstance(value, str) and bool(value)
               and value not in seen and value not in FORBIDDEN,
               "Duplicated, empty or forbidden lead-mind component: " + str(value))
        seen.add(value)

    for island in islands:
        _check(isinstance(island, dict), "Invalid power island")
        for field in ("id", "distribution_node", "converter"):
            unique(island.get(field))
        region = island.get("region")
        _check(isinstance(region, str) and region, "Power island without a region")
        _check(isinstance(island.get("control_room"), str)
               and island["control_room"], "Power island without a service room")
        reserve = island.get("local_reserve")
        _check(isinstance(reserve, dict), "Island lacks independent reserve")
        unique(reserve.get("id"))
        capacity = _positive(reserve.get("capacity_kwh"), "reserve capacity")
        initial = _positive(reserve.get("initial_kwh"), "candidate initial reserve")
        rating = _positive(reserve.get("max_discharge_kw"), "reserve discharge rating")
        _check(initial <= capacity, "Initial reserve exceeds capacity")
        _check(isinstance(island.get("machines"), list)
               and 1 <= len(island["machines"]) <= 2,
               "A single island fault may lose no more than two machines")
        machine_load = 0.0
        for machine in island["machines"]:
            _check(isinstance(machine, dict), "Invalid compute machine")
            for field in ("id", "terminal_node", "feeder", "isolator",
                          "cooling_domain"):
                unique(machine.get(field))
            _check(isinstance(machine.get("room"), str) and machine["room"],
                   "Compute machine has no physical room")
            links = machine.get("backbone_links")
            _check(isinstance(links, list) and len(links) == 2
                   and links[0] != links[1], "Two independent backbone ports required")
            for link in links:
                unique(link)
            final_route = machine.get("proposed_final_route_spaces")
            _check(isinstance(final_route, list) and bool(final_route)
                   and all(isinstance(x, str) and x for x in final_route)
                   and final_route[0] == island["control_room"]
                   and final_route[-1] == machine["room"],
                   "Machine final lacks a proposed continuous room route")
            machine_load += _positive(machine.get("load_kw"), "machine load")
            machines.add(machine["id"])
            regions[machine["id"]] = region
        _check(rating >= machine_load, "Island reserve cannot carry all its machines")
        # These are components downstream of the two existing MSBs. Neither
        # input may traverse the protected distribution or the other input.
        inputs = island.get("inputs")
        _check(isinstance(inputs, list) and len(inputs) == 2
               and {x.get("source") for x in inputs} == {"A", "B"},
               "Power island must have diverse A/B source paths")
        a_path, b_path = None, None
        for feed in inputs:
            _check(type(feed.get("selected")) is bool,
                   "Source contact requires explicit selected state")
            for field in ("edge", "breaker"):
                unique(feed.get(field))
            cable_rooms = feed.get("proposed_cable_route_spaces")
            _check(isinstance(cable_rooms, list) and bool(cable_rooms)
                   and all(isinstance(x, str) and x for x in cable_rooms)
                   and cable_rooms[-1] == island["control_room"],
                   "Proposed A/B feeder lacks a service-room route")
            route = feed.get("route_domains")
            _check(isinstance(route, list) and len(route) >= 3
                   and all(isinstance(x, str) and x for x in route)
                   and len(set(route)) == len(route),
                   "Unspecified, repeated or empty physical feed domain")
            _check(route[0] == UPSTREAM[feed["source"]]
                   and not set(route) & FORBIDDEN,
                   "Source path secretly traverses protected distribution")
            if feed["source"] == "A":
                a_path = set(route)
            else:
                b_path = set(route)
            all_routes.update(route)
        _check(not a_path & b_path,
               "A/B contacts share a fault domain before the island bus")
        _check(sum(bool(x["selected"]) for x in inputs) == 1,
               "Uncontrolled paralleling or an unselected island")
        _check(any(x["source"] == "A" and x["selected"] for x in inputs),
               "Commissioning default must be source A")
    _check(len(machines) == MACHINE_COUNT, "Exactly nine distinct machines required")
    _check(set(regions) == {f"MIND-{n:02d}" for n in range(1, 10)},
           "Unexpected lead-mind machine identity")
    return True


def fault_components(design):
    """Every declared single component/fault domain, including upstream buses."""
    validate_design(design)
    elements = set(UPSTREAM.values()) | set(FORBIDDEN)
    for island in design["islands"]:
        elements.update((island["distribution_node"], island["converter"],
                         island["local_reserve"]["id"]))
        for feed in island["inputs"]:
            elements.update((feed["edge"], feed["breaker"]))
            elements.update(feed["route_domains"])
            elements.update(feed["proposed_cable_route_spaces"])
        for machine in island["machines"]:
            elements.update((machine["id"], machine["terminal_node"],
                             machine["feeder"], machine["isolator"],
                             machine["cooling_domain"]))
            elements.update(machine["backbone_links"])
            elements.update(machine["proposed_final_route_spaces"])
    return tuple(sorted(elements))


def live_machines(design, *, failed=(), energized_main_nodes=None,
                  surveyed_reserves=None, endurance_seconds=None):
    """Resolve proposed physical reachability under explicit failed domains.

    A/B input alternatives are evaluated after *permitted* transfer. Optional
    measured reserve credit covers only bounded loss of both inputs; a dead
    island bus or converter cannot be rescued by a fictitious bypass.
    This is not an Evennia actual-state view or a promise of generated power.
    """
    validate_design(design)
    bad = set(failed)
    live_sources = (set(UPSTREAM.values()) if energized_main_nodes is None
                    else set(energized_main_nodes))
    duration = (_positive(endurance_seconds, "endurance_seconds")
                if endurance_seconds is not None
                else float(design["required_ride_through_seconds"]))
    charged = surveyed_reserves or {}
    alive = set()
    for island in design["islands"]:
        if island["distribution_node"] in bad or island["converter"] in bad:
            continue
        grid_ok = any(
            UPSTREAM[feed["source"]] in live_sources
            and feed["edge"] not in bad and feed["breaker"] not in bad
            and not bad.intersection(feed["route_domains"])
            and not bad.intersection(feed["proposed_cable_route_spaces"])
            for feed in island["inputs"]
        )
        reserve = island["local_reserve"]
        draw_kw = sum(m["load_kw"] for m in island["machines"])
        available = charged.get(reserve["id"], 0.0)
        reserve_ok = (
            reserve["id"] not in bad
            and type(available) in (int, float) and math.isfinite(available)
            and available >= draw_kw * duration / 3600.0
            and reserve["max_discharge_kw"] >= draw_kw
        )
        if not grid_ok and not reserve_ok:
            continue
        for machine in island["machines"]:
            if not bad.intersection((
                    machine["id"], machine["terminal_node"],
                    machine["feeder"], machine["isolator"],
                    machine["cooling_domain"]))
                    and not bad.intersection(machine["proposed_final_route_spaces"])
                    and any(link not in bad for link in machine["backbone_links"]):
                alive.add(machine["id"])
    return frozenset(alive)


def single_fault_sweep(design, *, surveyed_reserves=None):
    """Prove declared one-fault partitioning (not as-installed acceptance)."""
    validate_design(design)
    failures = {}
    for component in fault_components(design):
        survivors = live_machines(design, failed={component},
                                  surveyed_reserves=surveyed_reserves)
        failures[component] = MACHINE_COUNT - len(survivors)
        _check(len(survivors) >= MIN_SURVIVORS,
               f"Common-mode fault {component} disables {failures[component]} machines")
    return failures


def initial_reserve_ledger(design):
    """Zero measured energy on installation: nameplate is not free charge."""
    validate_design(design)
    return {"version": 1,
            "units": {island["local_reserve"]["id"]: {
                "surveyed": False, "capacity_kwh": 0.0,
                "initial_kwh": 0.0, "charge_kwh": 0.0,
                "charged_kwh": 0.0, "discharged_kwh": 0.0}
                for island in design["islands"]},
            "meter": {"delivered_kwh": 0.0, "unserved_kwh": 0.0}}


def validate_reserve_ledger(design, ledger):
    validate_design(design)
    intended = {i["local_reserve"]["id"]: i["local_reserve"]
                for i in design["islands"]}
    _check(isinstance(ledger, dict) and set(ledger) == {"version", "units", "meter"}
           and ledger["version"] == 1
           and isinstance(ledger["units"], dict)
           and set(ledger["units"]) == set(intended), "Unknown mind reserve ledger")
    _check(isinstance(ledger["meter"], dict)
           and set(ledger["meter"]) == {"delivered_kwh", "unserved_kwh"},
           "Unrecognised reserve meter")
    for value in ledger["meter"].values():
        _check(type(value) in (int, float) and math.isfinite(value) and value >= 0,
               "Invalid reserve meter quantity")
    delivered = 0.0
    for name, bank in ledger["units"].items():
        _check(isinstance(bank, dict) and set(bank) == {
            "surveyed", "capacity_kwh", "initial_kwh", "charge_kwh",
            "charged_kwh", "discharged_kwh"}, "Corrupt reserve unit")
        _check(type(bank["surveyed"]) is bool, "Invalid survey flag")
        for key in ("capacity_kwh", "initial_kwh", "charge_kwh",
                    "charged_kwh", "discharged_kwh"):
            value = bank[key]
            _check(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                   "Nonphysical reserve energy")
        _check(bank["capacity_kwh"] <= intended[name]["capacity_kwh"]
               and bank["initial_kwh"] <= bank["capacity_kwh"]
               and bank["charge_kwh"] <= bank["capacity_kwh"]
               and math.isclose(bank["initial_kwh"] + bank["charged_kwh"]
                                - bank["discharged_kwh"], bank["charge_kwh"],
                                rel_tol=1e-10, abs_tol=1e-8),
               "Reserve energy created or lost")
        if not bank["surveyed"]:
            _check(all(bank[k] == 0 for k in ("capacity_kwh", "initial_kwh",
                    "charge_kwh", "charged_kwh", "discharged_kwh")),
                   "Unsurveyed reserve cannot contribute energy")
        delivered += bank["discharged_kwh"]
    _check(math.isclose(delivered, ledger["meter"]["delivered_kwh"],
                        abs_tol=1e-8, rel_tol=1e-10),
           "Aggregate reserve meter does not reconcile")
    return True


def survey_reserve(design, ledger, name, *, capacity_kwh, charge_kwh):
    validate_reserve_ledger(design, ledger)
    _check(name in ledger["units"] and not ledger["units"][name]["surveyed"],
           "Reserve not fitted or already surveyed")
    capacity = _positive(capacity_kwh, "surveyed capacity")
    charge = charge_kwh
    _check(type(charge) in (float, int) and math.isfinite(charge)
           and 0 <= charge <= capacity, "Invalid actual reserve state of charge")
    result = copy.deepcopy(ledger)
    result["units"][name].update(
        surveyed=True, capacity_kwh=capacity, initial_kwh=float(charge),
        charge_kwh=float(charge))
    validate_reserve_ledger(design, result)
    return result


def spend_reserve(design, ledger, island_id, *, seconds):
    """Account bounded blackout energy; cannot fabricate backup or recharge."""
    validate_reserve_ledger(design, ledger)
    time = _positive(seconds, "seconds")
    _check(time <= 60, "Reserve ticks must stay bounded to ship physics ticks")
    island = next((i for i in design["islands"] if i["id"] == island_id), None)
    _check(island is not None, "Unknown physical island")
    bank = ledger["units"][island["local_reserve"]["id"]]
    demand_kw = sum(machine["load_kw"] for machine in island["machines"])
    required_kwh = demand_kw * time / 3600.0
    max_kwh = island["local_reserve"]["max_discharge_kw"] * time / 3600.0
    delivered = min(required_kwh, max_kwh, bank["charge_kwh"]
                    if bank["surveyed"] else 0.0)
    result = copy.deepcopy(ledger)
    unit = result["units"][island["local_reserve"]["id"]]
    unit["charge_kwh"] -= delivered
    unit["discharged_kwh"] += delivered
    result["meter"]["delivered_kwh"] += delivered
    result["meter"]["unserved_kwh"] += required_kwh - delivered
    validate_reserve_ledger(design, result)
    return result, math.isclose(delivered, required_kwh, abs_tol=1e-10)


def proposed_world_rows(design):
    """Return distinct Evennia-shaped rows for a future *verified* fitter.

    Edges use the new mind_power network, deliberately separate from G19's
    legacy 'power' audit and with no reverse feeder from the local reserves.
    These rows are not installed or energised by calling this function.
    """
    validate_design(design)
    rows = {}

    def add(category, name, room, reference, setting="unverified"):
        key = category + ":" + name
        _check(key not in rows, "Duplicate persisted circuit identity")
        rows[key] = {
            "key": key, "category": category, "source_id": name,
            "source_model": SOURCE_MODEL, "space_id": room,
            "condition": "serviceable", "setting": setting,
            "reference": reference, "details": {},
        }

    for island in design["islands"]:
        room, bus, reserve = (island["control_room"],
                              island["distribution_node"], island["local_reserve"])
        add("equipment", island["converter"], room,
            {"id": island["converter"], "family": "mind_island_converter",
             "island": island["id"]})
        add("equipment", reserve["id"], room,
            {"id": reserve["id"], "family": "mind_local_reserve",
             "island": island["id"], "capacity_kwh": reserve["capacity_kwh"]})
        add("node", bus, room, {"id": bus, "network": "mind_power",
                               "kind": "isolated_island_bus",
                               "owner_type": "equipment",
                               "owner_id": island["converter"]})
        battery_node = "NODE-" + reserve["id"]
        add("node", battery_node, room,
            {"id": battery_node, "network": "mind_power",
             "kind": "local_reserve_terminal", "owner_type": "equipment",
             "owner_id": reserve["id"]})
        battery_edge, battery_iso = ("EDGE-" + reserve["id"],
                                     "ISO-" + reserve["id"])
        add("edge", battery_edge, room,
            {"id": battery_edge, "network": "mind_power",
             "kind": "one_way_island_reserve",
             "from_node": battery_node, "to_node": bus,
             "isolator_ids": [battery_iso]}, "available")
        add("isolator", battery_iso, room,
            {"id": battery_iso, "network": "mind_power",
             "kind": "breaker", "current_state": "closed",
             "manual_operation": True, "remote_operable": False}, "closed")
        for feed in island["inputs"]:
            add("edge", feed["edge"], room,
                {"id": feed["edge"], "network": "mind_power",
                 "kind": "island_infeed",
                 "from_node": UPSTREAM[feed["source"]],
                 "to_node": bus, "isolator_ids": [feed["breaker"]],
                 "route_domains": list(feed["route_domains"]),
                 "route_spaces": list(feed["proposed_cable_route_spaces"]),
                 "break_before_make": True},
                "available" if feed["selected"] else "standby")
            add("isolator", feed["breaker"], room,
                {"id": feed["breaker"], "network": "mind_power",
                 "kind": "breaker", "current_state": "closed",
                 "manual_operation": True, "remote_operable": False}, "closed")
        for machine in island["machines"]:
            add("equipment", machine["id"], machine["room"],
                {"id": machine["id"], "family": "lead_mind_compute",
                 "island": island["id"], "load_kw": machine["load_kw"],
                 "cooling_domain": machine["cooling_domain"],
                 "backbone_links": list(machine["backbone_links"])})
            add("node", machine["terminal_node"], machine["room"],
                {"id": machine["terminal_node"], "network": "mind_power",
                 "kind": "compute_power_terminal", "owner_type": "equipment",
                 "owner_id": machine["id"]})
            add("edge", machine["feeder"], machine["room"],
                {"id": machine["feeder"], "network": "mind_power",
                 "kind": "dedicated_compute_feeder", "from_node": bus,
                 "to_node": machine["terminal_node"],
                 "isolator_ids": [machine["isolator"]],
                 "route_spaces": list(machine["proposed_final_route_spaces"])}, "available")
            add("isolator", machine["isolator"], machine["room"],
                {"id": machine["isolator"], "network": "mind_power",
                 "kind": "breaker", "current_state": "closed",
                 "manual_operation": True, "remote_operable": False}, "closed")
    return rows


def validate_fitted_source_routes(design, ship):
    """Trace all ten A/B candidate taps against actual v0.5 power rows.

    A feeder may be proposed only when the upstream existing route is a
    real, continuous and physically isolatable path. Bridge feeders are
    bidirectional in G19; all other edges are walked in their authored
    direction. Proposed new cables must follow real adjacent ship spaces.
    This does NOT install or survey the proposed new cable, transfer switch,
    or conductor capacity.
    """
    validate_design(design)
    _check(isinstance(ship, dict)
           and ship.get("schema_version") == "ox.ship-world/0.1",
           "Incorrect installed-ship source authority")
    for section in ("spaces", "access_links", "equipment", "service_nodes",
                    "service_edges", "isolation_points"):
        _check(isinstance(ship.get(section), list),
               "Fitted source lacks " + section)
    spaces = {s["id"] for s in ship["spaces"]}
    equipment = {e["id"]: e for e in ship["equipment"]}
    adjacent = set()
    for link in ship["access_links"]:
        _check(link["from"] in spaces and link["to"] in spaces,
               "Corrupt canonical ship passage")
        adjacent.add((link["from"], link["to"]))
        adjacent.add((link["to"], link["from"]))

    def verified_cable_route(rooms, source_room, destination_room):
        _check(isinstance(rooms, list) and bool(rooms)
               and rooms[0] == source_room and rooms[-1] == destination_room,
               "Proposed cable endpoints are not physically attached")
        _check(all(room in spaces for room in rooms),
               "Proposed cable crosses a nonexistent space")
        _check(all((left, right) in adjacent
                   for left, right in zip(rooms, rooms[1:])),
               "Proposed cable jumps between nonadjacent compartments")

    nodes = {n["id"]: n for n in ship["service_nodes"] if n["network"] == "power"}
    edges = {e["id"]: e for e in ship["service_edges"] if e["network"] == "power"}
    switches = {s["id"]: s for s in ship["isolation_points"]
                if s["network"] == "power"}
    _check(len(nodes) == 438 and len(edges) == 450 and len(switches) == 466,
           "Expected historical G19 power-register topology is missing")
    _check(all(node in nodes for node in UPSTREAM.values()),
           "Main-board sources are not authored in G19")
    count = 0
    traversed = set()
    for island in design["islands"]:
        _check(island["control_room"] in spaces,
               "Proposed island service room is not on the ship")
        for machine in island["machines"]:
            _check(machine["room"] in spaces, "Compute room is not on the ship")
            verified_cable_route(machine["proposed_final_route_spaces"],
                                 island["control_room"], machine["room"])
        for feed in island["inputs"]:
            expected = UPSTREAM[feed["source"]]
            route = feed["route_domains"]
            _check(route[0] == expected
                   and feed.get("tap_node") in nodes,
                   "Proposed input has no verified existing tap node")
            path_node = expected
            original_edges = 0
            for token in route[1:]:
                if token.startswith("MIND-"):
                    # MIND-* denotes the new, separately fabricated cable.
                    # Its physical routing must be surveyed before install.
                    continue
                if token.startswith("EDGE-"):
                    _check(token in edges, "Candidate invents a fitted conductor: " + token)
                    edge = edges[token]
                    _check(set(edge["isolator_ids"]) <= set(route)
                           and all(i in switches for i in edge["isolator_ids"]),
                           "Candidate route hides a real upstream breaker")
                    _check(all(room in spaces for room in edge.get("route_spaces", [])),
                           "Authored feeder path traverses a nonexistent space")
                    if edge["from_node"] == path_node:
                        path_node = edge["to_node"]
                    elif edge.get("kind") == "bridge_feeder" and edge["to_node"] == path_node:
                        path_node = edge["from_node"]
                    else:
                        raise MindPowerError(
                            "Broken upstream electrical route at " + token)
                    traversed.add(token)
                    original_edges += 1
                elif token.startswith("ISO-"):
                    _check(token in switches, "Unfitted upstream isolator: " + token)
                elif token.startswith(("NODE-", "PWR-")):
                    _check(token in nodes, "Unfitted upstream electrical node: " + token)
                    _check(token == path_node, "Path node is not actually connected: " + token)
                else:
                    _check(token in spaces, "Proposed cable corridor not on ship: " + token)
            _check(original_edges > 0 and feed["tap_node"] == path_node,
                   "Candidate input does not reach its existing tapped board")
            tap_owner = nodes[feed["tap_node"]].get("owner_id")
            _check(tap_owner in equipment
                   and equipment[tap_owner].get("system") == "power",
                   "Source tap is not fitted power equipment")
            verified_cable_route(feed["proposed_cable_route_spaces"],
                                 equipment[tap_owner]["space_id"],
                                 island["control_room"])
            count += 1
    return {"candidate_islands": len(design["islands"]),
            "candidate_machines": MACHINE_COUNT,
            "independent_input_routes": count,
            "candidate_new_feed_routes_verified": count,
            "candidate_machine_final_routes_verified": MACHINE_COUNT,
            "original_feeders_traced": len(traversed),
            "future_world_rows": len(proposed_world_rows(design))}
