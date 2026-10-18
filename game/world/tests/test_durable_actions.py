"""Real-world SQLite tests of durable, world-authoritative pump actions."""

from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship


class DurableActionTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()
        self.pump = self.ship["pump"]
        self.assertTrue(self.pump.inject_fault()[0])

    def test_action_once_on_same_id_and_collision_refused(self):
        req = "a" * 32
        receipt = self.pump.durable_action(req, "isolate", self.ship["watch"])
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(self.pump.durable_action(req, "isolate", self.ship["watch"]), receipt)
        self.assertEqual([e["operation"] for e in self.pump.db.event_history],
                         ["fault", "isolate"])
        with self.assertRaises(PermissionError):
            self.pump.durable_action(req, "repair", self.ship["watch"])
        with self.assertRaises(PermissionError):
            self.pump.durable_action(req, "isolate", self.ship["officer"])
        self.assertEqual(self.pump.state, "isolated")

    def test_only_actor_can_reconcile_persistent_result(self):
        req = "b" * 32
        receipt = self.pump.durable_action(req, "isolate", self.ship["watch"])
        self.pump.refresh_from_db()
        self.assertEqual(self.pump.durable_receipt(req, self.ship["watch"]), receipt)
        self.assertEqual(self.pump.durable_receipt(req, self.ship["officer"])["status"],
                         "unknown")
        self.assertIsNone(self.pump.durable_receipt("c" * 32, self.ship["watch"])
                          ["source_event_id"])

    def test_failed_command_does_not_turn_into_success_on_replay(self):
        req = "d" * 32
        denied = self.pump.durable_action(req, "repair", self.ship["watch"])
        self.assertEqual(denied["status"], "failed")
        self.pump.durable_action("e" * 32, "isolate", self.ship["watch"])
        self.assertEqual(self.pump.durable_action(req, "repair", self.ship["watch"]), denied)
        self.assertEqual(self.pump.state, "isolated")

    def test_bridge_officer_cannot_execute_remote_engineering(self):
        denied = self.pump.durable_action("f" * 32, "isolate", self.ship["officer"])
        self.assertEqual(denied["status"], "failed")
        self.assertEqual(self.pump.state, "low_pressure")
