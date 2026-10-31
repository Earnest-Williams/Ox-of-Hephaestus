"""G19 finite commercial-cargo thermal custody in the six original drums.

The six installed cargo heat exchangers and cargo-gas circulation packs
provide conditioned packaged-freight microclimates, NOT automatically
breathable cargo-hold atmosphere. No unknown freight is called perishable.
An operator must survey a physical drum thermal store and specifically
identify sensitive manifest lots. Thermal energy transfers between each
surveyed container environment and its actual service gallery; active
cooling is debited from the existing shared LT radiator capacity.
Quality loss is permanent; lost saleability does not erase cargo mass.
"""
from __future__ import annotations

import copy
import math

from world.ship_cargo_manifest import DRUMS

MAX_STEP_S = 10.0
COOLER_LIMIT_KW = 20.0
MIN_T_K = 1.0
MAX_T_K = 1000.0
SURVEY_MIN_T_K = 230.0
SURVEY_MAX_T_K = 350.0
PROFILES = {
    "cold_chain": {"min_k": 260.0, "max_k": 283.15,
                   "loss_per_day_k": 0.025},
    "cool_sensitive": {"min_k": 270.0, "max_k": 298.15,
                       "loss_per_day_k": 0.008},
    "heat_sensitive": {"min_k": 260.0, "max_k": 305.15,
                       "loss_per_day_k": 0.004},
}


class CargoClimateError(ValueError):
    """No physical evidence for cargo condition or thermal transfer."""


def _finite(number, minimum=0.0, maximum=None):
    if (type(number) not in (float, int) or not math.isfinite(number)
            or number < minimum or (maximum is not None and number > maximum)):
        raise CargoClimateError("Nonphysical measured cargo thermal value")
    return float(number)


def initial_cargo_environment():
    return {
        "version": 1,
        "drums": {drum: None for drum in DRUMS},
        "lots": {},
        "meter": {"radiator_rejected_kj": 0.0,
                  "gallery_exchange_kj": 0.0},
        "last": {"cooling_kw": 0.0, "cooled_drums": [],
                 "exposed_lots": [], "unmeasured_drums": list(DRUMS)},
    }


def validate_cargo_environment(ledger, manifest):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"version", "drums", "lots", "meter", "last"}
            or ledger["version"] != 1
            or not isinstance(ledger["drums"], dict)
            or set(ledger["drums"]) != set(DRUMS)
            or not isinstance(ledger["lots"], dict)
            or not isinstance(ledger["meter"], dict)
            or set(ledger["meter"]) != {"radiator_rejected_kj",
                                        "gallery_exchange_kj"}
            or not isinstance(ledger["last"], dict)
            or set(ledger["last"]) != {"cooling_kw", "cooled_drums",
                                      "exposed_lots", "unmeasured_drums"}
            or not isinstance(manifest, dict)
            or not isinstance(manifest.get("lots"), dict)):
        raise CargoClimateError("Cargo environment schema or physical manifest missing")
    for drum, row in ledger["drums"].items():
        if row is None:
            continue
        if not isinstance(row, dict) or set(row) != {
                "temperature_k", "target_k", "heat_capacity_kj_k",
                "conductance_kw_k", "surveyed"} or row["surveyed"] is not True:
            raise CargoClimateError("Unverified cargo-climate measurements")
        _finite(row["temperature_k"], MIN_T_K, MAX_T_K)
        _finite(row["target_k"], 265.0, 315.0)
        _finite(row["heat_capacity_kj_k"], 100.0, 50_000_000.0)
        _finite(row["conductance_kw_k"], 0.01, 2.0)
    for ident, row in ledger["lots"].items():
        if ident not in manifest["lots"] or not isinstance(row, dict):
            raise CargoClimateError("Temperature-sensitive lot lacks real freight identity")
        if set(row) != {"profile", "quality", "excursion_s",
                        "unmeasured_s", "last_temperature_k"}:
            raise CargoClimateError("Incomplete perishable-freight condition history")
        if row["profile"] not in PROFILES:
            raise CargoClimateError("Unknown physically declared freight sensitivity")
        _finite(row["quality"], 0.0, 1.0)
        _finite(row["excursion_s"])
        _finite(row["unmeasured_s"])
        if row["last_temperature_k"] is not None:
            _finite(row["last_temperature_k"], MIN_T_K, MAX_T_K)
    _finite(ledger["meter"]["radiator_rejected_kj"])
    exchange = ledger["meter"]["gallery_exchange_kj"]
    if type(exchange) not in (int, float) or not math.isfinite(exchange):
        raise CargoClimateError("Cargo gallery thermal exchange is not finite")
    _finite(ledger["last"]["cooling_kw"], 0, 6 * COOLER_LIMIT_KW)
    for field in ("cooled_drums", "exposed_lots", "unmeasured_drums"):
        items = ledger["last"][field]
        expected = set(DRUMS) if field != "exposed_lots" else set(ledger["lots"])
        # Type-check before sorting: a None among strings must be a
        # CargoClimateError, never an unclassified TypeError mid-tick.
        if (not isinstance(items, list)
                or any(type(item) is not str for item in items)
                or items != sorted(set(items))
                or not set(items) <= expected):
            raise CargoClimateError("Malformed cargo-climate instrument log")
    return True


