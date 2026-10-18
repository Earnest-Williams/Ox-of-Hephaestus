"""World-owned hails: identity, location, bounded facts and at-most-once replies."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.crew_interaction import send_hail, answer_hail
from world.live_crew import inbox, fixture_setup


class CrewInteractionTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        fixture_setup(scheduled_clock=True)
        self.ship = build_ship()
        self.lin = self.ship["officer"]
        self.ari = self.ship["watch"]
        self.iona = self.ship["chief"]

    def test_private_hail_grounded_answer_and_no_duplicate_delivery(self):
        ok, response = send_hail(self.lin, "iona", "How is P-01?")
        self.assertTrue(ok, response)
        self.assertEqual(response, "OX_HAIL_ACCEPTED hail-0001")
        self.assertEqual(inbox(self.ari), [])
        self.assertEqual(inbox(self.iona)[0]["kind"], "crew_hail")
        self.assertEqual(inbox(self.lin)[-1]["kind"], "coolant_alarm")
        self.assertFalse(send_hail(self.lin, "iona", "again")[0])
        ok, answer = answer_hail(self.iona, "hail-0001", "status")
        self.assertTrue(ok, answer)
        reply = inbox(self.lin)[-1]
        self.assertEqual(reply["kind"], "crew_reply")
        self.assertIn("LOW PRESSURE", reply["text"])
        self.assertEqual(inbox(self.iona)[-1]["kind"], "hail_answered")
        length = len(inbox(self.lin))
        self.assertTrue(answer_hail(self.iona, "hail-0001", "status")[0])
        self.assertEqual(len(inbox(self.lin)), length)

    def test_wrong_recipient_refused_and_no_direct_physical_commands(self):
        self.assertFalse(send_hail(self.lin, "unknown", "test")[0])
        self.assertFalse(send_hail(self.lin, "ari", "a" * 161)[0])
        self.assertTrue(send_hail(self.lin, "ari", "Please isolate the pump")[0])
        self.assertFalse(answer_hail(self.iona, "hail-0001", "status")[0])
        self.assertFalse(answer_hail(self.ari, "hail-0001", "isolate")[0])
        self.assertEqual(self.ship["pump"].state, "low_pressure")
        self.assertTrue(answer_hail(self.ari, "hail-0001", "ack")[0])
        self.assertEqual(self.ship["pump"].state, "low_pressure")

    def test_unreachable_station_has_no_fabricated_readout(self):
        self.assertTrue(send_hail(self.lin, "iona", "Status?")[0])
        self.iona.location = self.ship["passage"]
        self.assertTrue(answer_hail(self.iona, "hail-0001", "status")[0])
        self.assertIn("cannot verify P-01", inbox(self.lin)[-1]["text"])
