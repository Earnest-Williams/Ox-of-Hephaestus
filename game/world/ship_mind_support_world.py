"""Transactional world hardware fitting for the ship-control support plant.

No player/network principal is created, and fitting a fibre cannot remotely
operate a switch. The 153 support rows and optional 15 LT connection rows
live under their own model; the
legacy v0.5 ship and power registers are immutable reference authority.
"""

from __future__ import annotations

from world.ship_mind_power import MindPowerError
from world.ship_mind_support import (
    SCHEMA,
    connected_machines,
    proposed_heat_connection_rows,
    proposed_support_rows,
    validate_support,
)


def install_control_support(world_state, support, power, ship, *, initial_install=True):
    """World-clock caller owns the transaction; never overwrite prior rows."""
    specifications = proposed_support_rows(support, power, ship)
    required = {"equipment:" + machine["id"] for island in power["islands"]
                for machine in island["machines"]}
    host_id=support["gateway_candidates"][0]["host_equipment"]
    source_required=set(required)|{"equipment:"+host_id}
    machines = {row.key: row for row in world_state.objects.filter(
        key__in=sorted(source_required))}
    if set(machines) != source_required:
        raise MindPowerError("Fit nine physical compute terminals and the original local gateway host")
    host=machines["equipment:"+host_id]
    if (
        host.reference.get("kind") != "local_control_station"
        or host.space_id != support["gateway_candidates"][0]["room"]
        or (initial_install and host.condition in {"failed", "faulted", "severed", "destroyed"})
    ):
        raise MindPowerError("Original local control station has no healthy fitted host")
    for name in sorted(required):
        row=machines[name]
        if row.source_model != power["schema_version"] or (
            initial_install and row.condition in {"failed", "faulted", "severed", "destroyed"}
        ):
            raise MindPowerError("Network terminal has no verified fitted compute unit: " + name)
    created = 0
    for key, expected in sorted(specifications.items()):
        row, added = world_state.objects.get_or_create(key=key, defaults=expected)
        if not added and not (row.source_model == SCHEMA and
                              row.category == expected["category"] and
                              row.source_id == expected["source_id"] and
                              row.space_id == expected["space_id"] and
                              row.reference == expected["reference"]):
            raise MindPowerError("Previously fitted support identity drift: "+key)
        created += int(added)
    return {"created":created, "total":len(specifications),
            "rail_spans":44,"compute_drops":18,
            "independent_thermal_buffers":5}


def installed_support_rows(world_state, support, power, ship):
    """Exact world rows; no hardcoded concept of 'healthy' for missing kit."""
    expected = proposed_support_rows(support,power,ship)
    found = {row.key:row for row in world_state.objects.filter(
        key__in=list(expected))}
    if set(found) != set(expected):
        raise MindPowerError("Commissioned ship-control hardware is missing")
    for key, spec in expected.items():
        item=found[key]
        if (item.source_model != SCHEMA or item.category != spec["category"] or
            item.source_id != spec["source_id"] or
            item.space_id != spec["space_id"] or
            item.reference != spec["reference"]):
            raise MindPowerError("Ship-control cable or apparatus provenance altered: "+key)
    return found


def installed_network_cohort(world_state, support, power, ship, *, machines):
    rows=installed_support_rows(world_state,support,power,ship)
    return connected_machines(support,available_machines=set(machines),
                              physical_rows=rows)


def install_heat_connections(world_state, support, power, ship):
    """Explicitly fit additional closed-valve LT circuits, never repair old ones."""
    installed_support_rows(world_state, support, power, ship)
    specifications = proposed_heat_connection_rows(support, power, ship)
    created = 0
    metadata_updates = []
    for key, expected in sorted(specifications.items()):
        row, added = world_state.objects.get_or_create(key=key, defaults=expected)
        if (
            not added
            and row.category == "isolator"
            and all(
                getattr(row, field) == expected[field]
                for field in ("source_model", "category", "source_id", "space_id")
            )
        ):
            legacy = dict(expected["reference"])
            legacy.pop("manual_operation", None)
            if row.reference == legacy:
                before = {
                    "reference": row.reference,
                    "revision": row.revision,
                    "condition": row.condition,
                    "setting": row.setting,
                }
                row.reference = expected["reference"]
                row.revision += 1
                row.save(update_fields=["reference", "revision"])
                metadata_updates.append(
                    {
                        "key": key,
                        "before": before,
                        "after": {"reference": row.reference, "revision": row.revision},
                    }
                )
        if not added and any(
            getattr(row, field) != expected[field]
            for field in ("source_model", "category", "source_id", "space_id", "reference")
        ):
            raise MindPowerError("Thermal connection identity drift: " + key)
        created += int(added)
    return {"created": created, "total": len(specifications), "metadata_updates": metadata_updates}


def installed_heat_connection_rows(world_state, support, power, ship):
    """Validate exact as-fitted coolant provenance separately from original LT."""
    specifications = proposed_heat_connection_rows(support, power, ship)
    found = {row.key: row for row in world_state.objects.filter(key__in=list(specifications))}
    if set(found) != set(specifications):
        raise MindPowerError("Commissioned local LT circuit is missing")
    for key, expected in specifications.items():
        if any(
            getattr(found[key], field) != expected[field]
            for field in ("source_model", "category", "source_id", "space_id", "reference")
        ):
            raise MindPowerError("Local LT circuit provenance changed: " + key)
    return found
