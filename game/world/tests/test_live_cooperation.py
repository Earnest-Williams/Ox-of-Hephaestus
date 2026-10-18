"""Database-backed P3c cooperation, privacy and physical authorization gates."""
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.live_crew import (
    fixture_setup, inbox, relay_alarm, note_inspection, request_release,
    approve_release, report_resolution, offer_watch, accept_watch,
)

class LiveCrewWorldTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        fixture_setup()
        self.ship = build_ship()
        self.pump = self.ship["pump"]
        self.ari = self.ship["watch"]
        self.iona = self.ship["chief"]
        self.lin = self.ship["officer"]
        self.roster = self.ship["roster"]

    def _repair(self):
        self.assertEqual(self.pump.durable_action("a" * 32, "isolate", self.ari)["status"], "succeeded")
        self.assertEqual(self.pump.durable_action("b" * 32, "repair", self.ari)["status"], "succeeded")
        self.assertEqual(self.pump.state, "repaired")

    def test_private_alarm_and_role_scoped_radio(self):
        self.assertEqual([x["kind"] for x in inbox(self.lin)], ["coolant_alarm"])
        self.assertEqual(inbox(self.ari), [])
        self.assertEqual(inbox(self.iona), [])
        self.assertFalse(relay_alarm(self.ari)[0])
        self.assertTrue(relay_alarm(self.lin)[0])
        self.assertEqual([x["kind"] for x in inbox(self.ari)], ["radio_alert"])
        self.assertEqual([x["kind"] for x in inbox(self.lin)], ["coolant_alarm"])
        self.assertEqual(inbox(self.iona), [])
        for actor in (self.ari, self.iona, self.lin):
            self.assertTrue(all(x["recipient_dbref"] == actor.dbref for x in inbox(actor)))

    def test_chief_inspection_before_commission_and_verification_before_closure(self):
        self._repair()
        self.assertFalse(self.pump.commission(self.ari)[0])
        self.assertFalse(approve_release(self.iona)[0])
        self.assertFalse(request_release(self.lin)[0])
        self.assertTrue(request_release(self.ari)[0])
        self.assertFalse(approve_release(self.iona)[0])
        note_inspection(self.iona, self.pump)
        self.assertTrue(approve_release(self.iona)[0])
        self.assertEqual(self.pump.durable_action("c" * 32, "commission", self.ari)["status"], "succeeded")
        self.assertFalse(report_resolution(self.ari)[0])
        note_inspection(self.ari, self.pump)
        self.assertTrue(report_resolution(self.ari)[0])
        self.assertTrue(self.pump.db.ox_incident_closed)
        self.assertIn("incident_resolved", [x["kind"] for x in inbox(self.lin)])
        self.assertNotIn("release_request", [x["kind"] for x in inbox(self.lin)])
        self.assertIn("release_request", [x["kind"] for x in inbox(self.iona)])
        self.assertNotIn("coolant_alarm", [x["kind"] for x in inbox(self.iona)])

    def test_real_world_handover_requires_offered_due_watch(self):
        self.assertFalse(offer_watch(self.ari)[0])
        self.assertFalse(accept_watch(self.iona)[0])
        self._repair()
        self.assertTrue(request_release(self.ari)[0])
        note_inspection(self.iona, self.pump)
        self.assertTrue(approve_release(self.iona)[0])
        self.assertEqual(self.pump.durable_action("c" * 32, "commission", self.ari)["status"], "succeeded")
        note_inspection(self.ari, self.pump)
        self.assertTrue(report_resolution(self.ari)[0])
        self.assertEqual(self.roster.db.ox_world_minute, 475)
        self.assertFalse(accept_watch(self.iona)[0])
        self.assertTrue(offer_watch(self.ari)[0])
        self.assertTrue(accept_watch(self.iona)[0])
        self.assertEqual(self.roster.db.ox_active_engineer, self.iona.dbref)
        self.assertFalse(self.roster.db.ox_handover_due)
        self.assertEqual(inbox(self.iona)[-1]["kind"], "watch_transferred")
        self.assertEqual(inbox(self.ari)[-1]["kind"], "watch_transferred")

    def test_second_fault_reopens_incident_without_prior_approval(self):
        self._repair()
        self.assertTrue(request_release(self.ari)[0])
        note_inspection(self.iona, self.pump)
        self.assertTrue(approve_release(self.iona)[0])
        self.assertEqual(self.pump.durable_action("c" * 32, "commission", self.ari)["status"], "succeeded")
        note_inspection(self.ari, self.pump)
        self.assertTrue(report_resolution(self.ari)[0])
        previous = self.pump.db.ox_active_alarm
        self.assertTrue(self.pump.inject_fault()[0])
        self.assertNotEqual(self.pump.db.ox_active_alarm, previous)
        self.assertFalse(self.pump.db.ox_incident_closed)
        self.assertFalse(self.pump.db.ox_chief_released)
        self.assertIsNone(self.pump.db.ox_release_request)
        self.assertEqual([e["kind"] for e in inbox(self.lin)].count("coolant_alarm"), 2)
        self.assertFalse(self.pump.commission(self.ari)[0])
