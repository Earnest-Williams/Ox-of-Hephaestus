"""Pure G19 cargo accounting and finite freight transfer regressions."""
import unittest

from world.ship_cargo_manifest import (
    CargoError, initial_cargo, declare_cargo_lot, split_cargo_lot,
    verify_drum, validate_cargo, drum_balance, start_freight_transfer,
    step_freight, onboard_mass_kg, restow_cargo_lot, unsecured_drum_loads,
)
from world.ship_motion_machinery import initial_rotors, set_rotor_command


class ShipCargoTests(unittest.TestCase):
    def setUp(self):
        self.total = 900_000_000.0
        self.cargo = initial_cargo(self.total)

    def test_unlocated_cargo_remains_aboard_without_fabricated_drums(self):
        self.assertEqual(self.cargo["unlocated_onboard_kg"], self.total)
        self.assertEqual(self.cargo["lots"], {})
        self.assertEqual(onboard_mass_kg(self.cargo), self.total)
        self.assertTrue(validate_cargo(self.cargo, self.total))
        with self.assertRaises(CargoError):
            validate_cargo(self.cargo, self.total - 1)

    def test_survey_and_package_split_conserve_mass(self):
        cargo = declare_cargo_lot(
            self.cargo, lot_id="BULK01", mass_kg=200_000, drum="DR-01",
            azimuth_deg=0, radius_m=0.1, restrained=True)
        cargo = split_cargo_lot(
            cargo, source_id="BULK01", new_id="PALLET01", mass_kg=40_000)
        self.assertEqual(cargo["lots"]["BULK01"]["mass_kg"], 160_000)
        self.assertEqual(cargo["lots"]["PALLET01"]["mass_kg"], 40_000)
        self.assertEqual(cargo["unlocated_onboard_kg"], self.total - 200_000)
        self.assertTrue(validate_cargo(cargo, self.total))
        self.assertEqual(onboard_mass_kg(cargo), self.total)
        with self.assertRaises(CargoError):
            split_cargo_lot(cargo, source_id="BULK01", new_id="MIRACLE",
                            mass_kg=200_000)
        with self.assertRaises(CargoError):
            declare_cargo_lot(
                cargo, lot_id="FAKE", mass_kg=self.total, drum="DR-01",
                azimuth_deg=0, radius_m=1)

    def test_symmetric_stowage_cancels_imbalance(self):
        cargo = declare_cargo_lot(
            self.cargo, lot_id="A", mass_kg=50_000, drum="DR-02",
            azimuth_deg=0, radius_m=50)
        cargo = declare_cargo_lot(
            cargo, lot_id="B", mass_kg=50_000, drum="DR-02",
            azimuth_deg=180, radius_m=50)
        balance = drum_balance(cargo, "DR-02")
        self.assertAlmostEqual(balance["imbalance_kg_m"], 0, places=6)
        self.assertEqual(balance["known_cargo_kg"], 100_000)
        self.assertFalse(balance["surveyed"])
        cargo = verify_drum(cargo, "DR-02")
        self.assertTrue(drum_balance(cargo, "DR-02")["surveyed"])

    def _ready(self):
        cargo = declare_cargo_lot(
            self.cargo, lot_id="BOX", mass_kg=40_000,
            drum="DR-03", azimuth_deg=0, radius_m=0.1, kind="sled")
        cargo = verify_drum(cargo, "DR-03")
        rotors = set_rotor_command(initial_rotors(), "DR-03", "freight_extend")
        return cargo, rotors

    def test_transfer_requires_verified_survey_and_positive_hardlock(self):
        cargo, rotors = self._ready()
        unverified = dict(cargo, verified_drums=[])
        with self.assertRaises(CargoError):
            start_freight_transfer(
                unverified, rotors, lot_id="BOX", direction="to_lock",
                collar_healthy=True)
        released = set_rotor_command(rotors, "DR-03", "freight_retract")
        with self.assertRaises(CargoError):
            start_freight_transfer(
                cargo, released, lot_id="BOX", direction="to_lock",
                collar_healthy=True)
        with self.assertRaises(CargoError):
            start_freight_transfer(
                cargo, rotors, lot_id="BOX", direction="to_lock",
                collar_healthy=False)

    def test_timed_transfer_pauses_on_power_and_collar_casualty(self):
        cargo, rotors = self._ready()
        cargo = start_freight_transfer(
            cargo, rotors, lot_id="BOX", direction="to_lock",
            collar_healthy=True)
        self.assertEqual(cargo["lots"]["BOX"]["location"], "DR-03")
        paused, moved = step_freight(
            cargo, 60, power_ready=False, available_collars={"DR-03"})
        self.assertEqual(moved, ())
        self.assertEqual(paused["jobs"], cargo["jobs"])
        paused, moved = step_freight(
            cargo, 60, power_ready=True, available_collars=set())
        self.assertEqual(moved, ())
        paused, moved = step_freight(
            cargo, 60, power_ready=True, available_collars={"DR-03"})
        self.assertEqual(moved, ())
        self.assertEqual(paused["lots"]["BOX"]["location"], "DR-03")
        completed, moved = step_freight(
            paused, 10, power_ready=True, available_collars={"DR-03"})
        self.assertEqual(moved, ("BOX",))
        self.assertEqual(completed["lots"]["BOX"]["location"],
                         "DR-03-FREIGHT-LOCK")
        self.assertEqual(completed["jobs"], {})
        self.assertTrue(validate_cargo(completed, self.total))

    def test_pressure_gate_proof_required_before_spine_transfer(self):
        cargo, rotors = self._ready()
        cargo["lots"]["BOX"]["location"] = "DR-03-FREIGHT-LOCK"
        with self.assertRaises(CargoError):
            start_freight_transfer(
                cargo, rotors, lot_id="BOX", direction="to_spine",
                collar_healthy=True, gate_open=False)
        cargo = start_freight_transfer(
            cargo, rotors, lot_id="BOX", direction="to_spine",
            collar_healthy=True, gate_open=True)
        stuck, moved = step_freight(
            cargo, 60, power_ready=True, available_collars={"DR-03"},
            open_fixed_gates=set())
        self.assertEqual(moved, ())
        self.assertEqual(stuck["jobs"], cargo["jobs"])
        self.assertTrue(validate_cargo(stuck, self.total))

    def test_interdrum_spine_transfer_requires_receiving_collar_and_restow(self):
        cargo, rotors = self._ready()
        cargo["lots"]["BOX"]["location"] = "SPINE-FREIGHT"
        cargo = verify_drum(cargo, "DR-04")
        rotors = set_rotor_command(rotors, "DR-04", "freight_extend")
        transfer = start_freight_transfer(
            cargo, rotors, lot_id="BOX", direction="from_spine",
            collar_healthy=True, gate_open=True, destination_drum="DR-04")
        self.assertIn("DR-04", transfer["jobs"])
        midway, moved = step_freight(
            transfer, 30, power_ready=True, available_collars={"DR-04"},
            open_fixed_gates={"DR-04"})
        self.assertEqual(moved, ())
        nearly_arrived, moved = step_freight(
            midway, 30, power_ready=True, available_collars={"DR-04"},
            open_fixed_gates={"DR-04"})
        self.assertEqual(moved, ())
        arrived, moved = step_freight(
            nearly_arrived, 10, power_ready=True, available_collars={"DR-04"},
            open_fixed_gates={"DR-04"})
        self.assertEqual(moved, ("BOX",))
        self.assertEqual(arrived["lots"]["BOX"]["drum"], "DR-04")
        self.assertEqual(arrived["lots"]["BOX"]["location"],
                         "DR-04-FREIGHT-LOCK")
        self.assertTrue(validate_cargo(arrived, self.total))
        loading = start_freight_transfer(
            arrived, rotors, lot_id="BOX", direction="to_drum",
            collar_healthy=True)
        partial, moved = step_freight(
            loading, 60, power_ready=True, available_collars={"DR-04"})
        self.assertEqual(moved, ())
        installed, moved = step_freight(
            partial, 10, power_ready=True, available_collars={"DR-04"})
        self.assertEqual(moved, ("BOX",))
        self.assertTrue(unsecured_drum_loads(installed, "DR-04"))
        secured = restow_cargo_lot(
            installed, lot_id="BOX", azimuth_deg=180, radius_m=0.1)
        self.assertFalse(unsecured_drum_loads(secured, "DR-04"))
        self.assertTrue(validate_cargo(secured, self.total))

    def test_spine_station_cannot_be_double_booked(self):
        cargo, rotors = self._ready()
        cargo = declare_cargo_lot(
            cargo, lot_id="BOX2", mass_kg=1000, drum="DR-02",
            azimuth_deg=0, radius_m=0.1, kind="sled")
        cargo = verify_drum(cargo, "DR-02")
        rotors = set_rotor_command(rotors, "DR-02", "freight_extend")
        cargo["lots"]["BOX"]["location"] = "DR-03-FREIGHT-LOCK"
        cargo["lots"]["BOX2"]["location"] = "DR-02-FREIGHT-LOCK"
        underway = start_freight_transfer(
            cargo, rotors, lot_id="BOX", direction="to_spine",
            collar_healthy=True, gate_open=True)
        with self.assertRaises(CargoError):
            start_freight_transfer(
                underway, rotors, lot_id="BOX2", direction="to_spine",
                collar_healthy=True, gate_open=True)
        partial, moved = step_freight(
            underway, 60, power_ready=True,
            available_collars={"DR-03"}, open_fixed_gates={"DR-03"})
        self.assertEqual(moved, ())
        empty, moved = step_freight(
            partial, 10, power_ready=True,
            available_collars={"DR-03"}, open_fixed_gates={"DR-03"})
        self.assertEqual(moved, ("BOX",))
        with self.assertRaises(CargoError):
            start_freight_transfer(
                empty, rotors, lot_id="BOX2", direction="to_spine",
                collar_healthy=True, gate_open=True)

    def test_stowage_rejects_nan_and_invalid_shapes(self):
        for azimuth in (float("nan"), float("inf"), 360, -1):
            with self.assertRaises(CargoError):
                declare_cargo_lot(
                    self.cargo, lot_id="BAD", mass_kg=4, drum="DR-01",
                    azimuth_deg=azimuth, radius_m=1)
        with self.assertRaises(CargoError):
            declare_cargo_lot(
                self.cargo, lot_id="BAD", mass_kg=4, drum="DR-01",
                azimuth_deg=0, radius_m=0)
        with self.assertRaises(CargoError):
            declare_cargo_lot(
                self.cargo, lot_id="BAD", mass_kg=4, drum="DR-01",
                azimuth_deg=0, radius_m=1, kind="sled", restrained="yes")


if __name__ == "__main__":
    unittest.main()
