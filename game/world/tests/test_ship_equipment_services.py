"""Pure G19 secondary powered-equipment source, isolation and restart checks."""
import copy
import unittest
from types import SimpleNamespace as Row

from world.ship_electrical_power import ElectricalError
from world.ship_equipment_services import (
    AUTO_SERVICE, MANUAL_RESTART, SERVICE_LOADS, SHOP_TOOLS, WELD_CELLS,
    service_specs, service_ids, service_power,
    initial_service_operations, validate_service_operations,
    step_service_operations, rearm_service_machine,
)


def fixture():
    edges, switches, equipment = {}, {}, {}
    for record in service_specs().values():
        obj = Row(**record)
        if record["category"] == "edge":
            edges[record["source_id"]] = obj
        elif record["category"] == "isolator":
            switches[record["source_id"]] = obj
    for name, (room, panel) in SERVICE_LOADS.items():
        equipment[name] = Row(
            space_id=room, condition="serviceable",
            details={"physics_online": False, "physics_commanded_on": False})
    return edges, switches, equipment


class FittedServiceContracts(unittest.TestCase):
    def test_exact_twenty_six_original_service_equipment_endpoints(self):
        self.assertEqual(len(SERVICE_LOADS), 26)
        self.assertEqual(len(MANUAL_RESTART), 8)
        self.assertEqual(len(AUTO_SERVICE), 18)
        self.assertEqual(len(SHOP_TOOLS), 6)
        self.assertEqual(len(WELD_CELLS), 2)
        self.assertEqual(len(service_specs()), 78)
        self.assertTrue(all(
            row["source_model"] == "g19-operating-equipment/1"
            for row in service_specs().values()))
        self.assertEqual(
            {name for name in SERVICE_LOADS if "CARGO-" in name},
            {f"DR-{i:02d}-{type_}"
             for i in range(1, 7) for type_ in ("CARGO-HX", "CARGO-GAS")})
        self.assertEqual(
            {name for name in SERVICE_LOADS if name.startswith("GROW-")},
            {f"GROW-{i}-{type_}"
             for i in range(1, 4) for type_ in ("CTRL", "NUTRIENT")})

    def test_all_twenty_six_circuits_have_independent_power_and_faults(self):
        edges, switches, equipment = fixture()
        panels = {p for room, p in SERVICE_LOADS.values()}
        for name, (room, parent) in sorted(SERVICE_LOADS.items()):
            with self.subTest(unit=name):
                self.assertTrue(service_power(
                    name, nodes=panels, equipment=equipment,
                    edges=edges, switches=switches))
                _, feeder_id, breaker_id = service_ids(name)
                switches[breaker_id].setting = "open"
                self.assertFalse(service_power(
                    name, nodes=panels, equipment=equipment,
                    edges=edges, switches=switches))
                self.assertTrue(all(service_power(
                    other, nodes=panels, equipment=equipment,
                    edges=edges, switches=switches)
                    for other in SERVICE_LOADS if other != name))
                switches[breaker_id].setting = "closed"
                edges[feeder_id].condition = "severed"
                self.assertFalse(service_power(
                    name, nodes=panels, equipment=equipment,
                    edges=edges, switches=switches))
                edges[feeder_id].condition = "serviceable"
                equipment[name].condition = "failed"
                self.assertFalse(service_power(
                    name, nodes=panels, equipment=equipment,
                    edges=edges, switches=switches))
                equipment[name].condition = "serviceable"
                self.assertTrue(service_power(
                    name, nodes=panels, equipment=equipment,
                    edges=edges, switches=switches))
                self.assertFalse(service_power(
                    name, nodes=panels - {parent}, equipment=equipment,
                    edges=edges, switches=switches))

    def test_power_outage_latches_machine_tool_but_not_other_services(self):
        edges, switches, equipment = fixture()
        for name in ("GROW-1-CTRL", "GROW-1-NUTRIENT",
                     "DR-01-CARGO-HX", "DR-01-CARGO-GAS",
                     "SHOP-CNC-MILL"):
            equipment[name].details = {
                "physics_online": True, "physics_commanded_on": True}
        panels = {p for room, p in SERVICE_LOADS.values()}
        original = initial_service_operations()
        first = step_service_operations(
            original, 10, nodes=panels, equipment=equipment,
            edges=edges, switches=switches, supply_assured=True)
        self.assertEqual(len(first["last"]["operating"]), 5)
        self.assertFalse(first["units"]["SHOP-CNC-MILL"]["restart_latched"])
        self.assertEqual(original["units"]["SHOP-CNC-MILL"]["runtime_s"], 0)
        _, _, shop_breaker = service_ids("SHOP-CNC-MILL")
        switches[shop_breaker].setting = "open"
        broken = step_service_operations(
            first, 10, nodes=panels, equipment=equipment,
            edges=edges, switches=switches, supply_assured=True)
        self.assertTrue(broken["units"]["SHOP-CNC-MILL"]["restart_latched"])
        self.assertEqual(broken["units"]["SHOP-CNC-MILL"]["runtime_s"], 10)
        self.assertEqual(broken["units"]["SHOP-CNC-MILL"]["outage_s"], 10)
        self.assertIn("DR-01-CARGO-GAS", broken["last"]["operating"])
        switches[shop_breaker].setting = "closed"
        restored = step_service_operations(
            broken, 10, nodes=panels, equipment=equipment,
            edges=edges, switches=switches, supply_assured=True)
        self.assertIn("SHOP-CNC-MILL", restored["last"]["restart_required"])
        self.assertNotIn("SHOP-CNC-MILL", restored["last"]["operating"])
        armed = rearm_service_machine(restored, "SHOP-CNC-MILL")
        self.assertIn("DR-01-CARGO-GAS", armed["last"]["operating"])
        self.assertIn("GROW-1-CTRL", armed["last"]["operating"])
        equipment["SHOP-CNC-MILL"].details["physics_online"] = False
        starting = step_service_operations(
            armed, 10, nodes=panels, equipment=equipment,
            edges=edges, switches=switches, supply_assured=True)
        self.assertNotIn("SHOP-CNC-MILL", starting["last"]["operating"])
        equipment["SHOP-CNC-MILL"].details["physics_online"] = True
        resumed = step_service_operations(
            starting, 10, nodes=panels, equipment=equipment,
            edges=edges, switches=switches, supply_assured=True)
        self.assertIn("SHOP-CNC-MILL", resumed["last"]["operating"])
        self.assertEqual(resumed["units"]["SHOP-CNC-MILL"]["runtime_s"], 20)
        self.assertTrue(validate_service_operations(resumed))

    def test_brownout_stops_service_without_restarting_heavy_machinery(self):
        edges, switches, equipment = fixture()
        for name in ("GROW-3-CTRL", "WELD-CELL-A"):
            equipment[name].details.update(
                physics_online=True, physics_commanded_on=True)
        panels = {p for room, p in SERVICE_LOADS.values()}
        live = step_service_operations(
            initial_service_operations(), 10, nodes=panels,
            equipment=equipment, edges=edges, switches=switches,
            supply_assured=True)
        dark = step_service_operations(
            live, 10, nodes=panels, equipment=equipment, edges=edges,
            switches=switches, supply_assured=False)
        self.assertEqual(dark["last"]["operating"], [])
        self.assertTrue(dark["units"]["WELD-CELL-A"]["restart_latched"])
        again = step_service_operations(
            dark, 10, nodes=panels, equipment=equipment,
            edges=edges, switches=switches, supply_assured=True)
        self.assertIn("GROW-3-CTRL", again["last"]["operating"])
        self.assertIn("WELD-CELL-A", again["last"]["restart_required"])

    def test_corrupt_ledger_and_unsupervised_restart_refused(self):
        ledger = initial_service_operations()
        with self.assertRaises(ElectricalError):
            rearm_service_machine(ledger, "GROW-1-CTRL")
        invalid = copy.deepcopy(ledger)
        invalid["units"]["SHOP-PRESS"]["operating"] = True
        invalid["units"]["SHOP-PRESS"]["restart_latched"] = True
        with self.assertRaises(ElectricalError):
            validate_service_operations(invalid)
        edges, switches, equipment = fixture()
        for dt in (-1, 11, float("nan")):
            with self.assertRaises(ElectricalError):
                step_service_operations(
                    ledger, dt, nodes=set(), equipment=equipment,
                    edges=edges, switches=switches,
                    supply_assured=True)
