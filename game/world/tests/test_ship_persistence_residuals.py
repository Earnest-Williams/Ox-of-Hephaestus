"""F6 residuals: pressure cells, inert stock, exposure history and clock span."""

from __future__ import annotations

import copy
import math
import unittest
from typing import Any, Final

from world.ship_cargo_environment import (
    CargoClimateError,
    initial_cargo_environment,
    validate_cargo_environment,
)
from world.ship_motion_machinery import (
    MOTION_KEYS,
    RotorError,
    validate_motion_schema,
)
from world.ship_persistence_integrity import (
    BOUNDED_DEPARTURE_STOCKS,
    MAX_CELL_FIRE_FUEL_KG,
    ShipPersistenceError,
    clock_elapsed_bound_s,
    fitted_cell_thermal_capacity_kj_k,
    validate_departure_stock,
    validate_energy_custody,
    validate_exposure_history,
    validate_inventory_quantity,
    validate_pressure_cell_record,
)

VOLUME: Final[tuple[float, float]] = (100.0, 140.0)


def cell(cell_id: str = "PZ-ENG-CONTROL") -> dict[str, Any]:
    return {
        "gas_volume_m3": 120.0,
        "temperature_k": 293.15,
        "scenario_initial_pressure_pa": 101325.0,
        "scenario_provenance": "reference_midpoint_not_measured",
        "physics_oxygen_kg": 33.0,
        "physics_co2_kg": 0.08,
        "physics_smoke_kg": 0.0,
        "physics_fuel_kg": 0.0,
        "physics_burn_kg_s": 0.0,
        "physics_leak_kg_s": 0.0,
        "physics_mist_kg_s": 0.0,
        "physics_background_kw": 0.0,
        "physics_thermal_capacity_kj_k": fitted_cell_thermal_capacity_kj_k(cell_id),
        "physics_heat_exposure_s": 0.0,
        "physics_damage_index": 0.0,
    }


def check_cell(details: object, *, elapsed: float | None = 600.0) -> bool:
    return validate_pressure_cell_record(
        "PZ-ENG-CONTROL",
        details,
        authored_volume_m3=VOLUME,
        elapsed_bound_s=elapsed,
    )


class PressureCellRecordTests(unittest.TestCase):
    def test_commissioned_and_casualty_records_are_accepted(self) -> None:
        self.assertTrue(check_cell(cell()))
        casualty: dict[str, Any] = cell()
        casualty.update(
            physics_fuel_kg=MAX_CELL_FIRE_FUEL_KG,
            physics_burn_kg_s=5.0,
            physics_leak_kg_s=10.0,
            physics_leak_isolator_id="ISO-ATM-ENG-01",
            physics_manual_close_game_s=1000.0,
            hull_installed_spares_kg=12.5,
            hull_repair_game_time=1100.0,
            physics_heat_exposure_s=600.0,
        )
        self.assertTrue(check_cell(casualty))
        self.assertEqual(fitted_cell_thermal_capacity_kj_k("PZ-HAB-03"), 30_000.0)

    def test_writer_ceilings_and_authored_volume(self) -> None:
        mutations: tuple[tuple[str, object], ...] = (
            ("physics_fuel_kg", 1e30),
            ("physics_burn_kg_s", 6.0),
            ("physics_leak_kg_s", 51.0),
            ("physics_mist_kg_s", 0.6),
            ("physics_background_kw", 1e30),
            ("physics_damage_index", 1.5),
            ("physics_heat_exposure_s", 1e30),
            ("physics_thermal_capacity_kj_k", 30_000.0),
            ("gas_volume_m3", 1e30),
            ("gas_volume_m3", 99.0),
            ("scenario_initial_pressure_pa", 1e30),
            ("scenario_initial_pressure_pa", 10_000.0),
            ("scenario_provenance", "corrupt"),
            ("physics_leak_isolator_id", None),
            ("hull_repair_game_time", math.inf),
            ("physics_fuel_kg", True),
        )
        field: str
        bad: object
        for field, bad in mutations:
            with self.subTest(field=field, bad=bad):
                broken: dict[str, Any] = cell()
                broken[field] = bad
                with self.assertRaises(ShipPersistenceError):
                    check_cell(broken)

    def test_strict_key_set(self) -> None:
        extra: dict[str, Any] = cell()
        extra["fuzz_extra_field"] = 1
        with self.assertRaisesRegex(ShipPersistenceError, "extension"):
            check_cell(extra)
        dropped: dict[str, Any] = cell()
        del dropped["physics_damage_index"]
        with self.assertRaisesRegex(ShipPersistenceError, "Incomplete"):
            check_cell(dropped)
        with self.assertRaises(ShipPersistenceError):
            check_cell(["not", "a", "record"])

    def test_heat_exposure_without_trusted_span_is_only_finite(self) -> None:
        long_exposure: dict[str, Any] = cell()
        long_exposure["physics_heat_exposure_s"] = 1e9
        self.assertTrue(check_cell(long_exposure, elapsed=None))


