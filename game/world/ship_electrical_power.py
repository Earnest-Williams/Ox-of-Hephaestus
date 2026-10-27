"""G19 installed electrical network, protective trips and finite reserve accounting.

No energy is inferred from a declared switch, unqualified battery, or shore
connector. The installed nodes/edges/contacts remain authoritative; source
edges are directed, except the two physically bidirectional feeder kinds.
This is game-world engineering, not a fault-current certification model.
"""
from __future__ import annotations

import copy
import math
from collections import defaultdict, deque

GENERATION_MW = {"GEN-M": 3.0, "GEN-A": .65, "GEN-B": .65}
LOAD_MW = {"essential": .65, "protected": .75, "normal": 1.35,
           "demanding": 2.6}
SHIP_CAP_MW = 3.3
EXPECTED_TOPOLOGY = (438, 450, 466)
BATTERIES = ("BAT-COMMON-OPS", "BAT-COMMON-PROT")
FLYWHEELS = tuple(f"F{side}-FW-{n:02d}" for side in (1, 2)
                  for n in range(1, 33))
FLYWHEEL_NAMEPLATE_KWH = 3906.25
MAIN_BOARDS = ("PWR-MSB-A", "PWR-MSB-B")


class ElectricalError(ValueError):
    """Invalid physical network, generation, energy or switch state."""


def number(value, *, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < (1e-12 if positive else 0)):
        raise ElectricalError("Nonphysical finite electrical measurement")
    return float(value)


def initial_electrical():
    return {
        "version": 2, "banks": {}, "flywheels": {}, "shore": None,
        "faults": {}, "worksite_surveys": {}, "sync": None,
        "meter": {"generation_kwh": 0.0, "shore_import_kwh": 0.0,
                  "served_kwh": 0.0, "unserved_kwh": 0.0,
                  "battery_discharge_kwh": 0.0,
                  "battery_charge_kwh": 0.0,
                  "flywheel_discharge_kwh": 0.0,
                  "flywheel_charge_kwh": 0.0},
        "last": {},
    }


