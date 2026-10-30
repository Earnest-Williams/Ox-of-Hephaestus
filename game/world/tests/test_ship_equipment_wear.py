"""G19 pure secondary machinery fatigue, independent faults and real repair reset."""
import copy
import unittest
from types import SimpleNamespace as Row

from world.ship_electrical_power import ElectricalError
from world.ship_equipment_services import (
    SERVICE_LOADS, service_specs, service_ids,
    initial_service_operations, step_service_operations,
)
from world.ship_equipment_wear import (
    SERVICE_INTERVAL_S, FAILURE_MULTIPLIER,
    initial_equipment_wear, validate_equipment_wear,
    survey_existing_wear, step_equipment_wear,
)


def fixture(*running):
    equipment = {
        name: Row(space_id=room, condition="serviceable", details={
            "physics_commanded_on": name in running,
            "physics_online": name in running,
        }) for name, (room, panel) in SERVICE_LOADS.items()
    }
    wires = {}
    contacts = {}
    for spec in service_specs().values():
        if spec["category"] == "edge":
            wires[spec["source_id"]] = Row(**spec)
        elif spec["category"] == "isolator":
            contacts[spec["source_id"]] = Row(**spec)
    panels = {spec[1] for spec in SERVICE_LOADS.values()}
    return equipment, wires, contacts, panels


def step(services, equipment, wires, contacts, panels, *, seconds=10,
         powered=True):
    return step_service_operations(
        services, seconds, nodes=panels, equipment=equipment,
        edges=wires, switches=contacts, supply_assured=powered)


