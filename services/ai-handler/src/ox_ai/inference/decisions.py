"""Provider-neutral, bounded semantic decisions for Ox agents.

A decision is a proposal: it cannot mutate authoritative Evennia state.
No probability or calibrated confidence is fabricated for generative models.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol


class DecisionUnavailable(RuntimeError):
    """Inference is unavailable; no action must be submitted."""


class InvalidDecision(ValueError):
    """A model response could not be validated against the offered choices."""


@dataclass(frozen=True, slots=True)
class ChoiceRequest:
    """Select one existing option from character-visible context."""

    state: str
    options: Mapping[str, str]
    instructions: str = "Select the best permitted option for this character."

    def __post_init__(self) -> None:
        if not isinstance(self.state, str) or not self.state.strip():
            raise ValueError("Decision state must be nonempty text")
        if len(self.state) > 24000:
            raise ValueError("Decision state exceeds prototype limit")
        if not isinstance(self.instructions, str) or not self.instructions.strip():
            raise ValueError("Decision instructions must be nonempty text")
        choices = dict(self.options)
        if not 2 <= len(choices) <= 26:
            raise ValueError("Prototype decisions require 2 to 26 options")
        if any(
            not isinstance(key, str) or not key.strip()
            or not isinstance(label, str) or not label.strip()
            for key, label in choices.items()
        ):
            raise ValueError("Choice keys and descriptions must be nonempty strings")
        object.__setattr__(self, "options", MappingProxyType(choices))


@dataclass(frozen=True, slots=True)
class ChoiceDecision:
    """A validated option key; not evidence an action succeeded."""

    choice: str
    provider: str
    model: str


class ChoiceProvider(Protocol):
    """Swappable decision backend (rules, hosted API, future local Kev)."""

    def choose(self, question: ChoiceRequest) -> ChoiceDecision:
        """Return a bounded choice or raise without suggesting an action."""
        ...
