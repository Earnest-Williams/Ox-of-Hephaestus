"""Native Concordia prompt projection and private cognition revision contracts."""
from __future__ import annotations

from importlib.util import find_spec
import json
from pathlib import Path
import tempfile
import unittest

from ox_ai.agents.crew import (
    CommandOption, CrewAgent, CrewIdentity, StaleAgentRevision,
)
from ox_ai.memory.seeds import SeededMemory
from ox_ai.memory.temporal import TemporalMemory


class CaptureChoiceModel:
    def __init__(self):
        self.prompts = []

    def sample_choice(self, prompt, responses, *, seed=None):
        self.prompts.append(prompt)
        return 0, responses[0], {}

    def sample_text(self, prompt, **kwargs):
        raise AssertionError("A menu-driven decision must use sample_choice")


@unittest.skipUnless(find_spec("concordia") is not None,
                     "Requires optional native Concordia integration")
class OxNativeMemoryProjectionTests(unittest.TestCase):
    def setUp(self):
        self.model = CaptureChoiceModel()
        self.crew = CrewAgent(
            CrewIdentity("ox.person.mara", "#31", "Mara", "Cargo watch",
                         "Resolve assigned work without forging evidence"),
            self.model,
            initial_memories=(
                SeededMemory(
                    "mara.saw.1", "MARA PRIVATE: Lin once made me a promise.",
                    "mara", confidence=85, salience=95, occurred_turn=-250,
                    claim_key="mara_pledge", claim_subject="mara",
                    claim_stance=1, source_group="firstaccount",
                ),
                SeededMemory(
                    "mara.heard.2", "MARA OTHER: Another witness disputed that.",
                    "mara", kind="testimony", confidence=75,
                    salience=90, occurred_turn=-20,
                    claim_key="mara_pledge", claim_subject="mara",
                    claim_stance=-1, source_group="secondaccount",
                ),
                SeededMemory(
                    "teo.private.3", "TEO PRIVATE: My private suspicion.",
                    "teo", confidence=60, salience=100, occurred_turn=-3,
                ),
            ),
        )
        self.offer = (
            CommandOption("Talk to the officer", "speak", "mara"),
            CommandOption("Stay on watch", "defer"),
        )

    def test_native_model_receives_relevant_episodic_and_interpreted_context(self):
        request = self.crew.decide(self.offer)
        self.assertEqual(request.verb, "speak")
        prompt = self.model.prompts[-1]
        self.assertIn("MARA PRIVATE:", prompt)
        self.assertIn("MARA OTHER:", prompt)
        self.assertIn("mara_pledge", prompt)
        self.assertIn("contradictory=true", prompt)
        self.assertIn("learned_turn=0", prompt)
        self.assertIn("not a confirmed claim", prompt)
        self.assertIn("not world truth", prompt)
        self.assertNotIn("TEO PRIVATE:", prompt)
        self.assertNotIn("TEO PRIVATE", prompt.upper())

    def test_prompt_is_read_only_and_satisfies_fixed_budget(self):
        context = self.crew.entity.get_component("OxMemoryContext")
        self.assertIs(context._owner, self.crew)
        initial = self.crew.temporal_memories.to_records()
        interpretations = self.crew.interpretations.to_records()
        cognition_rev = self.crew.cognition_revision
        self.crew.decide(self.offer)
        self.crew.decide(self.offer)
        self.assertEqual(initial, self.crew.temporal_memories.to_records())
        self.assertEqual(interpretations, self.crew.interpretations.to_records())
        self.assertEqual(cognition_rev, self.crew.cognition_revision)
        self.assertEqual(len(self.model.prompts), 2)
        self.assertEqual(self.model.prompts[0], self.model.prompts[1])
        from concordia.typing import entity as entity_lib
        spec = entity_lib.choice_action_spec(
            call_to_action="Choose", options=("Talk to Mara", "defer"))
        memory_prompt = context.pre_act(spec)
        self.assertLessEqual(len(memory_prompt), 2201)
        self.assertEqual(context.get_state(), {})
        with self.assertRaises(ValueError):
            context.set_state({"remembered": "wrongly cached"})

    def test_irrelevant_private_histories_are_not_forced_into_prompt(self):
        self.crew.decide((CommandOption("Inspect the scrubber", "inspect", "a-01"),
                          CommandOption("Wait", "defer")))
        prompt = self.model.prompts[-1]
        self.assertNotIn("MARA PRIVATE:", prompt)
        self.assertNotIn("TEO PRIVATE:", prompt)
        self.assertNotIn("Current interpretation", prompt)

    def test_fork_binds_memory_projection_to_its_own_private_memory(self):
        fork = self.crew.fork_for_inference()
        component = fork.entity.get_component("OxMemoryContext")
        self.assertIs(component._owner, fork)
        self.assertIsNot(component._owner, self.crew)
        self.assertEqual(self.crew.cognition_revision, 0)
        added = TemporalMemory(
            "mara.after.fork", "mara",
            "NEW PRIVATE MARA evidence that arrived after inference started",
            "witnessed_speech", 20, 20, 100, 95,
            source_event_id="real.receipt.20",
        )
        self.assertTrue(self.crew.remember_timed(added))
        self.assertEqual(self.crew.revision, 0)
        self.assertEqual(self.crew.cognition_revision, 1)
        fork.decide(self.offer)
        self.assertNotIn("NEW PRIVATE MARA", self.model.prompts[-1])
        self.crew.decide(self.offer)
        self.assertIn("NEW PRIVATE MARA", self.model.prompts[-1])
        with self.assertRaises(StaleAgentRevision):
            self.crew.adopt_inference(
                fork, fork.pending_requests[-1], self.offer,
                expected_revision=0, expected_cognition_revision=0,
            )
        self.assertIsNotNone(self.crew.temporal_memories.get("mara.after.fork"))

    def test_checkpoint_and_legacy_no_context_or_revision_restore(self):
        original = self.crew.snapshot()
        self.assertEqual(original["cognition_revision"], 0)
        self.assertEqual(original["concordia_state"]["context_components"]
                         ["OxMemoryContext"], {})
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "crew.json"
            self.crew.save_checkpoint(dest)
            restored = CrewAgent.from_checkpoint(dest, CaptureChoiceModel())
            self.assertEqual(restored.cognition_revision, 0)
            self.assertIs(restored.entity.get_component("OxMemoryContext")._owner,
                          restored)
            self.assertEqual(
                restored.temporal_memories.to_records(),
                self.crew.temporal_memories.to_records(),
            )
            # Native Concordia ignores absent newly-added component state;
            # test a checkpoint produced before this projection existed.
            older = json.loads(dest.read_text(encoding="utf-8"))
            older.pop("cognition_revision")
            older["concordia_state"]["context_components"].pop(
                "OxMemoryContext")
            dest.write_text(json.dumps(older), encoding="utf-8")
            legacy = CrewAgent.from_checkpoint(dest, CaptureChoiceModel())
            self.assertEqual(legacy.cognition_revision, 0)
            legacy.decide(self.offer)
            self.assertIn("MARA PRIVATE:", legacy._model.prompts[-1])

    def test_cognition_version_advances_only_for_new_private_episodes(self):
        event = TemporalMemory(
            "mara.real.31", "mara", "A new personally witnessed statement",
            "witnessed_speech", 31, 31, 100, 90,
            source_event_id="world-31",
        )
        self.assertTrue(self.crew.remember_timed(event))
        self.assertEqual(self.crew.cognition_revision, 1)
        self.assertFalse(self.crew.remember_timed(event))
        self.assertEqual(self.crew.cognition_revision, 1)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "with_revision.json"
            self.crew.save_checkpoint(path)
            recovered = CrewAgent.from_checkpoint(path, CaptureChoiceModel())
            self.assertEqual(recovered.cognition_revision, 1)
            self.assertIsNotNone(recovered.temporal_memories.get("mara.real.31"))


if __name__ == "__main__":
    unittest.main()
