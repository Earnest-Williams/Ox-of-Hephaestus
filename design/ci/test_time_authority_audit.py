"""Pure tests for the static world-time migration inventory."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from audit_world_time import (
    REQUIRED, audit, classify_call, inspect_source, is_production,
)


EXAMPLE = """
from evennia.scripts.scripts import DefaultScript
from evennia.utils import gametime
from world.continuous_ship_physics import tick_continuous_physics

class ShipClock(DefaultScript):
    def at_repeat(self):
        now = gametime.gametime(absolute=True)
        tick_continuous_physics(now_game_time=now)
"""


class TimeAuthorityAuditTests(unittest.TestCase):
    def test_detects_independent_script_and_game_clock(self):
        hits = inspect_source("game/world/live_clock.py", EXAMPLE)
        kinds = {(entry.kind, entry.symbol) for entry in hits}
        self.assertIn(("scheduled_script", "ShipClock.at_repeat"), kinds)
        self.assertIn(("external_game_clock", "gametime.gametime"), kinds)
        self.assertIn(("world_tick", "tick_continuous_physics"), kinds)
        self.assertTrue(all(entry.path == "game/world/live_clock.py" for entry in hits))

    def test_classifies_external_wall_and_delayed_calls(self):
        self.assertEqual(classify_call("gametime.gametime"), "external_game_clock")
        self.assertEqual(classify_call("time.time"), "wall_clock")
        self.assertEqual(classify_call("datetime.now"), "wall_clock")
        self.assertEqual(classify_call("asyncio.sleep"), "scheduler")
        self.assertEqual(classify_call("create_script"), "scheduler")
        self.assertEqual(classify_call("tick_rounds"), "world_tick")
        self.assertIsNone(classify_call("math.sqrt"))
        self.assertIsNone(classify_call("network_reachable"))

    def test_test_and_vendor_sources_do_not_become_production_sites(self):
        self.assertTrue(is_production(Path("game/world/live_clock.py")))
        self.assertTrue(is_production(
            Path("services/ai-handler/src/ox_ai/runtime/watch_service.py")))
        for name in (
            "game/world/tests/test_live_clock.py",
            "game/world/migrations/0001_initial.py",
            "evennia/utils/gametime.py",
            "game/world/test_dummy.py",
            "game/world/example_test.py",
        ):
            with self.subTest(path=name):
                if name.startswith("evennia"):
                    # The target roots exclude vendored Evennia.
                    self.assertFalse(any(name.startswith(p + "/")
                                         for p in ("game", "services")))
                else:
                    self.assertFalse(is_production(Path(name)))

    def test_inventory_deterministic_and_missing_anchor_fails(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "sources missing"):
                audit(root)
            for path in REQUIRED:
                f = root / path
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("VALUE = 1\n", encoding="utf-8")
            source = root / "game/world/live_clock.py"
            source.write_text(EXAMPLE, encoding="utf-8")
            fake_test = root / "game/world/tests/test_clock.py"
            fake_test.parent.mkdir(parents=True, exist_ok=True)
            fake_test.write_text(EXAMPLE, encoding="utf-8")
            first, second = audit(root), audit(root)
            self.assertEqual(first, second)
            self.assertEqual(first["schema_version"], "ox-world-time-audit/1")
            self.assertFalse(first["dynamic_coverage"])
            self.assertEqual(first["scanned_files"], len(REQUIRED))
            self.assertEqual(first["site_count"], 3)
            self.assertNotIn("game/world/tests/test_clock.py",
                             {e["path"] for e in first["sites"]})
