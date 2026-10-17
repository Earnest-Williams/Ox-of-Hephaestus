"""Stdlib smoke tests for the provisional handler/world contract."""

import unittest
from dataclasses import FrozenInstanceError

from ox_ai.ports.base import ActionOutcome, ActionRequest, WorldObservation


class WorldContractTests(unittest.TestCase):
    """Verify the small importable contract scaffold."""

    def test_default_action_arguments_are_distinct(self):
        first = ActionRequest("r1", "engineer", "look")
        second = ActionRequest("r2", "engineer", "look")
        self.assertEqual(first.arguments, {})
        self.assertIsNot(first.arguments, second.arguments)

    def test_an_attempt_is_not_an_outcome(self):
        request = ActionRequest("r3", "engineer", "inspect", "pump")
        outcome = ActionOutcome(request.request_id, "unknown", "No confirmation")
        self.assertEqual(request.request_id, outcome.request_id)
        self.assertEqual(outcome.status, "unknown")

    def test_observation_is_character_scoped_and_frozen(self):
        observation = WorldObservation("e42", "engineer", 600.0, "Pressure falling")
        self.assertEqual(observation.character_id, "engineer")
        with self.assertRaises(FrozenInstanceError):
            observation.text = "Different text"


if __name__ == "__main__":
    unittest.main()
