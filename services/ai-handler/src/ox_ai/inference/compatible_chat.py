"""Minimal, strict choice adapter for OpenAI-compatible local chat endpoints.

The pinned Concordia OpenAI adapter sends some OpenAI-specific completion
parameters (e.g. reasoning_effort / verbosity). This optional alternative
uses only widely supported chat completions parameters for Ollama/vLLM-style
endpoints. A response outside the offered choices FAILS instead of guessing.
It does not call the network until `sample_text` or `sample_choice` is used.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class CompatibleChatModel:
    """Provide Concordia's LanguageModel surface over chat completions."""

    def __init__(
        self,
        model_name: str,
        *,
        api_key: str,
        api_base: str,
        client: Any | None = None,
    ) -> None:
        """Configure a model; supply a fake client to run offline tests."""
        if not model_name.strip() or not api_base.strip():
            raise ValueError("Model name and compatible API URL are required")
        if client is None:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=api_base,
                timeout=90,
            )
        self._client = client
        self._model_name = model_name

    def _complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        """Issue a standard, non-streaming chat completion."""
        response = self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You control one simulated crew member in a MUD. "
                        "You decide actions from your observations and goals. "
                        "Never claim an action occurred unless game text says so. "
                        "Follow the output format of each question exactly."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Inference endpoint returned empty text")
        return content.strip()

    def sample_choice(
        self,
        prompt: str,
        responses: Sequence[str],
        *,
        seed: int | None = None,
    ) -> tuple[int, str, dict[str, Any]]:
        """Select a lettered Concordia option from a single model call."""
        del seed  # portable chat endpoints do not consistently support seeds
        if not responses:
            raise ValueError("A model choice requires at least one option")
        allowed = tuple(responses)
        answer = self._complete(
            prompt + (
                "\nSelect the best permitted action. "
                "Reply with EXACTLY one letter from: "
                + ", ".join(allowed)
                + ". No explanation."
            ),
            max_tokens=24,
            temperature=0.0,
        )
        normalized = answer.lower().removeprefix("answer:").strip(" \"'()[]\n\t.")
        if normalized not in allowed:
            raise ValueError(
                "Model returned an invalid action choice; no MUD command "
                f"will be executed: {answer[:120]!r}"
            )
        return allowed.index(normalized), normalized, {"raw_response": answer}

    def sample_text(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        terminators=(),
        temperature: float = 0.0,
        top_p: float = 1.0,
        top_k: int = 0,
        timeout: float = 90,
        seed: int | None = None,
    ) -> str:
        """Support Concordia text prompts if a later agent component uses them."""
        del terminators, top_p, top_k, timeout, seed
        return self._complete(
            prompt,
            max_tokens=min(max(int(max_tokens), 1), 2048),
            temperature=temperature,
        )
