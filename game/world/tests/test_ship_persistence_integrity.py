"""F6-1: no fabricated material, motion or stored power in saved state."""
import copy
import unittest

from world.ship_persistence_integrity import (
    ShipPersistenceError, validate_departure_stock, validate_motion_quantities,
    validate_pressure_mass, validate_energy_custody,
)


def motion():
    return {
        "dry_mass_kg": 100_000_000.0,
        "cargo_capacity_kg": 900_000_000.0,
        "cargo_mass_kg": 900_000_000.0,
        "mission_fluids_kg": 1_000_000.0,
        "ftl_fuel_kg": 1_000_000.0,
        "expended_ftl_fuel_kg": 0.0,
        "propellant_kg": 5_000_000.0,
        "expended_propellant_kg": 0.0,
        "velocity_m_s": [0.0, 0.0, 0.0],
    }


def contract():
    return {
        "dry_t": 100_000,
        "commercial_cargo_t": 900_000,
        "mission_and_nonpropulsive_fluids_t": 1_000,
        "FTL_fuel_t": 1_000,
        "sublight_reaction_mass_t": 5_000,
    }


class G19PersistenceRegressions(unittest.TestCase):
    def test_departure_consumables_have_fitted_ceilings(self):
        self.assertTrue(validate_departure_stock(
            "INV-SPARES", 1.0, {"nominal_mass_t": 2.0}))
        self.assertTrue(validate_departure_stock(
            "INV-WASTE-RESIDUE", 50, {"nominal_mass_t": 0.0}))
        self.assertTrue(validate_departure_stock(
            "INV-SPARES", 1.0, {"nominal_mass_t": 2.0}, authored_nominal_t=2.0))
        with self.assertRaisesRegex(ShipPersistenceError, "fitted source"):
            validate_departure_stock(
                "INV-SPARES", 1.0, {"nominal_mass_t": 1e30},
                authored_nominal_t=2.0)
        for value in (float("inf"), float("nan"), -1, 1e30, None, "5"):
            with self.subTest(value=value):
                with self.assertRaises(ShipPersistenceError):
                    validate_departure_stock(
                        "INV-REACTION", value, {"nominal_mass_t": 5000.0})

    def test_mass_conservation_and_velocity_bound(self):
        self.assertTrue(validate_motion_quantities(motion(), contract()))
        for field, value in (("propellant_kg", 1e30),
                             ("ftl_fuel_kg", float("inf")),
                             ("cargo_mass_kg", 901e6),
                             ("velocity_m_s", [1e30, 0.0, 0.0]),
                             ("velocity_m_s", ["fast", 0.0, 0.0])):
            with self.subTest(field=field, value=value):
                bad = copy.deepcopy(motion())
                bad[field] = value
                with self.assertRaises(ShipPersistenceError):
                    validate_motion_quantities(bad, contract())
        lost_hull = motion()
        lost_hull["dry_mass_kg"] = 1.0
        with self.assertRaisesRegex(ShipPersistenceError, "dry mass"):
            validate_motion_quantities(lost_hull, contract())
        bad = motion()
        bad["propellant_kg"] = 4_000_000
        bad["expended_propellant_kg"] = 2_000_000
        with self.assertRaises(ShipPersistenceError):
            validate_motion_quantities(bad, contract())

    def test_real_departure_debits_and_forged_debits(self):
        water = {
            "waste_offload": {"delivered_kg": {
                "industrial": 2.0, "hazardous": 3.0, "sanitary": 4.0}},
            "cumulative": {"hydrogen_from_electrolysis_kg": 0.5},
        }
        shipped = motion()
        shipped["dry_mass_kg"] -= 5.0
        shipped["mission_fluids_kg"] -= 4.5
        self.assertTrue(validate_motion_quantities(shipped, contract(), water=water))
        for field in ("dry_mass_kg", "mission_fluids_kg"):
            corrupt = copy.deepcopy(shipped)
            corrupt[field] -= 2.0
            with self.subTest(account=field):
                with self.assertRaises(ShipPersistenceError):
                    validate_motion_quantities(corrupt, contract(), water=water)
        forged = copy.deepcopy(water)
        forged["waste_offload"]["delivered_kg"]["industrial"] = 1e30
        with self.assertRaises(ShipPersistenceError):
            validate_motion_quantities(shipped, contract(), water=forged)

    def test_pressure_mass_is_measured_not_unlimited(self):
        self.assertTrue(validate_pressure_mass(100.0, 100, 294))
        for mass, volume, temperature in (
                (1e30, 100.0, 294.0),
                (float("nan"), 100.0, 294.0),
                (100.0, 0, 294.0),
                (100.0, 100.0, None)):
            with self.assertRaises(ShipPersistenceError):
                validate_pressure_mass(mass, volume, temperature)

    def test_stored_power_respects_source_and_time(self):
        small = {
            "banks": {"BAT-COMMON-OPS": {
                "capacity_kwh": 1000.0, "initial_kwh": 500.0,
                "charged_kwh": 0.0, "discharged_kwh": 0.0}},
            "flywheels": {}, "shore": None,
            "meter": {"generation_kwh": 2.0, "served_kwh": 1.0},
        }
        values = dict(nameplates_kwh={"BAT-COMMON-OPS": 8000.0},
                      completed_ticks=2, max_tick_seconds=60.0,
                      generation_mw={"GEN-M": 3.0}, ship_cap_mw=3.3)
        self.assertTrue(validate_energy_custody(small, **values))
        for name, corruption in (
                ("capacity", 1e30), ("charge", 1e30), ("meter", 1e30)):
            with self.subTest(name=name):
                bad = copy.deepcopy(small)
                if name == "capacity":
                    bad["banks"]["BAT-COMMON-OPS"]["capacity_kwh"] = corruption
                elif name == "charge":
                    bad["banks"]["BAT-COMMON-OPS"]["charged_kwh"] = corruption
                else:
                    bad["meter"]["generation_kwh"] = corruption
                with self.assertRaises(ShipPersistenceError):
                    validate_energy_custody(bad, **values)


if __name__ == "__main__":
    unittest.main()
