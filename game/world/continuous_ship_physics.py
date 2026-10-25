"""G18 opt-in, authoritative continuous physics over the installed v0.5 ship.

One transaction advances a bounded interval of *game time*. The installed
CanonicalShipState rows, not this module or an LLM, own physical truth.
Reference geometry is read only for existing network and pressure-zone IDs.
This is a coarse causal freighter simulation, not a CFD/spacecraft solver.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict, deque
from functools import lru_cache

from django.db import transaction
from evennia.scripts.scripts import DefaultScript
from evennia.utils import gametime

from world.full_ship_operations import (
    MODEL, R_SPECIFIC_AIR, ShipOperationsError, _BROKEN, _conducts,
    _require_installed, load_candidate, state,
)
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_cargo_manifest import (
    CargoError, DRUMS as CARGO_DRUMS, initial_cargo, validate_cargo,
    onboard_mass_kg, declare_cargo_lot, split_cargo_lot, verify_drum,
    drum_balance, start_freight_transfer, step_freight,
    active_freight_mw,
)
from world.ship_motion_machinery import (
    DRUMS, ROTORS, RotorError, initial_rotors, set_rotor_command,
    step_rotors, motion_power_mw, rotor_gravity,
)

CLOCK_KEY = "meta:continuous-physics"
SCRIPT_KEY = "OxContinuousShipPhysics"
STEP_SECONDS = 10.0
MAX_ADVANCE_SECONDS = 60.0
GENERATION_MW = {"GEN-M": 3.0, "GEN-A": 0.65, "GEN-B": 0.65}
GENERATOR_NODES = {k: "NODE-" + k for k in GENERATION_MW}
PLANTS = {
    **{k: v for k, v in (("GEN-M", True), ("GEN-A", False), ("GEN-B", True))},
    "ECLSS-A": True, "ECLSS-B": True, "LT-PLANT": True,
    "RAD-LT-1": True, "RAD-LT-2": True,
    "RAD-LT-3": True, "RAD-LT-4": True,
    "FIRE-PUMP-FWD": True, "FIRE-PUMP-AFT": True,
}
LOAD_PROFILES_MW = {"essential": 0.65, "protected": 0.75,
                    "normal": 1.35, "demanding": 2.60}
AUTHORISED_ROLES = {"watch_engineer", "chief_engineer", "environment_tech"}
CP_GAS_KJ_KG_K = 1.0
O2_PER_FUEL = 2.667
FIRE_HEAT_KJ_KG = 20000.0
# Nominal combined chemical capture capacity is finite; spent sorbent must
# eventually be serviced. This does not regenerate oxygen or vent CO2 away.
CO2_CAPTURE_CAPACITY_KG = 150.0
CO2_CAPTURE_KG_S_PER_TRAIN = 0.004
# Gameplay-calibrated ship dynamics: inertial motion in a local reference
# frame, finite reaction mass, and a power-limited drive. Not a flight solver.
# Masses are commissioned from the installed v0.5 mission mass contract,
# never from an arbitrary light-spacecraft stand-in.
DRIVE_THRUST_N = 360_000.0
DRIVE_EXHAUST_M_S = 18_000.0
# Sublight reaction drive gets thrust energy from its distinct fictional drive
# plant. These megawatts are ONLY shipboard pumps, valves and control loads,
# never the hundreds of MW/GW of actual plume kinetic energy.
DRIVE_AUX_MW = 0.12
DRIVE_HEAT_KW = 2500.0
DRIVE_COOLING_KW = 1800.0
DRIVE_THERMAL_BUFFER_KJ = 150_000_000.0
DRIVE_THERMAL_RESET_KJ = 60_000_000.0
# Cargo manifests may supply a nonnegative installed payload mass. This
# explicit mass belongs to the ship motion ledger, never an LLM estimate.
# Cargo reference is 900,000 tonnes, not an 8,000-tonne proxy.
# The persistent commissioned manifest is the actual upper bound.
HELM_DIRECTIONS = {
    "x+": (1.0, 0.0, 0.0), "x-": (-1.0, 0.0, 0.0),
    "y+": (0.0, 1.0, 0.0), "y-": (0.0, -1.0, 0.0),
    "z+": (0.0, 0.0, 1.0), "z-": (0.0, 0.0, -1.0),
    "coast": (0.0, 0.0, 0.0),
}
ATTITUDE_COMMANDS = {
    "pitch+": (1.0, 0.0, 0.0), "pitch-": (-1.0, 0.0, 0.0),
    "yaw+": (0.0, 1.0, 0.0), "yaw-": (0.0, -1.0, 0.0),
    "roll+": (0.0, 0.0, 1.0), "roll-": (0.0, 0.0, -1.0),
    "hold": (0.0, 0.0, 0.0),
}
ATTITUDE_TORQUE_NM = 180_000.0
ATTITUDE_INERTIA_KG_M2 = 2.4e11
ATTITUDE_PROPELLANT_KG_S = 0.08


def _advance_motion(motion, dt, power, *, drive_operational=True, rcs_operational=True):
    """Finite-mass velocity-Verlet-like constant-thrust step in inertial axes."""
    result = dict(motion)
    position = list(result["position_m"])
    velocity = list(result["velocity_m_s"])
    fuel = float(result["propellant_kg"])
    cargo = float(result["cargo_mass_kg"])
    dry = float(result["dry_mass_kg"])
    ftl = float(result["ftl_fuel_kg"])
    fluids = float(result["mission_fluids_kg"])
    capacity = float(result["cargo_capacity_kg"])
    direction = HELM_DIRECTIONS[result["command"]]
    # Body-frame thrust must follow the vessel's orientation.
    if (len(result["attitude_rad"]) != 3
            or not all(math.isfinite(x) for x in result["attitude_rad"])):
        raise PhysicsError("Invalid ship attitude")
    pitch, yaw, roll = result["attitude_rad"]
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cr, sr = math.cos(roll), math.sin(roll)
    bx, by, bz = direction
    rx, ry, rz = bx, cr * by - sr * bz, sr * by + cr * bz
    px, py, pz = cp * rx + sp * rz, ry, -sp * rx + cp * rz
    direction = (cy * px - sy * py, sy * px + cy * py, pz)
    attitude_direction = ATTITUDE_COMMANDS[result["attitude_command"]]
    if len(position) != 3 or len(velocity) != 3 or not all(
            math.isfinite(x) for x in (*position, *velocity, fuel)) or fuel < 0 or not all(math.isfinite(x) and x >= 0 for x in
                (cargo, dry, ftl, fluids, capacity))
            or not 0 <= cargo <= capacity or dry <= 0:
        raise PhysicsError("Invalid ship motion or propellant state")
    # Drive energy is separate fictional machinery. Ship power supplies only
    # the real auxiliary electrical demand for valves and engine controls.
    powered = (power["assured"] and
               power["available_mw"] - power["requested_mw"] >= DRIVE_AUX_MW)
    burn_time = min(dt, fuel * DRIVE_EXHAUST_M_S / DRIVE_THRUST_N) if (
        powered and drive_operational and any(direction)) else 0.0
    spent = burn_time * DRIVE_THRUST_N / DRIVE_EXHAUST_M_S
    acceleration = DRIVE_THRUST_N / (dry + cargo + ftl + fluids + fuel - spent / 2) if spent else 0.0
    for axis in range(3):
        a = acceleration * direction[axis]
        position[axis] += velocity[axis] * dt + a * burn_time * (dt - burn_time / 2)
        velocity[axis] += a * burn_time
    angles = list(result["attitude_rad"])
    angular_velocity = list(result["angular_velocity_rad_s"])
    if len(angles) != 3 or len(angular_velocity) != 3 or not all(
            math.isfinite(x) for x in (*angles, *angular_velocity)):
        raise PhysicsError("Invalid attitude state")
    attitude_burn = min(dt, max(0.0, fuel - spent) / ATTITUDE_PROPELLANT_KG_S) if (
        power["essential_assured"] and rcs_operational and any(attitude_direction)) else 0.0
    attitude_spent = attitude_burn * ATTITUDE_PROPELLANT_KG_S
    for axis in range(3):
        a = ATTITUDE_TORQUE_NM / ATTITUDE_INERTIA_KG_M2 * attitude_direction[axis]
        angles[axis] += angular_velocity[axis] * dt + a * attitude_burn * (dt - attitude_burn / 2)
        angular_velocity[axis] += a * attitude_burn
    result["attitude_rad"] = angles
    result["angular_velocity_rad_s"] = angular_velocity
    result["propellant_kg"] = max(0.0, fuel - spent - attitude_spent)
    result["expended_propellant_kg"] += attitude_spent
    result["attitude_firing"] = attitude_burn > 0
    result["position_m"] = position
    result["velocity_m_s"] = velocity
    result["expended_propellant_kg"] += spent
    result["drive_firing"] = burn_time > 0
    result["drive_power_mw"] = DRIVE_AUX_MW if burn_time > 0 else 0.0
    return result
# Coarse installed machinery waste-heat loads (kW), deposited in the
# equipment's real pressure zone. They require an actually running plant;
# a disconnected or shut-down unit cannot heat its compartment indefinitely.
# These are gameplay reference loads, not qualified manufacturer data.
PLANT_WASTE_HEAT_KW = {
    "GEN-M": 75.0, "GEN-A": 16.0, "GEN-B": 16.0,
    "ECLSS-A": 8.0, "ECLSS-B": 8.0,
    "LT-PLANT": 12.0,
    "FIRE-PUMP-FWD": 6.0, "FIRE-PUMP-AFT": 6.0,
}


class PhysicsError(ShipOperationsError):
    """Unsafe or invalid physical operation."""


def _positive(value, *, zero=False, maximum=None):
    if (isinstance(value, bool) or not isinstance(value, (float, int))
            or not math.isfinite(value) or value < 0 or (value == 0 and not zero)
            or (maximum is not None and value > maximum)):
        raise PhysicsError("Nonphysical or out-of-range quantity")
    return float(value)


@lru_cache(maxsize=1)
def _topology():
    """Installed model's immutable zone mapping; never runtime switch truth."""
    ref = load_candidate()
    zones = {s["id"]: s.get("pressure_zone") for s in ref["spaces"]}
    owners = {e["id"]: zones.get(e["space_id"]) for e in ref["equipment"]}
    node_zones = {}
    for node in ref["service_nodes"]:
        node_zones[node["id"]] = (
            zones.get(node["owner_id"]) if node["owner_type"] == "space"
            else owners.get(node["owner_id"]))
    return zones, owners, node_zones


