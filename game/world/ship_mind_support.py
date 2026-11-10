"""Candidate ship-control backbone and independent local thermal support.

This module neither grants remote actuation nor starts a lead-mind process.
All paths are proposed new hardware over VERIFIED ship geometry. An
explicit operator commissioning step is required to create world rows.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import defaultdict, deque
from pathlib import Path

from world.ship_mind_power import MindPowerError, default_design_path, validate_design

SCHEMA = "ox.ship-support/1"
STATUS = "DESIGN_CANDIDATE_NOT_RUNTIME_AUTHORITY"
BROKEN = frozenset({"failed", "faulted", "severed", "jammed", "destroyed"})
MACHINES = frozenset("MIND-%02d" % i for i in range(1, 10))


def survey_signature(reference):
    """Bind an operator's measurement to the exact fitted apparatus."""
    return hashlib.sha256(
        json.dumps(reference, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def valid_support_survey(row, kind):
    """Require a current survey; repair or switch changes invalidate it."""
    survey = row.details.get(kind)
    valid = bool(
        isinstance(survey, dict)
        and type(survey.get("version")) is int
        and survey["version"] == 1
        and type(survey.get("row_revision")) is int
        and survey["row_revision"] == row.revision
        and survey.get("reference_sha256") == survey_signature(row.reference)
        and isinstance(survey.get("evidence_id"), str)
        and 0 < len(survey["evidence_id"]) <= 128
        and type(survey.get("observed_s")) in (int, float)
        and math.isfinite(survey["observed_s"])
        and survey["observed_s"] >= 0
    )
    if not valid:
        return False
    if kind == "data_survey":
        seals = survey.get("pressure_penetrations")
        if (
            survey.get("continuity_verified") is not True
            or survey.get("pressure_verified") is not True
            or not isinstance(seals, list)
            or not all(isinstance(s, str) for s in seals)
            or seals != sorted(set(seals))
        ):
            return False
        if row.category == "equipment":
            rpm = survey.get("continuous_rpm")
            return bool(
                survey.get("environment_verified") is True
                and survey.get("emi_verified") is True
                and type(rpm) in (int, float)
                and math.isfinite(rpm)
                and rpm >= 3.6
            )
        return survey.get("continuous_rpm") is None
    if kind == "cooling_survey":
        rate = survey.get("measured_kw")
        return (
            survey.get("sink_kind") in {"air", "lt"}
            and type(rate) in (int, float)
            and math.isfinite(rate)
            and rate > 0
        )
    return False


def data_penetrations(reference, ship):
    """List the real pressure boundaries crossed by one proposed cable."""
    boundaries = {}
    for passage in ship["access_links"]:
        if passage.get("pressure_boundary"):
            boundaries[frozenset((passage["from"], passage["to"]))] = passage["id"]
    route = reference.get("route_spaces", [])
    return sorted(
        {
            boundaries[frozenset((a, b))]
            for a, b in zip(route, route[1:])
            if frozenset((a, b)) in boundaries
        }
    )


def _require(ok, message):
    if not ok:
        raise MindPowerError(message)


def _number(value, *, positive=False):
    _require(type(value) in (float, int) and math.isfinite(value)
             and (value > 0 if positive else value >= 0),
             "Invalid finite thermal measurement")
    return float(value)


def default_support_path():
    return default_design_path().with_name("lead_mind_support_topology.json")


def load_support(path=None):
    return json.loads((Path(path) if path else default_support_path())
                      .read_text(encoding="utf-8"))


def _ship_geometry(ship):
    _require(isinstance(ship, dict)
             and ship.get("schema_version") == "ox.ship-world/0.1",
             "Wrong canonical ship authority")
    rooms = {item["id"]: item for item in ship["spaces"]}
    passages = set()
    for link in ship["access_links"]:
        x, y = link["from"], link["to"]
        _require(x in rooms and y in rooms,
                 "Access connection refers to uninstalled space")
        passages.add((x, y))
        passages.add((y, x))
    return rooms, passages


def _rail_span(rail, index):
    return "NET-SPAN-%s-%02d" % (rail, index)


def _rail_node(rail, room):
    return "NET-RAIL-%s-%s" % (rail, room)


def _nic_node(rail, machine):
    return "NET-NIC-%s-%s" % (rail, machine)


def validate_support(support, power, ship):
    """Prove corridor geometry, two actual frame crossings and isolation.

    This is a candidate geometry/identity proof, not physical commissioning
    or proof that a data fibre has been manufactured and drawn.
    """
    validate_design(power)
    _require(isinstance(support, dict)
             and support.get("schema_version") == SCHEMA
             and support.get("status") == STATUS
             and support.get("source_ship_model") == "ox.ship-world/0.1"
             and support.get("base_power_schema") == power["schema_version"],
             "Unrecognised or falsely fitted ship-control overlay")
    room_map, passages = _ship_geometry(ship)
    backbone = support.get("backbone")
    _require(isinstance(backbone, dict), "No ship-control backbone")
    rails = backbone.get("rail_rooms")
    _require(isinstance(rails, dict) and set(rails) == {"A", "B"},
             "Exactly two independent backbone rails required")
    for rail in ("A", "B"):
        line = rails[rail]
        originals = [room["id"] for room in ship["spaces"]
                     if room["id"].startswith("TRUNK-" + rail + "-")]
        _require(isinstance(line, list) and line == originals
                 and len(line) == 23 and len(set(line)) == 23
                 and all((x, y) in passages for x, y in zip(line, line[1:])),
                 "Backbone rail is not continuous through real spine rooms")
    _require(not set(rails["A"]) & set(rails["B"]),
             "A/B backbone rails share a physical room")

    couplers = backbone.get("couplers")
    _require(isinstance(couplers, list) and len(couplers) == 2,
             "Independent continuous HAB data rotary couplers required")
    by_rail = {x.get("rail"): x for x in couplers}
    _require(set(by_rail) == {"A", "B"}, "A/B coupler identities ambiguous")
    _require({c["id"] for c in couplers} == {"NET-ROT-A", "NET-ROT-B"},
             "Unexpected rotating data interface")
    for rail, c in by_rail.items():
        fixed = "HUB-FIXED-" + rail
        rotating = "HAB-04-COR" if rail == "A" else "HAB-08-COR"
        _require((c["fixed_room"], c["rotating_room"], c["kind"],
                  c["physical_status"]) == (
                     fixed, rotating, "continuous_rotary_data_coupler",
                     "NEW_UNCOMMISSIONED")
                 and room_map[fixed]["frame"] == "fixed"
                 and room_map[rotating]["frame"] == "hab_rotor",
                 "Data coupler must be an explicitly new independently rated rotary part")
    _require(by_rail["A"]["fixed_room"] != by_rail["B"]["fixed_room"]
             and by_rail["A"]["rotating_room"] != by_rail["B"]["rotating_room"],
             "Rotary data links cannot use the same mechanical interface")

    expected = {m["id"]:(island["region"], m["room"])
                for island in power["islands"] for m in island["machines"]}
    drops = backbone.get("drops")
    _require(isinstance(drops, list) and len(drops) == 18,
             "Each of nine machines requires two separate physical drops")
    seen = set()
    for drop in drops:
        machine, rail = drop.get("machine"), drop.get("rail")
        _require(machine in expected and rail in {"A", "B"}
                 and (machine, rail) not in seen,
                 "Duplicated or unknown machine network termination")
        seen.add((machine, rail))
        region, machine_room = expected[machine]
        _require(drop.get("id") == "NET-DROP-%s-%s" % (rail, machine)
                 and drop.get("region") == region
                 and drop.get("machine_room") == machine_room
                 and drop.get("anchor_room") in rails[rail],
                 "Network termination room or identity is inconsistent")
        route = drop.get("route_spaces")
        _require(isinstance(route, list) and len(route) >= 2
                 and route[0] == drop["anchor_room"]
                 and route[-1] == machine_room
                 and all(x in room_map for x in route),
                 "New data-cable route does not reach its stated machine")
        c = by_rail[rail] if region == "HAB" else None
        _require(drop.get("rotary_coupler") == (c["id"] if c else None),
                 "A/HAB crossing is neither independent nor explicitly attributed")
        crossings = [(x, y) for x, y in zip(route, route[1:])
                     if (x, y) not in passages]
        _require(crossings == ([(c["fixed_room"], c["rotating_room"])]
                              if c else []),
                 "Fabricated room jump or use of a personnel indexer as data conductor")
        # Do not treat a path on the wrong ship trunk as an independent rail.
        # Small, cross-connecting branch drops are permitted, because both
        # rails themselves remain in disjoint trunk routes.
    _require(len(seen) == 18, "Not all machine NICs have dual termination")

    cooling = support.get("cooling_islands")
    _require(isinstance(cooling, list) and len(cooling) == 5,
             "Exactly five separate cold-buffer islands required")
    used, plates = set(), set()
    for pod in cooling:
        island = next((x for x in power["islands"]
                       if pod.get("region") == x["region"]), None)
        _require(island is not None and pod.get("id") == "THERM-" + island["id"]
                 and pod.get("service_room") == island["control_room"]
                 and pod.get("machines") == [x["id"] for x in island["machines"]],
                 "Thermal island shares or misplaces machine load")
        _require(pod.get("status") == "CANDIDATE_UNSURVEYED"
                 and len(pod["machines"]) <= 2,
                 "Thermal path must stay locally buffered and unsurveyed")
        for k in ("independent_buffer_id", "heat_rejector_id"):
            _require(isinstance(pod.get(k), str) and pod[k] not in used,
                     "A local thermal storage or heat sink is shared between islands")
            used.add(pod[k])
        _require(pod.get("individual_cold_plates") ==
                 [m["cooling_domain"] for m in island["machines"]]
                 and not plates.intersection(pod["individual_cold_plates"]),
                 "Cold plates need one individually tracked machine load")
        plates.update(pod["individual_cold_plates"])
        _require(_number(pod.get("heat_rate_kw"), positive=True) ==
                 sum(m["load_kw"] for m in island["machines"])
                 and _number(pod.get("peak_rejection_kw"), positive=True) >=
                 pod["heat_rate_kw"]
                 and _number(pod.get("buffer_nameplate_kj"), positive=True) >=
                 pod["heat_rate_kw"] * _number(pod.get("ride_through_seconds"), positive=True)
                 and _number(pod["monitored_shutdown_temperature_k"]) >
                 _number(pod["normal_temperature_max_k"]) >
                 _number(pod["normal_temperature_min_k"]),
                 "Cooling power, bounded autonomy or shutdown is inadequately rated")
        feed = pod.get("lt_connection")
        original_nodes = {n["id"]: n for n in ship["service_nodes"]}
        source_id = "NODE-HAB-04-LT-COOLING-MAN" if pod["region"] == "HAB" else "NODE-LT-PLANT"
        source_room = "HAB-04-SERVICE-GALLERY" if pod["region"] == "HAB" else "ROTARY-UTIL-A"
        _require(
            isinstance(feed, dict)
            and feed.get("id") == "LT-FEED-" + pod["region"]
            and feed.get("node") == "NODE-MIND-LT-" + pod["region"]
            and feed.get("isolator") == "ISO-MIND-LT-" + pod["region"]
            and feed.get("source_node") == source_id
            and original_nodes[source_id]["network"] == "lt_cooling"
            and feed.get("source_room") == source_room,
            "Local thermal circuit has no actual original LT source",
        )
        routes = pod.get("machine_coolant_routes")
        _require(
            isinstance(routes, dict) and set(routes) == set(pod["machines"]),
            "Each cold plate requires its actual local pipe route",
        )
        paths = [(feed.get("route_spaces"), source_room, pod["service_room"])]
        paths += [(routes[m["id"]], pod["service_room"], m["room"]) for m in island["machines"]]
        for path, start, end in paths:
            _require(
                isinstance(path, list)
                and len(path) >= 1
                and path[0] == start
                and path[-1] == end
                and len(set(path)) == len(path)
                and all(room in room_map for room in path)
                and all(
                    (a, b) in passages and room_map[a]["frame"] == room_map[b]["frame"]
                    for a, b in zip(path, path[1:])
                ),
                "Coolant route invents a passage or moving-frame crossing",
            )
    _require(plates == {m["cooling_domain"] for isl in power["islands"]
                        for m in isl["machines"]},
             "Uncooled machine cannot be counted in survival claims")
    rack=support.get("secured_rack")
    _require(isinstance(rack,dict) and
             (rack.get("id"),rack.get("machine"),rack.get("room"),
              rack.get("physical_lock_mode"),rack.get("reader_commissioned"),
              rack.get("status")) == (
                "MIND-03-SECURE-RACK","MIND-03","XCON-GAP-23",
                "rack_only",False,"CANDIDATE_NO_ACCESS_READER"),
             "Protected rack must never lock the cross-trunk room")
    doors={x["id"]:x for x in ship["access_links"]}
    _require(rack.get("passage_doors")==[
                "ACC-XCON-GAP-23-A","ACC-XCON-GAP-23-B"]
             and all(name in doors for name in rack["passage_doors"])
             and all("XCON-GAP-23" in (
                    doors[name]["from"],doors[name]["to"])
                     for name in rack["passage_doors"]),
             "Monitored rack must preserve both real crew through-routes")

    gateways=support.get("gateway_candidates")
    _require(isinstance(gateways,list) and len(gateways)==1,
             "First mixed-generation gateway host not defined")
    gateway=gateways[0]
    equipment={x["id"]:x for x in ship["equipment"]}
    host=equipment.get(gateway.get("host_equipment"))
    _require(gateway.get("id")=="GW-LCS-DR-03"
             and gateway.get("segment_id")=="SEG-DR-03"
             and gateway.get("room")=="BE-05-SVC"
             and host is not None and host["kind"]=="local_control_station"
             and host["space_id"]==gateway["room"]
             and gateway.get("generation")=="mixed"
             and gateway.get("remote_authority") is False
             and gateway.get("command_enabled") is False
             and gateway.get("mapping_revision")==0
             and gateway.get("protocol_mapping")=="unknown",
             "Original drum-3 gateway must be a disabled physical host")
    _require(set(gateway.get("monitored_devices",[]))=={
                "DR-03-CARGO-HX","DR-03-CARGO-GAS","ISO-DR-03-LT-IF"},
             "First gateway must not add unrelated remote control")
    gateway_drops=gateway.get("rail_drops")
    _require(isinstance(gateway_drops,list) and len(gateway_drops)==2
             and {x.get("rail") for x in gateway_drops}=={"A","B"},
             "Gateway must preserve distinct but locally fallible cable paths")
    for gd in gateway_drops:
        rail=gd["rail"];path=gd.get("route_spaces")
        _require(gd.get("id")=="NET-GW-DROP-"+rail+"-DR-03"
                 and gd.get("anchor_room")=="TRUNK-"+rail+"-DR-03"
                 and isinstance(path,list) and len(path)>=2
                 and path[0]==gd["anchor_room"]
                 and path[-1]==gateway["room"]
                 and all(x in room_map for x in path)
                 and all((x,y) in passages for x,y in zip(path,path[1:])),
                 "Gateway branch claims a cable through nonexistent geometry")

    decision = support.get("design_decisions") or {}
    _require(decision.get("original_ship_untouched") is True
             and "XCON-GAP-23" in decision.get("rack_cross_connection", "")
             and "passable" in decision.get("rack_cross_connection", ""),
             "Cross-trunk passage must not be locked to protect machine 3")
    return {"backbone_spans": 44, "machine_drops": 18,
            "rotary_data_couplers": 2, "thermal_islands": 5,
            "machines": len(expected),
            "gateway_hosts":1, "secured_racks":1}


def fault_domains(support):
    backbone = support["backbone"]
    result = set(backbone["rail_rooms"]["A"] + backbone["rail_rooms"]["B"])
    for rail, rooms in backbone["rail_rooms"].items():
        result.update(_rail_node(rail, room) for room in rooms)
        result.update(_rail_span(rail, i) for i in range(len(rooms)-1))
    for c in backbone["couplers"]:
        result.add(c["id"])
        result.update((c["fixed_room"], c["rotating_room"]))
    for drop in backbone["drops"]:
        result.update((drop["id"], _nic_node(drop["rail"], drop["machine"]),
                       drop["machine"]))
        result.update(drop["route_spaces"])
    result.add(support["secured_rack"]["id"])
    for gateway in support["gateway_candidates"]:
        result.add(gateway["id"])
        for drop in gateway["rail_drops"]:
            result.update((drop["id"],"NET-GW-NIC-"+drop["rail"]+"-DR-03"))
            result.update(drop["route_spaces"])
    for pod in support["cooling_islands"]:
        result.update((pod["independent_buffer_id"], pod["heat_rejector_id"]))
        result.update(pod["lt_connection"][key] for key in ("id", "node", "isolator"))
        result.update(pod["individual_cold_plates"])
    return tuple(sorted(result))


def connected_machines(
    support, *, faults=(), available_machines=None, physical_rows=None, gateway_id=None
):
    """Return biggest intact connected compute cohort on either backbone.

    A/B backbone is distributed passive fibre, not a central switch.
    This is NOT proof of live gateway commands or of computational parity.
    """
    bad = set(faults)
    admitted = MACHINES if available_machines is None else set(available_machines)
    net = support["backbone"]
    links = defaultdict(set)
    endpoints = set(MACHINES)
    if gateway_id is not None:
        _require(
            gateway_id in {g["id"] for g in support["gateway_candidates"]},
            "Unknown physical gateway endpoint",
        )
        endpoints.add(gateway_id)

    def row_ok(key):
        if physical_rows is None:
            return True
        row = physical_rows.get(key)
        return (
            row is not None
            and row.source_model == SCHEMA
            and row.condition not in BROKEN
            and (row.category != "edge" or row.setting == "available")
            and (row.category == "node" or valid_support_survey(row, "data_survey"))
        )

    def join(u, v):
        links[u].add(v)
        links[v].add(u)

    for rail in ("A","B"):
        rooms = net["rail_rooms"][rail]
        for idx, room in enumerate(rooms):
            node = _rail_node(rail, room)
            if room in bad or node in bad or not row_ok("node:" + node):
                continue
            links.setdefault(node, set())
        for i, (left, right) in enumerate(zip(rooms, rooms[1:])):
            ident = _rail_span(rail,i)
            a, b = _rail_node(rail,left), _rail_node(rail,right)
            if ident not in bad and a in links and b in links and row_ok("edge:" + ident):
                join(a,b)
    for d in net["drops"]:
        rail, machine = d["rail"], d["machine"]
        nic = _nic_node(rail,machine)
        coupler = d["rotary_coupler"]
        if (machine not in admitted or machine in bad or d["id"] in bad or
                nic in bad or any(room in bad for room in d["route_spaces"]) or
                (coupler is not None and (coupler in bad or
                   not row_ok("equipment:" + coupler))) or
                not row_ok("node:" + nic) or not row_ok("edge:" + d["id"])):
            continue
        anchor = _rail_node(rail,d["anchor_room"])
        if anchor in links:
            join(anchor,machine)
    if gateway_id is not None and gateway_id not in bad:
        gateway = next(g for g in support["gateway_candidates"] if g["id"] == gateway_id)
        hardware = (
            physical_rows.get("equipment:" + gateway_id) if physical_rows is not None else None
        )
        if physical_rows is None or (hardware is not None and hardware.condition not in BROKEN):
            for drop in gateway["rail_drops"]:
                nic = "NET-GW-NIC-" + drop["rail"] + "-DR-03"
                anchor = _rail_node(drop["rail"], drop["anchor_room"])
                if (
                    drop["id"] not in bad
                    and nic not in bad
                    and not any(room in bad for room in drop["route_spaces"])
                    and row_ok("edge:" + drop["id"])
                    and row_ok("node:" + nic)
                    and anchor in links
                ):
                    join(anchor, gateway_id)
    # Endpoints are consumers, not an implicit A/B router. Traverse only
    # backbone junctions, and collect attached machines without walking
    # through a machine to the other rail. A genuine network bridge would
    # require its own fitted hardware and explicit operating state.
    biggest=set()
    visited=set()
    for vertex in list(links):
        if vertex in endpoints or vertex in visited:
            continue
        q=deque([vertex])
        component=set()
        visited.add(vertex)
        while q:
            pos=q.popleft()
            for neighbor in links[pos]:
                if neighbor in endpoints:
                    if neighbor in admitted or neighbor == gateway_id:
                        component.add(neighbor)
                elif neighbor not in visited:
                    visited.add(neighbor)
                    q.append(neighbor)
        if gateway_id is None or gateway_id in component:
            machines = component & MACHINES
            if len(machines) > len(biggest):
                biggest = machines
    return frozenset(biggest)


def single_fault_network_sweep(support, power, ship):
    validate_support(support,power,ship)
    cases={}
    # Thermal faults are tested separately; this sweep proves physical
    # communication paths only.
    components = set(fault_domains(support)) - {
        p["independent_buffer_id"] for p in support["cooling_islands"]} - {
        p["heat_rejector_id"] for p in support["cooling_islands"]} - {
        x for p in support["cooling_islands"]
        for x in p["individual_cold_plates"]}
    for component in sorted(components):
        live=connected_machines(support,faults={component})
        cases[component]=9-len(live)
        _require(len(live)>=7,
                 "Common network fault disables >2 machines: "+component)
    return cases


def initial_cooling_ledger(support):
    """Start five unmeasured stores with no usable thermal headroom."""
    return {
        "version": 2,
        "units": {
            x["independent_buffer_id"]: {
                "surveyed": False,
                "capacity_kj": 0.0,
                "free_kj": 0.0,
                "initial_free_kj": 0.0,
                "recovered_kj": 0.0,
                "absorbed_kj": 0.0,
                "rejected_kj": 0.0,
                "unabsorbed_kj": 0.0,
                "generated_kj": 0.0,
            }
            for x in support["cooling_islands"]
        },
    }


def validate_cooling_ledger(support, ledger):
    """Check both cumulative heat flow and the current cold inventory."""
    specs={x["independent_buffer_id"]:x for x in support["cooling_islands"]}
    _require(
        isinstance(ledger, dict)
        and set(ledger) == {"version", "units"}
        and type(ledger["version"]) is int
        and ledger["version"] == 2
        and isinstance(ledger["units"], dict)
        and set(ledger["units"]) == set(specs),
        "Unknown cooling storage ledger",
    )
    for name,unit in ledger["units"].items():
        _require(
            isinstance(unit, dict)
            and set(unit)
            == {
                "surveyed",
                "capacity_kj",
                "free_kj",
                "absorbed_kj",
                "rejected_kj",
                "unabsorbed_kj",
                "generated_kj",
                "initial_free_kj",
                "recovered_kj",
            }
            and type(unit["surveyed"]) is bool,
            "Incomplete independent thermal ledger",
        )
        for field in set(unit)-{"surveyed"}:
            _number(unit[field])
        _require(
            unit["capacity_kj"] <= specs[name]["buffer_nameplate_kj"] + 1e-9
            and unit["free_kj"] <= unit["capacity_kj"] + 1e-9
            and unit["initial_free_kj"] <= unit["capacity_kj"] + 1e-9
            and unit["recovered_kj"] <= unit["rejected_kj"] + 1e-9,
            "Unmeasured thermal headroom created",
        )
        _require(
            math.isclose(
                unit["generated_kj"],
                unit["absorbed_kj"]
                + unit["rejected_kj"]
                + unit["unabsorbed_kj"]
                - unit["recovered_kj"],
                abs_tol=1e-6,
            ),
            "Heat vanished from finite coolant accounting",
        )
        _require(
            math.isclose(
                unit["free_kj"],
                unit["initial_free_kj"] - unit["absorbed_kj"] + unit["recovered_kj"],
                abs_tol=1e-6,
            ),
            "Cold headroom changed without physical heat transfer",
        )
        if not unit["surveyed"]:
            _require(
                all(
                    unit[x] == 0
                    for x in (
                        "capacity_kj",
                        "free_kj",
                        "absorbed_kj",
                        "initial_free_kj",
                        "recovered_kj",
                    )
                ),
                "Unsurveyed buffer credited with cold capacity",
            )
    return True


def migrate_cooling_ledger(support, ledger):
    """Preserve v1 stored heat and every meter, without restoring cold."""
    if isinstance(ledger, dict) and type(ledger.get("version")) is int and ledger["version"] == 1:
        revised = copy.deepcopy(ledger)
        _require(isinstance(revised.get("units"), dict), "Invalid legacy cooling units")
        revised["version"] = 2
        for unit in revised["units"].values():
            _require(
                isinstance(unit, dict)
                and set(unit)
                == {
                    "surveyed",
                    "capacity_kj",
                    "free_kj",
                    "absorbed_kj",
                    "rejected_kj",
                    "unabsorbed_kj",
                    "generated_kj",
                },
                "Invalid legacy cooling custody",
            )
            unit["initial_free_kj"] = _number(unit["free_kj"]) + _number(unit["absorbed_kj"])
            unit["recovered_kj"] = 0.0
        validate_cooling_ledger(support, revised)
        return revised
    validate_cooling_ledger(support, ledger)
    return copy.deepcopy(ledger)


def survey_cooling_buffer(support, ledger, name, *, capacity_kj, free_kj):
    """Record one physical measurement, never refill a surveyed store."""
    validate_cooling_ledger(support,ledger)
    _require(name in ledger["units"] and
             not ledger["units"][name]["surveyed"],
             "Unknown, previously surveyed or unfitted coolant storage")
    rating=next(x["buffer_nameplate_kj"] for x in support["cooling_islands"]
                if x["independent_buffer_id"] == name)
    capacity=_number(capacity_kj, positive=True)
    free=_number(free_kj)
    _require(capacity<=rating and free<=capacity,
             "Measured local thermal storage exceeds rating")
    result=copy.deepcopy(ledger)
    result["units"][name].update(
        surveyed=True, capacity_kj=capacity, free_kj=free, initial_free_kj=free
    )
    validate_cooling_ledger(support,result)
    return result


def step_cooling_buffer(support,ledger,*,operating_machines,seconds,
                        measured_rejection_kw=None,failed=()):
    """Finite heat accounting; externally measured rejection is NOT invented.

    The caller proves an as-fitted heat-transfer path and deposits ALL
    rejected heat in its receiving cell. Spare rejection capacity releases
    stored heat, rather than silently resetting the buffer to full.
    """
    validate_cooling_ledger(support,ledger)
    dt=_number(seconds,positive=True)
    _require(dt<=60, "Unbounded thermal timestep")
    active=set(operating_machines)
    _require(active<=MACHINES, "Unfitted machine heat source")
    rejects=measured_rejection_kw or {}
    _require(set(rejects)<={x["id"] for x in support["cooling_islands"]},
             "Unknown heat sink credited with energy rejection")
    bad=set(failed)
    new=copy.deepcopy(ledger)
    trips=set()
    receipts={}
    for pod in support["cooling_islands"]:
        running=set(pod["machines"]) & active
        per_machine_kw=pod["heat_rate_kw"] / len(pod["machines"])
        heat=per_machine_kw * len(running) * dt
        failed_plates={
            machine for plate,machine in zip(
                pod["individual_cold_plates"],pod["machines"])
            if plate in bad and machine in running}
        plate_heat=per_machine_kw * len(failed_plates) * dt
        sound_heat=heat - plate_heat
        rejected_rate=_number(rejects.get(pod["id"],0))
        _require(rejected_rate<=pod["peak_rejection_kw"],
                 "Rejector output exceeded actual nameplate")
        reject_ok=pod["heat_rejector_id"] not in bad
        rejected=min(sound_heat,rejected_rate*dt) if reject_ok else 0
        bank=new["units"][pod["independent_buffer_id"]]
        capacity=(bank["free_kj"] if bank["surveyed"]
                  and pod["independent_buffer_id"] not in bad else 0)
        stored=min(sound_heat-rejected,capacity)
        bank["free_kj"]-=stored
        bank["absorbed_kj"]+=stored
        recoverable = (
            bank["capacity_kj"] - bank["free_kj"]
            if bank["surveyed"] and pod["independent_buffer_id"] not in bad
            else 0
        )
        recovered = min(recoverable, max(0, rejected_rate * dt - rejected)) if reject_ok else 0
        bank["free_kj"] += recovered
        bank["recovered_kj"] += recovered
        rejected += recovered
        bank["rejected_kj"]+=rejected
        bad_heat = max(0, sound_heat - (rejected - recovered) - stored) + plate_heat
        bank["unabsorbed_kj"]+=bad_heat
        bank["generated_kj"]+=heat
        trips.update(failed_plates)
        if sound_heat - (rejected - recovered) - stored > 1e-8:
            trips.update(running-failed_plates)
        receipts[pod["id"]] = {
            "generated_kj": heat,
            "rejected_kj": rejected,
            "absorbed_kj": stored,
            "unabsorbed_kj": bad_heat,
            "recovered_kj": recovered,
        }
    validate_cooling_ledger(support,new)
    return new, frozenset(trips), receipts


def air_rejection_rates(support, *, physical_rows, cells, room_zones, seconds, powered_machines):
    """Bound surveyed local air rejection by actual gas and thermal headroom.

    Fan auxiliaries are included in the rated machine load. Shared receiving
    cells have one thermal budget. A powered machine supplies fan auxiliaries.
    No heat is exported directly to vacuum or an imaginary LT connection.
    """
    dt = _number(seconds, positive=True)
    _require(dt <= 60, "Unbounded air rejection timestep")
    remaining = {}
    rates = {}
    for pod in support["cooling_islands"]:
        row = physical_rows["equipment:" + pod["heat_rejector_id"]]
        cell_id = room_zones.get(pod["service_room"])
        cell = cells.get(cell_id)
        rate = 0.0
        if (
            set(pod["machines"]) & set(powered_machines)
            and row.condition not in BROKEN
            and valid_support_survey(row, "cooling_survey")
            and cell
            and row.details["cooling_survey"].get("sink_kind", "air") == "air"
        ):
            measured = _number(row.details["cooling_survey"].get("measured_kw"))
            _require(measured <= pod["peak_rejection_kw"], "Air rejector survey exceeds rating")
            t = _number(cell["temperature"], positive=True)
            mass = _number(cell["mass"])
            volume = _number(cell["volume"], positive=True)
            if (
                pod["normal_temperature_min_k"] <= t < pod["normal_temperature_max_k"]
                and mass * 287.05 * t / volume >= 50000
            ):
                capacity = _number(cell["capacity"], positive=True) + mass
                headroom = (pod["normal_temperature_max_k"] - t) * capacity
                remaining[cell_id] = min(remaining.get(cell_id, headroom), headroom)
                rate = min(measured, remaining[cell_id] / dt)
                remaining[cell_id] -= rate * dt
        rates[pod["id"]] = rate
    return rates


def lt_rejection_rates(
    support,
    *,
    physical_rows,
    connection_rows,
    connected_lt_nodes,
    powered_machines,
    cooling_budget_kw,
):
    """Debit one finite original radiator allocation through surveyed pipes."""
    remaining = _number(cooling_budget_kw)
    rates = {}
    for pod in support["cooling_islands"]:
        row = physical_rows["equipment:" + pod["heat_rejector_id"]]
        feed = pod["lt_connection"]
        keys = ["edge:" + feed["id"], "node:" + feed["node"], "isolator:" + feed["isolator"]]
        parts = [connection_rows.get(k) for k in keys]
        survey = row.details.get("cooling_survey", {})
        rate = 0.0
        if (
            set(pod["machines"]) & set(powered_machines)
            and row.condition not in BROKEN
            and valid_support_survey(row, "cooling_survey")
            and survey.get("sink_kind") == "lt"
            and feed["source_node"] in connected_lt_nodes
            and all(part is not None and part.condition not in BROKEN for part in parts)
            and parts[0].setting == "available"
            and parts[2].setting == "open"
            and survey.get("connection_revisions") == {part.key: part.revision for part in parts}
        ):
            measured = _number(survey.get("measured_kw"))
            _require(measured <= pod["peak_rejection_kw"], "LT rejector survey exceeds rating")
            rate = min(measured, remaining)
            remaining -= rate
        rates[pod["id"]] = rate
    return rates


def proposed_heat_connection_rows(support, power, ship):
    """Five separately installed LT feed/return pairs, terminals and valves."""
    validate_support(support, power, ship)
    rows = {}
    for pod in support["cooling_islands"]:
        feed = pod["lt_connection"]
        route = feed["route_spaces"]
        room = pod["service_room"]
        refs = [
            (
                "node",
                feed["node"],
                "unverified",
                {
                    "id": feed["node"],
                    "network": "mind_lt",
                    "kind": "local_rejector_terminal",
                    "owner_type": "equipment",
                    "owner_id": pod["heat_rejector_id"],
                },
            ),
            (
                "edge",
                feed["id"],
                "available",
                {
                    "id": feed["id"],
                    "network": "mind_lt",
                    "kind": "lt_feed_return_pair",
                    "from_node": feed["source_node"],
                    "to_node": feed["node"],
                    "route_spaces": route,
                    "machine_routes": pod["machine_coolant_routes"],
                    "isolator_ids": [feed["isolator"]],
                },
            ),
            (
                "isolator",
                feed["isolator"],
                "closed",
                {
                    "id": feed["isolator"],
                    "network": "mind_lt",
                    "kind": "manual_coolant_valve",
                    "edge_ids": [feed["id"]],
                    "service_room": room,
                },
            ),
        ]
        for category, name, setting, reference in refs:
            key = category + ":" + name
            rows[key] = {
                "key": key,
                "category": category,
                "source_id": name,
                "source_model": SCHEMA,
                "space_id": room,
                "reference": reference,
                "condition": "serviceable",
                "setting": setting,
                "details": {},
            }
    return rows


def proposed_support_rows(support, power, ship):
    """Versioned operator-installable hardware, never legacy power edges."""
    validate_support(support,power,ship)
    rows={}
    def add(category, identifier, room, reference,setting="unverified"):
        key=category+":"+identifier
        _require(key not in rows,"Duplicated support component")
        rows[key]={
            "key":key,"category":category,"source_id":identifier,
            "source_model":SCHEMA,"space_id":room,
            "condition":"serviceable","setting":setting,
            "reference":reference,"details":{}}
    for rail,rooms in support["backbone"]["rail_rooms"].items():
        for i,room in enumerate(rooms):
            name=_rail_node(rail,room)
            add("node",name,room,{
                "id":name,"network":"mind_data","kind":"passive_fibre_splice",
                "owner_type":"space","owner_id":room})
            if i:
                previous=rooms[i-1];edge=_rail_span(rail,i-1)
                add("edge",edge,room,{
                    "id":edge,"network":"mind_data","kind":"passive_fibre_span",
                    "from_node":_rail_node(rail,previous),"to_node":name,
                    "route_spaces":[previous,room],"isolator_ids":[]},
                    "available")
    for c in support["backbone"]["couplers"]:
        add("equipment",c["id"],c["fixed_room"],{
            "id":c["id"],"family":"continuous_rotary_data_coupler",
            "network":"mind_data","from_room":c["fixed_room"],
            "to_room":c["rotating_room"],"rail":c["rail"]})
    for d in support["backbone"]["drops"]:
        nic=_nic_node(d["rail"],d["machine"])
        add("node",nic,d["machine_room"],{
            "id":nic,"network":"mind_data","kind":"compute_transceiver",
            "owner_type":"equipment","owner_id":d["machine"]})
        add("edge",d["id"],d["machine_room"],{
            "id":d["id"],"network":"mind_data","kind":"machine_fibre_drop",
            "from_node":_rail_node(d["rail"],d["anchor_room"]),
            "to_node":nic,"isolator_ids":[],
            "route_spaces":d["route_spaces"],
            "rotary_coupler":d["rotary_coupler"]}, "available")
    rack=support["secured_rack"]
    add("equipment",rack["id"],rack["room"],{
        "id":rack["id"],"family":"local_compute_security_enclosure",
        "owner_id":rack["machine"],
        "passage_doors_unchanged":list(rack["passage_doors"]),
        "access_point_id":rack["access_point"],
        "reader_commissioned":False})
    for gateway in support["gateway_candidates"]:
        add("equipment",gateway["id"],gateway["room"],{
            "id":gateway["id"],"family":"ship_control_gateway",
            "host_equipment":gateway["host_equipment"],
            "segment_id":gateway["segment_id"],
            "generation":gateway["generation"],
            "protocol_mapping":gateway["protocol_mapping"],
            "mapping_revision":gateway["mapping_revision"],
            "remote_authority":False,"command_enabled":False,
            "power_verified":False})
        for drop in gateway["rail_drops"]:
            nic="NET-GW-NIC-"+drop["rail"]+"-DR-03"
            add("node",nic,gateway["room"],{
                "id":nic,"network":"mind_data",
                "kind":"unverified_gateway_transceiver",
                "owner_type":"equipment","owner_id":gateway["id"]})
            add("edge",drop["id"],gateway["room"],{
                "id":drop["id"],"network":"mind_data",
                "kind":"gateway_fibre_drop",
                "from_node":_rail_node(drop["rail"],drop["anchor_room"]),
                "to_node":nic,"isolator_ids":[],
                "route_spaces":list(drop["route_spaces"])},
                "available")
    for pod in support["cooling_islands"]:
        room=pod["service_room"]
        for key,family in [(pod["independent_buffer_id"],"mind_cold_buffer"),
                           (pod["heat_rejector_id"],"mind_local_heat_rejector")]:
            add("equipment",key,room,{
                "id":key,"family":family,"cooling_island":pod["id"],
                "buffer_nameplate_kj":pod["buffer_nameplate_kj"],
                "peak_rejection_kw":pod["peak_rejection_kw"]})
        for plate,machine in zip(pod["individual_cold_plates"],pod["machines"]):
            room=next(m["room"] for isl in power["islands"]
                      for m in isl["machines"] if m["id"]==machine)
            add("equipment",plate,room,{
                "id":plate,"family":"individual_compute_cold_plate",
                "cooling_island":pod["id"],"owner_id":machine})
    return rows
