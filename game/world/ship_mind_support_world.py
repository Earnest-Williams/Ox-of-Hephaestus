"""Transactional world hardware fitting for the ship-control support plant.

No player/network principal is created, and fitting a fibre cannot remotely
operate a switch. The 147 new hardware rows live under their own model; the
legacy v0.5 ship and power registers are immutable reference authority.
"""
from __future__ import annotations

from world.ship_mind_power import MindPowerError
from world.ship_mind_support import (
    SCHEMA, connected_machines, proposed_support_rows, validate_support,
)


def install_control_support(world_state, support, power, ship):
    """World-clock caller owns the transaction; never overwrite prior rows."""
    specifications = proposed_support_rows(support, power, ship)
    required = {"equipment:" + machine["id"] for island in power["islands"]
                for machine in island["machines"]}
    machines = {row.key: row for row in world_state.objects.filter(
        key__in=sorted(required))}
    if set(machines) != required:
        raise MindPowerError("Fit nine physical compute terminals before their network")
    for name, row in machines.items():
        if row.source_model != power["schema_version"] or row.condition in {
                "failed","faulted","severed","destroyed"}:
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