def _clock(lock=False):
    qs = CanonicalShipState.objects
    if lock:
        qs = qs.select_for_update()
    try:
        clock = qs.get(pk=CLOCK_KEY)
    except CanonicalShipState.DoesNotExist as exc:
        raise PhysicsError("Continuous physics is not operator-armed") from exc
    if clock.condition != "armed" or clock.source_model != MODEL:
        raise PhysicsError("Physics epoch is not valid")
    return clock


def _now(value):
    return _positive(float(gametime.gametime(absolute=True)) if value is None
                     else value, zero=True)


def _snapshot(item):
    result = {"condition": item.condition, "setting": item.setting,
              "quantity": item.quantity, "revision": item.revision,
              "temperature_k": item.details.get("temperature_k"),
              "physics": {k: v for k, v in item.details.items()
                          if k.startswith("physics_")}}
    # Retain independently auditable machinery transitions in world events.
    # Earlier clock snapshots omitted motion and made a successfully
    # receipted helm/rotor operation indistinguishable from a no-op.
    if item.key == CLOCK_KEY:
        result["motion"] = item.details.get("motion")
        result["rotors"] = item.details.get("rotors")
        cargo = item.details.get("cargo")
        if cargo:
            # Preserve full integrity evidence but do not copy up to 2,048
            # manifest lots into every ten-second journal event.
            encoded = json.dumps(cargo, sort_keys=True, separators=(",", ":"))
            result["cargo"] = {
                "manifest_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                "unlocated_onboard_kg": cargo["unlocated_onboard_kg"],
                "lot_count": len(cargo["lots"]),
                "jobs": cargo["jobs"],
                "verified_drums": cargo["verified_drums"],
            }
    return result


def _event(item, operation, before, *, actor=None, request_id=None):
    return CanonicalShipEvent.objects.create(
        component_key=item.key, operation=operation,
        before=before, after=_snapshot(item),
        actor_dbref=getattr(actor, "dbref", None), request_id=request_id,
        game_time=float(gametime.gametime(absolute=True)),
    )


@transaction.atomic
def arm_continuous_physics(*, operator_approved=False, now_game_time=None):
    """Start an explicitly labelled scenario; never reset an installed casualty."""
    if not operator_approved:
        raise PermissionError("Only the operator may arm ship physics")
    _require_installed()
    existing = CanonicalShipState.objects.select_for_update().filter(pk=CLOCK_KEY).first()
    if existing is not None:
        if existing.condition != "armed":
            raise PhysicsError("Existing physics epoch is not healthy")
        return {"armed": False, "last_game_time": existing.details["last_game_time"]}
    cells = list(CanonicalShipState.objects.select_for_update()
                 .filter(category="pressure").order_by("key"))
    if (len(cells) != 133
            or any(c.quantity is None or c.quantity <= 0
                   or "physics_oxygen_kg" in c.details for c in cells)):
        raise PhysicsError("Establish 133 untouched nominal gas cells before arming")
    plant_rows = list(CanonicalShipState.objects.select_for_update()
                      .filter(key__in=["equipment:" + k for k in PLANTS]))
    if len(plant_rows) != len(PLANTS):
        raise PhysicsError("Authored life-support/power/thermal plant is missing")
    for cell in cells:
        d = dict(cell.details)
        if not (math.isfinite(d["temperature_k"]) and d["temperature_k"] > 0
                and math.isfinite(d["gas_volume_m3"]) and d["gas_volume_m3"] > 0):
            raise PhysicsError("Unknown cell temperature or volume")
        d.update(
            physics_oxygen_kg=cell.quantity * 0.232,
            physics_co2_kg=cell.quantity * 0.0006,
            physics_smoke_kg=0.0,
            physics_fuel_kg=0.0,
            physics_burn_kg_s=0.0,
            physics_leak_kg_s=0.0,
            physics_mist_kg_s=0.0,
            physics_background_kw=0.0,
            physics_heat_exposure_s=0.0,
            physics_damage_index=0.0,
            physics_thermal_capacity_kj_k=(
                30000.0 if cell.source_id.startswith("PZ-HAB-") else 5000.0),
        )
        cell.details = d
        cell.revision += 1
    CanonicalShipState.objects.bulk_update(cells, ["details", "revision"], batch_size=133)
    for item in plant_rows:
        d = dict(item.details)
        d["physics_online"] = PLANTS[item.source_id] and item.condition not in _BROKEN
        d["physics_commanded_on"] = d["physics_online"]
        d["physics_startup_s"] = 0.0
        item.details = d
        item.revision += 1
    CanonicalShipState.objects.bulk_update(plant_rows, ["details", "revision"], batch_size=100)
    # The selected v0.5 candidate already reconciles the entire mass ledger.
    # Copy its reference into the explicitly commissioned world-owned state;
    # it is not live configuration on later ticks.
    contract = load_candidate()["mass"]
    fields = ("dry_t", "commercial_cargo_t", "FTL_fuel_t",
              "sublight_reaction_mass_t", "mission_and_nonpropulsive_fluids_t")
    if not all(isinstance(contract.get(k), (int, float)) and
               math.isfinite(contract[k]) and contract[k] >= 0 for k in fields):
        raise PhysicsError("Invalid canonical ship departure mass contract")
    if not math.isclose(sum(contract[k] for k in fields),
                        contract["reference_departure_t"], rel_tol=1e-9):
        raise PhysicsError("Canonical ship departure mass does not reconcile")
    started = _now(now_game_time)
    CanonicalShipState.objects.create(
        key=CLOCK_KEY, category="meta", source_id="continuous-physics",
        source_model=MODEL, condition="armed", setting="scenario",
        details={
            "last_game_time": started, "step_seconds": STEP_SECONDS,
            "load_profile": "normal", "ticks": 0,
            "lost_to_space_kg": 0.0, "burned_fuel_kg": 0.0,
            "water_suppression_kg": 0.0,
            "co2_captured_kg": 0.0,
            "rotors": initial_rotors(),
            "cargo": initial_cargo(contract["commercial_cargo_t"] * 1000.0),
            "motion": {
                "position_m": [0.0, 0.0, 0.0],
                "velocity_m_s": [0.0, 0.0, 0.0],
                "dry_mass_kg": contract["dry_t"] * 1000.0,
                "cargo_mass_kg": contract["commercial_cargo_t"] * 1000.0,
                "cargo_capacity_kg": contract["commercial_cargo_t"] * 1000.0,
                "ftl_fuel_kg": contract["FTL_fuel_t"] * 1000.0,
                "mission_fluids_kg": contract["mission_and_nonpropulsive_fluids_t"] * 1000.0,
                "propellant_kg": contract["sublight_reaction_mass_t"] * 1000.0,
                "expended_propellant_kg": 0.0,
                "command": "coast", "drive_firing": False,
                "drive_power_mw": 0.0,
                "drive_condition": "operational",
                "drive_heat_kj": 0.0,
                "drive_trip_reason": None,
                "rcs_condition": "operational",
                "attitude_rad": [0.0, 0.0, 0.0],
                "angular_velocity_rad_s": [0.0, 0.0, 0.0],
                "attitude_command": "hold", "attitude_firing": False,
            },
            "provenance": "explicit_scenario_not_instrument_measured",
        },
    )
    return {"armed": True, "last_game_time": started, "cells": 133}


@transaction.atomic
def commission_g19_movement(*, operator_approved=False):
    """Explicit non-resetting G18 -> G19 migration of the active ship clock.

    The earlier 240-tonne placeholder fuel allocation is NOT promoted. Prior
    propellant expenditure is preserved against the candidate bunker reference.
    Position, velocity, attitude and work receipts are never cleared.
    """
    if not operator_approved:
        raise PermissionError("Explicit operator approval required for motion migration")
    clock = _clock(lock=True)
    d = dict(clock.details)
    motion = dict(d.get("motion", {}))
    changed = False
    required = ("dry_mass_kg", "ftl_fuel_kg", "mission_fluids_kg",
                "cargo_capacity_kg")
    if not all(k in motion for k in required):
        contract = load_candidate()["mass"]
        keys = ("dry_t", "commercial_cargo_t", "FTL_fuel_t",
                "sublight_reaction_mass_t", "mission_and_nonpropulsive_fluids_t")
        if not all(isinstance(contract.get(k), (float, int))
                   and math.isfinite(contract[k]) and contract[k] >= 0
                   for k in keys):
            raise PhysicsError("Cannot commission invalid candidate mass contract")
        if not math.isclose(sum(contract[k] for k in keys),
                            contract["reference_departure_t"], rel_tol=1e-9):
            raise PhysicsError("Candidate vessel mass does not reconcile")
        spent = float(motion.get("expended_propellant_kg", 0.0))
        if not math.isfinite(spent) or not 0 <= spent <= contract["sublight_reaction_mass_t"] * 1000:
            raise PhysicsError("Existing expended reaction mass cannot be reconciled")
        original_cargo = float(motion.get("cargo_mass_kg", 0.0))
        if original_cargo not in (0.0, contract["commercial_cargo_t"] * 1000):
            raise PhysicsError("Existing cargo manifest requires manual reconciliation")
        motion.update(
            dry_mass_kg=contract["dry_t"] * 1000,
            cargo_mass_kg=contract["commercial_cargo_t"] * 1000,
            cargo_capacity_kg=contract["commercial_cargo_t"] * 1000,
            ftl_fuel_kg=contract["FTL_fuel_t"] * 1000,
            mission_fluids_kg=contract["mission_and_nonpropulsive_fluids_t"] * 1000,
            propellant_kg=contract["sublight_reaction_mass_t"] * 1000 - spent,
        )
        if not motion.get("position_m"):
            motion["position_m"] = [0.0, 0.0, 0.0]
        if not motion.get("velocity_m_s"):
            motion["velocity_m_s"] = [0.0, 0.0, 0.0]
        if not motion.get("attitude_rad"):
            motion["attitude_rad"] = [0.0, 0.0, 0.0]
        if not motion.get("angular_velocity_rad_s"):
            motion["angular_velocity_rad_s"] = [0.0, 0.0, 0.0]
        motion.setdefault("command", "coast")
        motion.setdefault("attitude_command", "hold")
        motion.setdefault("drive_condition", "operational")
        motion.setdefault("rcs_condition", "operational")
        motion.setdefault("drive_firing", False)
        motion.setdefault("attitude_firing", False)
        motion.setdefault("drive_power_mw", 0.0)
        motion.setdefault("drive_heat_kj", 0.0)
        motion.setdefault("drive_trip_reason", None)
        d["motion"] = motion
        changed = True
    if "rotors" not in d:
        d["rotors"] = initial_rotors()
        changed = True
    if "cargo" not in d:
        # A candidate's unpositioned cargo is not six fabricated drum loads.
        d["cargo"] = initial_cargo(d["motion"]["cargo_mass_kg"])
        changed = True
    if changed:
        old = _snapshot(clock)
        d["movement_commissioned_from_candidate"] = MODEL
        clock.details = d
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        _event(clock, "g19_movement_commissioned", old)
    return {"commissioned": changed, "rotors": len(d["rotors"]),
            "cargo_mass_kg": d["motion"]["cargo_mass_kg"],
            "propellant_kg": d["motion"]["propellant_kg"]}