def survey_drum_environment(ledger, manifest, drum, *, temperature_k,
                            target_k, heat_capacity_kj_k,
                            conductance_kw_k):
    """Operator instruments one actually installed commercial drum once."""
    validate_cargo_environment(ledger, manifest)
    if drum not in DRUMS or ledger["drums"][drum] is not None:
        raise CargoClimateError("Drum cargo microclimate already surveyed or absent")
    measurement = {
        "temperature_k": _finite(temperature_k, SURVEY_MIN_T_K, SURVEY_MAX_T_K),
        "target_k": _finite(target_k, 265.0, 315.0),
        "heat_capacity_kj_k": _finite(
            heat_capacity_kj_k, 100.0, 50_000_000.0),
        "conductance_kw_k": _finite(conductance_kw_k, 0.01, 2.0),
        "surveyed": True,
    }
    result = copy.deepcopy(ledger)
    result["drums"][drum] = measurement
    validate_cargo_environment(result, manifest)
    return result


def survey_sensitive_lot(ledger, manifest, lot_id, profile):
    """Explicit identification of vulnerable *existing* commercial freight."""
    validate_cargo_environment(ledger, manifest)
    lot = manifest["lots"].get(lot_id)
    if (lot_id in ledger["lots"] or profile not in PROFILES
            or not lot or lot["location"] != lot["drum"]
            or ledger["drums"][lot["drum"]] is None):
        raise CargoClimateError("Sensitive cargo must be stowed in an instrumented drum")
    result = copy.deepcopy(ledger)
    result["lots"][lot_id] = {
        "profile": profile, "quality": 1.0,
        "excursion_s": 0.0, "unmeasured_s": 0.0,
        "last_temperature_k": result["drums"][lot["drum"]]["temperature_k"],
    }
    validate_cargo_environment(result, manifest)
    return result


def inherit_split_care(ledger, old_manifest, updated_manifest, source_id, new_id):
    """A manifest split cannot restore a known spoiled lot to pristine stock."""
    validate_cargo_environment(ledger, old_manifest)
    if source_id not in ledger["lots"]:
        return ledger
    if (new_id not in updated_manifest["lots"]
            or source_id not in updated_manifest["lots"]):
        raise CargoClimateError("Freight quality split has no real cargo daughter")
    result = copy.deepcopy(ledger)
    if new_id in result["lots"]:
        raise CargoClimateError("A previously assessed freight daughter was overwritten")
    result["lots"][new_id] = copy.deepcopy(result["lots"][source_id])
    validate_cargo_environment(result, updated_manifest)
    return result


def set_cargo_target(ledger, manifest, drum, target_k):
    validate_cargo_environment(ledger, manifest)
    if drum not in DRUMS or ledger["drums"][drum] is None:
        raise CargoClimateError("Target requires a surveyed actual cargo microclimate")
    result = copy.deepcopy(ledger)
    result["drums"][drum]["target_k"] = _finite(target_k, 265.0, 315.0)
    validate_cargo_environment(result, manifest)
    return result


