"""Game-owned duty timer and post-handover independent safety authority."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.live_clock import tick_game_clock
from world.live_crew import (
    fixture_setup, inbox, relay_alarm, note_inspection,
    request_release, approve_release, report_resolution,
    offer_watch, accept_watch,
)


class AutonomousWorldTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        fixture_setup(scheduled_clock=True)
        self.ship = build_ship()
        self.pump = self.ship["pump"]
        self.ari = self.ship["watch"]
        self.iona = self.ship["chief"]
        self.lin = self.ship["officer"]
        self.roster = self.ship["roster"]

    def _first_incident(self):
        self.assertEqual(
            self.pump.durable_action("a" * 32, "isolate", self.ari)["status"],
            "succeeded",
        )
        self.assertEqual(
            self.pump.durable_action("b" * 32, "repair", self.ari)["status"],
            "succeeded",
        )
        self.assertTrue(request_release(self.ari)[0])
        self.assertFalse(approve_release(self.ari)[0])
        note_inspection(self.iona, self.pump)
        self.assertTrue(approve_release(self.iona)[0])
        self.assertEqual(
            self.pump.durable_action("c" * 32, "commission", self.ari)["status"],
            "succeeded",
        )
        note_inspection(self.ari, self.pump)
        self.assertTrue(report_resolution(self.ari)[0])

    def test_world_timer_is_idempotent_and_not_inferred_from_resolution(self):
        self.assertFalse(tick_game_clock(now_game_time=100.0))
        self.assertFalse(tick_game_clock(now_game_time=104.5))
        self.assertFalse(self.roster.db.ox_handover_due)
        self._first_incident()
        # Incident closure must not manufacture a watch due event.
        self.assertFalse(self.roster.db.ox_handover_due)
        self.assertTrue(tick_game_clock(now_game_time=106.0))
        self.assertFalse(tick_game_clock(now_game_time=107.0))
        self.assertTrue(self.roster.db.ox_handover_due)
        self.assertEqual(
            [e["kind"] for e in inbox(self.ari)].count("handover_due"), 1
        )
        self.assertEqual(
            [e["kind"] for e in inbox(self.iona)].count("handover_due"), 1
        )
        self.assertNotIn("handover_due", [e["kind"] for e in inbox(self.lin)])

    def test_relief_engineer_can_repair_second_fault_but_cannot_self_approve(self):
        tick_game_clock(now_game_time=100)
        tick_game_clock(now_game_time=106)
        self._first_incident()
        self.assertTrue(offer_watch(self.ari)[0])
        self.assertTrue(accept_watch(self.iona)[0])
        self.assertEqual(self.roster.db.ox_active_engineer, self.iona.dbref)
        self.assertEqual(self.roster.db.ox_safety_reviewer, self.ari.dbref)
        self.assertTrue(self.pump.inject_fault()[0])
        self.assertTrue(relay_alarm(self.lin)[0])
        self.assertEqual(inbox(self.iona)[-1]["kind"], "radio_alert")
        self.assertEqual(
            self.pump.durable_action("d" * 32, "isolate", self.ari)["status"],
            "failed",
        )
        self.assertEqual(
            self.pump.durable_action("e" * 32, "isolate", self.iona)["status"],
            "succeeded",
        )
        self.assertEqual(
            self.pump.durable_action("f" * 32, "repair", self.iona)["status"],
            "succeeded",
        )
        self.assertTrue(request_release(self.iona)[0])
        self.assertFalse(approve_release(self.iona)[0])
        self.assertFalse(approve_release(self.lin)[0])
        self.assertFalse(approve_release(self.ari)[0])
        note_inspection(self.ari, self.pump)
        self.assertTrue(approve_release(self.ari)[0])
        self.assertEqual(
            self.pump.durable_action("1" * 32, "commission", self.iona)["status"],
            "succeeded",
        )
        self.assertFalse(report_resolution(self.iona)[0])
        note_inspection(self.iona, self.pump)
        self.assertTrue(report_resolution(self.iona)[0])
        self.assertEqual(self.pump.state, "normal")
        self.assertTrue(self.pump.db.ox_incident_closed)
        self.assertEqual(
            [e["kind"] for e in inbox(self.lin)].count("coolant_alarm"), 2
        )
        self.assertEqual(inbox(self.ari)[-1]["kind"], "incident_resolved")


    def test_failed_second_due_notification_preserves_deadline(self):
        from unittest.mock import patch
        from world import live_clock
        from world.event_journal import emit as original_emit
        from world.models import CrewEvent
        self.assertFalse(tick_game_clock(now_game_time=100.0))
        before = CrewEvent.objects.count()
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("journal interruption")
            return original_emit(*args, **kwargs)
        with patch.object(live_clock, "tick_game_clock", wraps=tick_game_clock):
            with patch("world.live_crew.emit", side_effect=fail_second):
                with self.assertRaises(RuntimeError):
                    tick_game_clock(now_game_time=106.0)
        self.assertFalse(self.roster.db.ox_handover_due)
        self.assertEqual(CrewEvent.objects.count(), before)
        self.assertTrue(tick_game_clock(now_game_time=106.0))
        self.assertEqual([e["kind"] for e in inbox(self.ari)].count("handover_due"), 1)
        self.assertEqual([e["kind"] for e in inbox(self.iona)].count("handover_due"), 1)



if __name__ == "__main__":
    import unittest
    unittest.main()
