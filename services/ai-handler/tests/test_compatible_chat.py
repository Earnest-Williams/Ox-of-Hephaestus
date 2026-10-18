"""Portable local-language-model adapter tests without network requests."""

import unittest
from types import SimpleNamespace

from ox_ai.inference.compatible_chat import CompatibleChatModel


class FakeClient:
    """Record completion requests and provide one configured response."""

    def __init__(self, answer):
        self.answer = answer
        self.kwargs = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
        self.kwargs.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.answer)
                )
            ]
        )


class CompatibleChatTests(unittest.TestCase):
    """LLM actions are bounded by Concordia's offered lettered choices."""

    def test_one_choice_is_selected_with_portable_completion_parameters(self):
        fake = FakeClient("(b)")
        model = CompatibleChatModel(
            "test-model",
            api_key="not-used",
            api_base="http://127.0.0.1:11434/v1",
            client=fake,
        )
        idx, response, debug = model.sample_choice(
            "Question: What next?\n(a) Look around\n(b) Inspect pump",
            ["a", "b"],
        )
        self.assertEqual((idx, response), (1, "b"))
        self.assertEqual(debug["raw_response"], "(b)")
        self.assertEqual(len(fake.kwargs), 1)
        self.assertNotIn("reasoning_effort", fake.kwargs[0])
        self.assertNotIn("verbosity", fake.kwargs[0])
        self.assertEqual(fake.kwargs[0]["model"], "test-model")

    def test_invalid_model_choice_never_falls_back_to_an_action(self):
        fake = FakeClient("I teleported to Engineering.")
        model = CompatibleChatModel(
            "test-model", api_key="unused",
            api_base="http://127.0.0.1:11434/v1", client=fake
        )
        with self.assertRaisesRegex(ValueError, "invalid action choice"):
            model.sample_choice("What next?", ["a", "b"])

    def test_model_text_completion(self):
        fake = FakeClient("The gauge is below nominal.")
        model = CompatibleChatModel(
            "test-model", api_key="unused",
            api_base="http://127.0.0.1:11434/v1", client=fake
        )
        self.assertIn("gauge", model.sample_text("What was observed?"))


if __name__ == "__main__":
    unittest.main()
