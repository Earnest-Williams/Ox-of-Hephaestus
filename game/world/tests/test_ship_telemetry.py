"""Verify the terminal reads world-owned room state and nothing private."""

from __future__ import annotations

import json

from evennia.utils.test_resources import EvenniaTestCase

from world.ship_model import AccessLinkSpec, ShipWorldModel, SpaceSpec
from world.ship_telemetry import read_spatial_telemetry
from world.ship_world import build_canonical_ship


class ShipTelemetryTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        model = ShipWorldModel(
            schema_version="ox.ship-world/0.1",
            model_version="0.4",
            principal={},
            spaces=(
                SpaceSpec("CMD-PRIMARY", "Bridge", "room", "fixed", "BOW", "serviceable", {}),
                SpaceSpec("ENG-CONTROL", "Engineering", "room", "fixed", "ENG", "serviceable", {}),
            ),
            access_links=(
                AccessLinkSpec("TEST-LINK", "CMD-PRIMARY", "ENG-CONTROL", "hatch", {}),
            ),
        )
        self.ship = build_canonical_ship(model)

    def test_world_conditions_not_source_json_conditions(self):
        bridge = self.ship["spaces"]["CMD-PRIMARY"]
        bridge.db.ox_current_condition = "smoke-damaged"
        bridge.db.private_crew_memory = "Private character interpretation"
        response = read_spatial_telemetry()

        self.assertEqual(response["schema"], "ox.telemetry.spatial/0.1")
        self.assertTrue(response["topology_complete"])
        self.assertEqual(response["model_version"], "0.4")
        self.assertEqual(response["coverage"]["spaces_expected"], 2)
        self.assertEqual(response["coverage"]["spaces_reporting"], 2)
        self.assertEqual(response["coverage"]["equipment"], "not_integrated")
        self.assertEqual(response["coverage"]["crew"], "not_exported")
        self.assertEqual(
            response["space_states"],
            [
                {"id": "CMD-PRIMARY", "condition": "smoke-damaged"},
                {"id": "ENG-CONTROL", "condition": "serviceable"},
            ],
        )
        self.assertNotIn("private_crew_memory", json.dumps(response))
        self.assertNotIn("Private character interpretation", json.dumps(response))
        self.assertNotIn("dbref", json.dumps(response))

    def test_incomplete_installation_is_not_reported_as_complete(self):
        self.ship["root"].db.ox_topology_complete = False
        self.assertFalse(read_spatial_telemetry()["topology_complete"])

    def test_missing_world_returns_no_invented_health(self):
        self.ship["root"].delete()
        response = read_spatial_telemetry()
        self.assertFalse(response["topology_complete"])
        self.assertEqual(response["coverage"]["spaces_expected"], 0)
        self.assertEqual(response["model_version"], "")
