"""World-owned G19 lead-mind electrical extension.

Installation is explicit, transactional (caller holds the continuous ship
clock), versioned and non-resetting. The source paths are the original
fitted G19 network, while the 96 new components belong to mind_power.
No handler-side assertion can energise a machine, and no nameplate adds
free kWh. The pure tick returns physical source contact transitions for
the world adapter to commit atomically.
"""
from __future__ import annotations

import copy
import math

from world.ship_mind_power import (
    MindPowerError, SOURCE_MODEL, FORBIDDEN, load_design,
    initial_reserve_ledger, proposed_world_rows, validate_reserve_ledger,
    validate_fitted_source_routes,
)

BROKEN = frozenset({"faulted", "failed", "severed", "jammed", "destroyed"})
METER_FIELDS = frozenset({
    "grid_served_kwh", "grid_charge_kwh", "reserve_served_kwh",
    "unserved_kwh",
})


def _require(condition, message):
    if not condition:
        raise MindPowerError(message)


def _finite(value, *, zero=True):
    _require(type(value) in (int, float) and math.isfinite(value)
             and (value >= 0 if zero else value > 0),
             "Invalid lead-mind power quantity")
    return float(value)


def _working(row):
    return row is not None and row.condition not in BROKEN


def _conducting_edge(rows, name, *, selected=True):
    row = rows.get("edge:" + name)
    if not _working(row):
        return False
    if selected and row.setting != "available":
        return False
    if not selected and row.setting not in {"available", "standby"}:
        return False
    for iso in row.reference.get("isolator_ids", []):
        contact = rows.get("isolator:" + iso)
        if not _working(contact) or contact.setting != "closed":
            return False
    return True


def install_mind_circuits(world_state, design, ship):
    """Fit distinct durable rows against existing G19 as-built identity.

    Call within the locked, operator-only ship-clock transaction. Partial
    installations or altered provenance raise, causing a DB rollback.
    Does not change any old G19 contact or already-installed new contact.
    """
    validate_fitted_source_routes(design, ship)
    source_rows = {}
    for section, category in (("service_nodes", "node"),
                              ("service_edges", "edge"),
                              ("isolation_points", "isolator")):
        source_rows.update({category + ":" + x["id"]: x
                            for x in ship[section] if x["network"] == "power"})
    required = set()
    for island in design["islands"]:
        for feed in island["inputs"]:
            required.add("node:" + feed["tap_node"])
            for token in feed["route_domains"]:
                category = ("edge" if token.startswith("EDGE-") else
                            "isolator" if token.startswith("ISO-") else
                            "node" if token.startswith(("NODE-", "PWR-")) else None)
                if category:
                    required.add(category + ":" + token)
    current = {row.key: row for row in
               world_state.objects.filter(key__in=sorted(required))}
    _require(set(current) == required, "G19 source feeder or switch not fitted")
    for key in sorted(required):
        record, existing = source_rows.get(key), current[key]
        _require(record is not None and existing.reference == record,
                 "Canonical G19 source route has been replaced: " + key)
    intended = proposed_world_rows(design)
    created = 0
    for key, entry in sorted(intended.items()):
        row, added = world_state.objects.get_or_create(key=key, defaults=entry)
        if not added:
            _require(row.source_model == SOURCE_MODEL
                     and row.category == entry["category"]
                     and row.source_id == entry["source_id"]
                     and row.space_id == entry["space_id"]
                     and row.reference == entry["reference"],
                     "Previously fitted lead-mind power identity drift: " + key)
        created += int(added)
    return {"created": created, "total": len(intended),
            "machines": 9, "islands": 5}


def initial_mind_runtime(design):
    return {"version": 1, "reserve": initial_reserve_ledger(design),
            "pending": {},
            "meter": {key: 0.0 for key in METER_FIELDS},
            "last": {}}


