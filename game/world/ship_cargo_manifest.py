"""Conservative world-owned cargo and freight-transfer ledger for Ox G19.

The v0.5 commercial cargo reference is *on board*, but its placement is NOT
specified by the ship source. Never infer six identical loads, or teleport a
900,000-tonne shipment through the 50-tonne freight spine. Explicit operator
survey assigns existing cargo to locations; crew may then perform timed,
interlocked physical transfers. The pure state machine performs no I/O.
"""
from __future__ import annotations

import math
import re

DRUMS = tuple(f"DR-{i:02d}" for i in range(1, 7))
SCHEMA = "ox.g19.cargo/1"
MAX_LOTS = 2048
ROUTINE_SLED_KG = 50_000.0
RESTRICTED_SLED_KG = 100_000.0
CARGO_TRANSFER_MW = 0.09
SLED_START_SECONDS = 30.0
SLED_RATE_KG_S = 1200.0
MAX_STOWAGE_RADIUS_M = 80.0
BALANCE_LIMIT_KG_M = 15_000.0


class CargoError(ValueError):
    """Invalid manifest, unsafe mechanism, or unproved conservation."""


def _mass(amount, *, zero=False):
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise CargoError("Cargo mass must be a physical number")
    value = float(amount)
    if not math.isfinite(value) or value < 0 or (value == 0 and not zero):
        raise CargoError("Cargo mass must be finite and nonnegative")
    return value


