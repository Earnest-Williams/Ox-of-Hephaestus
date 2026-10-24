"""G16g offline reviewer HTML tests; all samples are SYNTHETIC fixtures."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scenarios"))
import g16g_review_ui as reviewer


def fixture() -> tuple[dict, dict]:
    """No native dialogue or private actor identities appear in these tests."""
    dimensions = {
        "voice_distinctiveness": "Individual speaker fidelity",
        "profile_fidelity": "Fit to anonymous trait reference",
        "grounding": "No invented world facts",
        "naturalness": "Natural freighter-crew speech",
        "emotional_fit": "Appropriate tone",
    }
    items = [
        {
            "blind_id": f"{index:024x}",
            "anonymous_speaker_group": f"speaker-{index%6}",
            "neutral_original_trait_reference_0_to_100": {
                "conscientiousness": 51, "risk_tolerance": 52,
                "authority_challenge": 53, "agreeableness": 54,
                "collaboration": 55, "openness": 56,
            },
            "known_context": "The ship has no approved work order.",
            "preselected_speech_intent": "Request help, without giving orders.",
            "utterance": "Would you review this unsigned note, if you have time?",
        } for index in range(48)
    ]
    sheet = {
        "schema": 1,
        "blind_review": True,
        "providers_hidden": True,
        "prompt_arms_hidden": True,
        "human_review_needed": True,
        "rubric": dimensions,
        "permitted_flags": ["invented_permission", "factual_contradiction"],
        "items": items,
    }
    digest = hashlib.sha256(json.dumps(
        sheet, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    blank = {
        "schema": 1,
        "reviewer_id": "",
        "blinded_sheet_sha256": digest,
        "ratings": [
            {"blind_id": item["blind_id"], **{k: None for k in dimensions},
             "flags": []} for item in items
        ],
    }
    return sheet, blank


def rehash(sheet: dict, blank: dict) -> None:
    blank["blinded_sheet_sha256"] = hashlib.sha256(json.dumps(
        sheet, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


class OfflineReviewerSourceTests(unittest.TestCase):
    def test_render_public_only_with_valid_hash_and_all_48_samples(self):
        sheet, blank = fixture()
        html = reviewer.render(sheet, blank)
        self.assertIn("Ox / G16g", html)
        self.assertIn("const sheet = {", html)
        self.assertIn("const template = {", html)
        self.assertIn("g16g-", html)
        self.assertNotIn("__BLIND_SHEET__", html)
        self.assertNotIn("__BLANK_TEMPLATE__", html)
        self.assertNotIn("private_answer_key", html)
        self.assertNotIn("answer_key_keep_private", html)
        self.assertEqual(html.count("anonymous_speaker_group"), 49)
        self.assertIn(blank["blinded_sheet_sha256"], html)

    def test_injection_is_escaped_inside_js_not_executed_as_markup(self):
        sheet, blank = fixture()
        sheet["items"][1]["utterance"] = "</script><script>alert('PRIVATE')</script>"
        rehash(sheet, blank)
        html = reviewer.render(sheet, blank)
        self.assertNotIn("</script><script>alert", html)
        self.assertIn(r"\\u003c/script\\u003e", html)
        self.assertIn("const template = {", html)

    def test_reject_private_data_forged_hash_and_pre_scored_respondent(self):
        sheet, blank = fixture()
        bad = deepcopy(sheet)
        bad["items"][0]["provider"] = "secret-experimental-arm"
        rehash(bad, blank)
        with self.assertRaises(PermissionError):
            reviewer.render(bad, blank)
        sheet, blank = fixture()
        bad = deepcopy(sheet)
        bad["items"][0]["utterance"] = "some changed unverified world claim"
        with self.assertRaises(PermissionError):
            reviewer.render(bad, blank)
        bad = deepcopy(blank)
        bad["ratings"][0]["grounding"] = 5
        with self.assertRaises(ValueError):
            reviewer.render(sheet, bad)
        bad = deepcopy(sheet)
        bad["prompt_arms_hidden"] = False
        rehash(bad, blank)
        with self.assertRaises(PermissionError):
            reviewer.render(bad, blank)

    def test_public_pack_cli_generates_offline_html_without_answer_key(self):
        sheet, blank = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "public_review_pack.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr(reviewer.PACK_SHEET, json.dumps(sheet))
                bundle.writestr(reviewer.PACK_BLANK, json.dumps(blank))
                bundle.writestr("secret-not-in-archive.txt",
                                "Not used; this is only a test for unexpected ZIP files.")
            output = root / "offline.html"
            done = subprocess.run(
                [sys.executable, str(ROOT / "scenarios/g16g_review_ui.py"),
                 "--pack", str(archive), "--output", str(output)],
                check=True, text=True, capture_output=True,
            )
            self.assertIn("OX_G16G_PUBLIC_OFFLINE_REVIEWER_HTML_READY", done.stdout)
            html = output.read_text(encoding="utf-8")
            self.assertIn("reviewer_id", html)
            self.assertIn("anonymous_speaker_group", html)
            self.assertNotIn("secret-not-in-archive", html)
            self.assertGreater(len(html), 13000)


if __name__ == "__main__":
    unittest.main()
