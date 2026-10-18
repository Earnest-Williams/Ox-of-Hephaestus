"""Run one local Concordia engineer without connecting a game or remote LLM.

Install the handler with its optional [concordia] extra, then execute:
    python services/ai-handler/examples/one_engineer.py
"""

from pathlib import Path
import tempfile

from concordia.testing.mock_model import MockModel

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity
from ox_ai.ports.base import ActionOutcome, WorldObservation


def main() -> None:
    """Demonstrate observation, a bounded proposal and native state restore."""
    identity = CrewIdentity(
        agent_id="ox.eng.01",
        character_id="engineer",
        name="Ari",
        duty="Maintain engineering watch and investigate cooling alarms.",
        goal="Keep the ship and its people safe.",
    )
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / "engineer.json"
        crew = CrewAgent(identity, MockModel())
        crew.observe(
            WorldObservation(
                "obs-001",
                "engineer",
                3600.0,
                "Cooling header pressure is falling.",
                "world-100",
            )
        )
        proposed = crew.decide(
            [
                CommandOption("Inspect pressure gauge", "inspect", "gauge"),
                CommandOption("Wait on watch", "wait"),
            ]
        )
        print("Agent proposed:", proposed)
        print("World status: NOT EXECUTED")
        crew.record_outcome(
            ActionOutcome(proposed.request_id, "unknown", "No world connection")
        )
        crew.save_checkpoint(checkpoint)
        restored = CrewAgent.from_checkpoint(checkpoint, MockModel())
        print("Restored memories:", restored.memories)
        print("Requires reconciliation:", restored.pending_requests)


if __name__ == "__main__":
    main()