@transaction.atomic
def survey_cargo_lot(*, operator_approved=False, operation, lot_id=None,
                     mass_kg=None, drum=None, azimuth_deg=None,
                     radius_m=None, kind="bulk", restrained=True,
                     source_id=None):
    """Operator's actual cargo observation, never a synthetic load/unload.

    A manifest survey assigns known mass from the previously unlocated
    commercial cargo to a physical stowage datum. Splitting creates a small
    package within existing mass; verifying one drum does not assert anything
    about the other five. Every mutation is atomic and event-journalled.
    """
    if not operator_approved:
        raise PermissionError("Cargo placement requires an operator's surveyed evidence")
    clock = _clock(lock=True)
    before = _snapshot(clock)
    d = dict(clock.details)
    cargo = d.get("cargo")
    if cargo is None:
        raise PhysicsError("Cargo ledger not commissioned")
    try:
        if operation == "declare":
            revised = declare_cargo_lot(
                cargo, lot_id=lot_id, mass_kg=mass_kg, drum=drum,
                azimuth_deg=azimuth_deg, radius_m=radius_m,
                kind=kind, restrained=restrained)
        elif operation == "split":
            revised = split_cargo_lot(
                cargo, source_id=source_id, new_id=lot_id,
                mass_kg=mass_kg)
        elif operation == "verify":
            revised = verify_drum(cargo, drum)
        else:
            raise CargoError("Unknown cargo survey operation")
        validate_cargo(revised, d["motion"]["cargo_mass_kg"])
    except CargoError as exc:
        raise PhysicsError(str(exc)) from exc
    if revised != cargo:
        d["cargo"] = revised
        clock.details = d
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        event = _event(clock, "operator_cargo_" + operation, before)
        audit = dict(event.after)
        audit["survey"] = {
            "operation": operation, "lot_id": lot_id, "source_id": source_id,
            "mass_kg": mass_kg, "drum": drum, "azimuth_deg": azimuth_deg,
            "radius_m": radius_m, "kind": kind, "restrained": restrained,
            "recorded_lot": revised["lots"].get(lot_id),
        }
        event.after = audit
        event.save(update_fields=["after"])
    return {
        "operation": operation,
        "onboard_kg": onboard_mass_kg(revised),
        "unlocated_kg": revised["unlocated_onboard_kg"],
        "lots": len(revised["lots"]),
        "verified_drums": list(revised["verified_drums"]),
    }


def _physical_passage(iso):
    """A mechanically jammed-open air valve still leaks even if actuators fail."""
    kind = str(iso.reference.get("kind", "")).lower()
    if (iso.condition == "jammed" and iso.setting == "open"
            and ("valve" in kind or "damper" in kind)):
        return True
    return _conducts(iso)


def _live_edge(edge, isolators):
    r = edge.reference
    return (edge.condition not in _BROKEN and edge.setting == "available"
            and all(i in isolators and _physical_passage(isolators[i])
                    for i in r["isolator_ids"]))


def _reachable(edges, isolators, network, starts):
    graph = defaultdict(set)
    for edge in edges:
        r = edge.reference
        if r["network"] != network or not _live_edge(edge, isolators):
            continue
        a, b = r["from_node"], r["to_node"]
        graph[a].add(b)
        if network != "power" or r["kind"] in ("bridge_feeder", "cross_tie"):
            graph[b].add(a)
    reached = set(starts)
    queue = deque(sorted(reached))
    while queue:
        for neighbour in sorted(graph[queue.popleft()]):
            if neighbour not in reached:
                reached.add(neighbour)
                queue.append(neighbour)
    return reached


def _on(equipment, identifier):
    item = equipment.get(identifier)
    return bool(item and item.condition not in _BROKEN
                and item.details.get("physics_online") is True)


def _power(equipment, edges, isolators, profile):
    feeder = {e.source_id: e for e in edges if e.reference["network"] == "power"}
    active = {}
    for gen in GENERATION_MW:
        edge = feeder.get("EDGE-" + gen)
        active[gen] = bool(_on(equipment, gen) and edge and _live_edge(edge, isolators))
    mw = min(3.3, sum(GENERATION_MW[g] for g in active if active[g]))
    reached = _reachable(edges, isolators, "power",
                         [GENERATOR_NODES[k] for k in active if active[k]])
    requested = LOAD_PROFILES_MW[profile]
    # Available output is not the same as dispatched output. The electrical
    # plant supplies only the demand it can serve; generators cannot produce
    # full nameplate heat while delivering a fraction of their capacity.
    dispatched = min(mw, requested)
    generation_fraction = dispatched / mw if mw > 0 else 0.0
    # Protected bus can remain live under a partial generation shortfall.
    # Nonessential machinery still requires the selected full load profile.
    essential_assured = mw + 1e-9 >= LOAD_PROFILES_MW["essential"]
    return {
        "available_mw": mw, "requested_mw": requested,
        "dispatched_mw": dispatched,
        "generation_fraction": generation_fraction,
        "shortfall_mw": max(0.0, requested - mw),
        "assured": mw + 1e-9 >= requested,
        "essential_assured": essential_assured,
        "active_generators": tuple(k for k in GENERATION_MW if active[k]),
        "nodes": reached,
    }


def _parcel(a, b, mass):
    """Move finite mixed gas, species and enthalpy; walls stay in their cells."""
    amount = min(mass, a["mass"] * 0.20)
    if amount <= 0:
        return
    fraction = amount / a["mass"]
    for name in ("oxygen", "co2", "smoke"):
        moved = a[name] * fraction
        a[name] -= moved
        b[name] += moved
    energy = amount * CP_GAS_KJ_KG_K * a["temperature"]
    a["energy"] -= energy
    b["energy"] += energy
    a["mass"] -= amount
    b["mass"] += amount
    for cell in (a, b):
        cell["temperature"] = cell["energy"] / (
            cell["capacity"] + cell["mass"] * CP_GAS_KJ_KG_K)


def _cell_pressure(cell):
    return cell["mass"] * R_SPECIFIC_AIR * cell["temperature"] / cell["volume"]


def _load_cell(row):
    d = row.details
    mass = row.quantity
    if mass is None or mass < 0:
        raise PhysicsError("Unverified atmospheric mass")
    result = {
        "mass": mass, "oxygen": d["physics_oxygen_kg"],
        "co2": d["physics_co2_kg"], "smoke": d["physics_smoke_kg"],
        "fuel": d["physics_fuel_kg"], "burn": d["physics_burn_kg_s"],
        "leak": d["physics_leak_kg_s"], "mist": d["physics_mist_kg_s"],
        "background": d["physics_background_kw"],
        "temperature": d["temperature_k"], "volume": d["gas_volume_m3"],
        "capacity": d["physics_thermal_capacity_kj_k"],
        "exposure": d["physics_heat_exposure_s"],
        "damage": d["physics_damage_index"],
    }
    result["energy"] = (result["capacity"] + mass * CP_GAS_KJ_KG_K) * result["temperature"]
    if (any(not math.isfinite(x) or x < 0 for x in result.values())
            or result["oxygen"] + result["co2"] + result["smoke"] > mass + 1e-6):
        raise PhysicsError("Invalid cell gas, heat, or fuel state")
    return result


