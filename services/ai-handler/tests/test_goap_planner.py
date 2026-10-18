"""Stdlib-only GOAP tests: planning, costs, and unavailable goals."""

import unittest

from ox_ai.planning.goap import GoapAction, GoapPlanner, PlanUnavailable


def act(name, pre=(), adds=(), removes=(), *, cost=1):
    return GoapAction(
        name=name, requires=frozenset(pre), adds=frozenset(adds),
        removes=frozenset(removes), cost=cost, verb=name,
    )


class GoapPlannerTests(unittest.TestCase):
    def test_chooses_cheapest_multi_step_plan_not_first_available_action(self):
        planner = GoapPlanner((
            act("expensive_jump", {"start"}, {"goal"}, cost=9),
            act("walk", {"start"}, {"mid"}, {"start"}),
            act("climb", {"mid"}, {"goal"}),
        ))
        plan = planner.plan({"start"}, {"goal"})
        self.assertEqual([a.name for a in plan.actions], ["walk", "climb"])
        self.assertEqual(plan.total_cost, 2)
        self.assertGreater(plan.expanded_states, 0)

    def test_preconditions_are_enforced_and_tools_can_be_planned(self):
        planner = GoapPlanner((
            act("repair", {"at_pump", "has_tool"}, {"fixed"}),
            act("get_tool", {"at_locker"}, {"has_tool"}),
            act("go_locker", {"at_pump"}, {"at_locker"}, {"at_pump"}),
            act("return_to_pump", {"at_locker"}, {"at_pump"}, {"at_locker"}),
        ))
        result = planner.plan({"at_pump"}, {"fixed"})
        self.assertEqual(
            [a.name for a in result.actions],
            ["go_locker", "get_tool", "return_to_pump", "repair"],
        )
        self.assertEqual(result.total_cost, 4)

    def test_goal_already_met_requires_no_actions(self):
        result = GoapPlanner((act("x", {"start"}, {"done"}),)).plan(
            {"start", "done"}, {"done"}
        )
        self.assertEqual(result.actions, ())
        self.assertEqual(result.total_cost, 0)

    def test_no_plan_does_not_improvise_illegal_action(self):
        planner = GoapPlanner((act("fix", {"missing_part"}, {"done"}),))
        with self.assertRaises(PlanUnavailable):
            planner.plan({"at_pump"}, {"done"})

    def test_excluded_failed_operator_prevents_blind_retry(self):
        planner = GoapPlanner((act("fix", {"ready"}, {"done"}),))
        with self.assertRaises(PlanUnavailable):
            planner.plan({"ready"}, {"done"}, excluded={"fix"})

    def test_search_expansion_budget_is_bounded(self):
        planner = GoapPlanner((
            act("one", {"start"}, {"p"}),
            act("two", {"p"}, {"q"}),
            act("three", {"q"}, {"end"}),
        ), expansion_cap=1)
        with self.assertRaisesRegex(PlanUnavailable, "budget"):
            planner.plan({"start"}, {"end"})

    def test_invalid_action_models_rejected(self):
        with self.assertRaises(ValueError):
            GoapAction(
                "impossible", frozenset(), frozenset({"x"}),
                frozenset({"x"}), verb="impossible",
            )
        with self.assertRaises(ValueError):
            GoapPlanner((act("x"), act("x")))


if __name__ == "__main__":
    unittest.main()