def validate_electrical(s):
    if not isinstance(s, dict) or set(s) != {
            "version", "banks", "flywheels", "shore", "faults",
            "worksite_surveys", "sync", "meter", "last"
    } or s["version"] != 2:
        raise ElectricalError("Unrecognised commissioned electrical ledger")
    if not isinstance(s["banks"], dict) or not set(s["banks"]) <= set(BATTERIES):
        raise ElectricalError("Fictional battery source")
    if (not isinstance(s["flywheels"], dict)
            or not set(s["flywheels"]) <= set(FLYWHEELS)):
        raise ElectricalError("Unknown installed energy-storage module")
    for name, bank in {**s["banks"], **s["flywheels"]}.items():
        if set(bank) != {"capacity_kwh", "charge_kwh", "initial_kwh",
                         "charged_kwh", "discharged_kwh", "max_charge_mw",
                         "max_discharge_mw", "mode"}:
            raise ElectricalError("Unmeasured battery bank fields")
        for key in set(bank) - {"mode"}:
            number(bank[key])
        if (bank["mode"] not in {"standby", "charge", "discharge"}
                or not 0 <= bank["charge_kwh"] <= bank["capacity_kwh"] + 1e-8
                or not 0 <= bank["initial_kwh"] <= bank["capacity_kwh"]
                or not math.isclose(bank["initial_kwh"] + bank["charged_kwh"]
                                    - bank["discharged_kwh"], bank["charge_kwh"],
                                    rel_tol=1e-9, abs_tol=1e-7)):
            raise ElectricalError("Battery energy was created or lost")
    shore = s["shore"]
    if shore is not None:
        if not isinstance(shore, dict) or set(shore) != {
                "rated_mw", "connected", "import_kwh"}:
            raise ElectricalError("Invalid external shore meter")
        number(shore["rated_mw"], positive=True)
        number(shore["import_kwh"])
        if type(shore["connected"]) is not bool:
            raise ElectricalError("Invalid shore switching state")
    if (not isinstance(s["worksite_surveys"], dict)
            or any(room not in {"GEN-M-ROOM", "GEN-A-ROOM", "GEN-B-ROOM",
                                "F1-BAY", "F2-BAY"}
                   or category != "suited_service"
                   for room, category in s["worksite_surveys"].items())):
        raise ElectricalError("Unverified or invented hazardous electrical worksite")
    if not isinstance(s["faults"], dict):
        raise ElectricalError("Invalid breaker fault ledger")
    for target, fault in s["faults"].items():
        if not isinstance(target, str) or not target.startswith("ISO-"):
            raise ElectricalError("Unidentified real overcurrent switch")
        if set(fault) != {"observed_mw", "rating_mw", "overload_s", "latched"}:
            raise ElectricalError("Unmeasured breaker protection")
        for k in ("observed_mw", "rating_mw", "overload_s"):
            number(fault[k], positive=k == "rating_mw")
        if type(fault["latched"]) is not bool:
            raise ElectricalError("Invalid protection latch")
    if s["sync"] is not None:
        if not isinstance(s["sync"], dict) or set(s["sync"]) != {
                "expires_game_time", "ready_game_time", "source_signature"}:
            raise ElectricalError("Unmeasured bus synchronization")
        number(s["sync"]["expires_game_time"])
        number(s["sync"]["ready_game_time"])
        if s["sync"]["ready_game_time"] > s["sync"]["expires_game_time"]:
            raise ElectricalError("Invalid bounded synchronization window")
        if not isinstance(s["sync"]["source_signature"], list):
            raise ElectricalError("Invalid synchronisation witness")
    if set(s["meter"]) != {
            "generation_kwh", "shore_import_kwh", "served_kwh",
            "unserved_kwh", "battery_discharge_kwh", "battery_charge_kwh",
            "flywheel_discharge_kwh", "flywheel_charge_kwh"}:
        raise ElectricalError("Invalid energy metering")
    for v in s["meter"].values():
        number(v)
    if not isinstance(s["last"], dict):
        raise ElectricalError("Invalid electrical readback")
    return True


def migrate_v1_electrical(existing):
    """One-way non-resetting schema migration for earlier commissioned G19."""
    if not isinstance(existing, dict):
        raise ElectricalError("Invalid historical electrical account")
    if existing.get("version") == 2:
        validate_electrical(existing)
        return copy.deepcopy(existing)
    if existing.get("version") != 1:
        raise ElectricalError("Unknown electrical ledger version")
    value = copy.deepcopy(existing)
    value["version"] = 2
    value["flywheels"] = {}
    value["meter"]["flywheel_discharge_kwh"] = 0.0
    value["meter"]["flywheel_charge_kwh"] = 0.0
    validate_electrical(value)
    return value


def survey_flywheel(ledger, name, *, capacity_kwh, charge_kwh,
                    max_charge_mw, max_discharge_mw):
    """Register one independently measured installed module; no free 250 MWh."""
    validate_electrical(ledger)
    if name not in FLYWHEELS or name in ledger["flywheels"]:
        raise ElectricalError("Unknown or previously commissioned flywheel module")
    capacity = number(capacity_kwh, positive=True)
    charge = number(charge_kwh)
    charge_rate = number(max_charge_mw, positive=True)
    discharge_rate = number(max_discharge_mw, positive=True)
    if (capacity > FLYWHEEL_NAMEPLATE_KWH + 1e-7 or charge > capacity
            or charge_rate > SHIP_CAP_MW or discharge_rate > SHIP_CAP_MW):
        raise ElectricalError("Survey exceeds fitted module's bounded design rating")
    result = copy.deepcopy(ledger)
    result["flywheels"][name] = {
        "capacity_kwh": capacity, "charge_kwh": charge,
        "initial_kwh": charge, "charged_kwh": 0.0,
        "discharged_kwh": 0.0, "max_charge_mw": charge_rate,
        "max_discharge_mw": discharge_rate, "mode": "standby",
    }
    validate_electrical(result)
    return result


