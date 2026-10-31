"""G19 persisted-state bounds, separate from routine equipment transitions.

These pure validators check fields that are trusted after installation:
no non-finite inventories, no inflated fitted consumables, no impossible
sub-light velocity or mass, no invented battery/flywheel nameplate, and no
cumulative energy meter greater than the maximum elapsed physical throughput.

A corrupt row is REJECTED, never silently clamped or reset.  Explicit
future replenishment/migration needs a new separately receipted capacity
contract; reference nominal mass is not a permission to mint material.
"""
from __future__ import annotations

import math

# A generous upper bound for the coarse fictional gas-cell model.  This is
# a corruption tripwire, not a pressure-vessel certification pressure.
MAX_RECOGNISED_PRESSURE_PA = 2_000_000.0
MAX_SUBLIGHT_M_S = 299_792_458.0

# Independently fitted consumables. Waste receivers have separate finite
# capacities and can *grow* from processing, so their initial zero-mass
# inventory is intentionally not treated as an upper stock limit.  Cultivation
# can also add genuine harvested food; the food store needs its separately
# commissioned custody/capacity checks, not a fixed departure-stock ceiling.
BOUNDED_DEPARTURE_STOCKS = frozenset({
    "INV-WATER-NORMAL", "INV-WATER-RESERVE",
    "INV-SPARES", "INV-DC-CONSUMABLES",
    "INV-REACTION", "INV-FTL-FUEL",
    "INV-GEN-CART",
    "INV-GAS-REFILL-A", "INV-GAS-REFILL-B",
})


class ShipPersistenceError(ValueError):
    """An installed physical record is impossible or cannot be reconciled."""


def finite_number(value, label, *, maximum=None):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < 0 or (maximum is not None and value > maximum)):
        raise ShipPersistenceError("Invalid finite " + label)
    return float(value)


def validate_departure_stock(identifier, quantity_t, reference):
    """Only inventories originally stocked as consumables use a nominal cap."""
    if identifier not in BOUNDED_DEPARTURE_STOCKS:
        return True
    if not isinstance(reference, dict):
        raise ShipPersistenceError("Missing fitted stock reference: " + identifier)
    rated = finite_number(reference.get("nominal_mass_t"),
                          identifier + " departure mass")
    finite_number(quantity_t, identifier + " held mass", maximum=rated + 1e-8)
    return True


def validate_pressure_mass(mass_kg, volume_m3, temperature_k):
    """Reject an invented gas charge without modifying physical pressure."""
    mass = finite_number(mass_kg, "pressure-cell gas mass")
    volume = finite_number(volume_m3, "pressure-cell volume")
    temperature = finite_number(temperature_k, "pressure-cell temperature")
    if not volume or not temperature:
        raise ShipPersistenceError("Unmeasured pressure-cell volume or temperature")
    pressure = mass * 287.05 * temperature / volume
    if not math.isfinite(pressure) or pressure > MAX_RECOGNISED_PRESSURE_PA:
        raise ShipPersistenceError("Pressure-cell gas mass exceeds physical envelope")
    return True


