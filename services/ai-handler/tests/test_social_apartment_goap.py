"""GOAP chooses social intentions; no model, hidden-feelings oracle or romance script."""

import unittest

from ox_ai.planning.goap import GoapPlanner
from ox_ai.scenarios.apartment_goap import (
    HEARD_CUES, LINES, SOCIAL_ACTIONS, OfflineApartment, SocialGoapActor,
    make_pair, run_offline,
)


class ApartmentGoapTests(unittest.TestCase):
    def test_social_domain_uses_real_multistep_goap_search(self):
        planner = GoapPlanner(SOCIAL_ACTIONS)
        plan = planner.plan(
            {"in_apartment", "partner_present", "date_enjoyed",
             "partner_positive", "open_to_more"},
            {"invited"},
        )
        self.assertEqual([a.name for a in plan.actions],
                         ["appreciate", "invite"])
        self.assertEqual(plan.total_cost, 3)

    def test_predicted_speech_is_not_a_confirmed_action(self):
        woman, _man = make_pair(variant="mutual")
        proposal = woman.propose()
        self.assertEqual(proposal.action, "appreciate")
        self.assertNotIn("appreciated", woman.facts)
        with self.assertRaises(PermissionError):
            woman.confirm_spoken("The world did not report this line.")
        self.assertNotIn("appreciated", woman.facts)
        with self.assertRaises(RuntimeError):
            woman.propose()
        woman.confirm_spoken(proposal.line)
        self.assertIn("appreciated", woman.facts)

    def test_no_access_to_unspoken_romantic_interest(self):
        clara, ben = make_pair(variant="cautious")
        self.assertNotIn("partner_invited", clara.facts)
        self.assertNotIn("partner_pace", ben.facts)
        self.assertNotIn("partner_positive", clara.facts)
        self.assertNotIn("partner_positive", ben.facts)
        line = LINES["appreciate"]
        self.assertIn("partner_positive", HEARD_CUES[line])
        ben.hear(sender="Clara", event_id="evt-1", line=line)
        self.assertIn("partner_positive", ben.facts)
        # Expressing enjoyment is not an invitation, consent or proof of love.
        for secret in ("partner_invited", "partner_accepted",
                       "partner_wants_romance", "clara_interest"):
            self.assertNotIn(secret, ben.facts)
        self.assertFalse(ben.hear(sender="Clara", event_id="evt-1", line=line))
        with self.assertRaises(PermissionError):
            ben.hear(sender="Ben", event_id="evt-2", line=line)

    def test_social_goap_respects_actual_heard_boundary(self):
        clara, ben = make_pair(variant="mutual")
        scene = OfflineApartment(clara, ben)
        scene.step(clara)
        scene.step(ben)
        self.assertIn("partner_positive", ben.facts)
        # A new *spoken* boundary defeats an attractive invitation plan.
        ben.hear(sender="Clara", event_id="later-pace",
                 line=LINES["share_pace"])
        next_move = ben.propose()
        self.assertEqual(next_move.action, "acknowledge_pace")
        self.assertNotEqual(next_move.action, "invite")
        ben.confirm_spoken(next_move.line)
        self.assertIn("pace_acknowledged", ben.facts)

    def test_cautious_pair_has_no_pressure_after_pace_is_spoken(self):
        result = run_offline(variant="cautious")
        acts = [item["action"] for item in result["transcript"]]
        self.assertEqual(result["status"], "complete", result)
        self.assertIn("share_pace", acts)
        self.assertIn("acknowledge_pace", acts)
        self.assertNotIn("invite", acts)
        self.assertEqual(acts.count("goodnight"), 2)
        self.assertEqual(result["model_calls"], 0)
        self.assertTrue(all(
            entry["plan"][0] == entry["action"]
            for entry in result["transcript"]
        ))
        self.assertGreater(result["planning_calls"]["Clara"], 0)

    def test_mutual_and_mismatch_lead_to_different_conclusions(self):
        mutual = run_offline(variant="mutual")
        mismatch = run_offline(variant="mismatch")
        first = [item["action"] for item in mutual["transcript"]]
        second = [item["action"] for item in mismatch["transcript"]]
        self.assertEqual(mutual["status"], "complete", mutual)
        self.assertEqual(mismatch["status"], "complete", mismatch)
        self.assertIn("invite", first)
        self.assertIn("accept", first)
        self.assertIn("invite", second)
        self.assertIn("decline", second)
        self.assertIn("acknowledge_decline", second)
        self.assertNotIn("accept", second)
        self.assertNotEqual(first, second)

    def test_turn_cap_does_not_fabricate_happy_ending(self):
        result = run_offline(variant="mutual", turn_cap=1)
        self.assertEqual(result["status"], "turn_capped")
        self.assertEqual(result["turns"], 1)
        self.assertEqual(result["model_calls"], 0)

    def test_world_refusal_does_not_create_emotional_progress(self):
        clara, _ben = make_pair()
        attempt = clara.propose()
        clara.refuse("Not in the same room")
        self.assertNotIn("appreciated", clara.facts)
        self.assertIn(attempt.action, clara.blocked)
        # No invented success; retry needs new evidence or a different plan.
        self.assertIsNone(clara.propose())


if __name__ == "__main__":
    unittest.main()
