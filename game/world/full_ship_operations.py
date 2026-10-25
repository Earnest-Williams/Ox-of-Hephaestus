"""G17 full-ship operational state: explicit import, never an implicit reset.

The 0.5 design is not runtime truth until installed. After installation the
database owns condition, valve settings, inventory and access. No AI/handler
is granted direct database access. Methods in this module are server-side
operations; exposing any of them to characters requires a separate permission,
locality, suit/pressure and receipt gate.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict, deque
from pathlib import Path

from django.db import transaction
from evennia.utils import gametime

from world.models import CanonicalShipEvent, CanonicalShipState
from world.ship_world import find_ship_space

MODEL = "0.5-candidate"
CATEGORIES = {
    "equipment": "equipment",
    "access_links": "access",
    "service_nodes": "node",
    "service_edges": "edge",
    "isolation_points": "isolator",
    "inventories": "inventory",
}
_ALLOWED_ISOLATOR = {"open", "closed"}
_ALLOWED_ACCESS = {"open", "closed", "closed_or_auto"}
_BROKEN = {"faulted", "failed", "destroyed", "severed", "jammed"}
_ENABLED = {"open", "available", "standby", "closed_or_auto"}


class ShipOperationsError(ValueError):
    pass


def candidate_path() -> Path:
    return Path(__file__).resolve().parents[2] / "design/ship/ox_full_ship_v0.5_candidate.json"


def load_candidate(path=None):
    payload = json.loads(Path(path or candidate_path()).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "ox.ship-world/0.1" or payload.get("model_version") != MODEL:
        raise ShipOperationsError("Unsupported candidate model")
    if payload.get("status") != "DESIGN_CANDIDATE_NOT_RUNTIME_AUTHORITY":
        raise ShipOperationsError("Unreviewed candidate status")
    seen = {}
    spaces = {s["id"] for s in payload["spaces"]}
    for section in CATEGORIES:
        rows = payload.get(section)
        if not isinstance(rows, list):
            raise ShipOperationsError(f"Missing {section}")
        index = {}
        for row in rows:
            key = row.get("id")
            if not isinstance(key, str) or not key or key in index:
                raise ShipOperationsError(f"Duplicate/invalid {section} identity")
            index[key] = row
        seen[section] = index
    if len(spaces) != 421 or len(seen["access_links"]) != 517 or len(seen["equipment"]) != 808:
        raise ShipOperationsError("Unreviewed topology or equipment counts")
    if len(seen["isolation_points"]) != 1256:
        raise ShipOperationsError("Unreviewed isolation counts")
    for row in payload["access_links"]:
        if row["from"] not in spaces or row["to"] not in spaces:
            raise ShipOperationsError(f"Broken access {row['id']}")
    for row in payload["equipment"]:
        if row["space_id"] not in spaces:
            raise ShipOperationsError(f"Broken equipment location {row['id']}")
    for row in payload["service_edges"]:
        if row["from_node"] not in seen["service_nodes"] or row["to_node"] not in seen["service_nodes"]:
            raise ShipOperationsError(f"Broken service edge {row['id']}")
        if any(x not in seen["isolation_points"] for x in row["isolator_ids"]):
            raise ShipOperationsError(f"Broken service isolator {row['id']}")
    return payload


def _key(category, identifier):
    if category not in CATEGORIES.values() or not isinstance(identifier, str):
        raise ShipOperationsError("Invalid component identity")
    return f"{category}:{identifier}"


def state(category, identifier, *, lock=False):
    qs = CanonicalShipState.objects
    if lock:
        qs = qs.select_for_update()
    try:
        return qs.get(pk=_key(category, identifier))
    except CanonicalShipState.DoesNotExist as exc:
        raise ShipOperationsError("Component not installed") from exc


def _seed(section, row):
    category = CATEGORIES[section]
    location = (row.get("space_id") or
                (row.get("location_ids") or [None])[0] or
                (row.get("route_spaces") or [None])[0])
    condition = row.get("current_condition") or "serviceable"
    setting = (row.get("current_state") if category == "isolator" else
               row.get("normal_state") if category in {"access", "edge"} else
               "unverified")
    # Inventories are total ship holdings: allocations are metadata, NOT extra stock.
    quantity = row.get("nominal_mass_t") if category == "inventory" else None
    if quantity is not None and (not math.isfinite(float(quantity)) or quantity < 0):
        raise ShipOperationsError("Invalid inventory")
    return CanonicalShipState(
        key=_key(category, row["id"]), category=category, source_id=row["id"],
        source_model=MODEL, space_id=location, condition=condition,
        setting=setting, quantity=quantity, reference=row, details={},
    )


@transaction.atomic
def install_candidate(*, operator_approved=False, path=None):
    """Explicit one-time install. Existing rows are never overwritten.

    Requires canonical topology; avoids making v0.5 secretly authoritative.
    """
    if not operator_approved:
        raise PermissionError("Explicit operator approval required")
    payload = load_candidate(path)
    if find_ship_space("CMD-PRIMARY") is None:
        raise ShipOperationsError("Install canonical world topology first")
    # Prevent concurrent installers on PostgreSQL with a shared model anchor.
    anchor, created = CanonicalShipState.objects.get_or_create(
        key="meta:installation",
        defaults=dict(category="meta", source_id="installation",
                      source_model=MODEL, condition="installing",
                      reference={"model_version": MODEL}),
    )
    anchor = CanonicalShipState.objects.select_for_update().get(pk=anchor.pk)
    if anchor.condition == "installed":
        if anchor.source_model != MODEL:
            raise ShipOperationsError("Installed world model mismatch")
        return {"installed": False, "counts": anchor.details["counts"]}
    if not created:
        raise ShipOperationsError("Partial or competing installation; refuse overwrite")
    counts = {}
    for section, category in CATEGORIES.items():
        rows = [_seed(section, row) for row in payload[section]]
        CanonicalShipState.objects.bulk_create(rows, batch_size=250)
        counts[category] = len(rows)
    anchor.condition = "installed"
    anchor.details = {"counts": counts}
    anchor.save(update_fields=["condition", "details"])
    return {"installed": True, "counts": counts}


def _require_installed():
    anchor = CanonicalShipState.objects.filter(pk="meta:installation", condition="installed").first()
    if anchor is None:
        raise ShipOperationsError("Full ship not installed")


def _snapshot(component):
    return {"condition": component.condition, "setting": component.setting,
            "quantity": component.quantity, "revision": component.revision}


def _record(component, operation, before, actor=None, request_id=None):
    CanonicalShipEvent.objects.create(
        component_key=component.key, operation=operation,
        before=before, after=_snapshot(component),
        actor_dbref=getattr(actor, "dbref", None), request_id=request_id,
        game_time=float(gametime.gametime(absolute=True)),
    )


@transaction.atomic
def set_component_condition(category, identifier, new_condition, *, operator=False):
    """Fault injection is operator-only; repairs use a separate work gate."""
    if not operator:
        raise PermissionError("Fault injection is operator-only")
    if new_condition not in {"serviceable", "degraded", "faulted", "failed", "jammed", "severed"}:
        raise ShipOperationsError("Unknown condition")
    _require_installed()
    item = state(category, identifier, lock=True)
    if item.category not in {"equipment", "edge", "isolator", "access"}:
        raise ShipOperationsError("Component cannot accept physical fault")
    before = _snapshot(item)
    if item.condition == new_condition:
        return before
    item.condition = new_condition
    item.revision += 1
    item.save(update_fields=["condition", "revision"])
    _record(item, "operator_fault", before)
    return _snapshot(item)


@transaction.atomic
def set_isolator(identifier, setting, *, actor=None, operator=False):
    _require_installed()
    if setting not in _ALLOWED_ISOLATOR:
        raise ShipOperationsError("Expected open or closed")
    iso = state("isolator", identifier, lock=True)
    if iso.condition in _BROKEN:
        raise ShipOperationsError("Faulted isolator cannot be actuated")
    if not operator:
        if actor is None or getattr(actor, "location", None) is None:
            raise PermissionError("Local authenticated character required")
        if getattr(actor.location.db, "ox_space_id", None) != iso.space_id:
            raise PermissionError("Character not physically at isolator")
        if not iso.reference.get("manual_operation"):
            raise PermissionError("No local manual control")
        if not (actor.db.crew_role in {"watch_engineer", "chief_engineer", "environment_tech"}
                or actor.check_permstring("Developer")):
            raise PermissionError("Engineering qualifications required")
    before = _snapshot(iso)
    if iso.setting == setting:
        return before
    iso.setting = setting
    iso.revision += 1
    iso.save(update_fields=["setting", "revision"])
    _record(iso, "set_isolator", before, actor)
    return _snapshot(iso)


@transaction.atomic
def consume_stock(identifier, amount_t, *, operator=False):
    """Finite mass accounting. Player-facing transfers need a separate gate."""
    if not operator:
        raise PermissionError("Inventory operations require authorised work gateway")
    if not isinstance(amount_t, (int, float)) or isinstance(amount_t, bool):
        raise ShipOperationsError("Invalid mass")
    if not math.isfinite(amount_t) or amount_t <= 0:
        raise ShipOperationsError("Invalid mass")
    _require_installed()
    item = state("inventory", identifier, lock=True)
    before = _snapshot(item)
    if item.quantity is None or item.quantity + 1e-9 < amount_t:
        raise ShipOperationsError("Insufficient physical stock")
    item.quantity = max(0.0, item.quantity - amount_t)
    item.revision += 1
    item.save(update_fields=["quantity", "revision"])
    _record(item, "consume_stock", before)
    return _snapshot(item)


def _conducts(iso):
    # Both breaker and fluid valves conduct in their OPEN position.
    return iso.condition not in _BROKEN and iso.setting == "open"


def service_reachable(network, source_node):
    """Physical graph reachability, not proof of delivered capacity or flow.

    A closed or damaged isolator blocks its edge. Standby/closed service edges
    do not silently conduct. Sources and sinks are not invented.
    """
    _require_installed()
    nodes = {x.source_id for x in CanonicalShipState.objects.filter(category="node")
             if x.reference.get("network") == network}
    if source_node not in nodes:
        raise ShipOperationsError("Unknown source node in network")
    iso = {x.source_id: x for x in CanonicalShipState.objects.filter(category="isolator")}
    adj = defaultdict(list)
    for edge in CanonicalShipState.objects.filter(category="edge"):
        spec = edge.reference
        if spec["network"] != network or edge.condition in _BROKEN:
            continue
        if edge.setting not in {"available"}:
            continue
        if not all(_conducts(iso[i]) for i in spec["isolator_ids"]):
            continue
        a, b = spec["from_node"], spec["to_node"]
        adj[a].append(b)
        # Service edges are not assumed bidirectional: check return routes.
    seen = {source_node}
    pending = deque([source_node])
    while pending:
        for other in adj[pending.popleft()]:
            if other not in seen:
                seen.add(other)
                pending.append(other)
    return seen


def access_clearance(identifier, *, suited=False):
    """Conservative structural/environmental gate. No automatic movement.

    Unknown environment and vacuum always require a suit; positive differential
    cannot be overridden by a generic 'open' door state. Equalisation and suit
    integrity must be proved through later dedicated life-support operations.
    """
    _require_installed()
    door = state("access", identifier)
    spec = door.reference
    if door.condition in _BROKEN or door.setting not in {"open"}:
        return False, "access_not_open"
    from_room = find_ship_space(spec["from"])
    to_room = find_ship_space(spec["to"])
    if from_room is None or to_room is None:
        return False, "unknown_location"
    a = (from_room.db.ox_static or {}).get("pressure_zone")
    b = (to_room.db.ox_static or {}).get("pressure_zone")
    if a in (None, "VACUUM") or b in (None, "VACUUM"):
        return False, "unverified_environment" if not suited else "eva_interlock_not_integrated"
    if a != b and spec.get("pressure_boundary"):
        return False, "equalization_not_verified"
    return True, "clear"


def summary():
    _require_installed()
    result = defaultdict(int)
    for item in CanonicalShipState.objects.all().values("category", "condition", "setting"):
        result[item["category"]] += 1
        if item["condition"] in _BROKEN:
            result["faulted"] += 1
    return dict(result)
