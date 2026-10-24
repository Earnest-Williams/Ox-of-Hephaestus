"""G16g standalone voice contract; fixture cannot certify generated quality."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

try:
    import ox_ai
except ImportError:
    ox_ai = None


@unittest.skipUnless(
    ox_ai is not None and importlib.util.find_spec("concordia") is not None,
    "Optional native Concordia components absent from minimal service install",
)
class VoiceHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scenarios"))
        import g16g_speech_evaluation as voice
        cls.voice = voice

    def test_all_six_authored_personae_and_four_speech_intents(self):
        protocol = self.voice.verified_protocol()
        self.assertEqual(len(protocol["roles"]), 6)
        self.assertEqual(len(protocol["scenes"]), 4)
        self.assertEqual(protocol["generation"]["expected_sample_count_per_provider"], 48)
        for role in protocol["roles"]:
            original = self.voice.load_g9_trial().g9_blueprint(role).to_record()
            for scene in protocol["scenes"]:
                numeric, numeric_user, name = self.voice.prompt_for(
                    role, scene, "numeric_original",
                )
                prose, prose_user, other = self.voice.prompt_for(
                    role, scene, "prose_original",
                )
                self.assertEqual(name, other)
                self.assertEqual(numeric_user, prose_user)
                self.assertNotEqual(numeric, prose)
                self.assertIn("ALREADY been chosen", numeric)
                self.assertIn("ALREADY been chosen", prose)
                self.assertIn(scene["speech_intent"], prose_user)
                self.assertIn(scene["known_context"], prose_user)
            self.assertEqual(
                self.voice.load_g9_trial().g9_blueprint(role).to_record(), original
            )

    def test_48_fixture_responses_are_untrusted_text_not_actions(self):
        result = self.voice.evaluate(self.voice.FakeSpeechBackend())
        self.assertEqual(result["samples"], 48)
        self.assertFalse(result["real_text_generation_measured"])
        self.assertEqual(result["evennia_commands_sent"], 0)
        self.assertEqual(result["action_requests_generated"], 0)
        self.assertEqual(len(result["rows"]), 48)
        self.assertEqual(len(result["blind_review_sheet"]), 48)
        self.assertEqual(len({r["blind_id"] for r in result["rows"]}), 48)
        self.assertEqual(len(result["original_blueprint_sha256_by_role"]), 6)
        self.assertFalse(result["model_choice_adopted"])
        for row in result["blind_review_sheet"]:
            self.assertNotIn("profile_arm", row)
            self.assertNotIn("model_id", row)
            self.assertNotIn("role", row)

    def test_refuse_invalid_generation_or_unauthorised_model(self):
        for invalid in (
            {"text": " ", "model_id": "model"},
            {"text": "ok\x00", "model_id": "model"},
            {"text": "x" * 1201, "model_id": "model"},
            {"text": "ok", "model_id": ""},
            {"text": "ok", "model_id": "model", "prompt_tokens": -1},
        ):
            with self.subTest(invalid=str(invalid)[:40]), self.assertRaises(ValueError):
                self.voice.checked_generated(invalid)
        with tempfile.TemporaryDirectory() as root:
            gguf = Path(root) / "fake.gguf"
            gguf.write_bytes(b"not a genuine voice model")
            with self.assertRaises(PermissionError):
                self.voice.LocalQwenSpeech(
                    gguf, self.voice.verified_protocol()["providers"]["local_qwen"]["gguf_sha256"]
                )
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PermissionError):
                self.voice.HostedGeminiSpeech("gemini-2.5-flash")

    def test_blinded_review_remains_unscored_until_human_review(self):
        result = self.voice.evaluate(self.voice.FakeSpeechBackend())
        self.assertFalse(result["human_blind_review_complete"])
        self.assertFalse(result["model_choice_adopted"])
        self.assertIn("not a measured dollar price", result["limitations"])


if __name__ == "__main__":
    unittest.main()