def validate_mind_runtime(design, account):
    _require(isinstance(account, dict) and set(account) == {
        "version", "reserve", "pending", "meter", "last"}
        and account["version"] == 1, "Unrecognised lead-mind clock account")
    validate_reserve_ledger(design, account["reserve"])
    ids = {island["id"] for island in design["islands"]}
    _require(isinstance(account["pending"], dict)
             and set(account["pending"]) <= ids, "Nonexistent transfer controller")
    for pending in account["pending"].values():
        _require(isinstance(pending, dict)
                 and set(pending) == {"to", "elapsed_s"}
                 and pending["to"] in {"A", "B"}
                 and 0 <= _finite(pending["elapsed_s"])
                 < design["transfer_seconds"] + 1e-9,
                 "Corrupt transfer controller state")
    _require(isinstance(account["meter"], dict)
             and set(account["meter"]) == METER_FIELDS
             and isinstance(account["last"], dict),
             "Invalid lead-mind metering fields")
    for value in account["meter"].values():
        _finite(value)
    _require(math.isclose(
        account["reserve"]["meter"]["delivered_kwh"],
        account["meter"]["reserve_served_kwh"],
        rel_tol=1e-10, abs_tol=1e-8), "Island backup meter and clock disagree")
    return True


def _existing_source_usable(feed, rows, g19_nodes):
    if feed["tap_node"] not in g19_nodes:
        return False
    for item in feed["route_domains"]:
        if item in FORBIDDEN:
            return False
        if item.startswith("EDGE-"):
            if not _conducting_edge(rows, item):
                return False
        elif item.startswith("ISO-"):
            contact = rows.get("isolator:" + item)
            if not _working(contact) or contact.setting != "closed":
                return False
        elif item.startswith(("NODE-", "PWR-")):
            node = rows.get("node:" + item)
            if not _working(node):
                return False
            owner = node.reference.get("owner_id")
            if owner and not _working(rows.get("equipment:" + owner)):
                return False
    return True


def _input_usable(feed, rows, g19_nodes):
    return bool(_existing_source_usable(feed, rows, g19_nodes)
                and _conducting_edge(rows, feed["edge"], selected=False))


def _machine_usable(machine, rows):
    equipment = rows.get("equipment:" + machine["id"])
    return bool(_working(equipment)
                and _working(rows.get("node:" + machine["terminal_node"]))
                and _conducting_edge(rows, machine["feeder"]))


def _reserve_usable(island, rows, account):
    reserve = island["local_reserve"]
    bank = account["reserve"]["units"][reserve["id"]]
    return bool(bank["surveyed"] and _working(rows.get("equipment:" + reserve["id"]))
                and _conducting_edge(rows, "EDGE-" + reserve["id"])
                and bank["charge_kwh"] > 0)


def _charger_usable(island, rows, account):
    reserve = island["local_reserve"]
    bank = account["reserve"]["units"][reserve["id"]]
    return bool(bank["surveyed"] and _working(rows.get("equipment:" + reserve["id"]))
                and _conducting_edge(rows, "EDGE-CHARGE-" + reserve["id"]))