def _ref(obj):
    return obj.reference if hasattr(obj, "reference") else obj


def _id(obj):
    return obj.source_id if hasattr(obj, "source_id") else obj["id"]


def _live_edge(edge, switches):
    spec = _ref(edge)
    if hasattr(edge, "setting") and edge.setting != "available":
        return False
    if hasattr(edge, "condition") and edge.condition in {
            "faulted", "failed", "severed", "jammed", "destroyed"}:
        return False
    for key in spec["isolator_ids"]:
        switch = switches.get(key)
        if switch is None:
            return False
        if hasattr(switch, "condition") and switch.condition in {
                "faulted", "failed", "severed", "jammed", "destroyed"}:
            return False
        if getattr(switch, "setting", _ref(switch).get("current_state")) != "closed":
            return False
    return True


def audit_topology(nodes, edges, switches, *, strict=True):
    """Assert exact installed electrical source, conductor and breaker graph."""
    power_nodes = { _id(n): n for n in nodes
                    if _ref(n).get("network") == "power" }
    power_edges = { _id(e): e for e in edges
                    if _ref(e).get("network") == "power" }
    power_switches = {key: s for key, s in switches.items()
                      if _ref(s).get("network") == "power"}
    if strict and (len(power_nodes), len(power_edges),
                   len(power_switches)) != EXPECTED_TOPOLOGY:
        raise ElectricalError("Installed power graph differs from the authored 438/450/466 contract")
    if len(power_nodes) != len([n for n in nodes if _ref(n).get("network") == "power"]):
        raise ElectricalError("Duplicated electrical node")
    if len(power_edges) != len([e for e in edges if _ref(e).get("network") == "power"]):
        raise ElectricalError("Duplicated electrical feeder")
    for key, edge in power_edges.items():
        spec = _ref(edge)
        if (spec["from_node"] not in power_nodes
                or spec["to_node"] not in power_nodes
                or any(k not in power_switches for k in spec["isolator_ids"])):
            raise ElectricalError("Feeder has an unknown endpoint or protection switch: " + key)
    for source in GENERATION_MW:
        if "NODE-" + source not in power_nodes or "EDGE-" + source not in power_edges:
            raise ElectricalError("Missing real generator dispatch connection")
    return power_nodes, power_edges, power_switches


def connected_nodes(edges, switches, starts, *, blocked_nodes=()):
    """Walk conducting installed edges without traversing failed bus hardware."""
    blocked = set(blocked_nodes)
    graph = defaultdict(set)
    for edge in edges:
        spec = _ref(edge)
        if spec.get("network") != "power" or not _live_edge(edge, switches):
            continue
        a, b = spec["from_node"], spec["to_node"]
        if a in blocked or b in blocked:
            continue
        graph[a].add(b)
        if spec.get("kind") in ("bridge_feeder", "cross_tie"):
            graph[b].add(a)
    reached = set(starts) - blocked
    q = deque(sorted(reached))
    while q:
        for node in sorted(graph[q.popleft()]):
            if node not in reached:
                reached.add(node)
                q.append(node)
    return reached


