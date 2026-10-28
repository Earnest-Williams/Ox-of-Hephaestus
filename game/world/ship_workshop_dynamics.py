"""Attended G19 workshop mechanisms, not synthetic shipwide tachometers.

The original six machine-shop tools include five motor-driven spindles and
one hydraulic press. Their local operating surfaces can be physically
observed without creating a remote bridge sensor or material output.
Spindle inertia and pressure bleed-down persist after disconnect; an
electrically dead machine is not automatically safe to open.
Weld cells are explicitly excluded until an actual finite arc/test operation
is fitted: the existence of a live welding feed is NOT proof of an arc.
"""
from __future__ import annotations

import math

# (kind, nominal output, driven rise per second, passive decay per second,
#  minimum useful output). Calibration is gameplay-grade, not a maker manual.
# All six IDs are original independent workshop devices.
WORKSHOP_DRIVES = {
    "SHOP-CNC-LATHE": ("spindle_rpm", 2200.0, 180.0, 120.0, 250.0),
    "SHOP-CNC-MILL": ("spindle_rpm", 2400.0, 200.0, 130.0, 300.0),
    "SHOP-MANUAL-LATHE": ("spindle_rpm", 1200.0, 100.0, 70.0, 150.0),
    "SHOP-GRINDER": ("spindle_rpm", 3200.0, 300.0, 160.0, 400.0),
    "SHOP-BALANCER": ("spindle_rpm", 900.0, 65.0, 40.0, 120.0),
    "SHOP-PRESS": ("hydraulic_bar", 110.0, 12.0, 7.0, 35.0),
}
GAUGE_FIELD = "physics_workshop_gauge"
MAX_SECONDS = 10.0


class WorkshopGaugeError(ValueError):
    """Contradictory or nonphysical local machine output."""


def _finite(value):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < 0):
        raise WorkshopGaugeError("Invalid local mechanical gauge quantity")
    return float(value)


def gauge_valid(name, sample):
    if name not in WORKSHOP_DRIVES:
        raise WorkshopGaugeError("No commissioned original shop output mechanism")
    kind, maximum, _, _, _ = WORKSHOP_DRIVES[name]
    if (not isinstance(sample, dict)
            or set(sample) != {"kind", "value", "cumulative_output",
                               "driven_s", "sampled_s"}
            or sample["kind"] != kind
            or sample["sampled_s"] is None):
        raise WorkshopGaugeError("Invalid installed machine gauge record")
    value = _finite(sample["value"])
    _finite(sample["cumulative_output"])
    _finite(sample["driven_s"])
    _finite(sample["sampled_s"])
    if value > maximum + 1e-7:
        raise WorkshopGaugeError("Machine exceeds its physical rated output")
    return True


def step_workshop_gauge(name, prior, *, dt_s, now_s, driven):
    """Integrate real shop spindle inertia or hydraulic accumulator.

    'driven' must be established by actual machine contactor, healthy
    mechanism, assured source, and the separate service operating ledger.
    The integral records wheel turns for rotating units, or pressure-seconds
    for the press; it does not pretend a machined part has been produced.
    """
    if name not in WORKSHOP_DRIVES:
        raise WorkshopGaugeError("No physical workshop mechanism for this ID")
    dt = _finite(dt_s)
    instant = _finite(now_s)
    if dt > MAX_SECONDS or type(driven) is not bool:
        raise WorkshopGaugeError("Unbounded or unverified mechanical actuation")
    kind, maximum, rise, decay, _ = WORKSHOP_DRIVES[name]
    if prior is None:
        old = 0.0
        integral = 0.0
        driven_s = 0.0
    else:
        gauge_valid(name, prior)
        if instant <= prior["sampled_s"] or instant - prior["sampled_s"] + 1e-7 < dt:
            raise WorkshopGaugeError("Duplicate, stale or reordered workshop motion")
        old = float(prior["value"])
        integral = float(prior["cumulative_output"])
        driven_s = float(prior["driven_s"])
    actual = (min(maximum, old + rise * dt) if driven
              else max(0.0, old - decay * dt))
    # Integrate physical coasting as well as powered output. For pressure,
    # bar-seconds describes stored hydraulic state, not a completed press.
    integral += 0.5 * (old + actual) * dt / (60 if kind == "spindle_rpm" else 1)
    if driven:
        driven_s += dt
    result = {
        "kind": kind, "value": float(actual),
        "cumulative_output": float(integral),
        "driven_s": float(driven_s), "sampled_s": float(instant),
    }
    gauge_valid(name, result)
    return result


def machine_output_confirmed(name, details, *, observed_s, operating):
    """Local positively-moving shaft or pressure-building hydraulic pump.

    A commanded-on flag alone, even with a conducting electrical breaker,
    never suffices. Welding cells are not claimed without real arc work.
    """
    if name not in WORKSHOP_DRIVES:
        return False
    if not isinstance(details, dict) or type(operating) is not bool:
        return False
    gauge = details.get(GAUGE_FIELD)
    if gauge is None:
        return False
    gauge_valid(name, gauge)
    _finite(observed_s)
    _, _, _, _, minimum = WORKSHOP_DRIVES[name]
    return bool(
        operating and details.get("physics_commanded_on") is True
        and details.get("physics_online") is True
        and details.get("physics_startup_s", 0.0) == 0
        and abs(gauge["sampled_s"] - observed_s) < 1e-7
        and gauge["value"] >= minimum)


def machine_safely_stopped(name, details):
    """A disconnected but coasting spindle is still physically moving."""
    if name not in WORKSHOP_DRIVES:
        return True
    if not isinstance(details, dict):
        raise WorkshopGaugeError("No physical local machine record")
    gauge = details.get(GAUGE_FIELD)
    if gauge is None:
        return True  # never driven since this nonresetting retrofit
    gauge_valid(name, gauge)
    # Require essentially zero spindle movement/accumulator pressure before
    # hands enter the machine. A tripped breaker alone does not stop inertia.
    return gauge["value"] <= 1e-7
