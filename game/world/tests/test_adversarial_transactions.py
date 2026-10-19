"""Failure injection for ordinary crew commands outside the oxwork adapter.

Evennia owns the real transaction. A mid-notification exception must never
consume a duty obligation or make an equipment fault undiscoverable.
"""
from __future__ import annotations

from unittest.mock import patch

from evennia.objects.models import ObjectDB
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship, find_fixture
from world.live_clock import tick_game_clock
from world.live_crew import (
    fixture_setup, inbox, note_inspection, offer_watch, accept_watch,
    request_release, approve_release, report_resolution,
)
from world.models import CrewEvent


def fail_second(real_emit):
    seen = [0]

    def fail(*args, **kwargs):
        seen[0] += 1
        if seen[0] == 2:
            raise RuntimeError("synthetic second recipient failure")
        return real_emit(*args, **kwargs)
    return fail


class DirectCommandAtomicityTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        fixture_setup(scheduled_clock=True)
        self.ship = build_ship()

    def test_direct_watch_accept_cannot_partially_publish_transfer(self):
        ship = self.ship
        self.assertFalse(tick_game_clock(now_game_time=100))
        self.assertTrue(tick_game_clock(now_game_time=106))
        self.assertTrue(offer_watch(ship["watch"])[0])
        before = CrewEvent.objects.count()
        from world import live_crew
        with patch.object(live_crew, "emit",
                          side_effect=fail_second(live_crew.emit)):
            with self.assertRaises(RuntimeError):
                accept_watch(ship["chief"])
        roster = find_fixture("roster-board")
        self.assertEqual(roster.db.ox_active_engineer, ship["watch"].dbref)
        self.assertEqual(roster.db.ox_handover_offer, ship["watch"].dbref)
        self.assertTrue(roster.db.ox_handover_due)
        self.assertEqual(CrewEvent.objects.count(), before)
        self.assertTrue(accept_watch(ship["chief"])[0])
        for role in ("watch", "chief"):
            self.assertEqual(
                [e["kind"] for e in inbox(ship[role])].count("watch_transferred"),
                1,
            )

    def test_direct_approval_and_resolution_are_never_half_published(self):
        ship = self.ship
        pump = ship["pump"]
        self.assertEqual(
            pump.durable_action("a" * 32, "isolate", ship["watch"])["status"],
            "succeeded",
        )
        self.assertEqual(
            pump.durable_action("b" * 32, "repair", ship["watch"])["status"],
            "succeeded",
        )
        self.assertTrue(request_release(ship["watch"])[0])
        note_inspection(ship["chief"], pump)
        from world import live_crew
        before = CrewEvent.objects.count()
        with patch.object(live_crew, "emit",
                          side_effect=fail_second(live_crew.emit)):
            with self.assertRaises(RuntimeError):
                approve_release(ship["chief"])
        self.assertFalse(find_fixture("pump-p01").db.ox_chief_released)
        self.assertEqual(CrewEvent.objects.count(), before)
        self.assertTrue(approve_release(ship["chief"])[0])
        self.assertEqual(
            pump.durable_action("c" * 32, "commission", ship["watch"])["status"],
            "succeeded",
        )
        note_inspection(ship["watch"], pump)
        before = CrewEvent.objects.count()
        with patch.object(live_crew, "emit",
                          side_effect=fail_second(live_crew.emit)):
            with self.assertRaises(RuntimeError):
                report_resolution(ship["watch"])
        self.assertFalse(find_fixture("pump-p01").db.ox_incident_closed)
        self.assertEqual(CrewEvent.objects.count(), before)
        self.assertTrue(report_resolution(ship["watch"])[0])

    def test_direct_release_request_failure_retains_future_request(self):
        ship = self.ship
        pump = ship["pump"]
        self.assertEqual(
            pump.durable_action("d" * 32, "isolate", ship["watch"])["status"],
            "succeeded",
        )
        self.assertEqual(
            pump.durable_action("e" * 32, "repair", ship["watch"])["status"],
            "succeeded",
        )
        with patch("world.live_crew.emit",
                   side_effect=RuntimeError("journal offline")):
            with self.assertRaises(RuntimeError):
                request_release(ship["watch"])
        self.assertIsNone(find_fixture("pump-p01").db.ox_release_request)
        self.assertTrue(request_release(ship["watch"])[0])


class DirectFaultAtomicityTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()

    def test_scrubber_fault_second_alert_failure_restores_world_truth(self):
        from world import live_crew
        before = CrewEvent.objects.count()
        with patch.object(live_crew, "emit",
                          side_effect=fail_second(live_crew.emit)):
            with self.assertRaises(RuntimeError):
                self.ship["scrubber"].inject_fault()
        self.assertEqual(CrewEvent.objects.count(), before)
        fresh = ObjectDB.objects.get(pk=self.ship["scrubber"].pk)
        fresh.attributes.reset_cache()
        self.assertEqual(fresh.state, "nominal")
        self.assertEqual(len(fresh.db.event_history), 0)

    def test_pump_alarm_failure_restores_physical_state(self):
        pump = self.ship["pump"]
        pump.db.ox_chief_gate = True
        with patch("world.live_crew.emit",
                   side_effect=RuntimeError("journal offline")):
            with self.assertRaises(RuntimeError):
                pump.inject_fault()
        fresh = ObjectDB.objects.get(pk=pump.pk)
        fresh.attributes.reset_cache()
        self.assertEqual(fresh.state, "normal")
        self.assertEqual(len(fresh.db.event_history), 0)