def tick_mind_power(design, account, *, rows, g19_power, seconds):
    """Step local sources, measured reserve use and bounded grid load.

    `g19_power` must be the authoritative source_dispatch result from the
    same G19 ship tick. Grid service and charging are budgets, NOT credits:
    caller must add returned MW to step_energy, with charge MW included in
    external_charge_mw. A missing source node, breaker or actual supply fails
    closed. Transfer is break-before-make and consumes the entire current
    bounded tick on the old source/backup, switching at its end.
    """
    validate_mind_runtime(design, account)
    dt = _finite(seconds, zero=False)
    _require(dt <= 10.0, "Mind transfer must advance in bounded 10-second steps")
    expected = proposed_world_rows(design)
    for key, spec in expected.items():
        row = rows.get(key)
        _require(row is not None and row.source_model == SOURCE_MODEL
                 and row.category == spec["category"]
                 and row.space_id == spec["space_id"]
                 and row.reference == spec["reference"],
                 "Missing, altered or uncommissioned mind-power world row: " + key)

    _require(isinstance(g19_power, dict)
             and isinstance(g19_power.get("nodes"), (set, frozenset))
             and "main_available_mw" in g19_power
             and "producer_available_mw" in g19_power
             and "requested_mw" in g19_power, "Missing G19 source dispatch")
    available_kw = max(0.0, 1000 * (
        _finite(g19_power["main_available_mw"])
        - _finite(g19_power["requested_mw"])))
    # Only online generators / actual landed shore can recharge storage.
    producing_kw = max(0.0, 1000 * (
        _finite(g19_power["producer_available_mw"])
        - _finite(g19_power["requested_mw"])))
    new = copy.deepcopy(account)
    changed_contacts = []
    online = []
    offline = []
    grid_kw = 0.0
    charge_kw = 0.0
    grid_nodes = set(g19_power["nodes"])
    for island in design["islands"]:
        iid = island["id"]
        feeds = {x["source"]: x for x in island["inputs"]}
        selected = [src for src, feed in feeds.items()
                    if rows["edge:" + feed["edge"]].setting == "available"]
        _require(len(selected) == 1, "Infeed selection must be break-before-make")
        source = selected[0]
        other = "B" if source == "A" else "A"
        converter = rows["equipment:" + island["converter"]]
        bus = rows["node:" + island["distribution_node"]]
        healthy = _working(converter) and _working(bus)
        active_ready = bool(healthy and _input_usable(feeds[source], rows, grid_nodes))
        alternative_ready = bool(healthy and _input_usable(feeds[other], rows, grid_nodes))
        pending = new["pending"].get(iid)
        if active_ready:
            new["pending"].pop(iid, None)
            pending = None
        elif alternative_ready:
            if pending is None or pending["to"] != other:
                pending = {"to": other, "elapsed_s": 0.0}
            pending["elapsed_s"] += dt
            if pending["elapsed_s"] >= design["transfer_seconds"] - 1e-9:
                changed_contacts.append((feeds[source]["edge"], feeds[other]["edge"]))
                new["pending"].pop(iid, None)
            else:
                new["pending"][iid] = pending
        else:
            new["pending"].pop(iid, None)
        # A source change does not bypass the local reserve *during* this
        # step; grid power from the new input begins on the next ship tick.
        transfer_active = (not active_ready and alternative_ready)
        active_machines = [m for m in island["machines"]
                           if healthy and _machine_usable(m, rows)]
        demand_kw = sum(m["load_kw"] for m in active_machines)
        should_grid = bool(active_ready and demand_kw <= available_kw + 1e-9)
        bank = new["reserve"]["units"][island["local_reserve"]["id"]]
        grid_served_kw = demand_kw if should_grid else 0.0
        if should_grid:
            available_kw -= grid_served_kw
            grid_kw += grid_served_kw
        powered = False
        if should_grid:
            powered = True
        elif demand_kw and _reserve_usable(island, rows, new):
            required = demand_kw * dt / 3600.0
            delivered = min(required, bank["charge_kwh"],
                            island["local_reserve"]["max_discharge_kw"] * dt / 3600.0)
            bank["charge_kwh"] -= delivered
            bank["discharged_kwh"] += delivered
            new["reserve"]["meter"]["delivered_kwh"] += delivered
            new["meter"]["reserve_served_kwh"] += delivered
            powered = math.isclose(delivered, required, abs_tol=1e-10, rel_tol=1e-10)
            new["reserve"]["meter"]["unserved_kwh"] += max(0.0, required - delivered)
        if demand_kw and not powered:
            # Partial reserve delivery is not a fabricated online machine.
            partial = 0.0 if should_grid else (
                min(demand_kw * dt / 3600, account["reserve"]["units"][
                    island["local_reserve"]["id"]]["charge_kwh"])
                if _reserve_usable(island, rows, account) else 0.0)
            new["meter"]["unserved_kwh"] += max(0.0, demand_kw * dt / 3600 - partial)
        if powered:
            online.extend(m["id"] for m in active_machines)
        else:
            offline.extend(m["id"] for m in active_machines)
        offline.extend(m["id"] for m in island["machines"] if m not in active_machines)
        # An actual live selected feeder and metered generator surplus
        # may charge this island's *surveyed* store through its own breaker.
        if active_ready and _charger_usable(island, rows, new):
            limit = min(island["local_reserve"]["max_charge_kw"],
                        available_kw, producing_kw,
                        max(0.0, (bank["capacity_kwh"] - bank["charge_kwh"])
                            * 3600.0 / dt))
            if limit > 0:
                amount = limit * dt / 3600.0
                bank["charge_kwh"] += amount
                bank["charged_kwh"] += amount
                available_kw -= limit
                producing_kw -= limit
                charge_kw += limit

    kwh = dt / 3600.0
    new["meter"]["grid_served_kwh"] += grid_kw * kwh
    new["meter"]["grid_charge_kwh"] += charge_kw * kwh
    # Reserve charge is already included in per-bank conservation identity.
    new["last"] = {
        "seconds": dt, "powered": sorted(online), "unpowered": sorted(offline),
        "grid_served_mw": grid_kw / 1000.0,
        "grid_charge_mw": charge_kw / 1000.0,
        "transfers_completed": [[a, b] for a, b in changed_contacts],
    }
    validate_mind_runtime(design, new)
    return new, tuple(changed_contacts)
