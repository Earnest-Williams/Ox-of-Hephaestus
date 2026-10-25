"""G16o binary scoring and durable proposal tests; all logits are synthetic.

No world connection, receipt, model weights or behavioural evidence is used.
"""

from __future__ import annotations

import asyncio
import importlib.util
import threading
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.inference.disposition_choice import PersonalityAdjustedDeciderChoiceModel
from ox_ai.inference.position_balanced_choice import PositionBalancedDeciderChoiceModel
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.runtime.cognition_scheduler import (
    CognitionBudgetExceeded,
    CognitionTimedOut,
    CognitionUnavailable,
    DecisionScheduler,
)
from ox_ai.runtime.personality_routing import (
    CharacterRouteController,
    PersonalityRouter,
    PersonalState,
)

try:
    from ox_contracts import ActionTagCatalog, load_catalog
except ImportError:
    load_catalog = None


OPTIONS = (("report", "File observed cargo report"), ("defer", "Defer this report"))


class BinaryEngine:
    """Synthetic position bias, optionally semantic dominance or corruption."""

    def __init__(self, *, strong=False, bad_on=None):
        self.calls = []
        self.strong = strong
        self.bad_on = bad_on

    def system_one(self, prompt, questions):
        criteria = questions["next_action"]["criteria"]
        self.calls.append((prompt, tuple(criteria.values())))
        if len(self.calls) == self.bad_on:
            return {"answers": {"next_action": {"choice": "unoffered"}}}
        weights = {
            code: (19.0 if self.strong and "File" in label else 1.0) + (0.1 if i == 0 else 0.0)
            for i, (code, label) in enumerate(criteria.items())
        }
        total = sum(weights.values())
        scores = {code: value / total for code, value in weights.items()}
        return {
            "answers": {
                "next_action": {
                    "choice": max(scores, key=scores.get),
                    "probabilities": scores,
                }
            }
        }


class ForbiddenModel:
    """Detect any accidental fresh inference or text generation."""

    def sample_choice(self, *args, **kwargs):
        raise AssertionError("No legacy model or replay inference allowed")

    def sample_text(self, *args, **kwargs):
        raise AssertionError("No dialogue generation allowed")


class BinaryBalanceTests(unittest.TestCase):
    def test_two_rotations_balance_positions_and_bind_to_caller_order(self):
        records = []
        for order in (OPTIONS, tuple(reversed(OPTIONS))):
            engine = BinaryEngine()
            model = PositionBalancedDeciderChoiceModel("", order, engine=engine)
            index, code, _ = model.sample_choice("same private mind", ("A", "B"))
            self.assertEqual(order[index][0], model.last["selected_semantic_key"])
            self.assertEqual(code, ("A", "B")[index])
            self.assertEqual(model.last["underlying_native_calls"], 2)
            self.assertTrue(model.last["all_two_positions_per_semantic_option"])
            self.assertNotIn("all_three_positions_per_semantic_option", model.last)
            self.assertEqual(len(engine.calls), 2)
            for key, label in OPTIONS:
                self.assertEqual({labels.index(label) for _, labels in engine.calls}, {0, 1})
                self.assertAlmostEqual(model.last["semantic_probabilities"][key], 0.5)
            records.append(model.last)
        self.assertEqual(records[0], records[1])

    def test_semantic_signal_survives_and_failed_second_pass_erases_last(self):
        engine = BinaryEngine(strong=True)
        model = PositionBalancedDeciderChoiceModel("", OPTIONS, engine=engine)
        model.sample_choice("mind", ("A", "B"))
        self.assertEqual(model.last["selected_semantic_key"], "report")
        engine.bad_on = 4
        with self.assertRaises(ValueError):
            model.sample_choice("mind", ("A", "B"))
        self.assertEqual(len(engine.calls), 4)
        self.assertIsNone(model.last)

    def test_invalid_codes_cannot_invoke_backend_or_retain_a_result(self):
        engine = BinaryEngine()
        model = PositionBalancedDeciderChoiceModel("", OPTIONS, engine=engine)
        for codes in (("A",), ("A", "A"), ("A", "B", "C"), ([], "B"), ("", "B")):
            with self.subTest(codes=codes), self.assertRaises(ValueError):
                model.sample_choice("mind", codes)
            self.assertIsNone(model.last)
        self.assertFalse(engine.calls)

    @unittest.skipUnless(load_catalog is not None, "Requires strict action catalog")
    def test_uncertain_binary_safety_refuses_and_strong_binary_lock_forces_native(self):
        menu = load_catalog().menu("live.p4a_pump_alarm")
        profile = compose_blueprint("g16o.safety", "G16o Safety")
        for strong in (False, True):
            engine = BinaryEngine(strong=strong)
            model = PersonalityAdjustedDeciderChoiceModel(
                "",
                (("isolate", "File isolation proposal"), ("defer", "Defer isolation")),
                menu=menu,
                profile=profile,
                seed="g16o-safety",
                actor="#301",
                boundary="g16o.safety.event",
                kind="urgent",
                engine=engine,
            )
            if strong:
                model.sample_choice("hypothetical safety fixture", ("A", "B"))
                self.assertTrue(model.last["safety_locked"])
                self.assertEqual(model.last["selected_semantic_key"], "isolate")
                self.assertEqual(model.last["adjusted_scores"]["isolate"], 1.0)
            else:
                with self.assertRaises(PermissionError):
                    model.sample_choice("hypothetical safety fixture", ("A", "B"))
                self.assertIsNone(model.last)
            self.assertEqual(len(engine.calls), 2)


