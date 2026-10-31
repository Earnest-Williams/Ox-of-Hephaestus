"""G19 persisted-state bounds, separate from routine equipment transitions.

These pure validators check fields that are trusted after installation:
no non-finite inventories, no inflated fitted consumables, no impossible
sub-light velocity or mass, no invented battery/flywheel nameplate, no
cumulative energy meter greater than the maximum elapsed physical throughput,
no pressure-cell field outside what an authorised writer can produce, and no
exposure history longer than the ship clock has run.

A corrupt row is REJECTED, never silently clamped or reset.  Explicit
future replenishment/migration needs a new separately receipted capacity
contract; reference nominal mass is not a permission to mint material.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from typing import Final

# A generous upper bound for the coarse fictional gas-cell model.  This is
# a corruption tripwire, not a pressure-vessel certification pressure.
MAX_RECOGNISED_PRESSURE_PA: Final[float] = 2_000_000.0
MAX_SUBLIGHT_M_S: Final[float] = 299_792_458.0
AIR_R_J_KG_K: Final[float] = 287.05

# Independently fitted consumables. Waste receivers have separate finite
# capacities and can *grow* from processing, so their initial zero-mass
# inventory is intentionally not treated as an upper stock limit.  Cultivation
# can also add genuine harvested food; the food store needs its separately
# commissioned custody/capacity checks, not a fixed departure-stock ceiling.
# The inert make-up banks have no installed consumer yet: they can only hold
# at most their fitted charge.
BOUNDED_DEPARTURE_STOCKS: Final[frozenset[str]] = frozenset(
    {
        "INV-WATER-NORMAL",
        "INV-WATER-RESERVE",
        "INV-SPARES",
        "INV-DC-CONSUMABLES",
        "INV-REACTION",
        "INV-FTL-FUEL",
        "INV-GEN-CART",
        "INV-GAS-REFILL-A",
        "INV-GAS-REFILL-B",
        "INV-INERT-MAKEUP-A",
        "INV-INERT-MAKEUP-B",
    }
)

# Pressure-cell ceilings are the maxima of every authorised writer, not
# engineering limits: operator casualty injection (fuel 500 kg, burn 5 kg/s,
# leak 50 kg/s, background heat 1 MW), hull breach registration (10 kg/s),
# HAB water mist (0.5 kg/s) and the clamped damage index.
MAX_CELL_FIRE_FUEL_KG: Final[float] = 500.0
MAX_CELL_BURN_KG_S: Final[float] = 5.0
MAX_CELL_LEAK_KG_S: Final[float] = 50.0
MAX_CELL_MIST_KG_S: Final[float] = 0.5
MAX_CELL_BACKGROUND_KW: Final[float] = 1000.0
MAX_CELL_DAMAGE_INDEX: Final[float] = 1.0
HAB_CELL_THERMAL_CAPACITY_KJ_K: Final[float] = 30_000.0
CELL_THERMAL_CAPACITY_KJ_K: Final[float] = 5_000.0
# initialize_nominal_atmosphere() accepts only this scenario pressure range.
MIN_SCENARIO_PRESSURE_PA: Final[float] = 50_000.0
MAX_SCENARIO_PRESSURE_PA: Final[float] = 110_000.0
SCENARIO_PROVENANCES: Final[frozenset[str]] = frozenset(
    {"reference_midpoint_not_measured"}
)
CELL_PHYSICS_REQUIRED: Final[frozenset[str]] = frozenset(
    {
        "physics_oxygen_kg",
        "physics_co2_kg",
        "physics_smoke_kg",
        "physics_fuel_kg",
        "physics_burn_kg_s",
        "physics_leak_kg_s",
        "physics_mist_kg_s",
        "physics_background_kw",
        "physics_thermal_capacity_kj_k",
        "physics_heat_exposure_s",
        "physics_damage_index",
    }
)
# Written only by genuine installed casualty response and hull restoration.
CELL_OPTIONAL: Final[frozenset[str]] = frozenset(
    {
        "physics_leak_isolator_id",
        "physics_manual_close_game_s",
        "scenario_initial_pressure_pa",
        "scenario_provenance",
        "hull_installed_spares_kg",
        "hull_repair_game_time",
    }
)
CELL_BASE: Final[frozenset[str]] = frozenset({"gas_volume_m3", "temperature_k"})
_ISOLATOR_ID: Final[re.Pattern[str]] = re.compile(r"[A-Z0-9][A-Z0-9-]{0,63}")

# Exposure accrual is driven by the ship clock.  Hypoxia counts at most one
# second per second; other doses use a deliberately generous rate ceiling.
EXPOSURE_TIME_FIELDS: Final[frozenset[str]] = frozenset({"hypoxia_s"})
EXPOSURE_DOSE_FIELDS: Final[frozenset[str]] = frozenset(
    {"smoke_dose", "thermal_dose", "co2_dose", "water_deficit_kg"}
)
MAX_DOSE_RATE_PER_S: Final[float] = 1000.0


class ShipPersistenceError(ValueError):
    """An installed physical record is impossible or cannot be reconciled."""


def finite_number(value: object, label: str, *, maximum: float | None = None) -> float:
    if (
        type(value) not in (int, float)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
        or (maximum is not None and value > maximum)
    ):
        raise ShipPersistenceError("Invalid finite " + label)
    return float(value)


def fitted_cell_thermal_capacity_kj_k(cell_id: str) -> float:
    """The arming-time structural heat capacity of one installed gas cell."""
    if cell_id.startswith("PZ-HAB-"):
        return HAB_CELL_THERMAL_CAPACITY_KJ_K
    return CELL_THERMAL_CAPACITY_KJ_K


def validate_inventory_quantity(identifier: str, quantity_t: object) -> bool:
    """Every installed inventory, growable or not, holds a finite mass."""
    finite_number(quantity_t, identifier + " held mass")
    return True


def validate_departure_stock(
    identifier: str,
    quantity_t: object,
    reference: object,
    *,
    authored_nominal_t: object = None,
) -> bool:
    """Enforce original fitted capacity against independently authored source.

    The saved quantity AND the saved reference live in mutable database rows;
    a corrupted reference cannot increase the source's physical capacity.
    """
    if identifier not in BOUNDED_DEPARTURE_STOCKS:
        return True
    if not isinstance(reference, dict):
        raise ShipPersistenceError("Missing fitted stock reference: " + identifier)
    rated: float = finite_number(
        reference.get("nominal_mass_t"), identifier + " departure mass"
    )
    if authored_nominal_t is not None:
        authored: float = finite_number(
            authored_nominal_t, identifier + " source capacity"
        )
        if not math.isclose(rated, authored, rel_tol=0, abs_tol=1e-8):
            raise ShipPersistenceError(
                "Installed stock reference differs from fitted source: " + identifier
            )
        rated = authored
    finite_number(quantity_t, identifier + " held mass", maximum=rated + 1e-8)
    return True


def validate_pressure_mass(
    mass_kg: object, volume_m3: object, temperature_k: object
) -> bool:
    """Reject an invented gas charge without modifying physical pressure."""
    mass: float = finite_number(mass_kg, "pressure-cell gas mass")
    volume: float = finite_number(volume_m3, "pressure-cell volume")
    temperature: float = finite_number(temperature_k, "pressure-cell temperature")
    if not volume or not temperature:
        raise ShipPersistenceError("Unmeasured pressure-cell volume or temperature")
    pressure: float = mass * AIR_R_J_KG_K * temperature / volume
    if not math.isfinite(pressure) or pressure > MAX_RECOGNISED_PRESSURE_PA:
        raise ShipPersistenceError("Pressure-cell gas mass exceeds physical envelope")
    return True


def validate_pressure_cell_record(
    cell_id: str,
    details: object,
    *,
    authored_volume_m3: tuple[float, float] | None,
    elapsed_bound_s: float | None,
) -> bool:
    """Strict key set and writer-derived magnitudes for one armed gas cell.

    ``authored_volume_m3`` is the design free-gas interval from the immutable
    pressure reference; ``elapsed_bound_s`` is the longest the physics clock
    can have run, or None where no trusted clock span is available.
    """
    if not isinstance(details, dict):
        raise ShipPersistenceError("Unrecognised pressure-cell measurements")
    keys: set[object] = set(details)
    if not (CELL_BASE | CELL_PHYSICS_REQUIRED) <= keys:
        raise ShipPersistenceError("Incomplete pressure-cell physics fields")
    if not keys <= CELL_BASE | CELL_PHYSICS_REQUIRED | CELL_OPTIONAL:
        raise ShipPersistenceError("Invented pressure-cell schema extension")
    volume: float = finite_number(details["gas_volume_m3"], "pressure-cell volume")
    if authored_volume_m3 is not None:
        lower, upper = authored_volume_m3
        if not lower - 1e-9 <= volume <= upper + 1e-9:
            raise ShipPersistenceError(
                "Pressure-cell volume outside its authored envelope: " + cell_id
            )
    ceilings: tuple[tuple[str, float], ...] = (
        ("physics_fuel_kg", MAX_CELL_FIRE_FUEL_KG),
        ("physics_burn_kg_s", MAX_CELL_BURN_KG_S),
        ("physics_leak_kg_s", MAX_CELL_LEAK_KG_S),
        ("physics_mist_kg_s", MAX_CELL_MIST_KG_S),
        ("physics_background_kw", MAX_CELL_BACKGROUND_KW),
        ("physics_damage_index", MAX_CELL_DAMAGE_INDEX),
    )
    for field, ceiling in ceilings:
        finite_number(details[field], cell_id + "." + field, maximum=ceiling)
    capacity: float = finite_number(
        details["physics_thermal_capacity_kj_k"], cell_id + " heat capacity"
    )
    if capacity != fitted_cell_thermal_capacity_kj_k(cell_id):
        raise ShipPersistenceError("Pressure-cell structural heat capacity altered")
    finite_number(
        details["physics_heat_exposure_s"],
        cell_id + " heat exposure",
        maximum=elapsed_bound_s,
    )
    if "scenario_initial_pressure_pa" in details:
        setpoint: float = finite_number(
            details["scenario_initial_pressure_pa"], "commissioned setpoint"
        )
        if not MIN_SCENARIO_PRESSURE_PA <= setpoint <= MAX_SCENARIO_PRESSURE_PA:
            raise ShipPersistenceError("Commissioned cell setpoint outside scenario")
    if (
        "scenario_provenance" in details
        and details["scenario_provenance"] not in SCENARIO_PROVENANCES
    ):
        raise ShipPersistenceError("Unrecognised pressure-cell provenance")
    isolator: object = details.get("physics_leak_isolator_id")
    if "physics_leak_isolator_id" in details and (
        type(isolator) is not str or not _ISOLATOR_ID.fullmatch(isolator)
    ):
        raise ShipPersistenceError("Unidentified leak isolator")
    for field in (
        "physics_manual_close_game_s",
        "hull_installed_spares_kg",
        "hull_repair_game_time",
    ):
        if field in details:
            finite_number(details[field], cell_id + "." + field)
    return True


def validate_exposure_history(
    label: str, exposure: object, elapsed_bound_s: float | None
) -> bool:
    """No accumulated dose may exceed what the ship clock could have accrued."""
    if not isinstance(exposure, dict):
        raise ShipPersistenceError("Unrecognised exposure history: " + label)
    if elapsed_bound_s is None:
        return True
    for field in EXPOSURE_TIME_FIELDS | EXPOSURE_DOSE_FIELDS:
        if field not in exposure:
            continue
        ceiling: float = elapsed_bound_s * (
            1.0 if field in EXPOSURE_TIME_FIELDS else MAX_DOSE_RATE_PER_S
        )
        finite_number(exposure[field], label + "." + field, maximum=ceiling)
    return True


def clock_elapsed_bound_s(
    last_game_time: object, armed_game_time: object, max_tick_seconds: float
) -> float:
    """Longest the physics clock can have run, plus one in-progress tick.

    ``last_game_time`` cannot be inflated without stopping the clock (game
    time would run backwards), and ``armed_game_time`` must lie before it.
    """
    if (
        type(last_game_time) not in (int, float)
        or type(armed_game_time) not in (int, float)
        or not isinstance(last_game_time, (int, float))
        or not isinstance(armed_game_time, (int, float))
        or not math.isfinite(last_game_time)
        or not math.isfinite(armed_game_time)
        or armed_game_time > last_game_time
    ):
        raise ShipPersistenceError("Impossible ship-clock commissioning time")
    return float(last_game_time - armed_game_time) + max_tick_seconds


def validate_motion_quantities(
    motion: object, authored_mass: object, *, water: object = None
) -> bool:
    """Reconcile the persistent motion ledger with the immutable v0.5 mass basis.

    Motion and the original reaction/FTL inventory rows are different legacy
    custodians.  We bound each against the fitted departure stock without
    falsely equating them while their debit histories remain separate.
    """
    if not isinstance(motion, dict) or not isinstance(authored_mass, dict):
        raise ShipPersistenceError("Unknown commissioned motion mass contract")
    key_to_ref: dict[str, str] = {
        "dry_mass_kg": "dry_t",
        "cargo_capacity_kg": "commercial_cargo_t",
        "mission_fluids_kg": "mission_and_nonpropulsive_fluids_t",
    }
    for field, authored in key_to_ref.items():
        limit: float = 1000.0 * finite_number(authored_mass.get(authored), authored)
        finite_number(motion.get(field), field, maximum=limit + 1e-5)
    # This coarse inertial "dry" account includes installed stores and scrap.
    # Legitimate industrial/hazardous waste export debits dry mass at the
    # accepting berth; sanitary solids and vented hydrogen debit fluids.
    # Validate recorded departures, not an impossible fixed loaded mass.
    fitted_dry: float = 1000.0 * finite_number(authored_mass.get("dry_t"), "dry_t")
    fitted_fluids: float = 1000.0 * finite_number(
        authored_mass.get("mission_and_nonpropulsive_fluids_t"),
        "mission_and_nonpropulsive_fluids_t",
    )
    delivered: dict[str, float] = {"industrial": 0.0, "hazardous": 0.0, "sanitary": 0.0}
    hydrogen_departed: float = 0.0
    if water is not None:
        try:
            if not isinstance(water, dict):
                raise TypeError("water ledger")
            accounts: object = water["waste_offload"]["delivered_kg"]
            if not isinstance(accounts, dict):
                raise TypeError("delivered accounts")
            delivered = {
                key: finite_number(accounts[key], "waste exported " + key)
                for key in delivered
            }
            hydrogen_departed = finite_number(
                water["cumulative"]["hydrogen_from_electrolysis_kg"],
                "vented electrolysis hydrogen",
            )
        except (TypeError, KeyError) as exc:
            raise ShipPersistenceError(
                "Missing authoritative waste/hydrogen departure ledger"
            ) from exc
    accounted_dry: float = delivered["industrial"] + delivered["hazardous"]
    accounted_fluids: float = delivered["sanitary"] + hydrogen_departed
    if accounted_dry > fitted_dry or accounted_fluids > fitted_fluids:
        raise ShipPersistenceError("Offship waste or hydrogen exceeds fitted ship mass")
    if not math.isclose(
        motion["dry_mass_kg"], fitted_dry - accounted_dry, rel_tol=0, abs_tol=1e-4
    ):
        raise ShipPersistenceError("Ship dry mass differs from recorded offship waste")
    if not math.isclose(
        motion["mission_fluids_kg"],
        fitted_fluids - accounted_fluids,
        rel_tol=0,
        abs_tol=1e-4,
    ):
        raise ShipPersistenceError(
            "Ship mission fluids differ from recorded waste/hydrogen exports"
        )
    cargo_mass: float = finite_number(motion.get("cargo_mass_kg"), "cargo mass")
    if cargo_mass > motion["cargo_capacity_kg"] + 1e-5:
        raise ShipPersistenceError("Cargo exceeds installed hold capacity")
    for balance, spent, authored in (
        ("propellant_kg", "expended_propellant_kg", "sublight_reaction_mass_t"),
        ("ftl_fuel_kg", "expended_ftl_fuel_kg", "FTL_fuel_t"),
    ):
        fuel_limit: float = 1000.0 * finite_number(
            authored_mass.get(authored), authored
        )
        held: float = finite_number(motion.get(balance), balance)
        expended: float = finite_number(motion.get(spent), spent)
        if held + expended > fuel_limit + 1e-5:
            raise ShipPersistenceError(
                "Fuel remaining and expended exceed fitted stock: " + balance
            )
    velocity: object = motion.get("velocity_m_s")
    if not isinstance(velocity, list) or len(velocity) != 3:
        raise ShipPersistenceError("Invalid three-axis ship velocity")
    components: list[float] = []
    for x in velocity:
        if type(x) not in (int, float) or not math.isfinite(x):
            raise ShipPersistenceError("Non-finite ship velocity")
        components.append(float(x))
    if math.hypot(*components) > MAX_SUBLIGHT_M_S:
        raise ShipPersistenceError("Impossible superluminal inertial velocity")
    return True


def validate_energy_custody(
    electrical: object,
    nameplates_kwh: Mapping[str, float],
    completed_ticks: object,
    max_tick_seconds: float,
    generation_mw: Mapping[str, float],
    ship_cap_mw: float,
    *,
    elapsed_bound_s: float | None = None,
) -> bool:
    """Cross-check independent source nameplates and cumulative energy meters.

    Every meter can count at most the energy physically deliverable through
    the fitted power network over the elapsed ship-clock span.  The span is
    the smaller of the tick-count bound and, when available, the trusted
    game-time span since arming, so a corrupted tick counter cannot widen it.
    The allowance deliberately includes initial stored charge and generous
    parallel source headroom; it is not a replacement for exact per-tick
    generation/load conservation.
    """
    if not isinstance(electrical, dict):
        raise ShipPersistenceError("Unrecognised installed energy ledger")
    if type(completed_ticks) is not int or not 0 <= completed_ticks < 10**12:
        raise ShipPersistenceError("Impossible elapsed ship-clock tick counter")
    elapsed: float = (completed_ticks + 1) * finite_number(
        max_tick_seconds, "ship step bound"
    )
    if elapsed_bound_s is not None:
        elapsed = min(elapsed, finite_number(elapsed_bound_s, "ship clock span"))
    headroom_mw: float = sum(
        finite_number(x, "generator rating") for x in generation_mw.values()
    ) + 3 * finite_number(ship_cap_mw, "bus limit")
    max_meter_kwh: float = elapsed * headroom_mw / 3.6
    initial_kwh: float = 0.0
    try:
        stores: Iterable[tuple[str, object]] = [
            *electrical["banks"].items(),
            *electrical["flywheels"].items(),
        ]
        meters: dict[object, object] = electrical["meter"]
        shore: object = electrical["shore"]
    except (KeyError, AttributeError, TypeError) as exc:
        raise ShipPersistenceError("Incomplete installed energy ledger") from exc
    for name, bank in stores:
        if not isinstance(bank, dict):
            raise ShipPersistenceError("Unmeasured energy store: " + name)
        rated: float = finite_number(
            nameplates_kwh.get(name), "unverified fitted electrical nameplate: " + name
        )
        actual: float = finite_number(
            bank.get("capacity_kwh"), "storage capacity: " + name
        )
        if actual > rated + 1e-6:
            raise ShipPersistenceError("Electrical storage exceeds nameplate: " + name)
        initial_kwh += finite_number(
            bank.get("initial_kwh"), "initial storage charge: " + name
        )
        for field in ("charged_kwh", "discharged_kwh"):
            if finite_number(bank.get(field), name + "." + field) > (
                max_meter_kwh + actual + 1e-6
            ):
                raise ShipPersistenceError(
                    "Invented cumulative storage energy: " + name
                )
    allowed: float = max_meter_kwh + initial_kwh + 1e-5
    if not isinstance(meters, dict):
        raise ShipPersistenceError("Unmeasured electrical meters")
    meter_name: object
    meter_value: object
    for meter_name, meter_value in meters.items():
        finite_number(
            meter_value, "electrical meter " + str(meter_name), maximum=allowed
        )
    if shore is not None:
        if not isinstance(shore, dict):
            raise ShipPersistenceError("Unrecognised shore source record")
        finite_number(shore.get("rated_mw"), "shore source rating", maximum=ship_cap_mw)
    return True
