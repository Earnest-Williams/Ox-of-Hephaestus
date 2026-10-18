"""Zero-LLM GOAP against the actual Evennia pump and permission machinery."""

from evennia.utils.test_resources import EvenniaTestCase

from ox_ai.agents.goap_crew import GoapCrewAgent
from world.ai_repair import conduct_repair_trial


class GoapPumpIntegrationTests(EvenniaTestCase):
    def test_goap_engineer_restores_pump_with_no_inference(self):
        from world.bootstrap import find_fixture

        result = conduct_repair_trial(
            agent_factory=GoapCrewAgent, max_steps=16
        )
        self.assertTrue(result.success, result.reason)
        self.assertEqual(result.pump_state, "normal")
        self.assertEqual(result.inference_calls, 0)
        self.assertEqual([step.command for step in result.steps], [
            "inspect console", "aft", "engineering", "isolate pump",
            "repair pump", "commission pump", "inspect pump", "finish",
        ])
        self.assertEqual(
            [e["operation"] for e in result.event_history],
            ["isolate", "repair", "commission"],
        )
        self.assertEqual(result.planning_calls, 2)
        self.assertGreater(result.expanded_states, 0)
        self.assertEqual(result.replans, 0)
        actor = find_fixture("crew-watch")
        self.assertTrue(all(
            e["actor_dbref"] == actor.dbref for e in result.event_history
        ))
        self.assertEqual(actor.location.key, "Engineering")
        self.assertIn("LOW PRESSURE", result.steps[0].response)
        self.assertIn("NORMAL", result.steps[-2].response)

    def test_unexpected_second_fault_causes_replanning_after_real_inspection(self):
        """Operator fault occurs after commissioning but before verification.

        The GOAP engineer only sees the changed condition on later inspection,
        then replans the repair. No privileged pump state is passed into it.
        """
        triggered = []

        def operator_injects_fault(line, ship):
            if line == "commission pump" and not triggered:
                success, _ = ship["pump"].inject_fault()
                self.assertTrue(success)
                triggered.append(True)

        result = conduct_repair_trial(
            agent_factory=GoapCrewAgent,
            max_steps=16,
            after_action=operator_injects_fault,
        )
        self.assertTrue(result.success, result.reason)
        self.assertEqual(result.inference_calls, 0)
        self.assertEqual(len(triggered), 1)
        self.assertGreaterEqual(result.replans, 1)
        self.assertGreaterEqual(result.planning_calls, 3)
        self.assertEqual(result.pump_state, "normal")
        operations = [e["operation"] for e in result.event_history]
        self.assertEqual(operations, [
            "isolate", "repair", "commission", "fault",
            "isolate", "repair", "commission",
        ])
        self.assertEqual(
            [s.command for s in result.steps].count("inspect pump"), 2
        )
        self.assertIn("LOW PRESSURE", [
            s.response for s in result.steps if s.command == "inspect pump"
        ][0])
