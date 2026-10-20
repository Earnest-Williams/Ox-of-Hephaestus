"""Bounded G8 policy checks without a running world."""
import unittest
from pathlib import Path
import ast
from importlib.util import find_spec, spec_from_file_location, module_from_spec


def load_trial():
    path = Path("scenarios/g8_soap_opera/live_trial.py")
    ast.parse(path.read_text(encoding="utf-8"))
    # This model-backed fixture is exercised by the native G8 workflow.
    # The minimal scaffold intentionally does not install Concordia.
    if find_spec("concordia") is None:
        raise unittest.SkipTest("G8 live fixture requires optional Concordia")
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


    def test_private_reinterpretation_changes_goap_social_appraisal(self):
        from pathlib import Path
        import tempfile
        mod = load_trial()
        with tempfile.TemporaryDirectory() as directory:
            t = mod.Trial(241, Path(directory))
            t.bind({r: f"#{i+1}" for i, r in enumerate(mod.ROSTER)})
            t.turn = 95
            before = t.perspective("mara", "lin")
            original = t.brains["mara"].temporal_memories.get("g8.mara.1").text
            opposing = mod.TemporalMemory(
                "g8.received.ari.statement", "ari",
                "Ari said: Lin is still my spouse.",
                "witnessed_speech", 95, 95, 100, 95,
                source_event_id="g8.real.heard.95",
                claim_key="lin_ari_separated", claim_subject="lin",
                claim_stance=-1, source_group="ari.marriage_account",
                claim_credibility=92,
            )
            t.remember_episode("mara", opposing)
            after = t.perspective("mara", "lin")
            self.assertLess(after[0], before[0])
            self.assertEqual(t.brains["mara"].temporal_memories.get(
                "g8.mara.1").text, original)
            revisions = [r for r in t.reinterpretations
                         if r["claim"] == "lin_ari_separated"]
            self.assertTrue(revisions)
            self.assertEqual(revisions[-1]["reason"], "counterevidence")
            self.assertEqual(revisions[-1]["source_id"], "g8.real.heard.95")
            self.assertIsNone(t.brains["teo"].temporal_memories.get(
                "g8.received.ari.statement"))
            # Two more same-origin repetitions cannot manufacture consensus.
            previous = len(t.reinterpretations)
            t.turn = 96
            t.remember_episode("mara", mod.TemporalMemory(
                "g8.received.ari.again", "ari", "Ari repeated the same account.",
                "witnessed_speech", 96, 96, 100, 95,
                source_event_id="g8.real.heard.96",
                claim_key="lin_ari_separated", claim_subject="lin",
                claim_stance=-1, source_group="ari.marriage_account",
                claim_credibility=92,
            ))
            self.assertEqual(len(t.reinterpretations), previous)

    def test_world_agreement_does_not_create_desire(self):
        import tempfile
        from pathlib import Path
        mod = load_trial()
        with tempfile.TemporaryDirectory() as directory:
            t = mod.Trial(241, Path(directory))
            t.bind({role: f"#{i + 1}" for i, role in enumerate(mod.ROSTER)})
            t.turn = 80
            t.remember_contract("mara", "lin", {
                "request_id": "a" * 32, "source_event_id": "oxevt-v2-999"
            }, "accepted")
            for observer in ("mara", "lin"):
                episode = next(x for x in t.brains[observer].temporal_memories.to_records()
                               if x["memory_id"].startswith("g8.world."))
                self.assertEqual(episode["interest_effect"], 0)
                self.assertGreater(episode["trust_effect"], 0)

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