@transaction.atomic
def tick_continuous_physics(*, now_game_time=None):
    """Advance at most one minute per transaction, replay-safe and restart-safe.

    Long server downtime is processed in bounded subsequent ticks; no elapsed
    time is silently discarded or replaced by a wall-clock guess.
    """
    clock = _clock(lock=True)
    now = _now(now_game_time)
    last = clock.details["last_game_time"]
    if now < last:
        raise PhysicsError("Game time moved backwards; epoch needs operator review")
    seconds = min(MAX_ADVANCE_SECONDS, now - last)
    if seconds <= 0:
        return {"advanced": False, "last_game_time": last}
    pressure_rows = list(CanonicalShipState.objects.select_for_update()
                         .filter(category="pressure").order_by("key"))
    if len(pressure_rows) != 133:
        raise PhysicsError("Pressure topology incomplete")
    equipment_rows = list(CanonicalShipState.objects.select_for_update()
                          .filter(category="equipment").order_by("key"))
    inventory = CanonicalShipState.objects.select_for_update().get(
        pk="inventory:INV-WATER-NORMAL")
    inventory_before = _snapshot(inventory)
    isolators = {x.source_id: x for x in
                 CanonicalShipState.objects.filter(category="isolator")}
    edges = list(CanonicalShipState.objects.filter(category="edge"))
    access_rows = list(CanonicalShipState.objects.filter(category="access"))
    equipment = {x.source_id: x for x in equipment_rows}
    zones, owners, node_zones = _topology()
    cells = {r.source_id: _load_cell(r) for r in pressure_rows}
    leak_isolators = {r.source_id: r.details.get("physics_leak_isolator_id")
                      for r in pressure_rows}
    # Reference node ownership is static within a tick. Avoid a database
    # query for every 10-second integration substep.
    atmosphere_source_nodes = {}
    for node in CanonicalShipState.objects.filter(category="node"):
        if (node.reference.get("network") == "atmosphere"
                and node.reference.get("owner_type") == "equipment"):
            atmosphere_source_nodes.setdefault(
                node.reference.get("owner_id"), []).append(node.source_id)
    # Only real physically open, rated links between *known* gas cells may
    # exchange mass. Unknown cargo atmosphere is never invented as vacuum.
    open_hatches = []
    for door in access_rows:
        if door.setting != "open" or not door.reference.get("pressure_boundary"):
            continue
        a = zones.get(door.reference["from"])
        b = zones.get(door.reference["to"])
        if a != b and a in cells and b in cells:
            open_hatches.append((door.source_id, a, b))
    captured_co2 = float(clock.details.get("co2_captured_kg", 0.0))
    if not math.isfinite(captured_co2) or not 0 <= captured_co2 <= CO2_CAPTURE_CAPACITY_KG:
        raise PhysicsError("Invalid finite CO2 sorbent inventory")
    total_before = sum(c["mass"] + c["fuel"] for c in cells.values()) + captured_co2
    lost = burned = water = 0.0
    changed_equipment = set()
    motion = dict(clock.details.get("motion", {}))
    if not motion:
        raise PhysicsError("Ship motion state not initialised")
    rotors = dict(clock.details.get("rotors", {}))
    cargo = dict(clock.details.get("cargo", {}))
    try:
        validate_cargo(cargo, motion["cargo_mass_kg"])
    except CargoError as exc:
        raise PhysicsError(str(exc)) from exc
    if set(rotors) != set(ROTORS):
        raise PhysicsError("Rotary machinery not commissioned")
    summary = {}
    duration = 0.0

    while duration < seconds - 1e-9:
        dt = min(STEP_SECONDS, seconds - duration)
        duration += dt
        for item in equipment_rows:
            d = item.details
            remaining = d.get("physics_startup_s", 0.0)
            if remaining > 0 and item.condition not in _BROKEN:
                remaining = max(0.0, remaining - dt)
                d = dict(d)
                d["physics_startup_s"] = remaining
                if remaining == 0 and d.get("physics_commanded_on") is True:
                    d["physics_online"] = True
                item.details = d
                item.revision += 1
                changed_equipment.add(item.key)

        power = _power(equipment, edges, isolators, clock.details["load_profile"])
        # Propulsion hardware is represented by durable world-owned motion
        # condition flags until dedicated drive/RCS installations are mapped.
        # A failed drive can coast, but cannot silently resume thrust.
        drive_operational = motion.get("drive_condition", "operational") == "operational"
        rcs_operational = motion.get("rcs_condition", "operational") == "operational"
        # A real, declared, restrained and captured cargo sled can be
        # advanced only while power and the separate collar/pressure
        # interfaces remain available. Mass doesn't disappear during travel.
        freight_load = active_freight_mw(cargo)
        freight_can_power = (
            power["assured"] and
            power["available_mw"] - power["requested_mw"] >= freight_load)
        freight_collars = {
            name for name in CARGO_DRUMS
            if equipment.get(name + "-FREIGHT-COLLAR") is not None
            and equipment[name + "-FREIGHT-COLLAR"].condition not in _BROKEN
            and rotors[name]["hardlock"] and rotors[name]["brake"]
            and rotors[name]["freight_collar"]
            and abs(rotors[name]["rpm"]) < 0.001
            and rotors[name]["target_rpm"] == 0
            and not rotors[name]["passenger_indexer"]
        }
        open_freight = {
            name for name in CARGO_DRUMS
            if any(door.source_id == "ACC-" + name + "-FREIGHT-CAPTURE"
                   and door.condition not in _BROKEN
                   and door.setting == "open" for door in access_rows)
        }
        cargo, completed_freight = step_freight(
            cargo, dt, power_ready=freight_can_power,
            available_collars=freight_collars, open_fixed_gates=open_freight)
        if freight_load and freight_can_power and freight_collars:
            power["requested_mw"] += freight_load
            power["dispatched_mw"] += freight_load
            power["generation_fraction"] = (
                power["dispatched_mw"] / power["available_mw"])
        rotary_load = motion_power_mw(rotors)
        rotary_can_power = (
            power["assured"] and
            power["available_mw"] - power["requested_mw"] >= rotary_load)
        rotor_equipment = {
            "HAB": all(equipment.get(name) is not None and
                       equipment[name].condition not in _BROKEN
                       for name in ("HAB-BEARING-FORE", "HAB-BEARING-AFT")),
            # Indexer and freight collar faults affect only their interfaces.
            # They do not magically seize the independent drum drive.
            **{name: True for name in DRUMS},
        }
        # Only individually surveyed placements can set a drum's cargo
        # imbalance. Unknown bulk mass is not silently made symmetrical.
        for drum in CARGO_DRUMS:
            measurement = drum_balance(cargo, drum)
            if measurement["surveyed"]:
                rotors[drum] = {
                    **rotors[drum],
                    "imbalance_kg_m": measurement["imbalance_kg_m"],
                }
        rotors = step_rotors(
            rotors, dt, powered=rotary_can_power, equipment_ok=rotor_equipment)
        if rotary_load and rotary_can_power:
            power["requested_mw"] += rotary_load
            power["dispatched_mw"] += rotary_load
            power["generation_fraction"] = (
                power["dispatched_mw"] / power["available_mw"])
        motion = _advance_motion(
            motion, dt, power, drive_operational=drive_operational,
            rcs_operational=rcs_operational)
        # Account for propulsion-control auxiliaries, NOT thrust energy, in
        # electrical dispatch and electrical-generator waste heat.
        drive_load = motion["drive_power_mw"]
        # Local machinery has finite thermal storage. The external drive
        # energy plant is fictional; the thermal penalty is world-owned and
        # cannot be exported to vacuum without a serviceable radiator path.
        heat = float(motion.get("drive_heat_kj", 0.0))
        if not math.isfinite(heat) or not 0 <= heat <= DRIVE_THERMAL_BUFFER_KJ:
            raise PhysicsError("Invalid propulsion thermal inventory")
        heat += DRIVE_HEAT_KW * dt if motion["drive_firing"] else 0.0
        drive_cooling_kw = 0.0
        connected_lt = _reachable(
            edges, isolators, "lt_cooling", ["NODE-LT-PLANT"])
        cooling = (
            len(connected_lt) > 1 and _on(equipment, "LT-PLANT")
            and any(_on(equipment, f"RAD-LT-{n}") for n in range(1, 5))
            and power["assured"])
        if cooling:
            drive_cooling_kw = min(DRIVE_COOLING_KW, heat / dt)
            heat = max(0.0, heat - drive_cooling_kw * dt)
        if heat >= DRIVE_THERMAL_BUFFER_KJ:
            heat = DRIVE_THERMAL_BUFFER_KJ
            motion["drive_condition"] = "thermal_trip"
            motion["drive_trip_reason"] = "propulsion_cooling_limit"
            motion["command"] = "coast"
        motion["drive_heat_kj"] = heat
        if drive_load:
            power["requested_mw"] += drive_load
            power["dispatched_mw"] += drive_load
            power["generation_fraction"] = (
                power["dispatched_mw"] / power["available_mw"])
            power["shortfall_mw"] = max(
                0.0, power["requested_mw"] - power["available_mw"])
        # No unproven infinite battery/flywheel bridge or magic auto load shedding.
        protected_power = power["essential_assured"] and (
            "PWR-PROT" in power["nodes"])
        powered = power["assured"] and bool(
            {"PWR-MSB-A", "PWR-MSB-B", "PWR-PROT"} & power["nodes"])
        active_air_trains = {
            eclss for eclss, node in
            (("ECLSS-A", "NODE-HAB-06-ECLSS-A-LP"),
             ("ECLSS-B", "NODE-HAB-08-ECLSS-B-LP"))
            if powered and _on(equipment, eclss) and node in power["nodes"]
        }
        # A powered processor cannot drive fans in another isolated duct
        # network. Motorised mixing requires a source on the same *currently
        # conducting* atmosphere graph; passive pressure movement does not.
        air_source_nodes = [
            node_id for train in sorted(active_air_trains)
            for node_id in atmosphere_source_nodes.get(train, ())
        ]
        air_on = bool(air_source_nodes)
        # Process gas at the *installed* ECLSS intake zone. The capture
        # medium is finite and remains aboard, so removing CO2 from the
        # circulating gas cannot silently delete mass from the ship.
        for train in sorted(active_air_trains):
            zone = owners.get(train)
            if zone not in cells:
                continue
            available = CO2_CAPTURE_CAPACITY_KG - captured_co2
            removed = min(cells[zone]["co2"],
                          CO2_CAPTURE_KG_S_PER_TRAIN * dt, available)
            if removed > 0:
                cells[zone]["co2"] -= removed
                cells[zone]["mass"] -= removed
                cells[zone]["energy"] -= removed * CP_GAS_KJ_KG_K * cells[zone]["temperature"]
                captured_co2 += removed
                cells[zone]["temperature"] = cells[zone]["energy"] / (
                    cells[zone]["capacity"] + cells[zone]["mass"] * CP_GAS_KJ_KG_K)
        fan_nodes = (_reachable(edges, isolators, "atmosphere", air_source_nodes)
                     if air_on else set())
        # Open pressure hatches are a separate flow path; closing a hatch
        # does not close an independent duct, or vice versa.
        for _door_id, a_id, b_id in open_hatches:
            a, b = cells[a_id], cells[b_id]
            exchange = min(0.25 * dt, 0.02 * a["mass"], 0.02 * b["mass"])
            _parcel(a, b, exchange)
            _parcel(b, a, exchange)
            pa, pb = _cell_pressure(a), _cell_pressure(b)
            if abs(pa - pb) > 1.0:
                donor, receiver = (a, b) if pa > pb else (b, a)
                _parcel(donor, receiver, min(
                    0.60 * dt * abs(pa - pb) / 101325.0,
                    0.1 * donor["mass"]))
        atm_edges = [e for e in edges
                     if e.reference["network"] == "atmosphere"
                     and _live_edge(e, isolators)]
        # Flow follows actual duct edges independently of open hatches.
        for edge in sorted(atm_edges, key=lambda e: e.source_id):
            a_id = node_zones.get(edge.reference["from_node"])
            b_id = node_zones.get(edge.reference["to_node"])
            if a_id == b_id or a_id not in cells or b_id not in cells:
                continue
            a, b = cells[a_id], cells[b_id]
            if (air_on and edge.reference["from_node"] in fan_nodes
                    and edge.reference["to_node"] in fan_nodes):
                # Counterflow is an exchange, not doubled net mass.
                x = min(2.0 * dt, 0.05 * a["mass"], 0.05 * b["mass"])
                _parcel(a, b, x)
                _parcel(b, a, x)
            pa, pb = _cell_pressure(a), _cell_pressure(b)
            if abs(pa - pb) > 1:
                donor, receiver = (a, b) if pa > pb else (b, a)
                _parcel(donor, receiver, min(0.12 * dt * abs(pa - pb) / 101325.0,
                                             donor["mass"] * 0.10))

        # Existing LT coolant route plus finite live radiator wings.
        cooling_nodes = _reachable(
            edges, isolators, "lt_cooling", ["NODE-LT-PLANT"])
        cool_zones = {node_zones.get(n) for n in cooling_nodes}
        cool_zones &= set(cells)
        total_cool_kw = (min(3750.0, 937.5 * sum(
            _on(equipment, "RAD-LT-" + str(i)) for i in range(1, 5)))
            if powered and _on(equipment, "LT-PLANT") else 0.0)
        # The propulsion thermal store and ordinary equipment share the
        # finite radiator budget: never reject the same heat twice.
        total_cool_kw = max(0.0, total_cool_kw - drive_cooling_kw)
        per_zone_kw = total_cool_kw / len(cool_zones) if cool_zones else 0.0

        fire_starts = [n for pump in ("FIRE-PUMP-FWD", "FIRE-PUMP-AFT")
                       if powered and _on(equipment, pump)
                       for n in ["NODE-" + pump]]
        fire_nodes = _reachable(edges, isolators, "fire_main", fire_starts)
        # Waste heat is a physical output of operating machinery, not an
        # operator-injected scenario fault. It persists through a cooling
        # failure and can therefore cause a secondary thermal casualty.
        machinery_heat_kw = defaultdict(float)
        for plant_id, heat_kw in PLANT_WASTE_HEAT_KW.items():
            zone = owners.get(plant_id)
            if zone in cells and _on(equipment, plant_id):
                if plant_id in GENERATION_MW:
                    if plant_id in power["active_generators"]:
                        # Fixed idling losses plus a load-dependent component.
                        machinery_heat_kw[zone] += heat_kw * (
                            0.25 + 0.75 * power["generation_fraction"])
                elif powered:
                    machinery_heat_kw[zone] += heat_kw
        for cell_id, cell in cells.items():
            mass = cell["mass"]
            leak_rate = cell["leak"]
            source_valve = leak_isolators.get(cell_id)
            if source_valve:
                isolator = isolators.get(source_valve)
                if isolator is None:
                    raise PhysicsError("Missing authored leak isolation point")
                # A valve closed at its real station arrests a service-line
                # leak; a valve mechanically stuck open cannot be saved by
                # a remote OFF indication.
                if not _physical_passage(isolator):
                    leak_rate = 0.0
            leak = min(mass, leak_rate * dt)
            if leak:
                portion = leak / mass
                for name in ("oxygen", "co2", "smoke"):
                    cell[name] *= (1.0 - portion)
                cell["energy"] -= leak * CP_GAS_KJ_KG_K * cell["temperature"]
                cell["mass"] -= leak
                lost += leak

            active_mist = (cell["mist"] > 0 and cell_id.startswith("PZ-HAB-")
                           and "NODE-" + cell_id[3:] + "-FIRE-MIST" in fire_nodes
                           and inventory.quantity is not None and inventory.quantity > 0)
            mist_kg = (min(cell["mist"] * dt, inventory.quantity * 1000.0)
                       if active_mist else 0.0)
            if mist_kg:
                inventory.quantity -= mist_kg / 1000.0
                water += mist_kg
                # Mist cools locally but cannot remove more sensible heat than exists.
                cell["energy"] -= min(
                    max(0.0, cell["energy"] -
                        (cell["capacity"] + cell["mass"]) * 273.15),
                    mist_kg * 50.0)
            burn = min(cell["fuel"], cell["burn"] * dt,
                       cell["oxygen"] / O2_PER_FUEL)
            if mist_kg:
                burn = min(burn, 0.15 * cell["burn"] * dt)
            if burn > 0:
                cell["fuel"] -= burn
                cell["oxygen"] -= burn * O2_PER_FUEL
                cell["smoke"] += burn * 0.08
                cell["co2"] += burn * (1.0 + O2_PER_FUEL - 0.08)
                cell["mass"] += burn
                cell["energy"] += burn * FIRE_HEAT_KJ_KG
                burned += burn
            cell["energy"] += (cell["background"] + machinery_heat_kw[cell_id]) * dt
            cell["temperature"] = cell["energy"] / (
                cell["capacity"] + cell["mass"] * CP_GAS_KJ_KG_K)
            if cell_id in cool_zones and per_zone_kw > 0:
                removal = min(per_zone_kw * dt, max(
                    0.0, (cell["temperature"] - 293.15) *
                    (cell["capacity"] + cell["mass"])))
                cell["energy"] -= removal
                cell["temperature"] = cell["energy"] / (
                    cell["capacity"] + cell["mass"] * CP_GAS_KJ_KG_K)
            if cell["temperature"] >= 345.0:
                cell["exposure"] += dt
                if cell["exposure"] >= 60.0:
                    cell["damage"] = min(1.0, cell["damage"] + 0.002 * dt)
            else:
                cell["exposure"] = max(0.0, cell["exposure"] - dt)
            if cell["fuel"] < 1e-9 or cell["oxygen"] < 1e-9:
                cell["burn"] = 0.0
            # No automatic ignition without a finite, already ignited fuel load.
            # Smoke/heat and equipment damage can still spread via open ducts.
        summary = {
            "available_mw": round(power["available_mw"], 4),
            "requested_mw": power["requested_mw"],
            "power_assured": powered,
            "protected_power": protected_power,
            "dispatched_mw": round(power["dispatched_mw"], 4),
            "shortfall_mw": round(power["shortfall_mw"], 4),
            "ventilation_powered": air_on,
            "cooling_kw": round(total_cool_kw, 3),
            "burning_cells": sum(c["burn"] > 0 for c in cells.values()),
            "open_pressure_hatches": len(open_hatches),
            "active_leaking_cells": sum(
                c["leak"] > 0 and (
                    not leak_isolators.get(zone)
                    or _physical_passage(isolators[leak_isolators[zone]]))
                for zone, c in cells.items()),
        }

    total_after = sum(c["mass"] + c["fuel"] for c in cells.values()) + captured_co2
    if not math.isclose(total_before, total_after + lost, abs_tol=1e-5, rel_tol=1e-10):
        raise PhysicsError("Gas, fire fuel and vented mass did not reconcile")
    pressure_changed = []
    for row in pressure_rows:
        c = cells[row.source_id]
        if any(not math.isfinite(x) or x < 0 for x in c.values()):
            raise PhysicsError("Nonphysical integration result")
        if c["oxygen"] + c["co2"] + c["smoke"] > c["mass"] + 1e-5:
            raise PhysicsError("Unaccounted gas species")
        d = dict(row.details)
        d.update(
            physics_oxygen_kg=c["oxygen"], physics_co2_kg=c["co2"],
            physics_smoke_kg=c["smoke"], physics_fuel_kg=c["fuel"],
            physics_burn_kg_s=c["burn"], physics_leak_kg_s=c["leak"],
            physics_mist_kg_s=c["mist"], physics_heat_exposure_s=c["exposure"],
            physics_damage_index=c["damage"], temperature_k=c["temperature"],
        )
        if d != row.details or abs(row.quantity - c["mass"]) > 1e-10:
            row.quantity = c["mass"]
            row.details = d
            if c["mass"] <= 1e-9:
                row.condition = "vacuum"
            elif c["damage"] >= 0.2 and row.condition == "scenario_nominal":
                row.condition = "heat_damaged"
            row.revision += 1
            pressure_changed.append(row)
    CanonicalShipState.objects.bulk_update(
        pressure_changed, ["quantity", "details", "condition", "revision"],
        batch_size=133)

    # Consequences act on authored plant records. Transient overtemperature
    # trips protection; sustained exposure makes *lasting* damage. A reset
    # may clear a protection trip only after physical cooling and isolation,
    # never erase the cumulative damage index or rebuild destroyed hardware.
    for item in equipment_rows:
        zone = owners.get(item.source_id)
        c = cells.get(zone)
        if c is None:
            continue
        if (c["damage"] >= 0.60 and item.condition in
                {"serviceable", "degraded", "faulted"}):
            previous = _snapshot(item)
            item.condition = "failed"
            details = dict(item.details)
            if item.source_id in PLANTS:
                details["physics_online"] = False
                details["physics_commanded_on"] = False
                details["physics_startup_s"] = 0.0
                details.pop("physics_trip_reason", None)
                details.pop("physics_trip_game_time", None)
            item.details = details
            item.revision += 1
            _event(item, "severe_thermal_damage", previous)
            changed_equipment.add(item.key)
        elif (item.source_id in PLANTS and item.condition == "serviceable"
                and c["temperature"] >= 333.15
                and item.details.get("physics_online") is True):
            previous = _snapshot(item)
            details = dict(item.details)
            details["physics_online"] = False
            details["physics_commanded_on"] = False
            details["physics_startup_s"] = 0.0
            details["physics_trip_reason"] = "local_overtemperature_protection"
            details["physics_trip_game_time"] = last + seconds
            item.details = details
            item.condition = "faulted"
            item.revision += 1
            _event(item, "thermal_protection_trip", previous)
            changed_equipment.add(item.key)
        elif c["damage"] >= 0.20 and item.condition == "serviceable":
            previous = _snapshot(item)
            item.condition = "degraded"
            item.revision += 1
            _event(item, "thermal_exposure_damage", previous)
            changed_equipment.add(item.key)
    if changed_equipment:
        CanonicalShipState.objects.bulk_update(
            [e for e in equipment_rows if e.key in changed_equipment],
            ["details", "condition", "revision"], batch_size=100)
    if water:
        inventory.revision += 1
        inventory.save(update_fields=["quantity", "revision"])
        _event(inventory, "finite_fire_mist_water", inventory_before)

    old = _snapshot(clock)
    d = dict(clock.details)
    d["last_game_time"] = last + seconds
    d["ticks"] += 1
    d["lost_to_space_kg"] += lost
    d["burned_fuel_kg"] += burned
    d["water_suppression_kg"] += water
    d["co2_captured_kg"] = captured_co2
    d["motion"] = motion
    d["rotors"] = rotors
    validate_cargo(cargo, motion["cargo_mass_kg"])
    d["cargo"] = cargo
    d["summary"] = {
        **summary,
        "gas_kg": round(sum(c["mass"] for c in cells.values()), 6),
        "oxygen_kg": round(sum(c["oxygen"] for c in cells.values()), 6),
        "smoke_kg": round(sum(c["smoke"] for c in cells.values()), 6),
        "fuel_kg": round(sum(c["fuel"] for c in cells.values()), 6),
        "damaged_cells": sum(c["damage"] >= 0.2 for c in cells.values()),
        "processed_seconds": seconds,
        "ship_position_m": [round(x, 3) for x in motion["position_m"]],
        "ship_velocity_m_s": [round(x, 6) for x in motion["velocity_m_s"]],
        "ship_propellant_kg": round(motion["propellant_kg"], 3),
        "ship_current_mass_kg": round(sum(motion[k] for k in
            ("dry_mass_kg", "cargo_mass_kg", "ftl_fuel_kg",
             "mission_fluids_kg", "propellant_kg")), 3),
        "ship_cargo_mass_kg": round(motion["cargo_mass_kg"], 3),
        "cargo_unlocated_kg": round(cargo["unlocated_onboard_kg"], 3),
        "freight_jobs": len(cargo["jobs"]),
        "drive_firing": motion["drive_firing"],
        "drive_power_mw": motion["drive_power_mw"],
        "drive_condition": motion["drive_condition"],
        "drive_heat_kj": round(motion.get("drive_heat_kj", 0.0), 2),
        "drive_trip_reason": motion.get("drive_trip_reason"),
        "rotor_rpm": {k: round(v["rpm"], 5) for k, v in rotors.items()},
        "rotor_gravity_g": {k: round(rotor_gravity(rotors, k), 4)
                            for k in ROTORS},
        "rcs_condition": motion["rcs_condition"],
        "ship_attitude_rad": [round(x, 8) for x in motion["attitude_rad"]],
        "ship_angular_velocity_rad_s": [round(x, 10) for x in motion["angular_velocity_rad_s"]],
    }
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "continuous_physics_tick", old)
    return {"advanced": True, "last_game_time": d["last_game_time"], **d["summary"]}