def _lot_id(identifier):
    if not isinstance(identifier, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", identifier) is None:
        raise CargoError("Manifest lot ID must be 1-48 ASCII letters/digits/underscore/dash")
    return identifier


def initial_cargo(reference_kg):
    """Undistributed reference is actual aboard mass, NOT an empty freighter."""
    amount = _mass(reference_kg)
    return {
        "schema": SCHEMA,
        "reference_departure_kg": amount,
        "unlocated_onboard_kg": amount,
        "lots": {},
        "verified_drums": [],
        "jobs": {},
        "delivered_offship_kg": 0.0,
        "port_contract_version": "ox.g19.commercial-port/1",
        "port_contacts": {},
        "port_jobs": {},
        "registered_external_kg": 0.0,
    }


def onboard_mass_kg(manifest):
    """In-flight commercial freight changes actual ship mass gradually."""
    onboard = (
        _mass(manifest["unlocated_onboard_kg"], zero=True) +
        sum(_mass(row["mass_kg"]) for row in manifest["lots"].values()
            if row["location"] != "OFFSHIP")
    )
    for job in manifest.get("port_jobs", {}).values():
        delta = float(job["transferred_kg"])
        onboard += delta if job["direction"] == "load" else -delta
    return onboard


def validate_cargo(manifest, motion_mass_kg):
    # Physical manifest extensions must be explicitly migrated: unknown JSON
    # fields are not a second authority for available onboard cargo.
    if (not isinstance(manifest, dict)
            or set(manifest) != set(initial_cargo(1.0))
            or manifest.get("schema") != SCHEMA):
        raise CargoError("Missing or unrecognised authoritative cargo schema")
    lots = manifest["lots"]
    if (not isinstance(lots, dict) or len(lots) > MAX_LOTS
            or not all(isinstance(manifest[key], dict) for key in
                       ("jobs", "port_contacts", "port_jobs"))
            or not isinstance(manifest["verified_drums"], list)
            or any(type(name) is not str for name in manifest["verified_drums"])):
        raise CargoError("Malformed cargo accounts or drum survey")
    lot_keys = {"mass_kg", "drum", "location", "kind", "azimuth_rad",
                "radius_m", "restrained"}
    for name, row in lots.items():
        _lot_id(name)
        if (not isinstance(row, dict)
                or not lot_keys <= set(row)
                or not set(row) <= lot_keys | {"external_source"}
                or row["kind"] not in {"bulk", "sled"}):
            raise CargoError("Malformed or unrecognised cargo lot fields")
        _mass(row["mass_kg"])
        origin = row["drum"]
        if origin not in DRUMS:
            raise CargoError("Unknown original drum")
        if row["location"] not in {
                origin, origin + "-FREIGHT-LOCK", "SPINE-FREIGHT", "OFFSHIP"}:
            raise CargoError("Unknown physical freight station")
        if not (math.isfinite(row["radius_m"]) and
                0 <= row["radius_m"] <= MAX_STOWAGE_RADIUS_M and
                math.isfinite(row["azimuth_rad"])):
            raise CargoError("Invalid stowage geometry")
        if not isinstance(row["restrained"], bool):
            raise CargoError("Unknown physical restraint")
    verified = set(manifest["verified_drums"])
    if not verified.issubset(DRUMS):
        raise CargoError("Invalid drum survey authority")
    if verified == set(DRUMS) and manifest["unlocated_onboard_kg"] > 0.001:
        raise CargoError("Six verified drums cannot leave commercial cargo unlocated")
    if (not math.isclose(onboard_mass_kg(manifest), _mass(motion_mass_kg, zero=True),
                         rel_tol=1e-12, abs_tol=0.001)):
        raise CargoError("Cargo and vessel mass ledgers diverged")
    declared_plus_unknown = (
        _mass(manifest["unlocated_onboard_kg"], zero=True)
        + sum(_mass(v["mass_kg"]) for v in lots.values())
    )
    reference = _mass(manifest["reference_departure_kg"], zero=True)
    imported = _mass(manifest.get("registered_external_kg", 0.0), zero=True)
    if not math.isclose(
            declared_plus_unknown, reference + imported,
            rel_tol=1e-12, abs_tol=0.001):
        raise CargoError("Cargo created or erased outside an audited transfer")
    outside = reference + imported - onboard_mass_kg(manifest)
    if (outside < -0.001 or not math.isclose(
            outside, _mass(manifest["delivered_offship_kg"], zero=True),
            rel_tol=1e-12, abs_tol=0.001)):
        raise CargoError("Port custody and vessel mass ledgers diverged")
    contacts = manifest.get("port_contacts", {})
    port_jobs = manifest.get("port_jobs", {})
    if len(contacts) > 12 or len(port_jobs) > 6:
        raise CargoError("More commercial ports or handlers than installed")
    active_drums = set()
    active_lots = set()
    for portal, job in port_jobs.items():
        if (not isinstance(job, dict)
                or not isinstance(portal, str) or
                re.fullmatch(r"DR-0[1-6]-P[12]", portal) is None or
                job.get("portal_id") != portal or
                job.get("direction") not in {"load", "unload"} or
                job.get("lot_id") not in lots):
            raise CargoError("Invalid installed commercial port transfer")
        drum = portal[:5]
        if (not isinstance(job.get("paused", False), bool)
                or not isinstance(job.get("reversing", False), bool)):
            raise CargoError("Commercial transfer control state invalid")
        if drum in manifest["jobs"]:
            raise CargoError("Commercial bulk and internal freight rail cannot overlap")
        if drum in active_drums or job["lot_id"] in active_lots:
            raise CargoError("Shared bulk machinery or cargo lot double-booked")
        active_drums.add(drum)
        active_lots.add(job["lot_id"])
        original = lots[job["lot_id"]]
        if (job["direction"] == "unload" and
                (original["drum"] != drum or original["location"] != drum)):
            raise CargoError("Outbound cargo is not in this drum")
        if job["direction"] == "load" and original["location"] != "OFFSHIP":
            raise CargoError("Inbound cargo has no external source")
        mass = _mass(original["mass_kg"])
        transferred = _mass(job.get("transferred_kg"), zero=True)
        remaining = _mass(job.get("remaining_kg"), zero=True)
        startup = _mass(job.get("startup_remaining_s"), zero=True)
        if (transferred > mass + 1e-6 or remaining > mass + 1e-6
                or not math.isclose(transferred + remaining, mass,
                                    rel_tol=1e-12, abs_tol=0.001)
                or startup > 60 or
                portal not in contacts or
                job.get("berth_id") != contacts[portal].get("berth_id")):
            raise CargoError("Physically impossible port transfer state")
    for portal, contact in contacts.items():
        if (not isinstance(portal, str) or
                re.fullmatch(r"DR-0[1-6]-P[12]", portal) is None or
                not isinstance(contact, dict) or
                contact.get("docked") is not True or
                not isinstance(contact.get("berth_id"), str)):
            raise CargoError("Invalid external mooring reference")
    if len(manifest["jobs"]) > len(DRUMS):
        raise CargoError("More concurrent freight operations than installed collars")
    for drum, job in manifest["jobs"].items():
        if (not isinstance(job, dict)
                or not {"lot_id", "remaining_s", "direction"} <= set(job)
                or drum not in DRUMS or job["lot_id"] not in lots):
            raise CargoError("Uninstalled freight transfer")
        if not math.isfinite(job["remaining_s"]) or job["remaining_s"] < 0:
            raise CargoError("Invalid transfer clock")
        if job.get("destination_drum", drum) != drum:
            raise CargoError("Transfer assigned to wrong physical collar")
        if job["direction"] not in {"to_lock", "to_drum", "to_spine", "from_spine"}:
            raise CargoError("Invalid freight direction")
    return True


def declare_cargo_lot(manifest, *, lot_id, mass_kg, drum,
                      azimuth_deg, radius_m, kind="bulk", restrained=True):
    """Explicit operator survey, *not* a loading transaction.

    This locates some existing, otherwise unpositioned reference mass.
    A declared bulk lot may be enormous but cannot fit a freight sled.
    """
    _lot_id(lot_id)
    mass = _mass(mass_kg)
    if (drum not in DRUMS or kind not in {"bulk", "sled"}
            or not isinstance(restrained, bool)
            or isinstance(azimuth_deg, bool)
            or not isinstance(azimuth_deg, (float, int))
            or not math.isfinite(azimuth_deg)
            or not 0 <= azimuth_deg < 360
            or isinstance(radius_m, bool)
            or not isinstance(radius_m, (float, int))
            or not math.isfinite(radius_m)
            or not 0 < radius_m <= MAX_STOWAGE_RADIUS_M):
        raise CargoError("Invalid drum, cargo class, restraint or stowage datum")
    if kind == "sled" and mass > RESTRICTED_SLED_KG:
        raise CargoError("Cargo sled exceeds the restricted 100-tonne limit")
    if len(manifest["lots"]) >= MAX_LOTS:
        raise CargoError("Manifest lot count exceeded")
    if lot_id in manifest["lots"] or mass > manifest["unlocated_onboard_kg"] + 1e-6:
        raise CargoError("Duplicate lot or more mass than the reference contains")
    result = dict(manifest)
    result["lots"] = dict(manifest["lots"])
    result["lots"][lot_id] = {
        "mass_kg": mass, "drum": drum, "location": drum,
        "kind": kind, "azimuth_rad": math.radians(azimuth_deg),
        "radius_m": float(radius_m), "restrained": restrained,
    }
    result["unlocated_onboard_kg"] = max(0.0, manifest["unlocated_onboard_kg"] - mass)
    return result


def split_cargo_lot(manifest, *, source_id, new_id, mass_kg):
    """Operator-recorded, physically observed package subdivision in place."""
    _lot_id(new_id)
    mass = _mass(mass_kg)
    if (source_id not in manifest["lots"] or new_id in manifest["lots"]
            or len(manifest["lots"]) >= MAX_LOTS):
        raise CargoError("Missing source, duplicate package or lot limit")
    source = manifest["lots"][source_id]
    if any(job["lot_id"] == source_id
           for job in manifest.get("port_jobs", {}).values()):
        raise CargoError("Cargo cannot be split during a commercial transfer")
    if (source["location"] != source["drum"]
            or source["kind"] != "bulk" or not source["restrained"]
            or mass >= source["mass_kg"] or mass > RESTRICTED_SLED_KG):
        raise CargoError("Source bulk cannot supply a verified movable sled")
    result = dict(manifest)
    result["lots"] = {k: dict(v) for k, v in manifest["lots"].items()}
    result["lots"][source_id]["mass_kg"] -= mass
    result["lots"][new_id] = {**source, "mass_kg": mass, "kind": "sled"}
    return result


def restow_cargo_lot(manifest, *, lot_id, azimuth_deg, radius_m):
    """Operator verifies secure berth after transfer; no teleportation."""
    if lot_id not in manifest["lots"]:
        raise CargoError("Unknown cargo to stow")
    lot = manifest["lots"][lot_id]
    if lot["location"] != lot["drum"]:
        raise CargoError("Package must be inside its drum")
    if (any(job["lot_id"] == lot_id for job in manifest["jobs"].values())
            or any(job["lot_id"] == lot_id
                   for job in manifest.get("port_jobs", {}).values())):
        raise CargoError("Cargo transfer still underway")
    if (isinstance(azimuth_deg, bool) or
            not isinstance(azimuth_deg, (int, float)) or
            not math.isfinite(azimuth_deg) or
            not 0 <= azimuth_deg < 360 or
            isinstance(radius_m, bool) or
            not isinstance(radius_m, (int, float)) or
            not math.isfinite(radius_m) or
            not 0 < radius_m <= MAX_STOWAGE_RADIUS_M):
        raise CargoError("Invalid surveyed cargo berth")
    result = dict(manifest)
    result["lots"] = {k: dict(v) for k, v in manifest["lots"].items()}
    result["lots"][lot_id]["radius_m"] = float(radius_m)
    result["lots"][lot_id]["azimuth_rad"] = math.radians(azimuth_deg)
    result["lots"][lot_id]["restrained"] = True
    return result


def unsecured_drum_loads(manifest, drum):
    return (
        any(row["drum"] == drum and row["location"] == drum
            and not row["restrained"]
            for row in manifest["lots"].values())
        or any(portal[:5] == drum
               for portal in manifest.get("port_jobs", {}))
    )


def verify_drum(manifest, drum):
    """Physical survey gate; operator asserts all *this* drum's loads known."""
    if drum not in DRUMS:
        raise CargoError("Unknown rotary cargo drum")
    if unsecured_drum_loads(manifest, drum):
        raise CargoError("Drum survey cannot pass during transfer or loose stowage")
    if ((set(manifest["verified_drums"]) | {drum}) == set(DRUMS)
            and manifest["unlocated_onboard_kg"] > 0.001):
        raise CargoError("Cannot certify all drums with missing stowage evidence")
    result = dict(manifest)
    result["verified_drums"] = sorted(set(manifest["verified_drums"]) | {drum})
    return result


def drum_balance(manifest, drum):
    """Stowage moment of surveyed lots; opposing placements cancel.

    A suspended job keeps the lot at its last confirmed location. Unknown
    reference mass is not silently distributed across six drums.
    """
    if drum not in DRUMS:
        raise CargoError("Unknown cargo drum")
    x = y = known = 0.0
    for lot_id, row in manifest["lots"].items():
        if row["drum"] != drum or row["location"] != drum:
            continue
        mass = row["mass_kg"]
        for job in manifest.get("port_jobs", {}).values():
            if job["lot_id"] == lot_id and job["direction"] == "unload":
                mass -= job["transferred_kg"]
        arm = mass * row["radius_m"]
        x += arm * math.cos(row["azimuth_rad"])
        y += arm * math.sin(row["azimuth_rad"])
        known += mass
    return {
        "known_cargo_kg": known,
        "imbalance_kg_m": math.hypot(x, y),
        "surveyed": drum in manifest["verified_drums"],
    }


def start_freight_transfer(manifest, rotors, *, lot_id, direction,
                           collar_healthy, gate_open=False, restricted=False,
                           destination_drum=None):
    """Begin a finite restrained-sled cycle; no immediate relocation."""
    if lot_id not in manifest["lots"]:
        raise CargoError("Unknown cargo lot")
    row = manifest["lots"][lot_id]
    drum = destination_drum if direction == "from_spine" and destination_drum else row["drum"]
    if drum not in DRUMS or (destination_drum is not None and direction != "from_spine"):
        raise CargoError("Invalid destination drum")
    rotor = rotors[drum]
    if drum not in manifest["verified_drums"]:
        raise CargoError("Drum cargo survey has not been verified")
    if any(portal[:5] == drum for portal in manifest.get("port_jobs", {})):
        raise CargoError("Commercial port handler is already operating in this drum")
    if any(job["lot_id"] == lot_id
           for job in manifest.get("port_jobs", {}).values()):
        raise CargoError("Lot is committed to external port transfer")
    # A parked, hardlocked drum must still permit removing cargo to CORRECT
    # a bad imbalance. The imbalance lockout belongs on spin-up, not on
    # restrained freight extraction while the drum is stationary.
    if (row["kind"] != "sled" or not row["restrained"]
            or row["mass_kg"] > (RESTRICTED_SLED_KG if restricted else ROUTINE_SLED_KG)):
        raise CargoError("Freight is unrestrained, oversize, or above sled rating")
    if not (rotor["hardlock"] and rotor["brake"] and
            abs(rotor["rpm"]) <= 0.001 and rotor["target_rpm"] == 0
            and rotor["freight_collar"] and not rotor["passenger_indexer"]
            and collar_healthy):
        raise CargoError("Freight collar, stopped alignment or machinery unavailable")
    moves = {
        "to_lock": (drum, drum + "-FREIGHT-LOCK"),
        "to_drum": (drum + "-FREIGHT-LOCK", drum),
        "to_spine": (drum + "-FREIGHT-LOCK", "SPINE-FREIGHT"),
        "from_spine": ("SPINE-FREIGHT", drum + "-FREIGHT-LOCK"),
    }
    if direction not in moves:
        raise CargoError("Invalid cargo transfer route")
    source, dest = moves[direction]
    if source != row["location"]:
        raise CargoError("Cargo is not at the source station")
    if direction == "to_drum" and not row["restrained"]:
        raise CargoError("Freight must remain secured for drum entry")
    if direction in {"to_spine", "from_spine"} and not gate_open:
        raise CargoError("Fixed pressure-rated freight capture is not open")
    if drum in manifest["jobs"]:
        raise CargoError("Freight collar is already handling another load")
    if direction in {"to_spine", "from_spine"}:
        if any(job["direction"] in {"to_spine", "from_spine"}
               for job in manifest["jobs"].values()):
            raise CargoError("Shared freight spine transfer station already occupied")
        if direction == "to_spine" and any(
                other["location"] == "SPINE-FREIGHT"
                for other in manifest["lots"].values()):
            raise CargoError("Freight spine receiving position occupied")
    result = dict(manifest)
    result["jobs"] = dict(manifest["jobs"])
    result["jobs"][drum] = {
        "lot_id": lot_id, "direction": direction, "destination": dest,
        "remaining_s": SLED_START_SECONDS + row["mass_kg"] / SLED_RATE_KG_S,
        "restricted": bool(restricted), "destination_drum": drum,
    }
    return result


def step_freight(manifest, dt, *, power_ready, available_collars,
                 open_fixed_gates=()):
    """Pause on power/door/actuator loss; relocate only at completed cycle."""
    if isinstance(dt, bool) or not isinstance(dt, (int, float)) or not math.isfinite(dt) or not 0 <= dt <= 60:
        raise CargoError("Invalid freight tick")
    result = dict(manifest)
    result["jobs"] = {k: dict(v) for k, v in manifest["jobs"].items()}
    result["lots"] = {k: dict(v) for k, v in manifest["lots"].items()}
    moved = []
    for drum, job in list(result["jobs"].items()):
        if (not power_ready or drum not in available_collars or
                (job["direction"] in {"to_spine", "from_spine"}
                 and drum not in open_fixed_gates)):
            continue
        job["remaining_s"] = max(0.0, job["remaining_s"] - dt)
        if job["remaining_s"] <= 1e-9:
            lot = result["lots"][job["lot_id"]]
            lot["location"] = job["destination"]
            if job["direction"] == "from_spine":
                lot["drum"] = drum
            if job["direction"] == "to_drum":
                # Arrival is not proof the package has been stowed or tied
                # down. Crew must physically certify its new berth first.
                lot["restrained"] = False
                lot["radius_m"] = 0.0
                lot["azimuth_rad"] = 0.0
            moved.append(job["lot_id"])
            del result["jobs"][drum]
    return result, tuple(moved)


def active_freight_mw(manifest):
    return CARGO_TRANSFER_MW * len(manifest["jobs"])
