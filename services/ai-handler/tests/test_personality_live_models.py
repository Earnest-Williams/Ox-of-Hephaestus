"""Strict local model adapters and real incident coverage fixture contracts."""
from __future__ import annotations
import unittest

from ox_ai.inference.decider_gguf_choice import DeciderGGUFChoiceModel
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.runtime.personality_routing import PersonalityRouter, PersonalState
from ox_ai.scenarios.p4a_personality_gate import (
    _select_coverage_seed, _profile, CHOICES, STATE,
)


class FakeDecider:
    def __init__(self, invalid=False):
        self.requests=[]
        self.invalid=invalid
    def system_one(self,state,questions):
        self.requests.append((state,questions))
        crit=questions["next_action"]["criteria"]
        keys=list(crit)
        return {"answers":{"next_action":{
            "choice":"unoffered" if self.invalid else keys[-1],
            "probabilities":{k:(1. if k==keys[-1] else 0.) for k in keys},
        }}}


class AdapterBoundaryTests(unittest.TestCase):
    def test_scored_options_only_and_subjective_context_preserved(self):
        engine=FakeDecider()
        model=DeciderGGUFChoiceModel("not-read.gguf",tuple(o.label for o in CHOICES),
                                     engine=engine)
        index,label,meta=model.sample_choice(
            "Crew memory and personal experience: high anxiety",("a","b"),
        )
        self.assertEqual((index,label),(1,"b"))
        self.assertIn("high anxiety",engine.requests[0][0])
        self.assertEqual(list(engine.requests[0][1]["next_action"]["criteria"]),["a","b"])
        self.assertEqual(set(meta["decider_native_choice"]["probabilities"]),{"a","b"})
        with self.assertRaisesRegex(RuntimeError,"cannot generate text"):
            model.sample_text("Don't generate")

    def test_unoffered_decision_fails_closed(self):
        model=DeciderGGUFChoiceModel("not-read.gguf",
                                     tuple(o.label for o in CHOICES),
                                     engine=FakeDecider(invalid=True))
        with self.assertRaisesRegex(ValueError,"Invalid native"):
            model.sample_choice("state",("a","b"))
        with self.assertRaises(ValueError):
            model.sample_choice("state",("a","a"))

    def test_coverage_seeds_reproduce_both_deterministic_branches(self):
        for persona in ("methodical","independent"):
            profile=_profile(persona)
            for route in ("goap","llm"):
                boundary="incident.oxevt-12345.isolation"
                seed=_select_coverage_seed(profile,"#77",boundary,route)
                policy=PersonalityRouter(profile,"#77",{},seed=seed)
                p=policy.probability(STATE,"ambiguous")
                observed="llm" if policy._draw(boundary)<p else "goap"
                self.assertEqual(route,observed)


if __name__=="__main__":
    unittest.main()
