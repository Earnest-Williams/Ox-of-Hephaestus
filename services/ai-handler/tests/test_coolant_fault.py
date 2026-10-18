"""P2 Scenario 1 acceptance, on the independent deterministic mock world.

No model, Concordia, Evennia or network access is needed. The test *does*
exercise the existing genuine GOAP search engine for the engineer's repairs.
"""

import json
import unittest

from ox_ai.agents.crew import StaleAgentRevision
from ox_ai.ports.base import ActionRequest, WorldObservation
from ox_ai.ports.mock.coolant_world import MockCoolantWorld
from ox_ai.scenarios.coolant_fault import run_demo
from ox_ai.scheduler.coolant import CoolantSupervisor


class CoordinatedCoolantTests(unittest.TestCase):
    def setUp(self):
        self.world = MockCoolantWorld()
        self.supervisor = CoolantSupervisor(self.world)

    def _incident(self):
        self.world.advance_to(180)
        alarm = self.world.trigger_fault()
        deliveries = self.supervisor.pump()
        return alarm, deliveries

    def test_three_crew_coordinate_actual_mock_pump_repair_without_llm(self):
        alarm, delivered = self._incident()
        self.assertGreaterEqual(delivered, 12)
        self.assertEqual(self.world.pump_state, "normal")
        self.assertTrue(self.world.incident_closed)
        self.assertEqual(self.supervisor.inference_calls, 0)
        self.assertEqual(self.supervisor.world_submissions, 10)
        self.assertGreaterEqual(self.supervisor.planning_calls, 2)
        self.assertGreater(self.supervisor.expanded_states, 0)
        self.assertEqual(self.supervisor.replans, 0)
        self.assertEqual(
            [(e.operation, e.actor_id) for e in self.world.pump_history],
            [
                ("fault", None), ("isolate", "ari"),
                ("repair", "ari"), ("commission", "ari"),
            ],
        )
        self.assertFalse(any(
            agent.pending_requests for agent in self.supervisor.agents.values()
        ))

        ari = self.supervisor.agents["ari"].memories
        iona = self.supervisor.agents["iona"].memories
        lin = self.supervisor.agents["lin"].memories
        self.assertEqual(ari[0]["kind"], "radio_alert")
        self.assertEqual(ari[0]["data"]["sender_id"], "lin")
        self.assertEqual(iona[0]["kind"], "release_request")
        self.assertEqual(lin[0]["observation_id"], alarm)
        self.assertEqual(lin[0]["kind"], "coolant_alarm")
        self.assertIn("incident_resolved", [e["kind"] for e in lin])
        self.assertNotIn("pump_readout", [e["kind"] for e in lin])
        self.assertNotIn("pump_transition", [e["kind"] for e in lin])
        self.assertNotIn("coolant_alarm", [e["kind"] for e in iona])
        self.assertIn("pump_readout", [e["kind"] for e in iona])

        # All private memories were addressed by the world to that person.
        events = {e.event_id: e for e in self.world.events}
        for person, agent in self.supervisor.agents.items():
            for remembered in agent.memories:
                event = events[remembered["observation_id"]]
                self.assertEqual(event.recipient_id, person)
                self.assertEqual(event.text, remembered["text"])

    def test_no_idle_polling_or_inference(self):
        self.assertEqual(self.supervisor.advance_to(179), 0)
        self.assertEqual(self.world.pending_observations, 0)
        self.assertEqual(self.supervisor.wake_counts, {
            "ari": 0, "iona": 0, "lin": 0,
        })
        self.assertEqual(self.supervisor.world_submissions, 0)
        self.assertEqual(self.supervisor.planning_calls, 0)
        self.assertEqual(self.supervisor.inference_calls, 0)
        self.assertEqual(self.world.pump_history, ())
        self.assertEqual(self.world.pump_state, "normal")

    def test_world_prevents_unauthorized_or_falsely_verified_operations(self):
        self.world.advance_to(180)
        self.world.trigger_fault()
        illegal = [
            ActionRequest("bridge-repair", "lin", "repair_pump", "pump"),
            ActionRequest("chief-commission", "iona", "commission_pump", "pump"),
            ActionRequest(
                "false-resolution", "ari", "report_resolved", "pump",
                {"alarm_id": "not-a-real-alarm"},
            ),
            ActionRequest("premature-repair", "ari", "repair_pump", "pump"),
            ActionRequest(
                "false-approval", "iona", "approve_release", "pump",
                {"request_id": "not-requested"},
            ),
        ]
        for attempted in illegal:
            with self.subTest(verb=attempted.verb):
                result = self.world.submit(attempted)
                self.assertEqual(result.status, "failed")
                self.assertEqual(self.world.pump_state, "low_pressure")
        self.assertEqual(len(self.world.pump_history), 1)
        self.assertFalse(self.world.incident_closed)

    def test_chief_must_inspect_before_approving_commission(self):
        self.world.advance_to(180)
        self.world.trigger_fault()
        self.world.submit(ActionRequest("read", "ari", "inspect_pump", "pump"))
        self.world.submit(ActionRequest("iso", "ari", "isolate_pump", "pump"))
        self.world.submit(ActionRequest("fix", "ari", "repair_pump", "pump"))
        self.assertEqual(self.world.pump_state, "repaired")
        self.assertEqual(
            self.world.submit(ActionRequest(
                "commission-early", "ari", "commission_pump", "pump"
            )).status, "failed",
        )
        request = ActionRequest(
            "release-req", "ari", "request_release", "pump",
        )
        self.assertEqual(self.world.submit(request).status, "succeeded")
        self.assertEqual(
            self.world.submit(ActionRequest(
                "approve-no-inspection", "iona", "approve_release", "pump",
                {"request_id": "release-req"},
            )).status, "failed",
        )
        self.assertEqual(
            self.world.submit(ActionRequest(
                "iona-reads", "iona", "inspect_pump", "pump"
            )).status, "succeeded",
        )
        self.assertEqual(
            self.world.submit(ActionRequest(
                "approve", "iona", "approve_release", "pump",
                {"request_id": "release-req"},
            )).status, "succeeded",
        )
        self.assertEqual(
            self.world.submit(ActionRequest(
                "commission-after", "ari", "commission_pump", "pump"
            )).status, "succeeded",
        )
        self.assertEqual(self.world.pump_state, "normal")

    def test_urgent_interruption_discards_stale_choice_before_physical_execution(self):
        self.world.advance_to(180)
        self.world.trigger_fault()
        # Deliver one event at a time so the test can interrupt deliberation
        # just after Ari proposes isolation but BEFORE the world sees it.
        person, alarm = self.world.next_observation()
        self.assertEqual(person, "lin")
        radio = self.supervisor.agents["lin"].observe(alarm)
        self.supervisor._submit(radio)

        person, alert = self.world.next_observation()
        self.assertEqual(person, "ari")
        inspection = self.supervisor.agents["ari"].observe(alert)
        self.supervisor._submit(inspection)

        person, readout = self.world.next_observation()
        self.assertEqual(person, "ari")
        isolate = self.supervisor.agents["ari"].observe(readout)
        self.assertEqual(isolate.verb, "isolate_pump")
        self.assertEqual(len(self.world.pump_history), 1)

        self.world.urgent_safety_recheck()
        person, urgency = self.world.next_observation()
        self.assertEqual(person, "ari")
        self.assertEqual(urgency.kind, "urgent_recheck")
        self.supervisor.agents["ari"].observe(urgency)
        with self.assertRaises(StaleAgentRevision):
            self.supervisor._submit(isolate)
        self.assertEqual(len(self.world.pump_history), 1)

        # Discard ONLY the unexecuted proposal. Re-observe live machinery.
        engineer = self.supervisor.agents["ari"]
        engineer.discard_stale(isolate)
        reinspection = engineer.continue_after_reconciliation()
        self.assertEqual(reinspection.verb, "inspect_pump")
        self.supervisor._submit(reinspection)
        self.supervisor.pump()
        self.assertEqual(self.world.pump_state, "normal")
        self.assertTrue(self.world.incident_closed)
        self.assertGreaterEqual(self.supervisor.replans, 1)
        self.assertEqual(self.supervisor.inference_calls, 0)

    def test_unknown_pump_action_survives_handler_restart_without_repeat(self):
        self.world.advance_to(180)
        self.world.drop_next_ack("isolate_pump")
        self.world.trigger_fault()
        self.supervisor.pump()
        self.assertEqual(self.world.pump_state, "isolated")
        self.assertFalse(self.world.incident_closed)
        self.assertEqual(
            len([e for e in self.world.pump_history if e.operation == "isolate"]), 1
        )
        outstanding = self.supervisor.agents["ari"].pending_requests
        self.assertEqual(len(outstanding), 1)
        self.assertEqual(outstanding[0].verb, "isolate_pump")

        checkpoint = json.loads(json.dumps(self.supervisor.snapshot()))
        restarted = CoolantSupervisor.from_snapshot(self.world, checkpoint)
        self.assertEqual(restarted.agents["ari"].pending_requests, outstanding)
        self.assertEqual(restarted.reconcile_pending(), 1)
        self.assertEqual(self.world.pump_state, "normal")
        self.assertTrue(self.world.incident_closed)
        self.assertEqual(
            [e.operation for e in self.world.pump_history],
            ["fault", "isolate", "repair", "commission"],
        )
        self.assertEqual(restarted.inference_calls, 0)
        self.assertFalse(any(
            a.pending_requests for a in restarted.agents.values()
        ))

    def test_request_deduplication_and_unauthorized_receipt(self):
        self.world.advance_to(180)
        self.world.trigger_fault()
        req = ActionRequest("stable-inspection", "ari", "inspect_pump", "pump")
        first = self.world.submit(req)
        self.assertEqual(first.status, "succeeded")
        self.assertEqual(self.world.submit(req), first)
        self.assertEqual(self.world.pending_observations, 2)
        with self.assertRaises(ValueError):
            self.world.submit(ActionRequest(
                "stable-inspection", "ari", "isolate_pump", "pump"
            ))
        with self.assertRaises(PermissionError):
            self.world.reconcile(req.request_id, character_id="lin")

    def test_foreign_character_cannot_receive_private_engineering_readout(self):
        obs = WorldObservation(
            "foreign-readout", "ari", 0, "P-01: isolated",
            kind="pump_readout",
            data={"state": "isolated", "chief_released": "no"},
        )
        with self.assertRaises(PermissionError):
            self.supervisor.agents["lin"].observe(obs)
        self.assertEqual(self.supervisor.agents["lin"].memories, ())

    def test_complete_operator_trace_matches_expected_repair(self):
        transcript = run_demo()
        self.assertEqual(transcript["status"], "passed")
        self.assertEqual(transcript["scope"], "deterministic_mock_world_only")
        self.assertEqual(transcript["pump_state"], "normal")
        self.assertTrue(transcript["incident_closed"])
        self.assertEqual(transcript["inference_calls"], 0)
        self.assertEqual(transcript["world_action_requests"], 10)


if __name__ == "__main__":
    unittest.main()
