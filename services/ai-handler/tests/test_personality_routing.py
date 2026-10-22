"""Personality-led selection between real GOAP and bounded Concordia inference.

Integration here intentionally issues NO world actions. All proposals use the
existing ActionRequest contract; Evennia remains sole authority. Tests check
that route persistence precedes any inference or proposed action.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import unittest

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.planning.goap import GoapAction, GoapPlanner, PlanUnavailable
from ox_ai.ports.base import WorldObservation
from ox_ai.runtime.personality_routing import (
    CharacterRouteController, PersonalState, PersonalityRouter,
)
from ox_ai.runtime.cognition_scheduler import DecisionScheduler

try:
    from concordia.testing.mock_model import MockModel
except ImportError:
    MockModel = None


def blueprint(person_id="router.a", **overrides):
    return compose_blueprint(
        person_id, "Router Test Engineer",
        templates=("occupation.environmental_technician",),
        trait_overrides=overrides,
    )


def make_router(profile=None, *, record=None, seed="ox-routing-seed1",
                character_id="#71"):
    return PersonalityRouter(
        profile or blueprint(), character_id,
        {} if record is None else record, seed=seed,
    )


class RouterPersistenceTests(unittest.TestCase):
    def test_same_boundary_idempotent_after_checkpoint_and_restart(self):
        profile=blueprint("router.stable", conscientiousness=88, authority_challenge=25)
        record={}
        router=make_router(profile,record=record)
        checkpoints=[]
        state=PersonalState(stress=.2,uncertainty=.6)
        first=router.select(
            boundary_id="world.event-7.procedure",kind="ambiguous",state=state,
            observation_revision=4,cognition_revision=2,
            persist=lambda: checkpoints.append(deepcopy(record)),
        )
        self.assertEqual(len(checkpoints),1)
        same=router.select(
            boundary_id="world.event-7.procedure",kind="ambiguous",
            state=PersonalState(stress=1,fatigue=1,uncertainty=1),
            observation_revision=44,cognition_revision=22,
            persist=lambda: self.fail("Never write a new roll for replay"),
        )
        self.assertEqual(first,same)
        restored=make_router(profile,record=deepcopy(checkpoints[0]))
        self.assertEqual(
            first,
            restored.select(
                boundary_id="world.event-7.procedure",kind="ambiguous",
                state=state,observation_revision=4,cognition_revision=2,
                persist=lambda: self.fail("A replay cannot reroll"),
            ),
        )
        second=make_router(profile,record={}).select(
            boundary_id="world.event-7.procedure",kind="ambiguous",state=state,
            observation_revision=4,cognition_revision=2,persist=lambda: None,
        )
        self.assertEqual(first.roll,second.roll)
        with self.assertRaises(ValueError):
            restored.select(
                boundary_id="world.event-7.procedure",kind="social",state=state,
                observation_revision=4,cognition_revision=2,persist=lambda: None,
            )

    def test_personality_and_subjective_state_modify_llm_frequency(self):
        methodical=make_router(blueprint(
            "methodical",conscientiousness=95, risk_tolerance=15,
            authority_challenge=5, openness=30))
        impulsive=make_router(blueprint(
            "impulsive",conscientiousness=15, risk_tolerance=95,
            authority_challenge=95, openness=80))
        calm=PersonalState()
        distressed=PersonalState(stress=1,fatigue=1,uncertainty=1,
                                  social_pressure=1)
        self.assertLess(methodical.probability(calm,"routine"),
                        impulsive.probability(calm,"routine"))
        self.assertLess(methodical.probability(calm,"routine"),
                        methodical.probability(distressed,"social"))
        self.assertGreaterEqual(methodical.probability(calm,"routine"),.02)
        self.assertLessEqual(impulsive.probability(distressed,"social"),.9)

    def test_feedback_changes_future_routing_without_forging_world_effect(self):
        record={}
        profile=blueprint("feedback.test",authority_challenge=20)
        router=make_router(profile,record=record)
        router.select(
            boundary_id="world.job.1",kind="routine",state=PersonalState(),
            observation_revision=1,cognition_revision=0,persist=lambda: None,
        )
        before=router.probability(PersonalState(),"routine")
        observation=WorldObservation(
            "observation-2","#71",12.0,
            "The character perceived that the improvisation succeeded.",
            source_event_id="world.consequence.2",
        )
        saved=[]
        router.perceived_consequence(
            boundary_id="world.job.1",observation=observation,
            interpretation="success",persist=lambda: saved.append(deepcopy(record)),
        )
        self.assertEqual(len(saved),1)
        self.assertGreater(router.probability(PersonalState(),"routine"),before)
        router.perceived_consequence(
            boundary_id="world.job.1",observation=observation,
            interpretation="success",persist=lambda: self.fail("No duplicate feedback"),
        )
        self.assertEqual(len(saved),1)
        with self.assertRaises(ValueError):
            router.perceived_consequence(
                boundary_id="world.job.1",observation=observation,
                interpretation="failure",persist=lambda: None,
            )
        with self.assertRaises(PermissionError):
            router.perceived_consequence(
                boundary_id="world.job.1",
                observation=WorldObservation(
                    "wrong-agent","#72",12.0,"I thought it worked.",
                    source_event_id="world.consequence.3",
                ),
                interpretation="success",persist=lambda: None,
            )
        self.assertEqual(router.record["reliance_basis_points"],350)
        recovered=make_router(profile,record=deepcopy(saved[0]))
        self.assertEqual(recovered.record["reliance_basis_points"],350)

    def test_checkpoint_failure_rolls_back_personal_state(self):
        record={}
        r=make_router(record=record)
        def fail():
            raise OSError("disk unavailable")
        with self.assertRaises(OSError):
            r.select(
                boundary_id="world.event1",kind="routine",state=PersonalState(),
                observation_revision=0,cognition_revision=0,persist=fail,
            )
        self.assertEqual(record["boundaries"],{})
        r.select(boundary_id="world.event1",kind="routine",state=PersonalState(),
                 observation_revision=0,cognition_revision=0,persist=lambda: None)
        with self.assertRaises(OSError):
            r.perceived_consequence(
                boundary_id="world.event1",
                observation=WorldObservation(
                    "seen","#71",4.0,"Consequences were observed.",
                    source_event_id="world.event2",
                ),
                interpretation="success",persist=fail,
            )
        self.assertEqual(record["feedback"],{})
        self.assertEqual(record["reliance_basis_points"],0)

    def test_cross_actor_or_altered_profile_cannot_resume(self):
        record={}
        p=blueprint("stable.id")
        make_router(p,record=record)
        for args in (
            dict(profile=blueprint("different.id")),
            dict(profile=p,character_id="#72"),
            dict(profile=p,seed="different.seed.44"),
            dict(profile=blueprint("stable.id",risk_tolerance=99)),
        ):
            with self.subTest(args=args),self.assertRaises(PermissionError):
                make_router(record=deepcopy(record),**args)

    def test_invalid_state_and_corrupt_route_are_rejected(self):
        for kwargs in (
            {"stress":float("nan")},{"fatigue":-0.1},
            {"uncertainty":1.001},{"social_pressure":True},
        ):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                PersonalState(**kwargs)
        r=make_router()
        with self.assertRaises(ValueError):
            r.select(boundary_id="../unsafe",kind="routine",state=PersonalState(),
                     observation_revision=0,cognition_revision=0,
                     persist=lambda: None)
        record=deepcopy(r.record)
        record["boundaries"]["world.event"]={"selected":"really_llm"}
        with self.assertRaises(ValueError):
            make_router(record=record)


@unittest.skipIf(MockModel is None,"Native Concordia optional extra not installed")
class RealConcordiaRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.profile=blueprint(
            "live.router",conscientiousness=60,authority_challenge=80,
            neuroticism=65,risk_tolerance=70,
        )
        self.record={}
        self.router=make_router(self.profile,record=self.record)
        self.model=SpyChoiceModel()
        self.agent=CrewAgent(
            CrewIdentity("ox.person.live.router","#71","Router Test Engineer",
                         "Diagnose safely","Keep equipment serviceable"),
            self.model,blueprint=self.profile,
        )
        self.scheduler=DecisionScheduler(max_parallel=1,timeout_seconds=10)
        self.controller=CharacterRouteController(
            self.router,self.scheduler,role="engineering",
        )
        self.plan=GoapPlanner((
            GoapAction("inspect_gauge",frozenset({"at_engineering"}),
                       frozenset({"observed"}),verb="inspect",target="gauge"),
        ))
        self.options=(
            CommandOption("Follow procedure: inspect gauge","inspect","gauge"),
            CommandOption("Make a personal judgement and defer","defer"),
        )
        self.persisted=[]

    def _boundary(self, want):
        probability=self.router.probability(PersonalState(),"routine")
        for i in range(200):
            name=f"world.event.{i}"
            r=self.router._draw(name)
            if (r<probability)==(want=="llm"):
                return name
        self.fail("Unable to find deterministic route fixture")

    def _persist(self):
        self.persisted.append(deepcopy(self.record))

    async def test_goap_does_real_symbolic_plan_with_zero_inference(self):
        decision=await self.controller.decide(
            agent=self.agent,planner=self.plan,
            beliefs=frozenset({"at_engineering"}),
            goals=frozenset({"observed"}),
            options=self.options,boundary_id=self._boundary("goap"),
            kind="routine",state=PersonalState(),persist=self._persist,
        )
        self.assertEqual(decision.route.selected,"goap")
        self.assertEqual(decision.goap_action,"inspect_gauge")
        self.assertEqual(decision.action.verb,"inspect")
        self.assertEqual(decision.model_calls,0)
        self.assertEqual(self.agent.usage.total_calls,0)
        self.assertFalse(self.agent.pending_requests)
        self.assertEqual(len(self.persisted),1)

    async def test_llm_can_choose_deviation_without_being_told_to_fail(self):
        decision=await self.controller.decide(
            agent=self.agent,planner=self.plan,
            beliefs=frozenset({"at_engineering"}),
            goals=frozenset({"observed"}),
            options=self.options,boundary_id=self._boundary("llm"),
            kind="routine",
            state=PersonalState(stress=.8,social_pressure=.4),
            persist=self._persist,
        )
        self.assertEqual(decision.route.selected,"llm")
        self.assertEqual(decision.action.verb,"defer")
        self.assertEqual(decision.model_calls,1)
        self.assertEqual(len(self.model.prompts),1)
        prompt=self.model.prompts[0]
        self.assertIn("Characterisation",prompt)
        self.assertIn("stress=0.80",prompt)
        self.assertIn("social_pressure=0.40",prompt)
        self.assertIn("Make a personal judgement and defer",prompt)
        self.assertIn(decision.action,self.agent.pending_requests)
        self.assertEqual(len(self.persisted),1)
        # The subjective decision is a proposal; nothing executed.
        self.assertEqual(self.scheduler.metrics["started"],1)

    async def test_llm_failure_never_silently_converts_into_goap(self):
        failing=FailingChoiceModel()
        agent=CrewAgent(self.agent.identity,failing,blueprint=self.profile)
        controller=CharacterRouteController(
            self.router,DecisionScheduler(timeout_seconds=10),
            role="engineering",
        )
        with self.assertRaisesRegex(Exception,"Inference failed"):
            await controller.decide(
                agent=agent,planner=self.plan,
                beliefs=frozenset({"at_engineering"}),
                goals=frozenset({"observed"}),
                options=self.options,boundary_id=self._boundary("llm"),
                kind="routine",state=PersonalState(),persist=self._persist,
            )
        self.assertFalse(agent.pending_requests)
        self.assertEqual(len(self.persisted),1)

    async def test_planner_cannot_use_unoffered_action_or_infer_fallback(self):
        with self.assertRaises(PlanUnavailable):
            await self.controller.decide(
                agent=self.agent,planner=self.plan,
                beliefs=frozenset({"at_engineering"}),
                goals=frozenset({"observed"}),
                options=(CommandOption("Defer","defer"),
                         CommandOption("Ask colleague","ask")),
                boundary_id=self._boundary("goap"),
                kind="routine",state=PersonalState(),persist=self._persist,
            )
        self.assertEqual(self.agent.usage.total_calls,0)

    async def test_cross_person_or_unmatched_blueprint_is_denied(self):
        other=CrewAgent(
            CrewIdentity("ox.person.other","#72","Other","Other","Other"),
            SpyChoiceModel(),blueprint=blueprint("other"),
        )
        with self.assertRaises(PermissionError):
            await self.controller.decide(
                agent=other,planner=self.plan,
                beliefs=frozenset({"at_engineering"}),
                goals=frozenset({"observed"}),
                options=self.options,boundary_id="world.other",
                kind="routine",state=PersonalState(),persist=self._persist,
            )
        self.assertFalse(self.persisted)


class SpyChoiceModel:
    def __init__(self):
        self.prompts=[]
    def sample_choice(self,prompt,responses,*,seed=None):
        self.prompts.append(prompt)
        return len(responses)-1, responses[-1], {}
    def sample_text(self,*args,**kwargs):
        raise AssertionError("Choice model must not generate text")


class FailingChoiceModel:
    def sample_choice(self,prompt,responses,*,seed=None):
        raise RuntimeError("SENSITIVE PROMPT CONTENT")
    def sample_text(self,*args,**kwargs):
        raise AssertionError("Choice model must not generate text")


if __name__=="__main__":
    unittest.main()
