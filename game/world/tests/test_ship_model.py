"""Validation tests for the prepared full-ship source model."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from world.ship_model import SCHEMA_VERSION, ShipModelError, load_ship_model


def _payload() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": "test-v1",
        "principal": {"name": "Ox test hull"},
        "spaces": [
            {
                "id": "A",
                "name": "A",
                "kind": "room",
                "frame": "fixed",
                "zone": "test",
                "current_condition": "serviceable",
                "damage_control_sector": "test-sector",
            },
            {
                "id": "B",
                "name": "B",
                "kind": "room",
                "frame": "fixed",
                "zone": "test",
                "current_condition": "serviceable",
            },
        ],
        "access_links": [{"id": "AB", "from": "A", "to": "B", "kind": "hatch"}],
        "equipment": [],
        "service_nodes": [],
        "service_edges": [],
        "isolation_points": [],
        "modifications": [],
        "documentation_records": [],
        "maintenance_tasks": [],
        "inventories": [],
    }


class ShipModelTests(TestCase):
    def _write(self, payload: dict, directory: str) -> Path:
        path = Path(directory) / "ship.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_canonical_v04_topology_counts(self):
        model = load_ship_model()
        self.assertEqual(model.schema_version, SCHEMA_VERSION)
        self.assertEqual(len(model.spaces), 421)
        self.assertEqual(len(model.access_links), 517)
        self.assertIn("CMD-PRIMARY", model.spaces_by_id)

    def test_optional_space_metadata_is_preserved(self):
        with TemporaryDirectory() as directory:
            model = load_ship_model(self._write(_payload(), directory))
        self.assertEqual(model.spaces_by_id["A"].metadata["damage_control_sector"], "test-sector")

    def test_dangling_access_link_is_rejected(self):
        payload = _payload()
        payload["access_links"][0]["to"] = "MISSING"
        with TemporaryDirectory() as directory:
            path = self._write(payload, directory)
            with self.assertRaisesRegex(ShipModelError, "unknown space"):
                load_ship_model(path)
