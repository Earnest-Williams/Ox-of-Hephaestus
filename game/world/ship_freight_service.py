"""Attended service routes into nine *existing* freight enclosures on the Ox.

They serve thirteen real machines. These are fixed, already-authored openings,
not new personnel corridors, transporter shortcuts or cargo-transfer grants.
A live permit keeps freight drives/motion inhibited until the working party
and any repair jobs have cleared the service enclosure.
"""
from __future__ import annotations

import copy
import math

SCHEMA = "ox.g19.freight-service/1"

# (accessible control side, served equipment room, original passage kind,
#  original rated pressure boundary, stopped rotor where applicable).
GATES = {
    **{
        f"ACC-DR-{n:02d}-FREIGHT-LOCK-LOGI": (
            f"LOGI-STOP-DR-{n:02d}", f"DR-{n:02d}-FREIGHT-LOCK",
            "freight_branch_tunnel", True, f"DR-{n:02d}")
        for n in range(1, 7)
    },
    "ACC-WR-SPARES-MATERIAL": (
        "SPARES-CENTRAL", "MATERIAL-STOCK", "freight_door", False, "WR-01"),
    "ACC-LOGI-STOP-HAB-HUB-SERVICES-MAIN": (
        "LOGI-STOP-HAB-HUB-SERVICES", "LOGI-HAB-HUB-SERVICES",
        "freight_gate", False, None),
    "ACC-WR-FREIGHT-STAGING": (
        "LOGI-STOP-HAB-HUB-SERVICES", "WR-FREIGHT-STAGING",
        "freight_door", True, "WR-01"),
}

# Original fitted equipment and its *actual* owning room. Never relocate an
# equipment row or manufacture an extra station to make it reachable.
WORKSITES = {
    **{
        f"DR-{n:02d}-FREIGHT-COLLAR":
            (f"DR-{n:02d}-FREIGHT-LOCK",
             f"ACC-DR-{n:02d}-FREIGHT-LOCK-LOGI")
        for n in range(1, 7)
    },
    "IND-SCRAP-HOLD-B": ("MATERIAL-STOCK", "ACC-WR-SPARES-MATERIAL"),
    "LP-MATERIAL-STOCK": ("MATERIAL-STOCK", "ACC-WR-SPARES-MATERIAL"),
    **{
        f"LOGI-SLED-{n:02d}": (
            "LOGI-HAB-HUB-SERVICES",
            "ACC-LOGI-STOP-HAB-HUB-SERVICES-MAIN")
        for n in range(1, 5)
    },
    "WR-HEAVY-LOCK": ("WR-FREIGHT-STAGING", "ACC-WR-FREIGHT-STAGING"),
}

QUALIFIED_ROLES = frozenset({"watch_engineer", "chief_engineer", "cargo_officer"})


class FreightServiceError(ValueError):
    """A service permit would bypass an installed physical interlock."""


def verify_as_built(candidate):
    """Check original 0.5 spaces, equipment and links, without modifying them."""
    spaces = {row["id"]: row for row in candidate["spaces"]}
    links = {row["id"]: row for row in candidate["access_links"]}
    equipment = {row["id"]: row for row in candidate["equipment"]}
    if len(GATES) != 9 or len(WORKSITES) != 13:
        raise FreightServiceError("Fitted service inventory has drifted")
    for ident, (control, site, kind, boundary, rotor) in GATES.items():
        entry = links.get(ident)
        a, b = spaces.get(control), spaces.get(site)
        if (entry is None or a is None or b is None
                or (entry["from"], entry["to"], entry["kind"],
                    entry["pressure_boundary"]) !=
                   (control, site, kind, boundary)
                or a["frame"] != b["frame"]
                or not all(isinstance(room["pressure_zone"], str)
                           and room["pressure_zone"].startswith("PZ-")
                           for room in (a, b))
                or rotor is not None and rotor not in
                   {"WR-01", *(f"DR-{n:02d}" for n in range(1, 7))}):
            raise FreightServiceError("No verified rated service passage: " + ident)
    for name, (room, gate) in WORKSITES.items():
        if (name not in equipment or equipment[name]["space_id"] != room
                or gate not in GATES or GATES[gate][1] != room):
            raise FreightServiceError("Unfitted service equipment: " + name)
    return True


def initial_service_access():
    return {"schema": SCHEMA, "secured_links": [],
            "releases_completed": 0}


def validate_service_access(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"schema", "secured_links",
                               "releases_completed"}
            or ledger["schema"] != SCHEMA
            or not isinstance(ledger["secured_links"], list)
            or ledger["secured_links"] != sorted(set(ledger["secured_links"]))
            or not set(ledger["secured_links"]) <= set(GATES)
            or type(ledger["releases_completed"]) is not int
            or ledger["releases_completed"] < 0):
        raise FreightServiceError("Unknown or corrupt freight service custody")
    return True


def service_command(ledger, gate, verb):
    """Pure transition; runtime must verify actual site before it changes."""
    validate_service_access(ledger)
    if gate not in GATES or verb not in {"open", "close"}:
        raise FreightServiceError("No installed or supported service hatch")
    updated = copy.deepcopy(ledger)
    open_now = gate in updated["secured_links"]
    if verb == "open":
        if open_now:
            raise FreightServiceError("Service hatch already secured for entry")
        updated["secured_links"].append(gate)
        updated["secured_links"].sort()
    else:
        if not open_now:
            raise FreightServiceError("Service hatch is not in maintenance custody")
        updated["secured_links"].remove(gate)
        updated["releases_completed"] += 1
    validate_service_access(updated)
    return updated


def secured(ledger):
    """Fail closed before explicit commissioning."""
    if ledger is None:
        return False
    validate_service_access(ledger)
    return bool(ledger["secured_links"])


def service_hardware_ready(gate, *, rotors, cargo, water, motion):
    """Require genuine stationary hardware and zero active cargo movements.

    This test is repeated at permit issue, movement and every repair tick:
    a stale receipt or a later casualty never implies continuing clearance.
    """
    if gate not in GATES:
        return False
    if (not isinstance(cargo, dict) or not isinstance(motion, dict)
            or not isinstance(rotors, dict)
            or cargo.get("jobs") or cargo.get("port_jobs")
            or cargo.get("port_contacts")
            or (water or {}).get("waste_offload", {}).get("jobs")
            or motion.get("command") != "coast"
            or motion.get("attitude_command") != "hold"
            or (motion.get("ftl_leg") or {}).get("status") == "engaged"):
        return False
    rotor_id = GATES[gate][4]
    if rotor_id is None:
        return True
    rotor = rotors.get(rotor_id)
    if not isinstance(rotor, dict):
        return False
    rpm = rotor.get("rpm")
    target = rotor.get("target_rpm")
    return bool(
        type(rpm) in (float, int) and type(target) in (float, int)
        and math.isfinite(rpm) and math.isfinite(target)
        and abs(rpm) < 0.001 and target == 0
        and rotor.get("hardlock") is True
        and rotor.get("brake") is True
        and not rotor.get("indexing")
        and not rotor.get("freight_collar")
        and not rotor.get("passenger_indexer")
        and rotor.get("condition") in {"serviceable", "worn"}
    )
