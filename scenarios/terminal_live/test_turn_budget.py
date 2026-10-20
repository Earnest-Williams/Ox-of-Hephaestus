"""Pure checks for the disposable runner's decision ceilings."""
import unittest
from turn_budget import TurnBudget, TurnCapReached


class TurnBudgetTests(unittest.TestCase):
    def test_per_actor_limit_never_pretends_a_death(self):
        b = TurnBudget(("teo", "captain"), max_per_character=3, max_total=12)
        self.assertEqual([b.claim("teo") for _ in range(3)], [1, 2, 3])
        with self.assertRaisesRegex(TurnCapReached, "character_turn_limit:teo"):
            b.claim("teo")
        self.assertEqual(b.total, 3)
        self.assertEqual(b.counts["teo"], 3)
        self.assertEqual(b.claim("captain"), 1)

    def test_global_limit_stops_at_exact_threshold(self):
        b = TurnBudget(("teo", "captain"), max_per_character=100, max_total=5)
        for role in ("teo", "captain", "teo", "captain", "teo"):
            b.claim(role)
        self.assertEqual(b.total, 5)
        with self.assertRaisesRegex(TurnCapReached, "total_turn_limit"):
            b.claim("captain")
        self.assertEqual(b.total, 5)

    def test_unknown_actor_cannot_consume_a_turn(self):
        b = TurnBudget(("teo",), max_per_character=100, max_total=480)
        with self.assertRaises(PermissionError):
            b.claim("operator")
        self.assertEqual(b.total, 0)

    def test_cap_is_comfortably_above_preceding_137_decisions(self):
        roles = ("teo", "captain", "lin", "mara", "ari", "iona")
        b = TurnBudget(roles, max_per_character=100, max_total=480)
        for turn in range(480):
            b.claim(roles[turn % 6])
        self.assertEqual(b.total, 480)
        self.assertEqual(set(b.counts.values()), {80})
        with self.assertRaisesRegex(TurnCapReached, "total_turn_limit"):
            b.claim("teo")


if __name__ == "__main__":
    unittest.main()