@unittest.skipUnless(
    load_catalog is not None and importlib.util.find_spec("concordia"),
    "Requires the real pinned Concordia and strict contracts",
)
class BinaryControllerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.profile = compose_blueprint("g16o.technician", "G16o Technician")
        self.state = PersonalState(stress=0.4, uncertainty=0.3)
        self.boundary = "g16o.original.station.event"
        # This catalog exists only inside the test. No live world menu is added.
        self.catalog = ActionTagCatalog.model_validate_json("""{
          "schema_version":1,"menus":[{
            "menu_key":"offline.g16o.report","scope":"offline_trial",
            "safety_critical":false,"options":[
              {"semantic_key":"report","verb":"round_report","target":"ship",
               "arguments":[["station","cargo"]],
               "tags":{"risk":-0.2,"deference":0.5,"social":0.0,"autonomy":0.0,"procedure":0.8}},
              {"semantic_key":"defer","verb":"defer","target":null,
               "tags":{"risk":0.2,"deference":-0.5,"social":0.0,"autonomy":0.4,"procedure":-0.8}}
            ]}]}""")
        self.menu = self.catalog.menus[0]
        self.options = (
            CommandOption(OPTIONS[0][1], "round_report", "ship", {"station": "cargo"}),
            CommandOption(OPTIONS[1][1], "defer"),
        )
        for i in range(256):
            router = PersonalityRouter(self.profile, "#301", {}, seed=f"g16o-seed-{i}")
            if router._draw(self.boundary) < router.probability(self.state, "routine"):
                self.seed = router.record["seed"]
                break
        else:
            self.fail("Cannot select a deterministic model-route fixture")

    def actor(self):
        """Create a separate actual native Concordia actor."""
        return CrewAgent(
            CrewIdentity(
                "ox.person." + self.profile.person_id,
                "#301",
                self.profile.name,
                "Review the observed station",
                "Propose an offered action",
            ),
            ForbiddenModel(),
            blueprint=self.profile,
        )

    def controller(self, engine, *, record=None, budget=2, timeout=30):
        """Give this test a private router and bounded scheduler."""
        router = PersonalityRouter(self.profile, "#301", record or {}, seed=self.seed)
        return CharacterRouteController(
            router,
            DecisionScheduler(
                max_parallel=1,
                per_actor_budget=budget,
                total_budget=budget,
                timeout_seconds=timeout,
            ),
            role="g16o",
            decider_engine=engine,
        )

    async def decide(self, controller, actor, *, options=None, persist=lambda: None):
        """Patch only the offline test catalog, with no server or transport."""
        with (
            mock.patch.dict("os.environ", {"OX_PERSONALITY_CHOICE": "1"}),
            mock.patch("ox_contracts.load_catalog", return_value=self.catalog),
        ):
            return await controller.decide(
                agent=actor,
                planner=GoapPlanner((GoapAction("defer", verb="defer"),)),
                beliefs=frozenset(),
                goals=frozenset({"reviewed"}),
                options=options if options is not None else self.options,
                boundary_id=self.boundary,
                kind="routine",
                state=self.state,
                menu_key=self.menu.menu_key,
                persist=persist,
            )

    async def test_two_forward_budget_checkpoint_and_exact_argument_replay(self):
        engine, actor = BinaryEngine(strong=True), self.actor()
        ctrl = self.controller(engine)
        writes = []
        result = await self.decide(
            ctrl,
            actor,
            persist=lambda: writes.append(
                (deepcopy(ctrl.router.record), len(actor.pending_requests))
            ),
        )
        self.assertEqual(result.model_calls, 2)
        self.assertEqual(len(engine.calls), 2)
        self.assertEqual(result.action.arguments, {"station": "cargo"})
        self.assertEqual([pending for _, pending in writes], [0, 0])
        saved = writes[-1][0]["personality_choices"][self.boundary]["choice"]
        self.assertEqual(saved["policy_version"], 2)
        self.assertEqual(saved["underlying_native_calls"], 2)
        self.assertTrue(saved["all_two_positions_per_semantic_option"])
        replay = await self.decide(
            ctrl,
            actor,
            options=tuple(reversed(self.options)),
            persist=lambda: self.fail("Replay cannot persist"),
        )
        self.assertEqual(replay.action, result.action)
        self.assertEqual(replay.model_calls, 0)
        self.assertEqual(ctrl.scheduler.metrics["started"], 2)

    async def test_one_unit_budget_cannot_start_a_partial_binary_decision(self):
        engine, actor = BinaryEngine(), self.actor()
        ctrl = self.controller(engine, budget=1)
        with self.assertRaises(CognitionBudgetExceeded):
            await self.decide(ctrl, actor)
        self.assertFalse(engine.calls)
        self.assertFalse(actor.pending_requests)
        self.assertNotIn("personality_choices", ctrl.router.record)

    async def test_full_concordia_prompt_and_policy_are_invariant_to_outer_order(self):
        records = []
        for order in (self.options, tuple(reversed(self.options))):
            ctrl = self.controller(BinaryEngine())
            await self.decide(ctrl, self.actor(), options=order)
            records.append(ctrl.router.record["personality_choices"][self.boundary])
        self.assertEqual(records[0], records[1])

    async def test_crash_before_adoption_recovers_without_new_forward(self):
        actor = self.actor()
        ctrl = self.controller(BinaryEngine(strong=True))
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "pre-adoption.json"
            original = await self.decide(ctrl, actor, persist=lambda: actor.save_checkpoint(path))
            restored = CrewAgent.from_checkpoint(path, ForbiddenModel())
            self.assertFalse(restored.pending_requests)
            record = deepcopy(ctrl.router.record)
            replay = self.controller(ForbiddenModel(), record=record)
            recovered = await self.decide(
                replay, restored, persist=lambda: self.fail("Already durable")
            )
            self.assertEqual(recovered.action, original.action)
            self.assertEqual(recovered.model_calls, 0)

    async def test_binary_ledger_rejects_ternary_version_and_coverage_claims(self):
        ctrl = self.controller(BinaryEngine())
        await self.decide(ctrl, self.actor())
        for field, value in (
            ("policy_version", 1),
            ("underlying_native_calls", 3),
            ("all_two_positions_per_semantic_option", False),
            ("balanced_native_picks", ["report"] * 3),
        ):
            record = deepcopy(ctrl.router.record)
            record["personality_choices"][self.boundary]["choice"][field] = value
            replay = self.controller(ForbiddenModel(), record=record)
            with self.subTest(field=field), self.assertRaises((ValueError, PermissionError)):
                await self.decide(replay, self.actor())

    async def test_failed_second_pass_never_commits_a_choice(self):
        ctrl, actor = self.controller(BinaryEngine(bad_on=2)), self.actor()
        with self.assertRaises(CognitionUnavailable):
            await self.decide(ctrl, actor)
        self.assertNotIn("personality_choices", ctrl.router.record)
        self.assertFalse(actor.pending_requests)

    async def test_binary_safety_lock_and_refusal_reach_the_actual_controller(self):
        self.menu = load_catalog().menu("live.p4a_pump_alarm")
        self.catalog = ActionTagCatalog(schema_version=1, menus=(self.menu,))
        self.options = (
            CommandOption("File isolation proposal", "isolate", "pump"),
            CommandOption("Defer isolation", "defer"),
        )
        for strong in (False, True):
            ctrl, actor = self.controller(BinaryEngine(strong=strong)), self.actor()
            if strong:
                proposal = await self.decide(ctrl, actor)
                saved = ctrl.router.record["personality_choices"][self.boundary]["choice"]
                self.assertTrue(saved["safety_locked"])
                self.assertEqual(proposal.action.verb, "isolate")
                self.assertEqual(saved["adjusted_scores"]["isolate"], 1.0)
                self.assertTrue(all(value == 0.0 for value in saved["shifts"].values()))
            else:
                with self.assertRaises(PermissionError):
                    await self.decide(ctrl, actor)
                self.assertNotIn("personality_choices", ctrl.router.record)
                self.assertFalse(actor.pending_requests)

    async def test_binary_choice_checkpoint_failure_prevents_adoption(self):
        ctrl, actor = self.controller(BinaryEngine()), self.actor()
        writes = []

        def fail_choice_write():
            writes.append(1)
            if len(writes) == 2:
                raise OSError("Unavailable checkpoint")

        with self.assertRaises(CognitionUnavailable):
            await self.decide(ctrl, actor, persist=fail_choice_write)
        self.assertEqual(len(writes), 2)
        self.assertNotIn("personality_choices", ctrl.router.record)
        self.assertFalse(actor.pending_requests)

    async def test_timed_out_binary_worker_drains_without_adoption(self):
        started, release = threading.Event(), threading.Event()
        delegate = BinaryEngine()

        class HeldEngine:
            """Block until the caller has expired, without a real provider."""

            def system_one(self, prompt, questions):
                started.set()
                if not release.wait(5):
                    raise TimeoutError("Test did not release the detached worker")
                return delegate.system_one(prompt, questions)

        ctrl, actor = self.controller(HeldEngine(), timeout=0.15), self.actor()
        try:
            with self.assertRaises(CognitionTimedOut):
                await self.decide(ctrl, actor)
            self.assertTrue(started.is_set())
        finally:
            release.set()
            for _ in range(200):
                if not ctrl.scheduler.metrics["inflight_roles"]:
                    break
                await asyncio.sleep(0.01)
        self.assertFalse(ctrl.scheduler.metrics["inflight_roles"])
        self.assertFalse(actor.pending_requests)
        self.assertNotIn("personality_choices", ctrl.router.record)
        self.assertEqual(len(delegate.calls), 2)


if __name__ == "__main__":
    unittest.main()
