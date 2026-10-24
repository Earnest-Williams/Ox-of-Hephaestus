"""G16g blinded voice review must not become a synthetic model-quality claim."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import pathlib
import sys
import unittest

try:
    import ox_ai
except ImportError:
    ox_ai = None


@unittest.skipUnless(
    ox_ai is not None and importlib.util.find_spec("concordia") is not None,
    "Optional native Concordia needed for authenticated original G9 blueprints",
)
class BlindedVoiceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "scenarios"))
        import g16g_speech_evaluation as voice
        import g16g_blind_review as review
        cls.voice = voice
        cls.review = review

    def source_for_structural_testing_only(self, provider="qwen-local"):
        """Synthetic rows made deliberately recognizable as non-native TEST fixtures.

        No workflow is allowed to export this substituted record as a real
        experiment: it exists only in memory inside this unittest.
        """
        output = self.voice.evaluate(self.voice.FakeSpeechBackend())
        output["provider"] = provider
        output["fake_provider"] = False
        output["real_text_generation_measured"] = True
        output["total_completion_tokens_reported"] = 48 * 12
        output["total_prompt_tokens_reported"] = 48 * 100
        for row in output["rows"]:
            row["fixture_only"] = False
            row["model_id"] = (
                "qwen3.5-4b-local-q4km" if provider == "qwen-local"
                else "gemini-offline-test"
            )
        return output

    def test_never_review_genuine_fixture_output(self):
        raw = self.voice.evaluate(self.voice.FakeSpeechBackend())
        with self.assertRaises(PermissionError):
            self.review.prepare([raw], salt=b"a" * 16)
        wrong = deepcopy(raw)
        wrong["provider"] = "qwen-local"
        wrong["fake_provider"] = False
        wrong["real_text_generation_measured"] = True
        with self.assertRaises(PermissionError):
            self.review.prepare([wrong], salt=b"a" * 16)

    def test_randomized_blind_ids_preserve_neutral_speaker_group(self):
        source = self.source_for_structural_testing_only()
        sheet, key, template = self.review.prepare([source], salt=b"s" * 16)
        self.assertEqual(len(sheet["items"]), 48)
        self.assertEqual(len(key["items"]), 48)
        self.assertEqual(len(template["ratings"]), 48)
        self.assertEqual(len({r["blind_id"] for r in sheet["items"]}), 48)
        self.assertEqual(len({r["anonymous_speaker_group"] for r in sheet["items"]}), 6)
        self.assertTrue(sheet["providers_hidden"] and sheet["prompt_arms_hidden"])
        self.assertEqual(len(template["blinded_sheet_sha256"]), 64)
        expected = next(x for x in sheet["items"])
        self.assertEqual(len(expected["neutral_original_trait_reference_0_to_100"]), 6)
        for item in sheet["items"]:
            self.assertNotIn("original_role", item)
            self.assertNotIn("provider", item)
            self.assertNotIn("profile_arm", item)
            self.assertNotIn("salt_hex_keep_private", item)
        # Anonymous group, not a treatment indicator; eight rows/actor/provider
        from collections import Counter
        self.assertEqual(set(Counter(x["anonymous_speaker_group"] for x in sheet["items"]).values()), {8})

    def test_multiple_providers_get_unique_ids_without_unblinding_roles(self):
        qwen = self.source_for_structural_testing_only("qwen-local")
        gemini = self.source_for_structural_testing_only("gemini-hosted")
        public, secret, template = self.review.prepare(
            [qwen, gemini], salt=b"x" * 16,
        )
        self.assertEqual(len(public["items"]), 96)
        self.assertEqual(len({r["blind_id"] for r in public["items"]}), 96)
        self.assertEqual(len({r["anonymous_speaker_group"] for r in public["items"]}), 6)
        self.assertEqual(len(secret["items"]), 96)
        self.assertNotIn("provider", public["items"][0])
        self.assertEqual(len(template["ratings"]), 96)

    def test_cannot_self_certify_without_two_complete_human_reviews(self):
        data=self.source_for_structural_testing_only()
        public, key, template=self.review.prepare([data], salt=b"c" * 16)
        with self.assertRaises(PermissionError):
            self.review.summarize_reviews(key, [])
        with self.assertRaises(PermissionError):
            self.review.summarize_reviews(key, [template])
        r1=deepcopy(template)
        r2=deepcopy(template)
        r1["reviewer_id"]="blind.review.one"
        r2["reviewer_id"]="blind.review.two"
        for file in (r1,r2):
            for row in file["ratings"]:
                for category in self.review.instrument()["categories"]:
                    row[category]=4
        result=self.review.summarize_reviews(key,[r1,r2])
        self.assertEqual(result["utterances_reviewed"], 48)
        self.assertEqual(result["distinct_independent_reviewer_ids"], 2)
        self.assertTrue(result["human_review_complete"])
        self.assertIsNone(result["selected_production_speech_provider"])
        self.assertFalse(result["production_choice_model_unchanged"] is False)
        self.assertEqual(result["world_commands_sent"], 0)
        r2["reviewer_id"]="blind.review.one"
        with self.assertRaises(PermissionError):
            self.review.summarize_reviews(key,[r1,r2])
        r2["reviewer_id"]="blind.review.two"
        r2["ratings"][0]["voice_distinctiveness"]=None
        with self.assertRaises(ValueError):
            self.review.summarize_reviews(key,[r1,r2])
        r2["ratings"][0]["voice_distinctiveness"]=4
        r2["ratings"][0]["flags"]=["fabricated_world_authority"]
        with self.assertRaises(ValueError):
            self.review.summarize_reviews(key,[r1,r2])

if __name__ == "__main__":
    unittest.main()
