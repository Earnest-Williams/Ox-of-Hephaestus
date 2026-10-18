"""Native Concordia cognition attached to one ordinary, scoped Evennia character.

This module never supplies game authority to a model. It accepts only world
observations legitimately received by its own character, presents a finite
action menu, and accounts for confirmed vs unknown outcomes separately.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
import math
from pathlib import Path
import uuid

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity
from ox_ai.ports.base import ActionOutcome, ActionRequest, WorldObservation


ROLES = {
    "lin": (
        "Lin Sato", "Bridge officer responsible for cooling alarms and radio",
        "Protect ship operations and relay verified alarms to engineering",
    ),
    "ari": (
        "Ari Sen", "Engineering watch; work on P-01 only with physical access",
        "Diagnose P-01, use trained GOAP procedures and obtain chief release",
    ),
    "iona": (
        "Iona Vek", "Chief engineer; independent safety inspector and relief watch",
        "Reject unsafe commissioning and receive an accountable watch handover",
    ),
}


def make_model(provider: str | None = None):
    """Explicit local test model or opt-in hosted Gemini; no silent API fallback."""
    kind = (provider or os.environ.get("OX_COGNITION_PROVIDER", "mock")).lower()
    if kind == "mock":
        from concordia.testing.mock_model import MockModel
        return MockModel()
    if kind == "gemini":
        from ox_ai.inference.gemini_choices import GeminiChoiceModel, GeminiChoiceProvider
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("A Gemini live trial requires GEMINI_API_KEY")
        return GeminiChoiceModel(
            GeminiChoiceProvider(key, model_name=os.environ.get(
                "OX_LLM_MODEL", "gemini-3.1-flash-lite"
            ))
        )
    raise ValueError("OX_COGNITION_PROVIDER must be 'mock' or 'gemini'")


class LiveCrewBrain:
    """A distinct persisted Concordia component graph per world character."""

    def __init__(
        self, role: str, character_dbref: str, model,
        *, journal_path: Path | None = None,
    ) -> None:
        if role not in ROLES:
            raise ValueError("Unknown crew assignment")
        name, duty, goal = ROLES[role]
        self.role = role
        self.agent = CrewAgent(
            CrewIdentity(
                agent_id=f"ox.live.{role}",
                character_id=character_dbref,
                name=name,
                duty=duty,
                goal=goal,
            ),
            model,
            journal_path=journal_path,
        )
        self._game_time: float = 0.0

    @property
    def character_id(self) -> str:
        return self.agent.identity.character_id

    @property
    def inference_calls(self) -> int:
        return self.agent.usage.total_calls

    def observe_event(self, event: Mapping[str, object]) -> bool:
        """Accept a addressed game OOB event, not a handler's aggregate journal."""
        if event.get("recipient_dbref") != self.character_id:
            raise PermissionError("World event intended for another crew member")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("Missing authoritative event ID")
        data = event.get("data", {})
        if not isinstance(data, Mapping):
            raise TypeError("Event details must be a mapping")
        game_time = float(event["game_time"])
        if not math.isfinite(game_time) or game_time < 0:
            raise ValueError("Invalid authoritative game timestamp")
        # Late recipient-specific events can have older timestamps. Preserve
        # each event's actual time, and remember the newest known game time.
        self._game_time = max(self._game_time, game_time)
        return self.agent.observe(WorldObservation(
            observation_id=event_id,
            character_id=self.character_id,
            game_time=game_time,
            text=f"{event.get('kind', 'event')}: {event.get('text', '')}; "
                 + ", ".join(f"{k}={v}" for k, v in sorted(data.items())),
            source_event_id=event_id,
            kind=str(event.get("kind", "event")),
        ))

    def observe_local(self, description: str, text: str) -> None:
        """Only feed readouts actually returned to this character by the game."""
        self.agent.observe(WorldObservation(
            observation_id="local-" + uuid.uuid4().hex,
            character_id=self.character_id,
            game_time=self._game_time,
            text=f"{description}: {text}",
            kind="local_readout",
        ))

    def choose(self, primary: CommandOption, *, alternative: str) -> ActionRequest:
        """Ask the *native Concordia entity* to decide, not a scripted phase table.

        The alternative always permits deferral. Deferral never sends a
        dangerous physical command. The test model selects the first option;
        a real model can decline it.
        """
        return self.agent.decide(
            [primary, CommandOption(alternative, "defer")],
            expected_revision=self.agent.revision,
        )

    def require(self, request: ActionRequest, command: str) -> None:
        """Fail closed if cognition deferred or offered an unexpected command."""
        if request.character_id != self.character_id:
            raise PermissionError("Model proposal belongs to another character")
        if request.verb != command:
            self.agent.record_outcome(
                ActionOutcome(request.request_id, "succeeded",
                              "Local choice to defer; no world command was sent")
            )
            raise RuntimeError(
                f"{self.role} chose not to execute {command}; world unchanged"
            )

    def confirm(self, request: ActionRequest, world_event: Mapping[str, object]) -> None:
        """Only a genuine recipient-scoped event may confirm a world command."""
        self.observe_event(world_event)
        self.agent.record_outcome(ActionOutcome(
            request_id=request.request_id,
            status="succeeded",
            description=f"World delivered {world_event['kind']}",
            source_event_id=str(world_event["event_id"]),
        ))

    def selected_procedure(self, request: ActionRequest) -> None:
        """An accepted internal procedure is NOT a successful game operation."""
        self.agent.record_outcome(ActionOutcome(
            request.request_id, "succeeded",
            "Selected a local GOAP procedure, not a claimed physical result"
        ))

    def record_unknown(self, request: ActionRequest) -> None:
        self.agent.record_outcome(ActionOutcome(
            request.request_id, "unknown", "No world confirmation received"
        ))

    def save_checkpoint(self, path: Path) -> None:
        self.agent.save_checkpoint(path)

    @classmethod
    def from_checkpoint(
        cls, role: str, character_dbref: str, model, path: Path,
    ) -> "LiveCrewBrain":
        """Restore native Concordia state without replaying unknown actions."""
        restored = cls(role, character_dbref, model)
        restored.agent = CrewAgent.from_checkpoint(path, model)
        if (restored.agent.identity.character_id != character_dbref
                or restored.agent.identity.agent_id != f"ox.live.{role}"):
            raise PermissionError("Checkpoint cannot control a different identity")
        restored._game_time = float(restored.agent.snapshot()["last_game_time"] or 0)
        return restored


def build_live_brains(
    ids: Mapping[str, str], *, provider: str | None = None,
    journal_dir: Path | None = None,
) -> dict[str, LiveCrewBrain]:
    """Construct independent models/entities; not one shared omniscient actor."""
    if set(ids) != set(ROLES) or len(set(ids.values())) != len(ROLES):
        raise ValueError("Exactly three distinct world identities are required")
    return {
        role: LiveCrewBrain(
            role, str(ids[role]), make_model(provider),
            journal_path=(journal_dir / f"{role}.jsonl") if journal_dir else None,
        )
        for role in ROLES
    }