class StockExposureAndClockTests(unittest.TestCase):
    def test_inert_makeup_is_bounded_and_every_inventory_finite(self) -> None:
        for bank in ("INV-INERT-MAKEUP-A", "INV-INERT-MAKEUP-B"):
            self.assertIn(bank, BOUNDED_DEPARTURE_STOCKS)
            self.assertTrue(
                validate_departure_stock(
                    bank, 3.5, {"nominal_mass_t": 3.5}, authored_nominal_t=3.5
                )
            )
            bad: object
            for bad in (1e30, math.inf, None, -1.0):
                with self.subTest(bank=bank, bad=bad):
                    with self.assertRaises(ShipPersistenceError):
                        validate_departure_stock(
                            bank, bad, {"nominal_mass_t": 3.5}, authored_nominal_t=3.5
                        )
        self.assertTrue(validate_inventory_quantity("INV-WASTE-RESIDUE", 1e6))
        for bad in (math.inf, math.nan, None, "1.0", -0.1):
            with self.subTest(bad=bad):
                with self.assertRaises(ShipPersistenceError):
                    validate_inventory_quantity("INV-WASTE-RESIDUE", bad)

    def test_exposure_cannot_outlast_the_clock(self) -> None:
        history: dict[str, Any] = {
            "hypoxia_s": 60.0,
            "smoke_dose": 4.0,
            "thermal_dose": 0.0,
            "co2_dose": 0.0,
            "water_deficit_kg": 0.1,
            "condition": "impaired",
        }
        self.assertTrue(validate_exposure_history("crew #5", history, 120.0))
        self.assertTrue(validate_exposure_history("crew #5", history, None))
        field: str
        for field in ("hypoxia_s", "thermal_dose", "smoke_dose", "water_deficit_kg"):
            with self.subTest(field=field):
                broken: dict[str, Any] = dict(history)
                broken[field] = 1e30
                with self.assertRaises(ShipPersistenceError):
                    validate_exposure_history("crew #5", broken, 120.0)
        over: dict[str, Any] = dict(history, hypoxia_s=121.0)
        with self.assertRaises(ShipPersistenceError):
            validate_exposure_history("crew #5", over, 120.0)

    def test_clock_span_is_bounded_by_arming_time(self) -> None:
        self.assertEqual(clock_elapsed_bound_s(1000.0, 400.0, 60.0), 660.0)
        for last, armed in ((1000.0, 1001.0), (math.inf, 0.0), (1000.0, None)):
            with self.subTest(last=last, armed=armed):
                with self.assertRaises(ShipPersistenceError):
                    clock_elapsed_bound_s(last, armed, 60.0)

    def test_corrupted_tick_counter_cannot_widen_energy_ceiling(self) -> None:
        electrical: dict[str, Any] = {
            "banks": {},
            "flywheels": {},
            "meter": {"generation_kwh": 1e6},
            "shore": None,
        }
        generation: dict[str, float] = {"GEN-A": 10.0}
        # 1e6 kWh needs ~144 h at 25 MW headroom; a huge tick count would allow
        # it, but the trusted 600 s clock span does not.
        self.assertTrue(
            validate_energy_custody(electrical, {}, 10**11, 60.0, generation, 5.0)
        )
        with self.assertRaises(ShipPersistenceError):
            validate_energy_custody(
                electrical, {}, 10**11, 60.0, generation, 5.0, elapsed_bound_s=600.0
            )
        broken: dict[str, Any]
        for broken in ({"banks": {}}, {**electrical, "shore": {}}):
            with self.subTest(broken=sorted(broken)):
                with self.assertRaises(ShipPersistenceError):
                    validate_energy_custody(
                        broken, {}, 0, 60.0, generation, 5.0, elapsed_bound_s=60.0
                    )


class LedgerSchemaTests(unittest.TestCase):
    def test_motion_ledger_has_exactly_its_commissioned_fields(self) -> None:
        motion: dict[str, object] = {key: None for key in MOTION_KEYS}
        self.assertTrue(validate_motion_schema(motion))
        extra: dict[str, object] = dict(motion, fuzz_extra_field=1)
        dropped: dict[str, object] = dict(motion)
        del dropped["velocity_m_s"]
        schema: dict[str, object] | None
        for schema in (extra, dropped, None):
            with self.subTest(schema=type(schema).__name__):
                with self.assertRaises(RotorError):
                    validate_motion_schema(schema)

    def test_cargo_climate_log_with_none_is_classified(self) -> None:
        ledger: dict[str, Any] = copy.deepcopy(
            initial_cargo_environment()  # type: ignore[no-untyped-call]
        )
        manifest: dict[str, Any] = {"lots": {}}
        self.assertTrue(
            validate_cargo_environment(  # type: ignore[no-untyped-call]
                ledger, manifest
            )
        )
        ledger["last"]["unmeasured_drums"] = [None, *ledger["last"]["unmeasured_drums"]]
        with self.assertRaises(CargoClimateError):
            validate_cargo_environment(  # type: ignore[no-untyped-call]
                ledger, manifest
            )


if __name__ == "__main__":
    unittest.main()
