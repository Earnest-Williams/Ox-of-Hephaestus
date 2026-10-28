"""Finite G19 potable, grey/black water and sealed solid-waste transitions.

Pure deterministic transition: callers hold the canonical physics clock lock and
write the existing inventory rows in the same transaction. The design/reference
JSON is never mutated. Quantities here are kg (water density ~= 1 kg/L).

The 39 t potable working charge is a *separate installed tank*, not a new
inventory account or 39 t of new departure mass. The normal 162 t and protected
70 t remain the existing authoritative inventory quantities.

The 10% unrecovered fraction of sanitary throughput is *not potable*: 1%
becomes finite, sealed sanitary residue, 9% is reclassified as accounted
nonpotable process/reject mass outside this subsystem. This coarse cross-ledger
transfer is visible; it never turns into drinkable water or a phantom tank.
"""
from __future__ import annotations

import math

DAY = 86400.0
WORKING_CAPACITY_KG = 39000.0
LOCAL_KG = {"grey": 500.0, "black": 250.0}
FIXED_KG = {"grey": 10000.0, "black": 2000.0}
CASSETTE_KG = {
    "sanitary": {"A": 8000.0, "B": 8000.0},
    "industrial": {"A": 4000.0, "B": 4000.0},
    "hazardous": {"A": 1000.0, "B": 1000.0},
}
STREAM_FRACTION = {"grey": 0.88, "black": 0.12}
PROCESS_KG_DAY = {"grey": 1100.0, "black": 120.0}
DOMESTIC_KG_DAY = 1000.0
RECOVERY_FRACTION = 0.90
SANITARY_RESIDUE_FRACTION = 0.01
# The balance of wastewater treatment is a metered mission process/reject
# loss, not silent regeneration or mass conjured in a second potable tank.
REJECT_FRACTION = 1.0 - RECOVERY_FRACTION - SANITARY_RESIDUE_FRACTION
MAINTENANCE_AND_FOOD_KG_DAY = {
    "cultivation": 35000.0 / 730.0,
    "food_rehydration": 740.0 / 730.0,
    "servicing": 21924.0 / 730.0,
}
# Outside the 35.6 kg/day crew respiration flow, this is the voted
# gas-leakage makeup allocation, only drawn when oxygen generation is live.
OXYGEN_FEED_KG_DAY = (29236.0 + 2100.0) / 730.0
OXYGEN_FROM_WATER = 16.0 / 18.0
TRANSFER_KG_S = 0.02
EPS = 1e-7


class WaterError(ValueError):
    """Unsafe, unbalanced, non-finite or physically unavailable water work."""


def initial_water():
    from world.ship_waste_offload import initial_offload
    return {
        "waste_offload": initial_offload(),
        "working_kg": WORKING_CAPACITY_KG,
        "local": {s: {"grey": 0.0, "black": 0.0} for s in "AB"},
        "fixed": {"grey": 0.0, "black": 0.0},
        "cassettes": {
            k: {"A": 0.0, "B": 0.0} for k in CASSETTE_KG
        },
        # Source surveys are the operator's physically verified unspent local
        # holdings, not additional material above the inventory ledger.
        "source_surveys": {},
        "filter_carried_kg": {},
        "filter_staged_kg": {"A": 0.0, "B": 0.0},
        "water_train": {"A": "on", "B": "on"},
        "waste_train": {"A": "on", "B": "on"},
        "decontaminate": {"A": False, "B": False},
        "cassette_sealed": {k: {"A": True, "B": True} for k in CASSETTE_KG},
        "oxygen_outlet_verified": {"A": False, "B": False},
        "reserve_released": False,
        "potable_quarantined": False,
        "quality_sample": None,
        "quality_sample_tick": None,
        "suspected_contamination_kg": 0.0,
        "cumulative": {
            "domestic_used_kg": 0.0, "domestic_unserved_kg": 0.0,
            "waste_processed_kg": 0.0, "water_recovered_kg": 0.0,
            "reject_kg": 0.0, "sanitary_solids_kg": 0.0,
            "makeup_kg": 0.0, "emergency_makeup_kg": 0.0,
            "technical_kg": 0.0, "technical_unserved_kg": 0.0,
            "rationed_nonessential_kg": 0.0,
            "decontaminated_kg": 0.0,
            "oxygen_from_electrolysis_kg": 0.0,
            "hydrogen_from_electrolysis_kg": 0.0,
            "industrial_waste_kg": 0.0, "hazardous_waste_kg": 0.0,
        },
    }