def validate_motion_quantities(motion, authored_mass):
    """Reconcile the persistent motion ledger with the immutable v0.5 mass basis.

    Motion and the original reaction/FTL inventory rows are different legacy
    custodians.  We bound each against the fitted departure stock without
    falsely equating them while their debit histories remain separate.
    """
    if not isinstance(motion, dict) or not isinstance(authored_mass, dict):
        raise ShipPersistenceError("Unknown commissioned motion mass contract")
    key_to_ref = {
        "dry_mass_kg": "dry_t",
        "cargo_capacity_kg": "commercial_cargo_t",
        "mission_fluids_kg": "mission_and_nonpropulsive_fluids_t",
    }
    for field, authored in key_to_ref.items():
        limit = 1000.0 * finite_number(authored_mass.get(authored), authored)
        finite_number(motion.get(field), field, maximum=limit + 1e-5)
    # No modeled process consumes hull/structure. Losing dry mass in a
    # saved record can increase acceleration without a resource debit.
    fitted_dry = 1000.0 * finite_number(authored_mass.get("dry_t"), "dry_t")
    if not math.isclose(motion["dry_mass_kg"], fitted_dry,
                        rel_tol=0, abs_tol=1e-5):
        raise ShipPersistenceError("Ship dry mass diverged from installed hull")
    cargo_mass = finite_number(motion.get("cargo_mass_kg"), "cargo mass")
    if cargo_mass > motion["cargo_capacity_kg"] + 1e-5:
        raise ShipPersistenceError("Cargo exceeds installed hold capacity")
    for balance, spent, authored in (
            ("propellant_kg", "expended_propellant_kg",
             "sublight_reaction_mass_t"),
            ("ftl_fuel_kg", "expended_ftl_fuel_kg", "FTL_fuel_t")):
        limit = 1000.0 * finite_number(authored_mass.get(authored), authored)
        held = finite_number(motion.get(balance), balance)
        expended = finite_number(motion.get(spent), spent)
        if held + expended > limit + 1e-5:
            raise ShipPersistenceError("Fuel remaining and expended exceed fitted stock: "
                                       + balance)
    velocity = motion.get("velocity_m_s")
    if not isinstance(velocity, list) or len(velocity) != 3:
        raise ShipPersistenceError("Invalid three-axis ship velocity")
    if any(type(x) not in (int, float) or not math.isfinite(x)
           for x in velocity):
        raise ShipPersistenceError("Non-finite ship velocity")
    if math.hypot(*velocity) > MAX_SUBLIGHT_M_S:
        raise ShipPersistenceError("Impossible superluminal inertial velocity")
    return True


def validate_energy_custody(electrical, nameplates_kwh, completed_ticks,
                            max_tick_seconds, generation_mw, ship_cap_mw):
    """Cross-check independent source nameplates and cumulative energy meters.

    Every meter can count at most the energy physically deliverable through
    the fitted power network over the number of elapsed ship-clock ticks.
    The allowance deliberately includes initial stored charge and generous
    parallel source headroom; it is not a replacement for exact per-tick
    generation/load conservation.
    """
    if not isinstance(electrical, dict):
        raise ShipPersistenceError("Unrecognised installed energy ledger")
    if type(completed_ticks) is not int or not 0 <= completed_ticks < 10**12:
        raise ShipPersistenceError("Impossible elapsed ship-clock tick counter")
    elapsed = (completed_ticks + 1) * finite_number(
        max_tick_seconds, "ship step bound")
    headroom_mw = (sum(finite_number(x, "generator rating")
                       for x in generation_mw.values()) +
                   3 * finite_number(ship_cap_mw, "bus limit"))
    max_meter_kwh = elapsed * headroom_mw / 3.6
    initial_kwh = 0.0
    for category in ("banks", "flywheels"):
        for name, bank in electrical[category].items():
            rated = finite_number(nameplates_kwh.get(name),
                                  "unverified fitted electrical nameplate: " + name)
            actual = finite_number(bank.get("capacity_kwh"),
                                   "storage capacity: " + name)
            if actual > rated + 1e-6:
                raise ShipPersistenceError("Electrical storage exceeds nameplate: " + name)
            initial_kwh += finite_number(bank.get("initial_kwh"),
                                          "initial storage charge: " + name)
            for field in ("charged_kwh", "discharged_kwh"):
                if finite_number(bank.get(field), name + "." + field) > (
                        max_meter_kwh + actual + 1e-6):
                    raise ShipPersistenceError("Invented cumulative storage energy: " + name)
    allowed = max_meter_kwh + initial_kwh + 1e-5
    for field, value in electrical["meter"].items():
        finite_number(value, "electrical meter " + field, maximum=allowed)
    if electrical["shore"] is not None:
        finite_number(electrical["shore"]["rated_mw"], "shore source rating",
                      maximum=ship_cap_mw)
    return True
