"""P4e actor-bound durable receipts and specialist safety contracts."""
from __future__ import annotations

from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase
from commands.ship import CmdOxAction, CmdOxReceipt, CmdInspect
from world.bootstrap import build_ship
from world.crew_interaction import send_hail, answer_hail
from world.live_crew import inbox


class DurableSpecialistTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()
        self.cargo = self.ship["cargo"]
        self.teo = self.ship["environment"]
        self.ari = self.ship["watch"]
        self.lin = self.ship["officer"]
        self.cradle = self.ship["cradle"]
        self.scrubber = self.ship["scrubber"]

    def test_restow_and_certify_receipts_bound_to_mara(self):
        self.assertTrue(self.cradle.inject_fault()[0])
        self.cradle.note_inspection(self.cargo)
        ident = "a" * 32
        first = self.cradle.durable_action(ident, "restow", self.cargo)
        self.assertEqual(first["status"], "succeeded")
        self.assertEqual(first["source_event_id"], "c01-0002")
        self.cradle.refresh_from_db()
        self.assertEqual(self.cradle.durable_action(ident, "restow", self.cargo), first)
        self.assertEqual([e["operation"] for e in self.cradle.db.event_history],
                         ["shift", "restow"])
        with self.assertRaises(PermissionError):
            self.cradle.durable_action(ident, "certify", self.cargo)
        with self.assertRaises(PermissionError):
            self.cradle.durable_action(ident, "restow", self.ari)
        self.assertEqual(self.cradle.durable_receipt(ident, self.ari)["status"], "unknown")
        self.assertEqual(self.cradle.durable_receipt(ident, self.cargo), first)
        # Certification is a separate world action, after a *fresh* survey.
        denied = self.cradle.durable_action("b" * 32, "certify", self.cargo)
        self.assertEqual(denied["status"], "failed")
        self.cradle.note_inspection(self.cargo)
        self.assertEqual(self.cradle.durable_action("b" * 32, "certify", self.cargo), denied)
        self.assertEqual(self.cradle.durable_action("c" * 32, "certify", self.cargo)["status"],
                         "succeeded")
        self.assertEqual(self.cradle.state, "secured")

    def test_consumable_cartridge_is_debited_once_after_lost_ack(self):
        self.assertTrue(self.scrubber.inject_fault()[0])
        self.scrubber.note_inspection(self.teo)
        self.assertEqual(
            self.scrubber.durable_action("d" * 32, "isolate", self.teo)["status"],
            "succeeded",
        )
        before = int(self.scrubber.db.spare_cartridges)
        initial = self.scrubber.durable_action("e" * 32, "replace", self.teo)
        self.assertEqual(initial["status"], "succeeded")
        self.assertEqual(initial["source_event_id"], "a01-0003")
        self.scrubber.refresh_from_db()
        self.assertEqual(self.scrubber.durable_receipt("e" * 32, self.teo), initial)
        self.assertEqual(self.scrubber.durable_action("e" * 32, "replace", self.teo), initial)
        self.assertEqual(self.scrubber.db.spare_cartridges, before - 1)
        self.assertEqual(self.scrubber.durable_receipt("e" * 32, self.lin)["status"],
                         "unknown")
        self.assertEqual(self.scrubber.durable_action("f" * 32, "replace", self.ari)
                         ["status"], "failed")
        self.scrubber.note_inspection(self.teo)
        self.assertEqual(
            self.scrubber.durable_action("0" * 32, "restart", self.teo)["status"],
            "succeeded",
        )
        self.assertEqual(self.scrubber.state, "nominal")
        self.assertEqual(
            [e["operation"] for e in self.scrubber.db.event_history],
            ["saturate", "isolate", "replace", "restart"],
        )

    def test_commands_preserve_pump_two_argument_contract(self):
        def command(kind, person, args):
            cmd = kind()
            cmd.caller = person
            cmd.args = args
            with patch.object(person, "msg") as output:
                cmd.func()
                return output.call_args.kwargs if output.call_args.kwargs else (
                    output.call_args.args[0]
                )
        self.assertTrue(self.cradle.inject_fault()[0])
        command(CmdInspect, self.cargo, "cargo")
        response = command(CmdOxAction, self.cargo, "1" * 32 + " restow cargo")
        receipt = response["ox_receipt"][0][0]
        self.assertEqual(receipt["status"], "succeeded")
        seen = command(CmdOxReceipt, self.cargo, "1" * 32 + " cargo")
        self.assertEqual(seen["ox_receipt"][0][0], receipt)
        self.assertEqual(command(CmdOxReceipt, self.ari, "1" * 32 + " cargo")
                         ["ox_receipt"][0][0]["status"], "unknown")
        self.assertTrue(self.ship["pump"].inject_fault()[0])
        historical = command(CmdOxAction, self.ari, "2" * 32 + " isolate")
        self.assertEqual(historical["ox_receipt"][0][0]["status"], "succeeded")
        self.assertEqual(self.ship["pump"].state, "isolated")

    def test_specialist_hail_is_grounded_and_only_addressed_to_one(self):
        self.assertTrue(self.cradle.inject_fault()[0])
        self.assertTrue(self.scrubber.inject_fault()[0])
        self.assertTrue(send_hail(self.lin, "mara", "Are the restraints safe?")[0])
        self.assertTrue(send_hail(self.lin, "teo", "What about the scrubber?")[0])
        self.assertEqual([e["kind"] for e in inbox(self.cargo)],
                         ["cargo_shift", "crew_hail"])
        self.assertEqual([e["kind"] for e in inbox(self.teo)],
                         ["atmosphere_alarm", "crew_hail"])
        self.assertTrue(answer_hail(self.cargo, "hail-0001", "status")[0])
        self.assertTrue(answer_hail(self.teo, "hail-0002", "status")[0])
        replies = [e["text"] for e in inbox(self.lin) if e["kind"] == "crew_reply"]
        self.assertEqual(len(replies), 2)
        self.assertIn("UNSECURED", replies[0])
        self.assertIn("SATURATED", replies[1])
        self.assertFalse(answer_hail(self.ari, "hail-0001", "status")[0])
        self.assertEqual(self.cradle.state, "unsecured")
        self.assertEqual(self.scrubber.state, "saturated")
