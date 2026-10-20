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


    def test_temporal_memories_change_private_appraisal(self):
        from pathlib import Path
        import tempfile
        mod = load_trial()
        with tempfile.TemporaryDirectory() as directory:
            t = mod.Trial(241, Path(directory))
            t.bind({role: f"#{i + 1}" for i, role in enumerate(mod.ROSTER)})
            t.turn = 100
            trust, affection, sources = t.perspective("mara", "lin")
            base_trust = t.private["mara"]["trust"]["lin"]
            base_affection = t.private["mara"]["affection"]["lin"]
            self.assertTrue(sources)
            self.assertNotEqual((trust, affection), (base_trust, base_affection))
            # A newer refusal affects the next appraisal, even while the
            # original romance recollection continues to exist.
            from ox_ai.memory.temporal import TemporalMemory
            t.brains["mara"].remember_timed(TemporalMemory(
                "refusal.101", "lin", "Lin turned me down.", "world_receipt",
                101, 101, 100, 100, trust_effect=-40, interest_effect=-30,
                source_event_id="oxevt-v2-101"))
            t.turn = 102
            updated = t.perspective("mara", "lin")
            self.assertLess(updated[0], trust)
            self.assertLess(updated[1], affection)
            self.assertGreater(len(updated[2]), len(sources))


if __name__ == "__main__":
    unittest.main()
