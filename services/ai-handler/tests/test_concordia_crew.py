"""Offline integration tests against the pinned native Concordia component APIs."""

import json
from pathlib import Path
import tempfile
import unittest

from ox_ai.ports.base import ActionOutcome, WorldObservation

try:
    from concordia.testing.mock_model import MockModel
except ImportError:
    MockModel = None


@unittest.skipIf(MockModel is None, "Install ox-ai-handler[concordia] for P1")
class ConcordiaCrewTests(unittest.TestCase):
    """Exercise a real Concordia entity with a deterministic model stub."""

    def setUp(self):
        """Create one engineering watchkeeper without an external LLM."""
        from ox_ai.agents.crew import CrewAgent, CrewIdentity

        self.identity = CrewIdentity(
            agent_id="ox.eng.01",
            character_id="engineer",
            name="Ari",
            duty="Watch the cooling system and communicate anomalies.",
            goal="Keep the ship and crew safe.",
        )
        self.crew = CrewAgent(self.identity, MockModel())

    def _observe(self):
        """Deliver a character-scoped pressure report."""
        return WorldObservation(
            observation_id="obs-001",
            character_id="engineer",
            game_time=3600.0,
            text="Cooling header pressure is falling.",
            source_event_id="world-100",
        )

    def _choices(self):
        """Offer two commands, neither of which changes the world yet."""
        from ox_ai.agents.crew import CommandOption

        return [
            CommandOption("Inspect pressure gauge", "inspect", "gauge"),
            CommandOption("Remain on watch", "wait"),
        ]

    def test_entity_observes_and_proposes_a_structured_attempt(self):
        """Concordia's choice becomes a validated WorldPort request."""
        self.assertTrue(self.crew.observe(self._observe()))
        request = self.crew.decide(self._choices(), expected_revision=1)
        self.assertEqual(self.crew.entity.name, "Ari")
        self.assertEqual(request.verb, "inspect")
        self.assertEqual(request.target, "gauge")
        self.assertEqual(request.character_id, "engineer")
        self.assertEqual(request.agent_revision, 1)
        self.assertEqual(self.crew.usage.total_calls, 1)
        self.assertIn(request, self.crew.pending_requests)
        self.assertTrue(
            any("Cooling header pressure" in value for value in self.crew.memories)
        )

    def test_scope_duplicate_and_stale_decision(self):
        """Unaddressed and replayed observations must not create knowledge."""
        from ox_ai.agents.crew import StaleAgentRevision

        wrong = WorldObservation("obs-002", "bridge", 3600, "Private bridge event")
        with self.assertRaises(PermissionError):
            self.crew.observe(wrong)
        self.assertEqual(self.crew.revision, 0)
        self.assertTrue(self.crew.observe(self._observe()))
        self.assertFalse(self.crew.observe(self._observe()))
        self.assertEqual(self.crew.revision, 1)
        with self.assertRaises(StaleAgentRevision):
            self.crew.decide(self._choices(), expected_revision=0)
        self.assertEqual(self.crew.usage.total_calls, 0)

    def test_checkpoint_preserves_memory_and_unresolved_requests(self):
        """After restart, restore memory and pending action without retry."""
        from ox_ai.agents.crew import CrewAgent

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = root / "crew.jsonl"
            crew = CrewAgent(self.identity, MockModel(), journal_path=journal)
            crew.observe(self._observe())
            request = crew.decide(self._choices())
            crew.record_outcome(ActionOutcome(request.request_id, "unknown", "Lost ACK"))
            target = root / "crew-checkpoint.json"
            crew.save_checkpoint(target)

            restored = CrewAgent.from_checkpoint(
                target, MockModel(), journal_path=journal
            )
            self.assertEqual(restored.revision, 1)
            self.assertEqual(restored.usage.total_calls, 0)
            self.assertEqual(len(restored.pending_requests), 1)
            self.assertEqual(restored.pending_requests[0].request_id, request.request_id)
            self.assertFalse(restored.observe(self._observe()))
            self.assertTrue(
                any("Cooling header pressure" in value for value in restored.memories)
            )
            events = [
                json.loads(line) for line in journal.read_text().splitlines()
            ]
            self.assertEqual(
                [event["event_type"] for event in events],
                ["observation", "action_proposed", "world_outcome", "restored"],
            )
            self.assertEqual(events[1]["request_id"], request.request_id)
            self.assertEqual(events[1]["model_requests"], 1)

            restored.record_outcome(
                ActionOutcome(request.request_id, "succeeded", "Inspected gauge")
            )
            self.assertFalse(restored.pending_requests)
            self.assertEqual(restored.usage.total_calls, 0)

    def test_empty_and_duplicate_command_choices_are_rejected(self):
        """Only a unique finite option set may reach the inference client."""
        from ox_ai.agents.crew import CommandOption

        with self.assertRaises(ValueError):
            self.crew.decide([])
        with self.assertRaises(ValueError):
            self.crew.decide(
                [CommandOption("same", "look"), CommandOption("same", "wait")]
            )
        self.assertEqual(self.crew.usage.total_calls, 0)


if __name__ == "__main__":
    unittest.main()
