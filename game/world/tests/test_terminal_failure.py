"""G6 terminal failure: authoritative Evennia state, private evidence and death."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.event_journal import inbox
from world.terminal_failure import (
    arm_terminal, audit_terminal, ensure_terminal_clock, observe_terminal, tick_terminal,
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

    def test_captain_can_use_reserve_only_after_reaching_environmental_plant(self):
        captain = self.ship["captain"]
        self.assertEqual(captain.location, self.ship["bridge"])
        denied = execute_work(
            captain, "4" * 32, "terminal_reserve", "ship",
        )
        self.assertEqual(denied["status"], "failed")
        self.assertEqual(self.ship["pump"].db.ox_terminal_incident["reserve_left"], 2)

        # Exercise the real Evennia relocation and the same receipt gateway
        # as a six-client scenario, not an operator mutation of resources.
        self.assertTrue(captain.move_to(self.ship["environmental"], quiet=True))
        self.assertEqual(captain.location, self.ship["environmental"])
        released = execute_work(
            captain, "5" * 32, "terminal_reserve", "ship",
        )
        self.assertEqual(released["status"], "succeeded")
        self.assertEqual(self.ship["pump"].db.ox_terminal_incident["reserve_left"], 1)
        self.assertEqual(
            execute_work(captain, "5" * 32, "terminal_reserve", "ship"),
            released,
        )
        self.assertEqual(self.ship["pump"].db.ox_terminal_incident["reserve_left"], 1)
        denied_command = execute_work(
            captain, "6" * 32, "terminal_command", "ship",
        )
        self.assertEqual(denied_command["status"], "failed")

        officer = self.ship["officer"]
        self.assertTrue(officer.move_to(self.ship["environmental"], quiet=True))
        forbidden = execute_work(
            officer, "7" * 32, "terminal_reserve", "ship",
        )
        self.assertEqual(forbidden["status"], "failed")
        self.assertEqual(self.ship["pump"].db.ox_terminal_incident["reserve_left"], 1)

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

    def test_post_server_operator_audit_serializes_real_evennia_savers(self):
        self.assertEqual(execute_work(
            self.ship["chief"], "b" * 32, "terminal_survey", "ship",
        )["status"], "succeeded")
        with TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "audit.json"
            report = audit_terminal(str(report_path))
            self.assertEqual(report["fatal"], False)
            parsed = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(
                parsed["actual_physical_work"][0]["verb"],
                "terminal_survey",
            )
            self.assertEqual(parsed["receipted_attempts"][0]["role"], "iona")

    def test_nominal_cartridge_replacement_is_valid_diagnostic_work(self):
        scrubber = self.ship["scrubber"]
        teo = self.ship["environment"]
        self.assertEqual(scrubber.state, "nominal")
        self.assertEqual(scrubber.db.spare_cartridges, 2)
        early = execute_work(teo, "e" * 32, "terminal_replace", "ship")
        self.assertEqual(early["status"], "failed")
        self.assertEqual(scrubber.db.spare_cartridges, 2)
        execute_work(teo, "a" * 32, "terminal_survey", "ship")
        replaced = execute_work(teo, "b" * 32, "terminal_replace", "ship")
        self.assertEqual(replaced["status"], "succeeded")
        self.assertEqual(scrubber.db.spare_cartridges, 1)
        self.assertEqual(scrubber.state, "nominal")
        self.assertEqual(
            execute_work(teo, "b" * 32, "terminal_replace", "ship"), replaced,
        )
        self.assertEqual(scrubber.db.spare_cartridges, 1)
        self.assertIn("pressure loss", observe_terminal(teo)["own_finding"])
        self.assertEqual(
            [e["operation"] for e in scrubber.db.event_history][-3:],
            ["diagnostic_isolate", "replace", "restart"],
        )
        for _ in range(60):
            tick_terminal()
        self.assertTrue(self.ship["pump"].db.ox_terminal_incident["fatal"])
        self.assertTrue(teo.db.ox_terminal_dead)

    def test_cartridge_shortage_and_crosscheck_are_physical_evidence(self):
        scrubber = self.ship["scrubber"]
        teo = self.ship["environment"]
        execute_work(teo, "c" * 32, "terminal_survey", "ship")
        scrubber.db.spare_cartridges = 0
        no_stock = execute_work(teo, "d" * 32, "terminal_replace", "ship")
        self.assertEqual(no_stock["status"], "failed")
        self.assertEqual(scrubber.state, "nominal")
        self.assertEqual(len(scrubber.db.event_history), 0)
        self.assertEqual(observe_terminal(teo)["local_cartridge_spares"], 0)
        self.assertIsNone(
            observe_terminal(self.ship["officer"])["local_cartridge_spares"]
        )
        crosscheck = execute_work(teo, "f" * 32, "terminal_crosscheck", "ship")
        self.assertEqual(crosscheck["status"], "succeeded")
        self.assertIn("Independent differential-pressure", observe_terminal(teo)["own_finding"])
        self.assertNotIn("Independent differential-pressure",
                         observe_terminal(self.ship["officer"])["own_finding"])

    def test_repeat_reports_and_captain_orders_need_new_evidence(self):
        teo = self.ship["environment"]
        captain = self.ship["captain"]
        execute_work(teo, "0" * 32, "terminal_survey", "ship")
        self.assertEqual(execute_work(
            teo, "1" * 32, "terminal_broadcast", "ship",
        )["status"], "succeeded")
        first = len([e for e in inbox(captain) if e["kind"] == "terminal_report"])
        self.assertEqual(first, 1)
        self.assertEqual(execute_work(
            teo, "2" * 32, "terminal_broadcast", "ship",
        )["status"], "failed")
        self.assertEqual(len([e for e in inbox(captain)
                              if e["kind"] == "terminal_report"]), first)
        self.assertEqual(execute_work(
            captain, "3" * 32, "terminal_command", "ship",
        )["status"], "succeeded")
        order_count = len([e for e in inbox(teo) if e["kind"] == "terminal_order"])
        self.assertEqual(execute_work(
            captain, "4" * 32, "terminal_command", "ship",
        )["status"], "failed")
        self.assertEqual(len([e for e in inbox(teo)
                              if e["kind"] == "terminal_order"]), order_count)
        execute_work(teo, "5" * 32, "terminal_crosscheck", "ship")
        self.assertEqual(execute_work(
            teo, "6" * 32, "terminal_broadcast", "ship",
        )["status"], "succeeded")
        self.assertEqual(execute_work(
            captain, "7" * 32, "terminal_command", "ship",
        )["status"], "succeeded")

