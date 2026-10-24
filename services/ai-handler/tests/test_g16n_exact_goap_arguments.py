"""G16n: argument-bearing GOAP commands retain full world-grounded signatures.

These are synthetic actor/offline-planning examples. The actual P4k forty
crew work round still needs an independently authored, G16a-tagged and
world-authorised live menu before any personality controller is enabled.
"""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from unittest import mock
import unittest

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.runtime.cognition_scheduler import DecisionScheduler
from ox_ai.runtime.disposition_goap import personality_goap_costs
from ox_ai.runtime.personality_routing import (
    CharacterRouteController, PersonalState, PersonalityRouter,
)

try:
    from ox_contracts import (
        ActionTagCatalog, DispositionTags, TaggedAction, TaggedMenu,
    )
except ImportError:
    ActionTagCatalog = DispositionTags = TaggedAction = TaggedMenu = None


class ForbiddenModel:
    def sample_choice(self,*args,**kwargs):
        raise AssertionError("GOAP must not consult or generate model results")
    def sample_text(self,*args,**kwargs):
        raise AssertionError("GOAP cannot generate dialogue")


@unittest.skipUnless(
    ActionTagCatalog is not None,
    "Strict Pydantic G16a action contracts optional in minimal scaffold install",
)
class ArgumentGroundedGoapTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        zero = DispositionTags(
            risk=0.0,deference=0.0,social=0.0,
            autonomy=0.0,procedure=0.0,
        )
        self.menu = TaggedMenu(
            menu_key="offline.argumented_world_probe",
            scope="offline_trial",
            safety_critical=False,
            options=(
                TaggedAction(
                    semantic_key="cargo_round",verb="round_report",
                    target="ship",arguments=(("station","cargo"),),
                    tags=zero,
                ),
                TaggedAction(
                    semantic_key="pump_round",verb="round_report",
                    target="ship",arguments=(("station","pump"),),
                    tags=zero,
                ),
                TaggedAction(
                    semantic_key="defer",verb="defer",
                    target=None,arguments=(),tags=zero,
                ),
            ),
        )
        self.catalog=ActionTagCatalog(schema_version=1,menus=(self.menu,))
        self.offered=(
            CommandOption("File cargo station round","round_report","ship",
                          {"station":"cargo"}),
            CommandOption("File pump station round","round_report","ship",
                          {"station":"pump"}),
            CommandOption("Defer this review","defer"),
        )
        self.planner=GoapPlanner((
            GoapAction("cargo_round",requires=frozenset({"inspected"}),
                       adds=frozenset({"round_reviewed"}),cost=.1,
                       verb="round_report",target="ship",
                       arguments=(("station","cargo"),)),
            GoapAction("pump_round",requires=frozenset({"inspected"}),
                       adds=frozenset({"round_reviewed"}),cost=100,
                       verb="round_report",target="ship",
                       arguments=(("station","pump"),)),
            GoapAction("defer",requires=frozenset({"inspected"}),
                       adds=frozenset({"round_reviewed"}),cost=100,
                       verb="defer"),
        ))
        self.state=PersonalState(
            stress=.5,fatigue=.3,social_pressure=.2,uncertainty=.3,
        )
        self.profile=compose_blueprint(
            "g16n.test.technician","G16n Technician",
            trait_overrides={"conscientiousness":85,
                             "authority_challenge":30},
        )

    def routed_goap(self):
        boundary="g16n.original.world.event"
        seed=None
        for i in range(5000):
            candidate="g16n-goap-test-seed-"+str(i)
            trial=PersonalityRouter(self.profile,"#301",{},seed=candidate)
            if trial._draw(boundary)>=trial.probability(self.state,"routine"):
                seed=candidate
                break
        self.assertIsNotNone(seed)
        router=PersonalityRouter(self.profile,"#301",{},seed=seed)
        brain=CrewAgent(
            CrewIdentity("ox.person."+self.profile.person_id,"#301",
                         "G16n Technician","Inspect observed station",
                         "Consider a permitted local report"),
            ForbiddenModel(),blueprint=self.profile,
        )
        ctrl=CharacterRouteController(
            router,DecisionScheduler(max_parallel=1,
                                     per_actor_budget=16,total_budget=16),
            role="g16n.technician",
        )
        saves=[]
        def persist():
            saves.append(deepcopy(router.record))
        return boundary,router,brain,ctrl,persist,saves

    async def test_exact_args_survive_opt_in_goap_and_restart_replay(self):
        boundary,router,brain,ctrl,persist,saves=self.routed_goap()
        with (mock.patch.dict("os.environ",{"OX_PERSONALITY_CHOICE":"1"}),
              mock.patch("ox_contracts.load_catalog",return_value=self.catalog)):
            original=await ctrl.decide(
                agent=brain,planner=self.planner,
                beliefs=frozenset({"inspected"}),
                goals=frozenset({"round_reviewed"}),
                options=self.offered,boundary_id=boundary,
                kind="routine",state=self.state,
                menu_key=self.menu.menu_key,persist=persist,
            )
            self.assertEqual(original.route.selected,"goap")
            self.assertEqual(original.model_calls,0)
            self.assertEqual(original.action.verb,"round_report")
            self.assertEqual(original.action.target,"ship")
            self.assertEqual(original.action.arguments,{"station":"cargo"})
            self.assertEqual(len(brain.pending_requests),0)
            self.assertEqual(len(saves),2)
            self.assertEqual(
                router.record["personality_choices"][boundary]["selected_semantic_key"],
                "cargo_round",
            )
            recorded=deepcopy(router.record)
            follow=await ctrl.decide(
                agent=brain,planner=self.planner,
                beliefs=frozenset({"inspected"}),
                goals=frozenset({"round_reviewed"}),
                options=tuple(reversed(self.offered)),boundary_id=boundary,
                kind="routine",state=self.state,
                menu_key=self.menu.menu_key,
                persist=lambda:self.fail("Ledger replay cannot repersist"),
            )
            self.assertEqual(follow.action,original.action)
            self.assertEqual(router.record,recorded)

    async def test_mismatch_command_arguments_fail_before_any_ledger_is_written(self):
        boundary,router,brain,ctrl,persist,saves=self.routed_goap()
        mismatched=(
            CommandOption("File cargo station round","round_report","ship",
                          {"station":"scrubber"}),
            *self.offered[1:],
        )
        with (mock.patch.dict("os.environ",{"OX_PERSONALITY_CHOICE":"1"}),
              mock.patch("ox_contracts.load_catalog",return_value=self.catalog)):
            with self.assertRaises(ValueError):
                await ctrl.decide(
                    agent=brain,planner=self.planner,
                    beliefs=frozenset({"inspected"}),
                    goals=frozenset({"round_reviewed"}),
                    options=mismatched,boundary_id=boundary,
                    kind="routine",state=self.state,
                    menu_key=self.menu.menu_key,persist=persist,
                )
        self.assertFalse(saves)
        self.assertEqual(router.record["boundaries"],{})
        self.assertFalse(brain.pending_requests)

    async def test_authored_exact_argument_tags_price_only_matching_operators(self):
        prices=personality_goap_costs(
            self.planner,self.menu,self.profile,offered=self.offered,
        )
        self.assertEqual(set(prices),{"cargo_round","pump_round","defer"})
        self.assertAlmostEqual(prices["cargo_round"],.1)
        self.assertAlmostEqual(prices["pump_round"],100)
        changed=GoapPlanner((
            GoapAction(
                "cargo_round",requires=frozenset({"inspected"}),
                adds=frozenset({"round_reviewed"}),cost=.1,
                verb="round_report",target="ship",
                arguments=(("station","scrubber"),),
            ),*self.planner.actions[1:],
        ))
        with self.assertRaisesRegex(ValueError,"Untagged"):
            personality_goap_costs(
                changed,self.menu,self.profile,offered=self.offered,
            )

    async def test_replay_rejects_rebound_operator_argument(self):
        boundary,router,brain,ctrl,persist,saves=self.routed_goap()
        with (mock.patch.dict("os.environ",{"OX_PERSONALITY_CHOICE":"1"}),
              mock.patch("ox_contracts.load_catalog",return_value=self.catalog)):
            first=await ctrl.decide(
                agent=brain,planner=self.planner,
                beliefs=frozenset({"inspected"}),
                goals=frozenset({"round_reviewed"}),
                options=self.offered,boundary_id=boundary,
                kind="routine",state=self.state,
                menu_key=self.menu.menu_key,persist=persist,
            )
            other=GoapPlanner((
                GoapAction(
                    "cargo_round",requires=frozenset({"inspected"}),
                    adds=frozenset({"round_reviewed"}),cost=.1,
                    verb="round_report",target="ship",
                    arguments=(("station","scrubber"),),
                ),*self.planner.actions[1:],
            ))
            with self.assertRaisesRegex(PermissionError,"persisted GOAP"):
                await ctrl.decide(
                    agent=brain,planner=other,
                    beliefs=frozenset({"inspected"}),
                    goals=frozenset({"round_reviewed"}),
                    options=self.offered,boundary_id=boundary,
                    kind="routine",state=self.state,
                    menu_key=self.menu.menu_key,
                    persist=lambda:self.fail("Rebound replay cannot persist"),
                )
            self.assertEqual(first.action.arguments,{"station":"cargo"})

    async def test_legacy_goap_matches_arguments_instead_of_arbitrary_same_verb(self):
        boundary,router,brain,ctrl,persist,saves=self.routed_goap()
        with mock.patch.dict("os.environ",{"OX_PERSONALITY_CHOICE":"0"}):
            chosen=await ctrl.decide(
                agent=brain,planner=self.planner,
                beliefs=frozenset({"inspected"}),
                goals=frozenset({"round_reviewed"}),
                options=tuple(reversed(self.offered)),boundary_id=boundary,
                kind="routine",state=self.state,persist=persist,
            )
        self.assertEqual(chosen.route.selected,"goap")
        self.assertEqual(chosen.action.arguments,{"station":"cargo"})
        self.assertEqual(chosen.action.verb,"round_report")

    def test_reject_noncanonical_or_mutable_grounded_operator_arguments(self):
        base=dict(name="round",verb="round_report",target="ship")
        for args in (
            {"station":"cargo"},(("station","cargo"),("station","pump")),
            (("station",5),), (("", "cargo"),),
            (("z","z"),("a","a")),
        ):
            with self.subTest(args=args),self.assertRaises(ValueError):
                GoapAction(**base,arguments=args)
        self.assertEqual(
            GoapAction(**base,arguments=(("station","cargo"),)).arguments,
            (("station","cargo"),),
        )


if __name__=="__main__":
    unittest.main()
