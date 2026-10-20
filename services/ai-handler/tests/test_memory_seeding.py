"""G8 authored-memory seed contract and optional native Concordia regression."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ox_ai.memory.seeds import SeededMemory, validate_seed_memories


class MemorySeedValidationTests(unittest.TestCase):
    def test_provenance_and_disputed_memory_are_preserved_as_authored(self):
        a = SeededMemory("lin-mara-lounge", "Mara thinks we separated.", "Mara",
                         "interpretation", 52, 93)
        self.assertIn("NOT world-verified", a.render())
        self.assertIn("confidence=52", a.render())
        self.assertIn("interpretation", a.render())

    def test_invalid_records_and_duplicate_ids_fail_closed(self):
        a = SeededMemory("one", "A recollection", "Ari")
        with self.assertRaises(ValueError):
            validate_seed_memories((a, a))
        with self.assertRaises(TypeError):
            validate_seed_memories(("untyped",))
        with self.assertRaises(ValueError):
            validate_seed_memories([a] * 65)
        for kwargs in (
            {"memory_id": "with spaces"},
            {"text": ""},
            {"text": "line\nline"},
            {"kind": "world_fact"},
            {"confidence": True},
            {"salience": 101},
        ):
            data = {"memory_id": "sample", "text": "Something happened",
                    "about": "Ari"}
            data.update(kwargs)
            with self.subTest(data=data), self.assertRaises(ValueError):
                SeededMemory(**data)


try:
    from concordia.testing.mock_model import MockModel
except ImportError:
    MockModel = None


@unittest.skipIf(MockModel is None, "Concordia not installed")
class NativeMemorySeedingTests(unittest.TestCase):
    def test_private_seed_checkpoint_and_no_duplicate_restore(self):
        from ox_ai.agents.crew import CrewAgent, CrewIdentity
        def person(name, ref, memories):
            return CrewAgent(CrewIdentity(name, ref, name, "Watch", "Work"),
                             MockModel(), initial_memories=memories)
        seed = SeededMemory("ari-break", "I remember a painful separation.",
                            "Iona", "recollection", 90, 88)
        a = person("Ari", "#1", (seed,))
        b = person("Iona", "#2", ())
        self.assertEqual(len(a.memories), 1)
        self.assertEqual(len(b.memories), 0)
        self.assertIn("painful separation", a.memories[0])
        self.assertEqual(len(a.fork_for_inference().memories), 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ari.json"
            a.save_checkpoint(path)
            restored = CrewAgent.from_checkpoint(path, MockModel())
            self.assertEqual(restored.memories, a.memories)
            restored.save_checkpoint(path)
            again = CrewAgent.from_checkpoint(path, MockModel())
            self.assertEqual(len(again.memories), 1)

    def test_live_factory_scopes_seeds_to_one_authenticated_actor(self):
        from ox_ai.agents.live_concordia import build_live_brains
        seed = SeededMemory("lin1", "I doubt Iona's account.", "Iona")
        brains = build_live_brains({"lin": "#1", "ari": "#2", "iona": "#3"},
                                  provider="mock", memory_seeds={"lin": (seed,)})
        self.assertEqual(len(brains["lin"].agent.memories), 1)
        self.assertEqual(len(brains["ari"].agent.memories), 0)
        with self.assertRaises(ValueError):
            build_live_brains({"lin": "#1", "ari": "#2", "iona": "#3"},
                              provider="mock", memory_seeds={"mara": (seed,)})


if __name__ == "__main__":
    unittest.main()
