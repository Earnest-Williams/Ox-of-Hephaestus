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


class TemporalMemoryTests(unittest.TestCase):
    def memory(self, key, when, *, learned=0, salience=80, confidence=90,
               source="recollection", trust=12, interest=-4):
        from ox_ai.memory.temporal import TemporalMemory
        return TemporalMemory(
            key, "mara", "This is my subjective account", source,
            when, learned, confidence, salience,
            trust_effect=trust, interest_effect=interest,
        )

    def test_newer_episode_more_accessible_than_old_same_strength(self):
        from ox_ai.memory.temporal import TemporalMemoryBank
        bank = TemporalMemoryBank((
            self.memory("old", -600), self.memory("new", 88, learned=88)))
        self.assertEqual(bank.retrieve("mara", 100, limit=1)[0].memory_id, "new")
        self.assertGreater(bank.retrieve("mara", 100, limit=1)[0].importance(100),
                           bank.retrieve("mara", 100, limit=2)[1].importance(100))
        self.assertEqual(bank.retrieve("mara", 700, limit=1)[0].memory_id, "new")

    def test_salient_older_memory_can_survive_and_rehearsal_updates_recall_only(self):
        from ox_ai.memory.temporal import TemporalMemoryBank
        event = self.memory("formative", -900, salience=100, confidence=100)
        bank = TemporalMemoryBank((event,))
        before = event.importance(160)
        self.assertEqual(bank.retrieve("mara", 160, rehearse=True)[0].memory_id,
                         "formative")
        self.assertEqual(event.occurred_turn, -900)
        self.assertEqual(event.last_recalled_turn, 160)
        self.assertEqual(event.recall_count, 1)
        self.assertGreater(event.importance(160), before)

    def test_hearsay_weaker_than_personally_observed_same_claim(self):
        from ox_ai.memory.temporal import TemporalMemoryBank
        rumor = self.memory("rumor", 50, learned=50, source="testimony")
        seen = self.memory("seen", 50, learned=50, source="witnessed_speech")
        bank = TemporalMemoryBank((rumor, seen))
        self.assertEqual(bank.retrieve("mara", 55, limit=1)[0].memory_id, "seen")

    def test_opposing_recollections_remain_distinct_and_bounded(self):
        from ox_ai.memory.temporal import TemporalMemoryBank
        a = self.memory("told-yes", -12, trust=20)
        b = self.memory("told-no", -10, trust=-20)
        bank = TemporalMemoryBank((a, b))
        self.assertEqual(len(bank), 2)
        self.assertEqual(len(bank.appraisal("mara", 0)[2]), 2)
        self.assertFalse(bank.add(a))
        with self.assertRaises(ValueError):
            bank.add(self.memory("told-yes", -12, trust=-20))
        self.assertEqual(len(bank), 2)

    def test_no_future_memory_or_learned_before_occurrence(self):
        from ox_ai.memory.temporal import TemporalMemoryBank
        with self.assertRaises(ValueError):
            self.memory("impossible", 10, learned=2)
        bank = TemporalMemoryBank((self.memory("later", 10, learned=12),))
        self.assertEqual(bank.retrieve("mara", 9), ())
        self.assertEqual(bank.retrieve("mara", 10), ())
        self.assertEqual(len(bank.retrieve("mara", 12)), 1)

    def test_checkpoint_restores_time_and_recall_without_cross_agent_leakage(self):
        from ox_ai.memory.temporal import TemporalMemoryBank, TemporalMemory
        from ox_ai.agents.crew import CrewAgent, CrewIdentity
        from concordia.testing.mock_model import MockModel
        lin = CrewAgent(CrewIdentity("lin", "#1", "Lin", "Bridge", "Watch"),
                        MockModel(), initial_memories=(
                            SeededMemory("lin.history", "Mara was once kind.",
                                         "mara", occurred_turn=-75,
                                         trust_effect=11),))
        ari = CrewAgent(CrewIdentity("ari", "#2", "Ari", "Engineering", "Work"),
                        MockModel())
        self.assertEqual(len(ari.temporal_memories), 0)
        original = lin.temporal_memories.appraisal("mara", 40)
        lin.temporal_memories.retrieve("mara", 40, rehearse=True)
        episode = TemporalMemory(
            "world-r1", "mara", "Mara declined my proposal.", "world_receipt",
            42, 42, 100, 95, trust_effect=-28, interest_effect=-12,
            source_event_id="oxevt-v2-12")
        self.assertTrue(lin.remember_timed(episode))
        self.assertFalse(lin.remember_timed(episode))
        self.assertNotEqual(lin.temporal_memories.appraisal("mara", 42),
                            original)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lin.json"
            lin.save_checkpoint(path)
            restored = CrewAgent.from_checkpoint(path, MockModel())
            self.assertEqual(restored.temporal_memories.to_records(),
                             lin.temporal_memories.to_records())
            self.assertEqual(len(restored.temporal_memories), 2)
            self.assertEqual(len(ari.temporal_memories), 0)
            fork = restored.fork_for_inference()
            fork.temporal_memories.retrieve("mara", 55, rehearse=True)
            self.assertNotEqual(fork.temporal_memories.to_records(),
                                restored.temporal_memories.to_records())

    def test_no_world_authority_from_subjective_memory(self):
        from ox_ai.agents.crew import CrewAgent, CrewIdentity
        from concordia.testing.mock_model import MockModel
        agent = CrewAgent(CrewIdentity("x", "#6", "X", "Duty", "Watch"),
                          MockModel(), initial_memories=(
                              SeededMemory("fake-promise", "Ari promised me a ship.",
                                           "ari", trust_effect=40),))
        self.assertEqual(agent.pending_requests, ())
        self.assertEqual(agent.revision, 0)
        self.assertEqual(len(agent.temporal_memories), 1)


if __name__ == "__main__":
    unittest.main()
