"""G16l: opt-in safety controller *integration* with SYNTHETIC System One scores.

G16e's 936 real forwards had zero native safety scores >=0.85. This test
exercises both branches of the immutable safety policy through genuine
Concordia actor shadow inference, bounded scheduling, durable ledgers and
replay. These are deterministic fixture probabilities, NEVER claims that
a native model is calibrated, safe, or approved to execute world work.
"""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from unittest import mock
import unittest

from ox_ai.agents.crew import CommandOption
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.runtime.cognition_scheduler import CognitionUnavailable, DecisionScheduler
from ox_ai.runtime.personality_choice_ledger import PersonalityChoiceLedger
from ox_ai.runtime.personality_routing import (
    CharacterRouteController, PersonalState, PersonalityRouter,
)

try:
    from ox_contracts import load_catalog
    from ox_ai.agents.crew import CrewAgent, CrewIdentity
    from concordia.testing.mock_model import MockModel
except ImportError:
    load_catalog = CrewAgent = CrewIdentity = MockModel = None


class DeterministicHighOrWeakSystemOne:
    """No GGUF, no actual model calibration or permission reasoning."""

    def __init__(self, target: str, *, high: bool):
        self.target = target
        self.high = high
        self.calls = 0

    def system_one(self, prompt: str, questions: dict) -> dict:
        self.calls += 1
        options = questions["next_action"]["criteria"]
        if (not isinstance(prompt, str) or not prompt
                or not isinstance(options, dict) or len(options) != 3):
            raise ValueError("Missing finite original actor prompt")
        scores = {}
        for code, label in options.items():
            key = next((key for key in (
                "reserve_spare", "support_loan", "seek_review"
            ) if key in label), None)
            if key is None:
                raise ValueError("Unrecognized tagged safety action")
            # Explicitly define SEMANTIC score, not output-letter score.
            if self.high:
                scores[code] = 0.96 if key == self.target else 0.02
            else:
                scores[code] = {"reserve_spare": .34, "support_loan": .33,
                                "seek_review": .33}[key]
        best = max(scores.values())
        selected = next(code for code in options
                        if scores[code] >= best - 1e-9)
        return {"answers": {"next_action": {
            "choice": selected, "probabilities": scores,
        }}}


class ForbiddenLegacyModel:
    def sample_choice(self, *a, **kw):
        raise AssertionError("Tagged G16c opt-in must not consult untagged LLM")
    def sample_text(self, *a, **kw):
        raise AssertionError("G16c does not generate speech")


