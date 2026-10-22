"""Forty genuinely separate native Concordia checkpoints.

This is the cognitive restore gate, NOT a forty-session Evennia acceptance.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

try:
    from concordia.testing.mock_model import MockModel
except ImportError:
    MockModel = None


@unittest.skipIf(MockModel is None, "Pinned native Concordia is required")
class FortyNativeRecoveryTests(unittest.TestCase):
    def test_forty_native_graphs_recover_isolated_memory_and_replays(self):
        from ox_ai.agents.crew import CrewAgent, CrewIdentity
        from ox_ai.ports.base import WorldObservation

        with tempfile.TemporaryDirectory(prefix="ox-forty-brains-") as dirname:
            root = Path(dirname)
            agents = {}
            for i in range(40):
                identity = CrewIdentity(
                    agent_id=f"ox.person.fleet-{i:02d}",
                    character_id=f"#{1000+i}",
                    name=f"Fleet Member {i:02d}",
                    duty="Attend assigned compartment and ship systems",
                    goal="Act only upon authenticated local evidence",
                )
                agent = CrewAgent(identity, MockModel())
                private_text = f"PRIVATE-FLEET-MEMORY-{i:02d}"
                observation = WorldObservation(
                    observation_id=f"oxevt-fleet-{i:02d}",
                    character_id=identity.character_id,
                    game_time=1000.0 + i,
                    text=private_text,
                    source_event_id=f"oxevt-fleet-{i:02d}",
                    kind="radio",
                )
                self.assertTrue(agent.observe(observation))
                self.assertFalse(agent.observe(observation))
                agent.save_checkpoint(root / f"crew-{i:02d}.json")
                agents[i] = (identity, observation, agent)

            self.assertEqual(len({id(x[2].entity) for x in agents.values()}), 40)
            del agents
            restored = {}
            for i in range(40):
                agent = CrewAgent.from_checkpoint(
                    root / f"crew-{i:02d}.json", MockModel()
                )
                self.assertEqual(agent.identity.character_id, f"#{1000+i}")
                self.assertEqual(agent.identity.agent_id, f"ox.person.fleet-{i:02d}")
                self.assertEqual(agent.revision, 1)
                self.assertTrue(any(
                    f"PRIVATE-FLEET-MEMORY-{i:02d}" in item
                    for item in agent.memories
                ))
                self.assertFalse(agent.observe(WorldObservation(
                    observation_id=f"oxevt-fleet-{i:02d}",
                    character_id=f"#{1000+i}",
                    game_time=1000.0 + i,
                    text="Duplicate must not be ingested",
                    source_event_id=f"oxevt-fleet-{i:02d}",
                    kind="radio",
                )))
                with self.assertRaises(PermissionError):
                    agent.observe(WorldObservation(
                        observation_id=f"foreign-{i}",
                        character_id=f"#{1000+((i+1)%40)}",
                        game_time=1100.0,
                        text="Foreign observation",
                        kind="radio",
                    ))
                restored[i] = agent
            self.assertEqual(len({id(a.entity) for a in restored.values()}), 40)
            for i, agent in restored.items():
                own = f"PRIVATE-FLEET-MEMORY-{i:02d}"
                self.assertTrue(any(own in m for m in agent.memories))
                self.assertFalse(any(
                    f"PRIVATE-FLEET-MEMORY-{j:02d}" in m
                    for j in range(40) if j != i
                    for m in agent.memories
                ))
