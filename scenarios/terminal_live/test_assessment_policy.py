"""Focused GOAP regression: refusals suppress ONLY the same actual submission."""
from __future__ import annotations

import unittest

from continuous_trial import AdaptiveGoap, valid_options, urgency
from assessment_payload import compose_assessment


def view(oxygen=12.30, *, co2=2.50, minute=60, token=None):
    return {
        "minute": minute, "oxygen_kpa": oxygen, "co2_percent": co2,
        "reading_proof": token or "a" * 64,
        "own_finding": "", "location": "Bridge",
        "nearby_living": [], "local_cartridge_spares": None,
        "local_reserve_bottles": None,
    }


class GenuineRevisionTests(unittest.TestCase):
    def setUp(self):
        self.controller = AdaptiveGoap("lin")
        self.controller.attempts["terminal_survey"] = 1
        self.first = view()

    def decide(self, current, *, sequence=1, kinds=("terminal_report",)):
        options = valid_options("lin", current, self.controller.state())
        return self.controller.select(
            current, [{"kind": kind} for kind in kinds],
            options, sequence,
        )[0].verb

    def refuse_once(self):
        assessment = self.controller.propose_assessment(self.first, 1)
        self.assertEqual(self.decide(self.first), "terminal_assess")
        self.controller.notice(
            "terminal_assess", "failed", self.first, 1,
            assessment=assessment, refusal_reason="unchanged_assessment",
        )
        return assessment

    def test_identical_claim_and_evidence_is_not_retried(self):
        prior = self.refuse_once()
        self.assertNotEqual(self.decide(self.first), "terminal_assess")
        self.assertEqual(
            self.controller.last_refused_assessment_content, prior,
        )
        self.assertEqual(self.controller.last_refusal_reason, "unchanged_assessment")

    def test_changed_risk_band_is_eligible_despite_prior_refusal(self):
        prior = self.refuse_once()
        newer = view(9.60, co2=4.50, minute=92, token="b" * 64)
        self.assertNotEqual(
            self.controller.propose_assessment(newer, 1), prior,
        )
        self.assertEqual(self.decide(newer), "terminal_assess")

    def test_meaningful_sensor_change_inside_same_band_is_eligible(self):
        self.refuse_once()
        newer = view(11.63, co2=2.77, minute=72, token="b" * 64)
        self.assertEqual(urgency(newer), urgency(self.first))
        self.assertEqual(self.decide(newer), "terminal_assess")

    def test_changed_interpretation_of_exact_same_evidence_is_eligible(self):
        prior = self.refuse_once()
        # A different interpretation may come from reconsideration of the
        # *same* source reading. The world must not require new evidence.
        rewritten = dict(prior)
        rewritten["claim"] = "This may be recoverable after further investigation"
        rewritten["confidence"] = "moderate"
        rewritten["rationale"] = "On reflection I see another viable hypothesis"
        self.controller.propose_assessment = lambda *_: rewritten
        self.assertEqual(self.decide(self.first), "terminal_assess")

    def test_decreasing_danger_may_warrant_reassessment(self):
        prior = self.refuse_once()
        improved = view(16.20, co2=1.55, minute=76, token="c" * 64)
        self.assertLess(urgency(improved), urgency(self.first))
        self.assertEqual(self.decide(improved, kinds=()), "terminal_assess")
        self.assertNotEqual(
            self.controller.propose_assessment(improved, 1), prior,
        )

    def test_same_claim_with_new_addressed_report_is_eligible(self):
        self.refuse_once()
        self.assertEqual(
            self.decide(self.first, sequence=20), "terminal_assess",
        )

    def test_payload_uses_actual_observation_not_global_world_truth(self):
        proposal = self.controller.propose_assessment(self.first, 1)
        self.assertEqual(proposal["oxygen_kpa"], "12.30")
        self.assertEqual(proposal["reading_minute"], "60")
        self.assertEqual(proposal["evidence_sequence"], "1")
        self.assertNotIn("cause", proposal)
        self.assertEqual(
            proposal,
            compose_assessment(
                self.first,
                claim=proposal["claim"], confidence=proposal["confidence"],
                rationale=proposal["rationale"], evidence_sequence=1,
            ),
        )


if __name__ == "__main__":
    unittest.main()
