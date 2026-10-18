"""P2 watch-handover acceptance: privacy, duties, restarts, zero idle work.

All of this is a stdlib-only deterministic mock; no model or Evennia import.
"""

import json
import unittest

from ox_ai.agents.crew import StaleAgentRevision
from ox_ai.ports.base import ActionRequest, WorldObservation
from ox_ai.ports.mock.watch_world import MockWatchWorld
from ox_ai.scheduler.watch import WatchSupervisor


class WatchHandoverTests(unittest.TestCase):
    def setUp(self):
        self.world = MockWatchWorld()
        self.handler = WatchSupervisor(self.world)
        self.concern = "P-01 pressure oscillation; unverified, check next watch"

    def test_idle_time_does_not_wake_any_agent_or_call_a_model(self):
        self.assertEqual(self.handler.advance_to(300), 0)
        self.assertEqual(self.handler.advance_to(474), 0)
        self.assertEqual(self.handler.pump(), 0)
        self.assertEqual(self.handler.wake_counts, {
            "ari": 0, "iona": 0, "lin": 0
        })
        self.assertEqual(self.handler.world_submissions, 0)
        self.assertEqual(self.handler.inference_calls, 0)
        self.assertEqual(self.world.events, ())
        self.assertEqual(self.world.active_watch["engineering"], "ari")

    def test_three_people_have_separate_authorised_knowledge(self):
        self.world.advance_to(450)
        sensor_id = self.world.sense_pressure_drift(self.concern)
        bridge_id = self.world.bridge_navigation_update(
            "Navigation plot nominal; remain on assigned bridge watch"
        )
        self.assertEqual(self.handler.pump(), 2)
        self.assertEqual(self.handler.wake_counts, {
            "ari": 1, "iona": 0, "lin": 1
        })

        ari = self.handler.agents["ari"]
        iona = self.handler.agents["iona"]
        lin = self.handler.agents["lin"]
        self.assertEqual(ari.memories[0]["source_event_id"], sensor_id)
        self.assertEqual(lin.memories[0]["source_event_id"], bridge_id)
        self.assertIn(self.concern, ari.memories[0]["text"])
        self.assertFalse(iona.memories)
        self.assertTrue(all(
            self.concern not in event["text"] for event in lin.memories
        ))
        self.assertTrue(all(
            "Navigation plot" not in event["text"] for event in ari.memories
        ))
        self.assertEqual(self.handler.world_submissions, 0)

        self.assertEqual(self.handler.advance_to(474), 0)
        self.assertEqual(self.handler.advance_to(475), 5)
        self.assertEqual(self.world.active_watch["engineering"], "iona")
        self.assertFalse(ari.active_watch)
        self.assertTrue(iona.active_watch)
        self.assertEqual(self.handler.world_submissions, 2)
        self.assertEqual(self.handler.inference_calls, 0)
        self.assertEqual(self.handler.wake_counts, {
            "ari": 4, "iona": 2, "lin": 1
        })
        self.assertEqual(
            [e["kind"] for e in iona.memories],
            ["handover_report", "watch_transferred"],
        )
        reported = iona.memories[0]
        self.assertIn(self.concern, reported["text"])
        self.assertIn("Unverified observation", reported["text"])
        # Iona's knowledge is reported testimony, not a direct sensor read.
        self.assertEqual(reported["kind"], "handover_report")
        self.assertNotIn(sensor_id, [
            e["source_event_id"] for e in iona.memories
        ])
        self.assertEqual(
            [e["kind"] for e in lin.memories], ["bridge_status"]
        )
        self.assertTrue(all(
            self.concern not in e["text"] for e in lin.memories
        ))
        self.assertEqual(self.handler.advance_to(476), 0)
        self.assertEqual(self.handler.world_submissions, 2)

    def test_empty_handover_is_allowed_but_still_requires_acknowledgment(self):
        self.handler.advance_to(475)
        self.assertEqual(self.world.active_watch["engineering"], "iona")
        notes = self.handler.agents["iona"].memories
        self.assertIn("No outstanding concerns", notes[0]["text"])
        self.assertEqual(self.handler.world_submissions, 2)

    def test_world_rejects_early_wrong_party_and_forged_acceptance(self):
        premature = ActionRequest(
            "early", "ari", "report_handover", "iona",
            {"summary": "No concerns"},
        )
        self.assertEqual(self.world.submit(premature).status, "failed")
        self.assertEqual(self.world.active_watch["engineering"], "ari")

        self.world.advance_to(475)
        self.assertTrue(self.world.announce_handover_due())
        self.assertFalse(self.world.announce_handover_due())
        impostor = ActionRequest(
            "fake", "lin", "report_handover", "iona",
            {"summary": "Ship looks healthy"},
        )
        self.assertEqual(self.world.submit(impostor).status, "failed")
        forged = ActionRequest(
            "fake-ack", "iona", "accept_watch", "ari",
            {"report_id": "mock-99999"},
        )
        self.assertEqual(self.world.submit(forged).status, "failed")
        self.assertEqual(self.world.active_watch["engineering"], "ari")
        self.assertEqual(
            [e.kind for e in self.world.events].count("handover_report"), 0
        )

    def test_deduplicated_request_id_cannot_duplicate_report(self):
        self.world.advance_to(475)
        self.world.announce_handover_due()
        req = ActionRequest(
            "stable-report-id", "ari", "report_handover", "iona",
            {"summary": "Unverified pressure concern"},
        )
        first = self.world.submit(req)
        second = self.world.submit(req)
        self.assertEqual(first, second)
        self.assertEqual(first.status, "succeeded")
        self.assertEqual(
            [e.kind for e in self.world.events].count("handover_report"), 1
        )
        with self.assertRaises(ValueError):
            self.world.submit(ActionRequest(
                "stable-report-id", "ari", "report_handover", "iona",
                {"summary": "changed content"},
            ))
        with self.assertRaises(PermissionError):
            self.world.reconcile("stable-report-id", character_id="lin")

    def test_handler_restart_and_unknown_ack_do_not_repeat_report(self):
        self.world.advance_to(450)
        self.world.sense_pressure_drift(self.concern)
        self.handler.pump()
        self.world.advance_to(475)
        self.world.announce_handover_due()
        item = self.world.next_observation()
        self.assertEqual(item[0], "ari")
        outgoing = self.handler.agents["ari"]
        request = outgoing.observe(item[1])
        self.assertEqual(request.verb, "report_handover")
        # World acted, but handler lost the response before it could learn
        # that the report was delivered to the relief engineer.
        lost_ack = self.world.submit(request, drop_ack=True)
        outgoing.record_outcome(lost_ack)
        self.assertEqual(lost_ack.status, "unknown")
        self.assertEqual(outgoing.pending_requests, (request,))

        durable_checkpoint = json.loads(json.dumps(self.handler.snapshot()))
        restarted = WatchSupervisor.from_snapshot(
            self.world, durable_checkpoint
        )
        self.assertEqual(
            restarted.agents["ari"].pending_requests, (request,)
        )
        self.assertEqual(restarted.reconcile_pending(), 1)
        self.assertFalse(restarted.agents["ari"].pending_requests)
        # The scheduled wake may be replayed after restart, but the world
        # delivers handover_due at most once. Never resend the operation.
        restarted.advance_to(475)
        self.assertEqual(self.world.active_watch["engineering"], "iona")
        self.assertEqual(
            [e.kind for e in self.world.events].count("handover_report"), 1
        )
        self.assertEqual(
            [e.kind for e in self.world.events].count("watch_transferred"), 2
        )
        self.assertEqual(restarted.inference_calls, 0)

    def test_no_cross_character_delivery_or_duplicate_memory(self):
        world_event = WorldObservation(
            "scope-1", "ari", 300, "Private engineering status",
            source_event_id="scope-1", kind="sensor_concern",
            data={"summary": "Pump vibration"},
        )
        with self.assertRaises(PermissionError):
            self.handler.agents["lin"].observe(world_event)
        outgoing = self.handler.agents["ari"]
        self.assertIsNone(outgoing.observe(world_event))
        self.assertIsNone(outgoing.observe(world_event))
        self.assertEqual(outgoing.revision, 1)
        self.assertEqual(len(outgoing.memories), 1)
        with self.assertRaises(StaleAgentRevision):
            outgoing.observe(
                WorldObservation("two", "ari", 301, "New event"),
                expected_revision=0,
            )

    def test_budget_interrupt_preserves_remaining_delivery_queue(self):
        self.world.advance_to(450)
        self.world.sense_pressure_drift("Check vibration")
        self.world.bridge_navigation_update("Flight plan on course")
        with self.assertRaisesRegex(RuntimeError, "budget"):
            self.handler.pump(max_deliveries=1)
        self.assertEqual(self.handler.wake_counts["ari"], 1)
        self.assertEqual(self.handler.wake_counts["lin"], 0)
        self.assertEqual(self.world.pending_observations, 1)
        self.assertEqual(self.handler.pump(), 1)
        self.assertEqual(self.handler.wake_counts["lin"], 1)
        self.assertEqual(self.handler.world_submissions, 0)

    def test_clock_never_moves_backward(self):
        self.world.advance_to(470)
        with self.assertRaises(ValueError):
            self.world.advance_to(469)
        with self.assertRaises(ValueError):
            self.world.announce_handover_due()
        with self.assertRaises(ValueError):
            self.handler.schedule(469, "engineering_handover")


if __name__ == "__main__":
    unittest.main()