class EquipmentWearContracts(unittest.TestCase):
    def test_migration_samples_existing_runtime_without_new_failures(self):
        units, wires, switches, panels = fixture("SHOP-CNC-MILL")
        services = initial_service_operations()
        services["units"]["SHOP-CNC-MILL"]["runtime_s"] = 4_000_000
        wear = initial_equipment_wear(services)
        self.assertEqual(
            wear["units"]["SHOP-CNC-MILL"]["seen_runtime_s"], 4_000_000)
        self.assertEqual(wear["units"]["SHOP-CNC-MILL"]["wear_s"], 0)
        services = step(services, units, wires, switches, panels)
        newer, changes = step_equipment_wear(wear, services, units)
        self.assertEqual(changes, [])
        self.assertEqual(newer["units"]["SHOP-CNC-MILL"]["wear_s"], 10)
        self.assertTrue(validate_equipment_wear(newer, services))

    def test_historic_repair_receipt_cannot_erase_newly_surveyed_wear(self):
        units, wires, switches, panels = fixture("SHOP-GRINDER")
        units["SHOP-GRINDER"].details["repair_completed_game_time"] = 500.0
        services = initial_service_operations()
        wear = initial_equipment_wear(services, units)
        self.assertEqual(
            wear["units"]["SHOP-GRINDER"]["last_repair_game_time"], 500.0)
        limit = SERVICE_INTERVAL_S["SHOP-GRINDER"]
        wear = survey_existing_wear(
            wear, services, "SHOP-GRINDER",
            equivalent_hours=(limit - 5) / 3600)
        services = step(services, units, wires, switches, panels)
        worn, changes = step_equipment_wear(wear, services, units)
        self.assertEqual(changes, [("SHOP-GRINDER", "degraded")])
        self.assertGreater(worn["units"]["SHOP-GRINDER"]["wear_s"], limit)
        self.assertEqual(
            worn["units"]["SHOP-GRINDER"]["last_repair_game_time"], 500.0)

    def test_surveyed_high_hour_cnc_degrades_then_faults_independently(self):
        units, wires, switches, panels = fixture(
            "SHOP-CNC-MILL", "GROW-1-CTRL")
        services = initial_service_operations()
        wear = initial_equipment_wear(services)
        warn = SERVICE_INTERVAL_S["SHOP-CNC-MILL"]
        wear = survey_existing_wear(
            wear, services, "SHOP-CNC-MILL",
            equivalent_hours=(warn - 5) / 3600)
        services = step(services, units, wires, switches, panels)
        wear, events = step_equipment_wear(wear, services, units)
        self.assertEqual(events, [("SHOP-CNC-MILL", "degraded")])
        self.assertIn(
            "SHOP-CNC-MILL", wear["last"]["maintenance_due"])
        self.assertNotIn("GROW-1-CTRL", wear["last"]["maintenance_due"])
        self.assertEqual(wear["units"]["GROW-1-CTRL"]["wear_s"], 10)
        units["SHOP-CNC-MILL"].condition = "degraded"
        # Advance to the last five seconds of the higher wear failure
        # threshold: no random or globally applied failure timer.
        injected = copy.deepcopy(wear)
        injected["units"]["SHOP-CNC-MILL"]["wear_s"] = (
            warn * FAILURE_MULTIPLIER - 5)
        services = step(services, units, wires, switches, panels)
        faulted, changes = step_equipment_wear(injected, services, units)
        self.assertEqual(changes, [("SHOP-CNC-MILL", "faulted")])
        self.assertEqual(
            faulted["units"]["SHOP-CNC-MILL"]["wear_faults"], 1)
        self.assertIn("SHOP-CNC-MILL", faulted["last"]["new_faults"])
        self.assertEqual(faulted["units"]["GROW-1-CTRL"]["stage"], "normal")

    def test_wear_pauses_when_individual_motor_isolated(self):
        units, wires, switches, panels = fixture("SHOP-CNC-MILL")
        services = initial_service_operations()
        wear = initial_equipment_wear(services)
        services = step(services, units, wires, switches, panels)
        wear, _ = step_equipment_wear(wear, services, units)
        _, _, fuse = service_ids("SHOP-CNC-MILL")
        switches[fuse].setting = "open"
        dark = step(services, units, wires, switches, panels)
        paused, changes = step_equipment_wear(wear, dark, units)
        self.assertEqual(changes, [])
        self.assertEqual(paused["units"]["SHOP-CNC-MILL"]["wear_s"], 10)
        self.assertEqual(dark["units"]["SHOP-CNC-MILL"]["runtime_s"], 10)

    def test_only_real_completed_repair_resets_faulted_wear_stage(self):
        units, wires, switches, panels = fixture("SHOP-CNC-MILL")
        services = initial_service_operations()
        wear = survey_existing_wear(
            initial_equipment_wear(services), services, "SHOP-CNC-MILL",
            equivalent_hours=SERVICE_INTERVAL_S["SHOP-CNC-MILL"]
                             * FAILURE_MULTIPLIER / 3600)
        services = step(services, units, wires, switches, panels)
        worn, events = step_equipment_wear(wear, services, units)
        self.assertEqual(events, [("SHOP-CNC-MILL", "faulted")])
        units["SHOP-CNC-MILL"].condition = "serviceable"
        units["SHOP-CNC-MILL"].details["physics_online"] = False
        units["SHOP-CNC-MILL"].details["physics_commanded_on"] = False
        repeat, events = step_equipment_wear(worn, services, units)
        self.assertEqual(events, [("SHOP-CNC-MILL", "faulted")])
        self.assertEqual(repeat["units"]["SHOP-CNC-MILL"]["stage"], "faulted")
        units["SHOP-CNC-MILL"].details["repair_completed_game_time"] = 1200
        repaired, changes = step_equipment_wear(repeat, services, units)
        self.assertEqual(changes, [])
        self.assertEqual(repaired["units"]["SHOP-CNC-MILL"]["wear_s"], 0)
        self.assertEqual(repaired["units"]["SHOP-CNC-MILL"]["stage"], "normal")
        self.assertEqual(
            repaired["units"]["SHOP-CNC-MILL"]["wear_faults"], 1)
        second, changes = step_equipment_wear(repaired, services, units)
        self.assertEqual(changes, [])
        self.assertEqual(second["units"]["SHOP-CNC-MILL"]["wear_s"], 0)

    def test_surveys_bad_inputs_and_time_jump_fail_closed(self):
        units, wires, switches, panels = fixture("SHOP-GRINDER")
        services = initial_service_operations()
        wear = initial_equipment_wear(services)
        wear = survey_existing_wear(
            wear, services, "SHOP-GRINDER", equivalent_hours=20)
        with self.assertRaises(ElectricalError):
            survey_existing_wear(
                wear, services, "SHOP-GRINDER", equivalent_hours=5)
        for name, equivalent in (
            ("SHOP-GRINDER", float("nan")),
            ("MISSING", 0),
            ("GROW-1-CTRL", -1),
            ("GROW-1-CTRL", 5000),
        ):
            with self.assertRaises(ElectricalError):
                survey_existing_wear(
                    wear, services, name, equivalent_hours=equivalent)
        corrupted = copy.deepcopy(wear)
        corrupted["units"]["SHOP-GRINDER"]["seen_runtime_s"] = 500
        with self.assertRaises(ElectricalError):
            validate_equipment_wear(corrupted, services)
        services["units"]["SHOP-GRINDER"]["runtime_s"] = 100
        with self.assertRaises(ElectricalError):
            step_equipment_wear(wear, services, units)