def step_cargo_environment(ledger, manifest, dt, *, ambient_by_drum,
                           operating_machines, connected_lt_nodes,
                           cooling_budget_kw):
    """Return new state, gallery heat movements, and actual LT rejection kW.

    Each drum cooler requires BOTH original independently fused machine
    services plus its original conducting LT rotary interface, while a
    shared 20-kW-equivalent limit bounds each active thermal skid. Heat
    exchange with a real measured service gallery is signed: positive
    gallery_exchange_kj represents sensible energy transferred FROM the
    gallery into the cargo thermal store. The caller must deduct it from
    the same actual pressure cell, and the shared LT radiator allowance.
    """
    validate_cargo_environment(ledger, manifest)
    seconds = _finite(dt, 0.0, MAX_STEP_S)
    budget = _finite(cooling_budget_kw, 0.0, 3750.0)
    if (not isinstance(ambient_by_drum, dict)
            or not isinstance(operating_machines, (set, tuple, list))
            or not isinstance(connected_lt_nodes, (set, tuple, list))):
        raise CargoClimateError("Cargo environment lacks measured galleries or service paths")
    active = set(operating_machines)
    lt = set(connected_lt_nodes)
    result = copy.deepcopy(ledger)
    exchanged, cooled = {}, []
    total_rejection = 0.0
    for drum in DRUMS:
        row = result["drums"][drum]
        if row is None:
            continue
        ambient = ambient_by_drum.get(drum)
        if ambient is None:
            continue
        gallery_temp = _finite(ambient, MIN_T_K, MAX_T_K)
        temperature = row["temperature_k"]
        capacity = row["heat_capacity_kj_k"]
        # The bounded real wall heat leak follows actual measured gallery
        # temperature. A heavy freight heat store cannot jump in ten seconds.
        wall_exchange = row["conductance_kw_k"] * (
            gallery_temp - temperature) * seconds
        row["temperature_k"] += wall_exchange / capacity
        exchanged[drum] = wall_exchange
        if (seconds > 0 and budget > 0
                and f"{drum}-CARGO-HX" in active
                and f"{drum}-CARGO-GAS" in active
                and "NODE-" + drum + "-LT-IF" in lt):
            need_kw = max(0.0, (row["temperature_k"] -
                                row["target_k"]) * capacity / seconds)
            reject_kw = min(COOLER_LIMIT_KW, budget, need_kw)
            row["temperature_k"] -= reject_kw * seconds / capacity
            budget -= reject_kw
            total_rejection += reject_kw
            if reject_kw > 0:
                cooled.append(drum)
        if not MIN_T_K <= row["temperature_k"] <= MAX_T_K:
            raise CargoClimateError("Cargo heat exchanger exceeded measured temperature bounds")
    exposed = []
    for lot_id, condition in sorted(result["lots"].items()):
        lot = manifest["lots"][lot_id]
        row = result["drums"].get(lot["drum"])
        # Unstowed freight is in sealed custody during actual transfers.
        # Its quality is preserved as a recorded state, without claiming
        # a known temperature in an unmeasured transfer station.
        if lot["location"] != lot["drum"] or row is None:
            condition["unmeasured_s"] += seconds
            continue
        temperature = row["temperature_k"]
        condition["last_temperature_k"] = temperature
        profile = PROFILES[condition["profile"]]
        excursion_k = max(
            0.0, temperature - profile["max_k"],
            profile["min_k"] - temperature)
        if excursion_k:
            condition["excursion_s"] += seconds
            loss = min(
                condition["quality"],
                profile["loss_per_day_k"] * excursion_k * seconds / 86400.0)
            condition["quality"] = max(0.0, condition["quality"] - loss)
            exposed.append(lot_id)
    total_exchange = sum(exchanged.values())
    result["meter"]["gallery_exchange_kj"] += total_exchange
    result["meter"]["radiator_rejected_kj"] += total_rejection * seconds
    result["last"] = {
        "cooling_kw": total_rejection,
        "cooled_drums": sorted(cooled),
        "exposed_lots": sorted(exposed),
        "unmeasured_drums": sorted(
            drum for drum in DRUMS if result["drums"][drum] is None
            or drum not in ambient_by_drum),
    }
    validate_cargo_environment(result, manifest)
    return result, exchanged, total_rejection
