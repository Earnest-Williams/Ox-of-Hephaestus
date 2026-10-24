"""G16d: real symbolic search under authored character dispositions."""
from __future__ import annotations

import math
import unittest
from dataclasses import replace

from ox_ai.agents.crew import CommandOption
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.planning.goap import GoapAction, GoapPlanner, PlanUnavailable
from ox_ai.runtime.disposition_goap import (
    actor_dispositions, personality_goap_costs,
)
from ox_contracts import load_catalog


class WeightedGoapTests(unittest.TestCase):
    def setUp(self):
        self.menu = load_catalog().menu("g14.verified_mutual_aid")
        self.offered = tuple(
            CommandOption(action.semantic_key, action.verb, action.target)
            for action in self.menu.options
        )
        self.actions = tuple(
            GoapAction(
                action.semantic_key,
                frozenset({"offer_active"}),
                frozenset({"decision_made"}),
                verb=action.verb, target=action.target,
                cost=1.0,
            ) for action in self.menu.options
        )
        self.planner = GoapPlanner(self.actions)
        self.procedural = compose_blueprint(
            "g16d.procedural", "Procedural",
            trait_overrides={
                "conscientiousness": 95, "risk_tolerance": 15,
                "authority_challenge": 10, "collaboration": 95,
                "agreeableness": 90,
            },
        )
        self.independent = compose_blueprint(
            "g16d.independent", "Independent",
            trait_overrides={
                "conscientiousness": 20, "risk_tolerance": 90,
                "authority_challenge": 95, "collaboration": 15,
                "agreeableness": 20,
            },
        )

    def _choice(self, profile):
        prices = personality_goap_costs(
            self.planner, self.menu, profile, offered=self.offered,
        )
        self.assertEqual(set(prices), {x.name for x in self.actions})
        self.assertTrue(all(0.5 <= x <= 2.0 for x in prices.values()))
        p = self.planner.plan(
            {"offer_active"}, {"decision_made"}, cost_overrides=prices,
        )
        self.assertEqual(len(p.actions), 1)
        self.assertAlmostEqual(p.total_cost, prices[p.actions[0].name])
        return p.actions[0].name, prices

    def test_same_beliefs_goals_and_operator_model_different_habits(self):
        proc_action, proc_costs = self._choice(self.procedural)
        indep_action, indep_costs = self._choice(self.independent)
        self.assertEqual(proc_action, "accept_help")
        self.assertEqual(indep_action, "work_alone")
        self.assertNotEqual(proc_costs, indep_costs)
        for _ in range(10):
            self.assertEqual(proc_action, self._choice(self.procedural)[0])
            self.assertEqual(indep_action, self._choice(self.independent)[0])
        # Costs are never written back to shared operator templates.
        self.assertTrue(all(x.cost == 1.0 for x in self.planner.actions))

    def test_zero_model_calls_and_no_world_access_required(self):
        original = self.planner.plan({"offer_active"}, {"decision_made"})
        self.assertEqual(original.actions[0], self.planner.actions[0])
        self.assertEqual(original.total_cost, 1.0)
        self.assertEqual(actor_dispositions(self.procedural)["procedure"], 0.9)
        self.assertGreater(
            actor_dispositions(self.independent)["autonomy"],
            actor_dispositions(self.procedural)["autonomy"],
        )

    def test_exact_cost_override_contract(self):
        args = ({"offer_active"}, {"decision_made"})
        names = {x.name for x in self.actions}
        for bad in (
            {"accept_help": 0.5},
            dict.fromkeys(names | {"not_a_real_action"}, 1.0),
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.planner.plan(*args, cost_overrides=bad)
        for invalid in (-0.5, 0, float("nan"), float("inf"), True, "1.2"):
            overrides = dict.fromkeys(names, 1.0)
            overrides["accept_help"] = invalid
            with self.subTest(invalid=repr(invalid)), self.assertRaises(ValueError):
                self.planner.plan(*args, cost_overrides=overrides)

    def test_costs_are_positive_finite_and_deterministically_ordered(self):
        for invalid in (False, float("nan"), float("inf"), -1, 0, "1.0"):
            with self.subTest(invalid=repr(invalid)), self.assertRaises(ValueError):
                GoapAction(
                    "bad", frozenset(), frozenset({"x"}),
                    cost=invalid, verb="test",
                )
        # Stable insertion-order tie-break, even with fractional costs.
        costs = dict.fromkeys((x.name for x in self.actions), 0.75)
        self.assertEqual(
            self.planner.plan({"offer_active"}, {"decision_made"},
                              cost_overrides=costs).actions[0].name,
            self.actions[0].name,
        )
        self.assertEqual(
            self.planner.plan({"offer_active"}, {"decision_made"},
                              excluded={"accept_help"}, cost_overrides=costs).actions[0].name,
            self.actions[1].name,
        )

    def test_untagged_planner_step_and_changed_offer_fail_closed(self):
        extra = GoapAction("unmapped_operator", frozenset({"offer_active"}),
                           frozenset({"decision_made"}), verb="other")
        with self.assertRaises(ValueError):
            personality_goap_costs(
                GoapPlanner((*self.actions, extra)),
                self.menu, self.procedural, offered=self.offered,
            )
        with self.assertRaises(ValueError):
            personality_goap_costs(
                self.planner, self.menu, self.procedural,
                offered=self.offered[:2],
            )
        with self.assertRaises(ValueError):
            personality_goap_costs(
                self.planner, self.menu, self.procedural,
                offered=(*self.offered, self.offered[0]),
            )

    def test_safety_critical_menu_cannot_be_personality_weighted(self):
        critical = load_catalog().menu("g14.finite_spare_dispute")
        with self.assertRaises(PermissionError):
            personality_goap_costs(
                self.planner, critical, self.procedural, offered=self.offered,
            )

    def test_invalid_gain_and_missing_personality_fail_closed(self):
        for k in (-1.0, 0, 3.0, float("nan"), float("inf"), True):
            with self.subTest(k=k), self.assertRaises(ValueError):
                personality_goap_costs(
                    self.planner, self.menu, self.procedural,
                    offered=self.offered, k=k,
                )
        with self.assertRaises(TypeError):
            actor_dispositions(object())


if __name__ == "__main__":
    unittest.main()
