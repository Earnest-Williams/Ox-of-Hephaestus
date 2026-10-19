"""G6 terminal failure: authoritative Evennia state, private evidence and death."""
from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.event_journal import inbox
from world.terminal_failure import (
    arm_terminal, ensure_terminal_clock, observe_terminal, tick_terminal,
)
from world.work_actions import execute_work
from world.models import WorkReceipt


class TerminalFailureTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()
        self.case_id = arm_terminal(seed=241)

    def test_timer_is_only_started_from_real_server_lifecycle(self):
        """A management-shell arm must not schedule a disposable reactor."""
        from evennia.scripts.models import ScriptDB
        self.assertFalse(ScriptDB.objects.filter(
            db_key="ox_g6_terminal_clock",
        ).exists())
        with patch("evennia.utils.create.create_script") as created:
            self.assertTrue(ensure_terminal_clock())
            created.assert_called_once()
            kwargs = created.call_args.kwargs
            self.assertEqual(kwargs["obj"], self.ship["pump"])
            self.assertEqual(kwargs["interval"], 2)
            self.assertTrue(kwargs["persistent"])
            self.assertTrue(kwargs["start_delay"])
        self.ship["pump"].db.ox_terminal_incident = None
        with patch("evennia.utils.create.create_script") as created:
            self.assertFalse(ensure_terminal_clock())
            created.assert_not_called()

    def test_world_secret_never_enters_recipient_alarm(self):
        for role in ("officer", "watch", "chief", "cargo", "environment", "captain"):
            events = inbox(self.ship[role])
            alerts = [event for event in events if event["kind"] == "terminal_alarm"]
            self.assertEqual(len(alerts), 1)
            self.assertNotIn("fracture", str(alerts))
            obs = observe_terminal(self.ship[role])
            self.assertEqual(obs["character_dbref"], self.ship[role].dbref)
            self.assertNotIn("cause", obs)
            self.assertEqual(obs["status"], "alive")

    def test_real_work_requires_qualified_crew_and_station(self):
        self.assertEqual(execute_work(
            self.ship["chief"], "a" * 32, "terminal_survey", "ship",
        )["status"], "succeeded")
        mine = observe_terminal(self.ship["chief"])["own_finding"]
        self.assertIn("Fracture echoes", mine)
        self.assertEqual(observe_terminal(self.ship["officer"])["own_finding"], "")
        wrong = execute_work(
            self.ship["officer"], "b" * 32, "terminal_patch", "ship",
        )
        self.assertEqual(wrong["status"], "failed")
        self.assertEqual(execute_work(
            self.ship["chief"], "c" * 32, "terminal_patch", "ship",
        )["status"], "failed")
        self.assertEqual(execute_work(
            self.ship["chief"], "d" * 32, "terminal_broadcast", "ship",
        )["status"], "succeeded")
        published = [e for e in inbox(self.ship["captain"])
                     if e["kind"] == "terminal_report"]
        self.assertTrue(any("Fracture echoes" in e["text"] for e in published))
        self.assertEqual(
            execute_work(self.ship["chief"], "d" * 32, "terminal_broadcast", "ship")["status"],
            "succeeded",
        )
        self.assertEqual(len([
            e for e in inbox(self.ship["captain"]) if e["kind"] == "terminal_report"
        ]), len(published))
        with self.assertRaises(PermissionError):
            execute_work(self.ship["officer"], "d" * 32, "terminal_broadcast", "ship")

    def test_depletion_is_irreversible_and_character_death_persists(self):
        self.assertEqual(execute_work(
            self.ship["environment"], "1" * 32, "terminal_reserve", "ship",
        )["status"], "succeeded")
        self.assertEqual(execute_work(
            self.ship["environment"], "2" * 32, "terminal_reserve", "ship",
        )["status"], "succeeded")
        self.assertEqual(execute_work(
            self.ship["environment"], "3" * 32, "terminal_reserve", "ship",
        )["status"], "failed")
        for _ in range(100):
            tick_terminal()
        terminal = self.ship["pump"].db.ox_terminal_incident
        self.assertTrue(terminal["fatal"])
        self.assertLessEqual(terminal["terminal_at_minute"], 270)
        self.assertEqual(terminal["reserve_left"], 0)
        for key in ("officer", "watch", "chief", "cargo", "environment", "captain"):
            actor = self.ship[key]
            self.assertTrue(actor.db.ox_terminal_dead)
            self.assertFalse(actor.at_pre_move(self.ship["mess"]))
            with self.assertRaises(PermissionError):
                execute_work(actor, "f" * 32, "terminal_archive", "ship")
        self.assertEqual(WorkReceipt.objects.filter(operation="terminal_reserve").count(), 3)
        self.assertFalse(tick_terminal())

    def test_world_workflow_does_not_invent_scrubber_damage(self):
        self.assertEqual(self.ship["scrubber"].state, "nominal")
        r = execute_work(self.ship["environment"], "e" * 32, "terminal_replace", "ship")
        self.assertEqual(r["status"], "failed")
        self.assertEqual(self.ship["scrubber"].state, "nominal")
