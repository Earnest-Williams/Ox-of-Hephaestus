"""Candidate ship-control backbone and independent local thermal support.

This module neither grants remote actuation nor starts a lead-mind process.
All paths are proposed new hardware over VERIFIED ship geometry. An
explicit operator commissioning step is required to create world rows.
"""
from __future__ import annotations

import copy
import json
import math
from collections import defaultdict, deque
from pathlib import Path

from world.ship_mind_power import MindPowerError, validate_design, default_design_path

SCHEMA = "ox.ship-support/1"
STATUS = "DESIGN_CANDIDATE_NOT_RUNTIME_AUTHORITY"
BROKEN = frozenset({"failed", "faulted", "severed", "jammed", "destroyed"})
MACHINES = frozenset("MIND-%02d" % i for i in range(1, 10))


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
    _require(plates == {m["cooling_domain"] for isl in power["islands"]
                        for m in isl["machines"]},
             "Uncooled machine cannot be counted in survival claims")
    decision = support.get("design_decisions") or {}
    _require(decision.get("original_ship_untouched") is True
             and "XCON-GAP-23" in decision.get("rack_cross_connection", "")
             and "passable" in decision.get("rack_cross_connection", ""),
             "Cross-trunk passage must not be locked to protect machine 3")
    return {"backbone_spans": 44, "machine_drops": 18,
            "rotary_data_couplers": 2, "thermal_islands": 5,
            "machines": len(expected)}


def fault_domains(support):
    backbone = support["backbone"]
    result = set(backbone["rail_rooms"]["A"] + backbone["rail_rooms"]["B"])
    for rail, rooms in backbone["rail_rooms"].items():
        result.update(_rail_span(rail, i) for i in range(len(rooms)-1))
    for c in backbone["couplers"]:
        result.add(c["id"])
        result.update((c["fixed_room"], c["rotating_room"]))
    for drop in backbone["drops"]:
        result.update((drop["id"], _nic_node(drop["rail"], drop["machine"]),
                       drop["machine"]))
        result.update(drop["route_spaces"])
    for pod in support["cooling_islands"]:
        result.update((pod["independent_buffer_id"], pod["heat_rejector_id"]))
        result.update(pod["individual_cold_plates"])
    return tuple(sorted(result))


def connected_machines(support, *, faults=(), available_machines=None,
                       physical_rows=None):
    """Return biggest intact connected compute cohort on either backbone.

    A/B backbone is distributed passive fibre, not a central switch.
    This is NOT proof of live gateway commands or of computational parity.
    """
    bad = set(faults)
    admitted = MACHINES if available_machines is None else set(available_machines)
    net = support["backbone"]
    links = defaultdict(set)

    def row_ok(key):
        if physical_rows is None:
            return True
        row = physical_rows.get(key)
        return (row is not None and row.source_model == SCHEMA
                and row.condition not in BROKEN
                and (row.category != "edge" or row.setting == "available"))

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
    biggest = set()
    visited = set()
    for vertex in list(links):
        if vertex in visited:
            continue
        q=deque([vertex]); component=set()
        visited.add(vertex)
        while q:
            pos=q.popleft()
            if pos in MACHINES and pos in admitted:
                component.add(pos)
            for neighbor in links[pos]:
                if neighbor not in visited:
                    visited.add(neighbor);q.append(neighbor)
        if len(component)>len(biggest):
            biggest=component
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
    return {"version":1, "units":{
        x["independent_buffer_id"]:{
            "surveyed":False, "capacity_kj":0.0, "free_kj":0.0,
            "absorbed_kj":0.0, "rejected_kj":0.0,
            "unabsorbed_kj":0.0, "generated_kj":0.0}
        for x in support["cooling_islands"]}}


def validate_cooling_ledger(support, ledger):
    specs={x["independent_buffer_id"]:x for x in support["cooling_islands"]}
    _require(isinstance(ledger,dict) and set(ledger)=={"version","units"}
             and ledger["version"]==1 and isinstance(ledger["units"],dict)
             and set(ledger["units"])==set(specs), "Unknown cooling storage ledger")
    for name,unit in ledger["units"].items():
        _require(isinstance(unit,dict) and set(unit)=={
            "surveyed","capacity_kj","free_kj","absorbed_kj",
            "rejected_kj","unabsorbed_kj","generated_kj"}
            and type(unit["surveyed"]) is bool,
            "Incomplete independent thermal ledger")
        for field in set(unit)-{"surveyed"}:
            _number(unit[field])
        _require(unit["capacity_kj"] <= specs[name]["buffer_nameplate_kj"] + 1e-9
                 and unit["free_kj"] <= unit["capacity_kj"] + 1e-9,
                 "Unmeasured thermal headroom created")
        _require(math.isclose(unit["generated_kj"],
                   unit["absorbed_kj"]+unit["rejected_kj"]+
                   unit["unabsorbed_kj"],abs_tol=1e-6),
                 "Heat vanished from finite coolant accounting")
        if not unit["surveyed"]:
            _require(all(unit[x]==0 for x in ("capacity_kj","free_kj",
                                              "absorbed_kj")),
                     "Unsurveyed buffer credited with cold capacity")
    return True


def survey_cooling_buffer(support, ledger, name, *, capacity_kj, free_kj):
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
    result["units"][name].update(surveyed=True,capacity_kj=capacity,
                                 free_kj=free)
    validate_cooling_ledger(support,result)
    return result


def step_cooling_buffer(support,ledger,*,operating_machines,seconds,
                        measured_rejection_kw=None,failed=()):
    """Finite heat accounting; externally measured rejection is NOT invented.

    `measured_rejection_kw` must be bounded by a real as-fitted coolant or
    room-air heat-transfer receipt before integration into live G19 physics.
    No input means zero heat rejection. Output lists machines whose heat
    cannot be contained: the future runtime must trip them, not pretend
    their network/power state proves they are computationally healthy.
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
        bank["rejected_kj"]+=rejected
        bad_heat=max(0,sound_heat-rejected-stored)+plate_heat
        bank["unabsorbed_kj"]+=bad_heat
        bank["generated_kj"]+=heat
        trips.update(failed_plates)
        if sound_heat-rejected-stored>1e-8:
            trips.update(running-failed_plates)
        receipts[pod["id"]]={
            "generated_kj":heat,"rejected_kj":rejected,
            "absorbed_kj":stored,"unabsorbed_kj":bad_heat}
    validate_cooling_ledger(support,new)
    return new, frozenset(trips), receipts


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
