"""G9 longitudinal Decider experiment contracts, without expensive model loads."""
from importlib.util import find_spec, module_from_spec, spec_from_file_location
from pathlib import Path
import json
import tempfile
import unittest

from ox_ai.agents.crew_blueprints import CrewBlueprint


def load_g8():
    if find_spec("concordia") is None:
        raise unittest.SkipTest("Native Concordia optional extra not installed")
    path = Path("scenarios/g8_soap_opera/live_trial.py")
    spec = spec_from_file_location("g9_trial", path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_g9_evaluator():
    path = Path("scenarios/g8_soap_opera/g9_evaluate.py")
    spec = spec_from_file_location("g9_eval", path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LongitudinalPersonalityTests(unittest.TestCase):
    def test_actor_profiles_are_distinct_and_persistable(self):
        m = load_g8()
        profiles = [m.g9_blueprint(role) for role in m.ROSTER]
        self.assertEqual(len({p.person_id for p in profiles}), 6)
        self.assertEqual(len({p.traits for p in profiles}), 6)
        self.assertTrue(all(
            CrewBlueprint.from_record(p.to_record()) == p
            for p in profiles
        ))
        self.assertGreater(dict(m.g9_blueprint("iona").traits)["authority_challenge"],
                           dict(m.g9_blueprint("ari").traits)["authority_challenge"])
        self.assertGreater(dict(m.g9_blueprint("mara").traits)["agreeableness"],
                           dict(m.g9_blueprint("iona").traits)["agreeableness"])
        self.assertEqual(len(m.G9_INTENTS), len(m.G9_DESCRIPTIONS))
        self.assertEqual(set(m.G9_INTENTS), set(m.GOALS))
        for name in m.G9_INTENTS:
            self.assertEqual(m.GOAP.plan(
                {"together", "conversation_open", "heard_uncertainty"},
                {m.GOALS[name]},
            ).actions[0].verb, "say")

    def test_legacy_g8_remains_symbolic_without_loading_decider(self):
        m = load_g8()
        with tempfile.TemporaryDirectory() as d:
            t = m.Trial(241, Path(d))
            t.bind({role: f"#{i+1}" for i, role in enumerate(m.ROSTER)})
            self.assertEqual(t.cognition_mode, "symbolic")
            self.assertTrue(all(x.blueprint is None for x in t.brains.values()))
            self.assertEqual(len(t.route_audit), 0)
            t.save()
            with self.assertRaises(PermissionError):
                m.Trial(241, Path(d), cognition_mode="decider")
            t2 = m.Trial(241, Path(d))
            self.assertEqual(t2.cognition_mode, "symbolic")
            self.assertEqual(len(t2.brains), 6)

    def test_cognition_window_persists_without_erasing_actor_history(self):
        if find_spec("concordia") is None:
            self.skipTest("Native Concordia optional extra not installed")
        from concordia.testing.mock_model import MockModel
        from ox_ai.agents.crew import CrewAgent, CrewIdentity
        from ox_ai.ports.base import WorldObservation
        identity = CrewIdentity(
            "ox.g9.window", "#90", "Window Test",
            "Watch and listen", "Remember valid observations"
        )
        with tempfile.TemporaryDirectory() as d:
            agent = CrewAgent(
                identity, MockModel(), observation_history_length=8,
            )
            for i in range(13):
                self.assertTrue(agent.observe(
                    WorldObservation(f"world.g9.{i}", "#90", float(i),
                                     f"Received speech {i}", kind="heard_speech")
                ))
            self.assertEqual(agent.revision, 13)
            self.assertEqual(agent.observation_history_length, 8)
            checkpoint = Path(d) / "character.brain.json"
            agent.save_checkpoint(checkpoint)
            restored = CrewAgent.from_checkpoint(checkpoint, MockModel())
            self.assertEqual(restored.observation_history_length, 8)
            self.assertEqual(restored.revision, 13)
            fork = restored.fork_for_inference()
            self.assertEqual(fork.observation_history_length, 8)
            self.assertEqual(fork.snapshot()["seen_observations"],
                             restored.snapshot()["seen_observations"])
            with self.assertRaises(ValueError):
                CrewAgent(identity, MockModel(), observation_history_length=0)
            # Older snapshots default to the original full 32 observations.
            raw = json.loads(checkpoint.read_text())
            raw.pop("observation_history_length")
            checkpoint.write_text(json.dumps(raw))
            older = CrewAgent.from_checkpoint(checkpoint, MockModel())
            self.assertEqual(older.observation_history_length, 32)

    def test_counterfactual_menu_is_the_same_safe_goap_menu(self):
        if find_spec("concordia") is None:
            self.skipTest("Native Concordia optional extra not installed")
        path = Path("scenarios/g8_soap_opera/g9_memory_counterfactual.py")
        spec = spec_from_file_location("g9_counterfactual", path)
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        trial = load_g8()
        offered, mapped = mod.menu_for_target(trial, "mara", "lin")
        self.assertEqual(len(offered), len(trial.G9_INTENTS))
        self.assertEqual(set(mapped.values()), set(trial.G9_INTENTS))
        self.assertEqual({o.verb for o in offered}, {"say"})
        self.assertEqual(len({(o.verb, o.target) for o in offered}), len(offered))
        with self.assertRaises(ValueError):
            mod.menu_for_target(trial, "mara", "mara")
        with self.assertRaises(ValueError):
            mod.menu_for_target(trial, "mara", "unknown")

    def test_verifier_rejects_authored_only_or_incomplete_world(self):
        evaluation = load_g9_evaluator().evaluate
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "state.json").write_text(json.dumps({
                "turn":205, "cognition_mode":"decider",
                "trace":[{"turn":i,"kind":"private_reflection","actor":"ari"}
                         for i in range(1,206)],
                "faults":[{"name":"g8-0","kind":"cargo","at":35,
                           "seen":False,"completed":False,"receipts":[]}],
                "route_audit":[],
            }))
            with self.assertRaisesRegex(AssertionError,"Fault not recovered"):
                evaluation(p)


if __name__ == "__main__":
    unittest.main()
