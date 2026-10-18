"""Single Concordia-powered Ox crew member: Prototype 1, gate P1.

The member receives only character-scoped world observations. Its Concordia
entity selects *proposed* commands from caller-supplied choices; no selected
text can directly mutate the authoritative world. The handler can checkpoint
native Concordia state and reconcile outstanding requests after restoration.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any
import uuid

from ox_ai.inference.usage import MeteredModel
from ox_ai.ports.base import ActionOutcome, ActionRequest, WorldObservation


@dataclass(frozen=True, slots=True)
class CrewIdentity:
    """Stable Ox agent-to-game-character identity and current brief."""

    agent_id: str
    character_id: str
    name: str
    duty: str
    goal: str


@dataclass(frozen=True, slots=True)
class CommandOption:
    """A single proposed world command; world rules still validate it."""

    label: str
    verb: str
    target: str | None = None
    arguments: Mapping[str, str] = field(default_factory=dict)


class StaleAgentRevision(ValueError):
    """A decision was based on an obsolete agent observation revision."""


class CrewAgent:
    """Own one native Concordia entity and its Ox-side action accounting.

    This synchronous P1 component deliberately has no game transport or
    background scheduler. A later supervisor will decide when it is invoked.
    """

    CHECKPOINT_VERSION = 1

    def __init__(
        self,
        identity: CrewIdentity,
        model: Any,
        *,
        journal_path: Path | None = None,
    ) -> None:
        """Construct the Concordia component graph around a supplied model.

        Args:
            identity: One durable agent and its corresponding game character.
            model: Any Concordia LanguageModel-compatible inference client.
            journal_path: Optional append-only JSONL diagnostic journal.
        """
        from concordia.agents.entity_agent_with_logging import EntityAgentWithLogging
        from concordia.components.agent import concat_act_component
        from concordia.components.agent import constant
        from concordia.components.agent import memory
        from concordia.components.agent import observation

        self.identity = identity
        self.usage = MeteredModel(model)
        self._journal_path = Path(journal_path) if journal_path else None
        self._revision = 0
        self._seen_observations: set[str] = set()
        self._pending: dict[str, ActionRequest] = {}
        self._last_game_time: float | None = None

        components = {
            "Identity": constant.Constant(
                state=f"You are {identity.name}, a member of the spaceship crew.",
                pre_act_label="Identity",
            ),
            "Duty": constant.Constant(
                state=identity.duty,
                pre_act_label="Assigned duty",
            ),
            "Goal": constant.Constant(
                state=identity.goal,
                pre_act_label="Goal",
            ),
            "ObservationToMemory": observation.ObservationToMemory(),
            observation.DEFAULT_OBSERVATION_COMPONENT_KEY: (
                observation.LastNObservations(history_length=32)
            ),
            memory.DEFAULT_MEMORY_COMPONENT_KEY: memory.ListMemory([]),
        }
        self._entity = EntityAgentWithLogging(
            agent_name=identity.name,
            act_component=concat_act_component.ConcatActComponent(
                model=self.usage,
                component_order=tuple(components),
                randomize_choices=False,
                prefix_entity_name=False,
            ),
            context_components=components,
        )

    @property
    def entity(self) -> Any:
        """Expose the actual Concordia entity for controlled inspection."""
        return self._entity

    @property
    def revision(self) -> int:
        """Return the observation revision that decisions must reference."""
        return self._revision

    @property
    def pending_requests(self) -> tuple[ActionRequest, ...]:
        """Return attempts needing world acknowledgment or reconciliation."""
        return tuple(self._pending.values())

    @property
    def memories(self) -> tuple[str, ...]:
        """Read the agent's own Concordia ListMemory, not canonical facts."""
        from concordia.components.agent import memory

        bank = self._entity.get_component(memory.DEFAULT_MEMORY_COMPONENT_KEY)
        return tuple(bank.get_all_memories_as_text())

    def _record(self, kind: str, **details: Any) -> None:
        """Append a trace with separate world-time and wall-time provenance."""
        if self._journal_path is None:
            return
        event = {
            "event_type": kind,
            "agent_id": self.identity.agent_id,
            "character_id": self.identity.character_id,
            "agent_revision": self._revision,
            "game_time": self._last_game_time,
            "wall_time_utc": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self._journal_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def observe(self, observation: WorldObservation) -> bool:
        """Incorporate an authorised observation once; reject wrong recipients.

        Returns:
            True if the Concordia entity accepted a new observation, else
            False when the observation ID had already been consumed.
        """
        if observation.character_id != self.identity.character_id:
            raise PermissionError("Observation belongs to another character")
        if observation.observation_id in self._seen_observations:
            return False

        annotated = (
            f"Game time {observation.game_time}; "
            f"observation {observation.observation_id}: {observation.text}"
        )
        self._entity.observe(annotated)
        self._seen_observations.add(observation.observation_id)
        self._last_game_time = observation.game_time
        self._revision += 1
        self._record(
            "observation",
            observation_id=observation.observation_id,
            source_event_id=observation.source_event_id,
            text=observation.text,
        )
        return True

    def decide(
        self,
        choices: Sequence[CommandOption],
        *,
        expected_revision: int | None = None,
    ) -> ActionRequest:
        """Ask Concordia to choose a validated command attempt, not an outcome.

        Args:
            choices: The caller's currently offered commands; not a grant of
                authority to execute them.
            expected_revision: Optional optimistic observation revision.

        Raises:
            StaleAgentRevision: If knowledge changed before or during choice.
            ValueError: If choices are empty, ambiguous, or model-invalid.
        """
        from concordia.typing import entity as entity_lib

        if expected_revision is not None and expected_revision != self._revision:
            raise StaleAgentRevision("Observation revision changed")
        if not choices:
            raise ValueError("A choice requires at least one command option")
        by_label = {option.label: option for option in choices}
        if len(by_label) != len(choices) or any(
            not option.label or not option.verb for option in choices
        ):
            raise ValueError("Commands need unique nonempty labels and verbs")

        revision_at_start = self._revision
        calls_before = self.usage.total_calls
        choice = self._entity.act(
            entity_lib.choice_action_spec(
                call_to_action=(
                    "What should {name} attempt next on watch? "
                    "Choose one of the supplied commands. "
                    "Your choice is a request, not a completed action."
                ),
                options=tuple(by_label),
                tag="ox_command_attempt",
            )
        )
        if self._revision != revision_at_start:
            self._record("stale_decision_discarded", chosen_label=choice)
            raise StaleAgentRevision("Observation changed during inference")
        if choice not in by_label:
            self._record("invalid_decision", chosen_label=choice)
            raise ValueError("Concordia returned a command that was not offered")

        selected = by_label[choice]
        request = ActionRequest(
            request_id=uuid.uuid4().hex,
            character_id=self.identity.character_id,
            verb=selected.verb,
            target=selected.target,
            arguments=dict(selected.arguments),
            agent_revision=revision_at_start,
        )
        self._pending[request.request_id] = request
        self._record(
            "action_proposed",
            request_id=request.request_id,
            chosen_label=choice,
            verb=request.verb,
            target=request.target,
            model_requests=self.usage.total_calls - calls_before,
        )
        return request

    def record_outcome(self, outcome: ActionOutcome) -> None:
        """Record what the world reported without declaring unknown a failure."""
        if outcome.request_id not in self._pending:
            raise KeyError(f"No pending request {outcome.request_id}")
        self._record(
            "world_outcome",
            request_id=outcome.request_id,
            status=outcome.status,
            source_event_id=outcome.source_event_id,
            description=outcome.description,
        )
        if outcome.status in ("succeeded", "failed"):
            del self._pending[outcome.request_id]

    def snapshot(self) -> dict[str, Any]:
        """Return native Concordia state and Ox-owned pending action metadata."""
        return {
            "checkpoint_version": self.CHECKPOINT_VERSION,
            "identity": asdict(self.identity),
            "revision": self._revision,
            "seen_observations": sorted(self._seen_observations),
            "last_game_time": self._last_game_time,
            "pending_requests": [asdict(item) for item in self.pending_requests],
            "concordia_state": self._entity.get_state(),
        }

    def save_checkpoint(self, path: Path) -> None:
        """Atomically persist the native component snapshot as JSON."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(self.snapshot(), stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    @classmethod
    def from_checkpoint(
        cls,
        path: Path,
        model: Any,
        *,
        journal_path: Path | None = None,
    ) -> CrewAgent:
        """Restore native Concordia memory; never replay pending commands."""
        checkpoint = json.loads(Path(path).read_text(encoding="utf-8"))
        if checkpoint.get("checkpoint_version") != cls.CHECKPOINT_VERSION:
            raise ValueError("Unsupported crew checkpoint version")
        crew = cls(
            CrewIdentity(**checkpoint["identity"]),
            model,
            journal_path=journal_path,
        )
        crew._entity.set_state(checkpoint["concordia_state"])
        crew._revision = checkpoint["revision"]
        crew._seen_observations = set(checkpoint["seen_observations"])
        crew._last_game_time = checkpoint["last_game_time"]
        crew._pending = {
            request["request_id"]: ActionRequest(**request)
            for request in checkpoint["pending_requests"]
        }
        crew._record(
            "restored",
            pending_request_ids=sorted(crew._pending),
        )
        return crew
