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
        "version": 1, "banks": {}, "shore": None, "faults": {},
        "sync": None,
        "meter": {"generation_kwh": 0.0, "shore_import_kwh": 0.0,
                  "served_kwh": 0.0, "unserved_kwh": 0.0,
                  "battery_discharge_kwh": 0.0,
                  "battery_charge_kwh": 0.0},
        "last": {},
    }


def validate_electrical(s):
    if not isinstance(s, dict) or set(s) != {
            "version", "banks", "shore", "faults", "sync", "meter", "last"
    } or s["version"] != 1:
        raise ElectricalError("Unrecognised commissioned electrical ledger")
    if not isinstance(s["banks"], dict) or not set(s["banks"]) <= set(BATTERIES):
        raise ElectricalError("Fictional battery source")
    for name, bank in s["banks"].items():
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
                "expires_game_time", "source_signature"}:
            raise ElectricalError("Unmeasured bus synchronization")
        number(s["sync"]["expires_game_time"])
        if not isinstance(s["sync"]["source_signature"], list):
            raise ElectricalError("Invalid synchronisation witness")
    if set(s["meter"]) != {
            "generation_kwh", "shore_import_kwh", "served_kwh",
            "unserved_kwh", "battery_discharge_kwh", "battery_charge_kwh"}:
        raise ElectricalError("Invalid energy metering")
    for v in s["meter"].values():
        number(v)
    if not isinstance(s["last"], dict):
        raise ElectricalError("Invalid electrical readback")
    return True


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


def connected_nodes(edges, switches, starts):
    graph = defaultdict(set)
    for edge in edges:
        spec = _ref(edge)
        if spec.get("network") != "power" or not _live_edge(edge, switches):
            continue
        a, b = spec["from_node"], spec["to_node"]
        graph[a].add(b)
        if spec.get("kind") in ("bridge_feeder", "cross_tie"):
            graph[b].add(a)
    reached = set(starts)
    q = deque(sorted(reached))
    while q:
        for node in sorted(graph[q.popleft()]):
            if node not in reached:
                reached.add(node)
                q.append(node)
    return reached


def source_dispatch(equipment, edges, switches, profile, *, ledger=None,
                    dt_s=10, moored=False):
    """One bounded dispatch snapshot; optional finite shore and protected reserve.

    Batteries supply only actually reached protected loads, never the ordinary
    propulsion, refrigeration and freight budgets. No automatic load shed.
    """
    if profile not in LOAD_MW:
        raise ElectricalError("Unknown authorised ship load schedule")
    dt_s = number(dt_s, positive=True)
    if dt_s > 60:
        raise ElectricalError("Electrical dispatch step is unbounded")
    if ledger is not None:
        validate_electrical(ledger)
    routes = {_id(e): e for e in edges if _ref(e).get("network") == "power"}
    sources = {}
    for name, rating in GENERATION_MW.items():
        eq = equipment.get(name)
        feeder = routes.get("EDGE-" + name)
        if (eq is not None and eq.condition not in {
                "faulted", "failed", "severed", "jammed", "destroyed"}
                and eq.details.get("physics_online") is True
                and feeder is not None and _live_edge(feeder, switches)):
            sources[name] = rating
    main_mw = min(SHIP_CAP_MW, sum(sources.values()))
    starts = ["NODE-" + x for x in sources]
    shore = ledger.get("shore") if ledger is not None else None
    shore_active = bool(shore and shore["connected"] and moored
                       and not sources
                       and equipment.get("SHORE-PWR") is not None
                       and equipment["SHORE-PWR"].condition not in {
                           "faulted", "failed", "severed", "jammed", "destroyed"}
                       and "EDGE-SHORE-PWR" in routes
                       and _live_edge(routes["EDGE-SHORE-PWR"], switches))
    if shore_active:
        main_mw = min(SHIP_CAP_MW, shore["rated_mw"])
        starts.append("NODE-SHORE-PWR")
    reached = connected_nodes(edges, switches, starts)
    battery_nodes = set()
    qualified = []
    if ledger is not None:
        for name, bank in sorted(ledger["banks"].items()):
            feeder = routes.get("EDGE-" + name)
            eq = equipment.get(name)
            if (bank["mode"] != "discharge" or bank["charge_kwh"] <= 0
                    or eq is None or eq.condition in {
                        "faulted", "failed", "severed", "jammed", "destroyed"}
                    or feeder is None or not _live_edge(feeder, switches)):
                continue
            reachable = connected_nodes(edges, switches, ["NODE-" + name])
            if set(MAIN_BOARDS) & reachable:
                raise ElectricalError("Unrated battery reverse-backfeed reaches a main board")
            if "PWR-PROT" not in reachable:
                continue
            battery_nodes |= reachable
            max_mw = min(bank["max_discharge_mw"], bank["charge_kwh"] * 3600 / dt_s)
            qualified.append((name, max_mw))
    demand = LOAD_MW[profile]
    essential_need = min(demand, LOAD_MW["protected"])
    battery_budget = sum(rate for _, rate in qualified)
    backed_mw = min(battery_budget, max(0.0, essential_need - main_mw))
    requested_main_mw = max(0.0, demand - backed_mw)
    has_protected = "PWR-PROT" in reached or ("PWR-PROT" in battery_nodes
                                            and backed_mw > 0)
    essential_assured = (main_mw + backed_mw + 1e-9 >= LOAD_MW["essential"])
    assured = (main_mw + backed_mw + 1e-9 >= demand
               and (backed_mw == 0 or profile in {"essential", "protected"}))
    return {
        "available_mw": main_mw, "requested_mw": demand,
        "dispatched_mw": min(main_mw, requested_main_mw),
        "generation_fraction": min(1.0, requested_main_mw / main_mw) if main_mw else 0.0,
        "shortfall_mw": max(0.0, demand - main_mw - backed_mw),
        "assured": assured, "essential_assured": essential_assured,
        "active_generators": tuple(sorted(sources)),
        "nodes": reached | (battery_nodes if backed_mw else set()),
        "main_nodes": reached,
        "main_available_mw": main_mw,
        "battery_budget_mw": battery_budget,
        "battery_dispatched_mw": backed_mw,
        "battery_sources": qualified,
        "shore_active": shore_active,
        "protected_assured": has_protected and essential_assured,
        "source_signature": sorted(sources),
    }


