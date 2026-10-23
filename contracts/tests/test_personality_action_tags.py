"""G16a strict schema and real authored finite-menu source compatibility."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest

from pydantic import ValidationError
from ox_contracts import ActionTagCatalog, DispositionTags, load_catalog


ROOT = Path(__file__).resolve().parents[2]


def assignment(path: str, name: str):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    found = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    ]
    if len(found) != 1:
        raise AssertionError(f"Expected exactly one {name} in {path}")
    return found[0]


def signature(call):
    if (not isinstance(call, ast.Call)
            or not isinstance(call.func, ast.Name)
            or call.func.id != "CommandOption"
            or not 2 <= len(call.args) <= 3 or call.keywords):
        raise AssertionError("Unrecognized offered CommandOption signature")
    verb = ast.literal_eval(call.args[1])
    target = ast.literal_eval(call.args[2]) if len(call.args) == 3 else None
    return (verb, target, ())


class StrictContractTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()

    def test_packaged_schema_digest_and_fail_closed_lookup(self):
        c = self.catalog
        self.assertEqual(c.schema_version, 1)
        self.assertEqual(len(c.menus), 10)
        self.assertEqual(sum(len(m.options) for m in c.menus), 32)
        self.assertEqual(c.content_sha256(), load_catalog().content_sha256())
        self.assertEqual(len(c.content_sha256()), 64)
        schema = DispositionTags.model_json_schema()
        self.assertEqual(schema["additionalProperties"], False)
        for name in ("risk", "deference", "social", "autonomy", "procedure"):
            self.assertEqual(schema["properties"][name]["minimum"], -1.0)
            self.assertEqual(schema["properties"][name]["maximum"], 1.0)
        self.assertEqual(
            c.menu("live.p4a_pump_alarm").by_command("isolate", "pump").semantic_key,
            "isolate",
        )
        for func in (
            lambda: c.menu("live.p4a_pump_alarm").by_command("isolate", "cargo"),
            lambda: c.menu("live.p4a_pump_alarm").by_key("grant_permission"),
            lambda: c.menu("unknown.world.operation"),
        ):
            with self.assertRaises(KeyError):
                func()

    def test_reject_nonfinite_coerced_missing_extra_duplicate(self):
        original = json.loads(self.catalog.model_dump_json())
        for bad in (1, True, "0.5", None, float("nan"), float("inf"), -1.01, 1.01):
            payload = deepcopy(original)
            payload["menus"][0]["options"][0]["tags"]["risk"] = bad
            with self.subTest(value=repr(bad)), self.assertRaises(ValidationError):
                ActionTagCatalog.model_validate_json(json.dumps(payload))
        for dimension in ("risk", "deference", "social", "autonomy", "procedure"):
            payload = deepcopy(original)
            del payload["menus"][0]["options"][0]["tags"][dimension]
            with self.subTest(dimension=dimension), self.assertRaises(ValidationError):
                ActionTagCatalog.model_validate_json(json.dumps(payload))
        payload = deepcopy(original)
        payload["menus"][0]["options"][0]["tags"]["unauthorized"] = 0.5
        with self.assertRaises(ValidationError):
            ActionTagCatalog.model_validate_json(json.dumps(payload))
        payload = deepcopy(original)
        payload["menus"].append(deepcopy(payload["menus"][0]))
        with self.assertRaises(ValidationError):
            ActionTagCatalog.model_validate_json(json.dumps(payload))
        payload = deepcopy(original)
        payload["menus"][0]["options"].append(deepcopy(payload["menus"][0]["options"][0]))
        with self.assertRaises(ValidationError):
            ActionTagCatalog.model_validate_json(json.dumps(payload))
        payload = deepcopy(original)
        payload["menus"][0]["options"][1]["verb"] = payload["menus"][0]["options"][0]["verb"]
        with self.assertRaises(ValidationError):
            ActionTagCatalog.model_validate_json(json.dumps(payload))

    def test_projection_requires_all_dimensions_and_finite_values(self):
        t = self.catalog.menu("g14.verified_mutual_aid").by_key("work_alone").tags
        with self.assertRaises(ValueError):
            t.project({"autonomy": 0.5})
        with self.assertRaises(ValueError):
            t.project(dict(risk=0.0, deference=0.0, social=0.0,
                           autonomy=float("nan"), procedure=0.0))


class ExistingMenuCoverageTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()

    def check_menu(self, key, observed):
        declared = self.catalog.menu(key)
        self.assertEqual(
            {x.signature for x in declared.options}, set(observed),
            f"Missing, invented, or stale tagged action in {key}"
        )
        self.assertEqual(len(declared.options), len(observed))
        self.assertEqual(len(set(observed)), len(observed))

    def test_g14_cases_are_identical_semantic_signatures(self):
        cases = assignment("scenarios/g8_soap_opera/g14_profile_salience.py", "CASES")
        self.assertIsInstance(cases, ast.Tuple)
        self.assertEqual(len(cases.elts), 4)
        for case in cases.elts:
            self.assertEqual(case.func.id, "Case")
            key = ast.literal_eval(case.args[0])
            original = ast.literal_eval(case.args[4])
            self.assertEqual(
                [x.semantic_key for x in self.catalog.menu("g14." + key).options],
                [action for action, _label in original]
            )
            self.check_menu(
                "g14." + key,
                [("consider." + action, "g14." + key, ()) for action, _ in original],
            )

    def test_real_p4a_alarm_menu(self):
        value = assignment(
            "services/ai-handler/src/ox_ai/scenarios/p4a_personality_gate.py", "CHOICES"
        )
        self.assertIsInstance(value, ast.Tuple)
        self.check_menu("live.p4a_pump_alarm", [signature(c) for c in value.elts])
        self.assertTrue(self.catalog.menu("live.p4a_pump_alarm").safety_critical)

    def test_existing_offline_gauge_and_four_dilemmas(self):
        value = assignment("scenarios/personality_route_trial.py", "options")
        self.assertIsInstance(value, ast.Tuple)
        self.check_menu("offline.personality_gauge", [signature(c) for c in value.elts])
        cases = assignment(
            "services/ai-handler/src/ox_ai/scenarios/personality_dilemmas.py", "DILEMMAS"
        )
        self.assertIsInstance(cases, ast.Tuple)
        self.assertEqual(len(cases.elts), 4)
        for case in cases.elts:
            name = ast.literal_eval(case.args[0])
            offered = case.args[6]
            self.assertIsInstance(offered, ast.Tuple)
            self.check_menu(
                "offline.dilemma." + name, [signature(c) for c in offered.elts]
            )
        g14_cases = assignment(
            "scenarios/g8_soap_opera/g14_profile_salience.py", "CASES"
        ).elts
        expected = {"live.p4a_pump_alarm", "offline.personality_gauge"}
        expected.update("g14." + ast.literal_eval(x.args[0]) for x in g14_cases)
        expected.update("offline.dilemma." + ast.literal_eval(x.args[0]) for x in cases.elts)
        self.assertEqual({m.menu_key for m in self.catalog.menus}, expected)

    def test_seven_native_direction_signs_retrospective_sanity_only(self):
        # Native mean score shift = numeric independent - numeric original,
        # exact successful G14 final-head run #40028008764. These seven
        # directional checks are RETROSPECTIVE, not predictive validation.
        scores = {
            "g14.verified_mutual_aid": {
                "accept_help": -0.011233333333333326,
                "work_alone": 0.004783333333333334,
            },
            "g14.approved_watch_relief": {
                "cover_watch": -0.02029444444444445,
                "keep_watch": 0.011783333333333333,
            },
            "g14.uncertain_private_apology": {
                "consider_talk": -0.014322222222222228,
                "protect_space": 0.009594444444444438,
                "ask_later": 0.0047166666666666746,
            },
        }
        contrast = dict(risk=1.0, deference=-1.0, social=-1.0,
                        autonomy=1.0, procedure=-1.0)
        count = 0
        for menu, actions in scores.items():
            for key, observed in actions.items():
                lean = self.catalog.menu(menu).by_key(key).tags.project(contrast)
                self.assertNotEqual(lean, 0.0)
                self.assertEqual(lean > 0, observed > 0, f"{menu}:{key}")
                count += 1
        self.assertEqual(count, 7)


if __name__ == "__main__":
    unittest.main()
