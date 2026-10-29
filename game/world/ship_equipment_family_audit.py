"""Evidence-tier audit of ALL 808 fitted machines and 91 original families.

Classification is deliberately conservative:
- direct_physics: original equipment has current process/source/sensor/actuator
  logic, sometimes shared with the parent subsystem; NOT a blanket claim
  of individual performance acceptance.
- interface_or_custody: equipment is meaningful through real access,
  resource ownership, structural containment or a coupled mechanism; it
  is not a second independent motor/pressure cell.
- controlled_hardware: equipment has fitted state, electrical/gas/thermal
  or interlock dependencies, but a separate positive-effect demonstration
  may still be needed.
- open_interaction: equipment whose intended portable, mobile or independent
  operation still lacks a complete verified operator/physics contract.

No family can quietly disappear into an unreviewed generic default.
The report lists original IDs and installed rooms for every open item.
"""
from __future__ import annotations

from collections import Counter

from world.ship_auxiliary_electrical import MOTORS
from world.ship_cabin_fancoils import FANCOILS
from world.ship_equipment_services import SERVICE_LOADS
from world.ship_flywheel_maintenance import MODULES as FLYWHEEL_MODULES
from world.ship_instrumentation_world import original_panel_roster
from world.ship_refuge_life_support import REFUGE_PACKS
from world.ship_survival_craft_air import PACKS as SURVIVAL_CRAFT_PACKS
from world.ship_portable_air import STOWAGE as PORTABLE_CO2_PACKS
from world.ship_portable_damage import FITTED as PORTABLE_PUMP_FANS


class EquipmentFamilyAuditError(ValueError):
    """An original equipment identity, allocation or disposition drifted."""


DIRECT_PHYSICS = frozenset("""
air_handler bearing_lube_skid carbon_dioxide_recovery_skid
cargo_atmosphere_pack cargo_handler cargo_thermal_skid crop_process_skid
cultivation_controller dehumidifier emergency_life_support environmental_train
fabrication_cell fan_coil fire_pump flywheel_module ftl_field_system generator
indexed_drum_personnel_carrier indexer_drive linear_drive local_panel machine_tool
main_hab_drive oxygen_generation_skid rotor_drive thermal_plant waste_processor
water_processor survival_craft_life_support portable_pump portable_fan
portable_scrubber
""".split())

INTERFACE_OR_CUSTODY = frozenset("""
arc_end_pressure_hatch bridge_utility_sleeve damage_control_locker debris_shield
drum_freight_docking_collar fire_suppression_manifold freight_lock
hab_keyed_centre_saddle hab_repressurization_manifold hab_sliding_outer_saddle
indexer_docking_collar inert_makeup_storage interarc_pressure_spool
isolated_hazard_waste_cassette main_hab_bearing main_hab_brake manifold
receiver_manifold repressurization_header rotor_bearing sealed_waste_residue_receiver
segregated_byproduct_vent segregated_industrial_scrap_cassette tank_group
vacuum_receiver waste_receiver
""".split())

CONTROLLED_HARDWARE = frozenset("""
battery breathable_refill_gas_bank cabin_panel debris_sensor distribution_board
dust_ionizer emergency_scrubber eva_work_platform field_coils fire_detection_loop
freight_sled independent_indexer_carrier indexer inert_makeup_mixer
inert_makeup_regulator local_control_station local_fire_suppression oxygen_bank
personnel_cart process_water_unit protected_local_system radiator
repressurization_regulator repressurization_rotary_union rotary_fluid_interface
rotary_gas_interface rotary_power_interface shore_interface switchboard
trim_system workshop_rotor
""".split())

OPEN_INTERACTION = frozenset("""
eva_rail_crawler inspection_robot
""".split())