def _leak_active(cell):
    """A closed actual source valve contains a line leak without erasing damage."""
    details = cell.details
    if details.get("physics_leak_kg_s", 0.0) <= 0:
        return False
    isolator_id = details.get("physics_leak_isolator_id")
    if not isolator_id:
        return True  # a direct hull breach has no magic isolator
    try:
        isolator = state("isolator", isolator_id)
    except ShipOperationsError:
        return True  # unknown control cannot prove a leak stopped
    return _physical_passage(isolator)


def _air_safe(cell):
    """Conservative screen for UNsuited local work and pressure-hatch opening."""
    if cell.quantity is None or cell.quantity <= 0:
        return False
    d = cell.details
    if not all(k in d for k in (
            "gas_volume_m3", "temperature_k", "physics_oxygen_kg",
            "physics_co2_kg", "physics_smoke_kg", "physics_damage_index",
            "physics_leak_kg_s", "physics_burn_kg_s")):
        return False
    p = cell.quantity * R_SPECIFIC_AIR * d["temperature_k"] / d["gas_volume_m3"]
    o2 = d["physics_oxygen_kg"] / 0.032
    remaining = max(0.0, cell.quantity - d["physics_oxygen_kg"]) / 0.029
    po2 = p * o2 / (o2 + remaining) if o2 + remaining else 0.0
    return (
        80000.0 <= p <= 120000.0 and 16000.0 <= po2 <= 26000.0
        and 278.15 <= d["temperature_k"] <= 313.15
        and d["physics_co2_kg"] <= 0.005 * cell.quantity
        and d["physics_smoke_kg"] <= 0.00001 * cell.quantity
        and d["physics_damage_index"] < 0.20
        and not _leak_active(cell)
        and d["physics_burn_kg_s"] == 0
    )


