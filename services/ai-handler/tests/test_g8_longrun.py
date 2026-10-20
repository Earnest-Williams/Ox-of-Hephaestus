"""Bounded G8 policy checks without a running world."""
import unittest
from pathlib import Path
import ast
from importlib.util import spec_from_file_location, module_from_spec


def load_trial():
    path = Path("scenarios/g8_soap_opera/live_trial.py")
    ast.parse(path.read_text(encoding="utf-8"))
    spec = spec_from_file_location("ox_g8_live", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrialWiringTests(unittest.TestCase):
    def test_bounded_roster_schedule_and_world_work(self):
        mod = load_trial()
        self.assertEqual(len(mod.ROSTER), 6)
        self.assertEqual(len(mod.SCHEDULE), 5)
        self.assertEqual([t for _, t in mod.SCHEDULE],
                         [35, 138, 256, 367, 444])
        self.assertEqual(sum(len(mod.SEED_TEXT[p]) for p in mod.ROSTER), 18)
        self.assertEqual(mod.WORK["cargo"][-1], "return")
        self.assertEqual(mod.WORK["scrubber"][-1], "return")

    def test_private_seed_claims_and_real_goap_planning(self):
        mod = load_trial()
        memories = mod.seeds_for("mara")
        self.assertEqual(len({m.memory_id for m in memories}), 3)
        self.assertTrue(all("NOT world-verified" in m.render() for m in memories))
        plan = mod.GOAP.plan({"together", "conversation_open",
                              "heard_uncertainty"}, {"interest_expressed"})
        self.assertTrue(plan.actions)


if __name__ == "__main__":
    unittest.main()