def _quantity(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise WaterError("Non-numeric physical quantity")
    if not math.isfinite(x) or x < -EPS:
        raise WaterError("Non-finite or negative physical quantity")
    return max(0.0, float(x))


def validate_water(water, stocks):
    """Check every live finite receiver against its independently owned stock."""
    if not isinstance(water, dict) or not isinstance(stocks, dict):
        raise WaterError("Uncommissioned water ledger")
    for ident in ("normal", "reserve", "sanitary", "industrial", "hazardous"):
        _quantity(stocks[ident])
    if _quantity(water["working_kg"]) > WORKING_CAPACITY_KG + EPS:
        raise WaterError("Potable tank overfill")
    for side in "AB":
        for medium in STREAM_FRACTION:
            if _quantity(water["local"][side][medium]) > LOCAL_KG[medium] + EPS:
                raise WaterError("Local sanitation buffer overfill")
        for subsystem in ("water_train", "waste_train"):
            if water[subsystem][side] not in ("on", "off", "quarantined"):
                raise WaterError("Unknown train command")
        if not isinstance(water["decontaminate"][side], bool):
            raise WaterError("Invalid local water decontamination command")
    if not isinstance(water["source_surveys"], dict) or not isinstance(
            water["filter_carried_kg"], dict):
        raise WaterError("Missing physical material custody records")
    for source, sites in water["source_surveys"].items():
        if not isinstance(source, str) or not source.startswith("INV-") or not isinstance(sites, dict):
            raise WaterError("Invalid surveyed material account")
        for room, amount in sites.items():
            if not isinstance(room, str) or not room or _quantity(amount) < 0:
                raise WaterError("Invalid local material holding")
        if source in {"INV-DC-CONSUMABLES", "INV-SPARES"}:
            key = "filter" if source == "INV-DC-CONSUMABLES" else "spares"
            if key in stocks and sum(sites.values()) > stocks[key] + EPS:
                raise WaterError("Verified material stock exceeds unspent source")
    for actor_id, kg in water["filter_carried_kg"].items():
        if (not isinstance(actor_id, str) or not actor_id or
                _quantity(kg) > 4.0 + EPS):
            raise WaterError("Unbounded or anonymous carried filter")
    for side in "AB":
        if _quantity(water["filter_staged_kg"][side]) > 10.0 + EPS:
            raise WaterError("Water processor filter rack overfilled")
    for medium in STREAM_FRACTION:
        if _quantity(water["fixed"][medium]) > FIXED_KG[medium] + EPS:
            raise WaterError("Fixed wastewater receiver overfill")
    from world.ship_waste_offload import validate_offload
    in_transit = {
        category: sum(job["aboard_kg"] for job in water["waste_offload"]["jobs"].values()
                      if job["category"] == category)
        for category in CASSETTE_KG
    }
    for category, limits in CASSETTE_KG.items():
        for side, cap in limits.items():
            if not isinstance(water["cassette_sealed"][category][side], bool):
                raise WaterError("Waste cassette seal state corrupt")
            if _quantity(water["cassettes"][category][side]) > cap + EPS:
                raise WaterError("Waste cassette overfill")
        filled = sum(water["cassettes"][category].values()) + in_transit[category]
        if not math.isclose(filled, stocks[category], abs_tol=1e-5, rel_tol=1e-10):
            raise WaterError("Sealed receiver and inventory disagree")
    if set(water["oxygen_outlet_verified"]) != {"A", "B"} or any(
            not isinstance(x, bool) for x in water["oxygen_outlet_verified"].values()):
        raise WaterError("Unknown hydrogen outlet commissioning")
    validate_offload(water, stocks)
    for amount in water["cumulative"].values():
        _quantity(amount)
    _quantity(water["suspected_contamination_kg"])
    if water["suspected_contamination_kg"] > water["working_kg"] + EPS:
        raise WaterError("Unbounded contaminated water")
    if not isinstance(water["reserve_released"], bool) or not isinstance(
            water["potable_quarantined"], bool):
        raise WaterError("Invalid protected water or quality interlock")


def _cassette_space(water, category, hardware):
    return sum(
        max(0.0, cap - water["cassettes"][category][side])
        for side, cap in CASSETTE_KG[category].items()
        if hardware.get("bins", {}).get(category, {}).get(side, False)
    )


def _fill_cassette(water, category, mass, hardware):
    """Only compatible, sound, sealed receivers; no phantom shared space."""
    remaining = _quantity(mass)
    if remaining > _cassette_space(water, category, hardware) + EPS:
        raise WaterError("No sealed compatible receiver capacity")
    for side, cap in CASSETTE_KG[category].items():
        if not hardware.get("bins", {}).get(category, {}).get(side, False):
            continue
        moved = min(remaining, max(0.0, cap - water["cassettes"][category][side]))
        water["cassettes"][category][side] += moved
        remaining -= moved
    if remaining > EPS:
        raise WaterError("Sealed receiver exhausted")
    return mass


def step_water(water, seconds, *, stocks, hardware, crew_count=40,
               cultivation_demand_kg=None):
    """Process coupled potable use, dirty-water buffers, recovery and waste.

    hardware is the *current*, tested graph/condition/power evidence:
      potable: verified powered potable main/rotary distribution;
      process[side]: treatment machinery/power and both wet networks alive;
      fixed[medium]: any open double-isolated wet union to fixed receiver;
      oxygen: verified O2 generator, hydrogen buffer/discharge and ECLSS path;
      bins[category][side]: separately sound sealed receiver.
    The caller cannot substitute declared equipment nameplate status for it.
    """
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or (
            seconds < 0 or seconds > DAY):
        raise WaterError("Unbounded water physics step")
    if not isinstance(crew_count, int) or not 0 <= crew_count <= 40:
        raise WaterError("Crew demand outside installed 40-person contract")
    if cultivation_demand_kg is not None:
        if (type(cultivation_demand_kg) not in (int, float)
                or not math.isfinite(cultivation_demand_kg)
                or cultivation_demand_kg < 0
                or cultivation_demand_kg >
                    MAINTENANCE_AND_FOOD_KG_DAY["cultivation"] *
                    seconds / DAY * crew_count / 40 + EPS):
            raise WaterError("Crop water claim exceeds this tick's real allocation")
    validate_water(water, stocks)
    import copy
    w = copy.deepcopy(water)
    stock = {k: _quantity(v) for k, v in stocks.items()}
    daily = seconds / DAY
    scale = crew_count / 40.0
    report = {
        "domestic_kg": 0.0, "unserved_kg": 0.0,
        "processed_kg": 0.0, "recovered_kg": 0.0, "reject_kg": 0.0,
        "sanitary_kg": 0.0, "makeup_kg": 0.0,
        "oxygen_kg": 0.0, "hydrogen_kg": 0.0,
        "technical_kg": 0.0, "cultivation_water_kg": 0.0,
        "rationed_nonessential_kg": 0.0,
        "decontaminated_kg": 0.0,
        "power_required": False,
    }
    if seconds == 0:
        return w, stock, report

    potable_ready = bool(hardware.get("potable")) and not w["potable_quarantined"]
    process = {
        side: bool(hardware.get("process", {}).get(side))
        and w["water_train"][side] == "on"
        and w["waste_train"][side] == "on"
        for side in "AB"
    }
    # An explicitly commanded local purifier can slowly treat quarantined
    # working water. It consumes real filter stock, deposits captured material
    # in a compatible sealed *hazardous* cassette, and does not magic the
    # whole working tank into pure water on a reset.
    if w["potable_quarantined"] and w["suspected_contamination_kg"] > EPS:
        for side in "AB":
            if not process[side] or not w["decontaminate"][side]:
                continue
            fraction = 0.002
            amount = min(
                w["suspected_contamination_kg"], 0.1 * seconds,
                w["filter_staged_kg"][side] / fraction,
                _cassette_space(w, "hazardous", hardware) / fraction)
            if amount <= EPS:
                continue
            spent = amount * fraction
            _fill_cassette(w, "hazardous", spent, hardware)
            w["filter_staged_kg"][side] -= spent
            stock["hazardous"] += spent
            w["suspected_contamination_kg"] -= amount
            w["quality_sample"] = None
            report["decontaminated_kg"] += amount
            w["cumulative"]["decontaminated_kg"] += amount
        if w["suspected_contamination_kg"] <= EPS:
            w["suspected_contamination_kg"] = 0.0
    # A damaged-but-running train has less capacity and lower water yield.
    # Recoverable effluent remains verified; the additional portion is
    # counted as process reject, not magically restored to the potable tank.
    yield_by_train, throughput = {}, {}
    for side in "AB":
        fraction = hardware.get("recovery_fraction", {}).get(side, RECOVERY_FRACTION)
        capacity = hardware.get("throughput_factor", {}).get(side, 1.0)
        if (isinstance(fraction, bool) or not isinstance(fraction, (int, float))
                or not math.isfinite(fraction)
                or not 0 < fraction <= RECOVERY_FRACTION):
            raise WaterError("Invalid actual water-treatment yield")
        if (isinstance(capacity, bool) or not isinstance(capacity, (int, float))
                or not math.isfinite(capacity) or not 0 <= capacity <= 1):
            raise WaterError("Invalid water processor derating")
        yield_by_train[side] = fraction
        throughput[side] = capacity
    limits = {
        side: {stream: (
            PROCESS_KG_DAY[stream] * daily * throughput[side]
            if process[side] else 0.0) for stream in STREAM_FRACTION}
        for side in "AB"}
    # A common sealed-solid receiver is NOT two independent infinite sinks.
    # Reserve its residual treatment capacity proportionally for both streams.
    residue_budget = {
        stream: _cassette_space(w, "sanitary", hardware)
        / SANITARY_RESIDUE_FRACTION * fraction
        for stream, fraction in STREAM_FRACTION.items()
    }
    report["power_required"] = potable_ready or any(process.values())

    def process_mass(side, stream, amount):
        if amount <= EPS:
            return 0.0
        amount = min(amount, limits[side][stream], residue_budget[stream],
                     _cassette_space(w, "sanitary", hardware)
                     / SANITARY_RESIDUE_FRACTION,
                     max(0.0, WORKING_CAPACITY_KG - w["working_kg"])
                     / yield_by_train[side])
        if amount <= EPS:
            return 0.0
        recovered = amount * yield_by_train[side]
        sanitary = amount * SANITARY_RESIDUE_FRACTION
        rejected = amount * (1.0 - yield_by_train[side] - SANITARY_RESIDUE_FRACTION)
        _fill_cassette(w, "sanitary", sanitary, hardware)
        stock["sanitary"] += sanitary
        w["working_kg"] += recovered
        limits[side][stream] -= amount
        residue_budget[stream] -= amount
        report["processed_kg"] += amount
        report["recovered_kg"] += recovered
        report["sanitary_kg"] += sanitary
        report["reject_kg"] += rejected
        return amount

    # Work through existing finite backlog first. A stopped processor can
    # leave contaminated effluent behind without silently recycling it.
    for stream in STREAM_FRACTION:
        for side in "AB":
            if not process[side]:
                continue
            backlog = w["local"][side][stream]
            done = process_mass(side, stream, backlog)
            w["local"][side][stream] -= done
        if hardware.get("fixed", {}).get(stream, False):
            for side in "AB":
                if process[side]:
                    done = process_mass(side, stream, w["fixed"][stream])
                    w["fixed"][stream] -= done

    demand = DOMESTIC_KG_DAY * daily * scale
    # Determine effluent acceptance BEFORE taking potable water out of its
    # tank. Limited treatment throughput and buffers cause water rationing,
    # rather than impossible untreated blackwater overflow.
    capacity = {}
    for stream, fraction in STREAM_FRACTION.items():
        processing = min(sum(limits[side][stream] for side in "AB"),
                         residue_budget[stream])
        buffering = sum(max(0.0, LOCAL_KG[stream] - w["local"][side][stream])
                        for side in "AB")
        if hardware.get("fixed", {}).get(stream, False):
            buffering += max(0.0, FIXED_KG[stream] - w["fixed"][stream])
        capacity[stream] = (processing + buffering) / fraction
    served = min(demand, w["working_kg"],
                 *(capacity[s] for s in STREAM_FRACTION)) if potable_ready else 0.0
    served = max(0.0, served)
    w["working_kg"] -= served

    # Direct treatment and bounded storage represent concurrent flow in one
    # integration interval. Source material remains aboard until processed.
    for stream, fraction in STREAM_FRACTION.items():
        remaining = served * fraction
        for side in "AB":
            if process[side]:
                remaining -= process_mass(side, stream, remaining)
        for side in "AB":
            transfer = min(remaining,
                           max(0.0, LOCAL_KG[stream] - w["local"][side][stream]))
            w["local"][side][stream] += transfer
            remaining -= transfer
        if remaining > EPS and hardware.get("fixed", {}).get(stream, False):
            transfer = min(remaining,
                           max(0.0, FIXED_KG[stream] - w["fixed"][stream]))
            w["fixed"][stream] += transfer
            remaining -= transfer
        if remaining > EPS:
            raise WaterError("Wastewater would overflow an unverified receiver")

    report["domestic_kg"] = served
    report["unserved_kg"] = max(0.0, demand - served)

    # Bounded, *separate* normal and explicitly released emergency makeup.
    # No automatic draindown of the protected 70 t reserve.
    if potable_ready:
        room = max(0.0, WORKING_CAPACITY_KG - w["working_kg"])
        moved = min(room, TRANSFER_KG_S * seconds, stock["normal"])
        w["working_kg"] += moved
        stock["normal"] -= moved
        report["makeup_kg"] += moved
        if w["reserve_released"]:
            room = max(0.0, WORKING_CAPACITY_KG - w["working_kg"])
            rescue = min(room, max(0.0, TRANSFER_KG_S * seconds - moved),
                         stock["reserve"])
            w["working_kg"] += rescue
            stock["reserve"] -= rescue
            w["cumulative"]["emergency_makeup_kg"] += rescue
            report["makeup_kg"] += rescue

    # Food and ordinary servicing consume declared voyage allowance only
    # while usable conditioned supply can actually be delivered. Unlocking
    # the 70 t degradation reserve places the ship in an emergency policy:
    # essential domestic water, food rehydration and O2 electrolysis remain
    # possible, but ordinary crop irrigation and routine washdown cannot
    # silently spend the protected reserve. Any deferral is a visible
    # operational consequence, not a hidden disappearance of crew demand.
    if potable_ready:
        for name, rate in MAINTENANCE_AND_FOOD_KG_DAY.items():
            request = (cultivation_demand_kg
                       if name == "cultivation" and cultivation_demand_kg is not None
                       else rate * daily * scale)
            restricted = w["reserve_released"] and name in {
                "cultivation", "servicing"}
            moved = 0.0 if restricted else min(request, w["working_kg"])
            w["working_kg"] -= moved
            report["technical_kg"] += moved
            if name == "cultivation":
                report["cultivation_water_kg"] = moved
            w["cumulative"]["technical_unserved_kg"] += request - moved
            if restricted:
                report["rationed_nonessential_kg"] += request
                w["cumulative"]["rationed_nonessential_kg"] += request
        if hardware.get("oxygen", False):
            request = OXYGEN_FEED_KG_DAY * daily * scale
            moved = min(request, w["working_kg"])
            w["working_kg"] -= moved
            report["technical_kg"] += moved
            report["oxygen_kg"] += moved * OXYGEN_FROM_WATER
            report["hydrogen_kg"] += moved * (1.0 - OXYGEN_FROM_WATER)
            w["cumulative"]["technical_unserved_kg"] += request - moved
        else:
            w["cumulative"]["technical_unserved_kg"] += (
                OXYGEN_FEED_KG_DAY * daily * scale)
    else:
        w["cumulative"]["technical_unserved_kg"] += (
            (sum(MAINTENANCE_AND_FOOD_KG_DAY.values()) + OXYGEN_FEED_KG_DAY)
            * daily * scale)

    for name, key in (
        ("domestic_used_kg", "domestic_kg"),
        ("domestic_unserved_kg", "unserved_kg"),
        ("waste_processed_kg", "processed_kg"),
        ("water_recovered_kg", "recovered_kg"),
        ("reject_kg", "reject_kg"),
        ("sanitary_solids_kg", "sanitary_kg"),
        ("makeup_kg", "makeup_kg"),
        ("technical_kg", "technical_kg"),
        ("oxygen_from_electrolysis_kg", "oxygen_kg"),
        ("hydrogen_from_electrolysis_kg", "hydrogen_kg"),
    ):
        w["cumulative"][name] += report[key]
    # The potable-side ledger never invents stock: changes in original stocks
    # plus all water/dirty/solid receiver quantities equal explicit exports.
    before = water_inventory_total(water, stocks)
    after = water_inventory_total(w, stock)
    exported = report["reject_kg"] + report["technical_kg"]
    if not math.isclose(before, after + exported, abs_tol=1e-4, rel_tol=1e-11):
        raise WaterError("Water/waste/solid process mass is not conserved")
    validate_water(w, stock)
    return w, stock, report


def water_inventory_total(water, stocks):
    return (
        water["working_kg"] + stocks["normal"] + stocks["reserve"]
        + sum(water["fixed"].values())
        + sum(sum(m.values()) for m in water["local"].values())
        + sum(stocks[category] for category in CASSETTE_KG)
        + stocks.get("filter", 0.0)
        + sum(water["filter_staged_kg"].values())
        + sum(water["filter_carried_kg"].values())
    )


def transfer_discard(water, stocks, *, category, source, kg, hardware):
    """Move already-owned compatible material to a finite segregated cassette.

    The outer caller verifies actual local access to both source and cassette
    plus classification; this transition performs no invisible collection.
    """
    if category not in ("industrial", "hazardous"):
        raise WaterError("Unsafe waste-class substitution")
    kg = _quantity(kg)
    if kg <= 0 or source not in stocks or source in CASSETTE_KG:
        raise WaterError("Invalid or insufficient classified source")
    validate_water(water, stocks)
    if stocks[source] + EPS < kg:
        raise WaterError("Cannot create scrap from nonexistent materials")
    import copy
    w, balances = copy.deepcopy(water), dict(stocks)
    _fill_cassette(w, category, kg, hardware)
    balances[source] -= kg
    balances[category] += kg
    w["cumulative"][category + "_waste_kg"] += kg
    validate_water(w, balances)
    return w, balances
