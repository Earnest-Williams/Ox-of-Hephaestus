"""G19 physical material staging and classified local waste-deposit contracts.

The water physics clock holds each survey, carried filter package and local
processor loading. These pure transitions never create a new spare or another
inventory. The outer world operation must verify the actor, real location,
inventory installation reference, receiver seal, and work receipt atomically.
"""
from __future__ import annotations

import copy

from world.ship_water_recycling import (
    WaterError, _quantity, CASSETTE_KG, transfer_discard,
)

MAX_FILTER_CARRY_KG = 4.0
MAX_FILTER_STAGE_KG = 10.0
MAX_HAND_WASTE_KG = 5.0
SOURCE_TO_WASTE = {
    "industrial": {"INV-SPARES"},
    "hazardous": {"INV-DC-CONSUMABLES"},
}


def register_source_survey(water, *, source, room, verified_kg, inventory_kg):
    """Operator physically confirms existing material in one storage room.

    Another room cannot claim the same unlocated manifest mass.
    """
    if not isinstance(source, str) or not source.startswith("INV-"):
        raise WaterError("Unknown material account")
    if not isinstance(room, str) or not room:
        raise WaterError("Unknown material storage room")
    verified_kg = _quantity(verified_kg)
    inventory_kg = _quantity(inventory_kg)
    if verified_kg <= 0:
        raise WaterError("Positive material survey required")
    w = copy.deepcopy(water)
    survey = w["source_surveys"].setdefault(source, {})
    total = sum(_quantity(v) for v in survey.values()) + verified_kg
    if total > inventory_kg + 1e-7:
        raise WaterError("Source survey exceeds actual unspent onboard inventory")
    survey[room] = survey.get(room, 0.0) + verified_kg
    return w


def take_filter(water, *, actor_dbref, room, kg, stock_kg):
    """Collect a finite surveyed cartridge batch into this person's custody."""
    kg = _quantity(kg)
    stock_kg = _quantity(stock_kg)
    if not 0 < kg <= MAX_FILTER_CARRY_KG:
        raise WaterError("Only a portable finite filter batch can be collected")
    w = copy.deepcopy(water)
    source = w["source_surveys"].get("INV-DC-CONSUMABLES", {})
    if (source.get(room, 0.0) + 1e-7 < kg or
            stock_kg + 1e-7 < kg):
        raise WaterError("No verified compatible filters at this room")
    carried = w["filter_carried_kg"].get(actor_dbref, 0.0)
    if carried + kg > MAX_FILTER_CARRY_KG + 1e-7:
        raise WaterError("Character cannot carry another filter batch")
    source[room] -= kg
    w["filter_carried_kg"][actor_dbref] = carried + kg
    return w, stock_kg - kg


def load_filter(water, *, actor_dbref, side, kg):
    """Install a personally transported cartridge at the actual purifier."""
    kg = _quantity(kg)
    if side not in {"A", "B"} or kg <= 0:
        raise WaterError("Select an installed water processor and positive batch")
    w = copy.deepcopy(water)
    carried = w["filter_carried_kg"].get(actor_dbref, 0.0)
    if carried + 1e-7 < kg:
        raise WaterError("Required filter batch is not carried by this worker")
    if w["filter_staged_kg"][side] + kg > MAX_FILTER_STAGE_KG + 1e-7:
        raise WaterError("Actual purifier cartridge rack already full")
    w["filter_carried_kg"][actor_dbref] = carried - kg
    w["filter_staged_kg"][side] += kg
    return w


def local_classified_deposit(water, stocks, *, category, source,
                             actor_room, target_side, kg, hardware):
    """Deposit source material only where it is *already physically located*."""
    if (category not in SOURCE_TO_WASTE
            or source not in SOURCE_TO_WASTE[category]
            or target_side not in {"A", "B"}):
        raise WaterError("Source material not compatible with this receiver")
    kg = _quantity(kg)
    if not 0 < kg <= MAX_HAND_WASTE_KG:
        raise WaterError("Waste handoff must use finite individual loads")
    surveyed = water["source_surveys"].get(source, {}).get(actor_room, 0.0)
    if surveyed + 1e-7 < kg:
        raise WaterError("Cannot dispose of material not surveyed at this receiver")
    specific = {
        "bins": {category: {target_side: bool(
            hardware.get("bins", {}).get(category, {}).get(target_side))}}
    }
    balance_key = "spares" if source == "INV-SPARES" else "filter"
    w, balances = transfer_discard(
        water, stocks, category=category, source=balance_key,
        kg=kg, hardware=specific)
    w["source_surveys"][source][actor_room] -= kg
    return w, balances
