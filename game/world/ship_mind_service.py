"""Attended computer cooldown and restart, with finite auxiliary electricity.

The world adapter supplies real heat-rejection observations and binds evidence
to fitted hardware. A cooling-only machine is never a computing endpoint.
"""

from __future__ import annotations

import hashlib
import json
import math

from world.ship_mind_power import MindPowerError

SERVICE_KEY = "physics_mind_service"
AUXILIARY_KW = 0.05
PROOF_SECONDS = 30.0
RIDE_THROUGH_SECONDS = 120.0
MACHINE_IDS = frozenset(f"MIND-{n:02d}" for n in range(1, 10))


def service_state(row):
    """Read a bounded persisted local controller, preserving legacy stop latches."""
    details = getattr(row, "details", {}) or {}
    record = details.get(SERVICE_KEY)
    if record is None:
        return {
            "mode": "stopped" if details.get("physics_mind_thermal_trip") else "running",
            "verified_s": 0.0,
            "observed_s": None,
            "signature": None,
            "row_revision": getattr(row, "revision", 0),
        }
    if (
        not isinstance(record, dict)
        or set(record) != {"mode", "verified_s", "observed_s", "signature", "row_revision"}
        or not isinstance(record["mode"], str)
        or record["mode"] not in {"running", "cooldown", "stopped"}
        or type(record["verified_s"]) not in (int, float)
        or not math.isfinite(record["verified_s"])
        or not 0 <= record["verified_s"] <= PROOF_SECONDS
        or type(record["row_revision"]) is not int
        or record["row_revision"] < 0
        or (
            record["observed_s"] is not None
            and (
                type(record["observed_s"]) not in (int, float)
                or not math.isfinite(record["observed_s"])
                or record["observed_s"] < 0
            )
        )
        or (
            record["signature"] is not None
            and (
                not isinstance(record["signature"], str)
                or len(record["signature"]) != 64
                or any(c not in "0123456789abcdef" for c in record["signature"])
            )
        )
    ):
        raise MindPowerError("Corrupt computer service controller")
    return dict(record)


def thermal_trip_only(row):
    """A later hardware mutation cannot masquerade as the original trip."""
    details = getattr(row, "details", {}) or {}
    return bool(
        row.condition == "faulted"
        and details.get("physics_mind_thermal_trip") is True
        and type(details.get("physics_mind_trip_revision")) is int
        and details.get("physics_mind_trip_revision") == getattr(row, "revision", 0)
    )


def machine_mode(row):
    """Return only a physically admissible compute or auxiliary operating mode."""
    record = service_state(row)
    if record["row_revision"] != getattr(row, "revision", 0):
        return "stopped"
    if record["mode"] == "cooldown":
        return "cooldown" if row.condition == "serviceable" or thermal_trip_only(row) else "stopped"
    if record["mode"] == "running" and not (getattr(row, "details", {}) or {}).get(
        "physics_mind_thermal_trip"
    ):
        return "running"
    return "stopped"


def service_signature(rows, load_profile, pod):
    """Invalidate restart evidence when physical supply or cooling hardware changes.

    Compute-controller bookkeeping is excluded: several computers may cool at
    once. Each controller separately binds its own equipment revision.
    """
    networks = {
        "power",
        "mind_power",
        "mind_lt",
        "lt_cooling",
        "g19_motor",
        "g19_motor_protected",
        "g19_local_dc",
        "g19_local_charger",
    }
    selected = {
        key
        for key, row in rows.items()
        if row.category in {"node", "edge", "isolator"} and row.reference.get("network") in networks
    }
    owners = {rows[key].reference.get("owner_id") for key in selected}
    owners.update(
        {
            "GEN-M",
            "GEN-A",
            "GEN-B",
            "LT-PLANT",
            "ROT-LT-COOLING-A",
            "ROT-LT-COOLING-B",
            *(f"RAD-LT-{n}" for n in range(1, 5)),
            pod["independent_buffer_id"],
            pod["heat_rejector_id"],
            *pod["individual_cold_plates"],
        }
    )
    records = []
    for key, row in sorted(rows.items()):
        if row.category == "equipment" and row.source_id in MACHINE_IDS:
            continue
        if key not in selected and not (row.category == "equipment" and row.source_id in owners):
            continue
        details = getattr(row, "details", {}) or {}
        records.append(
            (
                key,
                row.revision,
                row.condition,
                row.setting,
                details.get("physics_online"),
                details.get("physics_commanded_on"),
                details.get("physics_startup_s"),
            )
        )
    return hashlib.sha256(
        json.dumps([load_profile, records], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def changed_service(row, mode, *, verified_s=0.0, observed_s=None, signature=None):
    """Build the next controller state for one actual equipment revision."""
    return {
        "mode": mode,
        "verified_s": verified_s,
        "observed_s": observed_s,
        "signature": signature,
        "row_revision": row.revision + 1,
    }


def advance_cooldown(row, *, seconds, now_s, good, hazardous, signature):
    """Accumulate consecutive measured seconds; never reset a thermal inventory."""
    if type(seconds) not in (int, float) or not 0 < seconds <= 10:
        raise MindPowerError("Unbounded computer cooldown timestep")
    previous = service_state(row)
    if previous["mode"] != "cooldown":
        return None
    if hazardous or machine_mode(row) != "cooldown":
        return changed_service(row, "stopped")
    consecutive = previous["observed_s"] == now_s - seconds and previous["signature"] == signature
    verified = (
        min(PROOF_SECONDS, (previous["verified_s"] if consecutive else 0) + seconds) if good else 0
    )
    return changed_service(
        row, "cooldown", verified_s=verified, observed_s=now_s, signature=signature
    )


def request_service(row, command, *, now_s, signature, pod, bank, temperature_k):
    """Validate the physical recovery sequence; the adapter checks crew authority."""
    previous = service_state(row)
    if command == "stop":
        return changed_service(row, "stopped")
    if command == "cooldown":
        if row.condition != "serviceable" and not thermal_trip_only(row):
            raise MindPowerError("Repair physical damage before computer cooldown")
        return changed_service(row, "cooldown")
    if command != "restart":
        raise MindPowerError("Computer service requires cooldown, restart or stop")
    if (
        machine_mode(row) != "cooldown"
        or previous["verified_s"] < PROOF_SECONDS
        or previous["observed_s"] != now_s
        or previous["signature"] != signature
        or not bank["surveyed"]
        or bank["free_kj"] < pod["heat_rate_kw"] * RIDE_THROUGH_SECONDS
        or not pod["normal_temperature_min_k"] <= temperature_k < pod["normal_temperature_max_k"]
    ):
        raise MindPowerError(
            "Restart needs fresh measured cooling and recovered two-minute headroom"
        )
    return changed_service(row, "running")
