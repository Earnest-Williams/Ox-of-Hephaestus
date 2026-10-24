"""Pre-run G16e preregistration integrity and non-native fixture safeguards.

No model-quality claim and no native weights; actual six-actor experiment
runs only from the isolated, pinned source/weight Actions workflow.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
G16E_DIR = ROOT / "scenarios/g8_soap_opera"
sys.path.insert(0, str(G16E_DIR))
PREREG = ROOT / "design/prototypes/g16e-preregistration-v1.json"


class G16EProtocolTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(PREREG.read_text(encoding="utf-8"))

    def test_fixed_before_experiment_and_exact_936_call_budget(self):
        d = self.data
        self.assertEqual(d["status"], "preregistered_before_native_G16e")
        from hashlib import sha1
        raw = PREREG.read_bytes()
        blob = sha1(b"blob " + str(len(raw)).encode() + bytes((0,)) + raw).hexdigest()
        self.assertEqual(blob, "e8529be931bebb6cda5c00fab90458cf5ef52a3c")
        self.assertEqual(d["schema_version"], 1)
        self.assertEqual(len(d["scenarios"]), 8)
        self.assertEqual(len([c for c in d["scenarios"]
                              if c["source"] == "preregistered_new"]), 4)
        self.assertEqual(len([c for c in d["scenarios"] if c["safety"]]), 1)
        self.assertEqual(d["design_facts"]["actors"], 6)
        self.assertEqual(d["design_facts"]["native_engine_calls_per_actor"], 156)
        self.assertEqual(d["design_facts"]["total_planned_native_forwards"], 936)
        self.assertEqual(6 * 8 * 2 * 3 * 3 + 24 * 3, 936)
        self.assertEqual(d["acceptance"]["identical_repeat_choices_required"], 24)
        self.assertEqual(d["acceptance"]["minimum_adjusted_non_safety_disagreement_rate"], 0.25)
        self.assertFalse(d["acceptance"]["retune_on_failed_holdout"])

    def test_scene_independence_and_bounded_non_safety_contexts(self):
        d = self.data
        scenes = d["scenarios"]
        self.assertEqual(len({x["id"] for x in scenes}), 8)
        for scene in scenes:
            self.assertEqual(scene["id"].startswith("g16e."),
                             scene["source"] == "preregistered_new")
            if scene["source"] == "preregistered_new":
                self.assertFalse(scene["safety"])
                self.assertTrue(100 <= len(scene["context"]) <= 1200)
                self.assertEqual(scene["context"].count("{peer}"), 1)
                self.assertIn(scene["menu_key"], {
                    "g14.verified_mutual_aid",
                    "g14.approved_watch_relief",
                    "g14.uncertain_private_apology",
                })


@unittest.skipUnless(
    importlib.util.find_spec("concordia") is not None
    and importlib.util.find_spec("ox_contracts") is not None,
    "Optional genuine Concordia and cross-system G16a contract absent",
)
class ActualSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = importlib.import_module("g16e_native")
        cls.assess = importlib.import_module("g16e_assess")

    def test_tagged_native_menu_matches_all_eight_cases(self):
        record, scenes, catalog = self.native.fixed_protocol()
        self.assertEqual(len(scenes), 8)
        self.assertEqual(len({row["id"] for row, _, _ in scenes}), 8)
        self.assertEqual(len({catalog.menu(x["menu_key"]).menu_key
                              for x, _, _ in scenes}), 4)
        self.assertEqual(sum(x["safety"] for x, _, _ in scenes), 1)

    def test_each_observed_native_pass_has_independent_code_semantic_mapping(self):
        from ox_ai.inference.position_balanced_choice import PositionBalancedDeciderChoiceModel
        options = (
            ("accept_help", "Act: accept_help"),
            ("work_alone", "Act: work_alone"),
            ("reschedule", "Act: reschedule"),
        )
        tracer = self.native.ObservedNativeForwards(
            self.native.FakePositionBiasedEngine(), options
        )
        model = PositionBalancedDeciderChoiceModel(
            "", options, engine=tracer,
        )
        model.sample_choice("One identical hypothetical actor prompt", ("A", "B", "C"))
        self.assertEqual(len(tracer.records), 3)
        scores = model.last["semantic_probabilities"]
        for offset, passed in enumerate(tracer.records):
            self.assertEqual(passed["native_position"], offset)
            self.assertEqual(
                set(passed["position_to_semantic_key"]), set(scores)
            )
            self.assertEqual(len(passed["position_to_code"]), 3)
        for key in scores:
            self.assertAlmostEqual(
                scores[key],
                sum(row["semantic_scores"][key] for row in tracer.records) / 3,
            )

    def test_nonvacuous_synthetic_high_confidence_safety_lock(self):
        from ox_ai.agents.crew_blueprints import compose_blueprint
        from ox_ai.inference.disposition_choice import score_personality_choice
        profile = compose_blueprint("g16e.synthetic", "Safety Control")
        menu = self.native.load_catalog().menu("g14.finite_spare_dispute")
        kw = dict(
            menu=menu, profile=profile,
            seed="g16e-safety-coverage", actor="#900",
            boundary="world.synthetic.g16e.safety", kind="urgent"
        )
        with self.assertRaises(PermissionError):
            score_personality_choice(
                native_scores={
                    "reserve_spare": 0.45, "seek_review": 0.35,
                    "support_loan": 0.20
                }, **kw
            )
        locked = score_personality_choice(
            native_scores={
                "reserve_spare": 0.95, "seek_review": 0.03,
                "support_loan": 0.02
            }, **kw
        )
        self.assertTrue(locked["safety_locked"])
        self.assertEqual(locked["native_winner"], "reserve_spare")
        self.assertEqual(locked["selected_semantic_key"], "reserve_spare")
        self.assertEqual(locked["adjusted_scores"]["reserve_spare"], 1.0)
        self.assertTrue(all(value == 0.0 for value in locked["shifts"].values()))

    def test_independent_assessor_never_accepts_missing_actor_or_mock_data(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(FileNotFoundError):
                self.assess.assess(Path(root))
            # A forged actor row with no other five genuine actors must fail.
            (Path(root) / "ari.json").write_text(json.dumps({
                "schema": 1, "engine": "fixture", "role": "ari",
            }), encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                self.assess.assess(Path(root))


if __name__ == "__main__":
    unittest.main()
