"""Provisional Python contract for mock and Evennia world adapters.

These types describe the intent of the boundary, not an implemented adapter or
wire protocol. The authoritative world resolves an action; a model never does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class WorldObservation:
    """Information the world legitimately delivered to one character."""

    observation_id: str
    character_id: str
    game_time: float
    text: str
    source_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class ActionRequest:
    """A validated command attempt, not an assertion of physical success."""

    request_id: str
    character_id: str
    verb: str
    target: str | None = None
    arguments: Mapping[str, str] = field(default_factory=dict)
    agent_revision: int = 0


@dataclass(frozen=True, slots=True)
class ActionOutcome:
    """Best-known result; unknown requires observing/reconciling world state."""

    request_id: str
    status: Literal["pending", "succeeded", "failed", "unknown"]
    description: str
    source_event_id: str | None = None


class WorldPort(Protocol):
    """Async game boundary implemented by mock and Evennia adapters."""

    async def connect(self, character_id: str) -> None:
        """Open the character's normal game-side identity or session."""
        ...

    async def receive(self, character_id: str) -> WorldObservation:
        """Wait for the next authorised observation for this character."""
        ...

    async def submit(self, request: ActionRequest) -> ActionOutcome:
        """Attempt a command and return the best-known world-side outcome."""
        ...

    async def current_game_time(self) -> float:
        """Read the backend's authoritative simulated game clock."""
        ...

    async def disconnect(self, character_id: str) -> None:
        """Close a character's game-side connection."""
        ...
