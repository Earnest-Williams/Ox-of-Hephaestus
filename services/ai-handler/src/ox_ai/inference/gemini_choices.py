"""Gemini GenerateContent adapter for schema-bounded Ox decisions.

Only live, explicitly configured trials send requests to Google. The API key
never appears in prompts, logs, returned metadata or error messages.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from urllib import error as urlerror
from urllib import request as urlrequest

from ox_ai.inference.decisions import (
    ChoiceDecision,
    ChoiceRequest,
    DecisionUnavailable,
    InvalidDecision,
)


def _safe_http_error_details(exc: urlerror.HTTPError) -> str:
    """Return only diagnostic status and field path; never raw provider prose.

    Provider messages may echo request contents or secrets. Only machine
    readable status codes and recognised field identifiers reach logs.
    """
    try:
        payload = json.loads(exc.read(4096))
        details = payload.get("error", {})
        if not isinstance(details, dict):
            return ""
        found = []
        status = details.get("status")
        if isinstance(status, str) and re.fullmatch(r"[A-Z_]{3,64}", status):
            found.append(status)
        message = details.get("message")
        if isinstance(message, str):
            field = re.search(
                r"(?:generation_config|generationConfig|response_format|"
                r"responseFormat)(?:[.][A-Za-z0-9_]+)*",
                message,
            )
            if field is not None:
                found.append(f"field={field.group(0)}")
        return " (" + ", ".join(found) + ")" if found else ""
    except (AttributeError, OSError, TypeError, ValueError):
        return ""


class GeminiChoiceProvider:
    """Use Gemini's JSON-schema enum to constrain one selected option."""

    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = "gemini-3.1-flash-lite",
        timeout_seconds: float = 20.0,
        opener=None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("GEMINI_API_KEY must be provided for a live trial")
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", model_name):
            raise ValueError("Invalid Gemini model identifier")
        if not 0 < timeout_seconds <= 120:
            raise ValueError("Decision timeout must be between 0 and 120 seconds")
        self._api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self._opener = opener if opener is not None else urlrequest.urlopen

    def choose(self, question: ChoiceRequest) -> ChoiceDecision:
        """Fail closed on HTTP errors, unavailable output or invalid choices."""
        keys = list(question.options)
        schema = {
            "type": "object",
            "properties": {"choice": {"type": "string", "enum": keys}},
            "required": ["choice"],
            "additionalProperties": False,
        }
        prompt = (
            "Context and available actions for one spaceship crew member:\n"
            + question.state
            + "\n\nAllowed option identifiers and descriptions:\n"
            + json.dumps(dict(question.options), ensure_ascii=False)
            + "\nSelect precisely one option identifier."
        )
        body = {
            "systemInstruction": {"parts": [{"text": question.instructions}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseFormat": {
                    "text": {"mimeType": "APPLICATION_JSON", "schema": schema}
                },
                "maxOutputTokens": 256,
            },
        }
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + self.model_name
            + ":generateContent"
        )
        request = urlrequest.Request(
            endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as stream:
                raw = stream.read(65537)
        except urlerror.HTTPError as exc:
            raise DecisionUnavailable(
                f"Gemini decision API returned HTTP {exc.code}"
                + _safe_http_error_details(exc)
            ) from None
        except (urlerror.URLError, TimeoutError, OSError) as exc:
            raise DecisionUnavailable(
                f"Gemini decision API unavailable ({type(exc).__name__})"
            ) from None

        if len(raw) > 65536:
            raise InvalidDecision("Gemini returned an oversized response")
        try:
            response = json.loads(raw)
            candidates = response["candidates"]
            parts = candidates[0]["content"]["parts"]
            answer_text = "".join(
                part.get("text", "") for part in parts
                if isinstance(part, dict)
            )
            answer = json.loads(answer_text)
            if not isinstance(answer, dict) or set(answer) != {"choice"}:
                raise InvalidDecision("Gemini did not return a single choice")
            selected = answer["choice"]
        except (KeyError, IndexError, TypeError, UnicodeError, ValueError) as exc:
            if isinstance(exc, InvalidDecision):
                raise
            raise InvalidDecision("Gemini response is not valid choice JSON") from exc
        if not isinstance(selected, str) or selected not in question.options:
            raise InvalidDecision("Gemini selected an unoffered choice")
        return ChoiceDecision(
            choice=selected, provider="gemini", model=self.model_name
        )


class GeminiChoiceModel:
    """Concordia sample_choice bridge; never uses free-form generation.

    The existing Concordia component supplies the lettered choice prompt;
    only permitted option letters can be returned to the Evennia command path.
    """

    def __init__(self, provider: GeminiChoiceProvider) -> None:
        self.provider = provider

    def sample_choice(
        self,
        prompt: str,
        responses: Sequence[str],
        *,
        seed: int | None = None,
    ) -> tuple[int, str, dict]:
        del seed  # Gemini's hosted API does not offer a portable seeded choice.
        offered = tuple(responses)
        if len(set(offered)) != len(offered):
            raise ValueError("Duplicate Concordia choice identifiers")
        question = ChoiceRequest(
            state=prompt,
            options={
                name: f"Option ({name}) from the lettered menu in the context"
                for name in offered
            },
            instructions=(
                "Choose the most appropriate *attempted* next action for the "
                "observed spaceship crew member. Use the lettered action menu. "
                "Your choice does not mean an action succeeded."
            ),
        )
        decision = self.provider.choose(question)
        if decision.choice not in offered:
            raise InvalidDecision("Decision provider chose an unoffered option")
        return (
            offered.index(decision.choice),
            decision.choice,
            {"provider": decision.provider, "model": decision.model},
        )

    def sample_text(self, *args, **kwargs) -> str:
        raise DecisionUnavailable(
            "Gemini choice-only adapter does not support free-text generation"
        )
