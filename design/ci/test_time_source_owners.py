"""Regression guard for independent world timer ownership."""
from copy import deepcopy
from pathlib import Path
import unittest

from time_source_owners import OWNERS, SCHEMA, classify_scripts
from audit_world_time import audit


def sample():
    return {
        "schema_version": "ox-world-time-audit/1",
        "dynamic_coverage": False,
        "sites": [
            {
                "path": path, "symbol": name, "kind": "scheduled_script",
                "line": 1, "context": "test",
            }
            for path, name in sorted(OWNERS)
        ] + [{
            "path": "game/world/live_clock.py",
            "kind": "external_game_clock",
            "symbol": "gametime.gametime",
            "line": 2, "context": "tick_game_clock",
        }],
    }


class WorldTimeOwnerTests(unittest.TestCase):
    def test_exact_known_world_scripts_have_distinct_review_owners(self):
        result = classify_scripts(sample())
        self.assertEqual(result["schema_version"], SCHEMA)
        self.assertEqual(result["scheduled_entrypoints"], 3)
        self.assertFalse(result["pause_enabled"])
        self.assertFalse(result["runtime_completeness_claim"])
        self.assertEqual(
            {x["owner"] for x in result["entries"]}, {
                "continuous_physics",
                "engineering_duty_and_social",
                "disposable_terminal_scenario",
            },
        )
        self.assertEqual(result, classify_scripts(sample()))

    def test_unknown_timer_fails_until_ownership_is_reviewed(self):
        report = sample()
        report["sites"].append({
            "path": "game/world/new_watch.py",
            "kind": "scheduled_script",
            "symbol": "NewShipClock.at_repeat",
            "line": 10,
        })
        with self.assertRaisesRegex(ValueError, "Unclassified"):
            classify_scripts(report)

    def test_moved_or_missing_timer_fails_instead_of_silent_success(self):
        report = sample()
        report["sites"] = [
            x for x in report["sites"]
            if x.get("symbol") != "TerminalClock.at_repeat"
        ]
        with self.assertRaisesRegex(ValueError, "Missing expected"):
            classify_scripts(report)

    def test_duplicate_or_malformed_audit_refused(self):
        report = sample()
        report["sites"].append(deepcopy(report["sites"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            classify_scripts(report)
        for value in (None, {}, {"schema_version": "wrong"}, []):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    classify_scripts(value)

    def test_real_repository_still_has_exact_three_reviewed_scripts(self):
        # This gate intentionally fails when production adds a fourth
        # directly discoverable world timer without updating the owner map.
        root = Path(__file__).resolve().parents[2]
        real = audit(root)
        result = classify_scripts(real)
        self.assertEqual(result["scheduled_entrypoints"], 3)
