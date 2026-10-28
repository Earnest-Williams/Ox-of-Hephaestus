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
from world.ship_ftl_navigation import (
    NavigationError, AUXILIARY_MW as FTL_AUX_MW,
    FIELD_HEAT_KW as FTL_HEAT_KW, prepare_leg, command_leg, advance_leg,
)
from world.ship_port_operations import (
    PORTALS, PORT_AUX_MW, contacts_active, commission_port_contact,
    register_external_consignment, start_port_job, step_port_jobs,
    command_port_job,
)
from world.ship_cargo_manifest import (
    CargoError, DRUMS as CARGO_DRUMS, CARGO_TRANSFER_MW,
    initial_cargo, validate_cargo,
    onboard_mass_kg, declare_cargo_lot, split_cargo_lot, verify_drum,
    drum_balance, start_freight_transfer, step_freight,
    restow_cargo_lot, unsecured_drum_loads,
    active_freight_mw,
)
from world.ship_cargo_environment import (
    CargoClimateError, initial_cargo_environment,
    validate_cargo_environment, survey_drum_environment,
    survey_sensitive_lot, inherit_split_care, set_cargo_target,
    step_cargo_environment,
)
from world.ship_motion_machinery import (
    DRUMS, ROTORS, RotorError, initial_rotors, set_rotor_command,
    step_rotors, motion_power_mw, rotor_gravity,
)
from world.ship_water_recycling import (
    WaterError, initial_water, step_water, validate_water,
    FIXED_KG as WASTE_FIXED_CAPACITY_KG,
)
from world.ship_water_materials import (
    register_source_survey, take_filter, load_filter, local_classified_deposit,
)
from world.ship_waste_offload import (
    RECEIVERS as WASTE_RECEIVERS, WASTE_PORT_AUX_MW, initial_offload,
    validate_offload, accept_berth, approve_route, prepare as prepare_waste_offload,
    command as command_waste_offload, step_offload,
    debit_ship_mass_for_waste,
)
from world.ship_equipment_repair import (
    REPAIR_CLASSES, MAX_HAND_PARTS_KG, initial_repairs, validate_repairs,
    take_parts, begin_repair, join_repair, step_repairs, move_toolkit,
)
from world.ship_freight_service import (
    GATES as FREIGHT_SERVICE_GATES, WORKSITES as FREIGHT_SERVICE_WORKSITES,
    QUALIFIED_ROLES as FREIGHT_SERVICE_ROLES, FreightServiceError,
    verify_as_built as verify_freight_service_source,
    initial_service_access, validate_service_access,
    secured as freight_service_secured,
    service_command as command_freight_service,
    service_hardware_ready,
)
from world.ship_waste_repair_world import (
    selected_waste_route, live_waste_route, safe_repair_target,
)
from world.ship_hull_restoration import (
    HullError, initial_hull, validate_hull, register_breach,
    effective_leak, expected_repair_condition, finish_hull_work,
)
from world.ship_indexed_personnel import (
    IndexedTransferError, initial_personnel_transfers,
    validate_personnel_transfers, indexed_mechanism_ready,
    step_personnel_transfers, finish_personnel_transfer,
)
from world.ship_hab_sync import (
    HabSyncError, initial_hab_sync, validate_hab_sync,
    command_hab_sync, step_hab_sync,
)
from world.ship_major_damage import (
    MajorDamageError, initial_major_damage, validate_major_damage,
    exterior_face_for, register_major_site, start_containment,
    step_containments, revoke_containment, external_repair_ready,
)
from world.ship_crew_physiology import (
    CrewPhysiologyError, validate_crew_health, step_crew_in_space,
)
from world.ship_crew_exposure import initial_exposure
from world.ship_crew_medical import (
    MedicalError, MEDICAL_ROLES, TREATMENT_ROOM, PHARMACY_ROOM, OBSERVATION_ROOM,
    TREATMENT_PANEL, TREATMENT_FEEDER, TREATMENT_POWER_NODE,
    CLINIC_ZONE, initial_medical, validate_medical, carry_medical_kit,
    begin_care, begin_observation, discharge_observation, step_care,
)
from world.ship_propulsion_proof import (
    DriveProofError, initial_drive_proof, validate_drive_proof,
    start_drive_proof, verify_drive_proof,
)
from world.ship_propulsion_exterior import (
    PlumeAccessError, FACE as PROPULSION_FACE,
    BASE as PROPULSION_BASE, LINK as PROPULSION_LINK,
    STATION as PROPULSION_STATION,
    GATE_S as PROPULSION_GATE_S,
    initial_propulsion_exterior, validate_propulsion_exterior,
    survey_propulsion_exterior, propulsion_face_safe,
    issue_propulsion_permit, inspect_propulsion,
    release_propulsion_permit,
)
from world.ship_exterior_radiators import (
    ExteriorRadiatorError, RADIATORS as EXTERIOR_RADIATORS,
    FACES as EXTERIOR_RADIATOR_FACES,
    initial_exterior_radiators, validate_exterior_radiators,
    survey_skin as survey_exterior_skin, step_skins as step_exterior_skins,
    work_face_safe as radiator_face_safe, issue_service as secure_radiator,
    release_service as release_radiator,
)
from world.ship_flywheel_maintenance import (
    FlywheelServiceError, MODULES as SERVICE_FLYWHEELS,
    initial_flywheel_service, validate_flywheel_service,
    issue_permit, release_permit, permit_live, module_dead,
    module_room, module_breaker, bus_safe, service_pulse,
    migrate_flywheel_service_v1, begin_rundown, advance_rundowns,
    halt_rundown,
)
from world.ship_hazardous_access import (
    BayAccessError, LOCKS as BAY_SERVICE_LOCKS, CYCLE_S as BAY_SERVICE_CYCLE_S,
    initial_bay_access, validate_bay_access, survey_bay,
    step_bay_transits, finish_bay_transit,
)
from world.ship_casualty_transport import (
    RescueError, INTERIOR_CARRY_KINDS, initial_rescue,
    validate_rescue, begin_rescue, step_rescue, finish_rescue,
)
from world.ship_auxiliary_electrical import (
    LOCAL_LOADS, MOTORS, PROTECTED_FIRE_MOTORS, protected_fire_ids,
    install_auxiliary_circuits, initial_local_backup,
    validate_local_backup, migrate_local_backup, survey_local_backup,
    set_local_mode,
    step_local_backup, motor_power, fire_pump_service_ready,
    allocate_lt_cooling,
)
from world.ship_equipment_wear import (
    initial_equipment_wear, validate_equipment_wear,
    survey_existing_wear, step_equipment_wear,
)
from world.ship_equipment_services import (
    SERVICE_LOADS, MANUAL_RESTART, WELD_CELLS,
    install_service_circuits, enrol_service_plant_controls,
    initial_service_operations,
    validate_service_operations, rearm_service_machine,
    step_service_operations, service_power, service_ids,
)
from world.ship_food_cultivation import (
    CultivationError, GROW_BAYS, initial_cultivation,
    validate_cultivation, survey_existing_nutrients,
    plan_irrigation, step_cultivation, harvest_cultivation,
    replenish_nutrients, migrate_cultivation_v1,
)
from world.ship_food_logistics import (
    FoodError, STORES as FOOD_STORES, NUTRIENT_STORES,
    GALLEY as FOOD_GALLEY, MESS as FOOD_MESS,
    WASTE_RECEIVERS as FOOD_WASTE_RECEIVERS, RECIPES as FOOD_RECIPES,
    MAX_CARRY_KG as FOOD_CARRY_KG, initial_food, validate_food,
    unconsumed_stored_kg, take_stored, collect_crop, deliver_to_galley,
    prepare_meal, take_meal, set_meal_in_mess, eat_meal, step_food,
    take_waste, deliver_waste, certify_nutrients, take_nutrients,
    install_nutrients, feed_patient,
)
from world.ship_instrumentation import (
    InstrumentError, initial_instrumentation, validate_instrumentation,
    sample_instrumentation, acknowledge_alarm, panel_readout, diagnostics,
    panel_selftest,
)
from world.ship_process_outputs import (
    METRICS as PROCESS_METRICS, FIELD as PROCESS_FIELD,
    AIR_TRAINS, AIR_HANDLERS, SPINE_FANS, WATER_MACHINES, BEARING_PUMPS,
    ProcessOutputError, step_process_output, proves_process_output,
    machine_depressurized, attributed_fire_discharge,
)
from world.ship_workshop_welding import (
    WeldError, CELLS as WELDING_CELLS, ROOM as WELDING_ROOM,
    ARC_KW as WELD_ARC_KW, initial_welding, validate_welding,
    certify_filler, issue_filler, start_weld, step_welds,
    take_slag, deposit_slag,
)
from world.ship_workshop_fabrication import (
    FabricationError, WORKROOM as FABRICATION_ROOM,
    MACHINES as FABRICATION_MACHINES, MAX_HAND_PARTS_KG as FABRICATION_HAND_KG,
    initial_fabrication, validate_fabrication, certify_blanks, pick_blank,
    start_batch, step_batches, credit_repair_parts,
    take_offcuts, deposit_offcuts,
)
from world.ship_workshop_dynamics import (
    WORKSHOP_DRIVES, GAUGE_FIELD, WorkshopGaugeError,
    step_workshop_gauge, machine_output_confirmed, machine_safely_stopped,
)
from world.ship_fault_recovery import (
    FaultRecoveryError, initial_fault_cases, inspect_fault, isolate_fault,
    begin_verified_work, finished_verified_work, check_repair,
    authorize_restart, verify_restart, feeders_for, verified_open_feeders,
    verified_restored_feeders, advance_restart_evidence, validate_fault_cases,
)
from world.ship_instrumentation_world import (
    original_panel_roster, observed_panel_evidence, local_relay_summary,
)
from world.ship_refuge_media_service import (
    initial_refuge_media_service, validate_refuge_media_service,
    load_refuge_media,
)
from world.ship_refuge_life_support import (
    RefugeAirError, REFUGE_PACKS, initial_refuge_scrubbers,
    validate_refuge_scrubbers, survey_refuge_scrubber,
    step_refuge_scrubbers,
)
from world.ship_electrical_power import (
    ElectricalError, BATTERIES as POWER_BANKS,
    FLYWHEELS as POWER_FLYWHEELS,
    initial_electrical, validate_electrical, migrate_v1_electrical,
    audit_topology, source_dispatch, survey_battery, survey_flywheel,
    register_fault, reset_protection, step_protection, step_energy,
)
from world.ship_eva_operations import (
    EVAError, LOCKS as EVA_LOCKS, SUIT_O2_KG, MAX_GAS_BUFFER_KG,
    initial_eva, validate_eva, lock_contract, suit_of, checkout_suit,
    stage_suit_oxygen,
    return_suit, begin_cycle, step_cycles, transfer_recovered_gas,
    step_suit_metabolism, begin_eva_transit, step_eva_transits,
    finish_eva_transit,
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
    "ECLSS-A-O2-GEN": True, "ECLSS-B-O2-GEN": True,
    "RAD-LT-1": True, "RAD-LT-2": True,
    "RAD-LT-3": True, "RAD-LT-4": True,
    "FIRE-PUMP-FWD": True, "FIRE-PUMP-AFT": True,
    # Individual fan motors are physical plants, not passive ductwork.
    **{f"HAB-{n:02d}-AHU": True for n in range(1, 9)},
    "SPINE-AIR-FWD": True, "SPINE-AIR-AFT": True,
    # Cargo-climate and cultivation controllers are standing services.
    # Welding and machine tools need a supervised local startup.
    **{name: name not in MANUAL_RESTART for name in SERVICE_LOADS},
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
# Fictional v0.5 contract: ~4 km/s full-load delta-v from 5,000 t
# reaction mass and <=0.001 g axial acceleration when fully loaded.
# This effective exhaust speed is selected to reproduce that setting,
# NOT a current-day engine design or electric generator specification.
DRIVE_THRUST_N = 11_645_000.0
DRIVE_EXHAUST_M_S = 960_000.0
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
    if (
        len(position) != 3 or len(velocity) != 3
        or not all(math.isfinite(x) for x in (*position, *velocity, fuel))
        or fuel < 0
        or not all(math.isfinite(x) and x >= 0
                   for x in (cargo, dry, ftl, fluids, capacity))
        or cargo > capacity or dry <= 0
    ):
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
        if item.details.get("water"):
            water = item.details["water"]
            result["water"] = {
                "working_kg": water["working_kg"],
                "local": water["local"], "fixed": water["fixed"],
                "cassettes": water["cassettes"],
                "cumulative": water["cumulative"],
                "filter_staged_kg": water["filter_staged_kg"],
                "filter_carried_kg": water["filter_carried_kg"],
                "source_surveys": water["source_surveys"],
                "potable_quarantined": water["potable_quarantined"],
                "reserve_released": water["reserve_released"],
                "waste_offload": {
                    "jobs": water["waste_offload"]["jobs"],
                    "delivered_kg": water["waste_offload"]["delivered_kg"],
                },
            }
        if item.details.get("food") is not None:
            food = item.details["food"]
            result["food"] = {
                "remaining_stored_kg": unconsumed_stored_kg(food),
                "fresh_collected_kg": food["meter"]["fresh_collected_kg"],
                "meal_count": sum(len(v) for v in food["meals"].values()),
                "waste_deposited_kg": food["meter"]["waste_deposited_kg"],
                "crew_nutrition": food["crew"],
            }
        if item.details.get("repairs"):
            jobs = item.details["repairs"]
            result["repairs"] = {
                "active": jobs["jobs"], "completed": jobs["completed"],
                "installed_spares_kg": jobs["installed_kg"],
                "carried_spares_kg": jobs["carried_kg"],
                "toolkits_at_crib": jobs["toolkits_at_crib"],
                "toolkit_carriers": jobs["toolkit_carriers"],
                "site_surveys": jobs["site_surveys"],
            }
        if item.details.get("hab_sync") is not None:
            result["hab_sync"] = item.details["hab_sync"]
        if item.details.get("personnel_transfers") is not None:
            result["personnel_transfers"] = item.details["personnel_transfers"]
        if item.details.get("major_damage") is not None:
            result["major_damage"] = item.details["major_damage"]
        if item.details.get("freight_service") is not None:
            result["freight_service"] = item.details["freight_service"]
        if item.details.get("medical") is not None:
            result["medical"] = item.details["medical"]
        if item.details.get("rescue") is not None:
            result["rescue"] = item.details["rescue"]
        if item.details.get("bay_access") is not None:
            result["bay_access"] = item.details["bay_access"]
        if item.details.get("flywheel_service") is not None:
            result["flywheel_service"] = item.details["flywheel_service"]
        if item.details.get("exterior_radiators") is not None:
            result["exterior_radiators"] = item.details["exterior_radiators"]
        if item.details.get("propulsion_exterior") is not None:
            result["propulsion_exterior"] = item.details["propulsion_exterior"]
        if item.details.get("eva") is not None:
            system = item.details["eva"]
            result["eva"] = {
                "locks": system["locks"],
                "transits": system["transits"],
                "issued_kg": system["issued_kg"],
                "charged_kg": system["charged_kg"],
                "consumed_oxygen_kg": system["consumed_oxygen_kg"],
                "suits": {key: {
                    "holder": value["holder"],
                    "oxygen_kg": value["exposure"]["suit_oxygen_kg"],
                    "condition": value["exposure"]["condition"]}
                    for key, value in system["suits"].items()},
            }
        if item.details.get("local_backup") is not None:
            result["local_backup"] = item.details["local_backup"]
        if item.details.get("electrical") is not None:
            result["generator_cartridges"] = {
                "baseline_kg": item.details.get("generator_cartridge_baseline_kg"),
                "spent_housings_kg": item.details.get("generator_spent_cartridge_kg"),
            }
            power = item.details["electrical"]
            result["electrical"] = {
                "worksite_surveys": power["worksite_surveys"],
                "meter": power["meter"], "last": power["last"],
                "banks": power["banks"],
                "flywheels": {
                    "commissioned_modules": len(power.get("flywheels", {})),
                    "rated_capacity_kwh": sum(
                        x["capacity_kwh"] for x in power.get("flywheels", {}).values()),
                    "stored_kwh": sum(
                        x["charge_kwh"] for x in power.get("flywheels", {}).values())},
                "shore": power["shore"],
                "faults": power["faults"], "sync": power["sync"],
            }
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
                "expended_ftl_fuel_kg": 0.0,
                "ftl_leg": None,
                "nav_location": "unassigned_reference_origin",
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
def commission_g19_electrical(*, operator_approved=False):
    """Install an independent electrical ledger on the existing ship clock.

    Do not default batteries to full or assume a shore station exists. Every
    node, breaker and feeder remains the original installed Evennia object.
    """
    if not operator_approved:
        raise PermissionError("Only the world operator may commission electrical plant")
    _require_installed()
    item = _clock(lock=True)
    if item.details.get("electrical") is not None:
        install_auxiliary_circuits(CanonicalShipState)
        install_service_circuits(CanonicalShipState)
        newly_enrolled = enrol_service_plant_controls(CanonicalShipState)
        upgraded = migrate_v1_electrical(item.details["electrical"])
        local_old = item.details.get("local_backup")
        local_upgraded = migrate_local_backup(
            local_old if local_old is not None else initial_local_backup())
        refuge_old = item.details.get("refuge_scrubbers")
        refuge_upgraded = (refuge_old if refuge_old is not None
                          else initial_refuge_scrubbers())
        media_old = item.details.get("refuge_media_service")
        media_upgraded = (media_old if media_old is not None
                          else initial_refuge_media_service())
        try:
            validate_refuge_media_service(media_upgraded)
        except RefugeAirError as exc:
            raise PhysicsError(str(exc)) from exc
        cargo_climate_old = item.details.get("cargo_environment")
        cargo_climate_new = (cargo_climate_old if cargo_climate_old is not None
                             else initial_cargo_environment())
        try:
            validate_cargo_environment(cargo_climate_new, item.details["cargo"])
        except CargoClimateError as exc:
            raise PhysicsError(str(exc)) from exc
        services_old = item.details.get("service_operations")
        services_upgraded = (services_old if services_old is not None
                             else initial_service_operations())
        wear_old = item.details.get("equipment_wear")
        fitted_service_equipment = {
            unit.source_id: unit for unit in
            CanonicalShipState.objects.filter(
                category="equipment", source_id__in=SERVICE_LOADS)
        }
        wear_new = (wear_old if wear_old is not None
                    else initial_equipment_wear(
                        services_upgraded, fitted_service_equipment))
        try:
            validate_service_operations(services_upgraded)
            validate_equipment_wear(wear_new, services_upgraded)
        except ElectricalError as exc:
            raise PhysicsError(str(exc)) from exc
        try:
            validate_refuge_scrubbers(refuge_upgraded)
        except RefugeAirError as exc:
            raise PhysicsError(str(exc)) from exc
        fuel_needs_migration = "generator_cartridge_baseline_kg" not in item.details
        if (upgraded != item.details["electrical"]
                or local_upgraded != local_old
                or refuge_upgraded != refuge_old
                or media_upgraded != media_old
                or cargo_climate_new != cargo_climate_old
                or services_upgraded != services_old
                or wear_new != wear_old or fuel_needs_migration
                or newly_enrolled):
            previous = _snapshot(item)
            details = dict(item.details)
            details["electrical"] = upgraded
            details["local_backup"] = local_upgraded
            details["refuge_scrubbers"] = refuge_upgraded
            details["refuge_media_service"] = media_upgraded
            details["cargo_environment"] = cargo_climate_new
            details["service_operations"] = services_upgraded
            details["equipment_wear"] = wear_new
            if fuel_needs_migration:
                stock = state("inventory", "INV-GEN-CART", lock=True)
                if stock.quantity is None or not math.isfinite(stock.quantity) or stock.quantity < 0:
                    raise PhysicsError("Existing generator cartridges are not surveyed")
                details["generator_cartridge_baseline_kg"] = stock.quantity * 1000.0
                details["generator_spent_cartridge_kg"] = 0.0
            item.details = details
            item.revision += 1
            item.save(update_fields=["details", "revision"])
            _event(item, "g19_electrical_nonresetting_v2_migration", previous)
            return {"commissioned": False, "migrated": True}
        if "local_backup" not in item.details:
            previous = _snapshot(item)
            details = dict(item.details)
            details["local_backup"] = initial_local_backup()
            item.details = details
            item.revision += 1
            item.save(update_fields=["details", "revision"])
            _event(item, "g19_local_backup_nonresetting_install", previous)
            return {"commissioned": False, "local_backup_installed": True}
        return {"commissioned": False, "already_present": True}
    nodes = list(CanonicalShipState.objects.filter(category="node"))
    edges = list(CanonicalShipState.objects.filter(category="edge"))
    switches = {row.source_id: row for row in
                CanonicalShipState.objects.filter(category="isolator")}
    try:
        node_map, edge_map, switch_map = audit_topology(
            nodes, edges, switches, strict=True)
    except ElectricalError as exc:
        raise PhysicsError(str(exc)) from exc
    cartridges = state("inventory", "INV-GEN-CART", lock=True)
    if (cartridges.quantity is None or not math.isfinite(cartridges.quantity)
            or cartridges.quantity < 0):
        raise PhysicsError("Fitted generator-cartridge inventory is not verified")
    before = _snapshot(item)
    d = dict(item.details)
    install_auxiliary_circuits(CanonicalShipState)
    install_service_circuits(CanonicalShipState)
    enrol_service_plant_controls(CanonicalShipState)
    d["electrical"] = initial_electrical()
    d["local_backup"] = initial_local_backup()
    d["refuge_scrubbers"] = initial_refuge_scrubbers()
    d["refuge_media_service"] = initial_refuge_media_service()
    d["cargo_environment"] = initial_cargo_environment()
    d["service_operations"] = initial_service_operations()
    d["equipment_wear"] = initial_equipment_wear(
        d["service_operations"], {
            unit.source_id: unit for unit in
            CanonicalShipState.objects.filter(
                category="equipment", source_id__in=SERVICE_LOADS)})
    d["generator_cartridge_baseline_kg"] = cartridges.quantity * 1000.0
    d["generator_spent_cartridge_kg"] = 0.0
    item.details = d
    item.revision += 1
    item.save(update_fields=["details", "revision"])
    _event(item, "g19_electrical_commissioned", before)
    return {"commissioned": True, "nodes": len(node_map),
            "feeders": len(edge_map), "breakers": len(switch_map),
            "rated_battery_kwh": 0.0, "shore_connected": False}



@transaction.atomic
def commission_g19_cultivation(*, operator_approved=False):
    """Install only real, empty grow beds after electricity and water."""
    if not operator_approved:
        raise PermissionError("Original growing beds need operator commissioning")
    clock = _clock(lock=True)
    if clock.details.get("cultivation") is not None:
        old = clock.details["cultivation"]
        revised = migrate_cultivation_v1(old)
        if revised != old:
            before = _snapshot(clock)
            d = dict(clock.details)
            d["cultivation"] = revised
            clock.details = d
            clock.revision += 1
            clock.save(update_fields=["details", "revision"])
            _event(clock, "g19_cultivation_nonresetting_migration", before)
            return {"commissioned": False, "migrated": True}
        return {"commissioned": False}
    if (clock.details.get("service_operations") is None
            or clock.details.get("water") is None):
        raise PhysicsError("Commission real local grow power and water first")
    for number, room in GROW_BAYS.items():
        for suffix in ("CTRL", "NUTRIENT"):
            machine = state("equipment", f"GROW-{number}-{suffix}")
            if machine.space_id != room:
                raise PhysicsError("Source grow skid moved away from original bed")
        if _topology()[0].get(room) != f"PZ-HAB-{int(room[4:6]):02d}":
            raise PhysicsError("No original bounded crop-room atmosphere")
    before = _snapshot(clock)
    details = dict(clock.details)
    details["cultivation"] = initial_cultivation()
    clock.details = details
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_fitted_cultivation_commissioned", before)
    return {"commissioned": True, "beds": len(GROW_BAYS)}


@transaction.atomic
def survey_g19_cultivation_nutrients(*, operator_approved=False,
                                    bay=None, charge_kg=None):
    """One nonrenewable attestation of pre-existing charged skid material."""
    if not operator_approved:
        raise PermissionError("Only the operator can attest fitted nutrient inventory")
    if type(bay) is not int or bay not in GROW_BAYS:
        raise PhysicsError("No such original crop bed")
    clock = _clock(lock=True)
    ledger = clock.details.get("cultivation")
    if ledger is None:
        raise PhysicsError("Fitted cultivation plant has not been commissioned")
    try:
        revised = survey_existing_nutrients(
            ledger, bay=bay, charge_kg=charge_kg)
    except CultivationError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    details = dict(clock.details)
    details["cultivation"] = revised
    clock.details = details
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "operator_original_nutrient_charge_survey", before)
    return {"bay": bay, "surveyed_kg": charge_kg}


@transaction.atomic
def commission_g19_instrumentation(*, operator_approved=False):
    """Commission 116 REAL power-fed panels without fake sensors or reset."""
    if not operator_approved:
        raise PermissionError("Only operator may validate installed local instruments")
    _require_installed()
    clock = _clock(lock=True)
    if clock.details.get("electrical") is None:
        raise PhysicsError("Installed electrical distribution must be commissioned")
    roster, zones = original_panel_roster(load_candidate())
    installed = {row.source_id: row for row in CanonicalShipState.objects.filter(
        category="equipment", source_id__in=roster)}
    if len(installed) != len(roster):
        raise PhysicsError("Missing one of 116 original local panel units")
    for name, room in roster.items():
        if installed[name].space_id != room:
            raise PhysicsError("Original panel relocated without wiring")
        node = state("node", "NODE-" + name)
        if (node.reference.get("network") != "power"
                or node.reference.get("owner_id") != name):
            raise PhysicsError("Local panel not linked to genuine power node")
    previous = clock.details.get("instrumentation")
    if previous is not None:
        try:
            validate_instrumentation(previous, panel_rooms=roster)
        except InstrumentError as exc:
            raise PhysicsError(str(exc)) from exc
        return {"commissioned": False, "fitted_panels": len(roster)}
    try:
        ledger = initial_instrumentation(
            roster, zones, start_s=clock.details["last_game_time"])
        validate_instrumentation(ledger, panel_rooms=roster)
    except InstrumentError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    d = dict(clock.details)
    d["instrumentation"] = ledger
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_original_local_instrumentation_commissioned", before)
    return {"commissioned": True, "fitted_panels": len(roster),
            "last_sample_game_time": None}


def _instrument_power_grid(details):
    installed = {r.source_id: r for r in CanonicalShipState.objects.filter(
        category="equipment")}
    edges = list(CanonicalShipState.objects.filter(category="edge"))
    isolators = {r.source_id: r for r in CanonicalShipState.objects.filter(
        category="isolator")}
    grid = _power(installed, edges, isolators, details["load_profile"],
                  ledger=details.get("electrical"),
                  moored=contacts_active(details["cargo"]))
    return grid, installed


def _instrument_local_panel(actor, panel, room, ledger, *, require_live=True):
    info = ledger["panels"].get(panel)
    if info is None:
        raise PhysicsError("No commissioned original local instrument face")
    if info["room"] != room:
        raise PermissionError("No remote access to another shipboard panel")
    installed = state("equipment", panel)
    grid, equipment = _instrument_power_grid(_clock().details)
    if (installed.space_id != room or installed.condition in _BROKEN
            or "NODE-" + panel not in grid["nodes"]):
        if require_live:
            raise PhysicsError("Physical local panel unpowered or damaged")
        return False
    # An unpressurised original switchgear bay requires the same surveyed
    # breathing protection as manual electrical work; no free EVA oracle.
    zone = _topology()[0].get(room)
    if not (isinstance(zone, str) and zone.startswith("PZ-")):
        _electrical_crew_air_gate(actor, room, _clock().details["electrical"])
    return True


@transaction.atomic
def commission_g19_food(*, operator_approved=False):
    """Commission original 5 food stores and galley without minting inventory."""
    if not operator_approved:
        raise PermissionError("Only the operator may activate finite provisions")
    clock = _clock(lock=True)
    if clock.details.get("food") is not None:
        validate_food(clock.details["food"], inventory_kg=(
            state("inventory", "INV-FOOD-LONG-LEG").quantity * 1000.0))
        return {"commissioned": False}
    if (clock.details.get("water") is None or
            clock.details.get("service_operations") is None):
        raise PhysicsError("Food operations require actual water and electrical distribution")
    installed = load_candidate()
    candidates = {entry["id"]: entry for entry in installed["inventories"]}
    original = candidates.get("INV-FOOD-LONG-LEG", {})
    if (original.get("location_allocations_t") != {
            room: mass / 1000.0 for room, mass in FOOD_STORES.items()}
            or original.get("dehydrated_fallback_stock_t") != 24.82
            or original.get("conventional_stock_t") != 31.97):
        raise PhysicsError("Original five-store food manifest identity drifted")
    zones = _topology()[0]
    for room in (*FOOD_STORES, FOOD_GALLEY, FOOD_MESS, *GROW_BAYS.values()):
        if not zones.get(room, "").startswith("PZ-"):
            raise PhysicsError("Food worksite has no original real pressure cell")
    if state("equipment", "HAB-02-GALLEY-LP").space_id != FOOD_GALLEY:
        raise PhysicsError("Original galley electrical service panel missing")
    inventory = state("inventory", "INV-FOOD-LONG-LEG", lock=True)
    food = initial_food(inventory_kg=inventory.quantity * 1000.0)
    validate_food(food, inventory_kg=inventory.quantity * 1000.0)
    before = _snapshot(clock)
    d = dict(clock.details)
    d["food"] = food
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_food_stores_commissioned", before)
    return {"commissioned": True, "stores": len(FOOD_STORES),
            "manifest_kg": inventory.quantity * 1000.0}


@transaction.atomic
def survey_g19_food_nutrient_stock(*, operator_approved=False,
                                   room_id=None, kg=None):
    """Classify a REAL, already-located subset of the existing spares stock."""
    if not operator_approved:
        raise PermissionError("Only the operator can classify existing spare packs")
    clock = _clock(lock=True)
    d = dict(clock.details)
    food, water = d.get("food"), d.get("water")
    if food is None or water is None:
        raise PhysicsError("Food and physical spare custody not commissioned")
    if room_id not in NUTRIENT_STORES:
        raise PhysicsError("Nutrient packs not at an original spares rack")
    available = water["source_surveys"].get("INV-SPARES", {}).get(room_id, 0.0)
    try:
        revised = certify_nutrients(food, room=room_id, kg=kg,
                                    already_surveyed_kg=available)
    except FoodError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    d["food"] = revised
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_nutrient_stock_classified", before)
    return {"store": room_id, "verified_nutrients_kg": kg}


@transaction.atomic
def survey_g19_electrical_worksite(*, operator_approved=False, room_id=None):
    """Survey an actual nonpressurised generator switch room for suited work.

    This never renders the room breathable. Real individual protective gear
    is separately checked every time a crew member operates switchgear.
    """
    if not operator_approved:
        raise PermissionError("Physical electrical worksite survey is operator-only")
    if room_id not in {"GEN-M-ROOM", "GEN-A-ROOM", "GEN-B-ROOM",
                        "F1-BAY", "F2-BAY",
                        *(f"BE-{n:02d}-SVC" for n in range(1, 13))}:
        raise PhysicsError("Only fitted unpressurised electrical service bays may be surveyed")
    from world.ship_world import find_ship_space
    if (find_ship_space(room_id) is None
            or _topology()[0].get(room_id) not in {None, "VACUUM"}):
        raise PhysicsError("Power bay is not the fitted unpressurised worksite")
    if room_id.endswith("-ROOM"):
        if state("equipment", room_id.removesuffix("-ROOM")).space_id != room_id:
            raise PhysicsError("Generator worksite and real installed plant disagree")
    elif re.fullmatch(r"BE-(0[1-9]|1[0-2])-SVC", room_id):
        if state("equipment", room_id.replace("-SVC", "-BAT")).space_id != room_id:
            raise PhysicsError("Local rescue battery is not fitted in this bearing station")
    elif state("equipment", room_id.replace("-BAY", "-BUS")).space_id != room_id:
        raise PhysicsError("Flywheel bank and local power room disagree")
    import copy
    item = _clock(lock=True)
    details = dict(item.details)
    if "electrical" not in details:
        raise PhysicsError("G19 electrical power not commissioned")
    grid = copy.deepcopy(details["electrical"])
    if grid["worksite_surveys"].get(room_id) == "suited_service":
        return {"changed": False, "room_id": room_id}
    before = _snapshot(item)
    grid["worksite_surveys"][room_id] = "suited_service"
    validate_electrical(grid)
    details["electrical"] = grid
    item.details = details
    item.revision += 1
    item.save(update_fields=["details", "revision"])
    _event(item, "g19_electrical_hazardous_worksite_survey", before)
    return {"changed": True, "room_id": room_id}



def _flywheel_suit_ready(actor, room, details):
    """No legacy suit attestation is accepted in the two vacuum flywheel bays.

    Real issued EVA gear, its finite oxygen and chronic injury record, the
    actually surveyed lock and existing operator-attested worksite must all
    describe the SAME currently present engineer.
    """
    if room not in {"F1-BAY", "F2-BAY"} or actor is None:
        return False
    if (getattr(getattr(getattr(actor, "location", None), "db", None),
                "ox_space_id", None) != room
            or getattr(actor.db, "ox_terminal_dead", False)
            or getattr(actor.db, "crew_role", None) not in AUTHORISED_ROLES
            or _topology()[0].get(room) != "VACUUM"):
        return False
    health = CanonicalShipState.objects.filter(
        pk="crew_health:" + actor.dbref, source_model=MODEL).first()
    if health is None or health.condition not in {"fit", "impaired"}:
        return False
    ea, bay = details.get("eva"), details.get("bay_access")
    power = details.get("electrical")
    if (not ea or not bay or not power
            or room not in bay["surveyed_bays"]
            or power["worksite_surveys"].get(room) != "suited_service"
            or actor.dbref in ea["transits"]
            or actor.dbref in bay["jobs"]):
        return False
    _, suit = suit_of(ea, actor.dbref)
    return bool(
        suit is not None and suit["integrity"] >= .8
        and suit["exposure"]["condition"] not in {
            "incapacitated", "critical", "dead"}
        and suit["exposure"]["suit_oxygen_kg"] > 0.01)


def _electrical_crew_air_gate(actor, room, electrical):
    """No breathable-air guess in inherited generator rooms."""
    zone = _topology()[0].get(room)
    if isinstance(zone, str) and zone.startswith("PZ-"):
        if not _air_safe(state("pressure", zone)):
            raise PhysicsError("Local switchgear room has unsafe breathing air")
        return
    if room in {"F1-BAY", "F2-BAY"}:
        if not _flywheel_suit_ready(actor, room, _clock().details):
            raise PhysicsError("Flywheel work requires a real issued suit and surveyed service airlock")
        return
    if (zone not in {None, "VACUUM"}
            or electrical["worksite_surveys"].get(room) != "suited_service"
            or not bool(getattr(actor.db, "ox_suit_verified", False))):
        raise PhysicsError("Unpressurised switchgear requires site survey and verified suited engineer")


@transaction.atomic
def survey_g19_electrical_source(*, operator_approved=False, source,
                                 capacity_kwh=None, initial_kwh=None,
                                 max_charge_mw=None, max_discharge_mw=None,
                                 rated_mw=None):
    """Explicit operator measurement; only an installed source may be rated."""
    if not operator_approved:
        raise PermissionError("Operator attestation of physical source required")
    _require_installed()
    item = _clock(lock=True)
    d = dict(item.details)
    if "electrical" not in d:
        raise PhysicsError("Commission electrical network before rating sources")
    import copy
    e = copy.deepcopy(d["electrical"])
    if source in LOCAL_LOADS:
        if rated_mw is not None or max_charge_mw is not None or max_discharge_mw is not None:
            raise PhysicsError("Local DC store requires independently measured capacity and charge")
        battery = state("equipment", source, lock=True)
        room, consumer, panel, _, _ = LOCAL_LOADS[source]
        if battery.space_id != room or battery.condition in _BROKEN:
            raise PhysicsError("Local emergency source is not healthy at its installed site")
        for pk in ("node:" + "NODE-G19-BAT-" + source,
                   "edge:" + "EDGE-G19-LOCAL-" + source,
                   "isolator:" + "ISO-G19-LOCAL-" + source,
                   "edge:" + "EDGE-G19-CHARGE-" + source,
                   "isolator:" + "ISO-G19-CHARGE-" + source):
            if not CanonicalShipState.objects.filter(pk=pk).exists():
                raise PhysicsError("Local backup wiring not installed")
        try:
            backup = survey_local_backup(
                d["local_backup"], source, capacity_kwh=capacity_kwh,
                initial_kwh=initial_kwh)
        except ElectricalError as exc:
            raise PhysicsError(str(exc)) from exc
        before = _snapshot(item)
        d["local_backup"] = backup
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
        _event(item, "g19_local_battery_source_survey", before)
        return {"source": source, "rated": True, "local_only": True}
    if source not in (*POWER_BANKS, *POWER_FLYWHEELS, "SHORE-PWR"):
        raise PhysicsError("Unknown installed electrical source")
    # Every commissioned store has its own real equipment and power port.
    equipment = state("equipment", source, lock=True)
    source_is_flywheel = source in POWER_FLYWHEELS
    if (source_is_flywheel and (
            source in (d.get("flywheel_service") or
                       {"permits": {}})["permits"]
            or source in (d.get("flywheel_service") or
                          {"rundowns": {}}).get("rundowns", {}))):
        raise PhysicsError("An open maintenance lockout prevents source resurvey")
    feeder_id = ("EDGE-PWR-" if source_is_flywheel else "EDGE-") + source
    node_id = ("NODE-PWR-" if source_is_flywheel else "NODE-") + source
    feeder = state("edge", feeder_id, lock=True)
    node = state("node", node_id, lock=True)
    if (equipment.condition in _BROKEN or feeder.condition in _BROKEN
            or node.reference.get("network") != "power"
            or feeder.reference.get("network") != "power"):
        raise PhysicsError("Source, feeder or power terminal unverified")
    try:
        if source in POWER_BANKS:
            if rated_mw is not None:
                raise ElectricalError("Battery needs independently rated energy and current")
            # The two fitted banks have distinct 8/12 MWh design capacity
            # ratings. A site survey may derate a damaged/refitted bank but
            # cannot attest an arbitrary store larger than the installed one.
            nominal_mwh = equipment.reference.get("attributes", {}).get("MWh")
            if (not isinstance(nominal_mwh, (int, float))
                    or isinstance(nominal_mwh, bool)
                    or not math.isfinite(nominal_mwh)
                    or nominal_mwh <= 0
                    or not isinstance(capacity_kwh, (int, float))
                    or isinstance(capacity_kwh, bool)
                    or not math.isfinite(capacity_kwh)
                    or capacity_kwh > nominal_mwh * 1000.0 + 1e-7):
                raise ElectricalError("Battery survey exceeds fitted finite nameplate energy")
            e = survey_battery(
                e, source, capacity_kwh=capacity_kwh,
                charge_kwh=initial_kwh, max_charge_mw=max_charge_mw,
                max_discharge_mw=max_discharge_mw)
        elif source_is_flywheel:
            if rated_mw is not None:
                raise ElectricalError("Fitted flywheel needs a measured energy and converter rating")
            nominal_mwh = equipment.reference.get("attributes", {}).get(
                "deliverable_MWh_nominal")
            if (not isinstance(nominal_mwh, (int, float))
                    or isinstance(nominal_mwh, bool)
                    or not math.isfinite(nominal_mwh)
                    or not isinstance(capacity_kwh, (int, float))
                    or isinstance(capacity_kwh, bool)
                    or not math.isfinite(capacity_kwh)
                    or capacity_kwh > nominal_mwh * 1000.0 + 1e-7):
                raise ElectricalError("Flywheel measurement exceeds fitted nameplate")
            e = survey_flywheel(
                e, source, capacity_kwh=capacity_kwh,
                charge_kwh=initial_kwh, max_charge_mw=max_charge_mw,
                max_discharge_mw=max_discharge_mw)
        else:
            validate_electrical(e)
            if e["shore"] is not None:
                raise ElectricalError("Shore source has already been rated")
            mw = float(rated_mw)
            if not math.isfinite(mw) or not 0 < mw <= 3.3:
                raise ElectricalError("Unproven or excessive shore supply")
            e["shore"] = {"rated_mw": mw, "connected": False,
                          "import_kwh": 0.0}
            validate_electrical(e)
    except (TypeError, ValueError, ElectricalError) as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(item)
    d["electrical"] = e
    item.details = d
    item.revision += 1
    item.save(update_fields=["details", "revision"])
    _event(item, "g19_electrical_source_survey", before)
    return {"source": source, "rated": True, "operator_verified": True}


@transaction.atomic
def survey_g19_refuge_sorbent(*, operator_approved=False, pack_id,
                              remaining_capacity_kg):
    """Attest finite actual medium in one fitted HAB refuge air pack.

    This never creates new gas, loads arbitrary refill stock or assumes an
    old ship's original sorbent cartridges were fully replenished.
    """
    if not operator_approved:
        raise PermissionError("An operator must survey installed refuge media")
    _require_installed()
    item = _clock(lock=True)
    details = dict(item.details)
    if "electrical" not in details or "refuge_scrubbers" not in details:
        raise PhysicsError("Refuge package requires G19 electrical commissioning")
    if pack_id not in REFUGE_PACKS:
        raise PhysicsError("Not an installed independently powered refuge package")
    room, _battery_id = REFUGE_PACKS[pack_id]
    installed = state("equipment", pack_id, lock=True)
    attrs = installed.reference.get("attributes", {})
    if (installed.space_id != room or installed.condition in _BROKEN
            or installed.reference.get("kind") != "emergency_life_support"
            or attrs.get("people") != 40 or attrs.get("duration_h") != 72
            or attrs.get("independent_scrubber") is not True):
        raise PhysicsError("Installed refuge equipment does not match the fitted design")
    if _topology()[0].get(room) not in {
            "PZ-HAB-04", "PZ-HAB-08"}:
        raise PhysicsError("Refuge lacks its original pressure-cell envelope")
    try:
        replacement = survey_refuge_scrubber(
            details["refuge_scrubbers"], pack_id,
            remaining_capacity_kg=remaining_capacity_kg)
    except RefugeAirError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(item)
    details["refuge_scrubbers"] = replacement
    item.details = details
    item.revision += 1
    item.save(update_fields=["details", "revision"])
    _event(item, "g19_finite_refuge_sorbent_survey", before)
    return {"pack": pack_id, "remaining_capacity_kg": remaining_capacity_kg,
            "surveyed": True}


@transaction.atomic
def configure_g19_electrical_fault(*, operator_approved=False, breaker_id,
                                   rating_mw, measured_mw):
    """A real breaker/circuit gets an explicit overcurrent witness.

    Trip and persistent opening then happen in normal ship-time physics.
    Altering a scenario fault is operator-only, never crew magic repair.
    """
    if not operator_approved:
        raise PermissionError("Operator fault observation required")
    item = _clock(lock=True)
    d = dict(item.details)
    if "electrical" not in d:
        raise PhysicsError("Electrical plant not commissioned")
    breaker = state("isolator", breaker_id, lock=True)
    if (breaker.reference.get("network")
            not in {"power", "g19_motor", "g19_motor_protected",
                "g19_local_dc", "g19_local_charger",
                "g19_equipment_service"}
            or breaker.condition in _BROKEN):
        raise PhysicsError("No usable installed electrical breaker at this site")
    try:
        e = register_fault(d["electrical"], breaker_id,
                           rating_mw=rating_mw, observed_mw=measured_mw)
    except ElectricalError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(item)
    d["electrical"] = e
    item.details = d
    item.revision += 1
    item.save(update_fields=["details", "revision"])
    _event(item, "g19_electrical_fault_observed", before)
    return {"breaker": breaker_id, "measured_mw": measured_mw,
            "rating_mw": rating_mw}


@transaction.atomic
def commission_g19_water(*, operator_approved=False):
    """Attach the designed potable and disposal circuit to an existing epoch.

    G18 scenarios have no implicit 39 t water transfer or sanitation work.
    This one-time G19 commission respects all existing finite stocks and does
    not reset already injected faults, crew positions or the physics clock.
    """
    if not operator_approved:
        raise PermissionError("Water/waste commissioning is operator-only")
    _require_installed()
    clock = _clock(lock=True)
    if clock.details.get("water") is not None:
        return {"commissioned": False}
    tank = state("equipment", "POTABLE-TANK-MAIN")
    if tank.reference.get("attributes", {}).get("working_inventory_t_approx") != 39:
        raise PhysicsError("Installed 39 t working water reference missing")
    required = [
        "LP-WATER-FWD", "FIXED-GREY-HOLD", "FIXED-BLACK-HOLD",
        "WATER-PROC-A", "WATER-PROC-B", "WASTE-PROC-A", "WASTE-PROC-B",
        "WASTE-RESIDUE-HOLD-A", "WASTE-RESIDUE-HOLD-B",
        "IND-SCRAP-HOLD-A", "IND-SCRAP-HOLD-B",
        "HAZ-ISO-HOLD-A", "HAZ-ISO-HOLD-B",
    ]
    if (CanonicalShipState.objects.filter(
            key__in=["equipment:" + k for k in required]).count() != len(required)):
        raise PhysicsError("Water or physically segregated disposal plant missing")
    stocks = {name: state("inventory", ident).quantity for name, ident in (
        ("normal", "INV-WATER-NORMAL"),
        ("reserve", "INV-WATER-RESERVE"),
        ("sanitary", "INV-WASTE-RESIDUE"),
        ("industrial", "INV-INDUSTRIAL-SCRAP"),
        ("hazardous", "INV-HAZARDOUS-RESIDUE"),
    )}
    if any(x is None for x in stocks.values()) or any(
            stocks[k] != 0 for k in ("sanitary", "industrial", "hazardous")):
        raise PhysicsError("Generated waste stock must be explicitly reconciled before commission")
    water = initial_water()
    validate_water(water, {k: v * 1000.0 for k, v in stocks.items()})
    before = _snapshot(clock)
    d = dict(clock.details)
    d["water"] = water
    d["water_commissioned_at"] = d["last_game_time"]
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "commission_g19_water", before)
    return {"commissioned": True, "working_kg": water["working_kg"],
            "normal_kg": stocks["normal"] * 1000,
            "protected_kg": stocks["reserve"] * 1000}


def _water_hardware(water, equipment, edges, isolators, nodes, power, *, motor_ready=None):
    """Actual running equipment and conducting wet networks, not diagram links."""
    def sound(name):
        row = equipment.get(name)
        return bool(row and row.condition not in _BROKEN)

    def owned(network, owner):
        return [n.source_id for n in nodes
                if n.reference.get("network") == network
                and n.reference.get("owner_id") == owner]

    def rated_wet_valve_conducts(identifier):
        """The v0.5 manual/remote *rotary isolation* is a water valve.

        The generic actuator parser recognises only names containing
        "valve"/"damper"; these eight fitted valves have a more precise
        original machinery classification. Accept *only* their known
        physical identities and medium/side/location, not arbitrary unknown
        actuator kinds. A mechanically jammed-OPEN valve still conducts.
        """
        match = re.fullmatch(
            r"ISO-WET-(GREYWATER|BLACKWATER)-([AB])-(FIXED|ROTOR)",
            identifier)
        if match is None:
            row = isolators.get(identifier)
            return bool(row and _physical_passage(row))
        fluid, side, end = match.groups()
        row = isolators.get(identifier)
        if row is None:
            return False
        expected_kind = (
            f"manual/remote rated {fluid.lower()} "
            f"{'fixed-side' if end == 'FIXED' else 'rotor-side'} rotary isolation")
        expected_room = (
            f"ROTARY-UTIL-{side}" if end == "FIXED"
            else f"HAB-{'06' if side == 'A' else '08'}-SERVICE-GALLERY")
        return bool(
            row.reference.get("kind", "").lower() == expected_kind
            and row.reference.get("network") == fluid.lower()
            and row.reference.get("normal_state") == "closed"
            and row.space_id == expected_room
            and row.setting == "open"
            and (row.condition not in _BROKEN or row.condition == "jammed")
        )

    def wet_edge_can_flow(edge):
        if _live_edge(edge, isolators):
            return True
        # Authored rotary wet unions and segregated gas exhausts are
        # NORMALLY CLOSED at rest, not mechanically impossible to open.
        # Their real individual normally-closed valves own the live seal.
        # Never override an explicitly damaged edge or accept an arbitrary
        # standby/unverified byproduct route as conducting.
        ident = edge.source_id
        explicitly_valved = (
            ident in {f"EDGE-WET-{fluid}-{side}-ROTARY"
                      for fluid in ("GREYWATER", "BLACKWATER")
                      for side in "AB"}
            or ident in {f"EDGE-BYP-{side}-H2" for side in "AB"}
        )
        expected_ids = None
        match = re.fullmatch(r"EDGE-WET-(GREYWATER|BLACKWATER)-([AB])-ROTARY", ident)
        if match is not None:
            fluid, side = match.groups()
            expected_ids = {
                f"ISO-WET-{fluid}-{side}-FIXED",
                f"ISO-WET-{fluid}-{side}-ROTOR",
            }
        else:
            match = re.fullmatch(r"EDGE-BYP-([AB])-H2", ident)
            if match is not None:
                side = match.group(1)
                expected_ids = {
                    f"ISO-BYP-{side}-H2-SOURCE",
                    f"ISO-BYP-{side}-H2-HULL",
                }
        actual_ids = edge.reference.get("isolator_ids")
        return bool(
            explicitly_valved and edge.setting == "normally_closed"
            and edge.reference.get("normal_state") == "normally_closed"
            and edge.condition not in _BROKEN
            and isinstance(actual_ids, list) and len(actual_ids) == 2
            and set(actual_ids) == expected_ids
            and all(rated_wet_valve_conducts(identifier)
                    for identifier in actual_ids)
        )

    def connected(network, sources, destinations):
        if not sources or not destinations:
            return False
        # The installed v0.5 fixed waste-hold edges are documented in
        # reference-flow orientation (fixed receiver -> rotary manifold).
        # A pressurised wet service pipe is traversable both ways *when
        # physically open*, while pumps decide where actual effluent goes.
        # The G18 graph routine is directional for other media; do not
        # change generator/gas/thermal routing merely to fix wet topology.
        if network in {"potable_water", "greywater", "blackwater"}:
            graph = defaultdict(set)
            for edge in edges:
                if edge.reference["network"] != network or not wet_edge_can_flow(edge):
                    continue
                path_id = edge.source_id
                skip = False
                for side in "AB":
                    kind = network.upper()
                    if (path_id in {
                            f"EDGE-WET-{kind}-{side}-ROTARY",
                            f"EDGE-FIXED-{kind}-{side}"} and
                            not sound(f"ROT-{kind}-{side}")):
                        skip = True
                if skip:
                    continue
                a, b = edge.reference["from_node"], edge.reference["to_node"]
                graph[a].add(b)
                graph[b].add(a)
            reached = set(sources)
            queue = deque(sorted(reached))
            while queue:
                for other in sorted(graph[queue.popleft()]):
                    if other not in reached:
                        reached.add(other)
                        queue.append(other)
        else:
            reached = _reachable(edges, isolators, network, sources)
        return any(n in reached for n in destinations)

    # Pumps and emergency hygiene supply belong to the essential electrical
    # service tier. Full wastewater reclamation needs normal-load assurance.
    # A 50 kW brownout must not disable drinking water while its surviving
    # protected bus can still run a modest water distribution pump.
    running = power["assured"]
    essential_running = power["essential_assured"]
    potable_sources = owned("potable_water", "POTABLE-TANK-MAIN")
    potable_receivers = [
        n for arc in range(1, 9)
        for n in owned("potable_water", f"HAB-{arc:02d}-POTABLE-WATER-MAN")
    ]
    potable = (essential_running and sound("POTABLE-TANK-MAIN")
               and any(sound(f"ROT-POTABLE-WATER-{side}") for side in "AB")
               and connected("potable_water", potable_sources, potable_receivers))
    process = {}
    fixed = {}
    for medium in ("grey", "black"):
        net = medium + "water"
        supply = [
            n for arc in range(1, 9)
            for n in owned(net, f"HAB-{arc:02d}-{medium.upper()}WATER-MAN")
        ]
        for side in "AB":
            sink = owned(net, f"WASTE-PROC-{side}")
            key = f"{side}_{medium}"
            process[key] = connected(net, supply, sink)
        receiver = owned(net, "FIXED-GREY-HOLD" if medium == "grey"
                         else "FIXED-BLACK-HOLD")
        fixed[medium] = (
            sound("FIXED-GREY-HOLD" if medium == "grey" else "FIXED-BLACK-HOLD")
            and connected(net, supply, receiver))
    process_ok = {
        side: (running and sound(f"WASTE-PROC-{side}")
               and sound(f"WATER-PROC-{side}")
               and (motor_ready is None or (
                   motor_ready(f"WASTE-PROC-{side}")
                   and motor_ready(f"WATER-PROC-{side}")))
               and any(sound(f"ROT-POTABLE-WATER-{path}") for path in "AB")
               and connected("potable_water",
                             owned("potable_water", f"WATER-PROC-{side}"),
                             potable_sources)
               and process[f"{side}_grey"] and process[f"{side}_black"])
        for side in "AB"
    }
    bin_names = {
        "sanitary": ("WASTE-RESIDUE-HOLD-A", "WASTE-RESIDUE-HOLD-B"),
        "industrial": ("IND-SCRAP-HOLD-A", "IND-SCRAP-HOLD-B"),
        "hazardous": ("HAZ-ISO-HOLD-A", "HAZ-ISO-HOLD-B"),
    }
    bins = {
        group: {side: (sound(name) and water["cassette_sealed"][group][side]
                and name not in water["waste_offload"]["jobs"])
                for side, name in zip("AB", names)}
        for group, names in bin_names.items()
    }
    # An H2 vent must have BOTH actual local isolators conducting, and a
    # positively surveyed exterior nozzle. No false default exterior proof.
    oxygen_side = None
    for side in "AB":
        outlet = equipment.get(f"ECLSS-{side}-H2-VENT")
        field = equipment.get(f"ECLSS-{side}-O2-GEN")
        edge = next((e for e in edges
                     if e.source_id == f"EDGE-BYP-{side}-H2"), None)
        if (oxygen_side is None and potable and process_ok[side]
                and _on(equipment, f"ECLSS-{side}")
                and (motor_ready is None or motor_ready(f"ECLSS-{side}"))
                and outlet and outlet.condition not in _BROKEN and
                field and field.condition not in _BROKEN
                and _on(equipment, f"ECLSS-{side}-O2-GEN")
                and (motor_ready is None
                     or motor_ready(f"ECLSS-{side}-O2-GEN"))
                and edge and wet_edge_can_flow(edge)
                and water["oxygen_outlet_verified"][side]):
            oxygen_side = side
    return {
        "potable": potable,
        "process": process_ok,
        "recovery_fraction": {
            side: (0.80 if any(
                equipment.get(f"{family}-{side}") is not None and
                equipment[f"{family}-{side}"].condition == "degraded"
                for family in ("WASTE-PROC", "WATER-PROC"))
                else 0.90)
            for side in "AB"
        },
        "throughput_factor": {
            side: (0.60 if any(
                equipment.get(f"{family}-{side}") is not None and
                equipment[f"{family}-{side}"].condition == "degraded"
                for family in ("WASTE-PROC", "WATER-PROC"))
                else 1.0)
            for side in "AB"
        },
        "fixed": {k: essential_running and v for k, v in fixed.items()},
        "oxygen": oxygen_side is not None, "oxygen_side": oxygen_side,
        "bins": bins,
    }




@transaction.atomic
def survey_g19_water_material(*, operator_approved=False, source=None,
                              room_id=None, verified_kg=None):
    """Physically locate an existing material supply, never invent more."""
    if not operator_approved:
        raise PermissionError("Physical material survey is operator-only")
    if source not in {"INV-SPARES", "INV-DC-CONSUMABLES"}:
        raise PhysicsError("Unclassified material source")
    clock = _clock(lock=True)
    store = state("inventory", source, lock=True)
    from world.ship_world import find_ship_space
    if (room_id not in store.reference.get("location_ids", ())
            or not isinstance(room_id, str) or find_ship_space(room_id) is None):
        raise PhysicsError("No installed source stock at that room")
    amount = _positive(verified_kg)
    w = clock.details.get("water")
    if w is None:
        raise PhysicsError("Water/waste system not commissioned")
    # A global 8-tonne stock record cannot be re-surveyed as eight tonnes
    # at a 1.5-tonne HAB refuge. Authored room allocations are hard limits
    # on physically located, still-unspent consumables.
    allocations = store.reference.get("location_allocations_t")
    if allocations:
        already_at_room = w["source_surveys"].get(source, {}).get(room_id, 0.0)
        if (room_id not in allocations
                or already_at_room + amount > allocations[room_id] * 1000.0 + 1e-7):
            raise PhysicsError("Survey exceeds original local material allocation")
    try:
        w = register_source_survey(
            w, source=source, room=room_id,
            verified_kg=amount, inventory_kg=store.quantity * 1000.0)
    except WaterError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    d = dict(clock.details)
    d["water"] = w
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "operator_material_location_survey", before)
    return {"source": source, "room": room_id, "verified_kg": amount}


@transaction.atomic
def verify_g19_hydrogen_outlet(side, *, operator_approved=False,
                               exterior_clearance_verified=False):
    """Explicit as-installed exterior survey; never infer a safe vacuum port.

    A failed/out-of-clearance rotating H2 nozzle inhibits electrolysis.
    Closing a live control valve still blocks discharge after verification.
    """
    if not operator_approved:
        raise PermissionError("Physical outlet commissioning is operator-only")
    if side not in {"A", "B"} or not isinstance(exterior_clearance_verified, bool):
        raise PhysicsError("Select installed hydrogen outlet A or B and a real survey result")
    clock = _clock(lock=True)
    water = clock.details.get("water")
    if water is None:
        raise PhysicsError("Water/waste plant not commissioned")
    vent = state("equipment", f"ECLSS-{side}-H2-VENT")
    gen = state("equipment", f"ECLSS-{side}-O2-GEN")
    edge = state("edge", f"EDGE-BYP-{side}-H2")
    source = state("isolator", f"ISO-BYP-{side}-H2-SOURCE")
    hull = state("isolator", f"ISO-BYP-{side}-H2-HULL")
    if (vent.condition in _BROKEN or gen.condition in _BROKEN
            or edge.condition in _BROKEN or source.condition in _BROKEN
            or hull.condition in _BROKEN):
        if exterior_clearance_verified:
            raise PhysicsError("Damaged byproduct equipment cannot pass exterior survey")
    if (edge.reference.get("network") != "byproduct_exhaust"
            or vent.reference.get("attributes", {}).get("gas") != "H2"):
        raise PhysicsError("Hydrogen outlet provenance no longer matches installed ship")
    import copy
    w = copy.deepcopy(water)
    if w["oxygen_outlet_verified"][side] == exterior_clearance_verified:
        return {"changed": False, "side": side,
                "verified": exterior_clearance_verified}
    before = _snapshot(clock)
    w["oxygen_outlet_verified"][side] = exterior_clearance_verified
    details = dict(clock.details)
    details["water"] = w
    clock.details = details
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "water_hydrogen_outlet_survey", before)
    return {"changed": True, "side": side,
            "verified": exterior_clearance_verified}




@transaction.atomic
def commission_g19_freight_service(*, operator_approved=False):
    """Adopt nine already-mounted service openings without reinitialising them."""
    if not operator_approved:
        raise PermissionError("Service-opening commissioning requires world authority")
    _require_installed()
    verify_freight_service_source(load_candidate())
    clock = _clock(lock=True)
    if clock.details.get("freight_service") is not None:
        validate_service_access(clock.details["freight_service"])
        return {"commissioned": False, "gates": len(FREIGHT_SERVICE_GATES)}
    for gate, (control, site, kind, boundary, _rotor) in FREIGHT_SERVICE_GATES.items():
        door = state("access", gate)
        if (door.reference.get("from") != control
                or door.reference.get("to") != site
                or door.reference.get("kind") != kind
                or door.reference.get("pressure_boundary") is not boundary
                or door.setting != "closed"):
            raise PhysicsError("Service opening is not in original sealed position")
    before = _snapshot(clock)
    d = dict(clock.details)
    d["freight_service"] = initial_service_access()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "commission_g19_freight_service", before)
    return {"commissioned": True, "gates": len(FREIGHT_SERVICE_GATES),
            "equipment_served": len(FREIGHT_SERVICE_WORKSITES)}


@transaction.atomic
def commission_g19_personnel_transfers(*, operator_approved=False):
    """Explicitly commission eight existing indexed personnel mechanisms.

    This adds a durable job book, not compartments, pressure stock or new
    machinery. Existing voyages and older G18 tests are not auto-retrofitted.
    """
    if not operator_approved:
        raise PermissionError("World operator must commission indexed transfer machinery")
    clock = _clock(lock=True)
    if clock.details.get("personnel_transfers") is not None:
        validate_personnel_transfers(clock.details["personnel_transfers"])
        return {"commissioned": False}
    if set(clock.details.get("rotors", {})) != set(ROTORS):
        raise PhysicsError("Eight separate rotary mechanisms not commissioned")
    original = _snapshot(clock)
    d = dict(clock.details)
    d["personnel_transfers"] = initial_personnel_transfers()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "commission_g19_indexed_personnel", original)
    return {"commissioned": True, "rated_links": 9}


@transaction.atomic
def commission_g19_hab_sync(*, operator_approved=False):
    """Commission the existing pair of independent moving HAB indexer drives."""
    if not operator_approved:
        raise PermissionError("World operator must commission HAB moving carriers")
    clock = _clock(lock=True)
    if clock.details.get("hab_sync") is not None:
        validate_hab_sync(clock.details["hab_sync"])
        return {"commissioned": False}
    if clock.details.get("personnel_transfers") is None:
        raise PhysicsError("Commission the real indexed-carriage service first")
    for station in "AB":
        for suffix in ("DRIVE", "CARRIER", "FIXED-COLLAR", "ROT-COLLAR"):
            state("equipment", f"IX-{station}-{suffix}")
    before = _snapshot(clock)
    d = dict(clock.details)
    d["hab_sync"] = initial_hab_sync()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "commission_g19_moving_hab_indexer", before)
    return {"commissioned": True, "stations": 2}


@transaction.atomic
def commission_g19_crew_physiology(*, actor_dbrefs, operator_approved=False):
    """Register ACTUAL named crew, never simulate a hypothetical 40-person trip.

    Persists each person's injury, water deficit and measured exposure in
    CanonicalShipState (crew_health:#id). An already registered person
    retains all cumulative damage when commissioned again.
    """
    if not operator_approved:
        raise PermissionError("Only the operator can enrol live crew physiology")
    _clock(lock=True)
    if not isinstance(actor_dbrefs, (tuple, list)) or not actor_dbrefs:
        raise PhysicsError("Specify real crew actors to enrol")
    if len(actor_dbrefs) > 40 or len(set(actor_dbrefs)) != len(actor_dbrefs):
        raise PhysicsError("Duplicate or unbounded individual enrolment")
    from evennia.objects.models import ObjectDB
    from world.ship_world import find_ship_space
    zones = _topology()[0]
    newly = 0
    for ref in actor_dbrefs:
        if (not isinstance(ref, str)
                or re.fullmatch(r"#[0-9]+", ref) is None):
            raise PhysicsError("Crew enrolment requires an exact Evennia dbref")
        actor = ObjectDB.objects.filter(id=int(ref[1:])).first()
        room = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        if (actor is None or not getattr(actor.db, "crew_role", None)
                or find_ship_space(room) != getattr(actor, "location", None)
                or zones.get(room) is None):
            raise PhysicsError("Actor is not identified crew inside a real Ox space")
        key = "crew_health:" + ref
        prior = CanonicalShipState.objects.select_for_update().filter(pk=key).first()
        if prior:
            if prior.source_id != ref or prior.source_model != MODEL:
                raise PhysicsError("Existing crew physiological record belongs elsewhere")
            try:
                validate_crew_health(prior.details)
            except CrewPhysiologyError as exc:
                raise PhysicsError(str(exc)) from exc
            continue
        CanonicalShipState.objects.create(
            key=key, category="crew_health", source_id=ref,
            source_model=MODEL, space_id=room,
            condition="fit", setting="unprotected",
            reference={"type": "registered_real_crew"},
            details=initial_exposure(),
        )
        newly += 1
    return {"registered": newly, "requested": len(actor_dbrefs)}



@transaction.atomic
def commission_g19_medical(*, operator_approved=False, dressings=0, fluid_kg=0.0):
    """Verify existing HAB-04 rooms/plant; attest finite local first-aid stock once."""
    if not operator_approved:
        raise PermissionError("Only operator can attest existing pharmacy stock")
    clock = _clock(lock=True)
    if clock.details.get("medical") is not None:
        validate_medical(clock.details["medical"])
        return {"commissioned": False, "medical": clock.details["medical"]}
    from world.ship_world import find_ship_space
    zones = _topology()[0]
    for room in (TREATMENT_ROOM, PHARMACY_ROOM, OBSERVATION_ROOM):
        if (find_ship_space(room) is None or zones.get(room) != CLINIC_ZONE):
            raise PhysicsError("Original HAB-04 pharmacy/treatment bay not installed")
    panel = state("equipment", TREATMENT_PANEL)
    breaker = state("isolator", TREATMENT_FEEDER)
    obs_panel = state("equipment", "HAB-04-MED-OBS-LP")
    obs_breaker = state("isolator", "ISO-HAB-04-MED-OBS-LP")
    if (panel.space_id != TREATMENT_ROOM or
            breaker.reference.get("network") != "power" or
            obs_panel.space_id != OBSERVATION_ROOM or
            obs_breaker.space_id != OBSERVATION_ROOM or
            obs_breaker.reference.get("network") != "power"):
        raise PhysicsError("Original local medical power apparatus mismatched")
    try:
        medical = initial_medical(dressings=dressings, fluid_kg=fluid_kg)
    except MedicalError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    details = dict(clock.details)
    details["medical"] = medical
    clock.details = details
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_existing_clinic_medical_commissioned", before)
    return {"commissioned": True, "medical": medical}


def _medical_power_and_air(*, clock_details=None, room=TREATMENT_ROOM):
    """Test live clinic air, original local breaker and energized feeder."""
    if room not in {TREATMENT_ROOM, OBSERVATION_ROOM}:
        raise PhysicsError("Only as-installed clinic treatment and observation power")
    cell = state("pressure", CLINIC_ZONE)
    observed = room == OBSERVATION_ROOM
    panel = state("equipment",
                  "HAB-04-MED-OBS-LP" if observed else TREATMENT_PANEL)
    feeder = "ISO-HAB-04-MED-OBS-LP" if observed else TREATMENT_FEEDER
    node = "NODE-HAB-04-MED-OBS-LP" if observed else TREATMENT_POWER_NODE
    breaker = state("isolator", feeder)
    d = clock_details if clock_details is not None else _clock().details
    if (panel.condition in _BROKEN or breaker.condition in _BROKEN
            or breaker.setting != "closed"):
        return False, False
    equipment = {r.source_id: r for r in
                 CanonicalShipState.objects.filter(category="equipment")}
    isolators = {r.source_id: r for r in
                 CanonicalShipState.objects.filter(category="isolator")}
    power = _power(
        equipment, list(CanonicalShipState.objects.filter(category="edge")),
        isolators, d["load_profile"], ledger=d.get("electrical"),
        moored=contacts_active(d.get("cargo", {})))
    return bool(power["assured"] and node in power["nodes"]), _air_safe(cell)


@transaction.atomic
def commission_g19_rescue(*, operator_approved=False):
    """Activate two-carrier casualty transport through existing physical doors."""
    if not operator_approved:
        raise PermissionError("Only operator can commission shipboard rescue")
    clock = _clock(lock=True)
    if clock.details.get("medical") is None:
        raise PhysicsError("Commission the fitted HAB-04 clinic first")
    if clock.details.get("rescue") is not None:
        validate_rescue(clock.details["rescue"])
        return {"commissioned": False}
    old = _snapshot(clock)
    details = dict(clock.details)
    details["rescue"] = initial_rescue()
    clock.details = details
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_manual_casualty_transport_commissioned", old)
    return {"commissioned": True}



@transaction.atomic
def commission_g19_flywheel_access(*, operator_approved=False):
    """Commission exact original two service-airlock mechanisms, not gas cells."""
    if not operator_approved:
        raise PermissionError("Rated F1/F2 airlocks require operator authority")
    clock = _clock(lock=True)
    if clock.details.get("bay_access") is not None:
        validate_bay_access(clock.details["bay_access"])
        return {"commissioned": False}
    if clock.details.get("eva") is None:
        raise PhysicsError("Four finite EVA suits must be commissioned first")
    from world.ship_world import find_ship_space
    zones = _topology()[0]
    for link, (corridor, bay, panel) in BAY_SERVICE_LOCKS.items():
        door = state("access", link)
        control = state("equipment", panel)
        if (find_ship_space(corridor) is None or
                find_ship_space(bay) is None or
                zones.get(corridor) != "PZ-TRUNK-A-" + bay[:2] or
                zones.get(bay) != "VACUUM" or
                control.space_id != bay or
                (door.reference.get("from"), door.reference.get("to"),
                 door.reference.get("kind"),
                 door.reference.get("pressure_boundary")) != (
                    corridor, bay, "service_airlock", True)):
            raise PhysicsError("F1/F2 as-built pressure-sealed worksite mismatch")
    before = _snapshot(clock)
    d = dict(clock.details)
    d["bay_access"] = initial_bay_access()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "commission_g19_flywheel_service_locks", before)
    return {"commissioned": True, "fitted": len(BAY_SERVICE_LOCKS)}


@transaction.atomic
def survey_g19_flywheel_access(*, bay_id, operator_approved=False):
    """Attest which existing unpressurised F1/F2 worksite may be entered suited."""
    if not operator_approved:
        raise PermissionError("F1/F2 airlock safety survey is operator-only")
    if bay_id not in {entry[1] for entry in BAY_SERVICE_LOCKS.values()}:
        raise PhysicsError("Only the two fitted F1/F2 worksite bays")
    clock = _clock(lock=True)
    ledger = clock.details.get("bay_access")
    if ledger is None:
        raise PhysicsError("Rated flywheel service airlocks not commissioned")
    link = next(link for link, row in BAY_SERVICE_LOCKS.items()
                if row[1] == bay_id)
    door = state("access", link)
    panel = state("equipment", BAY_SERVICE_LOCKS[link][2])
    if (door.condition in _BROKEN or panel.condition in _BROKEN or
            _topology()[0].get(bay_id) != "VACUUM"):
        raise PhysicsError("Failed original flywheel worksite safety survey")
    try:
        surveyed = survey_bay(ledger, bay_id)
    except BayAccessError as exc:
        raise PhysicsError(str(exc)) from exc
    if surveyed == ledger:
        return {"changed": False, "bay": bay_id}
    before = _snapshot(clock)
    d = dict(clock.details)
    d["bay_access"] = surveyed
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_original_flywheel_suited_airlock_survey", before)
    return {"changed": True, "bay": bay_id}





@transaction.atomic
def commission_g19_propulsion_exterior(*, operator_approved=False):
    """Commission the actual aft EVA nozzle inspection face without new engine."""
    if not operator_approved:
        raise PermissionError("Operator must attest the original nozzle service face")
    clock = _clock(lock=True)
    if clock.details.get("propulsion_exterior") is not None:
        validate_propulsion_exterior(clock.details["propulsion_exterior"])
        return {"commissioned": False}
    if clock.details.get("eva") is None:
        raise PhysicsError("Real EVA system must be commissioned first")
    from world.ship_world import find_ship_space
    base, face = find_ship_space(PROPULSION_BASE), find_ship_space(PROPULSION_FACE)
    door = state("access", PROPULSION_LINK)
    if (base is None or face is None
            or base.db.ox_frame != "external" or face.db.ox_frame != "external"
            or _topology()[0].get(PROPULSION_BASE) != "VACUUM"
            or _topology()[0].get(PROPULSION_FACE) != "VACUUM"
            or (door.reference.get("from"), door.reference.get("to"),
                door.reference.get("kind"),
                door.reference.get("traverse_time_s")) != (
                    PROPULSION_BASE, PROPULSION_FACE,
                    "eva_work_platform_transfer", PROPULSION_GATE_S)):
        raise PhysicsError("Original aft nozzle platform geometry not fitted")
    if any(state("equipment", machine).space_id != space for machine, space in (
            ("LP-PROP-CTRL", PROPULSION_STATION),
            ("LCS-PROP", "PROP-SVC"))):
        raise PhysicsError("No original propulsion safety control path")
    before = _snapshot(clock)
    d = dict(clock.details)
    d["propulsion_exterior"] = initial_propulsion_exterior()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_original_aft_nozzle_inspection_commissioned", before)
    return {"commissioned": True, "workface": PROPULSION_FACE}


@transaction.atomic
def survey_g19_propulsion_exhaust(*, operator_approved=False,
                                  temperature_k, plume_clear):
    """Operator-attest an observed plume/skin after the last propellant use."""
    if not operator_approved:
        raise PermissionError("An exhaust clearance needs operator survey authority")
    clock = _clock(lock=True)
    d = dict(clock.details)
    ledger = d.get("propulsion_exterior")
    if ledger is None:
        raise PhysicsError("Aft nozzle workface has not been commissioned")
    if not isinstance(plume_clear, bool):
        raise PhysicsError("Plume clearance must be a positive Boolean observation")
    try:
        surveyed = survey_propulsion_exterior(
            ledger, temperature_k=temperature_k, plume_clear=plume_clear,
            motion=d["motion"], game_time=d["last_game_time"])
    except PlumeAccessError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    d["propulsion_exterior"] = surveyed
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_aft_exhaust_temperature_and_plume_attested", before)
    return {"workface": PROPULSION_FACE, "skin_temperature_k": temperature_k,
            "plume_clear": plume_clear}


def _propulsion_exterior_ready(details, equipment):
    """Require the genuine safety controls and work-platform hardware."""
    ledger = details.get("propulsion_exterior")
    if ledger is None:
        return False
    hardware = all(
        machine in equipment and equipment[machine].condition not in _BROKEN
        for machine in ("LCS-PROP", "LP-PROP-CTRL", "EVA-WORK-PLATFORM"))
    return bool(hardware and ledger["permit"] is not None
                and propulsion_face_safe(
                    ledger, motion=details["motion"],
                    hardware_ready=hardware))


def _propulsion_exterior_suit_ready(actor, details):
    if (actor is None or getattr(getattr(getattr(actor, "location", None), "db", None),
                                  "ox_space_id", None) != PROPULSION_FACE
            or getattr(actor.db, "ox_terminal_dead", False)
            or getattr(actor.db, "crew_role", None) not in AUTHORISED_ROLES):
        return False
    hp = CanonicalShipState.objects.filter(
        pk="crew_health:" + actor.dbref, source_model=MODEL).first()
    if hp is None or hp.condition not in {"fit", "impaired"}:
        return False
    system = details.get("eva")
    if system is None or actor.dbref in system["transits"]:
        return False
    _, suit = suit_of(system, actor.dbref)
    return bool(suit is not None and suit["integrity"] >= .8 and
                suit["exposure"]["suit_oxygen_kg"] > .01 and
                suit["exposure"]["condition"] not in {
                    "incapacitated", "critical", "dead"})


@transaction.atomic
def commission_g19_exterior_radiators(*, operator_approved=False):
    """Commission existing four LT and two HT exterior service platforms."""
    if not operator_approved:
        raise PermissionError("Exterior radiator hazard survey requires operator approval")
    clock = _clock(lock=True)
    if clock.details.get("exterior_radiators") is not None:
        validate_exterior_radiators(clock.details["exterior_radiators"])
        return {"commissioned": False}
    if clock.details.get("eva") is None or clock.details.get("repairs") is None:
        raise PhysicsError("Fitted EVA and shared maintenance must be commissioned")
    from world.ship_world import find_ship_space
    for key, spec in EXTERIOR_RADIATORS.items():
        wing = state("equipment", key)
        face = find_ship_space(spec["face"])
        host = "EXT-CENTRAL" if key.startswith("RAD-LT-") else "EXT-AFT"
        door = state("access", "ACC-" + host + "-" + spec["face"])
        if (wing.space_id != spec["station"]
                or face is None or face.db.ox_frame != "external"
                or _topology()[0].get(spec["face"]) != "VACUUM"
                or (door.reference.get("from"), door.reference.get("to"),
                    door.reference.get("kind")) != (
                        host, spec["face"], "eva_work_platform_transfer")):
            raise PhysicsError("Original exterior radiator hardware or access link mismatch")
        for isolator in spec["isolation"]:
            if state("isolator", isolator).reference.get("network") not in {
                    "ht_cooling", "lt_cooling"}:
                raise PhysicsError("Original coolant isolation valve not fitted")
    before = _snapshot(clock)
    d = dict(clock.details)
    d["exterior_radiators"] = initial_exterior_radiators()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_six_original_exterior_radiators_commissioned", before)
    return {"commissioned": True, "fitted_faces": 6}


@transaction.atomic
def survey_g19_radiator_skin(*, operator_approved=False,
                             radiator_id, temperature_k):
    """Attest an as-found local temperature; never infer a cool radiator."""
    if not operator_approved:
        raise PermissionError("Operator measurement needed for radiator surface")
    if radiator_id not in EXTERIOR_RADIATORS:
        raise PhysicsError("Not an authored physical radiator")
    clock = _clock(lock=True)
    ledger = clock.details.get("exterior_radiators")
    if ledger is None:
        raise PhysicsError("Original exterior thermal sites not commissioned")
    spec = EXTERIOR_RADIATORS[radiator_id]
    if state("equipment", radiator_id).space_id != spec["station"]:
        raise PhysicsError("Radiator no longer installed at its original control room")
    try:
        surveyed = survey_exterior_skin(
            ledger, radiator_id,
            temp_k=temperature_k, game_time=clock.details["last_game_time"])
    except ExteriorRadiatorError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    d = dict(clock.details)
    d["exterior_radiators"] = surveyed
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_original_radiator_skin_temperature_survey", before)
    return {"radiator": radiator_id, "measured_skin_k": temperature_k}


def _radiator_worksite_ready(details, key, equipment, isolators):
    """Use ACTUAL room valves, radiator skin, movement, parked nearby drums."""
    ledger = details.get("exterior_radiators")
    if ledger is None or key not in EXTERIOR_RADIATORS:
        return False
    return radiator_face_safe(
        ledger, key, isolators=isolators, equipment=equipment,
        motion=details["motion"], rotors=details["rotors"],
        require_permit=True)


def _radiator_suit_ready(actor, room, details):
    if actor is None or room not in EXTERIOR_RADIATOR_FACES:
        return False
    if (getattr(getattr(getattr(actor, "location", None), "db", None),
                "ox_space_id", None) != room
            or getattr(actor.db, "ox_terminal_dead", False)
            or getattr(actor.db, "crew_role", None) not in AUTHORISED_ROLES):
        return False
    hp = CanonicalShipState.objects.filter(
        pk="crew_health:" + actor.dbref, source_model=MODEL).first()
    if hp is None or hp.condition not in {"fit", "impaired"}:
        return False
    eva = details.get("eva")
    if eva is None or actor.dbref in eva["transits"]:
        return False
    _, suit = suit_of(eva, actor.dbref)
    return bool(suit is not None and suit["integrity"] >= .8
                and suit["exposure"]["condition"] not in {
                    "incapacitated", "critical", "dead"}
                and suit["exposure"]["suit_oxygen_kg"] > .01)


@transaction.atomic
def commission_g19_flywheel_service(*, operator_approved=False):
    """Commission non-resetting work permits against original measured stores."""
    if not operator_approved:
        raise PermissionError("Flywheel module maintenance requires operator authority")
    clock = _clock(lock=True)
    d = dict(clock.details)
    prior = d.get("flywheel_service")
    if prior is not None:
        try:
            upgraded = migrate_flywheel_service_v1(prior)
        except FlywheelServiceError as exc:
            raise PhysicsError(str(exc)) from exc
        if upgraded != prior:
            before = _snapshot(clock)
            d["flywheel_service"] = upgraded
            clock.details = d
            clock.revision += 1
            clock.save(update_fields=["details", "revision"])
            _event(clock, "g19_flywheel_rundown_custody_migrated", before)
        return {"commissioned": False,
                "live_permits": len(upgraded["permits"]),
                "live_rundowns": len(upgraded["rundowns"]),
                "migrated": upgraded != prior}
    if any(d.get(key) is None for key in (
            "electrical", "repairs", "eva", "bay_access")):
        raise PhysicsError("Commission original electricity, shared repairs, suits and bay locks first")
    if not all(name in d["bay_access"]["surveyed_bays"]
               for name in ("F1-BAY", "F2-BAY")):
        raise PhysicsError("Both original F1/F2 airlocks require verified surveys")
    before = _snapshot(clock)
    d["flywheel_service"] = initial_flywheel_service()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_flywheel_isolation_service_commissioned", before)
    return {"commissioned": True, "fitted_modules": len(SERVICE_FLYWHEELS)}


@transaction.atomic
def commission_g19_eva(*, operator_approved=False):
    """Commission two real EVA locks and four initially empty breathing sets."""
    if not operator_approved:
        raise PermissionError("EVA commissioning requires world authority")
    clock = _clock(lock=True)
    if clock.details.get("eva") is not None:
        validate_eva(clock.details["eva"])
        return {"commissioned": False}
    stock = state("inventory", "INV-DC-CONSUMABLES")
    if stock.quantity is None or stock.quantity * 1000 < 4 * SUIT_O2_KG:
        raise PhysicsError("No physical breathing reserve for issued suits")
    for lock in EVA_LOCKS:
        spec = lock_contract(lock)
        for kind, ident in (
                ("equipment", spec["panel"]), ("equipment", spec["crawler"]),
                ("isolator", spec["damper"]), ("isolator", spec["breaker"]),
                ("access", spec["inner"]), ("access", spec["outer"]),
                ("pressure", spec["zone"])):
            state(kind, ident)
    before = _snapshot(clock)
    d = dict(clock.details)
    d["eva"] = initial_eva()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "commission_g19_eva_airlocks", before)
    return {"commissioned": True, "suits": 4, "airlocks": 2}


@transaction.atomic
def commission_g19_major_damage(*, operator_approved=False):
    """Commission real local pressure-bulkhead isolation plus external repairs."""
    if not operator_approved:
        raise PermissionError("Only world operator commissions major hull recovery")
    clock = _clock(lock=True)
    if clock.details.get("major_damage") is not None:
        validate_major_damage(clock.details["major_damage"])
        return {"commissioned": False}
    if clock.details.get("hull") is None or clock.details.get("eva") is None:
        raise PhysicsError("Major damage requires commissioned hull and fitted EVA first")
    if clock.details.get("repairs") is None:
        raise PhysicsError("Finite shared spares/toolkits are required")
    panel = state("equipment", "LP-ENG-CONTROL")
    if panel.condition in _BROKEN:
        raise PhysicsError("No usable engineering damage-control panel")
    before = _snapshot(clock)
    d = dict(clock.details)
    d["major_damage"] = initial_major_damage()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "commission_g19_major_bulkhead_damage", before)
    return {"commissioned": True}


@transaction.atomic
def register_g19_major_breach_site(*, operator_approved=False, zone_id,
                                    exterior_room_id):
    """Attest a direct, bounded external face and all rated boundary locks.

    Detect unisolatable atmosphere ducts and refuse false containment.
    The registered major hole must already exist as a real pressure leak.
    """
    if not operator_approved:
        raise PermissionError("Major hull face requires world survey")
    clock = _clock(lock=True)
    reg = clock.details.get("major_damage")
    hull = clock.details.get("hull")
    if reg is None or hull is None:
        raise PhysicsError("Major hull containment not commissioned")
    from world.ship_world import find_ship_space
    if find_ship_space(exterior_room_id) is None:
        raise PhysicsError("Missing actual exterior maintenance room")
    zones, _, node_zones = _topology()
    if zones.get(exterior_room_id) != "VACUUM":
        raise PhysicsError("External hull repair face is not an installed vacuum worksite")
    boundaries = []
    for door in CanonicalShipState.objects.filter(category="access"):
        spec = door.reference
        left, right = zones.get(spec.get("from")), zones.get(spec.get("to"))
        if (left == zone_id) == (right == zone_id):
            continue
        if spec.get("pressure_boundary") is not True:
            raise PhysicsError("Unrated physical access prevents assured bulkhead containment")
        boundaries.append(door.source_id)
    for edge in CanonicalShipState.objects.filter(category="edge"):
        spec = edge.reference
        if spec.get("network") != "atmosphere":
            continue
        left = node_zones.get(spec.get("from_node"))
        right = node_zones.get(spec.get("to_node"))
        if (left == zone_id) != (right == zone_id):
            # This closure model does not remotely actuate unknown ductwork.
            # Require separately surveyed dampers and explicit isolation
            # before claiming full compartment containment.
            raise PhysicsError("Uncontained atmosphere duct crosses this shell; isolate locally first")
    try:
        reg = register_major_site(
            reg, hull, zone=zone_id, exterior_room=exterior_room_id,
            boundaries=boundaries)
    except MajorDamageError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    d = dict(clock.details)
    d["major_damage"] = reg
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "operator_major_exterior_breach_survey", before)
    return {"zone": zone_id, "external_room": exterior_room_id,
            "rated_boundaries": tuple(sorted(boundaries))}


@transaction.atomic
def commission_g19_hull(*, operator_approved=False):
    """Enable physical hull repair using the existing finite-spares service."""
    if not operator_approved:
        raise PermissionError("Hull commissioning is operator-only")
    clock = _clock(lock=True)
    if clock.details.get("hull") is not None:
        return {"commissioned": False}
    if clock.details.get("repairs") is None:
        raise PhysicsError("Commission physical shared repairs first")
    before = _snapshot(clock)
    d = dict(clock.details)
    d["hull"] = initial_hull()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "operator_hull_commissioned", before)
    return {"commissioned": True}


@transaction.atomic
def register_g19_hull_breach(*, operator_approved=False, zone_id,
                             site_room_id, leak_kg_s):
    """Survey a real room on the affected pressure shell, then record damage."""
    if not operator_approved:
        raise PermissionError("Hull damage commissioning is operator-only")
    clock = _clock(lock=True)
    hull = clock.details.get("hull")
    if hull is None:
        raise PhysicsError("G19 hull has not been commissioned")
    from world.ship_world import find_ship_space
    if (find_ship_space(site_room_id) is None
            or _topology()[0].get(site_room_id) != zone_id):
        raise PhysicsError("Hull repair face does not belong to this installed cell")
    cell = state("pressure", zone_id, lock=True)
    if (cell.details.get("physics_leak_kg_s", 0) != 0
            or cell.details.get("physics_leak_isolator_id")):
        raise PhysicsError("Existing valved/service leak cannot become a hull breach")
    try:
        new_hull = register_breach(
            hull, zone=zone_id, site_room=site_room_id, leak_kg_s=leak_kg_s)
    except HullError as exc:
        raise PhysicsError(str(exc)) from exc
    previous = _snapshot(cell)
    d = dict(cell.details)
    d["physics_leak_kg_s"] = new_hull["breaches"][zone_id]["original_leak_kg_s"]
    cell.details = d
    cell.revision += 1
    cell.save(update_fields=["details", "revision"])
    _event(cell, "operator_hull_breach", previous)
    before = _snapshot(clock)
    d = dict(clock.details)
    d["hull"] = new_hull
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "operator_hull_repair_face_survey", before)
    return {"zone": zone_id, "repair_room": site_room_id,
            "leak_kg_s": new_hull["breaches"][zone_id]["original_leak_kg_s"]}


@transaction.atomic
def commission_g19_repairs(*, operator_approved=False):
    """Explicitly install durable shared maintenance, not an instant repair."""
    if not operator_approved:
        raise PermissionError("Shared repair service requires operator commissioning")
    clock = _clock(lock=True)
    if clock.details.get("repairs") is not None:
        return {"commissioned": False}
    if clock.details.get("water") is None:
        raise PhysicsError("Shared spares require commissioned G19 physical material custody")
    before = _snapshot(clock)
    details = dict(clock.details)
    details["repairs"] = initial_repairs()
    clock.details = details
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "commission_g19_maintenance", before)
    return {"commissioned": True, "live_repair_slots": 32}



@transaction.atomic
def commission_g19_fabrication(*, operator_approved=False):
    """Attach a finite workpiece ledger to existing SHOP-MECH machinery."""
    if not operator_approved:
        raise PermissionError("Only the world operator commissions original workshop manufacturing")
    clock = _clock(lock=True)
    if clock.details.get("fabrication") is not None:
        validate_fabrication(clock.details["fabrication"])
        return {"commissioned": False}
    if any(clock.details.get(key) is None for key in (
            "water", "repairs", "electrical", "service_operations")):
        raise PhysicsError("Workshop needs real surveyed materials, powered machinery and shared repairs")
    from world.ship_world import find_ship_space
    if (find_ship_space(FABRICATION_ROOM) is None or
            not _topology()[0].get(FABRICATION_ROOM, "").startswith("PZ-")):
        raise PhysicsError("No original breathable machine shop")
    for name in FABRICATION_MACHINES:
        machine = state("equipment", name)
        if (machine.space_id != FABRICATION_ROOM or
                SERVICE_LOADS.get(name, (None,))[0] != FABRICATION_ROOM
                or state("isolator", service_ids(name)[2]).space_id != FABRICATION_ROOM):
            raise PhysicsError("As-built workshop machine and local feeder do not match")
    stock = state("inventory", "INV-SPARES")
    if stock.quantity is None or stock.quantity <= 0:
        raise PhysicsError("Workshop raw blanks require finite pre-existing spare material")
    old = _snapshot(clock)
    d = dict(clock.details)
    d["fabrication"] = initial_fabrication()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_fitted_workshop_fabrication_commissioned", old)
    return {"commissioned": True, "machines": sorted(FABRICATION_MACHINES)}


@transaction.atomic
def commission_g19_welding(*, operator_approved=False):
    """Commission only the two as-fitted rotating-workshop weld cells."""
    if not operator_approved:
        raise PermissionError("Only operator commissions installed welding work")
    clock = _clock(lock=True)
    if clock.details.get("welding") is not None:
        validate_welding(clock.details["welding"])
        return {"commissioned": False}
    if any(clock.details.get(key) is None for key in (
            "electrical", "water", "repairs", "service_operations")):
        raise PhysicsError("Original welding requires power, real source stock and shared repairs")
    from world.ship_world import find_ship_space
    if (find_ship_space(WELDING_ROOM) is None or
            _topology()[0].get(WELDING_ROOM) != "PZ-WR-SHOP"):
        raise PhysicsError("No original rotating welding room and gas cell")
    for name in WELDING_CELLS:
        part = state("equipment", name)
        feeder = state("isolator", service_ids(name)[2])
        if (part.space_id != WELDING_ROOM or
                feeder.space_id != WELDING_ROOM or
                SERVICE_LOADS[name][0] != WELDING_ROOM):
            raise PhysicsError("Original welding cell and refitted local feeder mismatch")
    previous = _snapshot(clock)
    d = dict(clock.details)
    d["welding"] = initial_welding()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_original_two_weld_cells_commissioned", previous)
    return {"commissioned": True, "original_cells": sorted(WELDING_CELLS)}


@transaction.atomic
def survey_g19_welding_filler(*, operator_approved=False, room_id=None,
                              verified_kg=None):
    """Classify only actually surveyed pre-existing INV-SPARES weld rod."""
    if not operator_approved:
        raise PermissionError("Only operator may classify existing weld filler")
    clock = _clock(lock=True)
    d = dict(clock.details)
    if d.get("welding") is None or d.get("water") is None:
        raise PhysicsError("Welding and surveyed materials not commissioned")
    stock = state("inventory", "INV-SPARES")
    if room_id not in stock.reference.get("location_ids", ()):
        raise PhysicsError("Weld wire is not in an original material store")
    existing = d["water"]["source_surveys"].get("INV-SPARES", {}).get(room_id, 0.0)
    try:
        classified = certify_filler(
            d["welding"], room=room_id, kg=verified_kg,
            surveyed_available_kg=existing)
    except WeldError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    d["welding"] = classified
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_finite_original_weld_filler_certified", before)
    return {"site": room_id, "filler_kg": classified["certified_kg"][room_id]}


@transaction.atomic
def survey_g19_fabrication_blanks(*, operator_approved=False,
                                  room_id=None, verified_kg=None):
    """Classify existing physically surveyed INV-SPARES blanks, once per store."""
    if not operator_approved:
        raise PermissionError("World operator must positively attest machinable stock")
    clock = _clock(lock=True)
    d = dict(clock.details)
    ledger = d.get("fabrication")
    water = d.get("water")
    if ledger is None or water is None:
        raise PhysicsError("Workshop and original material survey not commissioned")
    stock = state("inventory", "INV-SPARES")
    if room_id not in stock.reference.get("location_ids", ()):
        raise PhysicsError("This site has no original replacement-stock inventory")
    observed = water["source_surveys"].get("INV-SPARES", {}).get(room_id, 0.0)
    try:
        updated = certify_blanks(
            ledger, room=room_id, kg=verified_kg,
            surveyed_available_kg=observed)
    except FabricationError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    d["fabrication"] = updated
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "g19_real_machinable_blank_survey", before)
    return {"site": room_id, "certified_kg": updated["certified_kg"][room_id]}


@transaction.atomic
def survey_g19_repair_site(*, operator_approved=False, room_id=None,
                           work_class=None):
    """Attest an original nonbreathable generator or F1/F2 service bay.

    This records a workplace, not a new atmosphere, suit or repair permit.
    """
    if not operator_approved:
        raise PermissionError("Hazardous generator-service survey is operator-only")
    if work_class != "suited_service" or room_id not in {
            "GEN-M-ROOM", "GEN-A-ROOM", "GEN-B-ROOM", "F1-BAY", "F2-BAY"}:
        raise PhysicsError("Only installed generator or flywheel service bays can be surveyed")
    from world.ship_world import find_ship_space
    if (find_ship_space(room_id) is None or
            _topology()[0].get(room_id) not in {None, "VACUUM"}):
        raise PhysicsError("No fitted vacuum machinery worksite")
    installed = (
        room_id.replace("-ROOM", "") if room_id.endswith("-ROOM")
        else room_id.replace("-BAY", "-BUS"))
    if state("equipment", installed).space_id != room_id:
        raise PhysicsError("Installed machinery and original service room disagree")
    if room_id in {"F1-BAY", "F2-BAY"}:
        clock = _clock()
        if (clock.details.get("bay_access") is None or
                room_id not in clock.details["bay_access"]["surveyed_bays"]):
            raise PhysicsError("Original rated flywheel service airlock must be surveyed first")
    clock = _clock(lock=True)
    if clock.details.get("repairs") is None:
        raise PhysicsError("Shared repairs have not been commissioned")
    import copy
    repairs = copy.deepcopy(clock.details["repairs"])
    if repairs["site_surveys"].get(room_id) == work_class:
        return {"changed": False, "room_id": room_id}
    before = _snapshot(clock)
    repairs["site_surveys"][room_id] = work_class
    validate_repairs(repairs)
    details = dict(clock.details)
    details["repairs"] = repairs
    clock.details = details
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    event = _event(clock, "operator_suited_machinery_site_survey", before)
    audit = dict(event.after)
    audit["repair_site_survey"] = {"room": room_id, "class": work_class}
    event.after = audit
    event.save(update_fields=["after"])
    return {"changed": True, "room_id": room_id}


@transaction.atomic
def commission_waste_acceptance(*, operator_approved=False, acceptance_id,
                                portal_id, berth_id, category, limit_kg):
    """Operator-recorded compatible offship facility with a finite acceptance cap.

    The external berth may be attested before docking; docking itself remains
    a distinct real physical action, and no inventory moves on attestation.
    """
    if not operator_approved:
        raise PermissionError("External waste acceptance must be operator-verified")
    if portal_id not in PORTALS:
        raise PhysicsError("No such installed external cargo portal")
    clock = _clock(lock=True)
    water = clock.details.get("water")
    if water is None:
        raise PhysicsError("Water and sealed waste not commissioned")
    try:
        updated = accept_berth(
            water, acceptance_id=acceptance_id, portal_id=portal_id,
            berth_id=berth_id, category=category, limit_kg=limit_kg)
    except WaterError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    details = dict(clock.details)
    details["water"] = updated
    clock.details = details
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    event = _event(clock, "operator_waste_berth_acceptance", before)
    audit = dict(event.after)
    audit["waste_acceptance"] = {
        "acceptance_id": acceptance_id, "portal": portal_id,
        "berth": berth_id, "category": category, "limit_kg": limit_kg}
    event.after = audit
    event.save(update_fields=["after"])
    return {"acceptance_id": acceptance_id, "category": category,
            "portal_id": portal_id, "limit_kg": limit_kg}


@transaction.atomic
def survey_waste_freight_route(*, operator_approved=False, receiver_id, portal_id):
    """Verify original fitted internal logistics rails before loading waste."""
    if not operator_approved:
        raise PermissionError("A material route needs a physical operator survey")
    if portal_id not in PORTALS or receiver_id not in WASTE_RECEIVERS:
        raise PhysicsError("Unknown installed cassette or commercial portal")
    clock = _clock(lock=True)
    water = clock.details.get("water")
    if water is None:
        raise PhysicsError("Sealed waste is not commissioned")
    receiver = state("equipment", receiver_id)
    door_rows = list(CanonicalShipState.objects.filter(category="access"))
    try:
        route = selected_waste_route(
            receiver.space_id, portal_id[:5] + "-FREIGHT-LOCK",
            door_rows, _topology()[0])
        revised = approve_route(
            water, receiver=receiver_id, portal_id=portal_id, route=route)
    except WaterError as exc:
        raise PhysicsError(str(exc)) from exc
    if revised != water:
        before = _snapshot(clock)
        d = dict(clock.details)
        d["water"] = revised
        clock.details = d
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        event = _event(clock, "operator_waste_freight_route_survey", before)
        audit = dict(event.after)
        audit["freight_route_evidence"] = {
            "receiver": receiver_id, "portal": portal_id, "access_ids": route}
        event.after = audit
        event.save(update_fields=["after"])
    return {"receiver": receiver_id, "portal": portal_id,
            "access_ids": route, "segments": len(route)}


def _waste_freight_ready(job, water, *, rotors, equipment, access, pressure, zones, cargo):
    """True only for installed, safe and free fixed-spine freight machinery."""
    portal = job["portal_id"]
    drum = portal[:5]
    rotor = rotors.get(drum)
    gate = access.get("ACC-" + drum + "-FREIGHT-CAPTURE")
    handler = equipment.get(drum + "-RADIAL-FREIGHT-HANDLER")
    collar = equipment.get(drum + "-FREIGHT-COLLAR")
    if (rotor is None or gate is None or handler is None or collar is None
            or handler.condition in _BROKEN or collar.condition in _BROKEN
            or gate.condition in _BROKEN or gate.setting != "open"
            or not (rotor["hardlock"] and rotor["brake"] and
                    rotor["target_rpm"] == 0 and abs(rotor["rpm"]) < 0.001
                    and rotor["freight_collar"] and not rotor["passenger_indexer"])
            or any(p[:5] == drum for p in cargo.get("port_jobs", {}))
            or drum in cargo.get("jobs", {})
            or any(p[:5] == drum for p in cargo.get("port_contacts", {}))):
        return False
    receiver = equipment.get(next((r for r in WASTE_RECEIVERS
                                   if WASTE_RECEIVERS[r] == (
                                       job["category"], job["side"])), ""))
    if receiver is None or receiver.condition in _BROKEN:
        return False
    from_zone, to_zone = zones.get(receiver.space_id), zones.get(drum + "-FREIGHT-LOCK")
    if not (from_zone in pressure and to_zone in pressure
            and _air_safe(pressure[from_zone]) and _air_safe(pressure[to_zone])):
        return False
    return live_waste_route(
        job["route"], source_room=receiver.space_id,
        freight_lock=drum + "-FREIGHT-LOCK",
        doors=access, zones=zones, pressure_rows=pressure, rotors=rotors)


def _waste_port_ready(job, *, rotors, equipment, access, cargo):
    portal = job["portal_id"]
    drum = portal[:5]
    r = rotors.get(drum)
    seal = access.get("ACC-" + portal)
    handler = equipment.get(drum + "-RADIAL-FREIGHT-HANDLER")
    contact = cargo.get("port_contacts", {}).get(portal)
    return bool(
        r and seal and handler and contact
        and contact.get("berth_id") == job["berth_id"]
        and contact.get("docked", False)
        and handler.condition not in _BROKEN
        and seal.condition not in _BROKEN and seal.setting == "closed"
        and r["hardlock"] and r["brake"] and r["target_rpm"] == 0
        and abs(r["rpm"]) < 0.001
        and not r["freight_collar"] and not r["passenger_indexer"]
        and drum not in cargo.get("jobs", {})
        and not any(p[:5] == drum for p in cargo.get("port_jobs", {}))
    )

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
        motion.setdefault("expended_ftl_fuel_kg", 0.0)
        motion.setdefault("ftl_leg", None)
        motion.setdefault("nav_location", "unassigned_reference_origin")
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
    else:
        cargo = dict(d["cargo"])
        fresh = initial_cargo(d["motion"]["cargo_mass_kg"])
        for key in ("port_contract_version", "port_contacts", "port_jobs",
                    "registered_external_kg"):
            if key not in cargo:
                cargo[key] = fresh[key]
                changed = True
        d["cargo"] = cargo
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
def survey_g19_equipment_wear(*, operator_approved=False, unit_id,
                              equivalent_hours):
    """Attest inherited fatigue on one original machine without repairs.

    This one-time survey establishes *pre-existing* remaining maintenance
    life. It never changes physical condition or fabricates a spare part.
    """
    if not operator_approved:
        raise PermissionError("Existing-machine wear survey is operator-only")
    if unit_id not in SERVICE_LOADS:
        raise PhysicsError("No fitted service machine at this identifier")
    clock = _clock(lock=True)
    d = dict(clock.details)
    services = d.get("service_operations")
    wear = d.get("equipment_wear")
    if services is None or wear is None:
        raise PhysicsError("G19 equipment operation and maintenance not commissioned")
    installed = state("equipment", unit_id)
    if installed.space_id != SERVICE_LOADS[unit_id][0]:
        raise PhysicsError("Historical wear survey has no original worksite")
    try:
        new_wear = survey_existing_wear(
            wear, services, unit_id, equivalent_hours=equivalent_hours)
    except ElectricalError as exc:
        raise PhysicsError(str(exc)) from exc
    before = _snapshot(clock)
    d["equipment_wear"] = new_wear
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    _event(clock, "operator_observed_inherited_machine_wear", before)
    return {"unit": unit_id, "equivalent_hours": equivalent_hours,
            "surveyed": True}


@transaction.atomic
def survey_g19_cargo_environment(
        *, operator_approved=False, operation, drum=None, lot_id=None,
        profile=None, temperature_k=None, target_k=None,
        heat_capacity_kj_k=None, conductance_kw_k=None):
    """Observe a fitted container climate or record a specific vulnerable lot.

    The operator must explicitly instrument the cargo store and identify
    existing commercial freight; no unlocated bulk shipment silently
    becomes refrigerated, insured or damage-free.
    """
    if not operator_approved:
        raise PermissionError("Physical cargo-climate survey requires world authority")
    clock = _clock(lock=True)
    d = dict(clock.details)
    climate = d.get("cargo_environment")
    manifest = d.get("cargo")
    if climate is None or manifest is None:
        raise PhysicsError("Cargo thermal and freight manifests require G19 commissioning")
    if drum not in CARGO_DRUMS:
        raise PhysicsError("Select an installed cargo drum for climate survey")
    if operation == "drum":
        for target in (drum + "-CARGO-HX", drum + "-CARGO-GAS",
                       drum + "-LT-IF"):
            device = state("equipment", target)
            if device.condition in _BROKEN:
                raise PhysicsError("Drum sensor survey lacks installed sound equipment")
        try:
            climate = survey_drum_environment(
                climate, manifest, drum,
                temperature_k=temperature_k, target_k=target_k,
                heat_capacity_kj_k=heat_capacity_kj_k,
                conductance_kw_k=conductance_kw_k)
        except CargoClimateError as exc:
            raise PhysicsError(str(exc)) from exc
    elif operation == "lot":
        lot = manifest["lots"].get(lot_id)
        if not lot or lot["drum"] != drum:
            raise PhysicsError("Temperature-sensitive survey must identify existing local cargo")
        try:
            climate = survey_sensitive_lot(
                climate, manifest, lot_id, profile)
        except CargoClimateError as exc:
            raise PhysicsError(str(exc)) from exc
    else:
        raise PhysicsError("Cargo thermal survey requires drum or lot")
    before = _snapshot(clock)
    d["cargo_environment"] = climate
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    event = _event(clock, "operator_cargo_environment_" + operation, before)
    audit = dict(event.after)
    audit["source_measurement"] = {
        "drum": drum, "lot": lot_id, "profile": profile,
        "temperature_k": temperature_k, "target_k": target_k,
        "heat_capacity_kj_k": heat_capacity_kj_k,
        "conductance_kw_k": conductance_kw_k,
    }
    event.after = audit
    event.save(update_fields=["after"])
    return {"surveyed": True, "operation": operation, "drum": drum,
            "sensitive_lots": len(climate["lots"])}


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
        elif operation == "restow":
            revised = restow_cargo_lot(
                cargo, lot_id=lot_id, azimuth_deg=azimuth_deg,
                radius_m=radius_m)
        else:
            raise CargoError("Unknown cargo survey operation")
        validate_cargo(revised, d["motion"]["cargo_mass_kg"])
        if (operation == "split" and d.get("cargo_environment") is not None):
            d["cargo_environment"] = inherit_split_care(
                d["cargo_environment"], cargo, revised, source_id, lot_id)
    except (CargoError, CargoClimateError) as exc:
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


@transaction.atomic
def commission_commercial_port(*, operator_approved=False, operation,
                               portal_id, berth_id=None, lot_id=None,
                               mass_kg=None, kind="bulk"):
    """World-operator attestation of external cargo and physical mooring.

    Only a real port-side consignment can add cargo, and the vessel is
    prevented from thrusting during any mooring. Operator attestation does
    not itself move any mass; only clock-driven, crew-started port machinery
    may do that.
    """
    if not operator_approved:
        raise PermissionError("External berth/consignment must be commissioned")
    clock = _clock(lock=True)
    before = _snapshot(clock)
    d = dict(clock.details)
    motion = d["motion"]
    if (operation == "undock" and (d.get("electrical") or {}).get("shore")
            and d["electrical"]["shore"]["connected"]):
        raise PhysicsError("Disconnect and isolate the live shore lead before undocking")
    active_waste = [job for job in d.get("water", {}).get(
        "waste_offload", {}).get("jobs", {}).values()
        if job["portal_id"][:5] == portal_id[:5]]
    if operation == "undock" and any(
            job["phase"] != "return_ready" for job in active_waste):
        raise PhysicsError("Cannot release berth while sealed-waste transfer is active")
    if operation == "register" and active_waste:
        raise PhysicsError("Commercial handler reserved for sealed waste")
    if operation == "dock":
        drum = portal_id[:5] if portal_id in PORTALS else None
        rotor = d["rotors"].get(drum) if drum else None
        if not rotor or not (
                rotor["hardlock"] and rotor["brake"] and
                rotor["target_rpm"] == 0 and
                abs(rotor["rpm"]) <= 0.001 and
                not rotor["freight_collar"] and
                not rotor["passenger_indexer"]):
            raise PhysicsError("Commercial port must be stopped and hardlocked")
        access = state("access", "ACC-" + portal_id)
        handler = state("equipment", drum + "-RADIAL-FREIGHT-HANDLER")
        if (access.condition in _BROKEN or access.setting != "closed"
                or handler.condition in _BROKEN):
            raise PhysicsError("External docking requires sound portal seal and handler")
        if (motion["command"] != "coast"
                or motion["attitude_command"] != "hold"
                or any(abs(v) > 0.0001 for v in motion["angular_velocity_rad_s"])
                or (motion.get("ftl_leg") or {}).get("status") == "engaged"):
            raise PhysicsError("Cannot moor an accelerating or translating ship")
    try:
        if operation in {"dock", "undock"}:
            revised = commission_port_contact(
                d["cargo"], portal_id=portal_id, berth_id=berth_id,
                docked=operation == "dock")
        elif operation == "register":
            revised = register_external_consignment(
                d["cargo"], lot_id=lot_id, mass_kg=mass_kg,
                portal_id=portal_id, kind=kind,
                source_reference=berth_id)
        else:
            raise CargoError("Unknown operator port operation")
        validate_cargo(revised, motion["cargo_mass_kg"])
    except CargoError as exc:
        raise PhysicsError(str(exc)) from exc
    if revised != d["cargo"]:
        d["cargo"] = revised
        clock.details = d
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        event = _event(clock, "operator_port_" + operation, before)
        after = dict(event.after)
        after["port_evidence"] = {
            "operation": operation, "portal_id": portal_id,
            "berth_id": berth_id, "lot_id": lot_id, "mass_kg": mass_kg,
            "kind": kind,
        }
        event.after = after
        event.save(update_fields=["after"])
    return {
        "docked": list(revised.get("port_contacts", {})),
        "port_jobs": len(revised.get("port_jobs", {})),
        "onboard_kg": onboard_mass_kg(revised),
        "offship_kg": revised["delivered_offship_kg"],
    }


@transaction.atomic
def commission_ftl_route(*, operator_approved=False, route_id, destination,
                         distance_ly, cruise_c):
    """World-issued reference navigation leg; crew subsequently engage it."""
    if not operator_approved:
        raise PermissionError("Mission route must be independently commissioned")
    clock = _clock(lock=True)
    before = _snapshot(clock)
    d = dict(clock.details)
    try:
        d["motion"] = prepare_leg(
            d["motion"], route_id=route_id, destination=destination,
            distance_ly=distance_ly, speed_c=cruise_c)
    except NavigationError as exc:
        raise PhysicsError(str(exc)) from exc
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    event = _event(clock, "operator_ftl_route_plan", before)
    audit = dict(event.after)
    audit["ftl_plan"] = {
        "route_id": route_id, "destination": destination,
        "distance_ly": distance_ly, "cruise_c": cruise_c,
    }
    event.after = audit
    event.save(update_fields=["after"])
    return dict(d["motion"]["ftl_leg"])


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


def _power(equipment, edges, isolators, profile, *,
           ledger=None, dt_s=STEP_SECONDS, moored=False, nodes=None,
           cartridge_kg=None):
    if ledger is not None:
        try:
            installed_nodes = (nodes if nodes is not None else
                list(CanonicalShipState.objects.filter(category="node")))
            remaining = (cartridge_kg if cartridge_kg is not None else
                state("inventory", "INV-GEN-CART").quantity * 1000.0)
            return source_dispatch(
                equipment, edges, isolators, profile, ledger=ledger,
                dt_s=dt_s, moored=moored, nodes=installed_nodes,
                cartridge_kg=remaining)
        except ElectricalError as exc:
            raise PhysicsError(str(exc)) from exc
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
    # Only operator-commissioned physiology records have the full gas and
    # injury schema. Earlier G19 repair fixtures legitimately use a simple
    # crew_health marker with a different source_model.
    crew_rows = list(CanonicalShipState.objects.select_for_update()
                     .filter(category="crew_health", source_model=MODEL)
                     .order_by("key"))
    inventory = CanonicalShipState.objects.select_for_update().get(
        pk="inventory:INV-WATER-NORMAL")
    inventory_before = _snapshot(inventory)
    food_inventory = (
        state("inventory", "INV-FOOD-LONG-LEG", lock=True)
        if clock.details.get("food") is not None else None)
    food_before = _snapshot(food_inventory) if food_inventory is not None else None
    water_stocks = {
        "normal": inventory,
        "filter": state("inventory", "INV-DC-CONSUMABLES", lock=True),
        "spares": state("inventory", "INV-SPARES", lock=True),
        "reserve": state("inventory", "INV-WATER-RESERVE", lock=True),
        "sanitary": state("inventory", "INV-WASTE-RESIDUE", lock=True),
        "industrial": state("inventory", "INV-INDUSTRIAL-SCRAP", lock=True),
        "hazardous": state("inventory", "INV-HAZARDOUS-RESIDUE", lock=True),
    }
    water_stock_before = {k: _snapshot(v) for k, v in water_stocks.items()}
    cartridge_stock = (
        state("inventory", "INV-GEN-CART", lock=True)
        if clock.details.get("electrical") is not None else None)
    cartridge_before = _snapshot(cartridge_stock) if cartridge_stock else None
    cartridge_spent = float(clock.details.get(
        "generator_spent_cartridge_kg", 0.0))
    cartridge_baseline = clock.details.get("generator_cartridge_baseline_kg")
    if cartridge_stock is not None and (
            cartridge_baseline is None or
            not math.isfinite(cartridge_spent) or cartridge_spent < 0
            or not math.isclose(
                cartridge_stock.quantity * 1000.0 + cartridge_spent,
                cartridge_baseline, abs_tol=1e-4, rel_tol=1e-11)):
        raise PhysicsError("Generator cartridge magazine plus spent custody do not reconcile")
    isolators = {x.source_id: x for x in
                 CanonicalShipState.objects.select_for_update()
                 .filter(category="isolator")}
    edges = list(CanonicalShipState.objects.filter(category="edge"))
    access_rows = list(CanonicalShipState.objects.filter(category="access"))
    equipment = {x.source_id: x for x in equipment_rows}
    zones, owners, node_zones = _topology()
    cells = {r.source_id: _load_cell(r) for r in pressure_rows}
    hull = clock.details.get("hull")
    if hull is not None:
        try:
            validate_hull(hull)
            for zone, breach in hull["breaches"].items():
                if (zone not in cells or zones.get(breach["site_room"]) != zone
                        or not math.isclose(cells[zone]["leak"], effective_leak(breach),
                                            rel_tol=0, abs_tol=1e-7)):
                    raise PhysicsError("Hull leak and authoritative pressure cell disagree")
        except HullError as exc:
            raise PhysicsError(str(exc)) from exc
    leak_isolators = {r.source_id: r.details.get("physics_leak_isolator_id")
                      for r in pressure_rows}
    # Reference node ownership is static within a tick. Avoid a database
    # query for every 10-second integration substep.
    atmosphere_source_nodes = {}
    water_nodes = list(CanonicalShipState.objects.filter(category="node"))
    for node in water_nodes:
        if (node.reference.get("network") == "atmosphere"
                and node.reference.get("owner_type") == "equipment"):
            atmosphere_source_nodes.setdefault(
                node.reference.get("owner_id"), []).append(node.source_id)
    electrical = clock.details.get("electrical")
    local_backup = clock.details.get("local_backup")
    if local_backup is not None:
        try:
            validate_local_backup(local_backup)
        except ElectricalError as exc:
            raise PhysicsError(str(exc)) from exc
    refuge_scrubbers = clock.details.get("refuge_scrubbers")
    if refuge_scrubbers is not None:
        try:
            validate_refuge_scrubbers(refuge_scrubbers)
        except RefugeAirError as exc:
            raise PhysicsError(str(exc)) from exc
    refuge_captured_before = (
        refuge_scrubbers["meter"]["captured_kg"]
        if refuge_scrubbers is not None else 0.0)
    refuge_media = clock.details.get("refuge_media_service")
    if refuge_media is not None:
        try:
            validate_refuge_media_service(refuge_media)
        except RefugeAirError as exc:
            raise PhysicsError(str(exc)) from exc
    retired_refuge_co2 = (
        refuge_media["meter"]["retired_capture_kg"]
        if refuge_media is not None else 0.0)
    service_operations = clock.details.get("service_operations")
    if service_operations is not None:
        try:
            validate_service_operations(service_operations)
        except ElectricalError as exc:
            raise PhysicsError(str(exc)) from exc
    cultivation = clock.details.get("cultivation")
    if cultivation is not None:
        cultivation = migrate_cultivation_v1(cultivation)
    if cultivation is not None:
        if service_operations is None or clock.details.get("water") is None:
            raise PhysicsError("Cultivation has no commissioned power/water support")
        try:
            validate_cultivation(cultivation)
        except CultivationError as exc:
            raise PhysicsError(str(exc)) from exc
    fault_cases = clock.details.get("fault_cases")
    if fault_cases is not None:
        validate_fault_cases(fault_cases)
    instrumentation = clock.details.get("instrumentation")
    if instrumentation is not None:
        try:
            validate_instrumentation(instrumentation)
            if abs(instrumentation["last_s"] - last) > 1e-7:
                raise PhysicsError("Installed instrument epoch is not aligned with ship time")
        except InstrumentError as exc:
            raise PhysicsError(str(exc)) from exc
    food = clock.details.get("food")
    if food is not None:
        if food_inventory is None:
            raise PhysicsError("Installed food provisioning lacks real inventory")
        try:
            validate_food(food, inventory_kg=food_inventory.quantity * 1000.0)
        except FoodError as exc:
            raise PhysicsError(str(exc)) from exc
    equipment_wear = clock.details.get("equipment_wear")
    if equipment_wear is not None:
        if service_operations is None:
            raise PhysicsError("Maintenance wear lacks real individual runtime meters")
        try:
            validate_equipment_wear(equipment_wear, service_operations)
        except ElectricalError as exc:
            raise PhysicsError(str(exc)) from exc
    aux_edges = {x.source_id: x for x in edges
                 if x.reference.get("network") in {
                     "g19_motor", "g19_motor_protected",
                     "g19_local_dc", "g19_local_charger",
                     "g19_equipment_service"}}
    if electrical is not None:
        try:
            validate_electrical(electrical)
            audit_topology(water_nodes, edges, isolators, strict=True)
        except ElectricalError as exc:
            raise PhysicsError(str(exc)) from exc
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
    total_before = (sum(c["mass"] + c["fuel"] for c in cells.values())
                    + captured_co2 + refuge_captured_before
                    + retired_refuge_co2)
    lost = burned = water = oxygen_generated = 0.0
    water_state = clock.details.get("water")
    if water_state is not None:
        validate_water(water_state, {k: v.quantity * 1000.0
                                     for k, v in water_stocks.items()})
    water_report = None
    water_tick_report = None
    repairs = clock.details.get("repairs")
    if repairs is not None:
        validate_repairs(repairs)
    fabrication = clock.details.get("fabrication")
    if fabrication is not None:
        validate_fabrication(fabrication)
        if repairs is None or service_operations is None or water_state is None:
            raise PhysicsError("Installed machining has lost its repair, power or raw material ledger")
    welding = clock.details.get("welding")
    if welding is not None:
        validate_welding(welding)
        if repairs is None or service_operations is None or water_state is None:
            raise PhysicsError("Fitted welding has lost its spares, power or waste inventory")
    personnel_transfers = clock.details.get("personnel_transfers")
    if personnel_transfers is not None:
        try:
            validate_personnel_transfers(personnel_transfers)
        except IndexedTransferError as exc:
            raise PhysicsError(str(exc)) from exc
    hab_sync = clock.details.get("hab_sync")
    if hab_sync is not None:
        try:
            validate_hab_sync(hab_sync)
        except HabSyncError as exc:
            raise PhysicsError(str(exc)) from exc
    eva = clock.details.get("eva")
    flywheel_service = clock.details.get("flywheel_service")
    exterior_radiators = clock.details.get("exterior_radiators")
    propulsion_exterior = clock.details.get("propulsion_exterior")
    if propulsion_exterior is not None:
        try:
            validate_propulsion_exterior(propulsion_exterior)
        except PlumeAccessError as exc:
            raise PhysicsError(str(exc)) from exc
    if exterior_radiators is not None:
        try:
            validate_exterior_radiators(exterior_radiators)
        except ExteriorRadiatorError as exc:
            raise PhysicsError(str(exc)) from exc
    if flywheel_service is not None:
        try:
            flywheel_service = migrate_flywheel_service_v1(flywheel_service)
        except FlywheelServiceError as exc:
            raise PhysicsError(str(exc)) from exc
    if eva is not None:
        try:
            validate_eva(eva)
        except EVAError as exc:
            raise PhysicsError(str(exc)) from exc
    major_damage = clock.details.get("major_damage")
    if major_damage is not None:
        try:
            validate_major_damage(major_damage)
        except MajorDamageError as exc:
            raise PhysicsError(str(exc)) from exc
    waste_export_kg = 0.0
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
    cargo_climate = clock.details.get("cargo_environment")
    if cargo_climate is not None:
        try:
            validate_cargo_environment(cargo_climate, cargo)
        except CargoClimateError as exc:
            raise PhysicsError(str(exc)) from exc
    if set(rotors) != set(ROTORS):
        raise PhysicsError("Rotary machinery not commissioned")
    # Port jobs must not be allowed to change inertial mass during a
    # translation leg, and mooring retains the ship in a docked state.
    if contacts_active(cargo):
        if motion["command"] != "coast":
            raise PhysicsError("Main propulsion commanded while externally moored")
    if electrical is not None and electrical["shore"] is not None:
        import copy
        electrical = copy.deepcopy(electrical)
        if electrical["shore"]["connected"] and not contacts_active(cargo):
            # A lost berth never remains an infinite invisible external source.
            electrical["shore"]["connected"] = False
            electrical["last"] = dict(electrical["last"])
            electrical["last"]["shore_disconnect_reason"] = "physical_berth_lost"
    summary = {}
    duration = 0.0
    # Copy measured energy BEFORE its ordinary ship source dispatch ticks.
    # Finite flywheel rundown may credit only that same physical meter.
    if flywheel_service is not None and flywheel_service["rundowns"]:
        import copy
        original_rundown_electrical = copy.deepcopy(electrical)
        if original_rundown_electrical is None:
            raise PhysicsError("Flywheel rundown has no commissioned electrical meter")
    else:
        original_rundown_electrical = None

    while duration < seconds - 1e-9:
        dt = min(STEP_SECONDS, seconds - duration)
        duration += dt
        # Only physically delivered media earns per-machine output proof.
        media_output_kg = {name: 0.0 for name in PROCESS_METRICS}
        if (flywheel_service is not None and flywheel_service["rundowns"]
                and electrical is not None):
            # An attended supervised run-down does not keep spinning when
            # the operator leaves the vacuum bay, becomes disabled or loses
            # their actual life-support suit. The original rotor charge
            # persists; standby is a dispatch command, NOT a spin deletion.
            from evennia.objects.models import ObjectDB
            ids = [int(job["worker"][1:]) for job in
                   flywheel_service["rundowns"].values()]
            on_watch = {crew.dbref: crew for crew in
                        ObjectDB.objects.filter(id__in=ids)}
            import copy
            electrical = copy.deepcopy(electrical)
            for name, job in flywheel_service["rundowns"].items():
                worker = on_watch.get(job["worker"])
                sound = bool(
                    worker is not None
                    and _flywheel_suit_ready(worker, job["room"], {
                        **clock.details, "eva": eva,
                        "electrical": electrical,
                        "bay_access": clock.details.get("bay_access")})
                    and equipment[name].condition not in _BROKEN
                    and isolators[module_breaker(name)].condition not in _BROKEN
                    and isolators[module_breaker(name)].setting == "closed")
                electrical["flywheels"][name]["mode"] = (
                    "discharge" if sound else "standby")
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

        if electrical is not None:
            try:
                electrical, tripped = step_protection(electrical, isolators, dt)
            except ElectricalError as exc:
                raise PhysicsError(str(exc)) from exc
            for breaker_id in tripped:
                switch = isolators[breaker_id]
                before_trip = _snapshot(switch)
                spec = dict(switch.details)
                spec["physics_power_trip_latched"] = True
                spec["physics_power_trip_reason"] = "measured_overcurrent"
                switch.details = spec
                switch.setting = "open"
                switch.revision += 1
                switch.save(update_fields=["details", "setting", "revision"])
                _event(switch, "electrical_overcurrent_trip", before_trip)
        power = _power(equipment, edges, isolators, clock.details["load_profile"],
                       ledger=electrical, dt_s=dt,
                       moored=contacts_active(cargo), nodes=water_nodes,
                       cartridge_kg=(cartridge_stock.quantity * 1000.0
                                     if cartridge_stock is not None else None))
        def motor_ready(name):
            return (electrical is None or motor_power(
                name, nodes=power["nodes"], equipment=equipment,
                edges=aux_edges, switches=isolators))
        if service_operations is not None:
            try:
                service_operations = step_service_operations(
                    service_operations, dt, nodes=power["nodes"],
                    equipment=equipment, edges=aux_edges,
                    switches=isolators, supply_assured=power["assured"])
                # The six original machine-shop mechanisms have actual local
                # simulated spindle or hydraulic outputs, with inertia even
                # after an electrician opens the source. Only a running,
                # independently fused service may drive them. Neither a
                # live panel nor an ON command alone produces spindle speed.
                operating_shop = set(service_operations["last"]["operating"])
                for tool_id in WORKSHOP_DRIVES:
                    tool = equipment.get(tool_id)
                    if tool is None:
                        raise PhysicsError("Original workshop machine disappeared")
                    earlier = tool.details.get(GAUGE_FIELD)
                    latest = step_workshop_gauge(
                        tool_id, earlier, dt_s=dt,
                        now_s=last + duration,
                        driven=tool_id in operating_shop)
                    if earlier != latest:
                        new_details = dict(tool.details)
                        new_details[GAUGE_FIELD] = latest
                        tool.details = new_details
                        tool.revision += 1
                        changed_equipment.add(tool.key)
                if fabrication is not None and fabrication["jobs"]:
                    from evennia.objects.models import ObjectDB
                    involved = {
                        job["worker"] for job in fabrication["jobs"].values()}
                    live_workers = {
                        person.dbref: person for person in ObjectDB.objects.filter(
                            id__in=[int(ref[1:]) for ref in involved])}
                    ready_people = set()
                    for worker, person in live_workers.items():
                        hp = CanonicalShipState.objects.filter(
                            pk="crew_health:" + worker, source_model=MODEL).first()
                        if (getattr(getattr(getattr(person, "location", None),
                                            "db", None), "ox_space_id", None)
                                != FABRICATION_ROOM or
                                getattr(person.db, "ox_terminal_dead", False) or
                                hp is not None and hp.condition not in {"fit", "impaired"} or
                                getattr(person.db, "crew_role", None)
                                not in {"chief_engineer", "watch_engineer"}
                                and not person.check_permstring("Developer")):
                            continue
                        zone = zones.get(FABRICATION_ROOM)
                        shop = cells.get(zone)
                        if (shop is not None and shop["mass"] > 0 and
                                shop["damage"] < .2 and shop["burn"] == 0
                                and shop["leak"] == 0 and
                                278.15 <= shop["temperature"] <= 313.15
                                and 80000 <= _cell_pressure(shop) <= 120000):
                            ready_people.add(worker)
                    readings = {}
                    for machine in fabrication["jobs"]:
                        unit = equipment[machine]
                        gauge = unit.details.get(GAUGE_FIELD)
                        readings[machine] = {
                            "operating": machine_output_confirmed(
                                machine, unit.details, observed_s=last + duration,
                                operating=machine in operating_shop),
                            "cumulative_output": (
                                gauge["cumulative_output"] if gauge else 0.0),
                        }
                    try:
                        fabrication, newly_made = step_batches(
                            fabrication, dt, observed=readings,
                            present=ready_people,
                            free_part_kg={
                                worker: max(0.0, FABRICATION_HAND_KG -
                                            repairs["carried_kg"].get(worker, 0.0))
                                for worker in involved})
                        for worker, kg, source in newly_made:
                            repairs = credit_repair_parts(
                                repairs, actor=worker, kg=kg)
                            CanonicalShipEvent.objects.create(
                                component_key="equipment:" + source["machine"],
                                operation="g19_real_machine_part_finished",
                                before={"workpiece_kg": source["input_kg"],
                                        "request_id": source["request_id"]},
                                after={"held_repair_part_kg": kg,
                                       "workshop_offcuts_kg": source["offcuts_kg"],
                                       "worker": worker},
                                actor_dbref=worker, game_time=last + duration)
                    except FabricationError as exc:
                        raise PhysicsError(str(exc)) from exc
                if welding is not None:
                    # A powered cell isn't a weld. Only a staffed, physically
                    # loaded arc job can produce a new measurable heat/mass
                    # output at the real SHOP-WELD pressure cell.
                    from evennia.objects.models import ObjectDB
                    workers = {job["worker"] for job in welding["jobs"].values()}
                    people = {person.dbref: person for person in
                              ObjectDB.objects.filter(
                                  id__in=[int(ref[1:]) for ref in workers])}
                    welded_present = set()
                    welding_zone = cells.get(zones.get(WELDING_ROOM))
                    if welding_zone is None:
                        raise PhysicsError("Original weld bay has no actual pressure-cell gas")
                    pressure_here = _cell_pressure(welding_zone)
                    safe_shop = bool(
                        80000 <= pressure_here <= 120000 and
                        278.15 <= welding_zone["temperature"] <= 313.15 and
                        welding_zone["oxygen"] > .17 * welding_zone["mass"] and
                        welding_zone["co2"] <= .015 * welding_zone["mass"] and
                        welding_zone["smoke"] <= .00001 * welding_zone["mass"] and
                        welding_zone["burn"] == 0 and welding_zone["leak"] == 0
                        and welding_zone["damage"] < .2)
                    if safe_shop:
                        for worker, person in people.items():
                            hp = CanonicalShipState.objects.filter(
                                pk="crew_health:" + worker, source_model=MODEL).first()
                            if (getattr(getattr(getattr(person, "location", None),
                                                "db", None), "ox_space_id", None)
                                    == WELDING_ROOM and
                                    not getattr(person.db, "ox_terminal_dead", False) and
                                    (hp is None or hp.condition in {"fit", "impaired"}) and
                                    (getattr(person.db, "crew_role", None) in {
                                        "chief_engineer", "watch_engineer"}
                                     or person.check_permstring("Developer"))):
                                welded_present.add(worker)
                    try:
                        welding, weld_finished, welding_heat = step_welds(
                            welding, dt,
                            active=set(service_operations["last"]["operating"])
                                   & WELDING_CELLS,
                            present=welded_present, air_safe=safe_shop,
                            capacity={
                                worker: max(0.0, MAX_HAND_PARTS_KG -
                                      repairs["carried_kg"].get(worker, 0.0))
                                for worker in workers})
                        for worker, mass, provenance in weld_finished:
                            repairs = credit_repair_parts(
                                repairs, actor=worker, kg=mass)
                            CanonicalShipEvent.objects.create(
                                component_key="equipment:" + provenance["machine"],
                                operation="g19_attended_real_welded_joint_finished",
                                before={"base_kg": provenance["base_kg"],
                                        "filler_kg": provenance["filler_kg"],
                                        "request_id": provenance["request_id"]},
                                after={"joined_part_kg": mass,
                                       "retained_slag_kg": provenance["slag_kg"],
                                       "worker": worker},
                                actor_dbref=worker, game_time=last + duration)
                    except WeldError as exc:
                        raise PhysicsError(str(exc)) from exc
                    if welding_heat:
                        welding_zone["energy"] += sum(welding_heat.values())
                        welding_zone["temperature"] = (
                            welding_zone["energy"] /
                            (welding_zone["capacity"] +
                             welding_zone["mass"] * CP_GAS_KJ_KG_K))
                    for name in WELDING_CELLS:
                        machine = equipment.get(name)
                        if machine is None:
                            raise PhysicsError("Original weld cell missing from actual installed world")
                        prior = machine.details.get("physics_weld_arc_gauge")
                        amount = welding_heat.get(name, 0.0)
                        if amount > 0 or prior is not None:
                            details = dict(machine.details)
                            details["physics_weld_arc_gauge"] = {
                                "last_arc_kj": amount,
                                "cumulative_arc_kj": (
                                    (prior or {}).get("cumulative_arc_kj", 0.0)
                                    + amount),
                                "sample_game_time_s": last + duration,
                            }
                            machine.details = details
                            machine.revision += 1
                            changed_equipment.add(machine.key)
                if equipment_wear is not None:
                    equipment_wear, wear_events = step_equipment_wear(
                        equipment_wear, service_operations, equipment)
                    for affected, condition in wear_events:
                        machine = equipment[affected]
                        prior = _snapshot(machine)
                        machine.condition = condition
                        details = dict(machine.details)
                        details["physics_wear_stage"] = condition
                        if condition == "faulted":
                            # Real maintenance repair, rather than merely
                            # restoring a feeder, is required to restart.
                            details["physics_online"] = False
                            details["physics_commanded_on"] = False
                            details["physics_startup_s"] = 0.0
                        machine.details = details
                        machine.revision += 1
                        changed_equipment.add(machine.key)
                        _event(machine, "g19_secondary_machine_wear_trip",
                               prior)
            except ElectricalError as exc:
                raise PhysicsError(str(exc)) from exc
        irrigation_plan = {}
        if cultivation is not None:
            operating = set(service_operations["last"]["operating"])
            grow_operating = {
                f"GROW-{number}" for number in GROW_BAYS
                if all(f"GROW-{number}-{kind}" in operating
                       for kind in ("CTRL", "NUTRIENT"))
            }
            grow_air = set()
            for number, room in GROW_BAYS.items():
                zone = zones.get(room)
                cell = cells.get(zone)
                if cell is None:
                    continue
                pressure_pa = _cell_pressure(cell)
                oxygen_moles = cell["oxygen"] / 0.032
                other_moles = max(0.0, cell["mass"] - cell["oxygen"]) / 0.029
                partial_o2 = (pressure_pa * oxygen_moles /
                              (oxygen_moles + other_moles)
                              if oxygen_moles + other_moles else 0.0)
                if (80000 <= pressure_pa <= 120000
                        and 16000 <= partial_o2 <= 26000
                        and 278.15 <= cell["temperature"] <= 313.15
                        and cell["co2"] <= 0.005 * cell["mass"]
                        and cell["smoke"] <= 0.00001 * cell["mass"]
                        and cell["damage"] < 0.20 and cell["leak"] == 0
                        and cell["burn"] == 0):
                    grow_air.add(f"GROW-{number}")
            try:
                irrigation_plan = plan_irrigation(
                    cultivation, dt, operating=grow_operating,
                    air_safe=grow_air)
            except CultivationError as exc:
                raise PhysicsError(str(exc)) from exc
        if water_state is not None:
            hardware = _water_hardware(
                water_state, equipment, edges, isolators,
                water_nodes, power, motor_ready=motor_ready)
            try:
                water_state, balances, water_report = step_water(
                    water_state, dt,
                    stocks={key: item.quantity * 1000.0
                            for key, item in water_stocks.items()},
                    hardware=hardware, crew_count=40,
                    cultivation_demand_kg=(sum(irrigation_plan.values())
                                           if cultivation is not None else None),
                    food_rehydration_demand_kg=(
                        0.0 if food is not None else None))
            except WaterError as exc:
                raise PhysicsError(str(exc)) from exc
            for side in "AB":
                treated = water_report[f"processed_{side}_kg"]
                for kind in ("WASTE-PROC", "WATER-PROC"):
                    media_output_kg[f"{kind}-{side}"] += treated
            for key, amount in balances.items():
                water_stocks[key].quantity = amount / 1000.0
            if cultivation is not None:
                try:
                    cultivation = step_cultivation(
                        cultivation, dt, planned=irrigation_plan,
                        water_delivered_kg=water_report["cultivation_water_kg"])
                except CultivationError as exc:
                    raise PhysicsError(str(exc)) from exc
            if water_tick_report is None:
                water_tick_report = dict(water_report)
            else:
                for key, value in water_report.items():
                    if isinstance(value, bool):
                        water_tick_report[key] = water_tick_report[key] or value
                    elif isinstance(value, (int, float)):
                        water_tick_report[key] += value
            produced = water_report["oxygen_kg"]
            if produced:
                side = hardware["oxygen_side"]
                zone = owners.get(f"ECLSS-{side}")
                if zone not in cells:
                    raise PhysicsError("Oxygen generator not in verified bounded atmosphere")
                cell = cells[zone]
                # Electrolytic O2 is oxygen MASS, not a pressure-screen flag.
                cell["oxygen"] += produced
                cell["mass"] += produced
                cell["energy"] += produced * CP_GAS_KJ_KG_K * cell["temperature"]
                cell["temperature"] = cell["energy"] / (
                    cell["capacity"] + cell["mass"] * CP_GAS_KJ_KG_K)
                oxygen_generated += produced
            # Only the oxygen product remains aboard as breathable gas.
            # H2, technical process use and rejected wastewater are charged
            # to mission-fluid mass instead of making ship weight constant.
            # Unrecoverable domestic/cultivation/process water is transferred
            # to explicitly counted nonpotable mission sinks still on board;
            # only the validated H2 exterior vent removes ship mass here.
            mass_departed = water_report["hydrogen_kg"]
            if motion["mission_fluids_kg"] + 1e-7 < mass_departed:
                raise PhysicsError("Spent mission fluid exceeds actual ship mass")
            motion["mission_fluids_kg"] -= mass_departed
        # Propulsion hardware is represented by durable world-owned motion
        # condition flags until dedicated drive/RCS installations are mapped.
        # A failed drive can coast, but cannot silently resume thrust.
        # Authored local propulsion stations are real operating equipment.
        # A damaged local safing/controller makes both thruster families
        # unavailable, irrespective of the last commanded software state.
        controller_sound = (
            equipment.get("LCS-PROP") is not None
            and equipment["LCS-PROP"].condition not in _BROKEN)
        remote_panel_sound = any(
            equipment.get(key) is not None and
            equipment[key].condition not in _BROKEN
            for key in ("LP-CMD-PRIMARY", "LP-PROP-CTRL"))
        if not controller_sound:
            # A shared controller failure must not quietly resume a latched
            # thrust order after somebody replaces the broken electronics.
            motion["command"] = "coast"
            motion["attitude_command"] = "hold"
            if motion["drive_condition"] == "operational":
                motion["drive_condition"] = "inhibited"
                motion["drive_trip_reason"] = "propulsion_control_loss"
            if motion["rcs_condition"] == "operational":
                motion["rcs_condition"] = "inhibited"
        drive_operational = (
            motion.get("drive_condition", "operational") == "operational"
            and controller_sound and remote_panel_sound)
        rcs_operational = (
            motion.get("rcs_condition", "operational") == "operational"
            and controller_sound and remote_panel_sound)
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
            and equipment.get(name + "-RADIAL-FREIGHT-HANDLER") is not None
            and equipment[name + "-RADIAL-FREIGHT-HANDLER"].condition not in _BROKEN
            and motor_ready(name + "-RADIAL-FREIGHT-HANDLER")
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
        # These are separate full-size commercial portals, not the 50-tonne
        # internal spine. A real contact, stationary indexed drum, a sealed
        # inner gallery door and sound radial rail are all prerequisites.
        busy_waste_drums = (
            {job["portal_id"][:5] for job in
             water_state.get("waste_offload", {}).get("jobs", {}).values()}
            if water_state is not None else set())
        requested_ports = sorted(
            portal for portal, job in cargo.get("port_jobs", {}).items()
            if not job.get("paused", False)
            and portal[:5] not in busy_waste_drums)
        free_mw = max(0.0, power["available_mw"] - power["requested_mw"])
        ready_ports = set()
        for portal in requested_ports:
            drum = portal[:5]
            rotor = rotors[drum]
            access = next((x for x in access_rows
                           if x.source_id == "ACC-" + portal), None)
            sound_handler = (equipment.get(drum + "-RADIAL-FREIGHT-HANDLER")
                             is not None and
                             equipment[drum + "-RADIAL-FREIGHT-HANDLER"].condition
                             not in _BROKEN)
            if (free_mw + 1e-9 >= PORT_AUX_MW and power["assured"]
                    and access and access.condition not in _BROKEN
                    and access.setting == "closed" and sound_handler
                    and motor_ready(drum + "-RADIAL-FREIGHT-HANDLER")
                    and rotor["hardlock"] and rotor["brake"]
                    and rotor["target_rpm"] == 0
                    and abs(rotor["rpm"]) <= 0.001
                    and not rotor["passenger_indexer"]
                    and not rotor["freight_collar"]
                    and drum not in cargo["jobs"]):
                ready_ports.add(portal)
                free_mw -= PORT_AUX_MW
        cargo, finished_ports = step_port_jobs(
            cargo, dt, available_portals=ready_ports,
            capacity_kg=motion["cargo_capacity_kg"])
        motion["cargo_mass_kg"] = onboard_mass_kg(cargo)
        port_load = len(ready_ports) * PORT_AUX_MW
        if port_load:
            power["requested_mw"] += port_load
            power["dispatched_mw"] += port_load
            power["generation_fraction"] = (
                power["dispatched_mw"] / power["available_mw"])

        # Sealed solid-waste removal reuses the same fitted radial freight
        # handler and commercial port. Mass first follows the surveyed fixed
        # spine, remains INBOARD in a time-bound carrier, and leaves the ship
        # only when its separately authorised berth actually accepts it.
        # These phases never spend cargo inventory or fabricate a spare bin.
        if water_state is not None and water_state["waste_offload"]["jobs"]:
            by_access = {x.source_id: x for x in access_rows}
            by_pressure = {x.source_id: x for x in pressure_rows}
            freight_ready = set()
            waste_ports_ready = set()
            available = max(0.0, power["available_mw"] - power["requested_mw"])
            for receiver_id, job in sorted(
                    water_state["waste_offload"]["jobs"].items()):
                if job["paused"]:
                    continue
                if job["phase"] in {"hauling", "aborting", "returning"}:
                    if (power["assured"] and available + 1e-9 >= CARGO_TRANSFER_MW
                            and motor_ready(job["portal_id"][:5] + "-RADIAL-FREIGHT-HANDLER")
                            and _waste_freight_ready(
                                job, water_state, rotors=rotors,
                                equipment=equipment, access=by_access,
                                pressure=by_pressure, zones=zones,
                                cargo=cargo)):
                        freight_ready.add(receiver_id)
                        available -= CARGO_TRANSFER_MW
                elif job["phase"] == "offloading":
                    if (power["assured"] and available + 1e-9 >= WASTE_PORT_AUX_MW
                            and motor_ready(job["portal_id"][:5] + "-RADIAL-FREIGHT-HANDLER")
                            and _waste_port_ready(
                                job, rotors=rotors, equipment=equipment,
                                access=by_access, cargo=cargo)):
                        waste_ports_ready.add(receiver_id)
                        available -= WASTE_PORT_AUX_MW
            try:
                water_state, new_stocks, waste_step = step_offload(
                    water_state, dt, freight_ready=freight_ready,
                    port_ready=waste_ports_ready,
                    stocks={cat: water_stocks[cat].quantity * 1000.0
                            for cat in ("sanitary", "industrial", "hazardous")})
            except WaterError as exc:
                raise PhysicsError(str(exc)) from exc
            for cat, qty in new_stocks.items():
                water_stocks[cat].quantity = qty / 1000.0
            exported = waste_step["exported_kg"]
            if exported:
                try:
                    motion = debit_ship_mass_for_waste(
                        motion, waste_step["exported"])
                except WaterError as exc:
                    raise PhysicsError(str(exc)) from exc
                waste_export_kg += exported
            waste_load = (len(freight_ready) * CARGO_TRANSFER_MW +
                          len(waste_ports_ready) * WASTE_PORT_AUX_MW)
            if waste_load:
                power["requested_mw"] += waste_load
                power["dispatched_mw"] += waste_load
                power["generation_fraction"] = (
                    power["dispatched_mw"] / power["available_mw"])
        rotary_load = motion_power_mw(rotors)
        rotary_can_power = (
            power["assured"] and
            power["available_mw"] - power["requested_mw"] >= rotary_load)
        def sound(identifier):
            unit = equipment.get(identifier)
            return bool(unit and unit.condition not in _BROKEN)

        # Installed B-prime HAB bearings require two sound bearings, but
        # either of its independently maintainable drives can motor the ring.
        # Workshop rotor likewise has two separately maintainable drives.
        rotor_equipment = {
            "HAB": (
                sound("HAB-BEARING-FORE") and sound("HAB-BEARING-AFT")
                and any(sound(x) and motor_ready(x)
                        for x in ("HAB-DRIVE-FORE", "HAB-DRIVE-AFT"))
            ),
            "WR-01": (
                sound("WR-BEARING-A") and sound("WR-BEARING-B")
                and sound("WR-01")
                and any(sound(x) and motor_ready(x)
                        for x in ("WR-DRIVE-A", "WR-DRIVE-B"))
            ),
            **{
                name: all(any(
                    sound(f"BE-{bearing:02d}-LUBE-{mode}")
                    and motor_ready(f"BE-{bearing:02d}-LUBE-{mode}")
                    for mode in ("N", "S"))
                          for bearing in (2 * index - 1, 2 * index))
                for index, name in enumerate(DRUMS, 1)
            },
        }
        rotary_power_by_unit = {
            name: rotary_can_power and (
                sound(name + "-ROT-PWR") if name in DRUMS else
                sound("WR-ROT-PWR-IF") if name == "WR-01" else True
            ) for name in ROTORS
        }
        extension_ok = (
            sound("WR-EXTEND-SHOP") and motor_ready("WR-EXTEND-SHOP")
            and sound("WR-EXTEND-STORES") and motor_ready("WR-EXTEND-STORES"))
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
            rotors, dt, powered=rotary_power_by_unit,
            equipment_ok=rotor_equipment, extension_ok=extension_ok)
        if hab_sync is not None:
            station = hab_sync.get("station")
            hardware_ok = bool(
                station and all(
                    equipment.get(f"IX-{station}-{suffix}") is not None
                    and equipment[f"IX-{station}-{suffix}"].condition not in _BROKEN
                    for suffix in ("DRIVE", "CARRIER", "FIXED-COLLAR", "ROT-COLLAR"))
                and motor_ready(f"IX-{station}-DRIVE"))
            try:
                hab_sync = step_hab_sync(
                    hab_sync, dt, hab_rpm=rotors["HAB"]["rpm"],
                    hab_phase_rad=rotors["HAB"]["phase_rad"],
                    powered=bool(rotary_power_by_unit["HAB"]),
                    hardware_ok=hardware_ok)
            except HabSyncError as exc:
                raise PhysicsError(str(exc)) from exc
        if rotary_load and rotary_can_power:
            power["requested_mw"] += rotary_load
            power["dispatched_mw"] += rotary_load
            power["generation_fraction"] = (
                power["dispatched_mw"] / power["available_mw"])
        ftl_field = equipment.get("FTL-TRANSLATION-FIELD")
        field_healthy = bool(
            ftl_field and ftl_field.condition not in _BROKEN
            and equipment.get("LCS-FTL") is not None
            and equipment["LCS-FTL"].condition not in _BROKEN
            and motor_ready("FTL-TRANSLATION-FIELD"))
        ftl_active = (motion.get("ftl_leg") or {}).get("status") == "engaged"
        try:
            motion, ftl_aux = advance_leg(
                motion, dt, field_healthy=field_healthy,
                power_headroom_mw=power["available_mw"] - power["requested_mw"])
        except NavigationError as exc:
            raise PhysicsError(str(exc)) from exc
        if ftl_aux:
            power["requested_mw"] += ftl_aux
            power["dispatched_mw"] += ftl_aux
            power["generation_fraction"] = (
                power["dispatched_mw"] / power["available_mw"])
        motion = _advance_motion(
            motion, dt, power,
            drive_operational=drive_operational and not ftl_active
                              and not contacts_active(cargo),
            rcs_operational=rcs_operational and not ftl_active
                            and not contacts_active(cargo))
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
        heat += FTL_HEAT_KW * dt if ftl_aux else 0.0
        drive_cooling_kw = 0.0
        connected_lt = _reachable(
            edges, isolators, "lt_cooling", ["NODE-LT-PLANT"])
        # One physical LT radiator budget serves both propulsion and rooms.
        # A powered ship bus or running plant flag is not an alternative to
        # the LT motor's real fuse, feeder and connected coolant circuit.
        # The G18 legacy path retains its original protected-service gate.
        lt_service_assured = (
            power["assured"] and
            (electrical is not None or
             (power["essential_assured"] and "PWR-PROT" in power["nodes"]))
        )
        lt_radiators = sum(_on(equipment, f"RAD-LT-{n}")
                           for n in range(1, 5))
        try:
            lt_budget = allocate_lt_cooling(
                seconds=dt, drive_heat_kj=heat,
                active_radiators=lt_radiators,
                coolant_connected=len(connected_lt) > 1,
                plant_running=_on(equipment, "LT-PLANT"),
                motor_ready=motor_ready("LT-PLANT"),
                service_assured=lt_service_assured,
                drive_limit_kw=DRIVE_COOLING_KW)
        except ElectricalError as exc:
            raise PhysicsError(str(exc)) from exc
        drive_cooling_kw = lt_budget["drive_kw"]
        heat = max(0.0, heat - drive_cooling_kw * dt)
        if heat >= DRIVE_THERMAL_BUFFER_KJ:
            heat = DRIVE_THERMAL_BUFFER_KJ
            motion["drive_condition"] = "thermal_trip"
            motion["drive_trip_reason"] = "propulsion_cooling_limit"
            motion["command"] = "coast"
            if (motion.get("ftl_leg") or {}).get("status") == "engaged":
                leg = dict(motion["ftl_leg"])
                leg["status"] = "aborted"
                leg["reason"] = "propulsion_thermal_trip"
                motion["ftl_leg"] = leg
        motion["drive_heat_kj"] = heat
        if drive_load:
            power["requested_mw"] += drive_load
            power["dispatched_mw"] += drive_load
            power["generation_fraction"] = (
                power["dispatched_mw"] / power["available_mw"])
            power["shortfall_mw"] = max(
                0.0, power["requested_mw"] - power["available_mw"])
        # No unproven infinite battery/flywheel bridge or magic auto load shedding.
        protected_power = (power["protected_assured"]
                           if electrical is not None else
                           (power["essential_assured"]
                            and "PWR-PROT" in power["nodes"]))
        powered = power["assured"] and bool(
            {"PWR-MSB-A", "PWR-MSB-B", "PWR-PROT"} & power["nodes"])
        active_air_trains = {
            eclss for eclss, node in
            (("ECLSS-A", "NODE-HAB-06-ECLSS-A-LP"),
             ("ECLSS-B", "NODE-HAB-08-ECLSS-B-LP"))
            if powered and _on(equipment, eclss) and node in power["nodes"]
            and motor_ready(eclss)
        }
        # A powered processor cannot drive fans in another isolated duct
        # network. Motorised mixing requires a source on the same *currently
        # conducting* atmosphere graph; passive pressure movement does not.
        active_spine_air = {
            name for name in ("SPINE-AIR-FWD", "SPINE-AIR-AFT")
            if electrical is not None and powered and _on(equipment, name)
            and motor_ready(name)
        }
        air_source_nodes = [
            node_id for train in sorted(active_air_trains | active_spine_air)
            for node_id in atmosphere_source_nodes.get(train, ())
        ]
        # An AHU's physical ducts remain open after losing power, but do
        # not become infinite electrically driven mixing engines.
        all_ahu_nodes = {
            f"NODE-HAB-{n:02d}-AHU-AIR" for n in range(1, 9)
        }
        powered_ahu_nodes = {
            f"NODE-HAB-{n:02d}-AHU-AIR" for n in range(1, 9)
            if _on(equipment, f"HAB-{n:02d}-AHU")
            and motor_ready(f"HAB-{n:02d}-AHU")
        }
        # A source cannot energise fans beyond a STOPPED local AHU merely
        # because a distant distribution panel is still live. Exclude dead
        # manifold motors only from the *forced mixing* traversal, not the
        # physical atmosphere/pressure diffusion graph below.
        stopped_ahu_nodes = all_ahu_nodes - powered_ahu_nodes
        powered_air_edges = [
            edge for edge in edges
            if edge.reference["network"] == "atmosphere"
            and not stopped_ahu_nodes.intersection((
                edge.reference["from_node"], edge.reference["to_node"]))
        ]
        fan_nodes = (_reachable(
            powered_air_edges, isolators, "atmosphere", air_source_nodes)
                     if air_source_nodes else set())
        spine_discharge_nodes = {
            "SPINE-AIR-FWD": "NODE-SPINE-AIR-A-BOW",
            "SPINE-AIR-AFT": "NODE-SPINE-AIR-B-AFT",
        }
        spine_flow_ready = any(
            spine_discharge_nodes[station] in fan_nodes
            for station in active_spine_air)
        air_on = bool(
            fan_nodes.intersection(powered_ahu_nodes) or spine_flow_ready)
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
                media_output_kg[train] += removed
                cells[zone]["co2"] -= removed
                cells[zone]["mass"] -= removed
                cells[zone]["energy"] -= removed * CP_GAS_KJ_KG_K * cells[zone]["temperature"]
                captured_co2 += removed
                cells[zone]["temperature"] = cells[zone]["energy"] / (
                    cells[zone]["capacity"] + cells[zone]["mass"] * CP_GAS_KJ_KG_K)
        # Real atmospheric edges remain present for passive pressure flow;
        # forced mixing uses the separate powered-air reachability above.
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
            from_node, to_node = (
                edge.reference["from_node"], edge.reference["to_node"])
            powered_local_fans = all(
                endpoint not in all_ahu_nodes or endpoint in powered_ahu_nodes
                for endpoint in (from_node, to_node))
            if (air_on and from_node in fan_nodes and to_node in fan_nodes
                    and powered_local_fans):
                # Counterflow is an exchange, not doubled net mass.
                x = min(2.0 * dt, 0.05 * a["mass"], 0.05 * b["mass"])
                _parcel(a, b, x)
                _parcel(b, a, x)
                # Site-specific fan proof is actual local duct parcel motion,
                # not an inferred motor current or passive gas equilibration.
                for fan in AIR_HANDLERS:
                    if (f"NODE-{fan}-AIR" in (from_node, to_node)
                            and f"NODE-{fan}-AIR" in powered_ahu_nodes):
                        media_output_kg[fan] += x
                for fan in SPINE_FANS:
                    if (fan in active_spine_air and
                            any(node in (from_node, to_node)
                                for node in atmosphere_source_nodes.get(fan, ()))):
                        media_output_kg[fan] += x
            pa, pb = _cell_pressure(a), _cell_pressure(b)
            if abs(pa - pb) > 1:
                donor, receiver = (a, b) if pa > pb else (b, a)
                _parcel(donor, receiver, min(0.12 * dt * abs(pa - pb) / 101325.0,
                                             donor["mass"] * 0.10))

        # Real cargo skids reject heat only through their own original
        # rotary LT interface into the same radiator capacity used by
        # propulsion and habitation. Commercial cooling remains secondary
        # to occupied-space heat removal.
        cargo_cooling_kw = 0.0
        if cargo_climate is not None:
            gallery_ambient = {
                drum: cells["PZ-" + drum + "-SVC"]["temperature"]
                for drum in CARGO_DRUMS
                if "PZ-" + drum + "-SVC" in cells
            }
            cargo_coolant_nodes = {
                "NODE-" + drum + "-LT-IF" for drum in CARGO_DRUMS
                if ("NODE-" + drum + "-LT-IF" in connected_lt
                    and equipment.get(drum + "-LT-IF") is not None
                    and equipment[drum + "-LT-IF"].condition not in _BROKEN)
            }
            try:
                cargo_climate, gallery_exchange, cargo_cooling_kw = (
                    step_cargo_environment(
                        cargo_climate, cargo, dt,
                        ambient_by_drum=gallery_ambient,
                        operating_machines=(
                            service_operations["last"]["operating"]
                            if service_operations is not None else ()),
                        connected_lt_nodes=cargo_coolant_nodes,
                        cooling_budget_kw=min(
                            6.0 * 20.0, lt_budget["environment_kw"] * 0.10)))
            except CargoClimateError as exc:
                raise PhysicsError(str(exc)) from exc
            for drum, heat_kj in gallery_exchange.items():
                zone = "PZ-" + drum + "-SVC"
                gallery = cells[zone]
                gallery["energy"] -= heat_kj
                if gallery["energy"] <= 0:
                    raise PhysicsError("Cargo heat transfer emptied gallery sensible energy")
                gallery["temperature"] = gallery["energy"] / (
                    gallery["capacity"] +
                    gallery["mass"] * CP_GAS_KJ_KG_K)
            if cargo_cooling_kw > lt_budget["environment_kw"] + 1e-7:
                raise PhysicsError("Cargo cooling exceeded available LT radiator budget")

        # Existing LT coolant route plus finite live radiator wings.
        cooling_nodes = connected_lt
        cool_zones = {node_zones.get(n) for n in cooling_nodes}
        cool_zones &= set(cells)
        # Propulsion rejection was already debited from this *same*
        # motor-and-radiator-limited capacity earlier in this tick.
        total_cool_kw = max(
            0.0, lt_budget["environment_kw"] - cargo_cooling_kw)
        per_zone_kw = total_cool_kw / len(cool_zones) if cool_zones else 0.0

        fire_starts = [
            "NODE-" + pump for pump in PROTECTED_FIRE_MOTORS
            if _on(equipment, pump) and (
                fire_pump_service_ready(
                    pump, nodes=power["nodes"], equipment=equipment,
                    edges=aux_edges, switches=isolators,
                    normal_assured=powered,
                    protected_assured=protected_power)
                if electrical is not None else powered)
        ]
        fire_nodes = _reachable(edges, isolators, "fire_main", fire_starts)
        fire_water_delivered_kg = 0.0
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
                fire_water_delivered_kg += mist_kg
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
        # If two fire pumps share one live header, spray is proven but
        # individually attributed pump output is unknown. A single
        # operating pump can be credited with its real finite discharge.
        if electrical is not None:
            for name, kg in attributed_fire_discharge(
                    [node[5:] for node in fire_starts],
                    fire_water_delivered_kg,
                    demand_present=any(c["mist"] > 0 for c in cells.values())).items():
                media_output_kg[name] += kg
        local_charge_mw = 0.0
        if local_backup is not None:
            prior_charge = local_backup["meter"]["charged_kwh"]
            try:
                local_backup = step_local_backup(
                    local_backup, dt, nodes=power["nodes"],
                    equipment=equipment, edges=aux_edges, switches=isolators,
                    producer_nodes=power["producer_nodes"],
                    # Charger headroom is limited by the *deliverable*
                    # 3.3-MW main bus as well as live generation. Multiple
                    # online generators do not enlarge the ship bus rating.
                    producing_mw=min(power["producer_available_mw"],
                                     power["main_available_mw"]),
                    other_requested_mw=power["requested_mw"],
                    # Conducting copper does not imply sufficient bus MW.
                    # A physically connected but browned-out appliance must
                    # be eligible to draw its finite local DC reserve.
                    normal_assured=power["essential_assured"])
            except ElectricalError as exc:
                raise PhysicsError(str(exc)) from exc
            local_charge_mw = local_backup["last"]["grid_charge_requested_mw"]
            if not math.isclose(
                    local_backup["meter"]["charged_kwh"] - prior_charge,
                    local_charge_mw * dt / 3.6,
                    rel_tol=1e-10, abs_tol=1e-7):
                raise PhysicsError("Local charger energy escaped the generator ledger")
            if local_charge_mw > 0:
                power["requested_mw"] += local_charge_mw
                power["dispatched_mw"] += local_charge_mw
        if refuge_scrubbers is not None:
            # The actual normal refuge air load or the individually surveyed
            # and fully supplied local DC battery may drive its own package.
            # The main board's mere presence is insufficient: the original
            # appliance endpoint must be energised as well.
            normal_refuges = {
                pack for pack in REFUGE_PACKS
                if "NODE-PWR-" + pack in power["nodes"]
                and power["essential_assured"]
            }
            local_refuges = (
                set(local_backup["last"].get(
                    "active_local_consumers", {}).values())
                if local_backup is not None else set())
            try:
                refuge_scrubbers, cells = step_refuge_scrubbers(
                    refuge_scrubbers, dt,
                    powered_consumers=normal_refuges | local_refuges,
                    equipment=equipment, room_zones=zones, cells=cells)
            except RefugeAirError as exc:
                raise PhysicsError(str(exc)) from exc
        if electrical is not None:
            try:
                electrical = step_energy(
                    electrical, power, dt,
                    actual_requested_mw=power["requested_mw"],
                    external_charge_mw=local_charge_mw)
                if not math.isclose(
                        electrical["last"]["local_battery_recharged_kwh"],
                        local_charge_mw * dt / 3.6,
                        rel_tol=1e-10, abs_tol=1e-7):
                    raise PhysicsError("Generator and local charger meters disagree")
            except ElectricalError as exc:
                raise PhysicsError(str(exc)) from exc
            # Generator fuel conversion uses the original INV-GEN-CART stock
            # and retains spent housings aboard; no ship mass is erased.
            used = electrical["last"]["generator_cartridge_consumed_kg"]
            available = cartridge_stock.quantity * 1000.0
            if used > available + 1e-7:
                raise PhysicsError("Generator dispatched more than actual cartridges permit")
            cartridge_stock.quantity = max(0.0, available - used) / 1000.0
            cartridge_spent += used
            if not math.isclose(
                    cartridge_stock.quantity * 1000.0 + cartridge_spent,
                    cartridge_baseline, abs_tol=1e-4, rel_tol=1e-11):
                raise PhysicsError("Generator source fuel custody escaped its ledger")
        # Original machine records carry bounded medium-specific output
        # receipts. Empty loops create no positive proof; bearing oil
        # circulates in a finite-pressure sealed skid, with no mass loss.
        if electrical is not None:
            for machine_id in PROCESS_METRICS:
                machine = equipment.get(machine_id)
                if machine is None:
                    raise PhysicsError("Commissioned process feeder lost its original machine")
                prior = machine.details.get(PROCESS_FIELD)
                bearing_driven = bool(
                    machine_id in BEARING_PUMPS and power["assured"]
                    and machine.condition not in _BROKEN
                    and motor_ready(machine_id))
                if not (prior is not None or bearing_driven
                        or media_output_kg[machine_id] > 0):
                    continue
                try:
                    receipt = step_process_output(
                        machine_id, prior, dt_s=dt, now_s=last + duration,
                        delivered_kg=media_output_kg[machine_id],
                        driven=bearing_driven)
                except ProcessOutputError as exc:
                    raise PhysicsError(str(exc)) from exc
                if receipt != prior:
                    details = dict(machine.details)
                    details[PROCESS_FIELD] = receipt
                    machine.details = details
                    machine.revision += 1
                    changed_equipment.add(machine.key)
        summary = {
            "available_mw": round(power["available_mw"], 4),
            "requested_mw": power["requested_mw"],
            "power_assured": powered,
            "protected_power": protected_power,
            "dispatched_mw": round(power["dispatched_mw"], 4),
            "shortfall_mw": round(power["shortfall_mw"], 4),
            "ventilation_powered": air_on,
            "cooling_kw": round(total_cool_kw, 3),
            "cargo_cooling_kw": round(cargo_cooling_kw, 3),
            "cargo_conditioned_drums": (
                len(cargo_climate["last"]["cooled_drums"])
                if cargo_climate is not None else 0),
            "cargo_sensitive_lots_exposed": (
                len(cargo_climate["last"]["exposed_lots"])
                if cargo_climate is not None else 0),
            "active_cargo_environment_pairs": (
                sum(all(f"{drum}-{kind}" in
                        service_operations["last"]["operating"]
                        for kind in ("CARGO-HX", "CARGO-GAS"))
                    for drum in (f"DR-{n:02d}" for n in range(1, 7)))
                if service_operations is not None else 0),
            "crop_growth_kg_this_step": (
                cultivation["last"]["grown_kg"] if cultivation is not None else None),
            "active_cultivation_bays": (
                sum(all(f"GROW-{n}-{kind}" in
                        service_operations["last"]["operating"]
                        for kind in ("CTRL", "NUTRIENT"))
                    for n in (1, 2, 3))
                if service_operations is not None else 0),
            "active_workshop_machines": (
                len(set(service_operations["last"]["operating"])
                    & MANUAL_RESTART)
                if service_operations is not None else 0),
            "secondary_machines_maintenance_due": (
                len(equipment_wear["last"]["maintenance_due"])
                if equipment_wear is not None else 0),
            "secondary_machines_wear_faulted": (
                len(equipment_wear["last"]["faulted"])
                if equipment_wear is not None else 0),
            "refuge_co2_captured_kg": (
                round(refuge_scrubbers["meter"]["captured_kg"]
                      - refuge_captured_before, 6)
                if refuge_scrubbers is not None else 0.0),
            "burning_cells": sum(c["burn"] > 0 for c in cells.values()),
            "open_pressure_hatches": len(open_hatches),
            "active_leaking_cells": sum(
                c["leak"] > 0 and (
                    not leak_isolators.get(zone)
                    or _physical_passage(isolators[leak_isolators[zone]]))
                for zone, c in cells.items()),
        }

    total_after = (sum(c["mass"] + c["fuel"] for c in cells.values())
                   + captured_co2
                   + (refuge_scrubbers["meter"]["captured_kg"]
                      if refuge_scrubbers is not None else 0.0)
                   + retired_refuge_co2)
    if not math.isclose(total_before + oxygen_generated, total_after + lost,
                        abs_tol=1e-5, rel_tol=1e-10):
        raise PhysicsError("Gas, fire fuel and vented mass did not reconcile")
    # Two real airlock chambers, isolated by their installed atmospheric
    # dampers, have a physically finite recovered-gas buffer. The transfer
    # occurs ONLY after the full rated pump cycle, never by simply opening
    # an airlock door. Gas moved to the buffer is not vented or fabricated.
    if eva is not None:
        by_access_eva = {row.source_id: row for row in access_rows}
        carried_time = 0.0
        while carried_time < seconds - 1e-9:
            delta = min(STEP_SECONDS, seconds - carried_time)
            carried_time += delta
            ready_locks = set()
            for lock in EVA_LOCKS:
                spec = lock_contract(lock)
                damper = isolators.get(spec["damper"])
                breaker = isolators.get(spec["breaker"])
                panel = equipment.get(spec["panel"])
                inner = by_access_eva.get(spec["inner"])
                outer = by_access_eva.get(spec["outer"])
                if (damper and breaker and panel and inner and outer
                        and damper.setting == "closed"
                        and breaker.setting == "closed"
                        and damper.condition not in _BROKEN
                        and breaker.condition not in _BROKEN
                        and panel.condition not in _BROKEN
                        and inner.condition not in _BROKEN
                        and outer.condition not in _BROKEN
                        and inner.setting == "closed" and outer.setting == "closed"
                        and power["assured"]
                        and "NODE-LP-" + lock in power["nodes"]):
                    ready_locks.add(lock)
            try:
                eva, events = step_cycles(eva, delta, ready_locks=ready_locks)
                for lock, operation in events:
                    eva, cells = transfer_recovered_gas(
                        eva, cells, lock=lock, cycle=operation)
                eva = step_suit_metabolism(eva, delta)
                ready_links = set()
                for actor_key, job in eva["transits"].items():
                    door = by_access_eva.get(job["link"])
                    if not door or door.condition in _BROKEN or door.setting != "open":
                        continue
                    _, worn = suit_of(eva, actor_key)
                    if not worn:
                        continue
                    crawler_id = lock_contract(worn["home"])["crawler"]
                    crawler = equipment.get(crawler_id)
                    if not crawler or crawler.condition in _BROKEN:
                        continue
                    kind = door.reference.get("kind")
                    if kind == "airlock_outer_hatch":
                        chamber = next((room for room in EVA_LOCKS
                                        if lock_contract(room)["outer"] == job["link"]), None)
                        if (chamber is None
                                or eva["locks"][chamber]["mode"] != "vacuum"
                                or by_access_eva[lock_contract(chamber)["inner"]].setting != "closed"):
                            continue
                    elif kind not in {"eva_rail", "eva_work_platform_transfer"}:
                        continue
                    if kind == "eva_work_platform_transfer":
                        platform = equipment.get("EVA-WORK-PLATFORM")
                        if not platform or platform.condition in _BROKEN:
                            continue
                        if job["to"] == PROPULSION_FACE and not _propulsion_exterior_ready(
                                {**clock.details,
                                 "propulsion_exterior": propulsion_exterior,
                                 "motion": motion},
                                equipment):
                            continue
                        site = EXTERIOR_RADIATOR_FACES.get(job["to"])
                        if site is not None and not _radiator_worksite_ready(
                                {**clock.details,
                                 "exterior_radiators": exterior_radiators,
                                 "motion": motion, "rotors": rotors},
                                site, equipment, isolators):
                            continue
                    ready_links.add(job["link"])
                eva, _ = step_eva_transits(eva, delta, ready_links=ready_links)
            except EVAError as exc:
                raise PhysicsError(str(exc)) from exc

    # The six original radiator faces cool with measured thermal inertia.
    # Each live branch is derived from actual HT valves or the original
    # LT plant and twin rotary manifold isolators; this skin telemetry
    # does not credit a second independent waste-heat sink.
    if exterior_radiators is not None:
        radiator_hot = set()
        for name, spec in EXTERIOR_RADIATORS.items():
            if name.startswith("RAD-HT-"):
                valve = isolators.get(spec["isolation"][0])
                if (valve is not None and valve.condition not in _BROKEN
                        and valve.setting == "open"
                        and equipment.get(name) is not None
                        and equipment[name].condition not in _BROKEN):
                    radiator_hot.add(name)
            else:
                pump = equipment.get("LT-PLANT")
                if (pump is not None and _on(equipment, "LT-PLANT")
                        and all(isolators.get(iso) is not None
                                and isolators[iso].setting == "open"
                                for iso in spec["isolation"])):
                    radiator_hot.add(name)
        try:
            exterior_radiators = step_exterior_skins(
                exterior_radiators, seconds, hot_radiators=radiator_hot)
        except ExteriorRadiatorError as exc:
            raise PhysicsError(str(exc)) from exc

    # Every explicitly enrolled character inhales from their ACTUAL
    # pressure cell. Oxygen becomes equal accounted CO2 mass in that cell;
    # no free gas is created, and cumulative injury is durable per person.
    # EVA's existing suit clock is the sole respiratory source for anyone
    # wearing a real issued suit: do not charge room air or suit oxygen twice.
    crew_used_o2 = 0.0
    crew_exhaled_co2 = 0.0
    crew_incapacitated = 0
    if crew_rows:
        import copy
        from evennia.objects.models import ObjectDB
        ids = [int(row.source_id[1:]) for row in crew_rows
               if re.fullmatch(r"#[0-9]+", row.source_id or "")]
        if len(ids) != len(crew_rows):
            raise PhysicsError("Corrupt live crew health identifier")
        actors = {actor.dbref: actor for actor in ObjectDB.objects.filter(
            id__in=ids)}
        from world.ship_world import find_ship_space
        for row in crew_rows:
            actor = actors.get(row.source_id)
            room = getattr(getattr(getattr(actor, "location", None), "db", None),
                           "ox_space_id", None)
            if (actor is None or find_ship_space(room) !=
                    getattr(actor, "location", None)):
                raise PhysicsError("Registered crew location is not an installed ship space")
            try:
                validate_crew_health(row.details)
            except CrewPhysiologyError as exc:
                raise PhysicsError(str(exc)) from exc
            _, worn = suit_of(eva, row.source_id) if eva is not None else (None, None)
            if worn:
                state_now = copy.deepcopy(worn["exposure"])
            else:
                zone = zones.get(room)
                if zone not in cells and zone != "VACUUM":
                    raise PhysicsError("Unknown life-support envelope at crew position")
                state_now = copy.deepcopy(row.details)
                cell = cells.get(zone)
                time_sampled = 0.0
                while time_sampled < seconds - 1e-9:
                    dt = min(STEP_SECONDS, seconds - time_sampled)
                    try:
                        state_now, cell, breath = step_crew_in_space(
                            state_now, cell, dt)
                    except CrewPhysiologyError as exc:
                        raise PhysicsError(str(exc)) from exc
                    crew_used_o2 += breath["o2_used_kg"]
                    crew_exhaled_co2 += breath["co2_added_kg"]
                    time_sampled += dt
                if zone in cells:
                    cells[zone] = cell
            if getattr(actor.db, "ox_terminal_dead", False):
                state_now["condition"] = "dead"
            if (row.condition != state_now["condition"]
                    or row.details != state_now or row.space_id != room):
                row.condition = state_now["condition"]
                row.details = state_now
                row.space_id = room
                row.revision += 1
                row.save(update_fields=[
                    "condition", "details", "space_id", "revision"])
            if state_now["condition"] in {"incapacitated", "critical", "dead"}:
                crew_incapacitated += 1

    # Actual nutrition and food spoilage run on the same monotonic ship
    # clock and real HAB/store temperatures. The original finite provisions
    # row remains the sole source of stored food and loses exactly spoiled
    # or eaten edible mass; discarded material remains onboard in food-waste
    # custody until a fitted sanitary cassette accepts it.
    if food is not None:
        temperatures = {
            room: cells[zones[room]]["temperature"]
            for room in (*FOOD_STORES, FOOD_GALLEY, FOOD_MESS)
        }
        living = tuple(row.source_id for row in crew_rows
                       if row.condition != "dead")
        elapsed = 0.0
        while elapsed < seconds - 1e-9:
            dt = min(STEP_SECONDS, seconds - elapsed)
            try:
                food = step_food(food, dt, temperatures_k=temperatures,
                                 living_crew=living)
            except FoodError as exc:
                raise PhysicsError(str(exc)) from exc
            elapsed += dt
        remaining = unconsumed_stored_kg(food)
        if abs(food_inventory.quantity * 1000.0 - remaining) > 1e-9:
            food_inventory.quantity = remaining / 1000.0
            food_inventory.revision += 1
            food_inventory.save(update_fields=["quantity", "revision"])
            _event(food_inventory, "g19_spoiled_food_inventory_debit",
                   food_before)
        validate_food(food, inventory_kg=food_inventory.quantity * 1000.0)

    # Clinical work advances only against the same timed, physically present
    # individuals and the original HAB-04 treatment feed/atmospheric cell.
    medical = clock.details.get("medical")
    if medical is not None:
        validate_medical(medical)
        from evennia.objects.models import ObjectDB
        actors = {a.dbref: a for a in ObjectDB.objects.filter(
            id__in=[int(row.source_id[1:]) for row in crew_rows])}
        health = {row.source_id: dict(row.details) for row in crew_rows}
        present = {
            ref for ref, a in actors.items()
            if (getattr(getattr(a, "location", None), "db", None) is not None
                and getattr(a.location.db, "ox_space_id", None) == TREATMENT_ROOM
                and not getattr(a.db, "ox_terminal_dead", False)
                and ref in health)
        }
        observed_present = {
            ref for ref, a in actors.items()
            if (getattr(getattr(a, "location", None), "db", None) is not None
                and getattr(a.location.db, "ox_space_id", None) == OBSERVATION_ROOM
                and not getattr(a.db, "ox_terminal_dead", False)
                and ref in health)
        }
        # A caregiver's physiological state and current medical qualification
        # are independently checked on every tick.
        available = {
            ref for ref in present if health[ref]["condition"] in {"fit", "impaired"}
            and getattr(actors[ref].db, "crew_role", None) in MEDICAL_ROLES}
        for patient, case in medical["cases"].items():
            if case["caregiver"] not in available:
                present.discard(case["caregiver"])
        observed_available = {
            ref for ref in observed_present if health[ref]["condition"] in {
                "fit", "impaired"} and
                getattr(actors[ref].db, "crew_role", None) in MEDICAL_ROLES}
        for patient, course in medical.get("observations", {}).items():
            if (course.get("room", TREATMENT_ROOM) == OBSERVATION_ROOM
                    and course["caregiver"] not in observed_available):
                observed_present.discard(course["caregiver"])
            elif (course.get("room", TREATMENT_ROOM) == TREATMENT_ROOM
                  and course["caregiver"] not in available):
                present.discard(course["caregiver"])
        powered = bool(power["assured"] and
                       TREATMENT_POWER_NODE in power["nodes"] and
                       TREATMENT_FEEDER in isolators and
                       isolators[TREATMENT_FEEDER].setting == "closed" and
                       isolators[TREATMENT_FEEDER].condition not in _BROKEN and
                       equipment[TREATMENT_PANEL].condition not in _BROKEN)
        safe_air = bool(CLINIC_ZONE in cells and
                        _air_safe(state("pressure", CLINIC_ZONE)) and
                        cells[CLINIC_ZONE]["mass"] > 0 and
                        cells[CLINIC_ZONE]["damage"] < .2 and
                        cells[CLINIC_ZONE]["burn"] == 0 and
                        cells[CLINIC_ZONE]["leak"] == 0)
        obs_feeder = isolators.get("ISO-HAB-04-MED-OBS-LP")
        obs_panel = equipment.get("HAB-04-MED-OBS-LP")
        obs_powered = bool(
            obs_feeder is not None and obs_panel is not None
            and obs_feeder.condition not in _BROKEN
            and obs_feeder.setting == "closed"
            and obs_panel.condition not in _BROKEN and power["assured"]
            and "NODE-HAB-04-MED-OBS-LP" in power["nodes"])
        last_completed = ()
        for _medical_dt in range(int(math.ceil(seconds / STEP_SECONDS))):
            dt = min(STEP_SECONDS, seconds - _medical_dt * STEP_SECONDS)
            try:
                medical, health, last_done = step_care(
                    medical, health, dt, occupants=present,
                    equipment_ok=powered, breathable=safe_air,
                    observer_occupants=observed_present,
                    observer_powered=obs_powered,
                    observer_breathable=safe_air)
            except MedicalError as exc:
                raise PhysicsError(str(exc)) from exc
            last_completed += last_done
        for row in crew_rows:
            if (row.source_id in last_completed or
                    row.source_id in medical.get("observations", {}) or
                    row.details != health[row.source_id]):
                row.details = health[row.source_id]
                row.condition = row.details["condition"]
                row.revision += 1
                row.save(update_fields=["details", "condition", "revision"])
                CanonicalShipEvent.objects.create(
                    component_key="crew_health:" + row.source_id,
                    operation="crew_medical_stabilisation_complete",
                    before={"course_seconds": 300},
                    after={"condition": row.condition,
                           "injury": row.details["injury"]},
                    actor_dbref=row.source_id, game_time=last + seconds)

    # Manual casualty transport is not an ordinary self-walking exit. Two
    # registered able carriers physically accompany an immobile patient
    # through a currently rated, open, same-frame interior hatch.
    rescue = clock.details.get("rescue")
    if rescue is not None:
        validate_rescue(rescue)
        from evennia.objects.models import ObjectDB
        from world.ship_world import find_ship_space
        involved = {ref for patient, j in rescue["jobs"].items()
                    for ref in (patient, j["lead"], j["helper"])}
        actor_ids = [int(ref[1:]) for ref in involved]
        actors = {a.dbref: a for a in ObjectDB.objects.filter(id__in=actor_ids)}
        health = {r.source_id: r for r in crew_rows}
        doors = {a.source_id: a for a in access_rows}
        ready = set()
        for patient, job in rescue["jobs"].items():
            trio = (patient, job["lead"], job["helper"])
            if any(ref not in actors or ref not in health for ref in trio):
                continue
            if any(getattr(actors[ref].db, "ox_terminal_dead", False)
                   or getattr(actors[ref], "location", None) !=
                   find_ship_space(job["origin"]) for ref in trio):
                continue
            if any(health[ref].condition not in {"fit", "impaired"}
                   for ref in (job["lead"], job["helper"])):
                continue
            if health[patient].condition not in {
                    "impaired", "incapacitated", "critical"}:
                continue
            if (getattr(actors[job["lead"]].db, "crew_role", None) not in
                    MEDICAL_ROLES | {"chief_engineer", "watch_engineer"}
                    or not getattr(actors[job["helper"]].db, "crew_role", None)):
                continue
            if (eva is not None and any(ref in eva["transits"] for ref in trio)
                    or personnel_transfers is not None and any(
                        j["actor"] in trio
                        for j in personnel_transfers["jobs"].values())):
                continue
            door = doors.get(job["link"])
            if (door is None or door.condition in _BROKEN
                    or door.setting != "open"
                    or door.reference.get("kind") not in INTERIOR_CARRY_KINDS):
                continue
            origin, dest = (
                (door.reference.get("from"), door.reference.get("to"))
                if job["direction"] == "forward" else
                (door.reference.get("to"), door.reference.get("from")))
            if (origin != job["origin"] or dest != job["destination"]):
                continue
            a, b = find_ship_space(origin), find_ship_space(dest)
            if (a is None or b is None or a.db.ox_frame != b.db.ox_frame):
                continue
            zones_at = (zones.get(origin), zones.get(dest))
            if not all(zone in cells and _air_safe(state("pressure", zone))
                       for zone in zones_at):
                continue
            # Freshly integrated gas/thermal state overrides a stale healthy
            # room reading. A burning, leaking, smoked or empty compartment
            # cannot advance the two-carrier movement this tick.
            if any(cells[z]["mass"] <= 0 or cells[z]["burn"] > 0
                   or cells[z]["leak"] > 0 or cells[z]["damage"] >= .2
                   or cells[z]["smoke"] > cells[z]["mass"] * .00001
                   or cells[z]["co2"] > cells[z]["mass"] * .005
                   or not 278.15 <= cells[z]["temperature"] <= 313.15
                   or not 80000 <= (
                       cells[z]["mass"] * R_SPECIFIC_AIR *
                       cells[z]["temperature"] / cells[z]["volume"]) <= 120000
                   for z in zones_at):
                continue
            ready.add(patient)
        try:
            rescue, transfers_done = step_rescue(
                rescue, seconds, ready_patients=ready)
            for patient, job in transfers_done:
                destination = find_ship_space(job["destination"])
                if destination is None:
                    raise PhysicsError("Rescue destination no longer installed")
                for ref in (patient, job["lead"], job["helper"]):
                    if not actors[ref].move_to(destination, quiet=True):
                        raise PhysicsError("Physical casualty carriage movement vetoed")
                    if ref in health:
                        row = health[ref]
                        row.space_id = job["destination"]
                        row.revision += 1
                        row.save(update_fields=["space_id", "revision"])
                rescue = finish_rescue(
                    rescue, patient=patient, request_id=job["request_id"])
                CanonicalShipEvent.objects.create(
                    component_key="access:" + job["link"],
                    operation="crew_casualty_transport_complete",
                    before={"room": job["origin"], "patient": patient},
                    after={"room": job["destination"],
                           "carriers": [job["lead"], job["helper"]],
                           "seconds": job["total_s"],
                           "request_id": job["request_id"]},
                    actor_dbref=job["lead"], game_time=last + seconds)
        except RescueError as exc:
            raise PhysicsError(str(exc)) from exc

    # Both original F1/F2 pressure-rated service airlocks are enclosed
    # transfer mechanisms. Their two seals remain mechanically closed in
    # the normal access ledger while an issued-suit worker spends 180 s
    # in the captured service cycle. No air is assigned to unknown bays.
    bay_access = clock.details.get("bay_access")
    if bay_access is not None:
        validate_bay_access(bay_access)
        from evennia.objects.models import ObjectDB
        from world.ship_world import find_ship_space
        ids = [int(ref[1:]) for ref in bay_access["jobs"]]
        workers = {a.dbref: a for a in ObjectDB.objects.filter(id__in=ids)}
        bay_doors = {a.source_id: a for a in access_rows}
        ready = set()
        for ref, job in bay_access["jobs"].items():
            link = job["link"]
            corridor, bay, panel_id = BAY_SERVICE_LOCKS[link]
            door = bay_doors.get(link)
            actor = workers.get(ref)
            panel = equipment.get(panel_id)
            _, suit = suit_of(eva, ref) if eva is not None else (None, None)
            trunk_zone = zones.get(corridor)
            gas = cells.get(trunk_zone)
            if (actor is None or find_ship_space(job["from"]) !=
                    getattr(actor, "location", None)
                    or getattr(actor.db, "ox_terminal_dead", False)
                    or door is None or door.condition in _BROKEN
                    or door.setting != "closed"
                    or panel is None or panel.condition in _BROKEN
                    or panel.space_id != bay
                    or bay not in bay_access["surveyed_bays"]
                    or trunk_zone != "PZ-TRUNK-A-" + bay[:2] or gas is None
                    or not _air_safe(state("pressure", trunk_zone))
                    or gas["mass"] <= 0 or gas["burn"] > 0
                    or gas["leak"] > 0 or gas["damage"] >= .2
                    or gas["smoke"] > gas["mass"] * .00001
                    or not 80000 <= gas["mass"] * R_SPECIFIC_AIR *
                         gas["temperature"] / gas["volume"] <= 120000
                    or suit is None or suit["integrity"] < .8
                    or suit["exposure"]["condition"] in {
                        "incapacitated", "critical", "dead"}
                    or suit["exposure"]["suit_oxygen_kg"] <= 0):
                continue
            ready.add(link)
        try:
            bay_access, completed_bay = step_bay_transits(
                bay_access, seconds, ready_links=ready)
            for ref, job in completed_bay:
                destination = find_ship_space(job["to"])
                if destination is None or not workers[ref].move_to(
                        destination, quiet=True):
                    raise PhysicsError("Physical airlock occupant cannot be delivered")
                for row in crew_rows:
                    if row.source_id == ref:
                        row.space_id = job["to"]
                        row.revision += 1
                        row.save(update_fields=["space_id", "revision"])
                        break
                bay_access = finish_bay_transit(
                    bay_access, actor=ref, request_id=job["request_id"])
                CanonicalShipEvent.objects.create(
                    component_key="access:" + job["link"],
                    operation="crew_flywheel_service_transfer_complete",
                    before={"room": job["from"], "actor": ref},
                    after={"room": job["to"],
                           "cycle_seconds": BAY_SERVICE_CYCLE_S,
                           "request_id": job["request_id"]},
                    actor_dbref=ref, game_time=last + seconds)
        except BayAccessError as exc:
            raise PhysicsError(str(exc)) from exc
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
    if cartridge_stock is not None and not math.isclose(
            cartridge_stock.quantity, cartridge_before["quantity"],
            abs_tol=1e-13, rel_tol=0):
        cartridge_stock.revision += 1
        cartridge_stock.save(update_fields=["quantity", "revision"])
        _event(cartridge_stock, "g19_generator_cartridge_conversion",
               cartridge_before)
    for key, stock in water_stocks.items():
        before_stock = water_stock_before[key]
        if not math.isclose(stock.quantity, before_stock["quantity"],
                            abs_tol=1e-13, rel_tol=0.0):
            stock.revision += 1
            stock.save(update_fields=["quantity", "revision"])
            _event(stock, "water_or_waste_mass_transfer", before_stock)

    # Maintenance progresses only with qualified workers still physically
    # on site, and equipment still provably isolated and environmentally safe.
    # A recorded fault cannot be repaired by simply toggling a status flag.
    if major_damage is not None and major_damage["sites"]:
        from evennia.objects.models import ObjectDB
        by_access_major = {door.source_id: door for door in access_rows}
        ready_zones = set()
        for zone, work in major_damage["sites"].items():
            fitted = [by_access_major.get(k) for k in work["boundaries"]]
            doors_sound = all(
                door is not None and door.condition not in _BROKEN
                and door.reference.get("pressure_boundary") is True
                for door in fitted)
            closed = doors_sound and all(
                door.setting == "closed" for door in fitted)
            if work["isolated"]:
                if not closed:
                    major_damage = revoke_containment(major_damage, zone=zone)
                    CanonicalShipEvent.objects.create(
                        component_key="pressure:" + zone,
                        operation="major_hull_containment_lost",
                        before={"isolated": True},
                        after={"isolated": False, "reason": "rated_pressure_door_changed"},
                        game_time=last + seconds)
                continue
            if work["remaining_s"] <= 0 or not doors_sound:
                continue
            ref = work["operator"]
            operator = (ObjectDB.objects.filter(id=int(ref[1:])).first()
                        if ref and ref[1:].isdigit() else None)
            if (operator is None or getattr(operator, "location", None) is None
                    or getattr(operator.location.db, "ox_space_id", None) != "ENG-CONTROL"
                    or getattr(operator.db, "ox_terminal_dead", False)
                    or getattr(operator.db, "crew_role", None) not in AUTHORISED_ROLES):
                continue
            panel = equipment.get("LP-ENG-CONTROL")
            if (panel is None or panel.condition in _BROKEN
                    or not power["assured"]
                    or "NODE-LP-ENG-CONTROL" not in power["nodes"]):
                continue
            # A live cargo/manpower interface must finish before its door can
            # be closed: no traveller is silently ejected into the bulkhead.
            if any(j["link"] in work["boundaries"] for j in
                   (personnel_transfers or {"jobs": {}})["jobs"].values()):
                continue
            if any(j.get("portal_id", "")[:5] in zone for j in
                   (water_state or {}).get("waste_offload", {}).get("jobs", {}).values()):
                continue
            ready_zones.add(zone)
        try:
            major_damage, completed_seals = step_containments(
                major_damage, seconds, ready_zones=ready_zones)
        except MajorDamageError as exc:
            raise PhysicsError(str(exc)) from exc
        for zone in completed_seals:
            for identifier in major_damage["sites"][zone]["boundaries"]:
                door = by_access_major[identifier]
                prior = _snapshot(door)
                if door.setting != "closed":
                    door.setting = "closed"
                    door.revision += 1
                    door.save(update_fields=["setting", "revision"])
                    _event(door, "major_hull_bulkhead_sealed", prior)
            CanonicalShipEvent.objects.create(
                component_key="pressure:" + zone,
                operation="major_hull_containment_complete",
                before={"isolated": False},
                after={"isolated": True,
                       "rated_boundaries": major_damage["sites"][zone]["boundaries"],
                       "seconds": 120.0},
                game_time=last + seconds)
    if original_rundown_electrical is not None:
        try:
            flywheel_service, rundown_completed, rundown_output_kwh = (
                advance_rundowns(
                    flywheel_service,
                    before_electrical=original_rundown_electrical,
                    after_electrical=electrical))
        except FlywheelServiceError as exc:
            raise PhysicsError(str(exc)) from exc
        for name in rundown_completed:
            electrical["flywheels"][name]["mode"] = "standby"
            CanonicalShipEvent.objects.create(
                component_key="equipment:" + name,
                operation="g19_flywheel_metered_rundown_complete",
                before={"measured_charge_kwh": original_rundown_electrical[
                    "flywheels"][name]["charge_kwh"]},
                after={"measured_charge_kwh": electrical["flywheels"][
                    name]["charge_kwh"],
                       "delivered_kwh": original_rundown_electrical[
                           "flywheels"][name]["charge_kwh"]},
                game_time=last + seconds)
    if repairs is not None and repairs["jobs"]:
        from evennia.objects.models import ObjectDB
        refs = {ref for job in repairs["jobs"].values()
                for ref in job["workers"]}
        ids = [int(ref[1:]) for ref in refs if isinstance(ref, str)
               and ref.startswith("#") and ref[1:].isdigit()]
        by_id = {obj.dbref: obj for obj in ObjectDB.objects.filter(id__in=ids)}
        crew_health = {
            row.key.split(":", 1)[1]: row.condition
            for row in CanonicalShipState.objects.filter(
                key__in=["crew_health:" + ref for ref in refs])
        }
        present = defaultdict(set)
        by_pressure = {row.source_id: row for row in pressure_rows}
        for ref, actor in by_id.items():
            if (getattr(actor, "location", None) is not None
                    and getattr(actor.db, "crew_role", None) in AUTHORISED_ROLES
                    and not getattr(actor.db, "ox_terminal_dead", False)
                    and crew_health.get(ref) not in {
                        "incapacitated", "critical", "dead"}):
                room_id = getattr(actor.location.db, "ox_space_id", None)
                if room_id:
                    zone = zones.get(room_id)
                    if zone not in by_pressure:
                        _, worn = suit_of(eva, ref) if eva is not None else (None, None)
                        at_major_face = any(
                            v["external_face"] == room_id
                            for v in (major_damage or {"sites": {}})["sites"].values())
                        fitted_eva = bool(
                            at_major_face and worn is not None
                            and worn["integrity"] >= .8
                            and worn["exposure"]["suit_oxygen_kg"] > 0
                            and worn["exposure"]["condition"] not in {
                                "incapacitated", "critical", "dead"})
                        if room_id in {"F1-BAY", "F2-BAY"}:
                            real_suit = _flywheel_suit_ready(
                                actor, room_id, {
                                    **clock.details, "eva": eva,
                                    "electrical": electrical,
                                    "bay_access": bay_access})
                            if not (real_suit and
                                    repairs["site_surveys"].get(room_id) == "suited_service"):
                                continue
                        elif room_id in EXTERIOR_RADIATOR_FACES:
                            if not _radiator_suit_ready(
                                    actor, room_id, {
                                        **clock.details, "eva": eva,
                                        "exterior_radiators": exterior_radiators}):
                                continue
                        elif not fitted_eva and not (
                                repairs["site_surveys"].get(room_id) == "suited_service"
                                and getattr(actor.db, "ox_suit_verified", False)):
                            continue
                    present[room_id].add(ref)
        by_isolator = {x.source_id: x for x in isolators.values()}
        by_access = {x.source_id: x for x in access_rows}
        safe = set()
        for key, job in repairs["jobs"].items():
            category, identifier = key.split(":", 1)
            if category == "hull":
                breach = (hull or {}).get("breaches", {}).get(identifier)
                cell = by_pressure.get(identifier)
                major_site = (major_damage or {"sites": {}})["sites"].get(identifier)
                if major_site is not None:
                    boundaries_closed = {
                        id for id in major_site["boundaries"]
                        if id in by_access and
                        by_access[id].condition not in _BROKEN and
                        by_access[id].setting == "closed"
                    }
                    safe_repair = external_repair_ready(
                        major_damage, zone=identifier, room=job["room"],
                        suit_valid=any(
                            ref in present.get(job["room"], set())
                            for ref in job["workers"]),
                        actual_closed_boundaries=boundaries_closed)
                else:
                    safe_repair = bool(
                        breach and breach["site_room"] == job["room"]
                        and zones.get(job["room"]) == identifier
                        and _hull_repair_air_safe(cell))
                if (breach and cell
                        and expected_repair_condition(hull, identifier) == job["condition"]
                        and safe_repair):
                    safe.add(key)
                continue
            row = (equipment.get(identifier) if category == "equipment" else
                   by_isolator.get(identifier) if category == "isolator" else
                   by_access.get(identifier))
            valid_site = row is not None and (
                row.space_id == job["room"] or
                category == "equipment" and
                EXTERIOR_RADIATOR_FACES.get(job["room"]) == identifier or
                category == "access" and job["room"] in {
                    row.reference.get("from"), row.reference.get("to")})
            if (valid_site and category == "equipment"
                    and identifier in FREIGHT_SERVICE_WORKSITES
                    and not _freight_service_entry_ready(
                        FREIGHT_SERVICE_WORKSITES[identifier][1],
                        clock_details={
                            **_clock().details, "rotors": rotors,
                            "cargo": cargo, "water": water_state,
                            "motion": motion,
                        })):
                valid_site = False
            if (valid_site and row is not None
                    and category == "equipment"
                    and (identifier in WORKSHOP_DRIVES
                         and not machine_safely_stopped(identifier, row.details)
                         or identifier in BEARING_PUMPS
                         and not machine_depressurized(identifier, row.details))):
                # The original disconnected spindle can still coast and a
                # hydraulic press can retain pressure. No timed hands-on
                # work occurs until its actual local gauge reads zero.
                continue
            if (valid_site and row.condition == job["condition"] and
                    safe_repair_target(
                        row, pressure_rows=by_pressure, zones=zones,
                        rotors=rotors, motion=motion, water=water_state,
                        cargo=cargo, equipment=equipment,
                        isolators=isolators, workroom=job["room"],
                        surveyed_suit_work=(
                            repairs["site_surveys"].get(job["room"]) ==
                            "suited_service"
                            or job["room"] in EXTERIOR_RADIATOR_FACES),
                        flywheel_service=flywheel_service,
                        electrical=electrical,
                        exterior_radiators=exterior_radiators)):
                # A staged component may not progress while any of its
                # individually fitted feeds has been restored, bypassed or
                # damaged. Legacy repairs without a signed case retain the
                # existing specialist safe_repair_target interlocks.
                if category == "equipment" and fault_cases is not None:
                    case = fault_cases["cases"].get(identifier)
                    if case is not None and (
                            case["stage"] != "repairing" or not
                            verified_open_feeders(identifier, {
                                feeder: isolators.get(feeder)
                                for feeder in case["feeders"]})):
                        continue
                safe.add(key)
        try:
            repairs, repair_completed = step_repairs(
                repairs, seconds, present_workers=present,
                safe_targets=safe)
        except WaterError as exc:
            raise PhysicsError(str(exc)) from exc
        for key, original, installed_spares in repair_completed:
            category, identifier = key.split(":", 1)
            if category == "hull":
                if hull is None or identifier not in by_pressure:
                    raise PhysicsError("Hull repair lost its installed pressure cell")
                try:
                    hull, new_leak = finish_hull_work(
                        hull, zone=identifier, condition=original,
                        installed_kg=installed_spares)
                except HullError as exc:
                    raise PhysicsError(str(exc)) from exc
                cell = by_pressure[identifier]
                previous = _snapshot(cell)
                d = dict(cell.details)
                d["physics_leak_kg_s"] = new_leak
                d["hull_installed_spares_kg"] = hull["breaches"][identifier]["installed_spares_kg"]
                d["hull_repair_game_time"] = last + seconds
                cell.details = d
                cell.revision += 1
                cell.save(update_fields=["details", "revision"])
                cells[identifier]["leak"] = new_leak
                _event(cell, "crew_hull_restoration_complete", previous)
                continue
            item = (equipment[identifier] if category == "equipment" else
                    by_isolator[identifier] if category == "isolator" else
                    by_access[identifier])
            if item.condition != original:
                raise PhysicsError("Underlying machine condition changed before repair")
            prior = _snapshot(item)
            info = dict(item.details)
            info["repair_cumulative_kg"] = (
                info.get("repair_cumulative_kg", 0.0) + installed_spares)
            info["repair_completed_game_time"] = last + seconds
            # A real replacement does not restart pumps/generators by magic.
            if item.source_id in PLANTS:
                info["physics_online"] = False
                info["physics_commanded_on"] = False
                info["physics_startup_s"] = 0.0
            item.details = info
            item.condition = "serviceable"
            item.revision += 1
            item.save(update_fields=["details", "condition", "revision"])
            if category == "equipment" and identifier in set(MOTORS) | set(SERVICE_LOADS):
                cases = fault_cases or initial_fault_cases()
                if cases["cases"].get(identifier, {}).get("stage") == "repairing":
                    fault_cases = finished_verified_work(
                        cases, identifier, stamp=last + seconds,
                        installed_kg=installed_spares)
            _event(item, "crew_finite_equipment_repair_complete", prior)
    # The eight indexed personnel carriers share the same physical world
    # clock and pressure state. Doors stay shut while a carriage moves.
    # A failed actuator, lost power, unsafe air, or lost hardlock PAUSES work;
    # no inhabitant is teleported to a drum on a failed cycle.
    if eva is not None and eva["transits"]:
        from evennia.objects.models import ObjectDB
        from world.ship_world import find_ship_space
        for actor_key, transit in tuple(eva["transits"].items()):
            if transit["remaining_s"] > 1e-8:
                continue
            traveler = ObjectDB.objects.filter(id=int(actor_key[1:])).first()
            origin = find_ship_space(transit["from"])
            destination = find_ship_space(transit["to"])
            _, worn = suit_of(eva, actor_key)
            if (not traveler or not origin or not destination
                    or traveler.location != origin):
                eva = finish_eva_transit(
                    eva, actor=actor_key,
                    request_id=transit["request_id"], aborted=True)
                CanonicalShipEvent.objects.create(
                    component_key="access:" + transit["link"],
                    operation="crew_eva_transit_aborted",
                    before={"space_id": transit["from"]},
                    after={"reason": "occupant_or_room_changed",
                           "request_id": transit["request_id"]},
                    actor_dbref=actor_key, game_time=last + seconds)
                continue
            if (not worn or worn["integrity"] < 0.8
                    or worn["exposure"]["condition"] in {
                        "incapacitated", "critical", "dead"}):
                continue
            if transit["to"] == PROPULSION_FACE and not _propulsion_exterior_ready(
                    {**clock.details,
                     "propulsion_exterior": propulsion_exterior,
                     "motion": motion}, equipment):
                continue
            radiator_destination = EXTERIOR_RADIATOR_FACES.get(transit["to"])
            if radiator_destination is not None and not _radiator_worksite_ready(
                    {**clock.details, "exterior_radiators": exterior_radiators,
                     "motion": motion, "rotors": rotors},
                    radiator_destination, equipment, isolators):
                continue
            if not traveler.move_to(destination, quiet=True):
                continue
            eva = finish_eva_transit(
                eva, actor=actor_key, request_id=transit["request_id"])
            CanonicalShipEvent.objects.create(
                component_key="access:" + transit["link"],
                operation="crew_eva_transit_complete",
                before={"space_id": transit["from"]},
                after={"space_id": transit["to"], "request_id": transit["request_id"],
                       "travel_seconds": transit["total_s"]},
                actor_dbref=actor_key, game_time=last + seconds)
            traveler.msg("Your suited exterior transfer has reached its worksite.")
    if personnel_transfers is not None and personnel_transfers["jobs"]:
        from evennia.objects.models import ObjectDB
        from world.ship_world import find_ship_space
        by_access = {item.source_id: item for item in access_rows}
        by_pressure = {item.source_id: item for item in pressure_rows}
        ready_links = set()
        for job in personnel_transfers["jobs"].values():
            rotor_name = job["rotor"]
            if indexed_mechanism_ready(
                    job["link"], rotors=rotors, equipment=equipment,
                    access=by_access, pressure=by_pressure, room_zones=zones,
                    pressure_safe=_air_safe,
                    powered=(power["assured"] and
                             rotary_power_by_unit.get(rotor_name, False)
                             and (rotor_name not in DRUMS or
                                  motor_ready(rotor_name + "-PERSONNEL-INDEXER"))),
                    hab_sync=hab_sync):
                ready_links.add(job["link"])
        try:
            personnel_transfers, completed_candidates = step_personnel_transfers(
                personnel_transfers, seconds, ready_links=ready_links)
        except IndexedTransferError as exc:
            raise PhysicsError(str(exc)) from exc
        for job in completed_candidates:
            source = find_ship_space(job["from"])
            destination = find_ship_space(job["to"])
            ref = job["actor"]
            actor = ObjectDB.objects.filter(id=int(ref[1:])).first()
            if (actor is None or source is None or destination is None
                    or actor.location != source):
                # A character removed/repositioned by world authority cannot
                # be pulled back by a stale work order. Cancel and audit it.
                personnel_transfers = finish_personnel_transfer(
                    personnel_transfers, rotor=job["rotor"],
                    request_id=job["request_id"], aborted=True)
                CanonicalShipEvent.objects.create(
                    component_key="access:" + job["link"],
                    operation="crew_indexed_transfer_aborted",
                    before={"space_id": job["from"]},
                    after={"reason": "occupant_or_room_changed",
                           "request_id": job["request_id"]},
                    actor_dbref=ref, game_time=last + seconds)
                continue
            health = CanonicalShipState.objects.filter(
                pk="crew_health:" + ref).first()
            if (getattr(actor.db, "ox_terminal_dead", False)
                    or (health and health.condition in {
                        "incapacitated", "critical", "dead"})):
                continue  # an incapacitated occupant needs recovery, not teleport
            if not actor.move_to(destination, quiet=True):
                continue
            personnel_transfers = finish_personnel_transfer(
                personnel_transfers, rotor=job["rotor"],
                request_id=job["request_id"])
            CanonicalShipEvent.objects.create(
                component_key="access:" + job["link"],
                operation="crew_indexed_transfer_complete",
                before={"space_id": job["from"]},
                after={"space_id": job["to"], "request_id": job["request_id"],
                       "duration_s": job["total_s"]},
                actor_dbref=ref, game_time=last + seconds)
            actor.msg("The indexed personnel carriage reaches its destination.")
    old = _snapshot(clock)
    d = dict(clock.details)
    if fault_cases is not None:
        validate_fault_cases(fault_cases)
        d["fault_cases"] = fault_cases
    d["last_game_time"] = last + seconds
    d["ticks"] += 1
    d["lost_to_space_kg"] += lost
    d["burned_fuel_kg"] += burned
    d["water_suppression_kg"] += water
    d["co2_captured_kg"] = captured_co2
    d["motion"] = motion
    if instrumentation is not None:
        # Use physical end-of-tick cell/machine/breaker status. The chosen
        # source is an actual installed panel and its current power node,
        # not a global operator view of uninstalled future sensors.
        try:
            panel_evidence = observed_panel_evidence(
                instrumentation, cells=cells, equipment=equipment,
                isolators=isolators, nodes_energised=set(power["nodes"]),
                electrical=electrical, water=water_state,
                cultivation=cultivation, food=food,
                services=service_operations, motion=motion,
                fire_loops=(
                    "FIRE-DETECT-FWD", "FIRE-DETECT-CARGO-FWD",
                    "FIRE-DETECT-FLY-FWD", "FIRE-DETECT-CENTRAL",
                    "FIRE-DETECT-WR", "FIRE-DETECT-FLY-AFT",
                    "FIRE-DETECT-CARGO-AFT", "FIRE-DETECT-AFT",
                ))
            instrumentation = sample_instrumentation(
                instrumentation, last + seconds, panel_evidence)
            validate_instrumentation(instrumentation)
        except InstrumentError as exc:
            raise PhysicsError(str(exc)) from exc
        d["instrumentation"] = instrumentation
    if fault_cases is not None:
        # A verified restart is not two elapsed global ticks. The actual
        # installed machine must run with its correctly restored source and
        # a fresh GOOD local panel sample on each consecutive physics tick.
        # No remote panel can provide evidence for a different room.
        pending = {name: case for name, case in fault_cases["cases"].items()
                   if case["stage"] == "authorized"}
        if pending:
            observations = {}
            for name, case in sorted(pending.items()):
                machine = equipment.get(name)
                panel_id = (next((key for key, row in instrumentation["panels"].items()
                                  if row["room"] == case["room"]), None)
                            if instrumentation is not None else None)
                panel = (instrumentation["panels"][panel_id]
                         if panel_id is not None else None)
                recent = bool(panel and panel["status"] == "online"
                              and panel["last_good_s"] == last + seconds)
                known_alarm = bool(instrumentation and any(
                    row["active"] and row["panel"] == panel_id
                    and (row["subject"] == name
                         or row["subject"] in case["feeders"]
                         or row["code"] in {
                             "INSTRUMENT_LOST", "INSTRUMENT_UNRELIABLE"})
                    for row in instrumentation["alarms"].values()))
                physically_restored = bool(
                    recent and verified_restored_feeders(
                        name, {key: isolators.get(key)
                               for key in case["feeders"]},
                        checked_s=case["checked_s"],
                        last_good_s=panel["last_good_s"]))
                has_real_supply = bool(
                    machine is not None and (
                        fire_pump_service_ready(
                            name, nodes=power["nodes"], equipment=equipment,
                            edges=aux_edges, switches=isolators,
                            normal_assured=power["assured"],
                            protected_assured=power["protected_assured"])
                        if name in PROTECTED_FIRE_MOTORS else
                        power["assured"] and (
                            service_power(name, nodes=power["nodes"],
                                equipment=equipment, edges=aux_edges,
                                switches=isolators)
                            if name in SERVICE_LOADS else
                            motor_power(name, nodes=power["nodes"],
                                equipment=equipment, edges=aux_edges,
                                switches=isolators))))
                observations[name] = bool(
                    machine and machine.space_id == case["room"]
                    and machine.condition == "serviceable"
                    and (name in WATER_MACHINES + BEARING_PUMPS
                         or (machine.details.get("physics_commanded_on") is True
                             and machine.details.get("physics_online") is True
                             and machine.details.get("physics_startup_s", 0) == 0))
                    and not machine.details.get("physics_trip_reason")
                    and (name not in PROCESS_METRICS or
                         proves_process_output(
                             name, machine.details, observed_s=last + seconds))
                    and (name not in WORKSHOP_DRIVES or
                         machine_output_confirmed(
                             name, machine.details,
                             observed_s=last + seconds,
                             operating=bool(service_operations and
                               name in service_operations["last"]["operating"])))
                    and physically_restored and has_real_supply
                    and not known_alarm
                    and not (repairs and "equipment:" + name in repairs["jobs"]))
            fault_cases = advance_restart_evidence(
                fault_cases, now_s=last + seconds,
                observed_good=observations)
            d["fault_cases"] = fault_cases
    if local_backup is not None:
        d["local_backup"] = local_backup
    if refuge_scrubbers is not None:
        d["refuge_scrubbers"] = refuge_scrubbers
    if refuge_media is not None:
        d["refuge_media_service"] = refuge_media
    if service_operations is not None:
        d["service_operations"] = service_operations
    if cultivation is not None:
        validate_cultivation(cultivation)
        d["cultivation"] = cultivation
    if food is not None:
        validate_food(food, inventory_kg=food_inventory.quantity * 1000.0)
        d["food"] = food
    if cargo_climate is not None:
        validate_cargo_environment(cargo_climate, cargo)
        d["cargo_environment"] = cargo_climate
    if equipment_wear is not None:
        d["equipment_wear"] = equipment_wear
    if electrical is not None:
        d["electrical"] = electrical
        d["generator_spent_cartridge_kg"] = cartridge_spent
    if repairs is not None:
        d["repairs"] = repairs
    if fabrication is not None:
        validate_fabrication(fabrication)
        d["fabrication"] = fabrication
    if welding is not None:
        validate_welding(welding)
        d["welding"] = welding
    if hull is not None:
        d["hull"] = hull
    if personnel_transfers is not None:
        d["personnel_transfers"] = personnel_transfers
    if hab_sync is not None:
        d["hab_sync"] = hab_sync
    if eva is not None:
        d["eva"] = eva
    if medical is not None:
        d["medical"] = medical
    if rescue is not None:
        d["rescue"] = rescue
    if flywheel_service is not None:
        d["flywheel_service"] = flywheel_service
    if exterior_radiators is not None:
        d["exterior_radiators"] = exterior_radiators
    if propulsion_exterior is not None:
        d["propulsion_exterior"] = propulsion_exterior
    if bay_access is not None:
        d["bay_access"] = bay_access
    if major_damage is not None:
        d["major_damage"] = major_damage
    if water_state is not None:
        d["water"] = water_state
    d["rotors"] = rotors
    validate_cargo(cargo, motion["cargo_mass_kg"])
    d["cargo"] = cargo
    d["summary"] = {
        **summary,
        "electrical": ({
            "last": electrical["last"],
            "meter": electrical["meter"],
            "flywheel_modules": len(electrical["flywheels"]),
            "flywheel_held_kwh": sum(
                x["charge_kwh"] for x in electrical["flywheels"].values()),
            "generator_cartridges_remaining_kg": (
                cartridge_stock.quantity * 1000.0),
            "spent_cartridge_housings_kg": cartridge_spent,
            "tripped_breakers": sorted(
                key for key, fault in electrical["faults"].items()
                if fault["latched"]),
        } if electrical is not None else None),
        "flywheel_locked_modules": (len(flywheel_service["permits"])
                                    if flywheel_service is not None else None),
        "radiator_exterior_work_permits": (
            len(exterior_radiators["permits"])
            if exterior_radiators is not None else None),
        "aft_nozzle_permit_active": (
            propulsion_exterior["permit"] is not None
            if propulsion_exterior is not None else None),
        "aft_nozzle_inspections": (
            propulsion_exterior["inspected"]
            if propulsion_exterior is not None else None),
        "flywheel_active_rundowns": (len(flywheel_service["rundowns"])
                                      if flywheel_service is not None else None),
        "flywheel_rundown_delivered_kwh": (
            flywheel_service["rundown_delivered_kwh"]
            if flywheel_service is not None else None),
        "bay_access_active_cycles": (len(bay_access["jobs"]) if bay_access is not None else None),
        "bay_access_completed": (bay_access["completed"] if bay_access is not None else None),
        "rescue_active_transfers": (len(rescue["jobs"]) if rescue is not None else None),
        "rescue_completed": (rescue["completed"] if rescue is not None else None),
        "medical_active_cases": (len(medical["cases"]) if medical is not None else None),
        "medical_completed": (medical["completed"] if medical is not None else None),
        "crew_exposure_registered": len(crew_rows),
        "crew_incapacitated_or_worse": crew_incapacitated,
        "crew_o2_used_this_tick_kg": round(crew_used_o2, 7),
        "crew_co2_added_this_tick_kg": round(crew_exhaled_co2, 7),
        "gas_kg": round(sum(c["mass"] for c in cells.values()), 6),
        "oxygen_kg": round(sum(c["oxygen"] for c in cells.values()), 6),
        "smoke_kg": round(sum(c["smoke"] for c in cells.values()), 6),
        "fuel_kg": round(sum(c["fuel"] for c in cells.values()), 6),
        "damaged_cells": sum(c["damage"] >= 0.2 for c in cells.values()),
        "processed_seconds": seconds,
        "ship_position_m": [round(x, 3) for x in motion["position_m"]],
        "ship_velocity_m_s": [round(x, 6) for x in motion["velocity_m_s"]],
        "ship_propellant_kg": round(motion["propellant_kg"], 3),
        "ship_ftl_fuel_kg": round(motion["ftl_fuel_kg"], 3),
        "ftl_leg_status": (motion.get("ftl_leg") or {}).get("status"),
        "ship_current_mass_kg": round(sum(motion[k] for k in
            ("dry_mass_kg", "cargo_mass_kg", "ftl_fuel_kg",
             "mission_fluids_kg", "propellant_kg")), 3),
        "ship_cargo_mass_kg": round(motion["cargo_mass_kg"], 3),
        "cargo_unlocated_kg": round(cargo["unlocated_onboard_kg"], 3),
        "freight_jobs": len(cargo["jobs"]),
        "commercial_port_jobs": len(cargo.get("port_jobs", {})),
        "commercial_ports_docked": len(cargo.get("port_contacts", {})),
        "cargo_offship_kg": round(cargo["delivered_offship_kg"], 3),
        "food_stored_kg": (
            round(unconsumed_stored_kg(food), 5) if food is not None else None),
        "food_meals_prepared": (
            food["meter"]["meals_prepared"] if food is not None else None),
        "food_meals_consumed": (
            food["meter"]["meals_consumed"] if food is not None else None),
        "food_waste_held_kg": (
            round(sum(food["waste"].values()) +
                  sum(x["waste_kg"] for x in food["carried"].values()), 4)
            if food is not None else None),
        "nutrition_impaired": (
            len(food["last"]["impaired"]) if food is not None else None),
        "nutrition_incapacitated": (
            len(food["last"]["incapacitated"]) if food is not None else None),
        "instrument_panels_online": (
            sum(p["status"] == "online" for p in
                instrumentation["panels"].values())
            if instrumentation is not None else None),
        "instrument_active_alarms": (
            sum(a["active"] for a in instrumentation["alarms"].values())
            if instrumentation is not None else None),
        "instrument_samples": (
            instrumentation["sample_count"] if instrumentation is not None else None),
        "crop_staged_kg": (
            round(sum(b["staged_kg"] for b in cultivation["beds"].values()), 4)
            if cultivation is not None else None),
        "crop_standing_kg": (
            round(sum(b["standing_kg"] for b in cultivation["beds"].values()), 4)
            if cultivation is not None else None),
        "waste_exported_this_tick_kg": round(waste_export_kg, 4),
        "waste_exported_total_kg": (dict(water_state["waste_offload"]["delivered_kg"])
                                    if water_state is not None else None),
        "repair_work_orders": (len(repairs["jobs"]) if repairs is not None else None),
        "repairs_completed": (repairs["completed"] if repairs is not None else None),
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
        "water": ({
            "working_kg": round(water_state["working_kg"], 4),
            "makeup_kg": round(water_stocks["normal"].quantity * 1000, 4),
            "protected_kg": round(water_stocks["reserve"].quantity * 1000, 4),
            "fixed_kg": water_state["fixed"],
            "local_kg": water_state["local"],
            "cumulative": water_state["cumulative"],
            "potable_quarantined": water_state["potable_quarantined"],
            "port_jobs": water_state["waste_offload"]["jobs"],
            "port_delivered_kg": water_state["waste_offload"]["delivered_kg"],
            "last_step": water_tick_report,
        } if water_state is not None else None),
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


def _hull_repair_air_safe(cell):
    """Allow hand sealing only a *small* leak in otherwise verified safe air.

    General hatch opening and ordinary machine repair still reject ANY active
    leak. A hull patcher can approach a surveyed inner repair face only while
    the unvalved release is <=50 g/s and actual pressure, oxygen, smoke,
    temperature and fire are safe. Larger losses need separate suited access.
    """
    d = cell.details
    rate = d.get("physics_leak_kg_s")
    if (not isinstance(rate, (int, float)) or isinstance(rate, bool)
            or not math.isfinite(rate) or not 0 < rate <= 0.05
            or d.get("physics_leak_isolator_id")):
        return False
    from types import SimpleNamespace
    screened = SimpleNamespace(
        quantity=cell.quantity, details={**d, "physics_leak_kg_s": 0.0})
    return _air_safe(screened)


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


# Door families with a true local crew-operable latch. Personnel carriers,
# cargo port shutters, freight gates, vacuum airlocks and EVA mechanisms have
# separate controls and are never unlocked through this ordinary-door path.
CREW_LOCAL_DOOR_KINDS = frozenset({
    "pressure_door", "service_door", "door", "cargo_service_door",
    "service_panel", "cabin_door", "pressure_hatch", "service_hatch",
    "store_door", "fire_door",
})


def _freight_service_site_safe(gate, *, clock_details=None):
    """Verified pressure, idle machinery and sealed capture for an access bay."""
    if gate not in FREIGHT_SERVICE_GATES:
        return False
    control, site, kind, boundary, rotor = FREIGHT_SERVICE_GATES[gate]
    door = state("access", gate)
    if (door.condition in _BROKEN
            or (door.reference.get("from"), door.reference.get("to"),
                door.reference.get("kind"),
                door.reference.get("pressure_boundary")) !=
               (control, site, kind, boundary)):
        return False
    d = clock_details if clock_details is not None else _clock().details
    if not service_hardware_ready(
            gate, rotors=d.get("rotors"), cargo=d.get("cargo"),
            water=d.get("water"), motion=d.get("motion")):
        return False
    capture = (f"ACC-{rotor}-FREIGHT-CAPTURE"
               if rotor and rotor.startswith("DR-")
               else "ACC-WR-HEAVY-DOCK" if gate == "ACC-WR-FREIGHT-STAGING"
               else None)
    if capture is not None:
        fixed = state("access", capture)
        if fixed.condition in _BROKEN or fixed.setting != "closed":
            return False
    zones = _topology()[0]
    a, b = zones.get(control), zones.get(site)
    if (not isinstance(a, str) or not a.startswith("PZ-")
            or not isinstance(b, str) or not b.startswith("PZ-")):
        return False
    left, right = state("pressure", a), state("pressure", b)
    if not _air_safe(left) or not _air_safe(right):
        return False
    pa = left.quantity * R_SPECIFIC_AIR * left.details[
        "temperature_k"] / left.details["gas_volume_m3"]
    pb = right.quantity * R_SPECIFIC_AIR * right.details[
        "temperature_k"] / right.details["gas_volume_m3"]
    return bool(math.isfinite(pa) and math.isfinite(pb)
                and abs(pa - pb) <= 2000.0)


def _freight_service_entry_ready(gate, *, clock_details=None):
    """Recheck current custody and plant conditions at each actual crossing."""
    if gate not in FREIGHT_SERVICE_GATES:
        return False
    d = clock_details if clock_details is not None else _clock().details
    ledger = d.get("freight_service")
    if ledger is None:
        return False
    validate_service_access(ledger)
    if gate not in ledger["secured_links"]:
        return False
    door = state("access", gate)
    return bool(door.setting == "open" and
                _freight_service_site_safe(gate, clock_details=d))


def _ordinary_crew_door_preflight(hatch):
    """Verify a fitted ordinary local door without bypassing pressure or rotation."""
    spec = hatch.reference
    if spec.get("kind") not in CREW_LOCAL_DOOR_KINDS:
        raise PhysicsError("This boundary needs its dedicated cargo/EVA controller")
    from world.ship_world import find_ship_space
    origin, destination = (
        find_ship_space(spec.get("from")),
        find_ship_space(spec.get("to")),
    )
    if origin is None or destination is None:
        raise PhysicsError("No two installed rooms at this local door")
    if origin.db.ox_frame != destination.db.ox_frame:
        raise PhysicsError("Moving-frame doors require a rated indexer")
    zones = _topology()[0]
    a, b = zones.get(spec.get("from")), zones.get(spec.get("to"))
    if (not isinstance(a, str) or not a.startswith("PZ-")
            or not isinstance(b, str) or not b.startswith("PZ-")):
        raise PhysicsError("Ordinary door cannot expose an unknown or vacuum space")
    if a != b and spec.get("pressure_boundary") is not True:
        raise PhysicsError("Unrated door cannot join separate pressure cells")
    left = state("pressure", a, lock=True)
    right = state("pressure", b, lock=True)
    if not _air_safe(left) or not _air_safe(right):
        raise PhysicsError("Unsafe gas, temperature or pressure at local door")
    pressure_left = (left.quantity * R_SPECIFIC_AIR *
                     left.details["temperature_k"] /
                     left.details["gas_volume_m3"])
    pressure_right = (right.quantity * R_SPECIFIC_AIR *
                      right.details["temperature_k"] /
                      right.details["gas_volume_m3"])
    if (not math.isfinite(pressure_left) or not math.isfinite(pressure_right)
            or abs(pressure_left - pressure_right) > 2000.0):
        raise PhysicsError("Unsafe differential pressure at ordinary door")


def _personnel_fixed_hatch_preflight(hatch):
    """Protect the six drum service locks and two independent HAB capsules."""
    source_id = hatch.source_id
    if re.fullmatch(r"ACC-DR-0[1-6]-LOCK-FIX", source_id):
        rotor, kind = source_id[4:9], "pressure_door"
    elif source_id in {"ACC-IX-A-FIX", "ACC-IX-B-FIX"}:
        rotor, kind = "HAB", "pressure_hatch"
    elif source_id == "ACC-WR-FIXED-IX":
        rotor, kind = "WR-01", "indexer_hatch"
    else:
        raise PhysicsError("Not an installed fixed-side indexer hatch")
    spec = hatch.reference
    if spec.get("kind") != kind or spec.get("pressure_boundary") is not True:
        raise PhysicsError("Fixed-side indexer pressure boundary misclassified")
    clock = _clock(lock=True)
    r = clock.details.get("rotors", {}).get(rotor)
    if not r or r.get("passenger_indexer") or r.get("freight_collar"):
        raise PhysicsError("Cannot open fixed hatch while a rotary interface is captured")
    if rotor == "HAB" and clock.details.get("hab_sync", {}).get("mode") not in {None, "stowed"}:
        raise PhysicsError("Moving HAB capture must stow before fixed hatch access")
    transfers = clock.details.get("personnel_transfers")
    if transfers and rotor in transfers["jobs"]:
        raise PhysicsError("Fixed hatch cannot open during an indexed passenger run")
    zones = _topology()[0]
    a, b = zones.get(spec["from"]), zones.get(spec["to"])
    if (not isinstance(a, str) or not a.startswith("PZ-")
            or not isinstance(b, str) or not b.startswith("PZ-") or a == b):
        raise PhysicsError("No verified independent fixed-side gas cells")
    left = state("pressure", a, lock=True)
    right = state("pressure", b, lock=True)
    if not _air_safe(left) or not _air_safe(right):
        raise PhysicsError("Fixed-side indexer air quality or pressure unsafe")
    def pressure(cell):
        return cell.quantity * R_SPECIFIC_AIR * cell.details[
            "temperature_k"] / cell.details["gas_volume_m3"]
    if abs(pressure(left) - pressure(right)) > 2000:
        raise PhysicsError("Fixed-side hatch differential pressure unsafe")


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
    panel = state("equipment", "LP-" + room)
    if panel.condition in _BROKEN:
        raise PhysicsError("Physical helm control panel damaged; use another authorised station")


def _crew_at(actor, space_id):
    if (actor is None or getattr(actor, "location", None) is None
            or getattr(actor.location.db, "ox_space_id", None) != space_id):
        raise PermissionError("Authenticated character must be physically at local control")
    if (actor.db.crew_role not in AUTHORISED_ROLES
            and not actor.check_permstring("Developer")):
        raise PermissionError("No qualified department authority")


def _food_at(actor, room):
    """Any authenticated living ship crew may provision and eat locally.

    Department-specific machinery authorisation is deliberately NOT a
    requirement for ordinary galley, pantry and meal work.
    """
    if (actor is None or getattr(actor, "location", None) is None or
            getattr(actor.location.db, "ox_space_id", None) != room):
        raise PermissionError("Real crew must attend the original food worksite")
    if not (getattr(actor.db, "crew_role", None) or
            actor.check_permstring("Developer")):
        raise PermissionError("Food custody requires a real authenticated crew member")


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
    if action not in {"power", "switch", "plant", "schedule", "mist", "hatch", "service", "helm", "attitude", "rotor", "drive", "freight", "ftl", "port", "water", "waste", "wasteport", "repair", "hull", "eva", "damage", "freight_service", "medical", "rescue", "flywheel_service", "radiator_service", "propulsion_service", "cultivation", "food", "instrument", "fault", "fabricate", "weld"}:
        raise PhysicsError("Unknown physical operation")
    if actor is None or getattr(actor.db, "ox_terminal_dead", False):
        raise PermissionError("A deceased or missing character cannot operate machinery")
    _clock(lock=True)  # serializes physical actions with world ticks
    selftest_evidence = None
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
                    else "" if action in {"power", "power", "schedule", "helm", "attitude", "rotor", "drive", "freight", "ftl", "port", "water", "waste", "wasteport", "repair", "hull", "eva", "damage", "freight_service", "medical", "rescue", "flywheel_service", "radiator_service", "propulsion_service", "cultivation", "food", "instrument", "fault", "fabricate", "weld"}
                    else "equipment:") + (CLOCK_KEY if action in {"power", "schedule", "helm", "attitude", "rotor", "drive", "freight", "ftl", "port", "water", "waste", "wasteport", "repair", "hull", "eva", "damage", "freight_service", "medical", "rescue", "flywheel_service", "radiator_service", "propulsion_service", "cultivation", "food", "instrument", "fault", "fabricate", "weld"} else target)
                or previous.after.get("requested_value") != value):
            raise PermissionError("Global request ID already belongs to another action")
        return _receipt(previous, request_id, actor, action, target)
    service_ledger = _clock().details.get("freight_service")
    if service_ledger is not None:
        validate_service_access(service_ledger)
        if freight_service_secured(service_ledger):
            if action in {"freight", "port", "wasteport", "helm", "attitude",
                          "drive", "ftl"}:
                raise PhysicsError("Attended freight service inhibits ship and cargo movement")
            if action == "rotor" and value not in {"stop", "hardlock"}:
                raise PhysicsError("Service work party holds rotary machinery inhibited")
    # Exterior maintenance requires the physical ship to remain in a
    # stable service attitude. Emergency COAST/HOLD, drive INHIBIT, and
    # rotary STOP/HARDLOCK remain possible after a casualty; no permit
    # blocks actions that make the ship safer.
    nozzle_work = _clock().details.get("propulsion_exterior")
    if nozzle_work is not None and nozzle_work["permit"] is not None and (
            action == "helm" and value != "coast"
            or action == "attitude" and value != "hold"
            or action == "drive" and value == "release"
            or action == "ftl" and value == "engage"):
        raise PhysicsError("Aft nozzle EVA worker inhibits thrust, RCS and FTL release")
    radiator_work = _clock().details.get("exterior_radiators")
    if radiator_work is not None and radiator_work["permits"]:
        if (action == "helm" and value != "coast"
                or action == "attitude" and value != "hold"
                or action == "drive" and value == "release"
                or action == "ftl" and value == "engage"
                or action == "rotor" and value not in {"stop", "hardlock"}
                and any(target in EXTERIOR_RADIATORS[wing]["near_rotors"]
                        for wing in radiator_work["permits"])):
            raise PhysicsError(
                "Attended exterior radiator work inhibits thrust, attitude or adjacent drum motion")
    # A physically incapacitated engineer cannot operate ANY remote switch,
    # helm or machinery after injury. Previously issued request receipts
    # above stay replayable without executing a new action.
    health_row = CanonicalShipState.objects.filter(
        pk="crew_health:" + getattr(actor, "dbref", "")).first()
    if health_row and health_row.condition in {
            "incapacitated", "critical", "dead"}:
        from world.ship_crew_access import CrewTransitError
        raise CrewTransitError("Crew casualty cannot operate physical ship controls")
    # Once a person has boarded a moving indexed carrier they cannot
    # operate machinery elsewhere until the real transport completes.
    transfers = _clock().details.get("personnel_transfers")
    eva_system = _clock().details.get("eva")
    if eva_system and actor.dbref in eva_system["transits"]:
        raise PermissionError("Character occupies a timed exterior route")
    if transfers and any(
            job["actor"] == actor.dbref
            for job in transfers["jobs"].values()):
        raise PermissionError("Character is committed to a moving personnel carriage")
    rescue_busy = _clock().details.get("rescue")
    if rescue_busy is not None:
        validate_rescue(rescue_busy)
        for pending_patient, pending in rescue_busy["jobs"].items():
            if actor.dbref in {pending_patient, pending["lead"], pending["helper"]}:
                if not (action == "rescue" and target == pending_patient
                        and value == "cancel" and actor.dbref in {pending["lead"], pending["helper"]}):
                    raise PermissionError("Crew member committed to timed physical casualty transport")
    bay_service = _clock().details.get("bay_access")
    if bay_service is not None and actor.dbref in bay_service["jobs"]:
        raise PermissionError("Worker occupies a sealed flywheel service airlock")
    food_nutrition = _clock().details.get("food")
    if (food_nutrition is not None
            and actor.dbref in food_nutrition["last"]["incapacitated"]
            and (action != "food" or value != "eat")):
        raise PermissionError("Measured severe nutritional depletion prevents physical work")
    if action in {"repair", "wasteport", "hull", "eva", "rescue"}:
        # A worker who has become incapacitated cannot command or advance
        # a physical repair or sealed waste movement. Deduplicated historic
        # receipts above remain replayable without issuing a second action.
        from world.ship_crew_access import _health_gate
        # The two assigned carriers must be able to ABORT a carriage
        # without first leaving the running job that immobilises them.
        if not (action == "rescue" and value == "cancel"):
            _health_gate(actor)
    if action == "switch":
        item = state("isolator", target, lock=True)
        here = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        if (target in {"ISO-RAD-HT-1", "ISO-RAD-HT-2"}
                and here == "ENG-CONTROL"
                and item.reference.get("remote_operable")):
            _crew_at(actor, "ENG-CONTROL")
            if state("equipment", "LP-ENG-CONTROL").condition in _BROKEN:
                raise PhysicsError("Actual engineering remote HT isolation panel is damaged")
        else:
            _crew_at(actor, item.space_id)
        if not item.reference.get("manual_operation"):
            raise PermissionError("No local manual operation is installed")
        if value not in {"open", "closed"} or item.condition in _BROKEN:
            raise PhysicsError("Unsafe switch command")
        if value == "closed" and item.details.get("physics_power_trip_latched"):
            raise PhysicsError("Breaker is physically tripped; isolate fault and reset locally")
        if value == "closed":
            # Older work orders may predate signed fault cases. They still
            # own a true maintenance padlock on each individually fitted
            # breaker; nobody can energise machinery around active workers.
            outstanding = (_clock().details.get("repairs") or
                           {"jobs": {}})["jobs"]
            for work_id in outstanding:
                if work_id.startswith("equipment:"):
                    affected = work_id.split(":", 1)[1]
                    if affected in set(MOTORS) | set(SERVICE_LOADS):
                        if target in feeders_for(affected):
                            raise PhysicsError(
                                "Active physical repair job padlocks its fitted feeder")
            fault_cases = (_clock().details.get("fault_cases") or
                           {"cases": {}})["cases"]
            if any(target in case["feeders"] and case["stage"] in {
                    "isolated", "repairing", "repaired"}
                   for case in fault_cases.values()):
                raise PhysicsError("Attended machinery isolation padlock prevents re-energizing feeder")
        if value == "closed" and target in {"ISO-GEN-M", "ISO-GEN-A", "ISO-GEN-B"}:
            shore = (_clock().details.get("electrical") or {}).get("shore")
            if shore and shore["connected"]:
                raise PhysicsError("Cannot close generator feed against connected shore power")
        if (_clock().details.get("electrical") is not None
                and item.reference.get("network") in {
                    "power", "g19_motor", "g19_motor_protected",
                    "g19_local_dc", "g19_local_charger",
                    "g19_equipment_service"}):
            _electrical_crew_air_gate(
                actor, item.space_id, _clock().details["electrical"])
        radiator_ledger = _clock().details.get("exterior_radiators")
        if value == "open" and radiator_ledger is not None:
            for wing in radiator_ledger["permits"]:
                if target in EXTERIOR_RADIATORS[wing]["isolation"]:
                    raise PhysicsError("Crew holds a radiator coolant isolation padlock")
        if value == "closed" and target.startswith("ISO-PWR-F") and (
                target.removeprefix("ISO-PWR-") in
                (_clock().details.get("flywheel_service") or {"permits": {}})["permits"]):
            raise PhysicsError("Physical flywheel maintenance padlock inhibits module re-energisation")
        if value == "closed" and target.startswith("ISO-MSB-XTIE"):
            tie = state("edge", "EDGE-MSB-XTIE")
            if tie.setting == "available":
                raise PhysicsError("Open cross-tie and obtain fresh synchronisation before restoring contacts")
        before = _snapshot(item)
        if item.setting != value:
            item.setting = value
            fields = ["setting", "revision"]
            if (value == "closed" and item.reference.get("network") in {
                    "g19_motor", "g19_motor_protected", "g19_equipment_service"}):
                info = dict(item.details)
                info["physics_manual_close_game_s"] = _clock().details["last_game_time"]
                item.details = info
                fields.append("details")
            item.revision += 1
            item.save(update_fields=fields)
    elif action == "plant":
        if target not in PLANTS or value not in {"on", "off"}:
            raise PhysicsError("No approved local plant control for that unit")
        item = state("equipment", target, lock=True)
        _crew_at(actor, item.space_id)
        if item.condition in _BROKEN and value == "on":
            raise PhysicsError("Failed plant cannot be started")
        case = (_clock().details.get("fault_cases") or
                {"cases": {}})["cases"].get(target)
        if value == "on" and case is not None and case["stage"] not in {
                "authorized", "verified"}:
            raise PhysicsError("Attended fault case requires checked and authorized restart")
        before = _snapshot(item)
        on = value == "on"
        thermal_work = _clock().details.get("exterior_radiators")
        if (on and thermal_work is not None and
                any(wing.startswith("RAD-LT-") for wing in
                    thermal_work["permits"]) and
                target in {"LT-PLANT", "RAD-LT-1", "RAD-LT-2",
                           "RAD-LT-3", "RAD-LT-4"}):
            raise PhysicsError("Exterior LT radiator crew inhibits full manifold restart")
        if target in GENERATION_MW:
            electr = _clock().details.get("electrical")
            if electr:
                _electrical_crew_air_gate(actor, item.space_id, electr)
                if on and electr["shore"] and electr["shore"]["connected"]:
                    raise PhysicsError("Isolate the connected shore-power inlet before generator startup")
        d = dict(item.details)
        if target in SERVICE_LOADS:
            service_clock = _clock(lock=True)
            sd = dict(service_clock.details)
            service = sd.get("service_operations")
            if service is None:
                raise PhysicsError("Independent equipment circuits require G19 commissioning")
            validate_service_operations(service)
            if on and target in MANUAL_RESTART and (
                    not service["units"][target]["operating"]
                    or service["units"][target]["restart_latched"]):
                # A milling/welding controller may not auto-restart simply
                # because an electrician restored its lost feeder. The
                # engineer must attend the actual tool and re-arm it under
                # a live, physically fused source.
                equipment_now = {x.source_id: x for x in
                                 CanonicalShipState.objects.filter(category="equipment")}
                edges_now = list(CanonicalShipState.objects.filter(category="edge"))
                breakers_now = {x.source_id: x for x in
                                CanonicalShipState.objects.filter(category="isolator")}
                supply = _power(
                    equipment_now, edges_now, breakers_now,
                    sd["load_profile"], ledger=sd["electrical"],
                    moored=contacts_active(sd["cargo"]))
                if not (supply["assured"] and service_power(
                        target, nodes=supply["nodes"],
                        equipment=equipment_now,
                        edges={x.source_id: x for x in edges_now},
                        switches=breakers_now)):
                    raise PhysicsError("Machine tool requires a live attended power circuit to rearm")
                before_service = _snapshot(service_clock)
                sd["service_operations"] = rearm_service_machine(service, target)
                service_clock.details = sd
                service_clock.revision += 1
                service_clock.save(update_fields=["details", "revision"])
                _event(service_clock, "manual_machine_restart_armed",
                       before_service, actor=actor)
                d["physics_online"] = False
        d["physics_commanded_on"] = on
        d["physics_online"] = False if not on else d.get("physics_online", False)
        d["physics_startup_s"] = (30.0 if target in GENERATION_MW else 10.0) if (
            on and not d["physics_online"]) else 0.0
        if d != item.details:
            item.details = d
            item.revision += 1
            item.save(update_fields=["details", "revision"])

    elif action == "power":
        import copy
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        if "electrical" not in d:
            raise PhysicsError("G19 installed electrical power not commissioned")
        e = copy.deepcopy(d["electrical"])
        available_equipment = {r.source_id: r for r in
                               CanonicalShipState.objects.filter(category="equipment")}
        network_edges = list(CanonicalShipState.objects.filter(category="edge"))
        network_switches = {r.source_id: r for r in
                            CanonicalShipState.objects.filter(category="isolator")}
        def live_grid():
            return _power(available_equipment, network_edges, network_switches,
                          d["load_profile"], ledger=e,
                          moored=contacts_active(d["cargo"]))
        def at_switch(edge_id):
            edge = state("edge", edge_id, lock=True)
            if edge.reference.get("network") != "power" or edge.condition in _BROKEN:
                raise PhysicsError("Selected power conductor damaged or absent")
            controls = [state("isolator", x, lock=True)
                        for x in edge.reference["isolator_ids"]]
            if not controls or any(
                    c.condition in _BROKEN or
                    c.details.get("physics_power_trip_latched")
                    for c in controls):
                raise PhysicsError("Transfer requires safe installed switchgear")
            room = getattr(getattr(actor, "location", None).db,
                           "ox_space_id", None) if getattr(actor, "location", None) else None
            if room not in {c.space_id for c in controls}:
                raise PermissionError("Physically attend the actual feeder switchgear")
            _crew_at(actor, room)
            _electrical_crew_air_gate(actor, room, e)
            return edge
        if target == "EDGE-MSB-XTIE":
            edge = at_switch(target)
            if value == "sync":
                if edge.setting == "available":
                    raise PhysicsError("Cross-tie already conducting")
                snapshot = live_grid()
                if not snapshot["active_generators"] or not any(
                        board in snapshot["main_nodes"] for board in (
                            "PWR-MSB-A", "PWR-MSB-B")):
                    raise PhysicsError("No live main bus to verify for synchronisation")
                e["sync"] = {
                    "ready_game_time": d["last_game_time"] + 15.0,
                    "expires_game_time": d["last_game_time"] + 90.0,
                    "source_signature": list(snapshot["source_signature"]),
                }
            elif value == "close":
                token = e["sync"]
                snapshot = live_grid()
                if (edge.setting == "available" or not token
                        or d["last_game_time"] < token["ready_game_time"]
                        or d["last_game_time"] > token["expires_game_time"]
                        or token["source_signature"] != list(
                            snapshot["source_signature"])
                        or any(network_switches[k].setting != "closed"
                               for k in edge.reference["isolator_ids"])):
                    raise PhysicsError("Cross-tie has no valid live synchronisation and healthy contacts")
                edge.setting = "available"
                edge.revision += 1
                edge.save(update_fields=["setting", "revision"])
                e["sync"] = None
            elif value == "open":
                edge.setting = "standby"
                edge.revision += 1
                edge.save(update_fields=["setting", "revision"])
                e["sync"] = None
            else:
                raise PhysicsError("Tie requires sync|close|open")
        elif target == "PWR-PROT" or re.fullmatch(r"HAB-0[1-8]-PROT", target):
            if value not in {"select:A", "select:B"}:
                raise PhysicsError("Protected source requires select:A or select:B")
            code = "EDGE-PWR-MSB-{}-PROT" if target == "PWR-PROT" else (
                "EDGE-" + target + "-{}")
            circuits = {side: at_switch(code.format(side)) for side in "AB"}
            # Break-before-make; both edges belong to the same real bus
            # selection. A dead alternative cannot reverse-feed a main bus.
            side = value[-1]
            for source, edge in circuits.items():
                requested = "available" if side == source else "standby"
                if edge.setting != requested:
                    edge.setting = requested
                    edge.revision += 1
                    edge.save(update_fields=["setting", "revision"])
        elif (re.fullmatch(r"EDGE-PWR-MSB-[AB]-PROT", target)
              or re.fullmatch(r"EDGE-HAB-0[1-8]-PROT-[AB]", target)):
            edge = at_switch(target)
            if value not in {"enable", "isolate"}:
                raise PhysicsError("Individual feeder requires enable|isolate")
            other = (target.replace("MSB-A-PROT", "MSB-B-PROT")
                     if target.endswith("MSB-A-PROT") else
                     target.replace("MSB-B-PROT", "MSB-A-PROT")
                     if target.endswith("MSB-B-PROT") else
                     target[:-1] + ("A" if target.endswith("B") else "B"))
            alternate = state("edge", other, lock=True)
            if value == "enable":
                if (alternate.setting == "available"
                        or any(state("isolator", k).setting != "closed"
                               for k in edge.reference["isolator_ids"])):
                    raise PhysicsError("Break-before-make requires isolation of alternate source")
                edge.setting = "available"
            else:
                edge.setting = "standby"
            edge.revision += 1
            edge.save(update_fields=["setting", "revision"])
        elif target in PROTECTED_FIRE_MOTORS:
            if value not in {"select:normal", "select:protected"}:
                raise PhysicsError("Fire pump requires select:normal|select:protected")
            pump = state("equipment", target, lock=True)
            _crew_at(actor, pump.space_id)
            _electrical_crew_air_gate(actor, pump.space_id, e)
            if pump.condition in _BROKEN:
                raise PhysicsError("The actual fire pump has failed")
            normal = state("edge", "EDGE-G19-MOTOR-" + target, lock=True)
            protected_edge_id, _protected_iso = protected_fire_ids(target)
            alternate = state("edge", protected_edge_id, lock=True)
            if (normal.reference.get("network") != "g19_motor"
                    or alternate.reference.get("network") != "g19_motor_protected"
                    or alternate.reference.get("from_node") != "PWR-PROT"):
                raise PhysicsError("The two independent fitted motor source paths disagree")
            selected, released = ((normal, alternate) if value == "select:normal"
                                  else (alternate, normal))
            if selected.condition in _BROKEN:
                raise PhysicsError("Target fire-pump feeder is physically damaged")
            for isolator_id in selected.reference["isolator_ids"]:
                contact = state("isolator", isolator_id, lock=True)
                if (contact.condition in _BROKEN or contact.setting != "closed"
                        or contact.details.get("physics_power_trip_latched")):
                    raise PhysicsError("Cannot select an open, failed or tripped motor source")
            # Persist a break-before-make transfer, without energising both
            # independent sources even briefly.
            if released.setting != "standby":
                released.setting = "standby"
                released.revision += 1
                released.save(update_fields=["setting", "revision"])
            if selected.setting != "available":
                selected.setting = "available"
                selected.revision += 1
                selected.save(update_fields=["setting", "revision"])
        elif target in LOCAL_LOADS:
            battery = state("equipment", target, lock=True)
            _crew_at(actor, battery.space_id)
            _electrical_crew_air_gate(actor, battery.space_id, e)
            if battery.condition in _BROKEN:
                raise PhysicsError("Local emergency battery has failed")
            if value not in {"standby", "reserve", "charge"}:
                raise PhysicsError("Local battery requires standby|reserve|charge")
            d["local_backup"] = set_local_mode(d["local_backup"], target, value)
        elif target in (*POWER_BANKS, *POWER_FLYWHEELS):
            bank_equipment = state("equipment", target, lock=True)
            _crew_at(actor, bank_equipment.space_id)
            _electrical_crew_air_gate(actor, bank_equipment.space_id, e)
            family = "flywheels" if target in POWER_FLYWHEELS else "banks"
            if bank_equipment.condition in _BROKEN or target not in e[family]:
                raise PhysicsError("Unrated, isolated or damaged fitted energy store")
            if value not in {"standby", "charge", "discharge"}:
                raise PhysicsError("Energy store requires standby|charge|discharge")
            if family == "flywheels":
                custody = d.get("flywheel_service") or {}
                if target in custody.get("rundowns", {}):
                    raise PhysicsError("Supervised rotor rundown controls the individual source")
                if value != "standby" and target in custody.get("permits", {}):
                    raise PhysicsError("Measured flywheel remains under a real maintenance padlock")
            e[family][target]["mode"] = value
        elif target == "SHORE-PWR":
            supply = state("equipment", target, lock=True)
            _crew_at(actor, supply.space_id)
            if supply.condition in _BROKEN or not e["shore"]:
                raise PhysicsError("No surveyed external shore supply")
            if value == "connect":
                if not contacts_active(d["cargo"]):
                    raise PhysicsError("No physical commercial mooring")
                if live_grid()["active_generators"]:
                    raise PhysicsError("Isolate fitted generation before nonparallel shore connection")
                feeder = at_switch("EDGE-SHORE-PWR")
                if feeder.setting != "available":
                    raise PhysicsError("Shore source line is not physically selected")
                e["shore"]["connected"] = True
            elif value == "disconnect":
                e["shore"]["connected"] = False
            else:
                raise PhysicsError("Shore connection must be connect|disconnect")
        elif target.startswith("ISO-") and value == "reset":
            breaker = state("isolator", target, lock=True)
            if breaker.reference.get("network") not in {
                    "power", "g19_motor", "g19_motor_protected",
                    "g19_local_dc", "g19_local_charger",
                    "g19_equipment_service"}:
                raise PhysicsError("Not an installed power breaker")
            _crew_at(actor, breaker.space_id)
            if breaker.setting != "open" or breaker.condition in _BROKEN:
                raise PhysicsError("Protection reset requires isolated sound breaker")
            _electrical_crew_air_gate(actor, breaker.space_id, e)
            try:
                e = reset_protection(e, target)
            except ElectricalError as exc:
                raise PhysicsError(str(exc)) from exc
            bd = dict(breaker.details)
            bd.pop("physics_power_trip_latched", None)
            bd.pop("physics_power_trip_reason", None)
            breaker.details = bd
            breaker.revision += 1
            breaker.save(update_fields=["details", "revision"])
        else:
            raise PhysicsError("No installed local power operation for target")
        e["last"] = dict(e["last"])
        e["last"]["last_manual_control"] = {"target": target, "value": value}
        validate_electrical(e)
        d["electrical"] = e
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action in {"water", "waste"}:
        import copy
        def wet_crew_at(room):
            _crew_at(actor, room)
            zone = _topology()[0].get(room)
            if (not isinstance(zone, str) or not zone.startswith("PZ-")
                    or not _air_safe(state("pressure", zone))):
                raise PhysicsError("Local sanitation work requires verified safe atmosphere")

        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        if "water" not in d:
            raise PhysicsError("G19 water/waste plant has not been commissioned")
        w = copy.deepcopy(d["water"])
        if action == "water" and target == "INV-DC-CONSUMABLES":
            room = getattr(getattr(actor, "location", None).db, "ox_space_id", None) if getattr(actor, "location", None) else None
            if room is None:
                raise PermissionError("Source filter handoff needs a real local worker")
            wet_crew_at(room)
            stock_item = state("inventory", "INV-DC-CONSUMABLES", lock=True)
            if room not in stock_item.reference.get("location_ids", ()):
                raise PhysicsError("Cannot withdraw filters from a remote stores inventory")
            command, sep, amount = str(value).partition(":")
            if command != "pickup_filter" or not sep:
                raise PhysicsError("Local filter stores require pickup_filter:<kg>")
            try:
                qty = _positive(float(amount))
            except (TypeError, ValueError) as exc:
                raise PhysicsError("Invalid portable filter quantity") from exc
            stock_before = _snapshot(stock_item)
            try:
                w, new_amount = take_filter(
                    w, actor_dbref=actor.dbref, room=room, kg=qty,
                    stock_kg=stock_item.quantity * 1000.0)
            except WaterError as exc:
                raise PhysicsError(str(exc)) from exc
            stock_item.quantity = new_amount / 1000.0
            stock_item.revision += 1
            stock_item.save(update_fields=["quantity", "revision"])
            _event(stock_item, "local_filter_issued_to_carrier", stock_before,
                   actor=actor)
        elif action == "water" and target == "POTABLE-TANK-MAIN":
            wet_crew_at("WATER-FWD")
            if state("equipment", "LP-WATER-FWD").condition in _BROKEN:
                raise PhysicsError("Forward local water panel damaged")
            if value == "reserve_open":
                if w["potable_quarantined"]:
                    raise PhysicsError("Cannot release reserve into contaminated potable circuit")
                w["reserve_released"] = True
            elif value == "reserve_close":
                w["reserve_released"] = False
            elif value == "quarantine":
                w["potable_quarantined"] = True
                w["reserve_released"] = False
                w["quality_sample"] = None
            elif value == "sample":
                # Actual locally attended chemistry observation, not a model
                # claim that simply toggles a safety flag.
                w["quality_sample"] = (
                    "pass" if w["suspected_contamination_kg"] == 0.0 else "fail")
                w["quality_sample_tick"] = d["last_game_time"]
            elif value == "clear":
                if (w["quality_sample"] != "pass" or
                        w["suspected_contamination_kg"] > 0.0 or
                        not any(state("equipment", f"WATER-PROC-{side}").condition
                                not in _BROKEN for side in "AB")):
                    raise PhysicsError("Potable chemistry has not passed physical sampling")
                w["potable_quarantined"] = False
            else:
                raise PhysicsError("Water tank requires reserve_open|reserve_close|quarantine|sample|clear")
        elif action == "water" and target in {"WATER-PROC-A", "WATER-PROC-B"}:
            processor = state("equipment", target, lock=True)
            wet_crew_at(processor.space_id)
            side = target[-1]
            if isinstance(value, str) and value.startswith("load_filter:"):
                if processor.condition in _BROKEN:
                    raise PhysicsError("Damaged purifier cannot accept service filter")
                try:
                    qty = _positive(float(value.partition(":")[2]))
                    w = load_filter(w, actor_dbref=actor.dbref,
                                    side=side, kg=qty)
                except (WaterError, ValueError, TypeError) as exc:
                    raise PhysicsError("Verified carried filter and rack space required") from exc
            elif value in {"on", "off", "quarantine"}:
                if value == "on" and processor.condition in _BROKEN:
                    raise PhysicsError("Damaged purifier cannot resume work")
                w["water_train"][side] = (
                    "quarantined" if value == "quarantine" else value)
                if value != "on":
                    w["decontaminate"][side] = False
            elif value in {"decontaminate", "decontaminate_off"}:
                if value == "decontaminate" and (
                        processor.condition in _BROKEN or
                        not w["potable_quarantined"]):
                    raise PhysicsError("Cannot scrub unisolated or damaged potable supply")
                w["decontaminate"][side] = value == "decontaminate"
                if value == "decontaminate":
                    w["water_train"][side] = "on"
            else:
                raise PhysicsError("Unknown local purification work command")
        elif action == "waste" and target in {"WASTE-PROC-A", "WASTE-PROC-B"}:
            processor = state("equipment", target, lock=True)
            wet_crew_at(processor.space_id)
            if value not in {"on", "off", "quarantine"}:
                raise PhysicsError("Unknown sanitation processor command")
            if value == "on" and processor.condition in _BROKEN:
                raise PhysicsError("Damaged waste processor cannot restart")
            w["waste_train"][target[-1]] = (
                "quarantined" if value == "quarantine" else value)
        elif action == "waste" and target in {
                "WASTE-RESIDUE-HOLD-A", "WASTE-RESIDUE-HOLD-B",
                "IND-SCRAP-HOLD-A", "IND-SCRAP-HOLD-B",
                "HAZ-ISO-HOLD-A", "HAZ-ISO-HOLD-B"}:
            receiver = state("equipment", target, lock=True)
            wet_crew_at(receiver.space_id)
            group = ("sanitary" if target.startswith("WASTE-") else
                     "industrial" if target.startswith("IND-") else "hazardous")
            side = target[-1]
            if target in w["waste_offload"]["jobs"] and not (
                    isinstance(value, str) and value.startswith("stage:")):
                raise PhysicsError("Waste receiver is reserved for physical port transfer")
            if isinstance(value, str) and value.startswith("stage:"):
                if receiver.condition in _BROKEN:
                    raise PhysicsError("Damaged sealed receiver cannot depart its store")
                acc_id = value.partition(":")[2]
                permit = w["waste_offload"]["acceptances"].get(acc_id)
                if permit and any(
                        p[:5] == permit["portal_id"][:5]
                        for p in d.get("cargo", {}).get("port_jobs", {})):
                    raise PhysicsError("Port's installed radial handler already has commercial cargo")
                route = (w["waste_offload"]["routes"].get(
                    target + ":" + permit["portal_id"]) if permit else None)
                try:
                    w = prepare_waste_offload(
                        w, receiver=target, acceptance_id=acc_id, route=route)
                except WaterError as exc:
                    raise PhysicsError(str(exc)) from exc
            elif isinstance(value, str) and value.startswith("deposit:"):
                if group == "sanitary" or receiver.condition in _BROKEN or not (
                        w["cassette_sealed"][group][side]):
                    raise PhysicsError("Material not compatible with this sealed waste receiver")
                parts = value.split(":")
                if len(parts) != 3:
                    raise PhysicsError("Waste deposit requires deposit:<inventory-id>:<kg>")
                _, source, mass = parts
                try:
                    qty = _positive(float(mass))
                except (TypeError, ValueError) as exc:
                    raise PhysicsError("Waste load is not a valid positive quantity") from exc
                if source not in {"INV-SPARES", "INV-DC-CONSUMABLES"}:
                    raise PhysicsError("Unknown material custody account")
                original = state("inventory", source, lock=True)
                sink = state("inventory", (
                    "INV-INDUSTRIAL-SCRAP" if group == "industrial"
                    else "INV-HAZARDOUS-RESIDUE"), lock=True)
                if receiver.space_id not in original.reference.get("location_ids", ()):
                    raise PhysicsError("Source inventory not physically in this room")
                source_before = _snapshot(original)
                sink_before = _snapshot(sink)
                balances = {
                    "normal": state("inventory", "INV-WATER-NORMAL").quantity * 1000,
                    "reserve": state("inventory", "INV-WATER-RESERVE").quantity * 1000,
                    "sanitary": state("inventory", "INV-WASTE-RESIDUE").quantity * 1000,
                    "industrial": state("inventory", "INV-INDUSTRIAL-SCRAP").quantity * 1000,
                    "hazardous": state("inventory", "INV-HAZARDOUS-RESIDUE").quantity * 1000,
                    "filter": state("inventory", "INV-DC-CONSUMABLES").quantity * 1000,
                    "spares": state("inventory", "INV-SPARES").quantity * 1000,
                }
                try:
                    w, new_balances = local_classified_deposit(
                        w, balances, category=group, source=source,
                        actor_room=receiver.space_id, target_side=side,
                        kg=qty, hardware={"bins": {group: {
                            side: receiver.condition not in _BROKEN and
                            w["cassette_sealed"][group][side]}}})
                except WaterError as exc:
                    raise PhysicsError(str(exc)) from exc
                original.quantity = new_balances[
                    "spares" if source == "INV-SPARES" else "filter"] / 1000.0
                sink.quantity = new_balances[group] / 1000.0
                for row, prior in ((original, source_before), (sink, sink_before)):
                    row.revision += 1
                    row.save(update_fields=["quantity", "revision"])
                    _event(row, "classified_local_waste_deposit",
                           prior, actor=actor)
            elif value in {"seal", "unseal"}:
                if value == "unseal" and w["cassettes"][group][side] > 0:
                    raise PhysicsError("Loaded sealed waste cassette needs a real offload cycle")
                if value == "seal" and receiver.condition in _BROKEN:
                    raise PhysicsError("Damaged cassette cannot be proven sealed")
                w["cassette_sealed"][group][side] = value == "seal"
            else:
                raise PhysicsError("Waste receiver requires seal|unseal|deposit:<id>:<kg>")
        else:
            raise PhysicsError("Water or waste target is not an installed local control")
        stocks = {
            k: state("inventory", ident).quantity * 1000
            for k, ident in (
                ("normal", "INV-WATER-NORMAL"),
                ("reserve", "INV-WATER-RESERVE"),
                ("sanitary", "INV-WASTE-RESIDUE"),
                ("industrial", "INV-INDUSTRIAL-SCRAP"),
                ("hazardous", "INV-HAZARDOUS-RESIDUE"),
                ("filter", "INV-DC-CONSUMABLES"),
                ("spares", "INV-SPARES"),
            )
        }
        validate_water(w, stocks)
        d["water"] = w
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "wasteport":
        if target not in WASTE_RECEIVERS or value not in {
                "haul", "offload", "return", "pause", "resume", "abort",
                "capture_open", "capture_close"}:
            raise PhysicsError("Unknown local waste freight-handling command")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        water = d.get("water")
        if water is None:
            raise PhysicsError("Solid-waste port logistics not commissioned")
        job = water["waste_offload"]["jobs"].get(target)
        if job is None:
            raise PhysicsError("No matching on-board sealed waste cassette transfer")
        portal = job["portal_id"]
        drum = portal[:5]
        room = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        role = getattr(actor.db, "crew_role", None)
        cargo_authority = role in {
            "cargo_officer", "chief_engineer", "watch_engineer",
            "environment_tech"} or actor.check_permstring("Developer")
        if not cargo_authority:
            raise PermissionError("Port waste work requires actual cargo/engineering authority")
        required_room = (
            drum + "-FREIGHT-LOCK"
            if value in {"haul", "return", "capture_open", "capture_close"} or
            value == "abort" and job["phase"] in {"prepared", "hauling"}
            else "CARGO-CTRL-FWD")
        if room != required_room:
            raise PermissionError("Worker must attend the real freight or port station")
        cell = _topology()[0].get(room)
        if not cell or not _air_safe(state("pressure", cell)):
            raise PhysicsError("Waste transfer station atmosphere is unsafe")
        if value in {"capture_open", "capture_close"}:
            rotor = d["rotors"][drum]
            gate = state("access", "ACC-" + drum + "-FREIGHT-CAPTURE", lock=True)
            if gate.condition in _BROKEN:
                raise PhysicsError("Damaged rated freight hatch cannot cycle")
            if value == "capture_open":
                if (contacts_active(d["cargo"]) or not (
                        rotor["freight_collar"] and rotor["hardlock"]
                        and rotor["brake"] and rotor["target_rpm"] == 0
                        and abs(rotor["rpm"]) < 0.001
                        and not rotor["passenger_indexer"])):
                    raise PhysicsError("Freight capture requires a stationary indexed drum")
                spec = gate.reference
                z = _topology()[0]
                za, zb = z.get(spec["from"]), z.get(spec["to"])
                if not za or not zb or not za.startswith("PZ-") or not zb.startswith("PZ-"):
                    raise PhysicsError("Freight capture into unclassified atmosphere refused")
                ca, cb = state("pressure", za), state("pressure", zb)
                if not _air_safe(ca) or not _air_safe(cb):
                    raise PhysicsError("Freight capture air or heat unsafe")
                pa = ca.quantity * R_SPECIFIC_AIR * ca.details["temperature_k"] / ca.details["gas_volume_m3"]
                pb = cb.quantity * R_SPECIFIC_AIR * cb.details["temperature_k"] / cb.details["gas_volume_m3"]
                if abs(pa-pb) > 2000:
                    raise PhysicsError("Freight capture pressure difference too high")
            if gate.setting != ("open" if value == "capture_open" else "closed"):
                gate_before = _snapshot(gate)
                gate.setting = "open" if value == "capture_open" else "closed"
                gate.revision += 1
                gate.save(update_fields=["setting", "revision"])
                _event(gate, "local_sealed_waste_freight_gate", gate_before, actor=actor)
        if value in {"haul", "return"}:
            if value == "haul" and contacts_active(d["cargo"]):
                raise PhysicsError("First load a sealed cassette through freight before docking")
            access = {x.source_id: x for x in
                      CanonicalShipState.objects.filter(category="access")}
            equip = {x.source_id: x for x in
                     CanonicalShipState.objects.filter(category="equipment")}
            pressure = {x.source_id: x for x in
                        CanonicalShipState.objects.filter(category="pressure")}
            if not _waste_freight_ready(
                    job, water, rotors=d["rotors"], equipment=equip,
                    access=access, pressure=pressure, zones=_topology()[0],
                    cargo=d["cargo"]):
                raise PhysicsError("Sealed freight route, air, collar or handler unavailable")
        if value == "offload":
            access = {x.source_id: x for x in
                      CanonicalShipState.objects.filter(category="access")}
            equip = {x.source_id: x for x in
                     CanonicalShipState.objects.filter(category="equipment")}
            if not _waste_port_ready(
                    job, rotors=d["rotors"], equipment=equip,
                    access=access, cargo=d["cargo"]):
                raise PhysicsError("No verified berth or sealed functioning cargo port")
        try:
            d["water"] = (water if value in {"capture_open", "capture_close"}
                          else command_waste_offload(
                              water, receiver=target, verb=value))
            stocks = {cat: state("inventory", ident).quantity * 1000
                      for cat, ident in (
                          ("sanitary", "INV-WASTE-RESIDUE"),
                          ("industrial", "INV-INDUSTRIAL-SCRAP"),
                          ("hazardous", "INV-HAZARDOUS-RESIDUE"))}
            validate_offload(d["water"], stocks)
        except WaterError as exc:
            raise PhysicsError(str(exc)) from exc
        if d != item.details:
            item.details = d
            item.revision += 1
            item.save(update_fields=["details", "revision"])
    elif action == "damage":
        if value != "isolate":
            raise PhysicsError("Damage control requires isolate at the engineering panel")
        _crew_at(actor, "ENG-CONTROL")
        panel = state("equipment", "LP-ENG-CONTROL")
        if panel.condition in _BROKEN:
            raise PhysicsError("Installed central damage-control panel failed")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        major = d.get("major_damage")
        if major is None:
            raise PhysicsError("Major shell damage and EVA not commissioned")
        if target not in major["sites"]:
            raise PhysicsError("No surveyed major hull break in this real pressure cell")
        try:
            major = start_containment(major, zone=target, actor=actor.dbref)
        except MajorDamageError as exc:
            raise PhysicsError(str(exc)) from exc
        d["major_damage"] = major
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "eva":
        # All airlock, suit and exterior-platform actions have one durable
        # request receipt and are serialized against the authoritative clock.
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        eva = d.get("eva")
        if eva is None:
            raise PhysicsError("Real EVA plant and four finite suits not commissioned")
        try:
            validate_eva(eva)
        except EVAError as exc:
            raise PhysicsError(str(exc)) from exc
        import copy
        eva = copy.deepcopy(eva)
        room = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        if not room:
            raise PermissionError("Suited physical worker must stand in the ship")
        carried_id, carried = suit_of(eva, actor.dbref)
        if target == "INV-DC-CONSUMABLES":
            if not value.startswith("stage:"):
                raise PhysicsError("EVA source issue requires stage:<kg>")
            _crew_at(actor, room)
            stock = state("inventory", target, lock=True)
            try:
                kg = _positive(float(value.partition(":")[2]), maximum=SUIT_O2_KG)
                allocations = stock.reference.get("location_allocations_t", {})
                if (room not in allocations or
                        eva["source_used_kg"].get(room, 0) + kg >
                        allocations[room] * 1000 + 1e-7 or
                        stock.quantity * 1000 + 1e-7 < kg):
                    raise PhysicsError("No verified unused breathing stock at this real locker")
                new_eva = stage_suit_oxygen(eva, actor=actor.dbref,
                                            room=room, kg=kg)
            except (ValueError, TypeError, EVAError) as exc:
                raise PhysicsError(str(exc)) from exc
            old_stock = _snapshot(stock)
            stock.quantity -= kg / 1000.0
            stock.revision += 1
            stock.save(update_fields=["quantity", "revision"])
            _event(stock, "crew_eva_breathing_canister_issued", old_stock)
            eva = new_eva
        elif target in EVA_LOCKS:
            spec = lock_contract(target)
            if room not in {target, spec["trunk"], spec["outside"]}:
                raise PermissionError("Airlock controls are local to actual hatches")
            inner = state("access", spec["inner"], lock=True)
            outer = state("access", spec["outer"], lock=True)
            panel = state("equipment", spec["panel"])
            if panel.condition in _BROKEN:
                raise PhysicsError("Installed EVA local panel is damaged")
            mode = eva["locks"][target]["mode"]
            if value == "checkout":
                _crew_at(actor, target)
                if mode != "pressurised" or not _air_safe(
                        state("pressure", spec["zone"])):
                    raise PhysicsError("Suit must be checked out in breathable dock")
                if outer.setting != "closed":
                    raise PhysicsError("Suit issue requires outer pressure hatch shut")
                try:
                    available = next((row for key, row in sorted(eva["suits"].items())
                                      if row["home"] == target and row["holder"] is None), None)
                    if not available:
                        raise EVAError("No real spare suit at this lock")
                    needed = SUIT_O2_KG - available["exposure"]["suit_oxygen_kg"]
                    health_row = CanonicalShipState.objects.filter(
                        pk="crew_health:" + actor.dbref).first()
                    eva, _, _ = checkout_suit(
                        eva, actor=actor.dbref, lock=target,
                        supplied_oxygen_kg=needed,
                        wearer_health=health_row.details if health_row else None)
                except EVAError as exc:
                    raise PhysicsError(str(exc)) from exc
            elif value == "return":
                _crew_at(actor, target)
                if (mode != "pressurised" or inner.setting != "closed"
                        or outer.setting != "closed"):
                    raise PhysicsError("Return only in sealed re-pressurised airlock")
                try:
                    eva = return_suit(eva, actor=actor.dbref, lock=target)
                except EVAError as exc:
                    raise PhysicsError(str(exc)) from exc
            elif value in {"pumpdown", "repressurise"}:
                _crew_at(actor, target)
                if not carried or carried["home"] != target or carried["integrity"] < .8:
                    raise PhysicsError("Properly fitted issued suit required inside chamber")
                damper = state("isolator", spec["damper"])
                breaker = state("isolator", spec["breaker"])
                if (inner.setting != "closed" or outer.setting != "closed"
                        or damper.setting != "closed" or breaker.setting != "closed"
                        or damper.condition in _BROKEN or breaker.condition in _BROKEN):
                    raise PhysicsError("Seal both airlock doors and isolate the actual air branch")
                supply = _power(
                    {r.source_id:r for r in CanonicalShipState.objects.filter(
                        category="equipment")},
                    list(CanonicalShipState.objects.filter(category="edge")),
                    {r.source_id:r for r in CanonicalShipState.objects.filter(
                        category="isolator")},
                    item.details["load_profile"],
                    ledger=item.details.get("electrical"),
                    moored=contacts_active(item.details.get("cargo", {})))
                if not supply["assured"] or "NODE-LP-" + target not in supply["nodes"]:
                    raise PhysicsError("EVA pump has no verified local electrical feeder")
                if value == "pumpdown":
                    cell = state("pressure", spec["zone"])
                    if (not _air_safe(cell) or cell.quantity > MAX_GAS_BUFFER_KG):
                        raise PhysicsError("Unsafe gas or finite recovery-bottle capacity")
                try:
                    eva = begin_cycle(eva, lock=target, direction=value)
                except EVAError as exc:
                    raise PhysicsError(str(exc)) from exc
            elif value in {"inner_open", "inner_close"}:
                if room not in {target, spec["trunk"]}:
                    raise PermissionError("Cannot reach inner airlock hatch")
                if inner.condition in _BROKEN:
                    raise PhysicsError("Installed inner hatch damaged")
                if value == "inner_open":
                    if mode != "pressurised" or outer.setting != "closed":
                        raise PhysicsError("Inner hatch interlocked until full re-pressurisation")
                    zones = _topology()[0]
                    a = state("pressure", zones[spec["trunk"]])
                    b = state("pressure", spec["zone"])
                    if not _air_safe(a) or not _air_safe(b):
                        raise PhysicsError("No verified breathable gas both sides of inner hatch")
                    pa = a.quantity * R_SPECIFIC_AIR * a.details["temperature_k"] / a.details["gas_volume_m3"]
                    pb = b.quantity * R_SPECIFIC_AIR * b.details["temperature_k"] / b.details["gas_volume_m3"]
                    if abs(pa - pb) > 2000:
                        raise PhysicsError("Inner hatch differential pressure not equalised")
                original_door = _snapshot(inner)
                inner.setting = "open" if value == "inner_open" else "closed"
                inner.revision += 1
                inner.save(update_fields=["setting", "revision"])
                _event(inner, "crew_eva_inner_hatch", original_door)
            elif value in {"outer_open", "outer_close"}:
                if room not in {target, spec["outside"]}:
                    raise PermissionError("Exterior hatch only reachable at real airlock")
                if outer.condition in _BROKEN:
                    raise PhysicsError("Outer EVA hatch is damaged")
                if value == "outer_open":
                    if (mode != "vacuum" or inner.setting != "closed"
                            or not carried or carried["integrity"] < .8
                            or carried["exposure"]["suit_oxygen_kg"] <= 0):
                        raise PhysicsError("Unpressurised lock and sound breathing suit required")
                original_door = _snapshot(outer)
                outer.setting = "open" if value == "outer_open" else "closed"
                outer.revision += 1
                outer.save(update_fields=["setting", "revision"])
                _event(outer, "crew_eva_outer_hatch", original_door)
            else:
                raise PhysicsError("Use checkout, return, pumpdown, repressurise or hatch action")
        elif target.startswith("ACC-EXT-") and value in {"deploy", "stow"}:
            if not carried or carried["integrity"] < .8:
                raise PermissionError("Exterior work platform requires physical EVA suit")
            panel = state("access", target, lock=True)
            if (panel.reference.get("kind") != "eva_work_platform_transfer"
                    or room not in {panel.reference["from"], panel.reference["to"]}):
                raise PermissionError("No installed work platform at this exterior position")
            if panel.condition in _BROKEN:
                raise PhysicsError("EVA platform access mechanism damaged")
            platform = state("equipment", "EVA-WORK-PLATFORM")
            crawler = state("equipment", lock_contract(carried["home"])["crawler"])
            if platform.condition in _BROKEN or crawler.condition in _BROKEN:
                raise PhysicsError("Unserviceable EVA platform or issued crawler")
            if (panel.reference["to"] == PROPULSION_FACE
                    and value == "deploy" and room != PROPULSION_FACE
                    and not _propulsion_exterior_ready(
                        d, {row.source_id: row for row in
                            CanonicalShipState.objects.filter(category="equipment")})):
                raise PhysicsError("Aft plume is not safed and permitted for EVA entry")
            radiator = EXTERIOR_RADIATOR_FACES.get(panel.reference["to"])
            if radiator is not None and value == "deploy" and room != panel.reference["to"]:
                if not _radiator_worksite_ready(
                        d, radiator,
                        {row.source_id: row for row in
                         CanonicalShipState.objects.filter(category="equipment")},
                        {row.source_id: row for row in
                         CanonicalShipState.objects.filter(category="isolator")}):
                    raise PhysicsError("Cannot deploy onto an unisolated or hot radiator")
            original_door = _snapshot(panel)
            panel.setting = "open" if value == "deploy" else "closed"
            panel.revision += 1
            panel.save(update_fields=["setting", "revision"])
            _event(panel, "crew_eva_work_platform", original_door)
        else:
            raise PhysicsError("Unknown external worksite or fitted EVA airlock")
        d["eva"] = eva
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])


    elif action == "rescue":
        # The only assisted casualty movement is a two-person physically
        # occupied, timed *existing* interior passage. Neither carrier nor
        # patient may move themselves elsewhere until the job completes.
        clock = _clock(lock=True)
        d = dict(clock.details)
        rescue = d.get("rescue")
        if rescue is None:
            raise PhysicsError("Attended casualty transport not commissioned")
        validate_rescue(rescue)
        if not re.fullmatch(r"#[0-9]+", target):
            raise PhysicsError("Rescue target must be a real patient dbref")
        before = _snapshot(clock)
        try:
            if value == "cancel":
                job = rescue["jobs"].get(target)
                if job is None or actor.dbref not in {job["lead"], job["helper"]}:
                    raise PermissionError("Only a participating carrier at the origin may cancel")
                origin = getattr(getattr(actor.location, "db", None), "ox_space_id", None)
                if origin != job["origin"]:
                    raise PermissionError("Cancel from actual rescue origin")
                rescue = finish_rescue(
                    rescue, patient=target, request_id=job["request_id"],
                    cancelled=True)
            else:
                parts = value.split(":")
                if len(parts) != 3:
                    raise PhysicsError("Rescue needs <helper-dbref>:<link-id>:<direction>")
                helper_ref, link, direction = parts
                from evennia.objects.models import ObjectDB
                from world.ship_world import find_world_entity, find_ship_space
                from world.ship_crew_access import _clearance
                if not re.fullmatch(r"#[0-9]+", helper_ref):
                    raise PhysicsError("Two identifiable carriers required")
                helper = ObjectDB.objects.filter(id=int(helper_ref[1:])).first()
                patient = ObjectDB.objects.filter(id=int(target[1:])).first()
                exit_obj = find_world_entity(f"access:{link}:{direction}")
                if (helper is None or patient is None or exit_obj is None
                        or link not in {a.source_id for a in
                                        CanonicalShipState.objects.filter(category="access")}):
                    raise PhysicsError("Unknown crew member or fitted local passage")
                dest = exit_obj.destination
                origin = exit_obj.location
                if (actor.location != origin or helper.location != origin
                        or patient.location != origin
                        or origin is None or dest is None):
                    raise PermissionError("Both carriers and patient must share the actual departure room")
                if (getattr(actor.db, "crew_role", None) not in
                        MEDICAL_ROLES | {"chief_engineer", "watch_engineer"}
                        or not getattr(helper.db, "crew_role", None)):
                    raise PermissionError("Qualified rescue leader and enrolled helper required")
                if len({actor.dbref, helper_ref, target}) != 3:
                    raise PhysicsError("Two distinct carers cannot carry themselves")
                hp = {
                    ref: CanonicalShipState.objects.filter(
                        pk="crew_health:" + ref, source_model=MODEL).first()
                    for ref in (actor.dbref, helper_ref, target)}
                if (any(row is None for row in hp.values())
                        or hp[target].condition not in {
                            "impaired", "incapacitated", "critical"}
                        or any(hp[r].condition not in {"fit", "impaired"}
                               for r in (actor.dbref, helper_ref))
                        or any(getattr(a.db, "ox_terminal_dead", False)
                               for a in (actor, helper, patient))):
                    raise PhysicsError("Living measured patient and two capable enrolled carriers required")
                # The installed normal exit preflight tests BOTH independent
                # people and its actual pressure, damage, frame and opening.
                _clearance(actor, exit_obj, dest)
                _clearance(helper, exit_obj, dest)
                door = state("access", link)
                if door.reference.get("kind") not in INTERIOR_CARRY_KINDS:
                    raise PhysicsError("Only an existing ordinary interior door permits manual carry")
                if origin.db.ox_frame != dest.db.ox_frame:
                    raise PhysicsError("Manual carry cannot cross a moving frame")
                zones = _topology()[0]
                if not all(isinstance(zones.get(space.db.ox_space_id), str)
                           and zones[space.db.ox_space_id].startswith("PZ-")
                           for space in (origin, dest)):
                    raise PhysicsError("Unrated vacuum or unknown atmosphere cannot support manual carry")
                travel = door.reference.get("traverse_time_s")
                if (isinstance(travel, bool) or
                        not isinstance(travel, (int, float)) or
                        not math.isfinite(travel) or not 0 < travel <= 80):
                    raise PhysicsError("Unrated casualty handling width or transfer time")
                duration = max(30.0, float(travel) * 3.0)
                rescue = begin_rescue(
                    rescue, patient=target, lead=actor.dbref,
                    helper=helper_ref, link=link, direction=direction,
                    origin=origin.db.ox_space_id,
                    destination=dest.db.ox_space_id, seconds=duration,
                    request_id=request_id)
        except RescueError as exc:
            raise PhysicsError(str(exc)) from exc
        d["rescue"] = rescue
        clock.details = d
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        item = clock
    elif action == "weld":
        # An existing powered welding controller is not evidence of a joint:
        # source stock, actual original part, qualified attending crew and
        # finite physical arc work must be present.
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        ledger = d.get("welding")
        water = d.get("water")
        repairs = d.get("repairs")
        if ledger is None or water is None or repairs is None:
            raise PhysicsError("Real welding, material survey and spares not commissioned")
        room = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        _crew_at(actor, room)
        if (getattr(actor.db, "crew_role", None) not in {
                "chief_engineer", "watch_engineer"} and
                not actor.check_permstring("Developer")):
            raise PermissionError("Weldment requires a qualified, physically attending engineer")
        hp = CanonicalShipState.objects.filter(
            pk="crew_health:" + actor.dbref, source_model=MODEL).first()
        if hp is not None and hp.condition not in {"fit", "impaired"}:
            raise PhysicsError("Incapacitated engineer cannot perform hot welding")
        zone = _topology()[0].get(room)
        if not zone or not zone.startswith("PZ-") or not _air_safe(
                state("pressure", zone)):
            raise PhysicsError("Actual weld worksite requires safe commissioned gas")
        import copy
        try:
            if target == "filler" and value.startswith("pickup:"):
                store = state("inventory", "INV-SPARES", lock=True)
                if room not in store.reference.get("location_ids", ()):
                    raise PermissionError("Issue welding filler at original machine stores only")
                mass = float(value.partition(":")[2])
                ledger, remainder = issue_filler(
                    ledger, worker=actor.dbref, room=room, kg=mass,
                    stock_kg=store.quantity * 1000,
                    surveyed_available_kg=water["source_surveys"].get(
                        "INV-SPARES", {}).get(room, 0.0))
                water = copy.deepcopy(water)
                water["source_surveys"]["INV-SPARES"][room] -= mass
                validate_water(water, {
                    key: (remainder if key == "spares" else
                          state("inventory", ident).quantity*1000)
                    for key, ident in (
                        ("normal", "INV-WATER-NORMAL"),
                        ("reserve", "INV-WATER-RESERVE"),
                        ("sanitary", "INV-WASTE-RESIDUE"),
                        ("industrial", "INV-INDUSTRIAL-SCRAP"),
                        ("hazardous", "INV-HAZARDOUS-RESIDUE"),
                        ("filter", "INV-DC-CONSUMABLES"),
                        ("spares", "INV-SPARES"))})
                old_store = _snapshot(store)
                store.quantity = remainder / 1000
                store.revision += 1
                store.save(update_fields=["quantity", "revision"])
                _event(store, "g19_welding_filler_issued", old_store, actor=actor)
            elif target in WELDING_CELLS and value.startswith("start:"):
                if room != WELDING_ROOM:
                    raise PermissionError("Actual welding cell in SHOP-WELD only")
                machine = state("equipment", target, lock=True)
                if machine.space_id != room or machine.condition in _BROKEN:
                    raise PhysicsError("Welding equipment damaged or not installed here")
                machines = {r.source_id: r for r in
                            CanonicalShipState.objects.filter(category="equipment")}
                edges = list(CanonicalShipState.objects.filter(category="edge"))
                contacts = {r.source_id: r for r in
                            CanonicalShipState.objects.filter(category="isolator")}
                supply = _power(
                    machines, edges, contacts, d["load_profile"],
                    ledger=d.get("electrical"),
                    moored=contacts_active(d.get("cargo", {})))
                service = d.get("service_operations")
                if (service is None or not supply["assured"]
                        or target not in service["last"]["operating"]
                        or not service_power(
                            target, nodes=supply["nodes"], equipment=machines,
                            edges={row.source_id: row for row in edges},
                            switches=contacts)):
                    raise PhysicsError("No actual live weld-cell motor and current local supply")
                fields = value.split(":")
                if len(fields) != 3:
                    raise WeldError("Weld requires start:<base-kg>:<filler-kg>")
                ledger, repairs = start_weld(
                    ledger, repairs, worker=actor.dbref, machine=target,
                    base_kg=float(fields[1]), filler_kg=float(fields[2]),
                    request_id=request_id)
            elif target == "slag" and value.startswith("pickup:"):
                if room != WELDING_ROOM:
                    raise PermissionError("Weld slag must be collected at SHOP-WELD")
                ledger = take_slag(
                    ledger, worker=actor.dbref,
                    kg=float(value.partition(":")[2]))
            elif target in {"IND-SCRAP-HOLD-A", "IND-SCRAP-HOLD-B"} and value.startswith("deposit:"):
                receiver = state("equipment", target, lock=True)
                if room != receiver.space_id or receiver.condition in _BROKEN:
                    raise PermissionError("Weld slag must arrive at real industrial waste receiver")
                if target in water["waste_offload"]["jobs"]:
                    raise PhysicsError("Original sealed receiver reserved for waste port")
                store = state("inventory", "INV-INDUSTRIAL-SCRAP", lock=True)
                balances = {
                    key: state("inventory", ident).quantity*1000
                    for key, ident in (
                        ("normal", "INV-WATER-NORMAL"),
                        ("reserve", "INV-WATER-RESERVE"),
                        ("sanitary", "INV-WASTE-RESIDUE"),
                        ("industrial", "INV-INDUSTRIAL-SCRAP"),
                        ("hazardous", "INV-HAZARDOUS-RESIDUE"),
                        ("filter", "INV-DC-CONSUMABLES"),
                        ("spares", "INV-SPARES"))}
                ledger, water, new_balances = deposit_slag(
                    ledger, water, balances, worker=actor.dbref,
                    kg=float(value.partition(":")[2]), side=target[-1],
                    receiver_ready=True)
                old_store = _snapshot(store)
                store.quantity = new_balances["industrial"]/1000
                store.revision += 1
                store.save(update_fields=["quantity", "revision"])
                _event(store, "g19_real_weld_slag_deposited_to_cassette",
                       old_store, actor=actor)
            else:
                raise PhysicsError("Use weld filler pickup:<kg>, WELD-CELL start:<base>:<filler>, slag pickup:<kg>, or receiver deposit:<kg>")
        except (WeldError, WaterError, ValueError, TypeError) as exc:
            raise PhysicsError(str(exc)) from exc
        validate_welding(ledger)
        validate_repairs(repairs)
        d["welding"] = ledger
        d["water"] = water
        d["repairs"] = repairs
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "fabricate":
        # No globally accessible fabrication button: the current actor must
        # personally issue surveyed source blanks, operate the original shop,
        # or hand-carry offcuts into an authentic sealed waste receiver.
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        fab = d.get("fabrication")
        wet = d.get("water")
        repairs = d.get("repairs")
        if fab is None or wet is None or repairs is None:
            raise PhysicsError("No commissioned physically stocked workshop")
        room = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        _crew_at(actor, room)
        role = getattr(actor.db, "crew_role", None)
        if role not in {"chief_engineer", "watch_engineer"} and not actor.check_permstring("Developer"):
            raise PermissionError("Machining requires trained ship engineers")
        hp = CanonicalShipState.objects.filter(
            pk="crew_health:" + actor.dbref, source_model=MODEL).first()
        if hp is not None and hp.condition not in {"fit", "impaired"}:
            raise PhysicsError("Physically incapable machine-shop worker")
        zone = _topology()[0].get(room)
        if (zone is None or not zone.startswith("PZ-")
                or not _air_safe(state("pressure", zone))):
            raise PhysicsError("Workshop crew needs breathable real compartment air")
        import copy
        try:
            if target == "blank" and value.startswith("pickup:"):
                stock = state("inventory", "INV-SPARES", lock=True)
                if room not in stock.reference.get("location_ids", ()):
                    raise PermissionError("Raw workpieces only at original material stores")
                amount = float(value.partition(":")[2])
                fab, remaining = pick_blank(
                    fab, actor=actor.dbref, room=room, kg=amount,
                    stock_kg=stock.quantity * 1000,
                    surveyed_available_kg=wet["source_surveys"].get(
                        "INV-SPARES", {}).get(room, 0.0))
                wet = copy.deepcopy(wet)
                wet["source_surveys"]["INV-SPARES"][room] -= amount
                available = {
                    "normal": state("inventory", "INV-WATER-NORMAL").quantity * 1000,
                    "reserve": state("inventory", "INV-WATER-RESERVE").quantity * 1000,
                    "sanitary": state("inventory", "INV-WASTE-RESIDUE").quantity * 1000,
                    "industrial": state("inventory", "INV-INDUSTRIAL-SCRAP").quantity * 1000,
                    "hazardous": state("inventory", "INV-HAZARDOUS-RESIDUE").quantity * 1000,
                    "filter": state("inventory", "INV-DC-CONSUMABLES").quantity * 1000,
                    "spares": remaining}
                validate_water(wet, available)
                old_stock = _snapshot(stock)
                stock.quantity = remaining / 1000.0
                stock.revision += 1
                stock.save(update_fields=["quantity", "revision"])
                _event(stock, "machinable_blank_hand_issued", old_stock, actor=actor)
            elif target in FABRICATION_MACHINES and value.startswith("start:"):
                if room != FABRICATION_ROOM:
                    raise PermissionError("Machining only at existing SHOP-MECH")
                machine = state("equipment", target, lock=True)
                if machine.space_id != room or machine.condition in _BROKEN:
                    raise PhysicsError("Original spindle machinery is damaged")
                # The spindle needs genuine running power before productive
                # work can start. This never overrides the plant start command.
                units = {row.source_id: row for row in
                         CanonicalShipState.objects.filter(category="equipment")}
                edges = list(CanonicalShipState.objects.filter(category="edge"))
                isolators = {row.source_id: row for row in
                             CanonicalShipState.objects.filter(category="isolator")}
                supply = _power(units, edges, isolators,
                                d["load_profile"], ledger=d.get("electrical"),
                                moored=contacts_active(d.get("cargo", {})))
                svc = d.get("service_operations")
                if (not supply["assured"] or svc is None or
                        target not in svc["last"]["operating"] or
                        not service_power(
                            target, nodes=supply["nodes"], equipment=units,
                            edges={edge.source_id: edge for edge in edges},
                            switches=isolators)):
                    raise PhysicsError("Spindle must have real operating service and dedicated live feeder")
                gauge = machine.details.get(GAUGE_FIELD) or {}
                fab = start_batch(
                    fab, actor=actor.dbref, machine=target,
                    kg=float(value.partition(":")[2]),
                    request_id=request_id,
                    previous_output=gauge.get("cumulative_output", 0.0),
                    current_repair_kg=repairs["carried_kg"].get(actor.dbref, 0.0))
            elif target == "offcuts" and value.startswith("pickup:"):
                if room != FABRICATION_ROOM:
                    raise PermissionError("Collect chips at the actual workshop")
                fab = take_offcuts(
                    fab, actor=actor.dbref,
                    kg=float(value.partition(":")[2]))
            elif target in {"IND-SCRAP-HOLD-A", "IND-SCRAP-HOLD-B"} and value.startswith("deposit:"):
                receiver = state("equipment", target, lock=True)
                if room != receiver.space_id or receiver.condition in _BROKEN:
                    raise PermissionError("Carry chips to the real sound industrial receiver")
                if target in wet["waste_offload"]["jobs"]:
                    raise PhysicsError("Receiver currently reserved for port offload")
                stock = state("inventory", "INV-INDUSTRIAL-SCRAP", lock=True)
                balances = {
                    "normal": state("inventory", "INV-WATER-NORMAL").quantity * 1000,
                    "reserve": state("inventory", "INV-WATER-RESERVE").quantity * 1000,
                    "sanitary": state("inventory", "INV-WASTE-RESIDUE").quantity * 1000,
                    "industrial": stock.quantity * 1000,
                    "hazardous": state("inventory", "INV-HAZARDOUS-RESIDUE").quantity * 1000,
                    "filter": state("inventory", "INV-DC-CONSUMABLES").quantity * 1000,
                    "spares": state("inventory", "INV-SPARES").quantity * 1000,
                }
                fab, wet, new_stocks = deposit_offcuts(
                    fab, wet, balances, actor=actor.dbref,
                    kg=float(value.partition(":")[2]), side=target[-1],
                    receiver_ready=(receiver.condition not in _BROKEN))
                old_stock = _snapshot(stock)
                stock.quantity = new_stocks["industrial"] / 1000.0
                stock.revision += 1
                stock.save(update_fields=["quantity", "revision"])
                _event(stock, "attended_shop_offcuts_to_real_waste_cassette",
                       old_stock, actor=actor)
            else:
                raise PhysicsError("Use blank pickup:<kg>, machine start:<kg>, offcuts pickup:<kg> or receiver deposit:<kg>")
        except (FabricationError, WaterError, TypeError, ValueError) as exc:
            raise PhysicsError(str(exc)) from exc
        validate_fabrication(fab)
        validate_repairs(repairs)
        d["fabrication"] = fab
        d["water"] = wet
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "medical":
        # Individual medical work order. The pharmacy and treatment rooms
        # are physically distinct, so kit pickup/delivery requires movement.
        clock = _clock(lock=True)
        d = dict(clock.details)
        medical = d.get("medical")
        if medical is None:
            raise PhysicsError("HAB-04 first aid has not been commissioned")
        validate_medical(medical)
        room = getattr(getattr(actor, "location", None), "db", None)
        room_id = getattr(room, "ox_space_id", None)
        if getattr(actor.db, "crew_role", None) not in MEDICAL_ROLES:
            raise PermissionError("Only trained ship medical staff may treat casualties")
        own = CanonicalShipState.objects.filter(
            pk="crew_health:" + actor.dbref, source_model=MODEL).first()
        if own and own.condition not in {"fit", "impaired"}:
            raise PhysicsError("Disabled caregiver cannot attend patient")
        before = _snapshot(clock)
        try:
            if target == "kit":
                if value.startswith("pickup:"):
                    if room_id != PHARMACY_ROOM:
                        raise PermissionError("Pick up existing stock at the pharmacy")
                    count = int(value.split(":", 1)[1])
                    medical = carry_medical_kit(
                        medical, actor=actor.dbref, verb="pickup", cases=count)
                elif value == "deliver":
                    if room_id not in {TREATMENT_ROOM, OBSERVATION_ROOM}:
                        raise PermissionError("Deliver supplies inside real HAB-04 treatment or observation")
                    medical = carry_medical_kit(
                        medical, actor=actor.dbref, verb="deliver",
                        destination=room_id)
                else:
                    raise PhysicsError("Use kit pickup:<cases> or deliver")
            elif target in {"care", "observe", "discharge"}:
                if not re.fullmatch(r"#[0-9]+", value):
                    raise PhysicsError("Care target is the patient's real dbref")
                from evennia.objects.models import ObjectDB
                patient = ObjectDB.objects.filter(id=int(value[1:])).first()
                actual_room = (TREATMENT_ROOM if target == "care"
                               else room_id)
                if (patient is None or
                        actual_room not in {TREATMENT_ROOM, OBSERVATION_ROOM}
                        or (target == "care" and room_id != TREATMENT_ROOM)
                        or (getattr(getattr(patient, "location", None), "db", None)
                            is None or patient.location.db.ox_space_id != actual_room)):
                    raise PermissionError("Patient and attendant must share actual clinical worksite")
                hp = CanonicalShipState.objects.filter(
                    pk="crew_health:" + value, source_model=MODEL).first()
                if hp is None:
                    raise PhysicsError("Patient has no registered measured injury")
                powered, breathable = _medical_power_and_air(
                    clock_details=d, room=actual_room)
                if target == "care":
                    medical = begin_care(
                        medical, patient=value, caregiver=actor.dbref,
                        health=hp.details, patient_room=TREATMENT_ROOM,
                        caregiver_room=room_id, equipment_ok=powered,
                        breathable=breathable)
                elif target == "observe":
                    medical = begin_observation(
                        medical, patient=value, caregiver=actor.dbref,
                        health=hp.details, patient_room=actual_room,
                        caregiver_room=room_id, equipment_ok=powered,
                        breathable=breathable)
                else:
                    if (medical.get("observations", {}).get(value, {}).get(
                            "room", TREATMENT_ROOM) != room_id):
                        raise PermissionError("Discharge requires attendance at this patient's actual room")
                    medical = discharge_observation(
                        medical, patient=value, caregiver=actor.dbref)
            else:
                raise PhysicsError("Use physical medical kit, care, observe or discharge")
        except (MedicalError, ValueError) as exc:
            raise PhysicsError(str(exc)) from exc
        d["medical"] = medical
        clock.details = d
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        item = clock
    elif action == "hull":
        # This is a real two-stage service order, not a pressure reset. Every
        # gram of repair stock was first issued at the original stores.
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        hull = d.get("hull")
        repairs = d.get("repairs")
        if hull is None or repairs is None:
            raise PhysicsError("Hull and shared spares are not commissioned")
        try:
            validate_hull(hull)
        except HullError as exc:
            raise PhysicsError(str(exc)) from exc
        breach = hull["breaches"].get(target)
        if not breach:
            raise PhysicsError("No installed hull breach at this pressure cell")
        room = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        major = (d.get("major_damage") or {}).get("sites", {}).get(target)
        if major is None:
            _crew_at(actor, breach["site_room"])
            if (room != breach["site_room"]
                    or _topology()[0].get(room) != target):
                raise PermissionError("Crew not at the surveyed physical hull repair face")
        else:
            _crew_at(actor, major["external_face"])
            eva_state = d.get("eva")
            if eva_state is None:
                raise PhysicsError("External repair requires commissioned fitted EVA")
            _, suit = suit_of(eva_state, actor.dbref)
            closed = {
                door_id for door_id in major["boundaries"]
                if (state("access", door_id).condition not in _BROKEN
                    and state("access", door_id).setting == "closed")
            }
            if not external_repair_ready(
                    d["major_damage"], zone=target, room=room,
                    suit_valid=bool(suit and suit["integrity"] >= .8
                                    and suit["exposure"]["suit_oxygen_kg"] > 0
                                    and suit["exposure"]["condition"] not in {
                                        "incapacitated", "critical", "dead"}),
                    actual_closed_boundaries=closed):
                raise PhysicsError("Unsealed major breach or unprotected exterior repair face")
        cell = state("pressure", target, lock=True)
        if (major is None and not _hull_repair_air_safe(cell)
                or not math.isclose(cell.details.get("physics_leak_kg_s", -1),
                                 effective_leak(breach), rel_tol=0, abs_tol=1e-7)):
            raise PhysicsError("Hull site unsafe or breach and pressure state disagree")
        phase = expected_repair_condition(hull, target)
        work_key = "hull:" + target
        try:
            if value in {"patch", "restore"}:
                if (value == "patch" and phase != "jammed"
                        or value == "restore" and phase != "severed"):
                    raise HullError("Hull work sequence invalid; patch before permanent restoration")
                repairs = begin_repair(
                    repairs, target=work_key, room=room,
                    actor_dbref=actor.dbref, condition=phase)
            elif value == "join":
                active = repairs["jobs"].get(work_key)
                if not active or active["condition"] != phase:
                    raise HullError("No active matching hull repair order")
                repairs = join_repair(
                    repairs, target=work_key, actor_dbref=actor.dbref, room=room)
            else:
                raise HullError("Hull operation requires patch, restore or join")
        except (WaterError, HullError) as exc:
            raise PhysicsError(str(exc)) from exc
        d["repairs"] = repairs
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])



    elif action == "fault":
        if target not in set(MOTORS) | set(SERVICE_LOADS):
            raise PhysicsError("No individually fitted machine circuit")
        machine = state("equipment", target, lock=True)
        _crew_at(actor, machine.space_id)
        if (getattr(actor.db, "crew_role", None) not in AUTHORISED_ROLES
                and not actor.check_permstring("Developer")):
            raise PermissionError("Qualified engineering duty required for diagnostic permit")
        _food_at(actor, machine.space_id)
        if _clock().details.get("electrical") is None:
            raise PhysicsError("Individual machinery circuits not commissioned")
        _electrical_crew_air_gate(
            actor, machine.space_id, _clock().details["electrical"])
        clock = _clock(lock=True)
        before = _snapshot(clock)
        d = dict(clock.details)
        ledger = d.get("fault_cases") or initial_fault_cases()
        validate_fault_cases(ledger)
        feeders = {key: state("isolator", key, lock=True)
                   for key in feeders_for(target)}
        opened = verified_open_feeders(target, feeders)
        tripped = any(x.details.get("physics_power_trip_latched")
                      for x in feeders.values())
        stopped = (not any(machine.details.get(k) for k in (
            "physics_online", "physics_commanded_on", "physics_startup_s"))
            and machine_safely_stopped(target, machine.details)
            and machine_depressurized(target, machine.details))
        active = "equipment:" + target in (d.get("repairs") or {"jobs": {}})["jobs"]
        now = d["last_game_time"]
        stamp = machine.details.get("repair_completed_game_time")
        stock = machine.details.get("repair_cumulative_kg", 0.0)
        ins = d.get("instrumentation")
        panel = next((p for p, row in ins["panels"].items()
                      if row["room"] == machine.space_id), None) if ins else None
        alarm = next((k for k, a in ins["alarms"].items()
                      if a["panel"] == panel and a["subject"] == target
                      and a["active"]), None) if ins and panel else None
        try:
            if value == "inspect":
                svc = d.get("service_operations")
                restart = bool(svc and target in SERVICE_LOADS
                               and svc["units"][target]["restart_latched"])
                ledger = inspect_fault(ledger, target, room=machine.space_id,
                    actor=actor.dbref, now_s=now, condition=machine.condition,
                    revision=machine.revision, repair_stamp=stamp,
                    cumulative_spares_kg=stock, feeder_tripped=tripped,
                    restart_latched=restart, alarm=alarm,
                    panel=panel if alarm else None)
            elif value == "isolate":
                ledger = isolate_fault(ledger, target, actor=actor.dbref,
                    now_s=now, open_feeders=opened, stopped=stopped,
                    worksite_safe=not active)
            elif value == "check":
                ledger = check_repair(ledger, target, actor=actor.dbref,
                    now_s=now, condition=machine.condition,
                    open_feeders=opened, stopped=stopped, tripped=tripped,
                    active_work=active, repair_stamp=stamp,
                    cumulative_spares_kg=stock)
            elif value in {"authorize", "verify"}:
                if not ins or not panel:
                    raise FaultRecoveryError("Original local sensor panel required")
                p = ins["panels"][panel]
                panel_ok = p["status"] == "online" and p["last_good_s"] == now
                signal_quality_clear = not any(
                    a["panel"] == panel and a["active"] and a["code"] in {
                        "INSTRUMENT_LOST", "INSTRUMENT_UNRELIABLE"}
                    for a in ins["alarms"].values())
                units = {x.source_id: x for x in
                         CanonicalShipState.objects.filter(category="equipment")}
                edges = {x.source_id: x for x in
                         CanonicalShipState.objects.filter(category="edge")}
                switches = {x.source_id: x for x in
                            CanonicalShipState.objects.filter(category="isolator")}
                power = _power(units, list(edges.values()), switches,
                    d["load_profile"], ledger=d.get("electrical"),
                    moored=contacts_active(d["cargo"]))
                live = (
                    fire_pump_service_ready(
                        target, nodes=power["nodes"], equipment=units,
                        edges=edges, switches=switches,
                        normal_assured=power["assured"],
                        protected_assured=power["protected_assured"])
                    if target in PROTECTED_FIRE_MOTORS else
                    bool(power["assured"] and (
                        service_power(target, nodes=power["nodes"],
                            equipment=units, edges=edges, switches=switches)
                        if target in SERVICE_LOADS else
                        motor_power(target, nodes=power["nodes"],
                            equipment=units, edges=edges, switches=switches))))
                if value == "authorize":
                    case = ledger["cases"].get(target)
                    if case and case["stage"] == "checked" and not (
                            verified_restored_feeders(
                                target, feeders, checked_s=case["checked_s"],
                                last_good_s=p["last_good_s"])):
                        raise FaultRecoveryError(
                            "All genuine breakers must be manually reclosed "
                            "and the local panel sampled after reconnection")
                    ledger = authorize_restart(ledger, target, actor=actor.dbref,
                        now_s=now, sample_count=ins["sample_count"],
                        sound_hardware=(machine.condition == "serviceable"
                                        and panel_ok and signal_quality_clear),
                        live_feeder=live, tripped=tripped, active_work=active)
                else:
                    ledger = verify_restart(ledger, target, actor=actor.dbref,
                        now_s=now, sample_count=ins["sample_count"],
                        running=bool(
                            machine.details.get("physics_online")
                            if target not in WATER_MACHINES + BEARING_PUMPS
                            else proves_process_output(
                                target, machine.details, observed_s=now)),
                        live_feeder=live, condition=machine.condition,
                        tripped=tripped, panel_live=panel_ok,
                        signal_quality_clear=signal_quality_clear,
                        alarm_active=any(a["active"] and a["subject"] == target
                                         for a in ins["alarms"].values()
                                         if a["panel"] == panel))
            else:
                raise FaultRecoveryError("Inspect, isolate, check, authorize or verify")
        except FaultRecoveryError as exc:
            raise PhysicsError(str(exc)) from exc
        d["fault_cases"] = ledger
        clock.details = d
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        item = clock

    elif action == "instrument":
        # Human attention to one real powered panel. This cannot repair,
        # isolate, suppress, energize or falsify the sensed fault.
        clock = _clock(lock=True)
        before = _snapshot(clock)
        d = dict(clock.details)
        ledger = d.get("instrumentation")
        if ledger is None:
            raise PhysicsError("Original 116-panel instrumentation not commissioned")
        _food_at(actor, ledger["panels"].get(target, {}).get("room"))
        here = getattr(getattr(actor.location, "db", None), "ox_space_id", None)
        _instrument_local_panel(actor, target, here, ledger)
        if value == "test":
            # Live panel condition/power are checked, but no fresh gas value
            # or automatic recovery is fabricated by a self-test.
            current_grid, _ = _instrument_power_grid(d)
            actual_panel = state("equipment", target, lock=True)
            try:
                selftest_evidence = panel_selftest(
                    ledger, target, now_s=d["last_game_time"],
                    condition=actual_panel.condition,
                    powered=("NODE-" + target in current_grid["nodes"]))
            except InstrumentError as exc:
                raise PhysicsError(str(exc)) from exc
        elif isinstance(value, str) and value.startswith("ack:"):
            key = value[4:]
            try:
                ledger = acknowledge_alarm(
                    ledger, target, key, actor=actor.dbref,
                    now_s=d["last_game_time"])
            except InstrumentError as exc:
                raise PhysicsError(str(exc)) from exc
        else:
            raise PhysicsError("Only real panel self-test or local alarm acknowledge")
        d["instrumentation"] = ledger
        clock.details = d
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        item = clock

    elif action == "food":
        # Every parcel is picked up, carried through *actual* ship exits and
        # delivered at a real food/galley/grow/sanitation worksite. No global
        # inventory teleport, automatic meal production or free nutrient refill.
        normal_site = target in (
            set(FOOD_STORES) | set(NUTRIENT_STORES) |
            set(GROW_BAYS.values()) |
            {FOOD_GALLEY, FOOD_MESS} | set(FOOD_WASTE_RECEIVERS))
        feed_site = (isinstance(value, str) and value.startswith("feed:")
                     and target in _topology()[0]
                     and _topology()[0][target] not in {None, "VACUUM"})
        if not (normal_site or feed_site):
            raise PhysicsError("Food operation requires a real attended ship space")
        _food_at(actor, target)
        zone = _topology()[0].get(target)
        if not zone or not _air_safe(state("pressure", zone, lock=True)):
            raise PhysicsError("Food handling requires safe surveyed local air")
        item = _clock(lock=True)
        before = _snapshot(item)
        import copy
        d = dict(item.details)
        food = d.get("food")
        if food is None:
            raise PhysicsError("Original finite food stores not commissioned")
        manifest = state("inventory", "INV-FOOD-LONG-LEG", lock=True)
        try:
            validate_food(food, inventory_kg=manifest.quantity * 1000.0)
        except FoodError as exc:
            raise PhysicsError(str(exc)) from exc
        food = copy.deepcopy(food)
        parts = value.split(":") if isinstance(value, str) else []
        kitchen_water = d.get("water")
        store_water = None
        crop = d.get("cultivation")
        inventories = {}
        if not parts:
            raise PhysicsError("Food operation must identify a physical task")
        try:
            if parts[0] == "take" and len(parts) == 3:
                food = take_stored(
                    food, actor=actor.dbref, room=target,
                    kind=parts[1], kg=float(parts[2]))
            elif parts[0] == "crop" and len(parts) == 2:
                if crop is None:
                    raise FoodError("Growing beds not commissioned")
                bay = next((i for i, r in GROW_BAYS.items() if r == target), None)
                food, crop = collect_crop(
                    food, crop, actor=actor.dbref, bay=bay,
                    kg=float(parts[1]))
                d["cultivation"] = crop
            elif parts == ["deliver"] and target == FOOD_GALLEY:
                food = deliver_to_galley(food, actor=actor.dbref)
            elif parts[0] == "cook" and len(parts) == 2 and target == FOOD_GALLEY:
                if kitchen_water is None or d.get("electrical") is None:
                    raise FoodError("Kitchen has no commissioned water and electrical services")
                machine = state("equipment", "HAB-02-GALLEY-LP")
                machines = {x.source_id: x for x in CanonicalShipState.objects.filter(
                    category="equipment")}
                feeds = list(CanonicalShipState.objects.filter(category="edge"))
                contacts = {x.source_id: x for x in CanonicalShipState.objects.filter(
                    category="isolator")}
                nodes = list(CanonicalShipState.objects.filter(category="node"))
                grid = _power(machines, feeds, contacts, d["load_profile"],
                              ledger=d["electrical"],
                              moored=contacts_active(d["cargo"]), nodes=nodes)
                auxiliary = {e.source_id: e for e in feeds if
                             e.reference.get("network") in {
                                 "g19_motor", "g19_motor_protected"}}
                plant = _water_hardware(
                    kitchen_water, machines, feeds, contacts, nodes, grid,
                    motor_ready=lambda name: motor_power(
                        name, nodes=grid["nodes"], equipment=machines,
                        edges=auxiliary, switches=contacts))
                if (machine.condition in _BROKEN or
                        not grid["assured"] or
                        "NODE-HAB-02-GALLEY-LP" not in grid["nodes"] or
                        not plant["potable"] or kitchen_water["potable_quarantined"]):
                    raise FoodError("Galley loses actual electrical or potable process service")
                if parts[1] not in FOOD_RECIPES:
                    raise FoodError("Unknown galley recipe")
                demanded = FOOD_RECIPES[parts[1]]["water"]
                if kitchen_water["working_kg"] + 1e-7 < demanded:
                    raise FoodError("Insufficient measured potable tank water")
                food = prepare_meal(
                    food, recipe=parts[1], water_delivered_kg=demanded)
                w = copy.deepcopy(kitchen_water)
                w["working_kg"] -= demanded
                w["cumulative"]["technical_kg"] += demanded
                water_stocks = {
                    "normal": "INV-WATER-NORMAL",
                    "reserve": "INV-WATER-RESERVE",
                    "filter": "INV-DC-CONSUMABLES",
                    "spares": "INV-SPARES",
                    "sanitary": "INV-WASTE-RESIDUE",
                    "industrial": "INV-INDUSTRIAL-SCRAP",
                    "hazardous": "INV-HAZARDOUS-RESIDUE",
                }
                amounts = {k: state("inventory", v, lock=True).quantity * 1000.0
                           for k, v in water_stocks.items()}
                validate_water(w, amounts)
                d["water"] = w
            elif parts == ["meal_take"] and target == FOOD_GALLEY:
                food = take_meal(food, actor=actor.dbref)
            elif parts == ["meal_serve"] and target == FOOD_MESS:
                food = set_meal_in_mess(food, actor=actor.dbref)
            elif parts == ["eat"] and target in {FOOD_GALLEY, FOOD_MESS}:
                if not CanonicalShipState.objects.filter(
                        pk="crew_health:" + actor.dbref,
                        source_model=MODEL).exists():
                    raise FoodError("Only physically enrolled crew may consume ship provisions")
                food, _calories = eat_meal(food, actor=actor.dbref, room=target)
            elif parts[0] == "feed" and len(parts) == 2:
                # Feed a real patient at their actual position. The helper
                # brings a prepared meal, never a remote inventory credit.
                from evennia.objects.models import ObjectDB as PatientObjectDB
                patient_ref = parts[1]
                if re.fullmatch(r"#[0-9]+", patient_ref) is None:
                    raise FoodError("Assisted feeding requires a real patient dbref")
                patient = PatientObjectDB.objects.filter(
                    id=int(patient_ref[1:])).first()
                patient_health = CanonicalShipState.objects.filter(
                    pk="crew_health:" + patient_ref,
                    source_model=MODEL).first()
                if (patient is None or patient.location != actor.location
                        or patient_health is None
                        or patient_health.condition == "dead"
                        or getattr(patient.db, "ox_terminal_dead", False)):
                    raise FoodError("Only a living enrolled patient here can be fed")
                food, _calories = feed_patient(
                    food, attendant=actor.dbref, patient=patient_ref)
            elif parts[0] == "waste_take" and len(parts) == 2:
                food = take_waste(food, actor=actor.dbref, room=target,
                                  kg=float(parts[1]))
            elif parts[0] == "waste_deposit" and len(parts) == 2:
                if target not in FOOD_WASTE_RECEIVERS or kitchen_water is None:
                    raise FoodError("No original food-sanitation receiving station")
                from world.ship_water_recycling import _fill_cassette
                kg = float(parts[1])
                food = deliver_waste(food, actor=actor.dbref, kg=kg)
                machines = {x.source_id: x for x in CanonicalShipState.objects.filter(
                    category="equipment")}
                feeds = list(CanonicalShipState.objects.filter(category="edge"))
                contacts = {x.source_id: x for x in CanonicalShipState.objects.filter(
                    category="isolator")}
                nodes = list(CanonicalShipState.objects.filter(category="node"))
                grid = _power(machines, feeds, contacts, d["load_profile"],
                              ledger=d.get("electrical"),
                              moored=contacts_active(d["cargo"]), nodes=nodes)
                plant = _water_hardware(
                    kitchen_water, machines, feeds, contacts, nodes, grid)
                side = FOOD_WASTE_RECEIVERS[target]
                if not plant["bins"]["sanitary"][side]:
                    raise FoodError("Original sanitary receiver damaged, unsealed or isolated")
                receiver = {"sanitary": {"A": False, "B": False}}
                receiver["sanitary"][side] = True
                w = copy.deepcopy(kitchen_water)
                _fill_cassette(w, "sanitary", kg, {"bins": receiver})
                sanitary = state("inventory", "INV-WASTE-RESIDUE", lock=True)
                sanitary.quantity += kg / 1000.0
                sanitary.revision += 1
                sanitary.save(update_fields=["quantity", "revision"])
                source_stock = {
                    "normal": "INV-WATER-NORMAL",
                    "reserve": "INV-WATER-RESERVE",
                    "filter": "INV-DC-CONSUMABLES",
                    "spares": "INV-SPARES",
                    "sanitary": "INV-WASTE-RESIDUE",
                    "industrial": "INV-INDUSTRIAL-SCRAP",
                    "hazardous": "INV-HAZARDOUS-RESIDUE",
                }
                validate_water(w, {
                    key: state("inventory", inventory_id, lock=True).quantity * 1000.0
                    for key, inventory_id in source_stock.items()
                })
                d["water"] = w
            elif parts[0] == "nutrient_take" and len(parts) == 2:
                if target not in NUTRIENT_STORES or kitchen_water is None:
                    raise FoodError("No original nutrient-compatible spare rack")
                spares = state("inventory", "INV-SPARES", lock=True)
                w = copy.deepcopy(kitchen_water)
                available = w["source_surveys"].get(
                    "INV-SPARES", {}).get(target, 0.0)
                kg = float(parts[1])
                food = take_nutrients(food, actor=actor.dbref,
                                      room=target, kg=kg,
                                      available_kg=min(available, spares.quantity * 1000.0))
                w["source_surveys"]["INV-SPARES"][target] -= kg
                spares.quantity -= kg / 1000.0
                spares.revision += 1
                spares.save(update_fields=["quantity", "revision"])
                d["water"] = w
            elif parts[0] == "nutrient_install" and len(parts) == 2:
                if crop is None:
                    raise FoodError("No fitted cultivated bed has been commissioned")
                bay = next((i for i, r in GROW_BAYS.items() if r == target), None)
                kg = float(parts[1])
                crop = replenish_nutrients(crop, bay=bay, kg=kg)
                food = install_nutrients(food, actor=actor.dbref, kg=kg)
                d["cultivation"] = crop
            else:
                raise FoodError("Unknown local food transfer, recipe or waste operation")
            # Reconcile EVERY food operation against the same source inventory.
            validate_food(food)
        except (FoodError, CultivationError, WaterError, TypeError, ValueError) as exc:
            raise PhysicsError(str(exc)) from exc
        remaining = unconsumed_stored_kg(food)
        if abs(remaining - manifest.quantity * 1000.0) > 1e-9:
            manifest.quantity = remaining / 1000.0
            manifest.revision += 1
            manifest.save(update_fields=["quantity", "revision"])
        validate_food(food, inventory_kg=manifest.quantity * 1000.0)
        d["food"] = food
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])

    elif action == "cultivation":
        if target not in {f"GROW-{n}" for n in GROW_BAYS} or value != "harvest":
            raise PhysicsError("Only physical harvest at the three fitted grow bays is supported")
        bay = int(target[-1])
        room = GROW_BAYS[bay]
        _crew_at(actor, room)
        if not _air_safe(state("pressure", _topology()[0][room])):
            raise PhysicsError("Unsafe room atmosphere for attended food handling")
        clock = _clock(lock=True)
        cultivation = clock.details.get("cultivation")
        if cultivation is None:
            raise PhysicsError("Original hydroponics not commissioned")
        try:
            cultivation, collected = harvest_cultivation(cultivation, bay=bay)
        except CultivationError as exc:
            raise PhysicsError(str(exc)) from exc
        before = _snapshot(clock)
        details = dict(clock.details)
        details["cultivation"] = cultivation
        clock.details = details
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        item = clock
    elif action == "propulsion_service":
        # v0.5 has an exterior platform, but no separately identifiable
        # external nozzle machine. Only a suited inspection is admissible.
        if target != PROPULSION_FACE or value not in {
                "secure", "inspect", "release"}:
            raise PhysicsError("Only the original EXT-PROP-AFT inspection face is fitted")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        ledger = d.get("propulsion_exterior")
        if ledger is None:
            raise PhysicsError("Original aft workface not commissioned")
        equipment_here = {row.source_id: row for row in
                          CanonicalShipState.objects.filter(category="equipment")}
        sound = all(name in equipment_here and
                    equipment_here[name].condition not in _BROKEN
                    for name in ("LP-PROP-CTRL", "LCS-PROP", "EVA-WORK-PLATFORM"))
        try:
            if value == "secure":
                _crew_at(actor, PROPULSION_STATION)
                if not sound or not propulsion_face_safe(
                        ledger, motion=d["motion"], hardware_ready=sound):
                    raise PhysicsError("Propulsion/RCS not held, exhaust hot or plume unmeasured")
                ledger = issue_propulsion_permit(
                    ledger, actor=actor.dbref, game_time=d["last_game_time"],
                    motion=d["motion"], hardware_ready=sound)
            elif value == "inspect":
                _crew_at(actor, PROPULSION_FACE)
                if (not _propulsion_exterior_suit_ready(actor, d)
                        or not _propulsion_exterior_ready(d, equipment_here)):
                    raise PhysicsError("Original nozzle inspection requires a living issued-suit worker")
                ledger = inspect_propulsion(
                    ledger, actor=actor.dbref,
                    motion=d["motion"], hardware_ready=sound)
            else:
                _crew_at(actor, PROPULSION_STATION)
                from evennia.objects.models import ObjectDB
                from world.ship_world import find_ship_space
                face = find_ship_space(PROPULSION_FACE)
                occupied = bool(face and any(
                    getattr(person.db, "crew_role", None) for person in
                    ObjectDB.objects.filter(db_location=face)))
                transit = any(
                    job["to"] == PROPULSION_FACE or job["from"] == PROPULSION_FACE
                    for job in (d.get("eva") or
                                {"transits": {}})["transits"].values())
                ledger = release_propulsion_permit(
                    ledger, actor=actor.dbref,
                    occupied=occupied, transit_active=transit)
        except PlumeAccessError as exc:
            raise PhysicsError(str(exc)) from exc
        d["propulsion_exterior"] = ledger
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "radiator_service":
        if target not in EXTERIOR_RADIATORS or value not in {
                "secure", "release"}:
            raise PhysicsError("Only the six fitted radiator work platforms have service permits")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        ledger = d.get("exterior_radiators")
        if ledger is None:
            raise PhysicsError("Original exterior radiator work controller not commissioned")
        spec = EXTERIOR_RADIATORS[target]
        # The original HT valves are remotely operable. Their original
        # THERM-HT machinery room has UNKNOWN breathing atmosphere.
        # Use the installed engineering console; never teleport inside.
        console = ("ENG-CONTROL" if target.startswith("RAD-HT-")
                   else spec["station"])
        _crew_at(actor, console)
        if state("equipment", "LP-" + console).condition in _BROKEN:
            raise PhysicsError("Original radiator control panel unserviceable")
        equipment_here = {row.source_id: row for row in
                          CanonicalShipState.objects.filter(category="equipment")}
        iso_here = {row.source_id: row for row in
                    CanonicalShipState.objects.filter(category="isolator")}
        try:
            if value == "secure":
                if not radiator_face_safe(
                        ledger, target, isolators=iso_here,
                        equipment=equipment_here, motion=d["motion"],
                        rotors=d["rotors"]):
                    raise PhysicsError("Radiator still hot, not isolated, or ship not parked")
                ledger = secure_radiator(
                    ledger, radiator=target, actor=actor.dbref,
                    game_time=d["last_game_time"])
            else:
                from evennia.objects.models import ObjectDB
                from world.ship_world import find_ship_space
                outside = find_ship_space(spec["face"])
                # A fitted room contains exit and fixture objects as well
                # as people. Only actual living crew bodies hold a work face
                # occupied; an exit object must not permanently lock a valve.
                occupied = bool(outside and any(
                    getattr(person.db, "crew_role", None)
                    for person in ObjectDB.objects.filter(db_location=outside)))
                active = any(job["room"] == spec["face"] for job in
                             (d.get("repairs") or {"jobs": {}})["jobs"].values())
                transit = any(job["to"] == spec["face"]
                              or job["from"] == spec["face"]
                              for job in (d.get("eva") or
                                          {"transits": {}})["transits"].values())
                ledger = release_radiator(
                    ledger, radiator=target, actor=actor.dbref,
                    occupied=occupied, repair_active=active,
                    transit_active=transit)
        except ExteriorRadiatorError as exc:
            raise PhysicsError(str(exc)) from exc
        d["exterior_radiators"] = ledger
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "flywheel_service":
        # Per-module stored energy is sourced from the original electrical
        # metering, never inferred from a disconnected module feeder.
        if target not in SERVICE_FLYWHEELS or value not in {
                "lock", "release", "rundown", "halt"}:
            raise PhysicsError("Flywheel service requires fitted module and lock|release|rundown|halt")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        ledger = d.get("flywheel_service")
        if ledger is None:
            raise PhysicsError("As-built F1/F2 module lockout not commissioned")
        room = module_room(target)
        _crew_at(actor, room)
        if not _flywheel_suit_ready(actor, room, d):
            raise PhysicsError("Flywheel module service requires an actual issued suited worker")
        repairs = d.get("repairs")
        if (repairs is None or
                repairs["site_surveys"].get(room) != "suited_service"):
            raise PhysicsError("No operator-attested physical repair worksite")
        module = state("equipment", target, lock=True)
        breaker = state("isolator", module_breaker(target), lock=True)
        if (module.space_id != room or
                (breaker.space_id, breaker.reference.get("network"),
                 breaker.reference.get("kind")) != (room, "power", "breaker")):
            raise PhysicsError("Actual individual F1/F2 module feeder is mismatched")
        import copy
        electrical = copy.deepcopy(d["electrical"])
        try:
            if value == "lock":
                ledger = issue_permit(
                    ledger, module=target, worker=actor.dbref,
                    game_time=d["last_game_time"],
                    electrical=electrical,
                    switches={module_breaker(target): breaker})
            elif value == "release":
                ledger = release_permit(
                    ledger, module=target, worker=actor.dbref,
                    repair_active="equipment:" + target in repairs["jobs"])
            elif value == "rundown":
                store = electrical["flywheels"].get(target)
                if (module.condition in _BROKEN or breaker.condition in _BROKEN
                        or breaker.setting != "closed" or store is None
                        or store["mode"] != "standby"
                        or "equipment:" + target in repairs["jobs"]):
                    raise PhysicsError("Rundown needs an undamaged, connected, surveyed standby rotor")
                from world.ship_flywheel_maintenance import ZERO_KWH
                if store["charge_kwh"] <= ZERO_KWH:
                    raise PhysicsError("No stored spin energy: isolate for maintenance instead")
                # First demonstrate that THIS rotor, not a different
                # generator or bank, can deliver energy to a fitted live
                # ship load in the actual switchboard topology.
                proposed = copy.deepcopy(electrical)
                proposed["flywheels"][target]["mode"] = "discharge"
                physical = _power(
                    {row.source_id: row for row in
                     CanonicalShipState.objects.filter(category="equipment")},
                    list(CanonicalShipState.objects.filter(category="edge")),
                    {row.source_id: row for row in
                     CanonicalShipState.objects.filter(category="isolator")},
                    d["load_profile"], ledger=proposed, dt_s=STEP_SECONDS,
                    moored=contacts_active(d["cargo"]))
                if (not physical["has_live_load"] or
                        not any(name == target and mw > 0 for name, mw in
                                physical["flywheel_sources"])):
                    raise PhysicsError("No real downstream ship load or independent discharge source path")
                ledger = begin_rundown(
                    ledger, module=target, worker=actor.dbref,
                    charge_kwh=store["charge_kwh"],
                    game_time=d["last_game_time"])
                electrical = proposed
            else:
                ledger = halt_rundown(
                    ledger, module=target, worker=actor.dbref)
                electrical["flywheels"][target]["mode"] = "standby"
        except (FlywheelServiceError, ElectricalError) as exc:
            raise PhysicsError(str(exc)) from exc
        validate_electrical(electrical)
        d["electrical"] = electrical
        d["flywheel_service"] = ledger
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "repair":
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        repairs = d.get("repairs")
        water = d.get("water")
        if repairs is None or water is None:
            raise PhysicsError("Shared ship service and physical stock not commissioned")
        import copy
        r = copy.deepcopy(repairs)
        room = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        if target == "TOOL-CRIB":
            _crew_at(actor, "TOOL-CRIB")
            zone = _topology()[0].get("TOOL-CRIB")
            if zone is None or not _air_safe(state("pressure", zone)):
                raise PhysicsError("Tool-crate station atmosphere unsafe")
            if "TOOL-CRIB" not in state("inventory", "INV-SPARES").reference.get(
                    "location_ids", ()):
                raise PhysicsError("Existing fitted tool crib is not commissioned")
            try:
                d["repairs"] = move_toolkit(
                    r, actor_dbref=actor.dbref, verb=value)
            except WaterError as exc:
                raise PhysicsError(str(exc)) from exc
        elif target == "INV-SPARES":
            if not isinstance(value, str) or not value.startswith("pickup:"):
                raise PhysicsError("Spare collection requires pickup:<kg>")
            _crew_at(actor, room)
            zone = _topology()[0].get(room)
            if zone is None or not _air_safe(state("pressure", zone)):
                raise PhysicsError("Unsafe compartment for physical spares pickup")
            parts = state("inventory", "INV-SPARES", lock=True)
            if room not in parts.reference.get("location_ids", ()):
                raise PhysicsError("Spare account is not installed in this store")
            try:
                kg = _positive(float(value.partition(":")[2]))
                survey = copy.deepcopy(water)
                holdings = survey["source_surveys"].get("INV-SPARES", {})
                if holdings.get(room, 0.0) + 1e-7 < kg:
                    raise WaterError("Repair spares not physically surveyed here")
                new_repair, new_stock = take_parts(
                    r, actor_dbref=actor.dbref, kg=kg,
                    stock_kg=parts.quantity * 1000.0)
                survey["source_surveys"]["INV-SPARES"][room] -= kg
                validate_water(survey, {
                    cat: state("inventory", ident).quantity * 1000.0
                    for cat, ident in (
                        ("normal", "INV-WATER-NORMAL"), ("reserve", "INV-WATER-RESERVE"),
                        ("sanitary", "INV-WASTE-RESIDUE"),
                        ("industrial", "INV-INDUSTRIAL-SCRAP"),
                        ("hazardous", "INV-HAZARDOUS-RESIDUE"),
                        ("filter", "INV-DC-CONSUMABLES"),
                        ("spares", "INV-SPARES"))})
            except (WaterError, ValueError, TypeError) as exc:
                raise PhysicsError(str(exc)) from exc
            before_stock = _snapshot(parts)
            parts.quantity = new_stock / 1000.0
            parts.revision += 1
            parts.save(update_fields=["quantity", "revision"])
            _event(parts, "issued_to_local_maintenance_worker", before_stock,
                   actor=actor)
            d["water"] = survey
            d["repairs"] = new_repair
        else:
            if not isinstance(target, str) or target.count(":") != 1:
                raise PhysicsError("Repair target requires an exact category:id")
            category, ident = target.split(":", 1)
            if category not in {"equipment", "isolator", "access"}:
                raise PhysicsError("Only installed physical machinery can be repaired")
            unit = state(category, ident, lock=True)
            _crew_at(actor, room)
            if (category == "equipment"
                    and ident in FREIGHT_SERVICE_WORKSITES
                    and (room != FREIGHT_SERVICE_WORKSITES[ident][0]
                         or not _freight_service_entry_ready(
                             FREIGHT_SERVICE_WORKSITES[ident][1],
                             clock_details=d))):
                raise PhysicsError("Service equipment requires live attended freight lockout")
            radiator_face = (
                category == "equipment" and
                EXTERIOR_RADIATOR_FACES.get(room) == ident)
            if category == "access":
                if room not in {unit.reference.get("from"),
                                unit.reference.get("to")}:
                    raise PermissionError("Repairer must stand at the actual hatch endpoint")
            elif room != unit.space_id and not radiator_face:
                raise PermissionError("Repairer is not at the installed machinery")
            if radiator_face:
                if (not _radiator_suit_ready(actor, room, d) or
                        not _radiator_worksite_ready(
                            d, ident,
                            {row.source_id: row for row in
                             CanonicalShipState.objects.filter(category="equipment")},
                            {row.source_id: row for row in
                             CanonicalShipState.objects.filter(category="isolator")})):
                    raise PhysicsError("Exterior repair requires issued suit, permit and cool radiator")
            zone = _topology()[0].get(room)
            if radiator_face:
                if not _radiator_worksite_ready(
                        d, ident,
                        {row.source_id: row for row in
                         CanonicalShipState.objects.filter(category="equipment")},
                        {row.source_id: row for row in
                         CanonicalShipState.objects.filter(category="isolator")}):
                    raise PhysicsError("Exterior radiator lacks physical safe service permit")
            elif room in {"F1-BAY", "F2-BAY"}:
                if (r["site_surveys"].get(room) != "suited_service" or
                        not _flywheel_suit_ready(actor, room, d)):
                    raise PhysicsError("F1/F2 repairs require an actual issued oxygen suit and airlock survey")
                if ident in SERVICE_FLYWHEELS:
                    permit = (d.get("flywheel_service") or
                              {"permits": {}})["permits"].get(ident)
                    if (permit is None or
                            value == "start" and permit["worker"] != actor.dbref):
                        raise PhysicsError("Individual stopped flywheel requires its owner's padlocked module permit")
            elif not (isinstance(zone, str) and zone.startswith("PZ-")):
                if not (r["site_surveys"].get(room) == "suited_service"
                        and bool(getattr(actor.db, "ox_suit_verified", False))):
                    raise PhysicsError("Unpressurised machinery requires surveyed suited maintenance")
            pressure = {x.source_id: x for x in
                        CanonicalShipState.objects.filter(category="pressure")}
            isolators = {x.source_id: x for x in
                         CanonicalShipState.objects.filter(category="isolator")}
            equipment = {x.source_id: x for x in
                         CanonicalShipState.objects.filter(category="equipment")}
            if (category == "equipment" and ident in WORKSHOP_DRIVES
                    and not machine_safely_stopped(ident, unit.details)):
                raise PhysicsError(
                    "Machine rotor or hydraulic accumulator has not physically stopped")
            if (category == "equipment" and ident in BEARING_PUMPS
                    and not machine_depressurized(ident, unit.details)):
                raise PhysicsError("Bearing lubrication pressure must bleed down before repair")
            if not safe_repair_target(
                    unit, pressure_rows=pressure, zones=_topology()[0],
                    rotors=d["rotors"], motion=d["motion"],
                    water=water, cargo=d["cargo"], equipment=equipment,
                    isolators=isolators, workroom=room,
                    surveyed_suit_work=(
                        r["site_surveys"].get(room) == "suited_service"
                        or radiator_face),
                    flywheel_service=d.get("flywheel_service"),
                    electrical=d.get("electrical"),
                    exterior_radiators=d.get("exterior_radiators")):
                raise PhysicsError("Safe local isolation and known repairable damage required")
            try:
                if value == "start":
                    if category == "equipment" and ident in set(MOTORS) | set(SERVICE_LOADS):
                        cases = d.get("fault_cases") or initial_fault_cases()
                        case = cases["cases"].get(ident)
                        if case is not None:
                            if (case["stage"] != "isolated" or not
                                    verified_open_feeders(ident, {
                                        feeder: state("isolator", feeder, lock=True)
                                        for feeder in feeders_for(ident)})):
                                raise PhysicsError("Signed case requires physically verified complete feeder isolation")
                            d["fault_cases"] = begin_verified_work(
                                cases, ident, isolated=True)
                    r = begin_repair(
                        r, target=target, room=room,
                        actor_dbref=actor.dbref, condition=unit.condition)
                elif value == "join":
                    r = join_repair(
                        r, target=target, actor_dbref=actor.dbref,
                        room=room)
                else:
                    raise WaterError("Repair operation requires start or join")
            except WaterError as exc:
                raise PhysicsError(str(exc)) from exc
            d["repairs"] = r
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "port":
        if target not in PORTALS or not isinstance(value, str):
            raise PhysicsError("Unknown commercial loading portal")
        parts = value.split(":")
        if len(parts) != 2 or parts[0] not in {
                "load", "unload", "pause", "resume", "abort"}:
            raise PhysicsError("Port action requires load|unload|pause|resume|abort:<lot>")
        direction, lot_id = parts
        drum = target[:5]
        room = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        if (room not in {"CARGO-CTRL-FWD", drum + "-GALLERY"} or
                getattr(actor.db, "crew_role", None) not in
                {"cargo_officer", "chief_engineer", "watch_engineer"} and
                not actor.check_permstring("Developer")):
            raise PermissionError("Cargo operator must attend a real cargo station")
        station = state("equipment", "LP-CARGO-CTRL-FWD")
        handler = state("equipment", drum + "-RADIAL-FREIGHT-HANDLER")
        inner = state("access", "ACC-" + target)
        if station.condition in _BROKEN:
            raise PhysicsError("Commercial port local control panel damaged")
        if direction in {"load", "unload"} and any(
                job["portal_id"][:5] == drum for job in
                _clock().details.get("water", {}).get(
                    "waste_offload", {}).get("jobs", {}).values()):
            raise PhysicsError("This drum handler is reserved for a sealed waste cassette")
        if direction in {"load", "unload"} and (
                handler.condition in _BROKEN or inner.condition in _BROKEN):
            raise PhysicsError("Commercial port or cargo-handling machinery damaged")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        motion = d["motion"]
        if ((motion.get("ftl_leg") or {}).get("status") == "engaged"
                or motion["command"] != "coast"
                or motion["attitude_command"] != "hold"
                or any(abs(v) > 0.0001 for v in motion["angular_velocity_rad_s"])):
            raise PhysicsError("Cargo operations prohibited while ship manoeuvring")
        try:
            if direction in {"load", "unload"}:
                d["cargo"] = start_port_job(
                    d["cargo"], d["rotors"], lot_id=lot_id,
                    portal_id=target, direction=direction,
                    capacity_kg=motion["cargo_capacity_kg"],
                    equipment_ready=True, inner_gate_sealed=inner.setting == "closed")
            else:
                # Stopping an unsafe handler must remain possible during
                # an actuator casualty. Reverse travel resumes only when
                # physical machinery, contacts and power return.
                d["cargo"] = command_port_job(
                    d["cargo"], portal_id=target,
                    lot_id=lot_id, command=direction)
            validate_cargo(d["cargo"], motion["cargo_mass_kg"])
        except CargoError as exc:
            raise PhysicsError(str(exc)) from exc
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "freight_service":
        # A rated existing freight entry is not ordinarily walkable.
        # Qualified engineers open its maintenance wicket at the original
        # upstream station only after cargo/rotary lockout and gas checks.
        if target not in FREIGHT_SERVICE_GATES or value not in {"open", "close"}:
            raise PhysicsError("No fitted attended freight service passage")
        control, site, kind, boundary, rotor = FREIGHT_SERVICE_GATES[target]
        _crew_at(actor, control)
        if (actor.db.crew_role not in FREIGHT_SERVICE_ROLES
                and not actor.check_permstring("Developer")):
            raise PermissionError("Freight service requires an engineer or cargo officer")
        item = _clock(lock=True)
        before = _snapshot(item)
        ledger = item.details.get("freight_service")
        if ledger is None:
            raise PhysicsError("Fitted maintenance gates are not commissioned")
        validate_service_access(ledger)
        door = state("access", target, lock=True)
        if door.condition in _BROKEN:
            raise PhysicsError("Damaged freight service hatch cannot be actuated")
        if value == "open":
            if (door.setting != "closed" or
                    freight_service_secured(ledger) or
                    not _freight_service_site_safe(target,
                                                   clock_details=item.details)):
                raise PhysicsError("Freight service lockout, gas or parked machinery unsafe")
        else:
            if (target not in ledger["secured_links"]
                    or door.setting != "open"):
                raise PhysicsError("No matching live service access to release")
            from evennia.objects.models import ObjectDB
            from world.ship_world import find_ship_space
            workroom = find_ship_space(site)
            if workroom is None:
                raise PhysicsError("Fitted service compartment disappeared")
            if any(getattr(person.db, "crew_role", None)
                   for person in ObjectDB.objects.filter(db_location=workroom)):
                raise PhysicsError("Crew member remains in isolated freight worksite")
            if any(job["room"] == site for job in
                   (item.details.get("repairs") or {"jobs": {}})["jobs"].values()):
                raise PhysicsError("Finish on-site maintenance before restoring freight")
        try:
            altered = command_freight_service(ledger, target, value)
        except FreightServiceError as exc:
            raise PhysicsError(str(exc)) from exc
        prior_door = _snapshot(door)
        door.setting = "open" if value == "open" else "closed"
        door.revision += 1
        door.save(update_fields=["setting", "revision"])
        _event(door, "crew_attended_freight_service_gate", prior_door,
               actor=actor)
        details = dict(item.details)
        details["freight_service"] = altered
        item.details = details
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
        direction = value
        destination_drum = None
        if isinstance(value, str) and value.startswith("from_spine:"):
            direction = "from_spine"
            destination_drum = value.partition(":")[2]
        drum = destination_drum if destination_drum else lot["drum"]
        if drum not in DRUMS:
            raise PhysicsError("No installed target drum")
        if any(job["portal_id"][:5] == drum for job in
               d.get("water", {}).get("waste_offload", {}).get("jobs", {}).values()):
            raise PhysicsError("Freight collar is occupied by sealed waste operation")
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
        handler = state("equipment", drum + "-RADIAL-FREIGHT-HANDLER")
        if handler.condition in _BROKEN:
            raise PhysicsError("Actual cargo handling rail is inoperative")
        collar = state("equipment", drum + "-FREIGHT-COLLAR")
        gate = state("access", "ACC-" + drum + "-FREIGHT-CAPTURE")
        gate_open = gate.setting == "open" and gate.condition not in _BROKEN
        if gate_open and direction in {"to_spine", "from_spine"}:
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
                cargo, d["rotors"], lot_id=target, direction=direction,
                destination_drum=destination_drum,
                collar_healthy=collar.condition not in _BROKEN,
                gate_open=gate_open,
                restricted=lot["mass_kg"] > 50_000)
            validate_cargo(d["cargo"], d["motion"]["cargo_mass_kg"])
        except CargoError as exc:
            raise PhysicsError(str(exc)) from exc
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "ftl":
        room = getattr(getattr(getattr(actor, "location", None), "db", None),
                       "ox_space_id", None)
        role = getattr(actor.db, "crew_role", None)
        if (room not in {"CMD-PRIMARY", "NAV-PLANNING"} or
                role not in {"captain", "bridge_officer"} and
                not actor.check_permstring("Developer")):
            raise PermissionError("FTL requires a qualified navigator at command or navigation station")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        if value == "engage":
            if contacts_active(d.get("cargo", {})):
                raise PhysicsError("FTL translation prohibited while moored to cargo berth")
            field = state("equipment", "FTL-TRANSLATION-FIELD")
            station = state("equipment", "LCS-FTL")
            if field.condition in _BROKEN or station.condition in _BROKEN:
                raise PhysicsError("Installed translation-field machinery unavailable")
            # Dispatching a leg requires the *actual* separately fitted
            # translation-control feeder, not just a healthy machine object.
            # Before G19 electrical commissioning retain legacy G19 movement.
            if d.get("electrical") is not None:
                units = {x.source_id: x for x in
                         CanonicalShipState.objects.filter(category="equipment")}
                edges = list(CanonicalShipState.objects.filter(category="edge"))
                switches = {x.source_id: x for x in
                            CanonicalShipState.objects.filter(category="isolator")}
                supply = _power(
                    units, edges, switches, d["load_profile"],
                    ledger=d["electrical"],
                    moored=contacts_active(d.get("cargo", {})))
                if (not supply["assured"]
                        or not motor_power(
                            "FTL-TRANSLATION-FIELD", nodes=supply["nodes"],
                            equipment=units,
                            edges={x.source_id: x for x in edges},
                            switches=switches)):
                    raise PhysicsError(
                        "FTL translation control lacks its powered local feeder")
        try:
            d["motion"] = command_leg(d["motion"], target, value)
        except NavigationError as exc:
            raise PhysicsError(str(exc)) from exc
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
    elif action == "drive":
        if target not in {"MAIN", "RCS"} or value not in {"inhibit", "release", "reset", "prove_start", "prove_verify"}:
            raise PhysicsError("Unknown propulsion safety operation")
        _crew_at(actor, "PROP-CTRL")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        motion = dict(d.get("motion", {}))
        key = "drive_condition" if target == "MAIN" else "rcs_condition"
        current = motion.get(key)
        if value in {"prove_start", "prove_verify"}:
            if target != "MAIN":
                raise PhysicsError("Installed engine proof is for main thrust only")
            if (state("equipment", "LCS-PROP").condition in _BROKEN or
                    state("equipment", "LP-PROP-CTRL").condition in _BROKEN):
                raise PhysicsError("Damaged physical control cannot certify engine output")
            record = d.get("drive_proof") or initial_drive_proof()
            try:
                if value == "prove_start":
                    record = start_drive_proof(
                        record, actor=actor.dbref, motion=motion,
                        game_time=d["last_game_time"])
                else:
                    record = verify_drive_proof(
                        record, actor=actor.dbref, motion=motion,
                        game_time=d["last_game_time"])
            except DriveProofError as exc:
                raise PhysicsError(str(exc)) from exc
            d["drive_proof"] = record
        elif value == "reset":
            if target != "MAIN" or current != "thermal_trip":
                raise PhysicsError("No local propulsion thermal trip to reset")
            if motion.get("drive_heat_kj", 0) > DRIVE_THERMAL_RESET_KJ:
                raise PhysicsError("Propulsion too hot for safe manual reset")
            motion[key] = "inhibited"
            motion["drive_trip_reason"] = None
        elif value == "release":
            if current != "inhibited":
                raise PhysicsError("Only a locally inhibited sound drive can be released")
            if (state("equipment", "LCS-PROP").condition in _BROKEN
                    or state("equipment", "LP-PROP-CTRL").condition in _BROKEN):
                raise PhysicsError("Cannot re-arm propulsion through damaged local controls")
            # Inhibiting a drive does not repair underlying damage.
            motion[key] = "operational"
            if target == "MAIN" and motion.get("drive_trip_reason") == "propulsion_control_loss":
                motion["drive_trip_reason"] = None
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
            ("ENG-CONTROL", "HUB-FIXED-A", "HUB-FIXED-B")
            if target == "HAB" and (
                value.startswith("passenger_extend:") or
                value.startswith("sync:") or value == "sync_release" or
                value == "passenger_retract")
            else ("ENG-CONTROL",) if target == "HAB" else
            (target + "-FREIGHT-LOCK", target + "-SERVICE-LOCK"))
        if room not in permitted or (
                getattr(actor.db, "crew_role", None) not in roles and
                not actor.check_permstring("Developer")):
            raise PermissionError("Operator is not at that rotor's local machinery controls")
        if target in DRUMS and value in {
                "start", "release", "index", "freight_extend", "passenger_extend"}:
            manifest = _clock().details.get("cargo", {})
            if any(portal[:5] == target
                   for portal in manifest.get("port_contacts", {})):
                raise PhysicsError("Cannot release, index or motor an externally moored drum")
            if value == "start":
                if target not in manifest.get("verified_drums", []):
                    raise PhysicsError("Drum cargo has not been independently surveyed")
                if unsecured_drum_loads(manifest, target):
                    raise PhysicsError("Loose or unstowed freight prevents drum spin-up")
        if target in DRUMS:
            waste_jobs = [job for job in
                _clock().details.get("water", {}).get(
                    "waste_offload", {}).get("jobs", {}).values()
                if job["portal_id"][:5] == target]
            if waste_jobs and (value in {
                    "start", "release", "index", "passenger_extend"} or
                    value == "freight_retract" and any(j["phase"] in {
                        "hauling", "aborting", "returning"} for j in waste_jobs)):
                raise PhysicsError("Sealed waste freight capture must finish before rotary release")
        if target in DRUMS and target in _clock().details.get("cargo", {}).get("jobs", {}):
            if value in {"start", "release", "freight_retract", "passenger_extend"}:
                raise PhysicsError("Freight operation underway; cannot release its capture")
        transfers = _clock().details.get("personnel_transfers") or {"jobs": {}}
        if target == "HAB" and value in {"passenger_extend:A", "passenger_extend:B"}:
            if _clock().details.get("hab_sync", {}).get("mode") not in {None, "stowed"}:
                raise PhysicsError("Parked HAB collar cannot overlap its moving carrier")
        if target == "HAB" and value in {"sync:A", "sync:B", "sync_release"}:
            sync = _clock().details.get("hab_sync")
            if sync is None:
                raise PhysicsError("HAB moving indexer is not commissioned")
            if value.startswith("sync:"):
                station = value[-1]
                if room not in {"ENG-CONTROL", "HUB-FIXED-" + station}:
                    raise PermissionError("Engineer must select the actual HAB indexer station")
                if any(state("equipment", f"IX-{station}-{suffix}").condition
                       in _BROKEN for suffix in (
                           "DRIVE", "CARRIER", "FIXED-COLLAR", "ROT-COLLAR")):
                    raise PhysicsError("Moving HAB carrier hardware damaged")
                for door_id in (f"ACC-IX-{station}-FIX", f"ACC-IX-{station}-ROT"):
                    door = state("access", door_id)
                    if door.condition in _BROKEN or door.setting != "closed":
                        raise PhysicsError("Both HAB carrier hatches must be closed")
                clock_details = _clock().details
                supply = _power(
                    {r.source_id: r for r in CanonicalShipState.objects.filter(
                        category="equipment")},
                    list(CanonicalShipState.objects.filter(category="edge")),
                    {r.source_id: r for r in CanonicalShipState.objects.filter(
                        category="isolator")},
                    clock_details["load_profile"],
                    ledger=clock_details.get("electrical"),
                    moored=contacts_active(clock_details.get("cargo", {})))
                if not supply["assured"]:
                    raise PhysicsError("No confirmed electrical power for phase matching")
                if (clock_details.get("electrical") is not None
                        and "NODE-LP-" + room not in supply["nodes"]):
                    raise PhysicsError("Actual HAB indexer control station has lost its power feeder")
            item = _clock(lock=True)
            before = _snapshot(item)
            d = dict(item.details)
            try:
                d["hab_sync"] = command_hab_sync(
                    sync, "release" if value == "sync_release" else value,
                    hab_rpm=d["rotors"]["HAB"]["rpm"],
                    parked_indexer=d["rotors"]["HAB"]["passenger_indexer"],
                    occupied="HAB" in transfers["jobs"])
            except HabSyncError as exc:
                raise PhysicsError(str(exc)) from exc
            item.details = d
            item.revision += 1
            item.save(update_fields=["details", "revision"])
        elif target in transfers["jobs"] and value in {
                "passenger_retract", "start", "release", "index",
                "freight_extend", "freight_retract", "hardlock",
                "passenger_extend", "passenger_extend:A", "passenger_extend:B"}:
            raise PhysicsError("Occupied personnel carriage cannot be released or re-indexed")
        if target == "HAB" and value not in {"sync:A", "sync:B", "sync_release"} and (
                _clock().details.get("hab_sync", {}).get("mode") not in {None, "stowed"}
                and value in {"release", "index", "hardlock", "passenger_retract",
                              "passenger_extend:A", "passenger_extend:B"}):
            raise PhysicsError("Moving HAB phase lock excludes stationary collars and release")
        if target in DRUMS and value == "passenger_extend":
            fixed = state("access", "ACC-" + target + "-LOCK-FIX")
            rotary = state("access", "ACC-" + target + "-LOCK-ROT")
            if (fixed.condition in _BROKEN or fixed.setting != "closed"
                    or rotary.condition in _BROKEN or rotary.setting != "closed"):
                raise PhysicsError("Drum personnel locks must both be shut and sound")
        if target == "WR-01" and value == "passenger_extend":
            fixed = state("access", "ACC-WR-FIXED-IX")
            rotary = state("access", "ACC-WR-IX-HUB")
            if (state("equipment", "WR-INDEXER").condition in _BROKEN
                    or fixed.condition in _BROKEN or fixed.setting != "closed"
                    or rotary.condition in _BROKEN or rotary.setting != "closed"):
                raise PhysicsError("Workshop personnel indexer or its two hatches unsafe")
        if target == "HAB" and value in {
                "passenger_extend:A", "passenger_extend:B"}:
            station = value[-1]
            if room != "ENG-CONTROL" and room != "HUB-FIXED-" + station:
                raise PermissionError("Indexing must be ordered at its actual HAB station")
            fixed = state("access", f"ACC-IX-{station}-FIX")
            rotary = state("access", f"ACC-IX-{station}-ROT")
            if (fixed.condition in _BROKEN or fixed.setting != "closed"
                    or rotary.condition in _BROKEN or rotary.setting != "closed"
                    or any(state("equipment", f"IX-{station}-{suffix}").condition
                           in _BROKEN for suffix in (
                               "DRIVE", "CARRIER", "FIXED-COLLAR", "ROT-COLLAR"))):
                raise PhysicsError("Independent habitation indexer station not serviceable")
        if target in DRUMS and value in {"freight_extend", "passenger_extend"}:
            suffix = ("-FREIGHT-COLLAR" if value == "freight_extend"
                      else "-PERSONNEL-INDEXER")
            unit = state("equipment", target + suffix)
            if unit.condition in _BROKEN:
                raise PhysicsError("Transfer actuator damaged")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        if target == "HAB" and value in {"sync:A", "sync:B", "sync_release"}:
            # Already applied to the separately persistent moving-carrier
            # state, never submitted to the stationary rotor command parser.
            pass
        else:
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
        if (value != "hold"
                and state("equipment", "LCS-PROP").condition in _BROKEN):
            raise PhysicsError("Attitude-control command blocked by damaged propulsion station")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        motion = dict(d.get("motion", {}))
        if not motion:
            raise PhysicsError("Ship motion has not been commissioned")
        if (motion.get("ftl_leg") or {}).get("status") == "engaged":
            raise PhysicsError("Attitude controls locked during FTL translation")
        if value != "hold" and contacts_active(d.get("cargo", {})):
            raise PhysicsError("External commercial mooring prevents attitude thrust")
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
        if (value != "coast"
                and state("equipment", "LCS-PROP").condition in _BROKEN):
            raise PhysicsError("Main drive command blocked by damaged propulsion station")
        item = _clock(lock=True)
        before = _snapshot(item)
        d = dict(item.details)
        motion = dict(d.get("motion", {}))
        if not motion:
            raise PhysicsError("Ship motion has not been commissioned")
        if (motion.get("ftl_leg") or {}).get("status") == "engaged":
            raise PhysicsError("Sublight controls locked during FTL translation")
        if value != "coast" and contacts_active(d.get("cargo", {})):
            raise PhysicsError("External commercial mooring prevents thrust")
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
        ordinary_bridge = (item.source_id.startswith("ACC-BR-") and
                           "hatch" in str(spec.get("kind", "")).lower())
        fixed_indexer = (
            re.fullmatch(r"ACC-DR-0[1-6]-LOCK-FIX", item.source_id) is not None
            or item.source_id in {"ACC-IX-A-FIX", "ACC-IX-B-FIX",
                                  "ACC-WR-FIXED-IX"})
        ordinary_local = (
            not ordinary_bridge and not fixed_indexer
            and spec.get("kind") in CREW_LOCAL_DOOR_KINDS)
        if not ordinary_bridge and not fixed_indexer and not ordinary_local:
            raise PhysicsError("Cargo, EVA and machinery doors require dedicated interlocks")
        if item.condition in _BROKEN:
            raise PhysicsError("Damaged hatch cannot be safely actuated")
        if value == "open" and item.setting != "open":
            if ordinary_bridge:
                _hatch_open_preflight(item)
            elif fixed_indexer:
                _personnel_fixed_hatch_preflight(item)
            else:
                _ordinary_crew_door_preflight(item)
        before = _snapshot(item)
        if item.setting != value:
            item.setting = value
            item.revision += 1
            item.save(update_fields=["setting", "revision"])
    elif action == "service":
        if target in REFUGE_PACKS:
            if not isinstance(value, str) or not value.startswith("refill:"):
                raise PhysicsError("Refuge filter needs refill:<kg> of surveyed local media")
            item = state("equipment", target, lock=True)
            room, battery_id = REFUGE_PACKS[target]
            _crew_at(actor, room)
            if item.condition in _BROKEN or item.space_id != room:
                raise PhysicsError("Refuge filter appliance is unavailable for servicing")
            zone = _topology()[0].get(room)
            if not zone or not _air_safe(state("pressure", zone, lock=True)):
                raise PhysicsError("Refuge gas and temperature unsafe for unsuited filter service")
            # Both independent fitted electrical paths must be physically
            # locked open before an engineer removes the cartridge cassette.
            for iso_id in ("ISO-PWR-" + target,
                           "ISO-G19-LOCAL-" + battery_id):
                isolator = state("isolator", iso_id, lock=True)
                if isolator.condition in _BROKEN or isolator.setting != "open":
                    raise PhysicsError("Isolate both normal and emergency refuge electricity before service")
            try:
                media_kg = _positive(
                    float(value.partition(":")[2]),
                    maximum=4.0)
            except (TypeError, ValueError) as exc:
                raise PhysicsError("Portable refuge media is limited to four kilograms") from exc
            clock = _clock(lock=True)
            details = dict(clock.details)
            if (details.get("water") is None
                    or details.get("refuge_scrubbers") is None
                    or details.get("refuge_media_service") is None):
                raise PhysicsError("Refuge maintenance requires commissioned supplies and media")
            stock = state("inventory", "INV-DC-CONSUMABLES", lock=True)
            allocated = stock.reference.get("location_allocations_t", {})
            if room not in allocated:
                raise PhysicsError("No originally fitted consumable stock at this refuge")
            import copy
            water = copy.deepcopy(details["water"])
            source_sites = water["source_surveys"].get(
                "INV-DC-CONSUMABLES", {})
            at_room = source_sites.get(room, 0.0)
            try:
                scrubbers, media, remaining = load_refuge_media(
                    details["refuge_scrubbers"],
                    details["refuge_media_service"], target, media_kg,
                    surveyed_local_stock_kg=at_room,
                    inventory_stock_kg=stock.quantity * 1000.0)
                if at_room > allocated[room] * 1000.0 + 1e-7:
                    raise RefugeAirError("Unverified remote refuge stock allocation")
                source_sites[room] -= media_kg
                # The existing water/disposal ledger already owns verified
                # local material custody; spend the exact same real source.
                validate_water(water, {
                    "normal": state("inventory", "INV-WATER-NORMAL").quantity * 1000,
                    "reserve": state("inventory", "INV-WATER-RESERVE").quantity * 1000,
                    "sanitary": state("inventory", "INV-WASTE-RESIDUE").quantity * 1000,
                    "industrial": state("inventory", "INV-INDUSTRIAL-SCRAP").quantity * 1000,
                    "hazardous": state("inventory", "INV-HAZARDOUS-RESIDUE").quantity * 1000,
                    "filter": remaining,
                    "spares": state("inventory", "INV-SPARES").quantity * 1000,
                })
            except (RefugeAirError, WaterError) as exc:
                raise PhysicsError(str(exc)) from exc
            previous_clock = _snapshot(clock)
            previous_stock = _snapshot(stock)
            details["water"] = water
            details["refuge_scrubbers"] = scrubbers
            details["refuge_media_service"] = media
            clock.details = details
            clock.revision += 1
            clock.save(update_fields=["details", "revision"])
            _event(clock, "refuge_media_installed_in_actual_pack",
                   previous_clock, actor=actor)
            stock.quantity = remaining / 1000.0
            stock.revision += 1
            stock.save(update_fields=["quantity", "revision"])
            _event(stock, "refuge_local_consumable_to_cartridge",
                   previous_stock, actor=actor)
            before = _snapshot(item)
            d = dict(item.details)
            d["refuge_media_service_count"] = d.get(
                "refuge_media_service_count", 0) + 1
            d["last_media_service_kg"] = media_kg
            item.details = d
            item.revision += 1
            item.save(update_fields=["details", "revision"])
        elif (target in SERVICE_LOADS and
              target.endswith("-CARGO-HX")):
            if not isinstance(value, str) or not value.startswith("target:"):
                raise PhysicsError("Cargo heat exchanger requires target:<kelvin>")
            item = state("equipment", target, lock=True)
            _crew_at(actor, item.space_id)
            if item.condition in _BROKEN:
                raise PhysicsError("Local cargo temperature controller is damaged")
            zone = _topology()[1].get(target)
            if zone not in {"PZ-" + drum + "-SVC" for drum in CARGO_DRUMS}:
                raise PhysicsError("Cargo climate control has no verified gallery")
            if not _air_safe(state("pressure", zone, lock=True)):
                raise PhysicsError("Cargo gallery air or thermal conditions unsafe")
            clock = _clock(lock=True)
            details = dict(clock.details)
            climate = details.get("cargo_environment")
            if climate is None:
                raise PhysicsError("Cargo thermal observation has not been commissioned")
            equipments = {row.source_id: row for row in
                          CanonicalShipState.objects.filter(category="equipment")}
            wires = list(CanonicalShipState.objects.filter(category="edge"))
            contacts = {row.source_id: row for row in
                        CanonicalShipState.objects.filter(category="isolator")}
            grid = _power(
                equipments, wires, contacts, details["load_profile"],
                ledger=details.get("electrical"),
                moored=contacts_active(details["cargo"]))
            if not (grid["assured"] and service_power(
                    target, nodes=grid["nodes"], equipment=equipments,
                    edges={row.source_id: row for row in wires},
                    switches=contacts)):
                raise PhysicsError("Cargo control setpoint requires a live local feeder")
            try:
                requested_k = float(value.partition(":")[2])
                next_climate = set_cargo_target(
                    climate, details["cargo"], target[:5], requested_k)
            except (ValueError, TypeError, CargoClimateError) as exc:
                raise PhysicsError("Invalid surveyed cargo temperature setpoint") from exc
            before_clock = _snapshot(clock)
            details["cargo_environment"] = next_climate
            clock.details = details
            clock.revision += 1
            clock.save(update_fields=["details", "revision"])
            _event(clock, "crew_cargo_temperature_setpoint",
                   before_clock, actor=actor)
            before = _snapshot(item)
            unit_details = dict(item.details)
            unit_details["last_attended_setpoint_k"] = requested_k
            item.details = unit_details
            item.revision += 1
            item.save(update_fields=["details", "revision"])
        else:
            if target not in PLANTS or value != "reset":
                raise PhysicsError("Only original local thermal protection can be reset")
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
    if selftest_evidence is not None:
        after["selftest_evidence"] = selftest_evidence
    event.after = after
    event.save(update_fields=["after"])
    result = _receipt(event, request_id, actor, action, target)
    if selftest_evidence is not None:
        result["selftest"] = selftest_evidence
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
    if target.startswith("fault:"):
        name = target[6:]
        if name not in set(MOTORS) | set(SERVICE_LOADS):
            raise PhysicsError("No individually audited machinery feeder")
        machine = state("equipment", name)
        _crew_at(actor, machine.space_id)
        d = _clock().details
        ledger = d.get("fault_cases") or initial_fault_cases()
        validate_fault_cases(ledger)
        if d.get("electrical") is None:
            raise PhysicsError("Fitted individual machine distribution is not commissioned")
        fitted = {key: state("isolator", key) for key in feeders_for(name)}
        units = {x.source_id: x for x in
                 CanonicalShipState.objects.filter(category="equipment")}
        edges = {x.source_id: x for x in
                 CanonicalShipState.objects.filter(category="edge")}
        switches = {x.source_id: x for x in
                    CanonicalShipState.objects.filter(category="isolator")}
        distribution = _power(
            units, list(edges.values()), switches, d["load_profile"],
            ledger=d["electrical"], moored=contacts_active(d["cargo"]))
        room_id, parent_node = (SERVICE_LOADS[name]
                                if name in SERVICE_LOADS else MOTORS[name])
        actual_feed = (service_power(name, nodes=distribution["nodes"],
                       equipment=units, edges=edges, switches=switches)
                       if name in SERVICE_LOADS else
                       motor_power(name, nodes=distribution["nodes"],
                       equipment=units, edges=edges, switches=switches))
        instruments = d.get("instrumentation")
        panel_id = next((p for p, v in instruments["panels"].items()
                         if v["room"] == room), None) if instruments else None
        panel = instruments["panels"].get(panel_id) if panel_id else None
        observed_alarms = {
            key: {"code": a["code"], "active": a["active"],
                  "observed_s": a["last_s"]}
            for key, a in (instruments or {"alarms": {}})["alarms"].items()
            if a["panel"] == panel_id and a["active"]
               and (a["subject"] in {name, panel_id})}
        case = ledger["cases"].get(name)
        return {
            "machine": name, "room": machine.space_id,
            "condition": machine.condition, "case": case,
            "machine_commanded": machine.details.get("physics_commanded_on"),
            "machine_running": machine.details.get("physics_online"),
            "startup_remaining_s": machine.details.get("physics_startup_s"),
            "attended_mechanical_output": (
                machine.details.get(GAUGE_FIELD)
                if name in WORKSHOP_DRIVES else None),
            "mechanically_stopped": (
                machine_safely_stopped(name, machine.details)
                and machine_depressurized(name, machine.details)),
            "observed_process_output": (
                machine.details.get(PROCESS_FIELD)
                if name in PROCESS_METRICS else None),
            "process_output_recent": proves_process_output(
                name, machine.details, observed_s=d["last_game_time"]),
            "real_source_node": parent_node,
            "upstream_node_energised": parent_node in distribution["nodes"],
            "dispatch_assured": distribution["assured"],
            "equipment_feed_conducting": bool(actual_feed),
            "physically_isolated": verified_open_feeders(name, fitted),
            "breaker_evidence": {
                key: {
                    "condition": row.condition, "setting": row.setting,
                    "installed_room": row.space_id,
                    "network": row.reference.get("network"),
                    "protection_tripped": bool(row.details.get(
                        "physics_power_trip_latched")),
                    "manual_reclose_game_s": row.details.get(
                        "physics_manual_close_game_s"),
                }
                for key, row in fitted.items()},
            "panel": ({"id": panel_id, "status": panel["status"],
                       "last_good_s": panel["last_good_s"],
                       "age_s": (d["last_game_time"] - panel["last_good_s"]
                                 if panel["last_good_s"] is not None else None),
                       "observed_machine_alarms": observed_alarms}
                      if panel is not None else None),
            "active_local_work": (d.get("repairs") or {"jobs": {}})[
                "jobs"].get("equipment:" + name),
            "scope": "actually_attended_machine_and_fitted_local_circuits_only",
            "telemetry_caveat": "power_route_is_modelled_from_installed_switches_not_an_independent_voltmeter",
        }
    if (target in {"instruments", "alarms", "alarm_bridge"}
            or target.startswith("panel:")
            or target.startswith("diagnose:")):
        clock = _clock()
        ledger = clock.details.get("instrumentation")
        if ledger is None:
            raise PhysicsError("Original ship instrumentation not commissioned")
        try:
            validate_instrumentation(ledger)
        except InstrumentError as exc:
            raise PhysicsError(str(exc)) from exc
        if target == "alarm_bridge":
            grid, installed = _instrument_power_grid(clock.details)
            try:
                return local_relay_summary(
                    ledger, room=room, powered_nodes=set(grid["nodes"]),
                    equipment=installed)
            except InstrumentError as exc:
                raise PhysicsError(str(exc)) from exc
        panels = [key for key, p in ledger["panels"].items()
                  if p["room"] == room]
        if not panels:
            raise PermissionError("No original local instrument panel fitted in this room")
        if target.startswith("panel:"):
            panel = target[6:]
            _instrument_local_panel(actor, panel, room, ledger)
            return panel_readout(
                ledger, panel, now_s=clock.details["last_game_time"])
        if target.startswith("diagnose:"):
            key = target[9:]
            panel = key.split("|", 1)[0]
            _instrument_local_panel(actor, panel, room, ledger)
            try:
                return diagnostics(ledger, key, panel_id=panel)
            except InstrumentError as exc:
                raise PhysicsError(str(exc)) from exc
        visible = {
            panel: panel_readout(
                ledger, panel, now_s=clock.details["last_game_time"])
            for panel in panels
            if _instrument_local_panel(actor, panel, room, ledger,
                                       require_live=False)
        }
        if not visible:
            raise PhysicsError("No live local instrument at this physical worksite")
        if target == "alarms":
            return {"alarms": {
                key: alarm for sample in visible.values()
                for key, alarm in sample["active_alarms"].items()},
                "scope": "local_only_not_remote_failure_oracle"}
        return {"panels": visible,
                "scope": "installed_powered_instruments_in_own_room_only"}
    if target in {"food", "nutrition"}:
        clock = _clock()
        ledger = clock.details.get("food")
        if ledger is None:
            raise PhysicsError("Original ship food stores not commissioned")
        validate_food(ledger)
        carried = ledger["carried"].get(actor.dbref)
        personal = ledger["crew"].get(actor.dbref)
        if target == "nutrition":
            return {"crew": actor.dbref,
                    "personal_nutrition": personal,
                    "carried_food_and_meal": carried,
                    "scope": "self_only_local_crew_nutrition"}
        result = {"room": room, "carried": carried,
                  "personal_nutrition": personal,
                  "scope": "own_room_existing_provisions"}
        if room in ledger["stores"]:
            result["stored_kg_by_kind"] = ledger["stores"][room]
        if room == FOOD_GALLEY:
            result["raw_kg_by_kind"] = ledger["galley_raw"]
            result["meals_on_rack"] = len(ledger["meals"][FOOD_GALLEY])
        if room == FOOD_MESS:
            result["meals_on_rack"] = len(ledger["meals"][FOOD_MESS])
        if room in ledger["waste"]:
            result["spoiled_food_pending_kg"] = ledger["waste"][room]
        if room in ledger["nutrient_certified"]:
            result["certified_nutrient_spares_kg"] = (
                ledger["nutrient_certified"][room])
        return result
    if target.startswith("NODE-") or target in {"PWR-MSB-A", "PWR-MSB-B", "PWR-PROT"}:
        node = CanonicalShipState.objects.filter(pk="node:" + target).first()
        if node and node.reference.get("network") == "power":
            owner = node.reference.get("owner_id")
            owner_type = node.reference.get("owner_type")
            local = (owner if owner_type == "space" else
                     (state("equipment", owner).space_id if
                      owner_type == "equipment" else None))
            if local != room:
                raise PermissionError("Stand beside this real electrical circuit")
            clock = _clock()
            equipment = {r.source_id: r for r in
                         CanonicalShipState.objects.filter(category="equipment")}
            edges = list(CanonicalShipState.objects.filter(category="edge"))
            switches = {r.source_id: r for r in
                        CanonicalShipState.objects.filter(category="isolator")}
            grid = _power(equipment, edges, switches, clock.details["load_profile"],
                          ledger=clock.details.get("electrical"),
                          moored=contacts_active(clock.details.get("cargo", {})))
            return {"id": target, "path_energised": target in grid["nodes"],
                    "schedule_assured": grid["assured"] and target in grid["nodes"],
                    "scope": "physically_local_actual_power_circuit"}
    if target in {f"GROW-{n}" for n in GROW_BAYS}:
        name = target
        room_id = GROW_BAYS[int(name[-1])]
        if room != room_id:
            raise PermissionError("Attend the original grow-room process skid")
        ledger = _clock().details.get("cultivation")
        if ledger is None:
            raise PhysicsError("Cultivation not commissioned")
        validate_cultivation(ledger)
        return {
            "bed": name,
            **dict(ledger["beds"][name]),
            "last_producing": name in ledger["last"]["productive"],
            "water_applied_this_step_kg": ledger["last"]["water_applied_kg"],
            "scope": "physically_attended_growth_and_staged_harvest",
        }
    if target in REFUGE_PACKS:
        # The operator may service only the attended fitted package. A
        # remote character cannot query another refuge's sorbent reserve.
        pack_room, battery = REFUGE_PACKS[target]
        if room != pack_room:
            raise PermissionError("Attend the actual refuge air-treatment pack")
        clock = _clock()
        scrubber = clock.details.get("refuge_scrubbers")
        custody = clock.details.get("refuge_media_service")
        if scrubber is None or custody is None:
            raise PhysicsError("Refuge media has no commissioned service ledger")
        validate_refuge_scrubbers(scrubber)
        validate_refuge_media_service(custody)
        account = scrubber["units"].get(target)
        site = custody["sites"][target]
        stock = clock.details.get("water") or {}
        locally_surveyed = stock.get("source_surveys", {}).get(
            "INV-DC-CONSUMABLES", {}).get(pack_room, 0.0)
        normal_breaker = state("isolator", "ISO-PWR-" + target)
        battery_breaker = state(
            "isolator", "ISO-G19-LOCAL-" + battery)
        unit = state("equipment", target)
        return {
            "id": target, "equipment_sound": unit.condition not in _BROKEN,
            "media_surveyed": account is not None,
            "media_capacity_kg": account["capacity_kg"] if account else None,
            "captured_in_active_media_kg": (
                account["captured_kg"] if account else None),
            "media_available_kg": (
                max(0.0, account["capacity_kg"] - account["captured_kg"])
                if account else None),
            "retired_captured_co2_kg": site["retired_capture_kg"],
            "sealed_spent_media_kg": site["sealed_spent_media_kg"],
            "fresh_media_installed_kg": site["fresh_installed_kg"],
            "locally_surveyed_replacement_kg": locally_surveyed,
            "normal_fuse_open": normal_breaker.setting == "open",
            "local_dc_fuse_open": battery_breaker.setting == "open",
            "scope": "attended_individual_refuge_air_package",
        }
    if target in LOCAL_LOADS:
        # Per-unit electrical measurements are physically local, rather than
        # a bridge-wide oracle into inaccessible battery lockers.
        spec = LOCAL_LOADS[target]
        if room != spec[0]:
            raise PermissionError("Attend this emergency battery at its actual room")
        clock = _clock()
        ledger = clock.details.get("local_backup")
        if ledger is None:
            raise PhysicsError("Local emergency DC not commissioned")
        validate_local_backup(ledger)
        battery = state("equipment", target)
        load = state("equipment", spec[1])
        edge = state("edge", "EDGE-G19-LOCAL-" + target)
        breaker = state("isolator", "ISO-G19-LOCAL-" + target)
        charger = state("isolator", "ISO-G19-CHARGE-" + target)
        account = ledger["units"].get(target)
        return {
            "id": target, "rated": account is not None,
            "charge_kwh": account["charge_kwh"] if account else None,
            "capacity_kwh": account["capacity_kwh"] if account else None,
            "mode": account["mode"] if account else "unrated",
            "battery_sound": battery.condition not in _BROKEN,
            "appliance_sound": load.condition not in _BROKEN,
            "fuse_closed": breaker.setting == "closed",
            "charger_fuse_closed": charger.setting == "closed",
            "wire_sound": edge.condition not in _BROKEN,
            "charged_kwh": account["charged_kwh"] if account else None,
            "last_tick_battery_active": bool(
                ledger["last"].get("active_local_consumers", {}).get(target)),
            "scope": "attended_individual_local_dc_circuit",
        }
    if (target in SERVICE_LOADS
            and target.endswith("-CARGO-HX")):
        room_id, _ = SERVICE_LOADS[target]
        if room != room_id:
            raise PermissionError("Read the actual cargo heat-exchanger panel locally")
        clock = _clock()
        climate = clock.details.get("cargo_environment")
        if climate is None:
            raise PhysicsError("Cargo climate has not been commissioned")
        validate_cargo_environment(climate, clock.details["cargo"])
        drum = target[:5]
        observed = climate["drums"][drum]
        return {
            "id": target, "drum": drum,
            "sampled": observed is not None,
            "temperature_k": observed["temperature_k"] if observed else None,
            "target_temperature_k": observed["target_k"] if observed else None,
            "heat_capacity_kj_k": (
                observed["heat_capacity_kj_k"] if observed else None),
            "cooling_kw": (
                climate["last"]["cooling_kw"]
                if drum in climate["last"]["cooled_drums"] else 0.0),
            "sensitive_lots": {
                key: {"quality": lot["quality"],
                      "excursion_s": lot["excursion_s"],
                      "last_temperature_k": lot["last_temperature_k"]}
                for key, lot in climate["lots"].items()
                if clock.details["cargo"]["lots"][key]["drum"] == drum
            },
            "scope": "attended_real_cargo_environment_controller",
        }
    if target in SERVICE_LOADS:
        spec = SERVICE_LOADS[target]
        if room != spec[0]:
            raise PermissionError("Attend the original operating-equipment room")
        clock = _clock()
        running = clock.details.get("service_operations")
        if running is None:
            raise PhysicsError("Operating-equipment service not commissioned")
        validate_service_operations(running)
        units = {x.source_id: x for x in CanonicalShipState.objects.filter(
            category="equipment")}
        edges = list(CanonicalShipState.objects.filter(category="edge"))
        contacts = {x.source_id: x for x in CanonicalShipState.objects.filter(
            category="isolator")}
        power = _power(units, edges, contacts, clock.details["load_profile"],
                       ledger=clock.details.get("electrical"),
                       moored=contacts_active(clock.details.get("cargo", {})))
        supply = service_power(
            target, nodes=power["nodes"], equipment=units,
            edges={x.source_id: x for x in edges}, switches=contacts)
        account = running["units"][target]
        wear = clock.details.get("equipment_wear")
        current_wear = (wear["units"][target] if wear is not None else None)
        return {
            "id": target, "upstream_panel_energised": spec[1] in power["nodes"],
            "feeder_conducting": supply, "schedule_assured": power["assured"],
            "operating": account["operating"], "runtime_s": account["runtime_s"],
            "outage_s": account["outage_s"],
            "restart_required": account["restart_latched"],
            "local_breaker": service_ids(target)[2],
            "maintenance_stage": (
                current_wear["stage"] if current_wear else None),
            "wear_hours_since_service": (
                current_wear["wear_s"] / 3600.0 if current_wear else None),
            "historical_wear_surveyed": (
                current_wear["surveyed"] if current_wear else None),
            "workshop_mechanical_output": (
                units[target].details.get(GAUGE_FIELD)
                if target in WORKSHOP_DRIVES else None),
            "output_proven_at_site": (
                machine_output_confirmed(
                    target, units[target].details,
                    observed_s=clock.details["last_game_time"],
                    operating=bool(
                        power["assured"] and supply and
                        target in running["last"]["operating"]))
                if target in WORKSHOP_DRIVES else False),
            "scope": "attended_secondary_equipment_circuit",
        }
    if target in MOTORS:
        spec = MOTORS[target]
        if room != spec[0]:
            raise PermissionError("Attend this machinery motor feeder at its actual room")
        clock = _clock()
        equipment = {x.source_id: x for x in CanonicalShipState.objects.filter(
            category="equipment")}
        edges = list(CanonicalShipState.objects.filter(category="edge"))
        switches = {x.source_id: x for x in CanonicalShipState.objects.filter(
            category="isolator")}
        bus = _power(equipment, edges, switches, clock.details["load_profile"],
                     ledger=clock.details.get("electrical"),
                     moored=contacts_active(clock.details.get("cargo", {})))
        return {
            "id": target, "upstream_panel_energised": spec[1] in bus["nodes"],
            "feeder_conducting": motor_power(
                target, nodes=bus["nodes"], equipment=equipment,
                edges={x.source_id: x for x in edges}, switches=switches),
            "schedule_assured": bus["assured"],
            "source_selection": (
                ("protected"
                 if state("edge", protected_fire_ids(target)[0]).setting == "available"
                 else "normal"
                 if state("edge", "EDGE-G19-MOTOR-" + target).setting == "available"
                 else "isolated")
                if target in PROTECTED_FIRE_MOTORS else "single_source"),
            "scope": "attended_individual_motor_circuit",
        }
    if target == "power":
        electrical = _clock().details.get("electrical")
        if electrical is None:
            raise PhysicsError("G19 electrical metering not commissioned")
        accessible = {"ENG-CONTROL", "PROP-CTRL", "PWR-AFT",
                      "F1-BAY", "F2-BAY"}
        accessible |= {state("equipment", g).space_id for g in GENERATION_MW}
        if room not in accessible:
            raise PermissionError("Physical engineering power board required")
        return {"last_dispatch": electrical["last"],
                "meters_kwh": electrical["meter"],
                "rated_banks": {k: {
                    "charge_kwh": v["charge_kwh"],
                    "capacity_kwh": v["capacity_kwh"],
                    "mode": v["mode"]}
                    for k, v in electrical["banks"].items()},
                "flywheel_charge_kwh": sum(
                    v["charge_kwh"] for v in electrical["flywheels"].values()),
                "cartridge_remaining_kg": state(
                    "inventory", "INV-GEN-CART").quantity * 1000.0,
                "spent_cartridge_housings_kg": _clock().details.get(
                    "generator_spent_cartridge_kg", 0.0),
                "flywheel_modules_registered": len(electrical["flywheels"]),
                "tripped_breakers": sorted(
                    k for k, v in electrical["faults"].items() if v["latched"]),
                "shore_connected": (electrical["shore"]["connected"]
                    if electrical["shore"] else False),
                "scope": "physically_attended_engineering_power_board"}
    if target == "damage":
        major = _clock().details.get("major_damage")
        if major is None:
            raise PhysicsError("Major-hull damage control is not commissioned")
        visible = {}
        for zone, site in major["sites"].items():
            breach = (_clock().details.get("hull") or {}).get(
                "breaches", {}).get(zone)
            if (room not in {"ENG-CONTROL", site["external_face"],
                             breach["site_room"] if breach else None}):
                continue
            visible[zone] = {
                "isolated": site["isolated"],
                "remaining_s": site["remaining_s"],
                "external_face": site["external_face"],
                "rated_boundaries": len(site["boundaries"]),
                "open_or_damaged_boundaries": tuple(
                    door for door in site["boundaries"]
                    if state("access", door).setting != "closed"
                    or state("access", door).condition in _BROKEN),
                "measured_leak_kg_s": state("pressure", zone).details.get(
                    "physics_leak_kg_s"),
            }
        if not visible and room != "ENG-CONTROL":
            raise PermissionError("No surveyed major casualty at this position")
        return {"major_sites": visible,
                "scope": "engineering_damage_board_or_local_hull_face"}
    if target == "crew":
        own = CanonicalShipState.objects.filter(
            pk="crew_health:" + actor.dbref).first()
        if own is None:
            raise PhysicsError("This character is not enrolled in living-crew physics")
        return {
            "condition": own.condition, "room": own.space_id,
            "hypoxia_seconds": own.details["hypoxia_s"],
            "smoke_dose": own.details["smoke_dose"],
            "thermal_dose": own.details["thermal_dose"],
            "co2_dose": own.details["co2_dose"],
            "water_deficit_kg": own.details["water_deficit_kg"],
            "injury": own.details["injury"],
            "scope": "own_physically_measured_crew_health_only",
        }
    if target == "propulsion_service":
        d = _clock().details
        ledger = d.get("propulsion_exterior")
        if ledger is None:
            raise PhysicsError("Original exterior nozzle inspection is not commissioned")
        if room not in {PROPULSION_STATION, PROPULSION_FACE}:
            raise PermissionError("Read aft nozzle conditions from real control or exterior EVA face")
        validate_propulsion_exterior(ledger)
        equipment_here = {row.source_id: row for row in
                          CanonicalShipState.objects.filter(category="equipment")}
        if room == PROPULSION_FACE and not _propulsion_exterior_suit_ready(actor, d):
            raise PermissionError("Only a living issued-suit worker can read the nozzle face")
        return {"workface": PROPULSION_FACE, "survey": ledger["survey"],
                "permit_holder": (ledger["permit"] or {}).get("actor"),
                "ready": _propulsion_exterior_ready(d, equipment_here),
                "completed_inspections": ledger["inspected"],
                "access": state("access", PROPULSION_LINK).setting,
                "scope": "locally_attended_nozzle_inspection_and_plume"}
    if target == "radiator_service":
        d = _clock().details
        ledger = d.get("exterior_radiators")
        if ledger is None:
            raise PhysicsError("Fitted radiator worksite controller not commissioned")
        validate_exterior_radiators(ledger)
        visible = {}
        equipment_here = {row.source_id: row for row in
                          CanonicalShipState.objects.filter(category="equipment")}
        iso_here = {row.source_id: row for row in
                    CanonicalShipState.objects.filter(category="isolator")}
        for wing, spec in EXTERIOR_RADIATORS.items():
            panel = ("ENG-CONTROL" if wing.startswith("RAD-HT-")
                     else spec["station"])
            if room not in {panel, spec["face"]}:
                continue
            face = ledger["faces"][wing]
            visible[wing] = {
                "face": spec["face"], "skin_temperature_k": face["skin_k"],
                "measured_game_time": face["sample_game_time"],
                "permit": ledger["permits"].get(wing),
                "isolation_valves": {
                    name: state("isolator", name).setting
                    for name in spec["isolation"]},
                "worksite_ready": _radiator_worksite_ready(
                    d, wing, equipment_here, iso_here),
                "repair": (d.get("repairs") or {"jobs": {}})["jobs"].get(
                    "equipment:" + wing),
            }
        if not visible:
            raise PermissionError("Only the attended coolant control or exterior pad has local readings")
        return {"radiators": visible, "scope": "locally attended real radiator work faces"}
    if target == "flywheel_service":
        d = _clock().details
        ledger = d.get("flywheel_service")
        if ledger is None or room not in {"F1-BAY", "F2-BAY"}:
            raise PermissionError("Read the physical F1/F2 module maintenance station locally")
        validate_flywheel_service(ledger)
        if not _flywheel_suit_ready(actor, room, d):
            raise PermissionError("Suited engineer must attend the vacuum service bay")
        e = d["electrical"]
        owned = {
            name: {
                "measured_charge_kwh": e["flywheels"].get(
                    name, {}).get("charge_kwh"),
                "source_mode": e["flywheels"].get(name, {}).get("mode"),
                "feeder": state("isolator", module_breaker(name)).setting,
                "lockout_owner": ledger["permits"].get(name, {}).get("worker"),
                "rundown": ledger["rundowns"].get(name),
                "isolated_for_service_now": permit_live(
                    ledger, name, e, {
                        module_breaker(name): state(
                            "isolator", module_breaker(name))}),
                "job": (d.get("repairs") or {"jobs": {}})["jobs"].get(
                    "equipment:" + name),
            } for name in POWER_FLYWHEELS if module_room(name) == room and (
                name in e["flywheels"] or name in ledger["permits"])
        }
        return {"room": room, "modules": owned,
                "active_permits_here": sum(
                    name in ledger["permits"] for name in POWER_FLYWHEELS
                    if module_room(name) == room),
                "scope": "live_own_physically_attended_flywheel_bank"}
    if target == "bay_access":
        ledger = _clock().details.get("bay_access")
        if ledger is None:
            raise PhysicsError("Flywheel service airlocks not commissioned")
        validate_bay_access(ledger)
        local = {}
        for link, (corridor, bay, _panel) in BAY_SERVICE_LOCKS.items():
            if room in {corridor, bay}:
                local[link] = {
                    "surveyed": bay in ledger["surveyed_bays"],
                    "boundary": state("access", link).setting,
                    "occupied_by_self": actor.dbref in ledger["jobs"] and
                        ledger["jobs"][actor.dbref]["link"] == link,
                    "own_remaining_s": (
                        ledger["jobs"][actor.dbref]["remaining_s"]
                        if actor.dbref in ledger["jobs"] and
                        ledger["jobs"][actor.dbref]["link"] == link else None),
                }
        if not local:
            raise PermissionError("Attend original F1/F2 service hatch")
        return {"local_locks": local,
                "scope": "own_surveyed_original_sealed_flywheel_airlock"}
    if target == "rescue":
        ledger = _clock().details.get("rescue")
        if ledger is None:
            raise PhysicsError("Casualty transport not commissioned")
        validate_rescue(ledger)
        local = {}
        for patient, job in ledger["jobs"].items():
            if room in {job["origin"], job["destination"]} and (
                    actor.dbref in {patient, job["lead"], job["helper"]}):
                local[patient] = job
        return {"local_orders": local, "active_here": len(local),
                "scope": "only_own_local_timed_casualty_transport"}
    if target == "welding":
        d = _clock().details
        ledger = d.get("welding")
        if ledger is None:
            raise PhysicsError("Original independent welding cells not commissioned")
        if (room != WELDING_ROOM and room not in
                state("inventory", "INV-SPARES").reference.get("location_ids", ())):
            raise PermissionError("Weld stocks and arc meters are local, not remote")
        validate_welding(ledger)
        machines = {
            name: state("equipment", name).details.get("physics_weld_arc_gauge")
            for name in WELDING_CELLS} if room == WELDING_ROOM else {}
        return {
            "room": room,
            "certified_filler_here_kg": ledger["certified_kg"].get(room),
            "personal_filler_kg": ledger["filler_carried_kg"].get(actor.dbref, 0),
            "personal_slag_kg": ledger["slag_carried_kg"].get(actor.dbref, 0),
            "shop_slag_kg": ledger["slag_shop_kg"] if room == WELDING_ROOM else None,
            "active_jobs_here": ledger["jobs"] if room == WELDING_ROOM else {},
            "original_cell_arc_gauges": machines,
            "completed_weldments": ledger["completed"],
            "scope": "attended_real_weld_filler_and_thermal_output",
        }
    if target == "fabrication":
        d = _clock().details
        fab = d.get("fabrication")
        if fab is None:
            raise PhysicsError("Installed workshop fabrication is not commissioned")
        validate_fabrication(fab)
        if room != FABRICATION_ROOM and room not in {
                "SPARES-CENTRAL", "MATERIAL-STOCK", "STORE-CRIT-SPARES"}:
            raise PermissionError("Material reports are not available off site")
        return {"room": room,
                "certified_blanks_here_kg": fab["certified_kg"].get(room),
                "personal_blank_kg": fab["raw_carried_kg"].get(actor.dbref, 0.0),
                "personal_offcuts_kg": fab["offcuts_carried_kg"].get(actor.dbref, 0.0),
                "active_jobs_here": (fab["jobs"] if room == FABRICATION_ROOM
                                     else {}),
                "shop_offcuts_kg": (fab["shop_offcuts_kg"]
                                     if room == FABRICATION_ROOM else None),
                "finished_cumulative_kg": fab["finished_kg"],
                "completed_batches": fab["completed"],
                "last_local_receipts": (fab["receipts"][-5:]
                                        if room == FABRICATION_ROOM else []),
                "scope": "physically_attended_original_machine_shop"}
    if target == "medical":
        medical = _clock().details.get("medical")
        if medical is None or room not in {
                TREATMENT_ROOM, OBSERVATION_ROOM, PHARMACY_ROOM}:
            raise PermissionError("Attend commissioned HAB-04 pharmacy, treatment or observation")
        validate_medical(medical)
        return {"room": room, "clinic": TREATMENT_ROOM,
                "pharmacy_dressings": medical["pharmacy_dressings"]
                    if room == PHARMACY_ROOM else None,
                "pharmacy_fluid_kg": medical["pharmacy_fluid_kg"]
                    if room == PHARMACY_ROOM else None,
                "treatment_dressings": medical["dressings"]
                    if room == TREATMENT_ROOM else None,
                "treatment_fluid_kg": medical["fluid_kg"]
                    if room == TREATMENT_ROOM else None,
                "observation_dressings": medical.get("obs_dressings", 0)
                    if room == OBSERVATION_ROOM else None,
                "observation_fluid_kg": medical.get("obs_fluid_kg", 0.0)
                    if room == OBSERVATION_ROOM else None,
                "personal_kit": medical["carried"].get(actor.dbref),
                "active_cases": medical["cases"] if room == TREATMENT_ROOM else {},
                "observations": {
                    patient: course
                    for patient, course in medical.get("observations", {}).items()
                    if course.get("room", TREATMENT_ROOM) == room
                },
                "completed": medical["completed"],
                "observations_completed": medical.get("observation_completed", 0),
                "scope": "locally_attended_finite_HAB04_medical"}
    if target == "eva":
        system = _clock().details.get("eva")
        if system is None:
            raise PhysicsError("G19 EVA is not commissioned")
        _, suit = suit_of(system, actor.dbref)
        local = {}
        for lock in EVA_LOCKS:
            spec = lock_contract(lock)
            if room in {lock, spec["trunk"], spec["outside"]}:
                local[lock] = {
                    "mode": system["locks"][lock]["mode"],
                    "remaining_s": system["locks"][lock]["remaining_s"],
                    "recovered_gas_kg": system["locks"][lock]["buffer"]["mass"],
                    "inner": state("access", spec["inner"]).setting,
                    "outer": state("access", spec["outer"]).setting,
                    "air_damper": state("isolator", spec["damper"]).setting,
                }
        if not local and not room.startswith("EXT-") and suit is None:
            raise PermissionError("No EVA station or suit at this location")
        return {
            "locks_here": local,
            "suit": ({"home": suit["home"], "integrity": suit["integrity"],
                      "oxygen_kg": suit["exposure"]["suit_oxygen_kg"],
                      "co2_kg": suit["exposure"]["suit_co2_kg"],
                      "condition": suit["exposure"]["condition"]}
                     if suit else None),
            "staged_oxygen_kg": system["staged_kg"].get(actor.dbref, 0.0),
            "active_transit": system["transits"].get(actor.dbref),
            "scope": "local_issued_suit_and_airlock_only",
        }
    if target == "freight_service":
        ledger = _clock().details.get("freight_service")
        if ledger is None:
            raise PhysicsError("Attended freight service is not commissioned")
        validate_service_access(ledger)
        local = {}
        for gate, (control, site, kind, boundary, _rotor) in (
                FREIGHT_SERVICE_GATES.items()):
            if room in {control, site}:
                local[gate] = {
                    "control_room": control,
                    "worksite_room": site,
                    "physically_open": state("access", gate).setting == "open",
                    "permit_active": gate in ledger["secured_links"],
                    "entry_safe_now": _freight_service_entry_ready(gate),
                    "equipment_here": sorted(
                        name for name, (place, entry) in
                        FREIGHT_SERVICE_WORKSITES.items() if entry == gate),
                }
        if not local:
            raise PermissionError("No fitted freight service hatch at this position")
        return {"gates_here": local,
                "scope": "physical_local_service_hatch_only"}
    if target == "personnel":
        from world.ship_indexed_personnel import link_contract
        transfers = _clock().details.get("personnel_transfers")
        if transfers is None:
            raise PhysicsError("G19 indexed passenger mechanisms not commissioned")
        local = {}
        for link in (
                *(f"ACC-DR-{n:02d}-LOCK-ROT" for n in range(1, 7)),
                "ACC-IX-A-ROT", "ACC-IX-B-ROT", "ACC-WR-IX-HUB"):
            spec = link_contract(link)
            if room not in {spec["from"], spec["to"]}:
                continue
            rotor = _clock().details["rotors"][spec["rotor"]]
            local[link] = {
                "captured": bool(rotor["passenger_indexer"]),
                "station": rotor.get("passenger_station"),
                "active_job": transfers["jobs"].get(spec["rotor"]),
                "fixed_hatch_setting": state("access", spec["fixed_hatch"]).setting,
            }
        if not local:
            raise PermissionError("No indexed personnel transfer station here")
        return {"stations_here": local,
                "scope": "physically_local_indexed_passenger_transfer"}
    if target == "hull":
        hull = _clock().details.get("hull")
        if hull is None:
            raise PhysicsError("G19 hull is not commissioned")
        local = {zone: breach for zone, breach in hull["breaches"].items()
                 if breach["site_room"] == room}
        if not local:
            raise PermissionError("No registered hull repair face in this room")
        repairs = _clock().details.get("repairs", {})
        return {
            "breaches_here": {
                zone: {"phase": breach["phase"],
                       "measured_leak_kg_s": state("pressure", zone).details.get(
                           "physics_leak_kg_s"),
                       "installed_spares_kg": breach["installed_spares_kg"],
                       "work": repairs.get("jobs", {}).get("hull:" + zone)}
                for zone, breach in local.items()},
            "scope": "locally_surveyed_hull_faces_only",
        }
    if target == "repairs":
        repairs = _clock().details.get("repairs")
        if repairs is None:
            raise PhysicsError("Shared equipment repairs not commissioned")
        return {
            "carried_spares_kg": repairs["carried_kg"].get(actor.dbref, 0.0),
            "toolkit_carried": actor.dbref in repairs["toolkit_carriers"],
            "available_toolkits_here": (
                repairs["toolkits_at_crib"] if room == "TOOL-CRIB" else None),
            "work_orders_here": {
                key: job for key, job in repairs["jobs"].items()
                if job["room"] == room},
            "scope": "local_maintenance_work_orders_and_part_custody",
        }
    if target == "wasteport":
        waste = _clock().details.get("water")
        if waste is None:
            raise PhysicsError("Waste port service not commissioned")
        matches = {
            receiver: job for receiver, job in
            waste["waste_offload"]["jobs"].items()
            if room == "CARGO-CTRL-FWD"
            or room == job["portal_id"][:5] + "-FREIGHT-LOCK"
            or room == state("equipment", receiver).space_id}
        if not matches:
            raise PermissionError("No local sealed waste handling station or cassette")
        return {
            "jobs": matches,
            "delivered_kg": waste["waste_offload"]["delivered_kg"],
            "scope": "waste_hauls_observable_at_real_local_stations",
        }
    if target == "water":
        if room not in {"WATER-FWD", "HAB-06-ECLSS-A", "HAB-08-ECLSS-B",
                        "STORE-FLUID-AFT"}:
            raise PermissionError("Water and waste telemetry is limited to local stations")
        water = _clock().details.get("water")
        if not water:
            raise PhysicsError("G19 water/waste system not commissioned")
        readings = {
            "working_kg": round(water["working_kg"], 3),
            "normal_makeup_kg": state("inventory", "INV-WATER-NORMAL").quantity * 1000,
            "protected_reserve_kg": state("inventory", "INV-WATER-RESERVE").quantity * 1000,
            "potable_quarantined": water["potable_quarantined"],
            "quality_sample": water["quality_sample"],
            "hydrogen_outlets_verified": water["oxygen_outlet_verified"],
            "staged_purifier_filter_kg": water["filter_staged_kg"],
            "carried_filter_kg": water["filter_carried_kg"].get(actor.dbref, 0.0),
            "surveyed_here_kg": {
                source: rows.get(room, 0.0)
                for source, rows in water["source_surveys"].items()},
            "fixed_holding_kg": water["fixed"],
            "local_holding_kg": water["local"],
            "sealed_receivers_kg": water["cassettes"],
            "cumulative": water["cumulative"],
            "scope": "installed_local_water_and_waste_telemetry",
        }
        return readings
    if target == "cargo":
        if room not in {"CARGO-CTRL-FWD", "ENG-CONTROL"} and not (
                room and room.endswith("-FREIGHT-LOCK")):
            raise PermissionError("Freight manifest is local to a cargo station")
        cargo = _clock().details.get("cargo", {})
        return {
            "unlocated_onboard_kg": cargo.get("unlocated_onboard_kg"),
            "declared_lots": len(cargo.get("lots", {})),
            "active_jobs": dict(cargo.get("jobs", {})),
            "port_jobs": dict(cargo.get("port_jobs", {})),
            "docked_ports": dict(cargo.get("port_contacts", {})),
            "offship_kg": cargo.get("delivered_offship_kg", 0.0),
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
    if target == "drive_proof":
        _crew_at(actor, "PROP-CTRL")
        record = _clock().details.get("drive_proof") or initial_drive_proof()
        validate_drive_proof(record)
        return {"witness": record, "scope": "attended_measured_main_propulsion_run"}
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
def configure_water_casualty(*, operator=False, contaminated_kg=None):
    """Operator-only scenario contamination of already existing working water."""
    if not operator:
        raise PermissionError("Physical contamination injection is operator-only")
    item = _clock(lock=True)
    if item.details.get("water") is None:
        raise PhysicsError("Water/waste system not commissioned")
    if contaminated_kg is None:
        raise PhysicsError("Explicit finite contamination amount required")
    amount = _positive(contaminated_kg, zero=True)
    import copy
    w = copy.deepcopy(item.details["water"])
    if amount > w["working_kg"] + 1e-7:
        raise PhysicsError("Cannot contaminate more water than physically exists")
    before = _snapshot(item)
    w["suspected_contamination_kg"] = amount
    w["potable_quarantined"] = amount > 0
    w["reserve_released"] = False
    w["quality_sample"] = None
    w["quality_sample_tick"] = None
    d = dict(item.details)
    d["water"] = w
    item.details = d
    item.revision += 1
    item.save(update_fields=["details", "revision"])
    _event(item, "operator_water_contamination", before)
    return {"contaminated_kg": amount, "potable_quarantined": w["potable_quarantined"]}


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
        if cell_id in _clock().details.get("hull", {}).get("breaches", {}):
            raise PhysicsError("Registered hull breach requires finite physical repair")
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