DISPOSITIONS = {
    "direct_physics": DIRECT_PHYSICS,
    "interface_or_custody": INTERFACE_OR_CUSTODY,
    "controlled_hardware": CONTROLLED_HARDWARE,
    "open_interaction": OPEN_INTERACTION,
}
if len(set.union(*(set(v) for v in DISPOSITIONS.values()))) != sum(
        len(v) for v in DISPOSITIONS.values()):
    raise EquipmentFamilyAuditError("Equipment family review classes overlap")


def audit_fitted_equipment(reference):
    if (not isinstance(reference, dict)
            or reference.get("model_version") != "0.5-candidate"
            or reference.get("schema_version") != "ox.ship-world/0.1"):
        raise EquipmentFamilyAuditError("Unknown ship inventory provenance")
    equipment = reference.get("equipment")
    rooms = {row["id"] for row in reference.get("spaces", ())}
    if not isinstance(equipment, list) or len(equipment) != 808:
        raise EquipmentFamilyAuditError("Original 808 physical equipment roster changed")
    seen = {}
    families = Counter()
    groups = {key: {"units": 0, "kinds": set()} for key in DISPOSITIONS}
    by_kind = {}
    open_items = []
    classifications = {}
    for row in equipment:
        if not isinstance(row, dict):
            raise EquipmentFamilyAuditError("Non-object installed equipment")
        name, kind, room = row.get("id"), row.get("kind"), row.get("space_id")
        if (not isinstance(name, str) or not name
                or not isinstance(kind, str) or not kind
                or name in seen or room not in rooms):
            raise EquipmentFamilyAuditError("Duplicate, displaced or unnamed machine")
        seen[name] = row
        categories = [status for status, kinds in DISPOSITIONS.items()
                      if kind in kinds]
        if len(categories) != 1:
            raise EquipmentFamilyAuditError(
                "Unreviewed or ambiguous original equipment family: " + kind)
        status = categories[0]
        families[kind] += 1
        groups[status]["units"] += 1
        groups[status]["kinds"].add(kind)
        by_kind.setdefault(kind, []).append(name)
        classifications[name] = status
        if status == "open_interaction":
            open_items.append({"id": name, "kind": kind, "space_id": room})
    if len(families) != 91:
        raise EquipmentFamilyAuditError("Original 91 as-fitted families changed")
    for name, roster, kind in (
            ("cabin_coils", set(FANCOILS), "fan_coil"),
            ("flywheel_modules", set(FLYWHEEL_MODULES), "flywheel_module"),
            ("local_panels", set(original_panel_roster(reference)[0]), "local_panel")):
        actual = {row["id"] for row in equipment if row["kind"] == kind}
        if actual != roster:
            raise EquipmentFamilyAuditError(
                "Original audited direct equipment identity drift: " + name)
    for source, label in ((MOTORS, "fitted_motors"),
                          (SERVICE_LOADS, "secondary_powered_services"),
                          (REFUGE_PACKS, "finite_refuge_air"),
                          (SURVIVAL_CRAFT_PACKS, "surveyed_independent_craft_air"),
                          (PORTABLE_CO2_PACKS, "original_finite_portable_co2"),
                          (PORTABLE_PUMP_FANS, "original_portable_pumps_and_fans")):
        for name in source:
            if name not in seen or classifications[name] != "direct_physics":
                raise EquipmentFamilyAuditError(
                    "Runtime contract lost its original equipment: " + label
                    + "/" + name)
    counts = {key: {"equipment": value["units"],
                    "families": len(value["kinds"])}
              for key, value in groups.items()}
    if sum(row["equipment"] for row in counts.values()) != 808:
        raise EquipmentFamilyAuditError("Missing or double-counted original machine")
    return {
        "model": "0.5-candidate", "equipment": 808, "families": 91,
        "dispositions": counts,
        "open_items": sorted(open_items, key=lambda x: x["id"]),
        "by_kind": {kind: {"count": families[kind],
                          "disposition": next(key for key, values in
                                              DISPOSITIONS.items()
                                              if kind in values),
                          "ids": sorted(by_kind[kind])}
                    for kind in sorted(families)},
    }