def _hatch_open_preflight(hatch):
    """Only physically ordinary HAB bridge hatches; never rotary/cargo/EVA."""
    spec = hatch.reference
    if (not hatch.source_id.startswith("ACC-BR-")
            or spec.get("pressure_boundary") is not True
            or "hatch" not in str(spec.get("kind", "")).lower()):
        raise PhysicsError("This boundary requires a dedicated mechanical transfer controller")
    zones, _, _ = _topology()
    a, b = zones.get(spec["from"]), zones.get(spec["to"])
    if a is None or b is None or a == b or a == "VACUUM" or b == "VACUUM":
        raise PhysicsError("Unknown or unverified pressure receiver")
    if not a.startswith("PZ-") or not b.startswith("PZ-"):
        raise PhysicsError("Unclassified atmosphere cannot be joined")
    left = state("pressure", a, lock=True)
    right = state("pressure", b, lock=True)
    if not _air_safe(left) or not _air_safe(right):
        raise PhysicsError("Air sampling, pressure, fire or local integrity not safe")
    pa = left.quantity * R_SPECIFIC_AIR * left.details["temperature_k"] / left.details["gas_volume_m3"]
    pb = right.quantity * R_SPECIFIC_AIR * right.details["temperature_k"] / right.details["gas_volume_m3"]
    if abs(pa - pb) > 2000.0:
        raise PhysicsError("Hatch differential pressure exceeds verified opening limit")
    # The BR cell is a dual-ended pressure buffer, not a shortcut joining
    # both HAB arcs. Fail closed if its other rated door is open.
    bridge = a if a.startswith("PZ-BR-") else b if b.startswith("PZ-BR-") else None
    if bridge is None:
        raise PhysicsError("Not an ordinary habitation bridge transfer")
    for peer in CanonicalShipState.objects.filter(category="access", setting="open"):
        if peer.key == hatch.key:
            continue
        p = peer.reference
        if bridge in (zones.get(p["from"]), zones.get(p["to"])):
            raise PhysicsError("Opposite bridge pressure hatch must close first")


def _helm_at(actor):
    """Crew physically at an installed ship command or aft machinery console."""
    room = getattr(getattr(getattr(actor, "location", None), "db", None),
                   "ox_space_id", None)
    role = getattr(getattr(actor, "db", None), "crew_role", None)
    allowed = {
        "CMD-PRIMARY": {"captain", "bridge_officer"},
        "PROP-CTRL": {"captain", "bridge_officer", "chief_engineer", "watch_engineer"},
    }
    if room not in allowed or (role not in allowed[room] and
                               not actor.check_permstring("Developer")):
        raise PermissionError("Helm requires an authorised operator at a real command station")


def _crew_at(actor, space_id):
    if (actor is None or getattr(actor, "location", None) is None
            or getattr(actor.location.db, "ox_space_id", None) != space_id):
        raise PermissionError("Authenticated character must be physically at local control")
    if (actor.db.crew_role not in AUTHORISED_ROLES
            and not actor.check_permstring("Developer")):
        raise PermissionError("No qualified department authority")


def _receipt(event, request_id, actor, action, target):
    return {
        "request_id": request_id, "actor_dbref": actor.dbref,
        "operation": action, "target": target, "status": "succeeded",
        "source_event_id": str(event.sequence),
    }