def source_dispatch(equipment, edges, switches, profile, *, ledger=None,
                    dt_s=10, moored=False, nodes=None):
    """Rate installed sources, genuine energised load paths and backup roles.

    The operational battery's *own* fitted feeder goes to MSB-B; it may
    support ordinary main-board loads when measured. The separate protected
    battery goes only to PWR-PROT, with no reverse traversal to any main
    switchboard. An unrated store contributes exactly zero megawatts.
    """
    if profile not in LOAD_MW:
        raise ElectricalError("Unknown authorised ship load schedule")
    dt_s = number(dt_s, positive=True)
    if dt_s > 60:
        raise ElectricalError("Electrical dispatch step is unbounded")
    if ledger is not None:
        validate_electrical(ledger)
    routes = {_id(e): e for e in edges if _ref(e).get("network") == "power"}
    # The source model's real service-node owner is authoritative for bus
    # destruction: failed panels, rotary interfaces or switchboards are
    # nonconducting *even with every copper breaker physically closed*.
    # The legacy pure-node fixtures may omit node metadata; the installed
    # Evennia adapter supplies all 438 actual power-node owners.
    blocked_nodes = set()
    if nodes is not None:
        for node in nodes:
            ref = _ref(node)
            if ref.get("network") != "power" or ref.get("owner_type") != "equipment":
                continue
            unit = equipment.get(ref.get("owner_id"))
            if (unit is None or unit.condition in {
                    "faulted", "failed", "severed", "jammed", "destroyed"}):
                blocked_nodes.add(_id(node))
    sources = {}
    for name, rating in GENERATION_MW.items():
        eq = equipment.get(name)
        feeder = routes.get("EDGE-" + name)
        if (eq is not None and eq.condition not in {
                "faulted", "failed", "severed", "jammed", "destroyed"}
                and eq.details.get("physics_online") is True
                and feeder is not None and _live_edge(feeder, switches)
                and "NODE-" + name not in blocked_nodes
                and _ref(feeder)["to_node"] not in blocked_nodes):
            sources[name] = rating
    generator_mw = min(SHIP_CAP_MW, sum(sources.values()))
    starts = ["NODE-" + x for x in sources]
    shore = ledger.get("shore") if ledger is not None else None
    shore_active = bool(shore and shore["connected"] and moored
                        and not sources
                        and equipment.get("SHORE-PWR") is not None
                        and equipment["SHORE-PWR"].condition not in {
                            "faulted", "failed", "severed", "jammed", "destroyed"}
                        and "EDGE-SHORE-PWR" in routes
                        and _live_edge(routes["EDGE-SHORE-PWR"], switches)
                       and "NODE-SHORE-PWR" not in blocked_nodes
                       and _ref(routes["EDGE-SHORE-PWR"])[
                           "to_node"] not in blocked_nodes)
    if shore_active:
        generator_mw = min(SHIP_CAP_MW, shore["rated_mw"])
        starts.append("NODE-SHORE-PWR")
    producer_nodes = connected_nodes(
        edges, switches, starts, blocked_nodes=blocked_nodes)
    op_capacity = 0.0
    flywheel_capacity = 0.0
    prot_capacity = 0.0
    op_sources, prot_sources, flywheel_sources, charge_feeders = [], [], [], []
    prot_nodes = set()
    if ledger is not None:
        for name, bank in sorted(ledger["banks"].items()):
            feeder = routes.get("EDGE-" + name)
            eq = equipment.get(name)
            if (eq is None or eq.condition in {
                        "faulted", "failed", "severed", "jammed", "destroyed"}
                    or feeder is None or not _live_edge(feeder, switches)):
                continue
            actual_target = _ref(feeder)["to_node"]
            expected_target = ("PWR-MSB-B" if name == "BAT-COMMON-OPS"
                               else "PWR-PROT")
            if actual_target != expected_target:
                raise ElectricalError("Storage is wired to a different main/protected bus")
            if ("NODE-" + name in blocked_nodes
                    or expected_target in blocked_nodes):
                continue
            if (bank["mode"] == "charge" and expected_target in producer_nodes
                    and generator_mw > 0):
                # Fitted converter is bidirectional locally, but the general
                # graph's directed protected feeds remain unchanged.
                charge_feeders.append(name)
            if bank["mode"] != "discharge" or bank["charge_kwh"] <= 0:
                continue
            max_mw = min(bank["max_discharge_mw"],
                         bank["charge_kwh"] * 3600.0 / dt_s)
            if expected_target == "PWR-MSB-B":
                op_capacity += max_mw
                op_sources.append((name, max_mw))
                starts.append("NODE-" + name)
            else:
                candidate = connected_nodes(
                    edges, switches, ["NODE-" + name],
                    blocked_nodes=blocked_nodes)
                if set(MAIN_BOARDS) & candidate:
                    raise ElectricalError("Protected battery must never reverse-feed an MSB")
                if "PWR-PROT" in candidate:
                    prot_capacity += max_mw
                    prot_sources.append((name, max_mw))
                    prot_nodes |= candidate
    # Sixty-four original F1/F2 flywheels have separately isolated modules
    # and a bank bus with an independently selected A/B incoming conductor.
    # An energy store is NOT a grid source until individually surveyed and
    # connected through its true module feeder and bank infeed. In island
    # mode these bidirectional storage modules may support their selected
    # main board; unverified paralleling with live sources is prohibited.
    if ledger is not None:
        selected_infeeds = {}
        for side in ("F1", "F2"):
            incoming = []
            for n in (1, 2):
                route = routes.get(f"EDGE-{side}-BUS-IN-{n}")
                if (route and _ref(route).get("kind") == "bank_infeed"
                        and _ref(route).get("to_node") == f"NODE-{side}-BUS"
                        and _live_edge(route, switches)):
                    incoming.append(route)
            if len(incoming) > 1:
                raise ElectricalError("Two unsynchronised flywheel bus infeed contacts closed")
            selected_infeeds[side] = incoming[0] if incoming else None
        for name, module in sorted(ledger["flywheels"].items()):
            side = name[:2]
            incoming = selected_infeeds[side]
            module_feeder = routes.get("EDGE-PWR-" + name)
            fitted = equipment.get(name)
            if (incoming is None or fitted is None
                    or fitted.condition in {
                        "faulted", "failed", "severed", "jammed", "destroyed"}
                    or module_feeder is None
                    or _ref(module_feeder).get("kind") != "module_feeder"
                    or _ref(module_feeder).get("from_node") != f"NODE-{side}-BUS"
                    or _ref(module_feeder).get("to_node") != "NODE-PWR-" + name
                    or not _live_edge(module_feeder, switches)
                    or f"NODE-{side}-BUS" in blocked_nodes
                    or "NODE-PWR-" + name in blocked_nodes):
                continue
            selected_board = _ref(incoming)["from_node"]
            if selected_board not in MAIN_BOARDS:
                raise ElectricalError("Flywheel bank feeds a foreign ship bus")
            if selected_board in blocked_nodes:
                continue
            if module["mode"] == "charge" and generator_mw > 0:
                if selected_board in producer_nodes:
                    charge_feeders.append(name)
            elif (module["mode"] == "discharge"
                  and module["charge_kwh"] > 0
                  and generator_mw <= 0 and not op_sources):
                rating = min(module["max_discharge_mw"],
                             module["charge_kwh"] * 3600.0 / dt_s)
                flywheel_capacity += rating
                flywheel_sources.append((name, rating))
                starts.append(selected_board)
    # Gross generators, an actual landed shore lead, and a directly fitted
    # operational battery are allowed main-bus sources; all share the 3.3 MW
    # rated ship dispatch envelope, not separate limitless budgets.
    main_mw = min(SHIP_CAP_MW,
                  generator_mw + op_capacity + flywheel_capacity)
    op_max_mw = min(op_capacity, max(0.0, main_mw - generator_mw))
    flywheel_max_mw = max(0.0, main_mw - generator_mw - op_max_mw)
    main_nodes = connected_nodes(
        edges, switches, starts, blocked_nodes=blocked_nodes)
    demand = LOAD_MW[profile]
    protected_need = min(demand, LOAD_MW["protected"])
    backed_mw = min(prot_capacity,
                    max(0.0, protected_need - main_mw))
    requested_main_mw = max(0.0, demand - backed_mw)
    has_protected = ("PWR-PROT" in main_nodes
                     or ("PWR-PROT" in prot_nodes and backed_mw > 0))
    # The authored reference does not allocate MW per individual device;
    # the selected load schedule therefore remains a grouped budget. But
    # commissioning a bare main bus with every downstream breaker OPEN
    # is not evidence that a single watt has reached an actual consumer.
    load_kinds = {"room_feeder", "equipment_branch", "protected_branch",
                  "protected_load", "sector_service", "drum_feeder"}
    actual_consumers = main_nodes | (prot_nodes if backed_mw else set())
    fitted_loads_exist = any(_ref(edge).get("kind") in load_kinds
                             for edge in edges if _ref(edge).get("network") == "power")
    live_consumer = (not fitted_loads_exist or any(
        _ref(edge).get("kind") in load_kinds
        and _ref(edge)["to_node"] in actual_consumers
        and _live_edge(edge, switches)
        for edge in edges if _ref(edge).get("network") == "power"))
    essential_assured = (live_consumer and
                         main_mw + backed_mw + 1e-9 >= LOAD_MW["essential"])
    assured = (live_consumer and main_mw + backed_mw + 1e-9 >= demand
               and (backed_mw <= 1e-9 or profile in {"essential", "protected"}))
    main_dispatch = min(main_mw, requested_main_mw) if live_consumer else 0.0
    gen_dispatch = min(generator_mw, main_dispatch)
    return {
        "available_mw": main_mw, "requested_mw": demand,
        "dispatched_mw": main_dispatch,
        "generation_fraction": gen_dispatch / generator_mw if generator_mw else 0.0,
        "shortfall_mw": max(0.0, demand -
                            (main_mw + backed_mw if live_consumer else 0.0)),
        "assured": assured, "essential_assured": essential_assured,
        "active_generators": tuple(sorted(sources)),
        "nodes": main_nodes | (prot_nodes if backed_mw else set()),
        "main_nodes": main_nodes,
        "main_available_mw": main_mw,
        "producer_available_mw": generator_mw,
        "operational_battery_available_mw": op_max_mw,
        "flywheel_available_mw": flywheel_max_mw,
        "flywheel_sources": flywheel_sources,
        "battery_budget_mw": op_max_mw + prot_capacity,
        "battery_dispatched_mw": max(0.0, main_dispatch - gen_dispatch) + backed_mw,
        "protected_battery_dispatched_mw": backed_mw if live_consumer else 0.0,
        "operational_battery_sources": op_sources,
        "protected_battery_sources": prot_sources,
        "battery_sources": op_sources + prot_sources,
        "charge_feeders": charge_feeders,
        "shore_active": shore_active,
        "protected_assured": has_protected and essential_assured,
        "has_live_load": live_consumer,
        "source_signature": sorted(sources) +
            (["BAT-COMMON-OPS"] if op_sources else []) +
            [name for name, _ in flywheel_sources] + [
                "MSBA:" + str("PWR-MSB-A" in main_nodes),
                "MSBB:" + str("PWR-MSB-B" in main_nodes),
                "PROT:" + str(has_protected),
            ],
    }


