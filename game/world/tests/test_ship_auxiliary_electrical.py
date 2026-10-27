"""Pure G19 auxiliary electric fault, energy, and isolation regression."""
import copy
import unittest
from types import SimpleNamespace as Row

from world.ship_auxiliary_electrical import (
    LOCAL_LOADS, MOTORS, _specs, auxiliary_ids, initial_local_backup,
    survey_local_backup, set_local_mode, step_local_backup, motor_power,
    validate_local_backup,
)
from world.ship_electrical_power import ElectricalError


def fitted():
    spec = _specs()
    e = {}
    sw = {}
    equipment = {}
    for record in spec.values():
        row = Row(**record)
        if row.category == "edge":
            e[row.source_id] = row
        if row.category == "isolator":
            sw[row.source_id] = row
    for name, (room, consumer, panel, *_rest) in LOCAL_LOADS.items():
        equipment[name] = Row(space_id=room, condition="serviceable")
        equipment[consumer] = Row(space_id=room, condition="serviceable")
    for name, (room, _panel) in MOTORS.items():
        equipment[name] = Row(space_id=room, condition="serviceable")
    return e, sw, equipment


class AuxiliaryPowerContracts(unittest.TestCase):
    def test_all_real_harnesses_have_separate_endpoints_and_contacts(self):
        ids = _specs()
        self.assertEqual(len(ids), 3 * len(MOTORS) + 4 * len(LOCAL_LOADS))
        self.assertEqual(len(LOCAL_LOADS), 16)
        self.assertEqual(len(MOTORS), 3)
        self.assertEqual(len(set(ids)), len(ids))
        self.assertTrue(all(x["source_model"] == "g19-electrical-aux/1"
                            for x in ids.values()))

    def test_unrated_local_store_cannot_create_electricity(self):
        e, sw, units = fitted()
        ledger = initial_local_backup()
        self.assertEqual(step_local_backup(
            ledger, 10, nodes=set(), equipment=units,
            edges=e, switches=sw)["meter"]["delivered_kwh"], 0)

    def test_finite_local_backup_independent_of_main_grid(self):
        e, sw, units = fitted()
        name = "BE-01-BAT"
        ledger = survey_local_backup(initial_local_backup(), name,
                                     capacity_kwh=0.005, initial_kwh=0.005)
        ledger = set_local_mode(ledger, name, "reserve")
        result = step_local_backup(ledger, 10, nodes=set(),
                                   equipment=units, edges=e, switches=sw)
        self.assertAlmostEqual(result["meter"]["delivered_kwh"], 1 / 360)
        self.assertAlmostEqual(result["units"][name]["charge_kwh"], .005 - 1 / 360)
        after = step_local_backup(result, 10, nodes=set(),
                                  equipment=units, edges=e, switches=sw)
        self.assertAlmostEqual(after["units"][name]["charge_kwh"], 0)
        self.assertGreater(after["meter"]["unserved_kwh"], 0)
        validate_local_backup(after)
        self.assertEqual(ledger["units"][name]["charge_kwh"], .005)

    def test_local_grid_available_does_not_debit_battery(self):
        e, sw, units = fitted()
        name = "HAB-04-REFUGE-BAT"
        ledger = set_local_mode(survey_local_backup(
            initial_local_backup(), name,
            capacity_kwh=20, initial_kwh=12), name, "reserve")
        result = step_local_backup(
            ledger, 10, nodes={"NODE-PWR-HAB-04-REFUGE-AIR"}, equipment=units,
            edges=e, switches=sw)
        self.assertEqual(result["meter"]["delivered_kwh"], 0)
        self.assertEqual(result["units"][name]["charge_kwh"], 12)

    def test_refuge_bypasses_failed_primary_appliance_branch_not_entire_panel(self):
        e, sw, units = fitted()
        name = "HAB-04-REFUGE-BAT"
        ledger = set_local_mode(survey_local_backup(
            initial_local_backup(), name,
            capacity_kwh=20, initial_kwh=10), name, "reserve")
        parent = LOCAL_LOADS[name][2]
        self.assertNotEqual(parent, "NODE-PWR-HAB-04-REFUGE-AIR")
        battery = step_local_backup(
            ledger, 10, nodes={parent}, equipment=units,
            edges=e, switches=sw)
        self.assertGreater(battery["meter"]["delivered_kwh"], 0)
        self.assertIn(name, battery["last"]["active_local_consumers"])
        normal = step_local_backup(
            ledger, 10, nodes={parent, "NODE-PWR-HAB-04-REFUGE-AIR"},
            equipment=units, edges=e, switches=sw)
        self.assertEqual(normal["meter"]["delivered_kwh"], 0)

    def test_fuse_open_and_load_fault_refuse_backup(self):
        e, sw, units = fitted()
        name = "IX-A-LOCAL-BAT"
        ledger = set_local_mode(survey_local_backup(
            initial_local_backup(), name, capacity_kwh=1,
            initial_kwh=1), name, "reserve")
        _, edge, iso = auxiliary_ids(name)
        sw[iso].setting = "open"
        denied = step_local_backup(ledger, 10, nodes=set(),
                                   equipment=units, edges=e, switches=sw)
        self.assertEqual(denied["meter"]["delivered_kwh"], 0)
        self.assertGreater(denied["meter"]["unserved_kwh"], 0)
        sw[iso].setting = "closed"
        units[LOCAL_LOADS[name][1]].condition = "failed"
        denied = step_local_backup(ledger, 10, nodes=set(),
                                   equipment=units, edges=e, switches=sw)
        self.assertEqual(denied["meter"]["delivered_kwh"], 0)

    def test_motor_feeder_trip_is_individual(self):
        e, sw, units = fitted()
        name = "LT-PLANT"
        _, _, iso = auxiliary_ids(name, motor=True)
        panel = MOTORS[name][1]
        self.assertTrue(motor_power(name, nodes={panel},
                                    equipment=units, edges=e, switches=sw))
        sw[iso].setting = "open"
        self.assertFalse(motor_power(name, nodes={panel},
                                     equipment=units, edges=e, switches=sw))
        self.assertTrue(motor_power(
            "FIRE-PUMP-FWD", nodes={MOTORS["FIRE-PUMP-FWD"][1]},
            equipment=units, edges=e, switches=sw))

    def test_corrupt_meter_and_double_survey_rejected(self):
        name = "BE-06-BAT"
        ledger = survey_local_backup(initial_local_backup(), name,
                                     capacity_kwh=30, initial_kwh=20)
        with self.assertRaises(ElectricalError):
            survey_local_backup(ledger, name, capacity_kwh=30, initial_kwh=30)
        tampered = copy.deepcopy(ledger)
        tampered["units"][name]["charge_kwh"] += 1
        with self.assertRaises(ElectricalError):
            validate_local_backup(tampered)
        with self.assertRaises(ElectricalError):
            survey_local_backup(initial_local_backup(), name,
                                capacity_kwh=1000, initial_kwh=1)


if __name__ == "__main__":
    unittest.main()
