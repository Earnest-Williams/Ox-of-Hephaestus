"""Memory time advances from the simulation clock, not new memory arrivals."""
from __future__ import annotations

from importlib.util import find_spec
import json
from pathlib import Path
import tempfile
import unittest

from ox_ai.memory.clock import MemoryClockBridge


class ClockConversionTests(unittest.TestCase):
    def test_explicit_seconds_turn_conversion_and_no_implicit_round_up(self):
        frame = MemoryClockBridge(1000.0, memory_epoch_turn=7,
                                  seconds_per_turn=60.0)
        self.assertEqual(frame.turn_at(1000.0), 7)
        self.assertEqual(frame.turn_at(1119.9), 8)
        self.assertEqual(frame.turn_at(1120.0), 9)
        self.assertEqual(frame.game_time_at(9), 1120.0)
        self.assertEqual(MemoryClockBridge.from_record(frame.to_record()), frame)
        self.assertEqual(frame.turn_at(999.0), 6)  # late older evidence

    def test_reject_ambiguous_or_invalid_clock_frames(self):
        for invalid in (float("nan"), float("inf"), -1, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                MemoryClockBridge(1000.0, seconds_per_turn=invalid)
        with self.assertRaises(ValueError):
            MemoryClockBridge(1000.0).turn_at(float("nan"))
        with self.assertRaises(ValueError):
            MemoryClockBridge.from_record({"seconds_per_turn": 60.0})


@unittest.skipUnless(find_spec("concordia") is not None,
                     "Native Concordia required")
class OwnedMemoryClockTests(unittest.TestCase):
    def setUp(self):
        from concordia.testing.mock_model import MockModel
        from ox_ai.agents.crew import CrewAgent, CrewIdentity
        from ox_ai.memory.seeds import SeededMemory
        self.agent = CrewAgent(CrewIdentity("crew", "#7", "Crew", "Watch", "Observe"),
                               MockModel(), initial_memories=(
                                   SeededMemory("past", "Ari assisted a colleague",
                                                "ari", occurred_turn=-120),
                               ))

    def test_age_progresses_without_any_new_episode_or_observation(self):
        old = self.agent.temporal_memories.get("past").importance(0)
        self.assertTrue(self.agent.advance_memory_turn(550))
        self.assertLess(self.agent.temporal_memories.get("past").importance(
            self.agent.memory_now_turn), old)
        self.assertEqual(self.agent.revision, 0)
        self.assertEqual(self.agent.cognition_revision, 1)
        self.assertFalse(self.agent.advance_memory_turn(550))
        self.assertEqual(self.agent.cognition_revision, 1)
        with self.assertRaises(ValueError):
            self.agent.advance_memory_turn(549)

    def test_game_clock_advancement_rejects_stale_inference_without_rewriting_memory(self):
        from ox_ai.agents.crew import CommandOption, StaleAgentRevision
        offered = (CommandOption("Ask Ari", "speak", "ari"),)
        fork = self.agent.fork_for_inference()
        request = fork.decide(offered)
        frame = MemoryClockBridge(10000.0, 0, 60.0)
        self.agent.bind_memory_clock(frame)
        self.assertTrue(self.agent.advance_game_time(10120.0))
        self.assertEqual(self.agent.memory_now_turn, 2)
        self.assertFalse(self.agent.advance_game_time(10060.0))
        self.assertEqual(self.agent.cognition_revision, 1)
        with self.assertRaises(StaleAgentRevision):
            self.agent.adopt_inference(
                fork, request, offered,
                expected_revision=0, expected_cognition_revision=0)
        self.assertEqual(self.agent.temporal_memories.get("past").occurred_turn,
                         -120)

    def test_roundtrip_and_legacy_clock_migration(self):
        self.agent.advance_memory_turn(30)
        self.agent.bind_memory_clock(MemoryClockBridge(5000, 30, 2))
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "clock.json"
            self.agent.save_checkpoint(path)
            from ox_ai.agents.crew import CrewAgent
            restored = CrewAgent.from_checkpoint(path, self.agent._model)
            self.assertEqual(restored.memory_now_turn, 30)
            self.assertEqual(restored.memory_clock, self.agent.memory_clock)
            self.assertTrue(restored.advance_game_time(5010))
            self.assertEqual(restored.memory_now_turn, 35)
            legacy = json.loads(path.read_text(encoding="utf-8"))
            legacy.pop("memory_clock")
            legacy.pop("memory_now_turn")
            path.write_text(json.dumps(legacy), encoding="utf-8")
            old = CrewAgent.from_checkpoint(path, self.agent._model)
            self.assertEqual(old.memory_now_turn, 0)
            self.assertIsNone(old.memory_clock)

    def test_live_brain_maps_only_authoritative_event_time_and_does_not_rewind(self):
        from ox_ai.agents.live_concordia import LiveCrewBrain
        from concordia.testing.mock_model import MockModel
        brain = LiveCrewBrain("lin", "#11", MockModel())
        event = {"recipient_dbref": "#11", "event_id": "ev-1",
                 "game_time": 1000.0, "kind": "handover_due", "data": {}}
        self.assertTrue(brain.observe_event(event))
        self.assertEqual(brain.agent.memory_now_turn, 0)
        self.assertTrue(brain.advance_game_time(1150.0))
        self.assertEqual(brain.agent.memory_now_turn, 150)
        self.assertEqual(brain.agent.cognition_revision, 1)
        self.assertFalse(brain.observe_event(event))
        self.assertFalse(brain.advance_game_time(1050.0))
        self.assertEqual(brain.agent.memory_now_turn, 150)
        with self.assertRaises(PermissionError):
            brain.observe_event({**event, "event_id": "other", "recipient_dbref": "#88"})


if __name__ == "__main__":
    unittest.main()
