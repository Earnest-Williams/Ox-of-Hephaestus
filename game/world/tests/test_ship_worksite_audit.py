"""G19 808-piece real equipment-location and selected-route audit."""
import json
import unittest
from pathlib import Path

from world.ship_model import (
    SCHEMA_VERSION, AccessLinkSpec, ShipWorldModel, SpaceSpec,
    load_ship_model,
)
from world.ship_worksite_audit import (
    WorksiteAuditError, audit_equipment_worksites,
)

CANDIDATE = Path(__file__).resolve().parents[3] / (
    "design/ship/ox_full_ship_v0.5_candidate.json")


def sample():
    sites = [
        ("CMD-PRIMARY", "fixed"), ("HATCH", "fixed"),
        ("EXT-SKIN", "vacuum"), ("UNCONNECTED", "fixed"),
    ]
    rooms = tuple(SpaceSpec(
        id=key, name=key, kind="room", frame=frame, zone="test",
        current_condition="serviceable", metadata={})
        for key, frame in sites)
    links = (
        AccessLinkSpec(
            id="AB", from_id="CMD-PRIMARY", to_id="HATCH",
            kind="pressure_hatch", metadata={"pressure_boundary": True}),
        AccessLinkSpec(
            id="BE", from_id="HATCH", to_id="EXT-SKIN",
            kind="eva_work_platform_transfer", metadata={}),
    )
    return ShipWorldModel(
        schema_version=SCHEMA_VERSION, model_version="sample",
        principal={}, spaces=rooms, access_links=links)


class WorksiteCoverageTests(unittest.TestCase):
    def test_inventory_classifies_real_access_obligations(self):
        items = [
            {"id": "A", "kind": "pump", "space_id": "HATCH"},
            {"id": "B", "kind": "radiator", "space_id": "EXT-SKIN"},
            {"id": "C", "kind": "panel", "space_id": "UNCONNECTED"},
            {"id": "D", "kind": "orphan", "space_id": "UNKNOWN"},
        ]
        report = audit_equipment_worksites(sample(), items)
        self.assertEqual(report["equipment"], 4)
        self.assertEqual(report["route_classes"]["pressure_hatch"], 1)
        self.assertEqual(report["route_classes"]["exterior_or_eva"], 1)
        self.assertEqual(report["route_classes"]["disconnected"], 1)
        self.assertEqual(report["route_classes"]["unplaced"], 1)
        self.assertEqual(report["exterior_equipment_ids"], ["B"])
        self.assertEqual(report["unplaced_equipment"], ["D"])
        self.assertEqual(report["disconnected_equipment"], ["C"])
        self.assertIsNone(report["accessible_in_current_casualty"])

    def test_duplicate_equipment_refused(self):
        row = {"id": "ONE", "kind": "motor", "space_id": "HATCH"}
        with self.assertRaises(WorksiteAuditError):
            audit_equipment_worksites(sample(), [row, dict(row)])
        with self.assertRaises(WorksiteAuditError):
            audit_equipment_worksites(sample(), [{"id": "NO-KIND"}])

    def test_full_808_equipment_original_reference_has_site_inventory(self):
        payload = json.loads(CANDIDATE.read_text(encoding="utf-8"))
        model = load_ship_model(CANDIDATE)
        report = audit_equipment_worksites(model, payload["equipment"])
        self.assertEqual(len(model.spaces), 421)
        self.assertEqual(len(model.access_links), 517)
        self.assertEqual(report["equipment"], 808)
        self.assertEqual(sum(report["route_classes"].values()), 808)
        self.assertGreater(report["family_count"], 10)
        # A missing room is a real installation defect, never an inferred
        # accessible control station; keep this check strict.
        self.assertEqual(report["unplaced_equipment"], [])
        print("G19 equipment worksite access classification:",
              json.dumps({
                  "status": report["status"],
                  "equipment": report["equipment"],
                  "route_classes": report["route_classes"],
                  "route_obligations": report["selected_route_obligations"],
                  "disconnected_equipment": report["disconnected_equipment"],
                  "freight_segment_count": len(report[
                      "selected_route_uses_freight_hardware"]),
                  "exterior_equipment_count": report[
                      "exterior_equipment_count"],
              }, sort_keys=True))
