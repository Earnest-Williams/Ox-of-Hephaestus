"""G16c deterministic semantic action choice and durable world-proposal boundary.

Pure tests need only ox-contracts. The native Concordia integration gate
installs the pinned engine separately; no model weights or Evennia server.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import math
from unittest import mock
import unittest

from ox_ai.agents.crew import CommandOption
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.inference.disposition_choice import (
    PersonalityAdjustedDeciderChoiceModel,
    ReplayedPersonalityChoiceModel,
    choice_temperature, keyed_choice_draw, score_personality_choice,
)
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.runtime.cognition_scheduler import (
    CognitionBudgetExceeded, CognitionUnavailable, DecisionScheduler,
)
from ox_ai.runtime.personality_choice_ledger import (
    PersonalityChoiceLedger, deterministic_proposal_id,
)
from ox_ai.runtime.personality_routing import (
    CharacterRouteController, PersonalState, PersonalityRouter,
)

try:
    from ox_contracts import load_catalog
except ImportError:
    load_catalog = None


class SemanticNativeEngine:
    """Actual three-pass System One contract, but deliberately FAKE logits.

    Never count this backend as model quality or native G16e evidence.
    """

    def __init__(self, *, strong=False):
        self.calls = 0
        self.strong = strong

    def system_one(self, prompt, questions):
        self.calls += 1
        criteria = questions["next_action"]["criteria"]
        values = {}
        for index, (code, label) in enumerate(criteria.items()):
            key = next((name for name in (
                "accept_help", "work_alone", "reschedule",
                "reserve_spare", "support_loan", "seek_review",
            ) if name in label), None)
            if key is None:
                raise AssertionError("Unexpected test menu")
            if self.strong:
                # A repeatable real semantic dominance despite three rotations.
                base = 0.95 if key == "reserve_spare" else 0.025
            else:
                base = {"accept_help": 0.35, "work_alone": 0.40,
                        "reschedule": 0.25}[key]
            values[code] = base + (0.035 if index == 0 else 0)
        total = sum(values.values())
        scores = {code: v / total for code, v in values.items()}
        return {"answers": {"next_action": {
            "choice": max(scores, key=scores.get),
            "probabilities": scores,
        }}}


class LegacyModelMustNotRun:
    def sample_choice(self, prompt, responses, *, seed=None):
        raise AssertionError("The flag must use the G16c explicit scorer instead")

    def sample_text(self, *args, **kwargs):
        raise AssertionError("No generation requested")


def profile(person_id="g16c.owner", *, independent=False):
    traits = (
        {"conscientiousness": 20, "risk_tolerance": 95,
         "authority_challenge": 95, "collaboration": 15, "agreeableness": 20}
        if independent else
        {"conscientiousness": 95, "risk_tolerance": 10,
         "authority_challenge": 10, "collaboration": 95, "agreeableness": 90}
    )
    return compose_blueprint(person_id, "G16c Crew", trait_overrides=traits)


@unittest.skipIf(load_catalog is None, "Optional G16a contract not installed")
class PureChoiceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.menu = self.catalog.menu("g14.verified_mutual_aid")
        self.profile = profile()

    def engine_choice(self, menu_order):
        ordered = tuple(self.menu.by_key(key) for key in menu_order)
        engine = SemanticNativeEngine()
        model = PersonalityAdjustedDeciderChoiceModel(
            "", tuple((a.semantic_key, "Act: " + a.semantic_key) for a in ordered),
            menu=self.menu, profile=self.profile,
            seed="g16c-per-actor-seed", actor="#301",
            boundary="world.decision.34", kind="social", engine=engine,
        )
        selected_index, code, metadata = model.sample_choice(
            "Stable actor-private decision prompt", ("A", "B", "C"),
        )
        self.assertEqual(engine.calls, 3)
        self.assertEqual(metadata["decider_position_balanced_personality_choice"],
                         model.last)
        self.assertEqual(code, ("A", "B", "C")[selected_index])
        return model.last

    def test_semantic_invariance_permutation_and_frozen_model_budget(self):
        keys = tuple(x.semantic_key for x in self.menu.options)
        first = self.engine_choice(keys)
        permuted = self.engine_choice(tuple(reversed(keys)))
        self.assertEqual(first["selected_semantic_key"],
                         permuted["selected_semantic_key"])
        self.assertEqual(first["raw_scores"], permuted["raw_scores"])
        self.assertEqual(first["shifts"], permuted["shifts"])
        self.assertEqual(first["adjusted_scores"], permuted["adjusted_scores"])
        self.assertEqual(first["draw"], permuted["draw"])
        self.assertEqual(first["underlying_native_calls"], 3)
        self.assertAlmostEqual(sum(first["adjusted_scores"].values()), 1.0)
        self.assertTrue(all(abs(s) <= 0.21 for s in first["shifts"].values()))
        self.assertEqual(
            keyed_choice_draw("g16c-per-actor-seed", "#301", "world.decision.34"),
            first["draw"],
        )

    def test_traits_adjust_scores_explicitly_and_deterministically(self):
        raw = {"accept_help": 0.38, "work_alone": 0.39, "reschedule": 0.23}
        careful = score_personality_choice(
            native_scores=raw, menu=self.menu, profile=self.profile,
            seed="same-seed-value", actor="#301", boundary="world.test.1",
            kind="social",
        )
        independent = score_personality_choice(
            native_scores=raw, menu=self.menu, profile=profile(independent=True),
            seed="same-seed-value", actor="#301", boundary="world.test.1",
            kind="social",
        )
        self.assertNotEqual(careful["adjusted_scores"], independent["adjusted_scores"])
        self.assertNotEqual(careful["temperature"], independent["temperature"])
        self.assertEqual(careful["raw_scores"], independent["raw_scores"])
        self.assertTrue(
            careful["adjusted_scores"]["accept_help"] >
            independent["adjusted_scores"]["accept_help"]
        )
        self.assertEqual(choice_temperature(self.profile, urgent=True), 0.11)

    def test_critical_uncertain_refuses_and_strong_lock_forces_native(self):
        menu = self.catalog.menu("g14.finite_spare_dispute")
        args = dict(menu=menu, profile=self.profile,
                    seed="locked-case-seed", actor="#301",
                    boundary="world.test.safety", kind="urgent")
        with self.assertRaises(PermissionError):
            score_personality_choice(
                native_scores={"reserve_spare": 0.43,
                               "support_loan": 0.32, "seek_review": 0.25},
                **args,
            )
        good = score_personality_choice(
            native_scores={"reserve_spare": 0.96,
                           "support_loan": 0.02, "seek_review": 0.02},
            **args,
        )
        self.assertTrue(good["safety_locked"])
        self.assertEqual(good["selected_semantic_key"], "reserve_spare")
        self.assertEqual(good["adjusted_scores"]["reserve_spare"], 1.0)
        self.assertTrue(all(v == 0.0 for v in good["shifts"].values()))

    def test_invalid_native_vector_rejected_and_replay_requires_same_prompt(self):
        with self.assertRaises(ValueError):
            score_personality_choice(
                native_scores={"accept_help": 0.5, "work_alone": float("nan"),
                               "reschedule": 0.5},
                menu=self.menu, profile=self.profile,
                seed="seed", actor="#301", boundary="case", kind="social",
            )
        initial = self.engine_choice(tuple(x.semantic_key for x in self.menu.options))
        previous = ReplayedPersonalityChoiceModel(
            initial, tuple((a.semantic_key, "Act: " + a.semantic_key)
                           for a in self.menu.options),
        )
        ix, code, _meta = previous.sample_choice(
            "Stable actor-private decision prompt", ("A", "B", "C"),
        )
        self.assertEqual(code, ("A", "B", "C")[ix])
        self.assertEqual(previous.last, initial)
        with self.assertRaises(PermissionError):
            previous.sample_choice(
                "Altered private evidence not authorized for replay", ("A", "B", "C"),
            )


@unittest.skipUnless(load_catalog is not None and
                     importlib.util.find_spec("concordia") is not None,
                     "Optional G16a and native Concordia integration dependencies absent")
class NativeControllerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from ox_ai.agents.crew import CrewAgent, CrewIdentity
        self.profile = profile("g16c.native")
        self.agent = CrewAgent(
            CrewIdentity("ox.person." + self.profile.person_id,
                         "#301", self.profile.name, "Watch technician",
                         "Inspect the offered options"),
            LegacyModelMustNotRun(),
            blueprint=self.profile,
        )
        self.menu = load_catalog().menu("g14.verified_mutual_aid")
        self.offered = tuple(
            CommandOption("Act: " + a.semantic_key, a.verb, a.target)
            for a in self.menu.options
        )
        self.planner = GoapPlanner(tuple(
            GoapAction(a.semantic_key, requires=frozenset({"offer_active"}),
                       adds=frozenset({"handled"}), verb=a.verb, target=a.target)
            for a in self.menu.options
        ))
        self.state = PersonalState(stress=0.4, social_pressure=0.5)
        self.boundary = "world.offered.choice.1"
        self.snapshots = []

    def router_for(self, want):
        for n in range(256):
            ledger = {}
            r = PersonalityRouter(
                self.profile, "#301", ledger, seed=f"g16c-test-seed-{n}",
            )
            would = "llm" if r._draw(self.boundary) < r.probability(
                self.state, "social"
            ) else "goap"
            if would == want:
                return r
        self.fail("No stable seeded branch coverage")

    def persist(self):
        self.snapshots.append(deepcopy(self.router.record))

    def controller(self, router, *, engine=None):
        self.router = router
        return CharacterRouteController(
            router, DecisionScheduler(
                max_parallel=1, timeout_seconds=30,
                per_actor_budget=64, total_budget=64,
            ), role="g16c", decider_engine=engine,
        )

    async def do_choice(self, controller, agent=None, *, persist=None):
        return await controller.decide(
            agent=agent or self.agent,
            planner=self.planner,
            beliefs=frozenset({"offer_active"}),
            goals=frozenset({"handled"}),
            options=self.offered, boundary_id=self.boundary,
            kind="social", state=self.state,
            menu_key=self.menu.menu_key,
            persist=persist if persist is not None else self.persist,
        )

    async def test_decider_checkpoint_precedes_live_adoption_and_replays(self):
        router = self.router_for("llm")
        engine = SemanticNativeEngine()
        control = self.controller(router, engine=engine)
        observed = []
        def checkpoint():
            # Routing is committed before inference; choice record committed
            # while LIVE pending request ledger is still empty.
            observed.append((deepcopy(router.record), len(self.agent.pending_requests)))
        with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
            result = await self.do_choice(control, persist=checkpoint)
        self.assertEqual(result.route.selected, "llm")
        self.assertEqual(result.model_calls, 3)
        self.assertEqual(engine.calls, 3)
        self.assertEqual(len(observed), 2)
        self.assertEqual([v[1] for v in observed], [0, 0])
        self.assertNotIn("personality_choices", observed[0][0])
        entry = observed[1][0]["personality_choices"][self.boundary]
        self.assertEqual(entry["actor"], "#301")
        self.assertEqual(entry["request_id"], result.action.request_id)
        self.assertEqual(entry["choice"]["underlying_native_calls"], 3)
        self.assertEqual(
            entry["selected_semantic_key"],
            self.menu.by_command(result.action.verb, result.action.target).semantic_key,
        )
        self.assertEqual(len(self.agent.pending_requests), 1)
        with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
            replayed = await self.do_choice(
                control, persist=lambda: self.fail("Replay cannot checkpoint or reroll")
            )
        self.assertEqual(replayed.action, result.action)
        self.assertEqual(replayed.model_calls, 0)
        self.assertEqual(engine.calls, 3)

    async def test_goap_two_personalities_choose_distinct_plans(self):
        first = self.router_for("goap")
        ctrl = self.controller(first, engine=SemanticNativeEngine())
        with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
            a = await self.do_choice(ctrl)
        self.assertEqual(a.model_calls, 0)
        self.assertEqual(a.action.verb, "consider.accept_help")
        entry = first.record["personality_choices"][self.boundary]
        self.assertEqual(entry["route"], "goap")
        self.assertEqual(entry["request_id"], a.action.request_id)
        self.assertGreater(len(entry["choice"]["planner_costs"]), 0)
        with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
            repeat = await self.do_choice(
                ctrl, persist=lambda: self.fail("Replayed GOAP choice rerolled")
            )
        self.assertEqual(repeat.action.request_id, a.action.request_id)
        self.assertEqual(repeat.action.verb, a.action.verb)

    async def test_persist_failure_cannot_adopt_any_new_proposal(self):
        router = self.router_for("llm")
        ctrl = self.controller(router, engine=SemanticNativeEngine())
        calls = []
        def fail_second_persist():
            calls.append(1)
            if len(calls) == 2:
                raise OSError("checkpoint unavailable")
        with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
            with self.assertRaises(CognitionUnavailable):
                await self.do_choice(ctrl, persist=fail_second_persist)
        self.assertEqual(len(self.agent.pending_requests), 0)
        self.assertNotIn("personality_choices", router.record)
        self.assertEqual(len(calls), 2)

    async def test_crash_between_ledger_commit_and_agent_adoption_replays_original_id(self):
        from ox_ai.agents.crew import CrewAgent
        router = self.router_for("llm")
        engine = SemanticNativeEngine()
        ctrl = self.controller(router, engine=engine)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "pre_adoption_brain.json"
            def save_before_adopt():
                self.agent.save_checkpoint(path)
            with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
                first = await self.do_choice(ctrl, persist=save_before_adopt)
            # The last on-disk brain was saved from inside the choice hook,
            # before the live Agent adopted the detached draft.
            restored = CrewAgent.from_checkpoint(path, LegacyModelMustNotRun())
            self.assertEqual(len(restored.pending_requests), 0)
            self.assertEqual(engine.calls, 3)
            other = PersonalityRouter(
                self.profile, "#301", deepcopy(router.record),
                seed=router.record["seed"],
            )
            replay_controller = self.controller(other, engine=LegacyModelMustNotRun())
            with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
                recovered = await self.do_choice(
                    replay_controller, agent=restored,
                    persist=lambda: self.fail("Committed choice must not reroll"),
                )
            self.assertEqual(recovered.model_calls, 0)
            self.assertEqual(recovered.action.request_id, first.action.request_id)
            self.assertEqual(recovered.action.verb, first.action.verb)
            self.assertEqual(len(restored.pending_requests), 1)
            # A changed situation with identical boundary and revision may
            # not reuse a different private prompt under the old choice.
            tampered_brain = CrewAgent.from_checkpoint(path, LegacyModelMustNotRun())
            self.state = PersonalState(stress=0.9, social_pressure=0.1)
            with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
                with self.assertRaises(PermissionError):
                    await self.do_choice(
                        replay_controller, agent=tampered_brain,
                        persist=lambda: self.fail("No altered context replay"),
                    )
            self.assertEqual(len(tampered_brain.pending_requests), 0)

    async def test_modified_checkpoint_draw_or_scores_fails_closed(self):
        router = self.router_for("llm")
        ctrl = self.controller(router, engine=SemanticNativeEngine())
        with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
            await self.do_choice(ctrl)
        for change in ("draw", "adjusted"):
            record = deepcopy(router.record)
            score = record["personality_choices"][self.boundary]["choice"]
            if change == "draw":
                score["draw"] = 0.7777777777
            else:
                score["adjusted_scores"]["work_alone"] += 0.01
            saved_router = PersonalityRouter(
                self.profile, "#301", record, seed=router.record["seed"],
            )
            saved_route = saved_router.select(
                boundary_id=self.boundary, kind="social", state=self.state,
                observation_revision=self.agent.revision,
                cognition_revision=self.agent.cognition_revision,
                persist=lambda: self.fail("Reread must not reroll"),
            )
            with self.subTest(change=change), self.assertRaises(
                    (ValueError, PermissionError)):
                PersonalityChoiceLedger(saved_router).saved(
                    route=saved_route, menu=self.menu,
                    catalog_sha256=load_catalog().content_sha256(),
                )

    async def test_three_forward_budget_denies_when_two_units_available(self):
        router = self.router_for("llm")
        engine = SemanticNativeEngine()
        self.router = router
        ctrl = CharacterRouteController(
            router, DecisionScheduler(
                max_parallel=1, timeout_seconds=10,
                per_actor_budget=2, total_budget=2,
            ), role="g16c", decider_engine=engine,
        )
        with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
            with self.assertRaises(CognitionBudgetExceeded):
                await self.do_choice(ctrl)
        self.assertEqual(engine.calls, 0)
        self.assertEqual(len(self.agent.pending_requests), 0)
        self.assertNotIn("personality_choices", router.record)

    async def test_catalog_mismatch_refused_before_model_or_world(self):
        router = self.router_for("llm")
        ctrl = self.controller(router, engine=SemanticNativeEngine())
        changed = tuple(self.offered[:2])
        with mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}):
            with self.assertRaises(ValueError):
                await ctrl.decide(
                    agent=self.agent, planner=self.planner,
                    beliefs=frozenset({"offer_active"}),
                    goals=frozenset({"handled"}),
                    options=changed, boundary_id=self.boundary,
                    kind="social", state=self.state,
                    menu_key=self.menu.menu_key, persist=self.persist,
                )
        self.assertEqual(len(self.agent.pending_requests), 0)
        self.assertEqual(router.record["boundaries"], {})
        self.assertNotIn("personality_choices", router.record)


if __name__ == "__main__":
    unittest.main()
