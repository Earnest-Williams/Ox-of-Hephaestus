"""G10 factorial validity, safety, provenance, failure injection, actor isolation."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class G10StructuralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assess = load(
            "g10_assess_unit",
            "scenarios/g8_soap_opera/g10_assess.py",
        )

    def test_aggregation_rejects_absent_actor(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(FileNotFoundError, "required actor"):
                self.assess.assess(Path(tmp))

    def test_aggregation_rejects_mock_as_real_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lin.json").write_text(json.dumps({
                "role": "lin", "engine": "fixture"
            }))
            with self.assertRaisesRegex(PermissionError, "wrong actor or mock"):
                self.assess.assess(root)

    def test_pinned_factor_cardinality(self):
        self.assertEqual(len(self.assess.ROLES), 6)
        self.assertEqual(len(self.assess.CASES), 6)
        self.assertEqual(len(self.assess.ORDERS), 3)
        self.assertEqual(6*6*3*2, 216)


@unittest.skipUnless(
    importlib.util.find_spec("concordia") is not None,
    "Native Concordia optional dependency not installed",
)
class G10NativeConcordiaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.battery = load(
            "g10_battery_unit",
            "scenarios/g8_soap_opera/g10_decider_battery.py",
        )

    def test_six_distinct_dilemmas_have_real_symbolic_goap_baselines(self):
        mod = self.battery
        self.assertEqual(len(mod.CASES), 6)
        self.assertEqual(len({c.key for c in mod.CASES}), 6)
        for case in mod.CASES:
            self.assertEqual(len(case.options), 5)
            self.assertIn(case.baseline, {o[0] for o in case.options})
            self.assertEqual(case.baseline, mod.goap_control(case))
            self.assertTrue(case.unsafe.issubset({o[0] for o in case.options}))
            self.assertFalse(case.baseline in case.unsafe)
            self.assertIn(case.kind, ("social", "ambiguous", "urgent"))
            self.assertIn("{counterpart}", case.dilemma)

    def test_full_counterbalanced_menu_is_semantically_stable(self):
        mod=self.battery
        self.assertEqual(set(mod.ORDERS), set(mod.PATTERNS))
        for case in mod.CASES:
            canonical = mod.ordered(case, "Mara", "canonical")
            expected = {(x.verb, x.target, x.label) for x in canonical}
            self.assertEqual(len(expected), 5)
            for pattern in mod.ORDERS:
                options = mod.ordered(case, "Mara", pattern)
                self.assertEqual(expected,
                                 {(x.verb, x.target, x.label) for x in options})
                self.assertEqual({o.target for o in options},
                                 {"g10."+case.key})
                self.assertTrue(all(o.verb.startswith("propose.") for o in options))
                self.assertEqual(len(set(o.verb for o in options)), 5)
            with self.assertRaises(ValueError):
                mod.ordered(case, "Mara", "nonexistent")
            self.assertNotEqual(
                tuple(x.verb for x in mod.ordered(case,"Mara","canonical")),
                tuple(x.verb for x in mod.ordered(case,"Mara","reverse")),
            )

    def test_archive_fails_closed_on_any_rewritten_world_evidence(self):
        mod=self.battery
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"state.json").write_text(
                '{"turn":205,"cognition_mode":"decider"}',
                encoding="utf-8"
            )
            (root/"g9-report.json").write_text('{"turns":205}')
            with self.assertRaisesRegex(PermissionError,"hash mismatch"):
                mod.authenticated_archive(root)
            (root/"lin.brain.json").write_text('{"identity":{}}')
            with self.assertRaisesRegex(PermissionError,"hash mismatch"):
                mod.actor_archive(root,"lin")
        with self.assertRaises(ValueError):
            mod.actor_archive(Path("."),"outsider")

    def test_fixture_native_agent_uses_the_offered_menu_only(self):
        from ox_ai.agents.crew import CrewAgent,CrewIdentity
        mod=self.battery
        trial=load("g10_g9trial_unit","scenarios/g8_soap_opera/live_trial.py")
        blueprint=trial.g9_blueprint("mara")
        agent=CrewAgent(
            CrewIdentity("ox.person."+blueprint.person_id,
                         "#111",blueprint.name,"Cargo duty","Care for crew"),
            mod.FixtureFirst(), blueprint=blueprint,
            initial_memories=trial.seeds_for("mara"),
            observation_history_length=8,
        )
        case=mod.CASES[0]
        for pattern in mod.ORDERS:
            offered=mod.ordered(case,"Lin Sato",pattern)
            request=agent.decide(offered, expected_revision=0)
            self.assertEqual(request.verb,offered[0].verb)
            self.assertEqual(request.target,"g10."+case.key)
            self.assertIn(request,agent.pending_requests)
        self.assertEqual(agent.usage.total_calls,3)
        self.assertEqual(len(agent.pending_requests),3)

    def test_router_probabilities_change_between_people_without_forced_error(self):
        from ox_ai.runtime.personality_routing import PersonalityRouter,PersonalState
        mod=self.battery
        trial=load("g10_g9trial_routes","scenarios/g8_soap_opera/live_trial.py")
        state=PersonalState(stress=.4,fatigue=.5,social_pressure=.8,uncertainty=.5)
        chances={}
        for i, role in enumerate(mod.ROLES):
            router=PersonalityRouter(
                trial.g9_blueprint(role),f"#{111+i}",{},
                seed="g10-policy-test-"+role
            )
            probability=router.probability(state,"social")
            self.assertGreaterEqual(probability,.02)
            self.assertLessEqual(probability,.9)
            observed=sum(router._draw(f"g10.test.{j:04}")<probability
                         for j in range(1024))/1024
            self.assertLess(abs(observed-probability),.12)
            chances[role]=probability
        self.assertGreater(chances["iona"],chances["ari"])
        self.assertGreater(chances["mara"],chances["teo"])

    def test_private_memory_projection_ablation_is_owner_local(self):
        from ox_ai.agents.crew import CrewAgent,CrewIdentity
        from ox_ai.memory.concordia_context import OxMemoryContext
        from types import SimpleNamespace
        mod=self.battery
        trial=load("g10_g9trial_memory","scenarios/g8_soap_opera/live_trial.py")
        blueprint=trial.g9_blueprint("mara")
        member=CrewAgent(
            CrewIdentity("ox.person."+blueprint.person_id,
                         "#121",blueprint.name,"Cargo","Truth"),
            mod.FixtureFirst(), blueprint=blueprint,
            initial_memories=trial.seeds_for("mara"),
        )
        option=mod.ordered(mod.CASES[2], "Lin Sato","canonical")
        text=OxMemoryContext(member).pre_act(
            SimpleNamespace(options=tuple(o.label for o in option)))
        self.assertIn("Private remembered context",text)
        self.assertIn("Lin",text)
        other=CrewAgent(
            CrewIdentity("ox.person."+blueprint.person_id,
                         "#121",blueprint.name,"Cargo","Truth"),
            mod.FixtureFirst(), blueprint=blueprint,
            initial_memories=trial.seeds_for("mara"),
            memory_projection_enabled=False,
        )
        hidden=OxMemoryContext(other).pre_act(
            SimpleNamespace(options=tuple(o.label for o in option)))
        self.assertEqual(hidden,"")
        self.assertEqual(len(other.temporal_memories),len(member.temporal_memories))


if __name__=="__main__":
    unittest.main()