def step_energy(ledger, dispatch, seconds, *, actual_requested_mw=None):
    """Meter live supply under authoritative bounded ship time.

    Source-specific credits reconcile with finite storage debits. General
    main-board demand is never paid by the protected-only bank. Charging
    uses only surplus generation or shore import, not another battery.
    """
    validate_electrical(ledger)
    dt = number(seconds)
    if dt > 60:
        raise ElectricalError("Unbounded energy ledger tick")
    result = copy.deepcopy(ledger)
    demand = number(dispatch["requested_mw"] if actual_requested_mw is None
                    else actual_requested_mw)
    producing = number(dispatch["producer_available_mw"])
    ops_rating = number(dispatch["operational_battery_available_mw"])
    flywheel_rating = number(dispatch["flywheel_available_mw"])
    main = number(dispatch["main_available_mw"])
    if main > SHIP_CAP_MW + 1e-9:
        raise ElectricalError("Electrical schedule exceeds ship main bus envelope")
    live = dispatch["has_live_load"]
    protected = min(
        number(dispatch["protected_battery_dispatched_mw"]), demand) if live else 0.0
    main_served = min(main, max(0.0, demand - protected)) if live else 0.0
    generated = min(producing, main_served)
    ops_served = min(ops_rating, max(0.0, main_served - generated))
    flywheel_served = max(0.0, main_served - generated - ops_served)
    if flywheel_served > flywheel_rating + 1e-8:
        raise ElectricalError("Flywheel module power has not been rated")
    def debit_store(rows, need, source_key):
        remaining = need
        for name, maximum in rows:
            if remaining <= 1e-9:
                break
            bank = result[source_key][name]
            served = min(remaining, maximum, bank["charge_kwh"] * 3600.0 / dt) if dt else 0
            energy = served * dt / 3600.0
            bank["charge_kwh"] -= energy
            bank["discharged_kwh"] += energy
            remaining -= served
        if remaining > 1e-7:
            raise ElectricalError("Electrical stock discharged beyond measured energy")
    if dt > 0:
        debit_store(dispatch["operational_battery_sources"], ops_served, "banks")
        debit_store(dispatch["protected_battery_sources"], protected, "banks")
        debit_store(dispatch["flywheel_sources"], flywheel_served, "flywheels")
    battery_out = (ops_served + protected) * dt / 3600.0
    flywheel_out = flywheel_served * dt / 3600.0
    produced_kwh = generated * dt / 3600.0
    if dispatch["shore_active"]:
        result["shore"]["import_kwh"] += produced_kwh
        result["meter"]["shore_import_kwh"] += produced_kwh
    else:
        result["meter"]["generation_kwh"] += produced_kwh
    result["meter"]["battery_discharge_kwh"] += battery_out
    result["meter"]["flywheel_discharge_kwh"] += flywheel_out
    result["meter"]["served_kwh"] += main_served * dt / 3600 + protected * dt / 3600
    result["meter"]["unserved_kwh"] += max(
        0.0, demand - main_served - protected) * dt / 3600
    headroom = max(0.0, producing - generated)
    for name in sorted(dispatch["charge_feeders"]):
        storage = "flywheels" if name in result["flywheels"] else "banks"
        bank = result[storage][name]
        if bank["mode"] != "charge" or headroom <= 0:
            continue
        charge_rate = min(
            bank["max_charge_mw"], headroom,
            max(0.0, bank["capacity_kwh"] - bank["charge_kwh"]) * 3600 / dt
            if dt else 0.0)
        if charge_rate <= 0:
            continue
        energy = charge_rate * dt / 3600.0
        bank["charge_kwh"] += energy
        bank["charged_kwh"] += energy
        result["meter"][
            "flywheel_charge_kwh" if storage == "flywheels"
            else "battery_charge_kwh"] += energy
        if dispatch["shore_active"]:
            result["shore"]["import_kwh"] += energy
            result["meter"]["shore_import_kwh"] += energy
        else:
            result["meter"]["generation_kwh"] += energy
        headroom -= charge_rate
    result["last"] = {
        "sources": list(dispatch["active_generators"]),
        "shore": dispatch["shore_active"],
        "main_available_mw": main,
        "requested_mw": demand,
        "generator_delivered_mw": generated if not dispatch["shore_active"] else 0.0,
        "shore_delivered_mw": generated if dispatch["shore_active"] else 0.0,
        "operational_battery_delivered_mw": ops_served,
        "flywheel_delivered_mw": flywheel_served,
        "protected_battery_delivered_mw": protected,
        "battery_dispatched_mw": ops_served + protected,
        "unserved_mw": max(0.0, demand - main_served - protected),
        "protected_power": dispatch["protected_assured"],
        "main_a": "PWR-MSB-A" in dispatch["main_nodes"],
        "main_b": "PWR-MSB-B" in dispatch["main_nodes"],
        "nodes_energised": len(dispatch["nodes"]),
        "live_consumer_circuit": live,
    }
    validate_electrical(result)
    return result


