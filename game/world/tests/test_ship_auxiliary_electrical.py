"""Pure G19 auxiliary electric fault, energy, and isolation regression."""
import copy
import unittest
from types import SimpleNamespace as Row

from world.ship_auxiliary_electrical import (
    LOCAL_LOADS, MOTORS, _specs, auxiliary_ids, initial_local_backup,
    survey_local_backup, set_local_mode, step_local_backup, motor_power,
    validate_local_backup, migrate_local_backup, charger_ids,
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
        self.assertEqual(len(ids), 3 * len(MOTORS) + 6 * len(LOCAL_LOADS))
        self.assertEqual(len(LOCAL_LOADS), 16)
        self.assertEqual(len(MOTORS), 49)
        self.assertEqual(len(set(ids)), len(ids))
        self.assertTrue(all(x["source_model"] == "g19-electrical-aux/1"
                            for x in ids.values()))

    def test_critical_motor_families_are_fused_individually(self):
        e, sw, equipment = fitted()
        from collections import Counter
        families = Counter(
            "bearing_lube" if "-LUBE-" in name else
            "drum_indexer" if "-PERSONNEL-INDEXER" in name else
            "freight_handler" if "-RADIAL-FREIGHT-HANDLER" in name else
            "eclss" if name.startswith("ECLSS-") else
            "water" if name.startswith("WATER-PROC-") else
            "waste" if name.startswith("WASTE-PROC-") else
            "other"
            for name in MOTORS)
        self.assertEqual(families["bearing_lube"], 24)
        self.assertEqual(families["drum_indexer"], 6)
        self.assertEqual(families["freight_handler"], 6)
        self.assertEqual(families["eclss"], 2)
        self.assertEqual(families["water"], 2)
        self.assertEqual(families["waste"], 2)
        for name, (_, panel) in MOTORS.items():
            self.assertTrue(motor_power(
                name, nodes={panel}, equipment=equipment, edges=e, switches=sw),
                name)
        name = "BE-01-LUBE-N"
        _, _, breaker = auxiliary_ids(name, motor=True)
        sw[breaker].setting = "open"
        panel = MOTORS[name][1]
        self.assertFalse(motor_power(
            name, nodes={panel}, equipment=equipment, edges=e, switches=sw))
        self.assertTrue(motor_power(
            "BE-01-LUBE-S", nodes={panel},
            equipment=equipment, edges=e, switches=sw))

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

    def test_finite_charging_requires_live_generator_or_shore_path_and_fuse(self):
        e, sw, units = fitted()
        name = "HAB-04-REFUGE-BAT"
        parent = LOCAL_LOADS[name][2]
        ledger = set_local_mode(survey_local_backup(
            initial_local_backup(), name, capacity_kwh=1, initial_kwh=0
        ), name, "charge")
        prior = copy.deepcopy(ledger)
        charged = step_local_backup(
            ledger, 10, nodes={parent}, producer_nodes={parent},
            producing_mw=3.0, other_requested_mw=1.35,
            equipment=units, edges=e, switches=sw)
        expected = 10 * LOCAL_LOADS[name][4] / 3600.0
        self.assertAlmostEqual(charged["units"][name]["charge_kwh"], expected)
        self.assertAlmostEqual(charged["units"][name]["charged_kwh"], expected)
        self.assertAlmostEqual(charged["meter"]["charged_kwh"], expected)
        self.assertAlmostEqual(
            charged["last"]["grid_charge_requested_mw"],
            LOCAL_LOADS[name][4] / 1000.0)
        self.assertEqual(prior["units"][name]["charge_kwh"], 0)
        self.assertEqual(charged["meter"]["delivered_kwh"], 0)
        charge_edge, breaker = charger_ids(name)
        sw[breaker].setting = "open"
        refused = step_local_backup(
            ledger, 10, nodes={parent}, producer_nodes={parent},
            producing_mw=3.0, other_requested_mw=1.35,
            equipment=units, edges=e, switches=sw)
        self.assertEqual(refused["meter"]["charged_kwh"], 0)
        sw[breaker].setting = "closed"
        for parent_sources, supply, load in [
            (set(), 3., 1.35), ({parent}, 1.35, 1.35),
            ({parent}, 0., 0.),
        ]:
            refused = step_local_backup(
                ledger, 10, nodes={parent}, producer_nodes=parent_sources,
                producing_mw=supply, other_requested_mw=load,
                equipment=units, edges=e, switches=sw)
            self.assertEqual(refused["meter"]["charged_kwh"], 0)
        self.assertIn(charge_edge, e)

    def test_charge_then_reserve_reconciles_every_kwh(self):
        e, sw, units = fitted()
        name = "IX-A-LOCAL-BAT"
        parent = LOCAL_LOADS[name][2]
        ledger = survey_local_backup(
            initial_local_backup(), name,
            capacity_kwh=1, initial_kwh=0)
        ledger = set_local_mode(ledger, name, "charge")
        ledger = step_local_backup(
            ledger, 10, nodes={parent}, producer_nodes={parent},
            producing_mw=3.0, other_requested_mw=1.35,
            equipment=units, edges=e, switches=sw)
        gained = ledger["units"][name]["charge_kwh"]
        ledger = set_local_mode(ledger, name, "reserve")
        ledger = step_local_backup(
            ledger, 10, nodes=set(), equipment=units, edges=e, switches=sw)
        self.assertAlmostEqual(
            ledger["units"][name]["charge_kwh"] +
            ledger["units"][name]["delivered_kwh"], gained)
        self.assertEqual(ledger["meter"]["charged_kwh"], gained)
        validate_local_backup(ledger)

    def test_nonresetting_v1_local_battery_migration(self):
        name = "BE-06-BAT"
        v1 = {
            "version": 1,
            "units": {
                name: {"capacity_kwh": 30., "charge_kwh": 15.,
                       "initial_kwh": 25., "delivered_kwh": 10.,
                       "mode": "reserve"},
            },
            "meter": {"delivered_kwh": 10., "unserved_kwh": 1.2},
            "last": {"any_old_readout": "preserved"},
        }
        migrated = migrate_local_backup(v1)
        self.assertEqual(migrated["version"], 2)
        self.assertEqual(migrated["units"][name]["charge_kwh"], 15)
        self.assertEqual(migrated["meter"]["charged_kwh"], 0)
        self.assertEqual(migrated["last"], v1["last"])
        self.assertEqual(migrate_local_backup(migrated), migrated)
        with self.assertRaises(ElectricalError):
            migrate_local_backup(None)
        bad = copy.deepcopy(v1)
        bad["units"][name]["charge_kwh"] += 10
        with self.assertRaises(ElectricalError):
            migrate_local_backup(bad)

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