def step_energy(ledger, dispatch, seconds, *, actual_requested_mw=None):
    """Meter one authoritative tick, without consuming an imagined fuel store."""
    validate_electrical(ledger)
    dt = number(seconds)
    if dt > 60:
        raise ElectricalError("Unbounded energy ledger tick")
    result = copy.deepcopy(ledger)
    demand = number(dispatch["requested_mw"] if actual_requested_mw is None
                    else actual_requested_mw)
    main = number(dispatch["main_available_mw"])
    borrowed = number(dispatch["battery_dispatched_mw"])
    consumed = 0.0
    for name, maximum in dispatch["battery_sources"]:
        if borrowed <= 1e-9:
            break
        bank = result["banks"][name]
        portion = min(borrowed, maximum, bank["charge_kwh"] * 3600 / dt) if dt else 0.0
        amount = portion * dt / 3600
        bank["charge_kwh"] -= amount
        bank["discharged_kwh"] += amount
        borrowed -= portion
        consumed += amount
    if borrowed > 1e-7:
        raise ElectricalError("Battery dispatch exceeded stored energy")
    main_served = min(main, max(0.0, demand - consumed * 3600 / dt)) if dt else 0.0
    result["meter"]["generation_kwh"] += (
        0 if dispatch["shore_active"] else main_served * dt / 3600)
    if dispatch["shore_active"]:
        result["shore"]["import_kwh"] += main_served * dt / 3600
        result["meter"]["shore_import_kwh"] += main_served * dt / 3600
    result["meter"]["battery_discharge_kwh"] += consumed
    result["meter"]["served_kwh"] += main_served * dt / 3600 + consumed
    result["meter"]["unserved_kwh"] += max(
        0.0, demand * dt / 3600 - main_served * dt / 3600 - consumed)
    # Charging must use real electrical generation headroom and a conducting
    # path back to the physical battery input; charging is not free energy.
    headroom = max(0.0, main - main_served)
    for name, bank in sorted(result["banks"].items()):
        if bank["mode"] != "charge" or headroom <= 0:
            continue
        maximum = min(bank["max_charge_mw"], headroom,
                      max(0.0, bank["capacity_kwh"] - bank["charge_kwh"]) * 3600 / dt)
        if maximum <= 0:
            continue
        # The caller supplies direct live generator nodes in main_nodes.
        if "NODE-" + name not in dispatch["main_nodes"]:
            continue
        amount = maximum * dt / 3600
        bank["charge_kwh"] += amount
        bank["charged_kwh"] += amount
        result["meter"]["battery_charge_kwh"] += amount
        if dispatch["shore_active"]:
            result["shore"]["import_kwh"] += amount
            result["meter"]["shore_import_kwh"] += amount
        else:
            result["meter"]["generation_kwh"] += amount
        headroom -= maximum
    result["last"] = {
        "sources": list(dispatch["active_generators"]),
        "shore": dispatch["shore_active"],
        "main_available_mw": main,
        "requested_mw": demand,
        "battery_dispatched_mw": dispatch["battery_dispatched_mw"],
        "unserved_mw": max(0.0, demand - main - dispatch["battery_dispatched_mw"]),
        "protected_power": dispatch["protected_assured"],
        "main_a": "PWR-MSB-A" in dispatch["main_nodes"],
        "main_b": "PWR-MSB-B" in dispatch["main_nodes"],
        "nodes_energised": len(dispatch["nodes"]),
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
    if old and old["latched"]:
        raise ElectricalError("A tripped breaker must be repaired/reset locally")
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