@unittest.skipUnless(
    load_catalog is not None and MockModel is not None,
    "Typed catalog and real Concordia actor integration are optional",
)
class G16lSafetyControllerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.menu = load_catalog().menu("g14.finite_spare_dispute")
        self.assertTrue(self.menu.safety_critical)
        self.assertEqual(self.menu.scope, "hypothetical")
        self.actions = tuple(
            CommandOption("Act: " + a.semantic_key, a.verb, a.target)
            for a in self.menu.options
        )
        self.planner = GoapPlanner(tuple(
            GoapAction(a.semantic_key,
                       requires=frozenset({"offered"}),
                       adds=frozenset({"reviewed"}),
                       verb=a.verb, target=a.target)
            for a in self.menu.options
        ))
        self.boundary = "world.g16l.critical.001"
        self.state = PersonalState(
            stress=.8, fatigue=.2, social_pressure=.2, uncertainty=.75,
        )

    def _setup(self, *, independent: bool, selected: str,
               seed: str | None = None, target="reserve_spare",
               high=True):
        traits = (
            {"conscientiousness": 15, "risk_tolerance": 96,
             "authority_challenge": 96, "collaboration": 15,
             "agreeableness": 15}
            if independent else
            {"conscientiousness": 98, "risk_tolerance": 5,
             "authority_challenge": 5, "collaboration": 90,
             "agreeableness": 90}
        )
        profile = compose_blueprint(
            "g16l."+("independent" if independent else "procedural"),
            "G16l Safety Watch", trait_overrides=traits,
        )
        if seed is None:
            for n in range(10000):
                candidate = "g16l-original-actor-seed-"+str(n)
                temporary = PersonalityRouter(
                    profile, "#301", {}, seed=candidate,
                )
                choice = ("llm" if temporary._draw(self.boundary) <
                          temporary.probability(self.state, "urgent") else "goap")
                if choice == selected:
                    seed = candidate
                    break
            else:
                self.fail("Could not generate repeatable desired route")
        router = PersonalityRouter(profile, "#301", {}, seed=seed)
        agent = CrewAgent(
            CrewIdentity("ox.person."+profile.person_id, "#301",
                         profile.name, "Safety technician",
                         "Consider precisely the verified local offer"),
            ForbiddenLegacyModel(), blueprint=profile,
        )
        engine = DeterministicHighOrWeakSystemOne(target, high=high)
        control = CharacterRouteController(
            router, DecisionScheduler(
                max_parallel=1, timeout_seconds=4,
                total_budget=16, per_actor_budget=16,
            ),
            role="g16l.actor", decider_engine=engine,
        )
        saved = []

        def checkpoint():
            saved.append((deepcopy(router.record),len(agent.pending_requests)))

        return agent, router, engine, control, checkpoint, saved

    async def _decide(self, agent, ctrl, checkpoint, offered=None):
        with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
            return await ctrl.decide(
                agent=agent, planner=self.planner,
                beliefs=frozenset({"offered"}),
                goals=frozenset({"reviewed"}),
                options=offered or self.actions,
                boundary_id=self.boundary, kind="urgent",
                state=self.state, menu_key=self.menu.menu_key,
                persist=checkpoint,
            )

    async def test_positive_safety_lock_no_shift_and_durable_replay_for_both_personas(self):
        for independent in (False, True):
            with self.subTest(independent=independent):
                agent, router, engine, ctrl, cp, saves = self._setup(
                    independent=independent, selected="llm",
                )
                first = await self._decide(agent, ctrl, cp)
                self.assertEqual(first.route.selected, "llm")
                self.assertEqual(first.model_calls, 3)
                self.assertEqual(engine.calls, 3)
                self.assertEqual(len(saves), 2)
                self.assertEqual([n for _, n in saves], [0, 0])
                entry = router.record["personality_choices"][self.boundary]
                choices = entry["choice"]
                self.assertTrue(choices["safety_locked"])
                self.assertEqual(choices["native_winner"], "reserve_spare")
                self.assertEqual(choices["selected_semantic_key"], "reserve_spare")
                self.assertEqual(choices["adjusted_scores"]["reserve_spare"], 1.0)
                self.assertTrue(all(shift == 0.0 for shift in choices["shifts"].values()))
                self.assertEqual(choices["underlying_native_calls"], 3)
                self.assertEqual(len(choices["balanced_native_picks"]), 3)
                self.assertEqual(
                    entry["request_id"], first.action.request_id,
                )
                self.assertEqual(
                    self.menu.by_command(first.action.verb,
                                         first.action.target).semantic_key,
                    "reserve_spare",
                )
                self.assertEqual(len(agent.pending_requests), 1)
                replay = await self._decide(
                    agent, ctrl, lambda: self.fail("Replayed lock cannot reroll")
                )
                self.assertEqual(replay.action, first.action)
                self.assertEqual(replay.model_calls, 0)
                self.assertEqual(engine.calls, 3)

    async def test_positive_safety_lock_is_invariant_to_caller_action_order(self):
        results = []
        agent0, router0, eng0, ctrl0, cp0, snapshots0 = self._setup(
            independent=True, selected="llm")
        seed = router0.record["seed"]
        for offered in (self.actions,
                        self.actions[1:]+self.actions[:1],
                        tuple(reversed(self.actions))):
            agent, router, engine, ctrl, cp, _ = self._setup(
                independent=True, selected="llm", seed=seed)
            chosen = await self._decide(agent, ctrl, cp, offered)
            entry = router.record["personality_choices"][self.boundary]
            results.append((chosen.action.request_id, chosen.action.verb,
                            entry["choice"]["prompt_sha256"],
                            entry["choice"]["raw_scores"],
                            entry["choice"]["adjusted_scores"]))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    async def test_low_safety_confidence_refuses_and_never_falls_back_to_goap(self):
        agent, router, engine, ctrl, cp, saves = self._setup(
            independent=True, selected="llm", high=False)
        with self.assertRaises(CognitionUnavailable):
            await self._decide(agent, ctrl, cp)
        self.assertEqual(engine.calls, 3)
        self.assertEqual(router.record["boundaries"][self.boundary]["selected"],"llm")
        self.assertNotIn("personality_choices", router.record)
        self.assertEqual(len(agent.pending_requests), 0)
        self.assertEqual(len(saves), 1)
        # A failure of the stored deliberation route must NOT silently
        # generate a different GOAP proposal under the original boundary.
        with self.assertRaises(CognitionUnavailable):
            await self._decide(agent, ctrl, cp)
        self.assertEqual(router.record["boundaries"][self.boundary]["selected"],"llm")
        self.assertEqual(len(agent.pending_requests), 0)

    async def test_safety_critical_goap_branch_refuses_every_operator(self):
        agent, router, engine, ctrl, cp, saves = self._setup(
            independent=False, selected="goap")
        with self.assertRaises(PermissionError):
            await self._decide(agent, ctrl, cp)
        self.assertEqual(engine.calls, 0)
        self.assertEqual(router.record["boundaries"][self.boundary]["selected"],"goap")
        self.assertNotIn("personality_choices",router.record)
        self.assertEqual(len(agent.pending_requests),0)
        self.assertEqual(len(saves),1)

    async def test_high_confidence_risky_action_is_still_only_world_proposal(self):
        # Deliberately use a high *unsafely chosen* native action: a locked
        # model score is NOT a world authorization or evidence of safety.
        agent, router, engine, ctrl, cp, saves = self._setup(
            independent=False, selected="llm", target="support_loan")
        proposal = await self._decide(agent, ctrl, cp)
        ledger = router.record["personality_choices"][self.boundary]
        self.assertTrue(ledger["choice"]["safety_locked"])
        self.assertEqual(ledger["selected_semantic_key"],"support_loan")
        self.assertEqual(self.menu.by_command(
            proposal.action.verb,proposal.action.target).semantic_key,
                         "support_loan")
        self.assertEqual(len(agent.pending_requests),1)
        # The controller has no Evennia port and cannot issue a work receipt.
        self.assertEqual(proposal.action.character_id,"#301")
        self.assertEqual(self.menu.scope,"hypothetical")
        self.assertEqual(engine.calls,3)

    async def test_mutated_positive_lock_checkpoint_is_rejected_before_any_replay(self):
        agent, router, engine, ctrl, cp, saves = self._setup(
            independent=False, selected="llm")
        await self._decide(agent, ctrl, cp)
        for mutation in ("safety_locked", "raw_scores", "shifts",
                         "selected_semantic_key"):
            altered=deepcopy(router.record)
            value=altered["personality_choices"][self.boundary]["choice"]
            if mutation=="safety_locked":
                value["safety_locked"]=False
            elif mutation=="raw_scores":
                # A forged switch of the native evidence winner must
                # never be replayed as the original locked proposal.
                value["raw_scores"]={
                    "reserve_spare":.01, "support_loan":.98,
                    "seek_review":.01,
                }
            elif mutation=="shifts":
                value["shifts"]["reserve_spare"]=.01
            else:
                value["selected_semantic_key"]="support_loan"
            other=PersonalityRouter(
                agent.blueprint, "#301", altered,
                seed=router.record["seed"],
            )
            saved_route=other.select(
                boundary_id=self.boundary,kind="urgent",state=self.state,
                observation_revision=agent.revision,
                cognition_revision=agent.cognition_revision,
                persist=lambda: self.fail("Cannot repersist a saved route"),
            )
            with self.subTest(mutation=mutation), self.assertRaises(
                    (ValueError,PermissionError)):
                PersonalityChoiceLedger(other).saved(
                    route=saved_route, menu=self.menu,
                    catalog_sha256=load_catalog().content_sha256(),
                )


if __name__=="__main__":
    unittest.main()