def survey_battery(ledger, name, *, capacity_kwh, charge_kwh,
                   max_charge_mw, max_discharge_mw):
    """Accept separately measured finite fitted battery capacities, once."""
    validate_electrical(ledger)
    if name not in BATTERIES or name in ledger["banks"]:
        raise ElectricalError("No unmeasured fitted bank available")
    capacity = number(capacity_kwh, positive=True)
    charge = number(charge_kwh)
    inc = number(max_charge_mw, positive=True)
    out = number(max_discharge_mw, positive=True)
    if charge > capacity or inc > SHIP_CAP_MW or out > SHIP_CAP_MW:
        raise ElectricalError("Electrical storage ratings or charge physically impossible")
    result = copy.deepcopy(ledger)
    result["banks"][name] = {
        "capacity_kwh": capacity, "charge_kwh": charge,
        "initial_kwh": charge, "charged_kwh": 0.0,
        "discharged_kwh": 0.0, "max_charge_mw": inc,
        "max_discharge_mw": out, "mode": "standby",
    }
    validate_electrical(result)
    return result


def step_protection(ledger, switches, seconds):
    """Trip a real overloaded closed breaker, never automatically reclose it."""
    validate_electrical(ledger)
    dt = number(seconds)
    if dt > 10:
        raise ElectricalError("Breaker protective integration must be bounded")
    updated = copy.deepcopy(ledger)
    tripped = []
    for name, fault in sorted(updated["faults"].items()):
        switch = switches.get(name)
        if switch is None:
            raise ElectricalError("Recorded protection has no real installed breaker")
        if fault["latched"]:
            continue
        if (fault["observed_mw"] > fault["rating_mw"]
                and switch.setting == "closed"):
            fault["overload_s"] += dt
            if fault["overload_s"] >= 10:
                fault["latched"] = True
                tripped.append(name)
        else:
            fault["overload_s"] = 0.0
    validate_electrical(updated)
    return updated, tuple(tripped)


