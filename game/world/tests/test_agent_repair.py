"""Real Evennia command dispatch, driven by a Concordia entity.

The model here is scripted *on purpose*. CI establishes that command choices
cross the physical world boundary; it does NOT establish model reasoning.
The opt-in live_trial in world.ai_repair is the intelligence experiment.
"""

from __future__ import annotations

from evennia.utils.test_resources import EvenniaTestCase

from world.ai_repair import conduct_repair_trial


class ScriptedChoices:
    """Return a fixed choice sequence via Concordia's LanguageModel interface."""

    def __init__(self, choices):
        self._choices = list(choices)
        self.prompts = []

    def sample_choice(self, prompt, responses, *, seed=None):
        self.prompts.append(str(prompt))
        if not self._choices:
            raise AssertionError("Model was called more times than expected")
        choice = self._choices.pop(0)
        if choice not in responses:
            raise AssertionError(
                f"Script offered {choice!r}, but available options are {responses}"
            )
        return responses.index(choice), choice, {}

    def sample_text(self, *args, **kwargs):
        raise AssertionError("Unexpected free-text generation")


class RepairAgentIntegrationTests(EvenniaTestCase):
    """An accountless NPC executes real game commands through Concordia."""

    def test_agent_physically_reaches_engineering_and_fixes_pump(self):
        """No world writes from the agent: only ordinary command invocations."""
        from world.bootstrap import find_fixture

        model = ScriptedChoices([
            "Inspect Cooling Status Console",
            "Go aft",
            "Go engineering",
            "Inspect Cooling Pump P-01",
            "Isolate Cooling Pump P-01",
            "Inspect Cooling Pump P-01",
            "Repair Cooling Pump P-01",
            "Inspect Cooling Pump P-01",
            "Commission Cooling Pump P-01",
            "Inspect Cooling Pump P-01",
            "Finish trial (claim completed)",
        ])
        result = conduct_repair_trial(model, max_steps=16)
        self.assertTrue(result.success, result.reason)
        self.assertEqual(result.pump_state, "normal")
        self.assertEqual(result.inference_calls, 11)
        self.assertEqual(
            [s.command for s in result.steps],
            ["inspect console", "aft", "engineering", "inspect pump",
             "isolate pump", "inspect pump", "repair pump", "inspect pump",
             "commission pump", "inspect pump", "finish"],
        )
        self.assertIn("LOW PRESSURE", result.steps[0].response)
        self.assertIn("LOW PRESSURE", result.steps[3].response)
        self.assertIn("ISOLATED", result.steps[5].response)
        self.assertIn("REPAIRED", result.steps[7].response)
        self.assertIn("NORMAL", result.steps[9].response)
        self.assertEqual(
            [e["operation"] for e in result.event_history],
            ["isolate", "repair", "commission"],
        )
        actor = find_fixture("crew-watch")
        self.assertTrue(
            all(e["actor_dbref"] == actor.dbref for e in result.event_history)
        )
        self.assertEqual(actor.location.key, "Engineering")
        self.assertTrue(any("cooling" in p.lower() for p in model.prompts))

    def test_agent_claiming_success_does_not_fix_world(self):
        """Saying the work is complete has no machinery effect."""
        model = ScriptedChoices(["Finish trial (claim completed)"])
        result = conduct_repair_trial(model, max_steps=4)
        self.assertFalse(result.success)
        self.assertEqual(result.pump_state, "low_pressure")
        self.assertEqual(result.event_history, ())
        self.assertEqual(result.steps[0].command, "finish")

    def test_preconditions_still_apply_when_model_orders_wrong_repair(self):
        """A premature repair is rejected by the real Evennia game rules."""
        model = ScriptedChoices([
            "Go aft",
            "Go engineering",
            "Repair Cooling Pump P-01",
            "Finish trial (claim completed)",
        ])
        result = conduct_repair_trial(model, max_steps=6)
        self.assertFalse(result.success)
        self.assertEqual(result.pump_state, "low_pressure")
        self.assertIn("Cannot repair", result.steps[2].response)
        self.assertFalse(result.event_history)
