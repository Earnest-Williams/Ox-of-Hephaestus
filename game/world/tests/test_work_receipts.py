"""World-owned idempotent requests across equipment and social procedures."""
from __future__ import annotations

from unittest.mock import patch

from django.db import transaction
from evennia.utils.test_resources import EvenniaTestCase

from commands.crew import CmdOxWork, CmdOxWorkReceipt
from world.bootstrap import build_ship
from world.crew_interaction import send_hail
from world.live_crew import fixture_setup, inbox, note_inspection
from world.models import WorkReceipt
from world.work_actions import execute_work, work_receipt


class WorldWorkTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        fixture_setup(scheduled_clock=True)
        self.ship = build_ship()
        self.pump = self.ship["pump"]
        self.lin = self.ship["officer"]
        self.ari = self.ship["watch"]
        self.iona = self.ship["chief"]
        self.teo = self.ship["environment"]
        self.mara = self.ship["cargo"]

    def test_repeated_bridge_radio_is_one_real_event(self):
        request_id = "a" * 32
        original = execute_work(self.lin, request_id, "radio")
        self.assertEqual(original["status"], "succeeded")
        self.assertEqual(original["target"], "ship")
        self.assertEqual(original["source_event_id"], inbox(self.ari)[-1]["event_id"])
        count = len(inbox(self.ari))
        self.assertEqual(execute_work(self.lin, request_id, "radio"), original)
        self.assertEqual(len(inbox(self.ari)), count)
        self.assertEqual(work_receipt(self.lin, request_id), original)
        self.assertEqual(work_receipt(self.iona, request_id)["status"], "unknown")
        with self.assertRaises(PermissionError):
            execute_work(self.iona, request_id, "radio")
        with self.assertRaises(PermissionError):
            execute_work(self.lin, request_id, "offer")

    def test_failed_authorization_stays_failed_after_state_change(self):
        request_id = "b" * 32
        denied = execute_work(self.teo, request_id, "isolate", "scrubber")
        self.assertEqual(denied["status"], "failed")
        self.assertEqual(denied["source_event_id"], None)
        self.assertTrue(self.ship["scrubber"].inject_fault()[0])
        self.ship["scrubber"].note_inspection(self.teo)
        self.assertEqual(execute_work(self.teo, request_id, "isolate", "scrubber"),
                         denied)
        accepted = execute_work(self.teo, "c" * 32, "isolate", "scrubber")
        self.assertEqual(accepted["status"], "succeeded")

    def test_global_id_cannot_cross_fixture_and_consumable_once(self):
        scrubber = self.ship["scrubber"]
        self.assertTrue(scrubber.inject_fault()[0])
        scrubber.note_inspection(self.teo)
        self.assertEqual(execute_work(self.teo, "a" * 32, "isolate", "scrubber")
                         ["status"], "succeeded")
        before = scrubber.db.spare_cartridges
        receipt = execute_work(self.teo, "b" * 32, "replace", "scrubber")
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(scrubber.db.spare_cartridges, before - 1)
        self.assertEqual(execute_work(self.teo, "b" * 32, "replace", "scrubber"),
                         receipt)
        self.assertEqual(scrubber.db.spare_cartridges, before - 1)
        with self.assertRaises(PermissionError):
            execute_work(self.ari, "b" * 32, "isolate", "pump")
        self.assertEqual(self.pump.state, "low_pressure")
        self.assertEqual(WorkReceipt.objects.count(), 2)

    def test_safety_request_approval_and_watch_transfer_are_idempotent(self):
        self.assertEqual(execute_work(self.ari, "1" * 32, "isolate", "pump")
                         ["status"], "succeeded")
        self.assertEqual(execute_work(self.ari, "2" * 32, "repair", "pump")
                         ["status"], "succeeded")
        self.assertFalse(self.pump.db.ox_chief_released)
        request = execute_work(self.ari, "3" * 32, "request")
        self.assertEqual(request["status"], "succeeded")
        self.assertEqual(execute_work(self.ari, "3" * 32, "request"), request)
        self.assertEqual([e["kind"] for e in inbox(self.iona)].count("release_request"), 1)
        refused = execute_work(self.iona, "4" * 32, "approve")
        self.assertEqual(refused["status"], "failed")
        note_inspection(self.iona, self.pump)
        self.assertEqual(execute_work(self.iona, "4" * 32, "approve"), refused)
        approved = execute_work(self.iona, "5" * 32, "approve")
        self.assertEqual(approved["status"], "succeeded")
        self.assertTrue(self.pump.db.ox_chief_released)
        self.assertEqual(execute_work(self.ari, "6" * 32, "commission", "pump")
                         ["status"], "succeeded")
        note_inspection(self.ari, self.pump)
        self.assertEqual(execute_work(self.ari, "7" * 32, "resolve")
                         ["status"], "succeeded")
        # The synthetic scenario uses a scheduled clock; no premature
        # watch transfer is invented by the action service.
        self.assertEqual(execute_work(self.ari, "8" * 32, "offer")
                         ["status"], "failed")

    def test_hail_answer_once_and_reconcile_private_receipt(self):
        self.assertTrue(send_hail(self.lin, "iona", "Is P-01 safe?")[0])
        args = {"hail_id": "hail-0001", "mode": "status"}
        outcome = execute_work(self.iona, "a" * 32, "answer",
                               arguments=args)
        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(len([x for x in inbox(self.lin)
                              if x["kind"] == "crew_reply"]), 1)
        self.assertEqual(execute_work(self.iona, "a" * 32, "answer",
                                      arguments=args), outcome)
        self.assertEqual(len([x for x in inbox(self.lin)
                              if x["kind"] == "crew_reply"]), 1)
        with self.assertRaises(PermissionError):
            execute_work(self.iona, "a" * 32, "answer",
                         arguments={"hail_id": "hail-0001", "mode": "decline"})
        self.assertEqual(work_receipt(self.ari, "a" * 32)["status"], "unknown")

    def test_game_command_receipt_is_authoritative_and_actor_bound(self):
        command = CmdOxWork()
        command.caller = self.lin
        command.args = "a" * 32 + " radio ship"
        with patch.object(self.lin, "msg") as sent:
            command.func()
        receipt = sent.call_args.kwargs["ox_receipt"][0][0]
        self.assertEqual(receipt["status"], "succeeded")
        receipt_command = CmdOxWorkReceipt()
        receipt_command.caller = self.lin
        receipt_command.args = "a" * 32
        with patch.object(self.lin, "msg") as seen:
            receipt_command.func()
        self.assertEqual(seen.call_args.kwargs["ox_receipt"][0][0], receipt)
        receipt_command.caller = self.ari
        with patch.object(self.ari, "msg") as other:
            receipt_command.func()
        self.assertEqual(other.call_args.kwargs["ox_receipt"][0][0]["status"],
                         "unknown")

    def test_world_receipt_and_private_events_rollback_together(self):
        before = WorkReceipt.objects.count()
        initial = len(inbox(self.ari))
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    execute_work(self.lin, "a" * 32, "radio")
                    raise RuntimeError("simulate failed world commit")
        self.assertEqual(WorkReceipt.objects.count(), before)
        self.assertEqual(len(inbox(self.ari)), initial)
