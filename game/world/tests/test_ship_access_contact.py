"""Pure drum-3 passive-contact geometry and provenance contracts."""

from __future__ import annotations

from types import SimpleNamespace
import copy
import unittest

from world.ship_access_contact import (
    AccessContactError, CABLE, LINK, ROUTE, SENSOR,
    certificate_valid, contact_specifications, contact_transition,
    reference_hash,
)
from world.ship_model import load_ship_model


class Drum3AccessContactTests(unittest.TestCase):
    def test_local_contact_route_has_real_links_and_rated_final_hatch(self):
        model = load_ship_model()
        records = contact_specifications(model)
        self.assertEqual(set(records), {
            "equipment:" + SENSOR, "edge:" + CABLE})
        contact = records["equipment:" + SENSOR]
        cable = records["edge:" + CABLE]
        self.assertEqual(cable["reference"]["route_spaces"], list(ROUTE))
        self.assertEqual(len(cable["reference"]["route_link_ids"]), 4)
        self.assertIn(LINK, cable["reference"]["pressure_penetrations"])
        self.assertFalse(contact["reference"]["identity_reader"])
        self.assertFalse(contact["reference"]["network_commands"])
        self.assertEqual(contact["reference"]["incremental_power_kw"], 0)
        self.assertEqual(contact["setting"], "off")

    def test_only_changed_world_hatch_state_is_evidence(self):
        event = SimpleNamespace(
            operation="crew_hatch", component_key="access:" + LINK,
            before={"setting": "closed"}, after={"setting": "open"},
            actor_dbref="#123")
        self.assertEqual(contact_transition(event), {
            "setting_before": "closed", "setting_after": "open"})
        event.after = {"setting": "closed", "requested_value": "closed"}
        self.assertIsNone(contact_transition(event))
        event.after = {"setting": "open"}
        event.operation = "crew_indexed_transfer_queued"
        self.assertIsNone(contact_transition(event))
        event.operation = "crew_hatch"
        event.component_key = "access:WRONG"
        self.assertIsNone(contact_transition(event))

    def test_hardware_revision_and_survey_bind_proof(self):
        records = contact_specifications(load_ship_model())
        sensor = SimpleNamespace(**records["equipment:" + SENSOR], revision=2)
        cable = SimpleNamespace(**records["edge:" + CABLE], revision=1)
        rows = {"equipment:" + SENSOR: sensor, "edge:" + CABLE: cable}
        pwr = {"isolator:pwr": 3}
        sensor.setting = "enabled"
        sensor.details = {"contact_survey": {
            "sensor_revision": 2, "cable_revision": 1,
            "sensor_reference_hash": reference_hash(sensor.reference),
            "cable_reference_hash": reference_hash(cable.reference),
            "power_revisions": pwr, "evidence_id": "survey-1",
            "pressure_penetrations": cable.reference["pressure_penetrations"],
        }}
        self.assertTrue(certificate_valid(rows, pwr))
        self.assertFalse(certificate_valid(rows, {"isolator:pwr": 4}))
        cable.revision += 1
        self.assertFalse(certificate_valid(rows, pwr))
        cable.revision -= 1
        sensor.condition = "failed"
        self.assertFalse(certificate_valid(rows, pwr))
        sensor.condition = "serviceable"
        cable.reference = copy.deepcopy(cable.reference)
        cable.reference["to_room"] = "INVENTED"
        self.assertFalse(certificate_valid(rows, pwr))
