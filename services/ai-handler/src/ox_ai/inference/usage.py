"""Lightweight inference-call metering around a Concordia model.

The delegate implements Concordia's LanguageModel interface; this wrapper does
not initiate inference independently or make model calls on idle clock ticks.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class MeteredModel:
    """Forward Concordia model calls while recording invocation counts."""

    def __init__(self, delegate: Any) -> None:
        """Wrap a model implementing sample_text and sample_choice."""
        self._delegate = delegate
        self.text_calls = 0
        self.choice_calls = 0

    @property
    def total_calls(self) -> int:
        """Return model requests issued through this wrapper."""
        return self.text_calls + self.choice_calls

    def sample_text(self, prompt: str, **kwargs: Any) -> str:
        """Forward a text-sampling request without modifying its prompt."""
        self.text_calls += 1
        return self._delegate.sample_text(prompt, **kwargs)

    def sample_choice(
        self,
        prompt: str,
        responses: Sequence[str],
        *,
        seed: int | None = None,
    ) -> tuple[int, str, Any]:
        """Forward a constrained-choice inference request."""
        self.choice_calls += 1
        return self._delegate.sample_choice(prompt, responses, seed=seed)
