"""G19 finite on-site replacement of partly spent refuge scrubber media.

Uses original DC/life-safety consumables already stowed at HAB-04/08.
A replacement moves surveyed inventory mass into a fitted scrubber and
retains retired CO2 and spent media aboard the same actual refuge site.
No chemical regeneration or remote teleporting of stock is assumed.
"""
from __future__ import annotations

import copy
import math

from world.ship_refuge_life_support import (
    RefugeAirError, REFUGE_PACKS, NOMINAL_CAPTURE_KG,
    validate_refuge_scrubbers,
)

MAX_CARRIED_MEDIA_KG = 4.0
MAX_LOCAL_SPENT_MEDIA_KG = 8.0


def initial_refuge_media_service():
    return {
        "version": 1,
        "sites": {
            pack: {"fresh_installed_kg": 0.0,
                   "retired_capture_kg": 0.0,
                   "sealed_spent_media_kg": 0.0,
                   "operations": 0}
            for pack in sorted(REFUGE_PACKS)},
        "meter": {"fresh_installed_kg": 0.0, "retired_capture_kg": 0.0},
    }


def _finite(value):
    if (type(value) not in (int, float)
            or not math.isfinite(value) or value < 0):
        raise RefugeAirError("Invalid physical refuge media quantity")
    return float(value)


def validate_refuge_media_service(ledger):
    if (not isinstance(ledger, dict)
            or set(ledger) != {"version", "sites", "meter"}
            or ledger["version"] != 1
            or not isinstance(ledger["sites"], dict)
            or set(ledger["sites"]) != set(REFUGE_PACKS)
            or not isinstance(ledger["meter"], dict)
            or set(ledger["meter"]) != {"fresh_installed_kg",
                                       "retired_capture_kg"}):
        raise RefugeAirError("Unknown fitted refuge media custody")
    fresh_sum, captured_sum = 0.0, 0.0
    for pack, site in ledger["sites"].items():
        if not isinstance(site, dict) or set(site) != {
                "fresh_installed_kg", "retired_capture_kg",
                "sealed_spent_media_kg", "operations"}:
            raise RefugeAirError("Incomplete local sealed media custody")
        fresh = _finite(site["fresh_installed_kg"])
        retired = _finite(site["retired_capture_kg"])
        spent = _finite(site["sealed_spent_media_kg"])
        op = site["operations"]
        if (spent > MAX_LOCAL_SPENT_MEDIA_KG + 1e-8
                or retired > fresh + NOMINAL_CAPTURE_KG + 1e-7
                or type(op) is not int or op < 0):
            raise RefugeAirError("Retired media exceeds finite refuge receiver")
        fresh_sum += fresh
        captured_sum += retired
    if (not math.isclose(fresh_sum, _finite(
            ledger["meter"]["fresh_installed_kg"]), abs_tol=1e-7)
            or not math.isclose(captured_sum, _finite(
                ledger["meter"]["retired_capture_kg"]), abs_tol=1e-7)):
        raise RefugeAirError("Refuge media mass accounts do not reconcile")
    return True


def load_refuge_media(scrubbers, service, pack, kg, *,
                      surveyed_local_stock_kg, inventory_stock_kg):
    """Service one portable cassette at the authentic on-site locker.

    Empty fitted cartridge slots are loaded first; once nominal pack capacity
    is filled, a new cassette can replace an actually used segment only.
    The removed captured gas remains physically sequestered at the site.
    """
    validate_refuge_scrubbers(scrubbers)
    validate_refuge_media_service(service)
    if pack not in REFUGE_PACKS or pack not in scrubbers["units"]:
        raise RefugeAirError("Installed refuge scrubber was not surveyed")
    amount = _finite(kg)
    located = _finite(surveyed_local_stock_kg)
    stock = _finite(inventory_stock_kg)
    if (amount <= 0 or amount > MAX_CARRIED_MEDIA_KG
            or amount > located + 1e-8 or amount > stock + 1e-8):
        raise RefugeAirError("No surveyed portable replacement cartridge at this refuge")
    clean = copy.deepcopy(scrubbers)
    custody = copy.deepcopy(service)
    bank = clean["units"][pack]
    site = custody["sites"][pack]
    # No bank may silently accept more than its installed nominal module
    # capacity. Removing already used media frees a physical module slot.
    new_slot_kg = min(amount, max(0.0, NOMINAL_CAPTURE_KG -
                                  bank["capacity_kg"]))
    replacement_kg = amount - new_slot_kg
    if replacement_kg > bank["captured_kg"] + 1e-8:
        raise RefugeAirError("Only genuinely used scrubber modules can be replaced")
    if site["sealed_spent_media_kg"] + replacement_kg > (
            MAX_LOCAL_SPENT_MEDIA_KG + 1e-8):
        raise RefugeAirError("Local sealed retired-media receiver is full")
    bank["capacity_kg"] += new_slot_kg
    bank["captured_kg"] = max(0.0, bank["captured_kg"] - replacement_kg)
    clean["meter"]["captured_kg"] = max(
        0.0, clean["meter"]["captured_kg"] - replacement_kg)
    site["fresh_installed_kg"] += amount
    site["retired_capture_kg"] += replacement_kg
    site["sealed_spent_media_kg"] += replacement_kg
    site["operations"] += 1
    custody["meter"]["fresh_installed_kg"] += amount
    custody["meter"]["retired_capture_kg"] += replacement_kg
    validate_refuge_scrubbers(clean)
    validate_refuge_media_service(custody)
    return clean, custody, stock - amount