@transaction.atomic
def crew_physical_action(actor, request_id, action, target, value):
    """Real local control with global, durable request-ID deduplication.

    Only switches, installed plant and finite fire-mist controls are supported.
    Casualty injection and arbitrary repair are deliberately not crew powers.
    """
    if not isinstance(request_id, str) or re.fullmatch(r"[0-9a-f]{32}", request_id) is None:
        raise PhysicsError("Expected one 32-character lowercase request UUID")
    if action not in {"switch", "plant", "schedule", "mist", "hatch", "service", "helm", "attitude", "rotor", "drive", "freight"}:
        raise PhysicsError("Unknown physical operation")
    if actor is None or getattr(actor.db, "ox_terminal_dead", False):
        raise PermissionError("A deceased or missing character cannot operate machinery")
    _clock(lock=True)  # serializes physical actions with world ticks
    # The pre-existing world WorkReceipt ledger owns the *global* request-ID
    # namespace across both G18 and legacy social/ship work.
    old = WorkReceipt.objects.select_for_update().filter(pk=request_id).first()
    if old is not None:
        if (old.actor_dbref != actor.dbref or old.target != "ship_physics"
            or old.operation != action
            or old.arguments != {"target": target, "value": value}):
            raise PermissionError("Global work request ID collision")
        return dict(old.outcome)
    previous = CanonicalShipEvent.objects.filter(request_id=request_id).first()
    if previous is not None:
        if (previous.actor_dbref != getattr(actor, "dbref", None)
                or previous.operation != "crew_" + action
                or previous.component_key != (
                    "isolator:" if action == "switch"
                    else "pressure:" if action == "mist"
                    else "access:" if action == "hatch"
                    else "" if action in {"schedule", "helm", "attitude", "rotor", "drive", "freight"}
                    else "equipment:") + (CLOCK_KEY if action in {"schedule", "helm", "attitude", "rotor", "drive", "freight"} else target)
                or previous.after.get("requested_value") != value):
            raise PermissionError("Global request ID already belongs to another action")
        return _receipt(previous, request_id, actor, action, target)
    if action == "switch":
        item = state("isolator", target, lock=True)
        _crew_at(actor, item.space_id)
        if not item.reference.get("manual_operation"):
            raise PermissionError("No local manual operation is installed")
        if value not in {"open", "closed"} or item.condition in _BROKEN:
            raise PhysicsError("Unsafe switch command")
        before = _snapshot(item)
        if item.setting != value:
            item.setting = value
            item.revision += 1
            item.save(update_fields=["setting", "revision"])
    elif action == "plant":
        if target not in PLANTS or value not in {"on", "off"}:
            raise PhysicsError("No approved local plant control for that unit")
        item = state("equipment", target, lock=True)
        _crew_at(actor, item.space_id)
        if item.condition in _BROKEN and value == "on":
            raise PhysicsError("Failed plant cannot be started")
        before = _snapshot(item)
        on = value == "on"
        d = dict(item.details)
        d["physics_commanded_on"] = on
        d["physics_online"] = False if not on else d.get("physics_online", False)
        d["physics_startup_s"] = (30.0 if target in GENERATION_MW else 10.0) if (
            on and not d["physics_online"]) else 0.0
        if d != item.details:
            item.details = d
            item.revision += 1
            item.save(update_fields=["details", "revision"])
    elif action == "freight":
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        cargo = d.get("cargo", {})
        lot = cargo.get("lots", {}).get(target)
        if not lot:
            raise PhysicsError("Cargo lot has not been physically surveyed")
        drum = lot["drum"]
        room = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        if (room != drum + "-FREIGHT-LOCK" or
                getattr(actor.db, "crew_role", None) not in {
                    "cargo_officer", "chief_engineer", "watch_engineer"
                } and not actor.check_permstring("Developer")):
            raise PermissionError("Freight requires qualified operator at this drum's collar")
        zone = _topology()[0].get(room)
        if not zone or zone == "VACUUM" or not _air_safe(state("pressure", zone)):
            raise PhysicsError("Freight control atmosphere is unverified or unsafe")
        collar = state("equipment", drum + "-FREIGHT-COLLAR")
        gate = state("access", "ACC-" + drum + "-FREIGHT-CAPTURE")
        gate_open = gate.setting == "open" and gate.condition not in _BROKEN
        if gate_open and value in {"to_spine", "from_spine"}:
            spec = gate.reference
            zones = _topology()[0]
            za, zb = zones.get(spec["from"]), zones.get(spec["to"])
            if not za or not zb or za == "VACUUM" or zb == "VACUUM":
                raise PhysicsError("Freight boundary environment is unverified")
            ca, cb = state("pressure", za), state("pressure", zb)
            if not _air_safe(ca) or not _air_safe(cb):
                raise PhysicsError("Freight boundary cannot prove safe chemistry")
            pa = ca.quantity * R_SPECIFIC_AIR * ca.details["temperature_k"] / ca.details["gas_volume_m3"]
            pb = cb.quantity * R_SPECIFIC_AIR * cb.details["temperature_k"] / cb.details["gas_volume_m3"]
            if abs(pa - pb) > 2000:
                raise PhysicsError("Freight pressure differential too high")
        try:
            d["cargo"] = start_freight_transfer(
                cargo, d["rotors"], lot_id=target, direction=value,
                collar_healthy=collar.condition not in _BROKEN,
                gate_open=gate_open,
                restricted=lot["mass_kg"] > 50_000)
            validate_cargo(d["cargo"], d["motion"]["cargo_mass_kg"])
        except CargoError as exc:
            raise PhysicsError(str(exc)) from exc
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "drive":
        if target not in {"MAIN", "RCS"} or value not in {"inhibit", "release", "reset"}:
            raise PhysicsError("Unknown propulsion safety operation")
        _crew_at(actor, "PROP-CTRL")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        motion = dict(d.get("motion", {}))
        key = "drive_condition" if target == "MAIN" else "rcs_condition"
        current = motion.get(key)
        if value == "reset":
            if target != "MAIN" or current != "thermal_trip":
                raise PhysicsError("No local propulsion thermal trip to reset")
            if motion.get("drive_heat_kj", 0) > DRIVE_THERMAL_RESET_KJ:
                raise PhysicsError("Propulsion too hot for safe manual reset")
            motion[key] = "inhibited"
            motion["drive_trip_reason"] = None
        elif value == "release":
            if current != "inhibited":
                raise PhysicsError("Only a locally inhibited sound drive can be released")
            # Inhibiting a drive does not repair underlying damage.
            motion[key] = "operational"
        else:
            if current not in {"operational", "inhibited"}:
                raise PhysicsError("Damaged or tripped drive cannot bypass repair via inhibit")
            motion[key] = "inhibited"
        d["motion"] = motion
        if d != item.details:
            item.details = d
            item.revision += 1
            item.save(update_fields=["details", "revision"])
    elif action == "rotor":
        if target not in ROTORS:
            raise PhysicsError("No installed rotary machinery at that identifier")
        room = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        roles = {"chief_engineer", "watch_engineer"}
        permitted = ("ENG-CONTROL", "WR-ROTOR-MACHINERY") if target == "WR-01" else (
            ("ENG-CONTROL",) if target == "HAB" else
            (target + "-FREIGHT-LOCK", target + "-SERVICE-LOCK"))
        if room not in permitted or (
                getattr(actor.db, "crew_role", None) not in roles and
                not actor.check_permstring("Developer")):
            raise PermissionError("Operator is not at that rotor's local machinery controls")
        if target in DRUMS and target in _clock().details.get("cargo", {}).get("jobs", {}):
            if value in {"start", "release", "freight_retract", "passenger_extend"}:
                raise PhysicsError("Freight operation underway; cannot release its capture")
        if target in DRUMS and value in {"freight_extend", "passenger_extend"}:
            suffix = ("-FREIGHT-COLLAR" if value == "freight_extend"
                      else "-PERSONNEL-INDEXER")
            unit = state("equipment", target + suffix)
            if unit.condition in _BROKEN:
                raise PhysicsError("Transfer actuator damaged")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        try:
            d["rotors"] = set_rotor_command(d["rotors"], target, value)
        except RotorError as exc:
            raise PhysicsError(str(exc)) from exc
        if d != item.details:
            item.details = d
            item.revision += 1
            item.save(update_fields=["details", "revision"])
    elif action == "attitude":
        if target != "HELM" or value not in ATTITUDE_COMMANDS:
            raise PhysicsError("Unknown ship attitude command")
        _helm_at(actor)
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        motion = dict(d.get("motion", {}))
        if not motion:
            raise PhysicsError("Ship motion has not been commissioned")
        motion["attitude_command"] = value
        d["motion"] = motion
        if d != item.details:
            item.details = d
            item.revision += 1
            item.save(update_fields=["details", "revision"])
    elif action == "helm":
        if target != "HELM" or value not in HELM_DIRECTIONS:
            raise PhysicsError("Unknown ship thrust direction")
        _helm_at(actor)
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        motion = dict(d.get("motion", {}))
        if not motion:
            raise PhysicsError("Ship motion has not been commissioned")
        motion["command"] = value
        d["motion"] = motion
        if d != item.details:
            item.details = d
            item.revision += 1
            item.save(update_fields=["details", "revision"])
    elif action == "schedule":
        if target != "GEN-M" or value not in LOAD_PROFILES_MW:
            raise PhysicsError("Unknown dispatch profile")
        station = state("equipment", "GEN-M")
        _crew_at(actor, station.space_id)
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        d["load_profile"] = value
        if d != item.details:
            item.details = d
            item.revision += 1
            item.save(update_fields=["details", "revision"])
    elif action == "hatch":
        if value not in {"open", "closed"}:
            raise PhysicsError("Hatch must be opened or closed explicitly")
        item = state("access", target, lock=True)
        spec = item.reference
        room_id = getattr(getattr(actor, "location", None).db, "ox_space_id", None) if getattr(actor, "location", None) else None
        if room_id not in {spec["from"], spec["to"]}:
            raise PermissionError("Worker is not at the actual hatch")
        _crew_at(actor, room_id)
        if (not item.source_id.startswith("ACC-BR-") or
                "hatch" not in str(spec.get("kind", "")).lower()):
            raise PhysicsError("Machinery-indexed and cargo doors are not ordinary hatches")
        if item.condition in _BROKEN:
            raise PhysicsError("Damaged hatch cannot be safely actuated")
        if value == "open" and item.setting != "open":
            _hatch_open_preflight(item)
        before = _snapshot(item)
        if item.setting != value:
            item.setting = value
            item.revision += 1
            item.save(update_fields=["setting", "revision"])
    elif action == "service":
        if target not in PLANTS or value != "reset":
            raise PhysicsError("Only a local protection reset is currently modelled")
        item = state("equipment", target, lock=True)
        _crew_at(actor, item.space_id)
        d = dict(item.details)
        if (item.condition != "faulted"
                or d.get("physics_trip_reason") != "local_overtemperature_protection"
                or d.get("physics_online")
                or d.get("physics_commanded_on")
                or d.get("physics_startup_s", 0.0) != 0):
            raise PhysicsError("No safely isolated thermal protection trip to reset")
        zone = _topology()[1].get(target)
        if not zone or not _air_safe(state("pressure", zone, lock=True)):
            raise PhysicsError("Local air, temperature or persistent physical damage unsafe")
        if target in GENERATION_MW:
            breaker = state("isolator", "ISO-" + target, lock=True)
            if breaker.setting != "open" or breaker.condition in _BROKEN:
                raise PhysicsError("Generator feeder not positively isolated")
        before = _snapshot(item)
        d.pop("physics_trip_reason", None)
        d.pop("physics_trip_game_time", None)
        item.details = d
        item.condition = "serviceable"
        item.revision += 1
        item.save(update_fields=["details", "condition", "revision"])
    else:
        if value not in {"stop", "start"} or not target.startswith("PZ-HAB-"):
            raise PhysicsError("Only real HAB mist outlets can be commanded")
        item = state("pressure", target, lock=True)
        _, owners, _ = _topology()
        from world.ship_world import find_ship_space
        # The outlet is at the actual HAB pressure cell, not any remote room.
        if not getattr(actor, "location", None):
            raise PermissionError("Local worker required")
        room_id = getattr(actor.location.db, "ox_space_id", None)
        if room_id not in _topology()[0] or _topology()[0][room_id] != target:
            raise PermissionError("Worker is not inside the affected pressure zone")
        _crew_at(actor, room_id)
        if value == "start" and (item.details.get("physics_burn_kg_s", 0) <= 0
                                  or item.details.get("physics_mist_kg_s", 0) > 0):
            raise PhysicsError("No active ordinary fire to suppress or mist already running")
        if value == "start" and not bool(actor.db.ox_suit_verified):
            raise PermissionError("Verified breathing protection required near an active fire")
        # Delivery/power/water are rechecked every tick; command is not a
        # false assertion that an isolated fire main is delivering water.
        before = _snapshot(item)
        d = dict(item.details)
        d["physics_mist_kg_s"] = 0.5 if value == "start" else 0.0
        if d != item.details:
            item.details = d
            item.revision += 1
            item.save(update_fields=["details", "revision"])
    event = _event(item, "crew_" + action, before, actor=actor, request_id=request_id)
    # Store submitted argument in the immutable receipt, not just new state.
    after = dict(event.after)
    after["requested_value"] = value
    event.after = after
    event.save(update_fields=["after"])
    result = _receipt(event, request_id, actor, action, target)
    WorkReceipt.objects.create(
        request_id=request_id, actor_dbref=actor.dbref,
        target="ship_physics", operation=action,
        arguments={"target": target, "value": value},
        outcome=result, game_time=event.game_time,
    )
    return result


