"""No native weights needed: order balance, finite choices and fail-closed guard."""
from __future__ import annotations

import unittest

from ox_ai.inference.position_balanced_choice import (
    PositionBalancedDeciderChoiceModel,
)

OPTIONS = (
    ("accept", "Accept the pending offer."),
    ("defer", "Leave the pending offer unresolved."),
    ("decline", "Decline the pending offer."),
)


class PositionEngine:
    def __init__(self, *, bad_on=None, semantic_bonus=None):
        self.calls = []
        self.bad_on = bad_on
        self.semantic_bonus = semantic_bonus or {}

    def system_one(self, prompt, questions):
        criteria = questions["next_action"]["criteria"]
        codes = tuple(criteria)
        self.calls.append((prompt, tuple(criteria.values()), codes))
        ordinal = len(self.calls)
        if self.bad_on == ordinal:
            return {"answers": {"next_action": {
                "choice": codes[0], "probabilities": {codes[0]: 1.0},
            }}}
        # Deliberately strong positional preference, plus a stable bonus for
        # specific semantic text. Never assumes fixed action order.
        positional = (0.6, 0.3, 0.1)
        weights = {
            code: positional[i] + self.semantic_bonus.get(label, 0)
            for i, (code, label) in enumerate(criteria.items())
        }
        total = sum(weights.values())
        scores = {code: value / total for code, value in weights.items()}
        chosen = max(codes, key=lambda code: scores[code])
        return {"answers": {"next_action": {
            "choice": chosen, "probabilities": scores,
        }}}


class BalanceTests(unittest.TestCase):
    def model(self, options=OPTIONS, engine=None):
        return PositionBalancedDeciderChoiceModel(
            "weights-not-used.gguf", options,
            engine=engine if engine is not None else PositionEngine(),
        )

    def test_each_semantic_option_is_scored_at_all_three_positions(self):
        backend = PositionEngine()
        model = self.model(engine=backend)
        index, letter, meta = model.sample_choice(
            "Never omit this individual memory of a crewmember.", ("a", "b", "c"))
        self.assertEqual((index, letter), (0, "a"))
        self.assertEqual(model.last["underlying_native_calls"], 3)
        self.assertEqual(len(backend.calls), 3)
        self.assertTrue(model.last["all_three_positions_per_semantic_option"])
        for field in ("accept", "defer", "decline"):
            self.assertAlmostEqual(
                meta["decider_position_balanced_choice"]["semantic_probabilities"][field],
                1 / 3,
                places=12,
            )
        self.assertTrue(all("individual memory" in prompt
                            for prompt, _, _ in backend.calls))
        seen = {key: set() for key in ("accept", "defer", "decline")}
        for _, descriptions, _ in backend.calls:
            for pos, label in enumerate(descriptions):
                key = next(k for k, text in OPTIONS if text == label)
                seen[key].add(pos)
        self.assertEqual(seen, {key: {0, 1, 2} for key in seen})

    def test_caller_menu_order_cannot_move_selected_semantic_intent(self):
        original = self.model(engine=PositionEngine())
        new_order = (OPTIONS[2], OPTIONS[0], OPTIONS[1])
        shuffled = self.model(options=new_order, engine=PositionEngine())
        a = original.sample_choice("same observed mind", ("a", "b", "c"))
        b = shuffled.sample_choice("same observed mind", ("a", "b", "c"))
        self.assertEqual(original.last["selected_semantic_key"],
                         shuffled.last["selected_semantic_key"])
        self.assertEqual(
            original.last["semantic_probabilities"],
            shuffled.last["semantic_probabilities"],
        )
        # Codes change because the returned action remains bound to the
        # caller's offered menu. The semantic winner stays the same.
        self.assertEqual(a[1], "a")
        self.assertEqual(b[1], "b")

    def test_genuine_semantic_signal_remains_visible(self):
        backend = PositionEngine(semantic_bonus={OPTIONS[2][1]: 0.7})
        model = self.model(engine=backend)
        position, label, _ = model.sample_choice("same mind", ("a", "b", "c"))
        self.assertEqual((position, label), (2, "c"))
        self.assertEqual(model.last["selected_semantic_key"], "decline")
        self.assertGreater(
            model.last["semantic_probabilities"]["decline"],
            model.last["semantic_probabilities"]["accept"]
        )

    def test_fails_closed_after_partial_native_result(self):
        backend = PositionEngine(bad_on=2)
        model = self.model(engine=backend)
        with self.assertRaisesRegex(ValueError, "probability"):
            model.sample_choice("same mind", ("a", "b", "c"))
        self.assertEqual(len(backend.calls), 2)
        self.assertIsNone(model.last)

    def test_rejects_ambiguous_semantics_and_unoffered_codes(self):
        with self.assertRaises(ValueError):
            self.model(options=(OPTIONS[0], OPTIONS[0], OPTIONS[2]))
        with self.assertRaises(ValueError):
            self.model(options=OPTIONS[:1])
        with self.assertRaisesRegex(ValueError, "unique model response"):
            self.model().sample_choice("state", ("a", "a", "c"))
        with self.assertRaisesRegex(ValueError, "unique model response"):
            self.model().sample_choice("", ("a", "b", "c"))
        with self.assertRaisesRegex(RuntimeError, "cannot generate text"):
            self.model().sample_text("Respond with unrestricted advice")


if __name__ == "__main__":
    unittest.main()
