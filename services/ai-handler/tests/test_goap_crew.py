"""Independent GOAP-agent contract tests: no Concordia and no model usage."""

import unittest

from ox_ai.agents.crew import CommandOption, CrewIdentity, StaleAgentRevision
from ox_ai.agents.goap_crew import GoapCrewAgent
from ox_ai.planning.goap import PlanUnavailable
from ox_ai.ports.base import ActionOutcome, WorldObservation


class GoapCrewTests(unittest.TestCase):
    def setUp(self):
        self.agent = GoapCrewAgent(CrewIdentity(
            agent_id="goap-ari", character_id="evennia:#15", name="Ari Sen",
            duty="Engineering watch", goal="Restore and verify pump P-01",
        ))
        self.seq = 0

    def observe(self, text):
        self.seq += 1
        return self.agent.observe(WorldObservation(
            observation_id=f"obs-{self.seq}",
            character_id="evennia:#15", game_time=float(self.seq),
            text=text,
        ))

    def test_information_gathering_then_repair_plan_without_inference(self):
        self.observe("|cBridge|n\nYou see: Cooling Status Console\n|wExits:|n aft")
        self.assertEqual(self.agent.beliefs, frozenset({"at_bridge"}))
        choices = [
            CommandOption("Look around", "look"),
            CommandOption("Go aft", "aft"),
            CommandOption("Inspect Cooling Status Console", "inspect", "console"),
            CommandOption("Finish", "finish"),
        ]
        decision = self.agent.decide(choices, expected_revision=1)
        self.assertEqual((decision.verb, decision.target), ("inspect", "console"))
        self.assertEqual(self.agent.usage.total_calls, 0)

        self.agent.record_outcome(ActionOutcome(
            decision.request_id, "succeeded", "Command delivered"
        ))
        # Command delivery is NOT evidence that the pump has been inspected.
        self.assertNotIn("status_known", self.agent.beliefs)
        with self.assertRaisesRegex(PlanUnavailable, "Unreconciled"):
            self.agent.decide(choices)
        self.observe(
            "Command 'inspect console' returned:\n"
            "BRIDGE COOLING TELEMETRY\nCooling Pump P-01: LOW PRESSURE\n"
            "Loop pressure: below safe operating limits."
        )
        self.assertIn("pump_low_pressure", self.agent.beliefs)
        self.assertEqual(
            self.agent.remaining_plan,
            (),  # sensing goal finished; operational goal computed next
        )
        decision = self.agent.decide(choices)
        self.assertEqual(decision.verb, "aft")
        self.assertEqual(self.agent.remaining_plan, (
            "move_aft", "move_engineering", "isolate_pump",
            "repair_pump", "commission_pump", "verify_normal",
        ))
        self.assertEqual(self.agent.planning_calls, 2)
        self.assertEqual(self.agent.usage.total_calls, 0)

    def test_rejected_repair_updates_beliefs_and_replans(self):
        self.observe("|cEngineering|n\nYou see: Cooling Pump P-01")
        self.observe(
            "Command 'inspect pump' returned:\nCooling Pump P-01: ISOLATED"
        )
        choices = [
            CommandOption("Inspect pump", "inspect", "pump"),
            CommandOption("Isolate pump", "isolate", "pump"),
            CommandOption("Repair pump", "repair", "pump"),
            CommandOption("Commission pump", "commission", "pump"),
            CommandOption("Finish", "finish"),
        ]
        first = self.agent.decide(choices)
        self.assertEqual(first.verb, "repair")
        self.agent.record_outcome(
            ActionOutcome(first.request_id, "succeeded", "Command delivered")
        )
        self.observe(
            "Command 'repair pump' returned:\n"
            "Cannot repair P-01 while it is low pressure."
        )
        self.assertIn("pump_low_pressure", self.agent.beliefs)
        self.assertNotIn("repair_done", self.agent.beliefs)
        self.assertEqual(self.agent.replans, 1)
        second = self.agent.decide(choices)
        self.assertEqual(second.verb, "isolate")
        self.assertEqual(self.agent.usage.total_calls, 0)

    def test_unknown_world_outcome_does_not_retry_physical_command(self):
        self.observe("|cEngineering|n\nCooling Pump P-01")
        self.observe("Cooling Pump P-01: LOW PRESSURE")
        choices = [
            CommandOption("Isolate pump", "isolate", "pump"),
            CommandOption("Finish", "finish"),
        ]
        request = self.agent.decide(choices)
        self.assertEqual(request.verb, "isolate")
        self.agent.record_outcome(ActionOutcome(
            request.request_id, "unknown", "Response lost"
        ))
        self.assertEqual(self.agent.pending_requests, (request,))
        with self.assertRaisesRegex(PlanUnavailable, "Unreconciled"):
            self.agent.decide(choices)

    def test_unoffered_action_is_rejected_before_world_submission(self):
        self.observe("|cEngineering|n\nCooling Pump P-01")
        self.observe("Cooling Pump P-01: LOW PRESSURE")
        with self.assertRaisesRegex(PlanUnavailable, "not currently offered"):
            self.agent.decide([
                CommandOption("Wait", "wait"),
                CommandOption("Finish", "finish"),
            ])
        self.assertEqual(self.agent.pending_requests, ())

    def test_character_scope_duplicate_and_stale_revision(self):
        with self.assertRaises(PermissionError):
            self.agent.observe(WorldObservation(
                "wrong", "somebody-else", 0, "|cEngineering|n"
            ))
        ob = WorldObservation("one", "evennia:#15", 1, "|cBridge|n")
        self.assertTrue(self.agent.observe(ob))
        self.assertFalse(self.agent.observe(ob))
        self.assertEqual(self.agent.revision, 1)
        with self.assertRaises(StaleAgentRevision):
            self.agent.decide([], expected_revision=0)

    def test_conclusion_requires_observed_readout_not_command_receipt(self):
        self.observe("|cEngineering|n")
        self.observe("Cooling Pump P-01: REPAIRED")
        offered = [
            CommandOption("Commission pump", "commission", "pump"),
            CommandOption("Inspect pump", "inspect", "pump"),
            CommandOption("Finish", "finish"),
        ]
        req = self.agent.decide(offered)
        self.assertEqual(req.verb, "commission")
        self.agent.record_outcome(ActionOutcome(
            req.request_id, "succeeded", "Command delivered"
        ))
        self.assertNotIn("pump_normal", self.agent.beliefs)
        self.observe(
            "Command 'commission pump' returned:\nP-01: repaired -> normal."
        )
        self.assertIn("pump_normal", self.agent.beliefs)
        self.assertNotIn("normal_verified", self.agent.beliefs)
        # This synthetic setup did not deliver an OWN repair event, so the
        # required repair_done fact is absent; no false claim is possible.
        with self.assertRaises(PlanUnavailable):
            self.agent.decide(offered)


if __name__ == "__main__":
    unittest.main()
