"""Database-backed tests for the first playable Evennia spaceship fixture."""

from __future__ import annotations

from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase

from commands.ship import CmdInspect, CmdIsolate, CmdRepair
from world.bootstrap import build_ship, find_fixture


class ShipWorldTests(EvenniaTestCase):
    """Exercise real Evennia objects, exits, permissions and persisted state."""

    def setUp(self) -> None:
        """Construct the small ship in Evennia's isolated test database."""
        super().setUp()
        self.ship = build_ship()

    def test_three_compartments_have_bidirectional_exits(self):
        """Traverse the navigable bridge/passage/engineering graph."""
        ship = self.ship
        self.assertIsNone(ship["bridge"].location)
        self.assertIsNone(ship["passage"].location)
        self.assertIsNone(ship["engineering"].location)
        self.assertEqual(
            find_fixture("exit-bridge-passage").destination, ship["passage"]
        )
        self.assertEqual(
            find_fixture("exit-passage-bridge").destination, ship["bridge"]
        )
        self.assertEqual(
            find_fixture("exit-passage-engineering").destination,
            ship["engineering"],
        )
        self.assertEqual(
            find_fixture("exit-engineering-passage").destination,
            ship["passage"],
        )
        self.assertTrue(ship["watch"].move_to(ship["passage"], quiet=True))
        self.assertEqual(ship["watch"].location, ship["passage"])

    def test_seed_is_idempotent_and_preserves_operating_state(self):
        """Repeated setup must not duplicate crew or reset a real fault."""
        ship = self.ship
        ok, _message = ship["pump"].inject_fault()
        self.assertTrue(ok)
        self.assertTrue(ship["watch"].move_to(ship["passage"], quiet=True))
        another = build_ship()
        self.assertEqual(ship["pump"].id, another["pump"].id)
        self.assertEqual(ship["watch"].id, another["watch"].id)
        self.assertEqual(ship["watch"].location, ship["passage"])
        self.assertEqual(another["pump"].state, "low_pressure")
        self.assertEqual(len(another["pump"].db.event_history), 1)
        for marker in (
            "room-bridge",
            "room-passage",
            "room-engineering",
            "pump-p01",
            "crew-chief",
            "crew-watch",
            "crew-bridge",
        ):
            self.assertIsNotNone(find_fixture(marker))

    def test_engineering_cycle_requires_rights_and_locality(self):
        """A real pump changes state only through legitimate game actions."""
        pump = self.ship["pump"]
        watch = self.ship["watch"]
        officer = self.ship["officer"]
        self.assertEqual(pump.state, "normal")

        ok, _ = pump.repair(watch)
        self.assertFalse(ok)
        ok, _ = pump.inject_fault()
        self.assertTrue(ok)
        ok, _ = pump.isolate(officer)
        self.assertFalse(ok)
        self.assertEqual(pump.state, "low_pressure")

        self.assertTrue(watch.move_to(self.ship["passage"], quiet=True))
        ok, _ = pump.isolate(watch)
        self.assertFalse(ok)
        self.assertTrue(watch.move_to(self.ship["engineering"], quiet=True))
        for command in (pump.isolate, pump.repair, pump.commission):
            ok, _ = command(watch)
            self.assertTrue(ok)
        self.assertEqual(pump.state, "normal")
        events = pump.db.event_history
        self.assertEqual(
            [event["operation"] for event in events],
            ["fault", "isolate", "repair", "commission"],
        )
        self.assertEqual(
            [event["event_id"] for event in events],
            ["p01-0001", "p01-0002", "p01-0003", "p01-0004"],
        )
        self.assertEqual(events[1]["actor_dbref"], watch.dbref)
        self.assertTrue(all(isinstance(event["game_time"], float) for event in events))

    def test_inspection_is_character_local_but_bridge_has_telemetry(self):
        """The bridge receives measurements, not magical access to pump verbs."""
        bridge_officer = self.ship["officer"]
        pump = self.ship["pump"]
        self.assertIn("NORMAL", self.ship["console"].readout())
        pump.inject_fault()
        self.assertIn("LOW PRESSURE", self.ship["console"].readout())
        self.assertIn("Engineer Ari Sen", self.ship["roster"].readout())

        cmd = CmdInspect()
        cmd.caller = bridge_officer
        cmd.args = "console"
        with patch.object(bridge_officer, "msg") as output:
            cmd.func()
            output.assert_called_once()
            self.assertIn("LOW PRESSURE", str(output.call_args.args[0]))

        # A physical action requires proximity, even when the sensor reports
        # the failure remotely.
        ok, _ = pump.isolate(bridge_officer)
        self.assertFalse(ok)
        self.assertEqual(pump.state, "low_pressure")

    def test_equipment_cannot_be_removed_or_repaired_from_the_bridge(self):
        """Lookups and operations cannot bypass compartment or permission rules."""
        pump = self.ship["pump"]
        officer = self.ship["officer"]
        watch = self.ship["watch"]
        self.assertFalse(pump.access(watch, "get"))
        with patch.object(watch, "msg"):
            self.assertFalse(pump.at_pre_get(watch))

        cmd = CmdIsolate()
        cmd.caller = officer
        cmd.args = "pump"
        with patch.object(officer, "msg") as output:
            cmd.func()
            self.assertTrue(output.called)
        self.assertEqual(pump.state, "normal")

        cmd = CmdRepair()
        cmd.caller = watch
        cmd.args = "pump"
        with patch.object(watch, "msg") as output:
            cmd.func()
            self.assertIn("Cannot repair", str(output.call_args.args[0]))