def local_physics_readout(actor, target):
    """Local equipment/air read; never grant a global hidden-casualty oracle."""
    location = getattr(actor, "location", None)
    room = getattr(getattr(location, "db", None), "ox_space_id", None)
    if not room:
        raise PermissionError("Stand at an installed ship compartment")
    if target == "cargo":
        if room not in {"CMD-CARGO", "ENG-CONTROL"} and not (
                room and room.endswith("-FREIGHT-LOCK")):
            raise PermissionError("Freight manifest is local to a cargo station")
        cargo = _clock().details.get("cargo", {})
        return {
            "unlocated_onboard_kg": cargo.get("unlocated_onboard_kg"),
            "declared_lots": len(cargo.get("lots", {})),
            "active_jobs": dict(cargo.get("jobs", {})),
            "verified_drums": list(cargo.get("verified_drums", [])),
            "scope": "local_cargo_manifest",
        }
    if target in ROTORS:
        permitted = ("ENG-CONTROL", "WR-ROTOR-MACHINERY") if target == "WR-01" else (
            ("ENG-CONTROL",) if target == "HAB" else
            (target + "-FREIGHT-LOCK", target + "-SERVICE-LOCK"))
        if room not in permitted:
            raise PermissionError("Rotary gauges are local to their machine")
        row = dict(_clock().details.get("rotors", {}).get(target, {}))
        if not row:
            raise PhysicsError("Rotor not commissioned")
        row["gravity_g"] = round(rotor_gravity({target: row}, target), 4)
        return {"rotor": target, **row, "scope": "local_rotary_gauge"}
    if target == "helm":
        _helm_at(actor)
        motion = dict(_clock().details.get("motion", {}))
        return {"motion": motion, "scope": "local_helm_gauge"}
    if target == "air":
        zone = _topology()[0].get(room)
        if not zone:
            raise PhysicsError("No verified bounded atmosphere here")
        item = state("pressure", zone)
        d = item.details
        if "physics_oxygen_kg" not in d:
            raise PhysicsError("Atmosphere has not been instrumented by a scenario")
        pressure_pa = (item.quantity * R_SPECIFIC_AIR * d["temperature_k"]
                       / d["gas_volume_m3"])
        oxygen_moles = d["physics_oxygen_kg"] / 0.032
        other_moles = max(0.0, item.quantity - d["physics_oxygen_kg"]) / 0.029
        o2_partial_pa = (pressure_pa * oxygen_moles / (oxygen_moles + other_moles)
                         if oxygen_moles + other_moles else 0.0)
        return {
            "zone": zone, "pressure_pa": round(pressure_pa, 1),
            "oxygen_partial_pa": round(o2_partial_pa, 1),
            "temperature_k": round(d["temperature_k"], 2),
            "oxygen_kg": round(d["physics_oxygen_kg"], 3),
            "smoke_kg": round(d["physics_smoke_kg"], 5),
            "scope": "local_scenario_reading_sensor_reliability_unmodelled",
        }
    for category in ("equipment", "isolator", "access"):
        qs = CanonicalShipState.objects.filter(pk=category + ":" + target)
        item = qs.first() if category == "access" else qs.filter(space_id=room).first()
        if category == "access" and item and room not in {
                item.reference.get("from"), item.reference.get("to")}:
            item = None
        if item:
            return {
                "id": target, "category": category, "condition": item.condition,
                "setting": item.setting,
                "online": item.details.get("physics_online"),
                "trip_reason": item.details.get("physics_trip_reason"),
                "scope": "local_scenario_reading_sensor_reliability_unmodelled",
            }
    raise PermissionError("That machinery is not at this character's location")


@transaction.atomic
def configure_scenario_casualty(cell_id, *, operator=False, leak_kg_s=None,
                                heat_kw=None, fire_fuel_kg=None,
                                fire_burn_kg_s=None, leak_isolator_id=None):
    """Explicit operator test fault. No crew command exposes this interface."""
    if not operator:
        raise PermissionError("Only world operators may introduce scenario casualties")
    _clock(lock=True)
    item = state("pressure", cell_id, lock=True)
    before = _snapshot(item)
    d = dict(item.details)
    if leak_kg_s is not None:
        d["physics_leak_kg_s"] = _positive(leak_kg_s, zero=True, maximum=50)
    if leak_isolator_id is not None:
        if leak_kg_s is None or leak_kg_s <= 0:
            raise PhysicsError("A valved leak needs a positive leak rate")
        iso = state("isolator", leak_isolator_id, lock=True)
        zones, _, _ = _topology()
        kind = str(iso.reference.get("kind", "")).lower()
        if (iso.reference.get("network") != "atmosphere"
                or zones.get(iso.space_id) != cell_id
                or not iso.reference.get("manual_operation")
                or not ("valve" in kind or "damper" in kind)):
            raise PhysicsError("Not an authored local manual atmosphere isolator")
        d["physics_leak_isolator_id"] = leak_isolator_id
    if heat_kw is not None:
        d["physics_background_kw"] = _positive(heat_kw, zero=True, maximum=1000)
    if fire_fuel_kg is not None or fire_burn_kg_s is not None:
        if fire_fuel_kg is None or fire_burn_kg_s is None:
            raise PhysicsError("A fire requires both a finite source and burn rate")
        if d["physics_fuel_kg"] > 0 or d["physics_burn_kg_s"] > 0:
            raise PhysicsError("Cannot mint fresh combustible material during an existing fire")
        d["physics_fuel_kg"] = _positive(fire_fuel_kg, maximum=500)
        d["physics_burn_kg_s"] = _positive(fire_burn_kg_s, maximum=5)
        d["physics_mist_kg_s"] = 0.0
    if d == item.details:
        return {"changed": False}
    item.details = d
    item.revision += 1
    item.save(update_fields=["details", "revision"])
    _event(item, "operator_scenario_casualty", before)
    return {"changed": True}


class ContinuousShipPhysicsClock(DefaultScript):
    """One persistent Evennia world timer; never invokes an LLM."""

    def at_script_creation(self):
        self.key = SCRIPT_KEY
        self.desc = "Opt-in continuous ship physics (authoritative game seconds)"
        self.interval = 10
        self.persistent = True
        self.start_delay = True

    def at_repeat(self):
        if CanonicalShipState.objects.filter(pk=CLOCK_KEY, condition="armed").exists():
            tick_continuous_physics()


def ensure_continuous_physics_clock():
    """Start ticking only on explicitly armed worlds, including after restart."""
    if not CanonicalShipState.objects.filter(pk=CLOCK_KEY, condition="armed").exists():
        return False
    from evennia.scripts.models import ScriptDB
    from evennia.utils.create import create_script
    if not ScriptDB.objects.filter(db_key=SCRIPT_KEY).exists():
        create_script("world.continuous_ship_physics.ContinuousShipPhysicsClock",
                      key=SCRIPT_KEY)
    return True
