"""G19 physical process-output evidence from the original fitted ship.

This is a meter of effects *already moved through actual media*, not a
second power availability oracle. An independent 10-second machine receipt
must be backed by a real air parcel, treated effluent, suppression discharge,
or a wetted bearing lubrication skid. Standby/brownout/idle equipment has
zero new verified output. Historical cumulative totals do not authorize a
new restart. No new machine, valve, sensor, material stock or room is made.
"""
from __future__ import annotations

import math

from world.ship_auxiliary_electrical import MOTORS, PROTECTED_FIRE_MOTORS

AIR_TRAINS = ("ECLSS-A", "ECLSS-B")
AIR_HANDLERS = tuple(f"HAB-{n:02d}-AHU" for n in range(1, 9))
SPINE_FANS = ("SPINE-AIR-FWD", "SPINE-AIR-AFT")
WATER_MACHINES = tuple(f"{kind}-{side}" for side in "AB"
                       for kind in ("WASTE-PROC", "WATER-PROC"))
BEARING_PUMPS = tuple(
    f"BE-{n:02d}-LUBE-{side}" for n in range(1, 13) for side in "NS")
# Metric names deliberately distinguish moving air from removing CO2.
METRICS = {
    **{x: "co2_captured_kg" for x in AIR_TRAINS},
    **{x: "forced_air_exchange_kg" for x in AIR_HANDLERS + SPINE_FANS},
    **{x: "treated_effluent_kg" for x in WATER_MACHINES},
    **{x: "suppression_delivered_kg" for x in PROTECTED_FIRE_MOTORS},
    **{x: "oil_recirculated_kg" for x in BEARING_PUMPS},
}
if not set(METRICS) <= set(MOTORS):
    raise RuntimeError("Positive-output source refers to a nonexistent motor")

FIELD = "physics_process_output"
# Lubrication oil is captive to the existing sealed bearing service skid,
# recirculating rather than getting created or exhausted per revolution.
LUBE_MAX_BAR = 4.0
LUBE_RISE_BAR_S = 0.4
LUBE_DECAY_BAR_S = 0.6
LUBE_FLOW_KG_S = 0.015
LUBE_MIN_BAR = 1.0
MAX_DT = 10.0
EPS = 1e-7


class ProcessOutputError(ValueError):
    """No current, bounded and attributable equipment output."""


def _nonnegative(value):
    if (type(value) not in (int, float)
            or not math.isfinite(value) or value < 0):
        raise ProcessOutputError("Invalid nonnegative physical machine quantity")
    return float(value)


def check_receipt(name, row):
    if name not in METRICS:
        raise ProcessOutputError("No fitted observable process for that motor")
    if (not isinstance(row, dict)
            or set(row) != {"metric", "amount", "total", "sample_s", "pressure_bar"}
            or row["metric"] != METRICS[name]):
        raise ProcessOutputError("Uncommissioned or mismatched output receipt")
    amount = _nonnegative(row["amount"])
    cumulative = _nonnegative(row["total"])
    _nonnegative(row["sample_s"])
    pressure = _nonnegative(row["pressure_bar"])
    if (amount > cumulative + EPS
            or pressure > (LUBE_MAX_BAR if name in BEARING_PUMPS else 0.0) + EPS):
        raise ProcessOutputError("Impossible process total or bearing gauge")
    if name in BEARING_PUMPS and amount > LUBE_FLOW_KG_S * MAX_DT + EPS:
        raise ProcessOutputError("Bearing oil loop exceeded its pump capacity")
    return True


def step_process_output(name, prior, *, dt_s, now_s, delivered_kg=0.0,
                        driven=False):
    """Persist one physics step of actual *attributed* media movement.

    Ordinary process motors receive their real media transaction quantity;
    lubrication skids have their own finite hydraulic pressure state, driven
    only by the fitted motor and sound on-site skid. Pressure bleeds down on
    source loss. This is circulating loop flow, not consumed oil mass.
    """
    if name not in METRICS:
        raise ProcessOutputError("Not an original process motor")
    dt = _nonnegative(dt_s)
    now = _nonnegative(now_s)
    moved = _nonnegative(delivered_kg)
    if (dt <= 0 or dt > MAX_DT or type(driven) is not bool):
        raise ProcessOutputError("Invalid bounded machine observation interval")
    if prior is not None:
        check_receipt(name, prior)
        if now <= prior["sample_s"] or now + EPS < prior["sample_s"] + dt:
            raise ProcessOutputError("Duplicate or reordered machine output sample")
        total = float(prior["total"])
        previous_pressure = float(prior["pressure_bar"])
    else:
        total, previous_pressure = 0.0, 0.0
    if name in BEARING_PUMPS:
        if moved != 0:
            raise ProcessOutputError("Cannot inject imaginary bearing-oil receipts")
        pressure = (min(LUBE_MAX_BAR, previous_pressure + LUBE_RISE_BAR_S * dt)
                    if driven else
                    max(0.0, previous_pressure - LUBE_DECAY_BAR_S * dt))
        # Flow is positively proven only through the powered and wetted skid.
        # Residual pressure after an outage is NOT credited as new output.
        moved = (LUBE_FLOW_KG_S * dt * pressure / LUBE_MAX_BAR
                 if driven and pressure >= LUBE_MIN_BAR else 0.0)
    else:
        if driven or previous_pressure:
            raise ProcessOutputError("Unsupported synthetic process or oil pressure")
        pressure = 0.0
    result = {
        "metric": METRICS[name], "amount": float(moved),
        "total": total + moved, "sample_s": now,
        "pressure_bar": float(pressure),
    }
    check_receipt(name, result)
    return result


def proves_process_output(name, details, *, observed_s):
    """A current genuinely moved medium; old cumulative output never counts."""
    if name not in METRICS or not isinstance(details, dict):
        return False
    row = details.get(FIELD)
    if row is None:
        return False
    check_receipt(name, row)
    now = _nonnegative(observed_s)
    return bool(abs(row["sample_s"] - now) <= EPS and row["amount"] > EPS)


def machine_depressurized(name, details):
    """Hands-on servicing of a lube skid requires a bled-down manifold."""
    if name not in BEARING_PUMPS:
        return True
    if not isinstance(details, dict):
        raise ProcessOutputError("No physical bearing skid")
    row = details.get(FIELD)
    if row is None:
        return True
    check_receipt(name, row)
    return row["pressure_bar"] <= EPS


def attributed_fire_discharge(pumps, delivered_kg, *, demand_present):
    """A shared fire main cannot identify which of two pumps discharged.

    Positive proof belongs only to the *single* available fitted source
    when real spray has actually reduced finite suppression-water inventory.
    Two available pumps return no per-unit credit, not invented splitting.
    """
    quantity = _nonnegative(delivered_kg)
    if type(demand_present) is not bool:
        raise ProcessOutputError("No physically observed suppression demand")
    ids = tuple(pumps)
    if len(ids) != len(set(ids)) or any(x not in PROTECTED_FIRE_MOTORS for x in ids):
        raise ProcessOutputError("Unidentified real fire-main source")
    if not demand_present and quantity > EPS:
        raise ProcessOutputError("Water spray without an actual open mist demand")
    return {name: quantity if len(ids) == 1 and demand_present else 0.0
            for name in PROTECTED_FIRE_MOTORS}
