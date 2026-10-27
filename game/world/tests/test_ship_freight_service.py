"""Pure tests for nine original freight service gates and thirteen work sites."""
import copy
import json
import unittest
from pathlib import Path

from world.ship_access_audit import candidate_personnel_routes
from world.ship_freight_service import (
    FreightServiceError, GATES, WORKSITES,
    initial_service_access, validate_service_access,
    service_command, service_hardware_ready, verify_as_built,
)
from world.ship_model import load_ship_model

CANDIDATE = Path(__file__).resolve().parents[3] / (
    "design/ship/ox_full_ship_v0.5_candidate.json")


def machine_state():
    return {
        "rotors": {
            name: {
                "rpm": 0, "target_rpm": 0, "hardlock": True,
                "brake": True, "indexing": False, "freight_collar": False,
                "passenger_indexer": False, "condition": "serviceable",
            }
            for name in ("WR-01", *(f"DR-{i:02d}" for i in range(1, 7)))
        },
        "cargo": {
            "jobs": {}, "port_jobs": {}, "port_contacts": {},
        },
        "water": {"waste_offload": {"jobs": {}}},
        "motion": {
            "command": "coast", "attitude_command": "hold", "ftl_leg": None,
        },
    }


class FreightServicePureTests(unittest.TestCase):
    def test_all_thirteen_have_a_real_rated_entry_from_a_reachable_station(self):
        source = json.loads(CANDIDATE.read_text(encoding="utf-8"))
        self.assertTrue(verify_as_built(source))
        self.assertEqual(len(GATES), 9)
        self.assertEqual(len(WORKSITES), 13)
        model = load_ship_model(CANDIDATE)
        paths = candidate_personnel_routes(model)
        equipment = {item["id"]: item for item in source["equipment"]}
        for unit, (room, gate) in WORKSITES.items():
            with self.subTest(unit=unit):
                control, site, kind, boundary, rotor = GATES[gate]
                self.assertIn(control, paths)
                self.assertNotIn(room, paths)
                self.assertEqual(equipment[unit]["space_id"], room)
                self.assertEqual(site, room)
                self.assertNotIn(gate, [
                    link for path in paths.values()
                    for _, link, _ in path])
                self.assertEqual(source["model_version"], "0.5-candidate")

    def test_tampered_installation_rejected_without_inventing_a_passage(self):
        source = json.loads(CANDIDATE.read_text(encoding="utf-8"))
        wrong = copy.deepcopy(source)
        wrong_link = next(item for item in wrong["access_links"]
                          if item["id"] == "ACC-WR-SPARES-MATERIAL")
        wrong_link["to"] = "SHOP-MECH"
        with self.assertRaises(FreightServiceError):
            verify_as_built(wrong)
        wrong = copy.deepcopy(source)
        wrong_equipment = next(item for item in wrong["equipment"]
                               if item["id"] == "LOGI-SLED-01")
        wrong_equipment["space_id"] = "CMD-PRIMARY"
        with self.assertRaises(FreightServiceError):
            verify_as_built(wrong)

    def test_maintenance_custody_is_finite_idempotent_and_fail_closed(self):
        gate = "ACC-DR-01-FREIGHT-LOCK-LOGI"
        initial = initial_service_access()
        self.assertTrue(validate_service_access(initial))
        with self.assertRaises(FreightServiceError):
            service_command(initial, gate, "close")
        first = service_command(initial, gate, "open")
        self.assertEqual(first["secured_links"], [gate])
        self.assertEqual(initial["secured_links"], [])
        with self.assertRaises(FreightServiceError):
            service_command(first, gate, "open")
        released = service_command(first, gate, "close")
        self.assertEqual(released["secured_links"], [])
        self.assertEqual(released["releases_completed"], 1)
        with self.assertRaises(FreightServiceError):
            service_command(released, "ACC-DR-01-FREIGHT-CAPTURE", "open")
        for bad in ({"schema": "broken", "secured_links": [],
                     "releases_completed": 0},
                    {"schema": initial["schema"], "secured_links": [gate, gate],
                     "releases_completed": 0},
                    {"schema": initial["schema"], "secured_links": [],
                     "releases_completed": -1}):
            with self.subTest(bad=bad), self.assertRaises(FreightServiceError):
                validate_service_access(bad)

    def test_hardware_all_nine_requires_no_moving_cargo_or_rotation(self):
        data = machine_state()
        for gate in GATES:
            with self.subTest(gate=gate):
                self.assertTrue(service_hardware_ready(gate, **data))
        busy = copy.deepcopy(data)
        busy["cargo"]["jobs"] = {"DR-01": {"status": "hauling"}}
        self.assertFalse(service_hardware_ready(
            "ACC-LOGI-STOP-HAB-HUB-SERVICES-MAIN", **busy))
        moored = copy.deepcopy(data)
        moored["cargo"]["port_contacts"] = {"DR-01-P1": {}}
        self.assertFalse(service_hardware_ready(
            "ACC-WR-SPARES-MATERIAL", **moored))
        waste = copy.deepcopy(data)
        waste["water"]["waste_offload"]["jobs"] = {"job": {"status": "moving"}}
        self.assertFalse(service_hardware_ready(
            "ACC-DR-01-FREIGHT-LOCK-LOGI", **waste))
        for change in (
            {"rpm": 0.1}, {"target_rpm": 2.0},
            {"freight_collar": True}, {"passenger_indexer": True},
            {"hardlock": False}, {"brake": False},
        ):
            wrong = copy.deepcopy(data)
            wrong["rotors"]["DR-01"].update(change)
            self.assertFalse(service_hardware_ready(
                "ACC-DR-01-FREIGHT-LOCK-LOGI", **wrong))
        burning = copy.deepcopy(data)
        burning["motion"]["command"] = "thrust"
        self.assertFalse(service_hardware_ready(
            "ACC-WR-FREIGHT-STAGING", **burning))