def register_fault(ledger, name, *, rating_mw, observed_mw):
    validate_electrical(ledger)
    if not isinstance(name, str) or not name.startswith("ISO-"):
        raise ElectricalError("Power fault requires a real breaker identity")
    result = copy.deepcopy(ledger)
    old = result["faults"].get(name)
    # A field measurement may report that the original fault has ended,
    # but the protective latch is historical physical state and cannot be
    # cleared by another measurement or an operator re-rating.
    if old and old["latched"]:
        if not math.isclose(number(rating_mw, positive=True),
                            old["rating_mw"], abs_tol=1e-12):
            raise ElectricalError("Protection rating cannot change under a trip")
        result["faults"][name]["observed_mw"] = number(observed_mw)
    else:
        result["faults"][name] = {
            "rating_mw": number(rating_mw, positive=True),
            "observed_mw": number(observed_mw),
            "overload_s": old["overload_s"] if old else 0.0,
            "latched": False,
        }
    validate_electrical(result)
    return result


def reset_protection(ledger, name):
    validate_electrical(ledger)
    fault = ledger["faults"].get(name)
    if not fault or not fault["latched"] or fault["observed_mw"] > fault["rating_mw"]:
        raise ElectricalError("Open breaker remains unsafe or fault not isolated")
    result = copy.deepcopy(ledger)
    del result["faults"][name]
    validate_electrical(result)
    return result
