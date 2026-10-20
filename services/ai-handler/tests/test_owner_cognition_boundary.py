"""Guard the only supported mutation entrypoints into CrewAgent cognition."""
from __future__ import annotations

from importlib.util import find_spec
import json
from pathlib import Path
import tempfile
import unittest

from ox_ai.agents.crew import CrewAgent, CrewIdentity, CommandOption, StaleAgentRevision
from ox_ai.memory.seeds import SeededMemory
from ox_ai.memory.temporal import TemporalMemory


@unittest.skipUnless(find_spec("concordia") is not None, "Native Concordia required")
class OwnerMutationBoundaryTests(unittest.TestCase):
    def setUp(self):
        from concordia.testing.mock_model import MockModel
        self.model = MockModel()
        self.crew = CrewAgent(CrewIdentity("crew", "#8", "Crew", "Watch", "Investigate"),
                              self.model, initial_memories=(SeededMemory(
                                  "old.1", "Ari made a claim about a repair",
                                  "ari", occurred_turn=-6,
                                  claim_key="ari_repair", claim_subject="ari",
                                  claim_stance=1,
                              ),))

    def test_raw_mutators_not_exposed_and_read_results_detached(self):
        memory = self.crew.temporal_memories.get("old.1")
        memory.text = "Forgery"
        self.crew.temporal_memories.entries()[0].salience = 0
        self.crew.temporal_memories.retrieve("ari", 0)[0].confidence = 0
        belief = self.crew.interpretations.get("ari", "ari_repair")
        belief.confidence = 1
        belief.sources.clear()
        self.assertNotEqual(self.crew.temporal_memories.get("old.1").text, "Forgery")
        self.assertEqual(self.crew.temporal_memories.get("old.1").salience, 70)
        self.assertGreater(self.crew.interpretations.get("ari", "ari_repair").confidence, 1)
        with self.assertRaises(PermissionError):
            self.crew.temporal_memories.retrieve("ari", 0, rehearse=True)
        with self.assertRaises(AttributeError):
            self.crew.temporal_memories.add(memory)
        with self.assertRaises(AttributeError):
            self.crew.interpretations.admit(memory)
        with self.assertRaises(AttributeError):
            self.crew.temporal_memories = object()
        with self.assertRaises(AttributeError):
            self.crew.interpretations = object()
        self.assertEqual(self.crew.cognition_revision, 0)

    def test_rehearsal_is_revisioned_and_persists_across_checkpoint(self):
        self.assertEqual(self.crew.rehearse_memories("nobody", 10), ())
        self.assertEqual(self.crew.cognition_revision, 0)
        result = self.crew.rehearse_memories("ari", 10)
        self.assertEqual(result[0].last_recalled_turn, 10)
        self.assertEqual(self.crew.cognition_revision, 1)
        self.assertEqual(self.crew.temporal_memories.get("old.1").recall_count, 1)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "owner.json"
            self.crew.save_checkpoint(path)
            restored = CrewAgent.from_checkpoint(path, self.model)
            self.assertEqual(restored.cognition_revision, 1)
            self.assertEqual(restored.temporal_memories.get("old.1").recall_count, 1)

    def test_rehearsal_during_detached_inference_rejects_stale_adoption(self):
        offered = (CommandOption("Speak with Ari", "speak", "ari"),)
        fork = self.crew.fork_for_inference()
        draft = fork.decide(offered)
        self.crew.rehearse_memories("ari", 3)
        with self.assertRaises(StaleAgentRevision):
            self.crew.adopt_inference(fork, draft, offered,
                expected_revision=0, expected_cognition_revision=0)
        self.assertEqual(self.crew.pending_requests, ())
        self.assertEqual(self.crew.temporal_memories.get("old.1").recall_count, 1)

    def test_direct_reconsideration_is_revisioned_even_for_weak_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "legacy.json"
            checkpoint = self.crew.snapshot()
            # Legitimate partial legacy checkpoint: episode exists, index empty.
            checkpoint["interpretations"] = {
                "version": 1, "priors": [], "states": [],
            }
            path.write_text(json.dumps(checkpoint), encoding="utf-8")
            restored = CrewAgent.from_checkpoint(path, self.model)
            self.assertTrue(restored.reconsider_memory("old.1"))
            self.assertEqual(restored.cognition_revision, 1)
            self.assertFalse(restored.reconsider_memory("old.1"))
            self.assertEqual(restored.cognition_revision, 1)
            self.assertIsNotNone(restored.interpretations.get("ari", "ari_repair"))
            with self.assertRaises(ValueError):
                restored.reconsider_memory("absent")

    def test_episode_does_not_retain_mutable_caller_alias(self):
        episode = TemporalMemory("new.2", "ari", "He said he fixed it",
                                 "witnessed_speech", 20, 20, 100, 80,
                                 source_event_id="obs20")
        self.assertTrue(self.crew.remember_timed(episode))
        episode.text = "Caller later changed the object"
        self.assertEqual(self.crew.temporal_memories.get("new.2").text,
                         "He said he fixed it")
        self.assertFalse(self.crew.remember_timed(TemporalMemory(
            "new.2", "ari", "He said he fixed it",
            "witnessed_speech", 20, 20, 100, 80, source_event_id="obs20")))
        self.assertEqual(self.crew.cognition_revision, 1)


if __name__ == "__main__":
    unittest.main()
