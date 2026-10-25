"""G19 commercial-port handling for the six installed Ox cargo drums.

The internal 50/100-t sled spine is not an external bulk loader. A separate
operator-commissioned physical port contact allows the drum's authored P1/P2
portal and radial freight machinery to handle large commercial consignments.

Every 10-second tick transfers a finite quantity. Until a cycle completes,
part of a lot is aboard and part is offship; its full mass is conserved.
The port is not a second magic cargo reserve or a crew-access shortcut.
"""
from __future__ import annotations

import math
import re

from world.ship_cargo_manifest import (
    CargoError, DRUMS, MAX_LOTS, _lot_id, _mass, onboard_mass_kg,
)

PORTALS = tuple(f"{drum}-P{n}" for drum in DRUMS for n in (1, 2))
PORT_RATE_KG_S = 1500.0
PORT_START_SECONDS = 60.0
PORT_AUX_MW = 0.18
PORT_VERSION = "ox.g19.commercial-port/1"


def _portal(identifier):
    if identifier not in PORTALS:
        raise CargoError("Not an installed commercial loading portal")
    return identifier


def _berth(identifier):
    if (not isinstance(identifier, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", identifier) is None):
        raise CargoError("External berth must have an independently commissioned ID")
    return identifier


def port_drum(portal_id):
    return _portal(portal_id)[:5]


def port_fields():
    return {
        "port_contract_version": PORT_VERSION,
        "port_contacts": {},
        "port_jobs": {},
        "registered_external_kg": 0.0,
    }


def contacts_active(manifest):
    return any(row.get("docked", False)
               for row in manifest.get("port_contacts", {}).values())


def port_job_effective_kg(manifest, lot_id, *, aboard):
    """Current onboard/offship fractions; supports in-progress transfer."""
    lot = manifest["lots"][lot_id]
    initial = lot["mass_kg"] if lot["location"] != "OFFSHIP" else 0.0
    for job in manifest.get("port_jobs", {}).values():
        if job["lot_id"] != lot_id:
            continue
        initial += (1 if job["direction"] == "load" else -1) * job["transferred_kg"]
    return initial if aboard else lot["mass_kg"] - initial


def commission_port_contact(manifest, *, portal_id, berth_id, docked):
    """Explicit outside-world docking evidence; no model-created station."""
    _portal(portal_id)
    _berth(berth_id)
    if not isinstance(docked, bool):
        raise CargoError("Port contact must explicitly dock or undock")
    rows = dict(manifest.get("port_contacts", {}))
    if docked:
        existing = rows.get(portal_id)
        if existing is not None and existing["berth_id"] != berth_id:
            raise CargoError("Another berth is already connected at this port")
        rows[portal_id] = {"berth_id": berth_id, "docked": True}
    else:
        if any(job["portal_id"] == portal_id
               for job in manifest.get("port_jobs", {}).values()):
            raise CargoError("Port cannot undock with cargo in the transfer machinery")
        if portal_id not in rows or rows[portal_id]["berth_id"] != berth_id:
            raise CargoError("No such external berth is moored at this portal")
        del rows[portal_id]
    result = dict(manifest)
    result["port_contacts"] = rows
    return result


def register_external_consignment(manifest, *, lot_id, mass_kg, portal_id,
                                  kind="bulk", source_reference):
    """Record actual port-side cargo as an external consignment, never ship cargo.

    Only an approved world operator may call this via the canonical clock.
    """
    _lot_id(lot_id)
    mass = _mass(mass_kg)
    _portal(portal_id)
    _berth(source_reference)
    if kind not in {"bulk", "sled"}:
        raise CargoError("Unsupported external commercial cargo packaging")
    if len(manifest["lots"]) >= MAX_LOTS or lot_id in manifest["lots"]:
        raise CargoError("Duplicate or oversized commercial manifest")
    contact = manifest.get("port_contacts", {}).get(portal_id)
    if not contact or contact.get("berth_id") != source_reference:
        raise CargoError("Consignment source is not the connected external berth")
    if kind == "sled" and mass > 100_000:
        raise CargoError("Freight sled exceeds its rated 100-tonne envelope")
    result = dict(manifest)
    result["lots"] = {k: dict(v) for k, v in manifest["lots"].items()}
    result["lots"][lot_id] = {
        "mass_kg": mass, "drum": port_drum(portal_id), "location": "OFFSHIP",
        "kind": kind, "azimuth_rad": 0.0, "radius_m": 0.0,
        "restrained": False, "external_source": source_reference,
    }
    result["registered_external_kg"] = (
        result.get("registered_external_kg", 0.0) + mass)
    result["delivered_offship_kg"] = (
        result.get("delivered_offship_kg", 0.0) + mass)
    return result


def start_port_job(manifest, rotors, *, lot_id, portal_id, direction,
                   capacity_kg, equipment_ready, inner_gate_sealed):
    """Start, not complete, a berth-bound bulk loading/unloading cycle."""
    _portal(portal_id)
    if direction not in {"load", "unload"} or lot_id not in manifest["lots"]:
        raise CargoError("Unknown cargo lot or port transfer direction")
    contact = manifest.get("port_contacts", {}).get(portal_id)
    if not contact or not contact["docked"]:
        raise CargoError("External berth has not been positively connected")
    drum = port_drum(portal_id)
    rotor = rotors[drum]
    if (not equipment_ready or not inner_gate_sealed or
            not rotor["hardlock"] or not rotor["brake"] or
            rotor["target_rpm"] != 0 or abs(rotor["rpm"]) > 0.001 or
            rotor["passenger_indexer"] or rotor["freight_collar"]):
        raise CargoError("Port machinery, gallery seal or drum hardlock unavailable")
    if any(port_drum(job["portal_id"]) == drum
           for job in manifest.get("port_jobs", {}).values()):
        raise CargoError("Drum's single bulk handler already occupied")
    if drum in manifest["jobs"]:
        raise CargoError("Cannot share radial handler with an internal sled job")
    lot = manifest["lots"][lot_id]
    if any(job["lot_id"] == lot_id
           for job in manifest.get("port_jobs", {}).values()):
        raise CargoError("Cargo is already on a commercial loading rail")
    if direction == "unload":
        if lot["drum"] != drum or lot["location"] != drum or not lot["restrained"]:
            raise CargoError("Unload requires an identified secured lot in this drum")
    else:
        if lot["location"] != "OFFSHIP":
            raise CargoError("Load must draw from a registered offship consignment")
        if lot.get("external_source") != contact["berth_id"]:
            raise CargoError("External cargo is held at a different berth")
        if (not math.isfinite(capacity_kg) or capacity_kg <= 0):
            raise CargoError("Unknown ship commercial cargo capacity")
        committed = sum(job["remaining_kg"]
                        for job in manifest.get("port_jobs", {}).values()
                        if job["direction"] == "load")
        if onboard_mass_kg(manifest) + lot["mass_kg"] + committed > capacity_kg + 0.001:
            raise CargoError("Inbound consignment would overload commercial capacity")
    result = dict(manifest)
    result["port_jobs"] = {k: dict(v) for k, v in
                           manifest.get("port_jobs", {}).items()}
    result["port_jobs"][portal_id] = {
        "lot_id": lot_id, "portal_id": portal_id, "direction": direction,
        "remaining_kg": lot["mass_kg"], "transferred_kg": 0.0,
        "startup_remaining_s": PORT_START_SECONDS,
        "berth_id": contact["berth_id"],
        "paused": False, "reversing": False,
    }
    return result


def command_port_job(manifest, *, portal_id, lot_id, command):
    """Pause, restart or physically reverse an already started port transfer.

    Abort is an order to recover material *through the same handling rail*.
    It never deletes a part-loaded job or changes cargo mass instantly.
    """
    _portal(portal_id)
    if command not in {"pause", "resume", "abort"}:
        raise CargoError("Unknown commercial-port recovery operation")
    current = manifest.get("port_jobs", {}).get(portal_id)
    if current is None or current["lot_id"] != lot_id:
        raise CargoError("No such active cargo cycle at this portal")
    result = dict(manifest)
    result["port_jobs"] = {k: dict(v) for k, v in
                           manifest["port_jobs"].items()}
    job = result["port_jobs"][portal_id]
    if command == "pause":
        job["paused"] = True
    elif command == "resume":
        if job.get("reversing", False):
            raise CargoError("Recovery reversal cannot be cancelled by resume")
        job["paused"] = False
    else:
        if not job.get("reversing", False):
            job["reversing"] = True
            job["startup_remaining_s"] = PORT_START_SECONDS
        job["paused"] = False
    return result


def step_port_jobs(manifest, dt, *, available_portals, capacity_kg):
    """Conservatively integrate only hardware-ready and powered port jobs.

    Loss of contact, power, machinery or interlocks pauses existing progress;
    no amount moves when the job cannot physically advance. The caller may
    pass any subset of ready portals to represent finite electrical dispatch.
    """
    if (isinstance(dt, bool) or not isinstance(dt, (float, int)) or
            not math.isfinite(dt) or dt < 0 or dt > 60):
        raise CargoError("Invalid bounded commercial loading tick")
    if not math.isfinite(capacity_kg) or capacity_kg < 0:
        raise CargoError("Invalid remaining ship cargo capacity")
    result = dict(manifest)
    result["lots"] = {k: dict(v) for k, v in manifest["lots"].items()}
    result["port_jobs"] = {k: dict(v) for k, v in
                           manifest.get("port_jobs", {}).items()}
    completed = []
    for portal_id, job in sorted(list(result["port_jobs"].items())):
        if portal_id not in available_portals or job.get("paused", False):
            continue
        contact = result.get("port_contacts", {}).get(portal_id)
        if not contact or not contact.get("docked") or contact["berth_id"] != job["berth_id"]:
            continue
        wait = job["startup_remaining_s"]
        job["startup_remaining_s"] = max(0.0, wait - dt)
        working_seconds = max(0.0, dt - wait)
        if job.get("reversing", False):
            # The outbound/inbound stream is pumped back to its original
            # inventory. A casualty or blackout suspends the reversal too.
            amount = min(job["transferred_kg"],
                         working_seconds * PORT_RATE_KG_S)
            job["transferred_kg"] = max(0.0, job["transferred_kg"] - amount)
            job["remaining_kg"] += amount
            if job["transferred_kg"] <= 0.000001:
                completed.append((portal_id, job["lot_id"], "recovered"))
                del result["port_jobs"][portal_id]
            continue
        amount = min(job["remaining_kg"], working_seconds * PORT_RATE_KG_S)
        if job["direction"] == "load":
            amount = min(amount, max(0.0, capacity_kg - onboard_mass_kg(result)))
        job["remaining_kg"] = max(0.0, job["remaining_kg"] - amount)
        job["transferred_kg"] += amount
        if job["remaining_kg"] <= 0.000001:
            lot = result["lots"][job["lot_id"]]
            if job["direction"] == "load":
                lot["drum"] = port_drum(portal_id)
                lot["location"] = lot["drum"]
                lot["restrained"] = False
                lot["radius_m"] = 0.0
                lot["azimuth_rad"] = 0.0
                result["verified_drums"] = [
                    d for d in result["verified_drums"] if d != lot["drum"]
                ]
            else:
                lot["location"] = "OFFSHIP"
                lot["external_source"] = job["berth_id"]
                lot["restrained"] = False
                lot["radius_m"] = 0.0
                lot["azimuth_rad"] = 0.0
            completed.append((portal_id, job["lot_id"], job["direction"]))
            del result["port_jobs"][portal_id]
    outside = (result["reference_departure_kg"] +
               result.get("registered_external_kg", 0.0) -
               onboard_mass_kg(result))
    result["delivered_offship_kg"] = max(0.0, outside)
    return result, tuple(completed)


def port_power_mw(portals):
    return PORT_AUX_MW * len(portals)
