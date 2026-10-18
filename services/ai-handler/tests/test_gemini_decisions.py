"""No-network tests for bounded Gemini decisions and Concordia's choice API."""

from __future__ import annotations

import json
from io import BytesIO
import unittest
from urllib.error import HTTPError, URLError

from ox_ai.inference.decisions import (
    ChoiceDecision,
    ChoiceRequest,
    DecisionUnavailable,
    InvalidDecision,
)
from ox_ai.inference.gemini_choices import GeminiChoiceModel, GeminiChoiceProvider


def response(choice):
    return {
        "candidates": [{"content": {"parts": [
            {"text": json.dumps({"choice": choice})}
        ]}}]
    }


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, maximum):
        return self.content[:maximum]


class FakeHTTP:
    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def __call__(self, req, *, timeout):
        self.requests.append((req, timeout))
        if isinstance(self.answer, BaseException):
            raise self.answer
        return FakeResponse(json.dumps(self.answer).encode("utf-8"))


class DecisionTests(unittest.TestCase):

    def question(self):
        return ChoiceRequest(
            state="Low coolant pressure. Actions: (a) inspect (b) wait.",
            options={"a": "Inspect the pressure gauge", "b": "Wait"},
        )

    def test_schema_enforces_offered_choice_and_key_stays_out_of_body(self):
        fake = FakeHTTP(response("a"))
        provider = GeminiChoiceProvider(
            "test-secret", model_name="gemini-3.1-flash-lite",
            opener=fake,
        )
        result = provider.choose(self.question())
        self.assertEqual(result, ChoiceDecision(
            choice="a", provider="gemini", model="gemini-3.1-flash-lite"
        ))
        req, timeout = fake.requests[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(timeout, 20.0)
        self.assertEqual(req.get_header("X-goog-api-key"), "test-secret")
        self.assertNotIn(b"test-secret", req.data)
        payload = json.loads(req.data)
        self.assertEqual(
            payload["generationConfig"]["responseFormat"]["text"]["schema"]
            ["properties"]["choice"]["enum"], ["a", "b"]
        )
        self.assertEqual(
            payload["generationConfig"]["responseFormat"]["text"]["mimeType"],
            "APPLICATION_JSON",
        )

    def test_unoffered_choice_is_rejected(self):
        provider = GeminiChoiceProvider(
            "dummy", opener=FakeHTTP(response("teleport"))
        )
        with self.assertRaises(InvalidDecision):
            provider.choose(self.question())

    def test_malformed_or_missing_response_is_rejected(self):
        for payload in ({}, {"candidates": []}, {"candidates": [
            {"content": {"parts": [{"text": "not json"}]}}
        ]}):
            with self.subTest(payload=payload):
                provider = GeminiChoiceProvider(
                    "dummy", opener=FakeHTTP(payload)
                )
                with self.assertRaises(InvalidDecision):
                    provider.choose(self.question())

    def test_http_failure_does_not_reveal_secret(self):
        fake = FakeHTTP(HTTPError("https://example.test", 429, "busy", {}, None))
        provider = GeminiChoiceProvider("private-test-key", opener=fake)
        with self.assertRaises(DecisionUnavailable) as caught:
            provider.choose(self.question())
        self.assertIn("429", str(caught.exception))
        self.assertNotIn("private-test-key", str(caught.exception))

    def test_http_400_includes_only_safe_google_error_metadata(self):
        # The provider may echo the secret or original prompt in error text.
        # Only recognised API status and field names belong in CI logs.
        body = json.dumps({"error": {
            "code": 400,
            "status": "INVALID_ARGUMENT",
            "message": (
                "Invalid value at generation_config.response_format."
                "text.mime_type for private-test-key and secret user text"
            ),
        }}).encode("utf-8")
        fake = FakeHTTP(HTTPError(
            "https://example.test", 400, "bad request", {},
            BytesIO(body),
        ))
        provider = GeminiChoiceProvider("private-test-key", opener=fake)
        with self.assertRaises(DecisionUnavailable) as caught:
            provider.choose(self.question())
        result = str(caught.exception)
        self.assertIn("HTTP 400", result)
        self.assertIn("INVALID_ARGUMENT", result)
        self.assertIn(
            "field=generation_config.response_format.text.mime_type",
            result,
        )
        self.assertNotIn("private-test-key", result)
        self.assertNotIn("secret user text", result)
        self.assertNotIn("Invalid value", result)

    def test_non_json_http_error_is_never_echoed(self):
        fake = FakeHTTP(HTTPError(
            "https://example.test", 403, "forbidden", {},
            BytesIO(b"private-test-key"),
        ))
        provider = GeminiChoiceProvider("private-test-key", opener=fake)
        with self.assertRaises(DecisionUnavailable) as caught:
            provider.choose(self.question())
        self.assertEqual(
            str(caught.exception), "Gemini decision API returned HTTP 403"
        )

    def test_network_failure_is_explicit(self):
        fake = FakeHTTP(URLError("network down"))
        provider = GeminiChoiceProvider("dummy", opener=fake)
        with self.assertRaises(DecisionUnavailable):
            provider.choose(self.question())

    def test_empty_credentials_and_invalid_requests_are_rejected(self):
        with self.assertRaises(ValueError):
            GeminiChoiceProvider("")
        with self.assertRaises(ValueError):
            ChoiceRequest("observation", {"a": "only one option"})
        with self.assertRaises(ValueError):
            ChoiceRequest("observation", {"a": "inspect", "b": ""})

    def test_concordia_bridge_returns_finite_choice_only(self):
        fake = FakeHTTP(response("b"))
        model = GeminiChoiceModel(GeminiChoiceProvider("dummy", opener=fake))
        result = model.sample_choice(
            "What next?\n(a) Look around\n(b) Inspect pump", ("a", "b")
        )
        self.assertEqual(result[:2], (1, "b"))
        self.assertEqual(result[2]["provider"], "gemini")
        with self.assertRaises(DecisionUnavailable):
            model.sample_text("Tell a story")


if __name__ == "__main__":
    unittest.main()
