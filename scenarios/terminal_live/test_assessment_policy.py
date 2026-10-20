"""GOAP only revisits a standing prognosis after contrary evidence.

These focused regressions intentionally distinguish:
* changed data that CONFIRM the accepted prognosis (no review), from
* new information that CONTRADICTS the accepted prognosis (review).
The authoritative Evennia world remains responsible for checking actual
assessment identity; the policy controls whether actors should submit one.
"""
from __future__ import annotations

import unittest

from continuous_trial import AdaptiveGoap, valid_options
from prognosis_policy import PrognosisReview


FINDING = "Local pressure trend indicates declining atmosphere"


def view(oxygen=12.30, *, co2=2.50, minute=60, token="a" * 64,
         finding=FINDING):
    return {
        "minute": minute, "oxygen_kpa": oxygen, "co2_percent": co2,
        "reading_proof": token, "own_finding": finding,
        "location": "Bridge", "nearby_living": [],
        "local_cartridge_spares": None, "local_reserve_bottles": None,
    }


def addressed(seq: int, code: str | None = None, *,
              text="New crew observation") -> dict:
    event = {
        "sequence": seq, "kind": "terminal_report",
        "text": text,
    }
    if code is not None:
        event["datum_evidence_code"] = code
    return event


class PrognosisPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = AdaptiveGoap("lin")
        self.policy.attempts["terminal_survey"] = 1
        self.policy.last_relayed = FINDING
        self.first = view()

    def decide(self, current, *, events=None, sequence=1):
        recent = [] if events is None else events
        self.policy.review_evidence(current, recent)
        menu = valid_options("lin", current, self.policy.state())
        choice, explanation = self.policy.select(
            current, recent, menu, sequence,
        )
        return choice.verb

    def accept_first(self):
        self.assertEqual(self.decide(self.first), "terminal_assess")
        assessment = self.policy.propose_assessment(self.first, 1)
        self.policy.notice(
            "terminal_assess", "succeeded", self.first, 1,
            assessment=assessment,
        )
        self.assertEqual(self.policy.prognosis.phase, "threat")
        self.assertIsNone(self.policy.prognosis.pending)
        return assessment

    def test_initial_prognosis_requires_evidence(self):
        unseen = view(finding="")
        self.assertNotEqual(self.decide(unseen), "terminal_assess")
        self.assertNotIn(
            "terminal_assess",
            {option.verb for option in valid_options(
                "lin", unseen, self.policy.state(),
            )},
        )
        with self.assertRaisesRegex(RuntimeError, "No counterevidence"):
            self.policy.propose_assessment(unseen, 1)

    def test_first_prognosis_is_permitted_once_and_not_repeated(self):
        prior = self.accept_first()
        self.assertNotEqual(self.decide(self.first), "terminal_assess")
        self.assertEqual(self.policy.prognosis.last_accepted, prior)

    def test_worsening_readings_and_critical_alarm_do_not_reopen_prognosis(self):
        self.accept_first()
        events = [
            {"sequence": 20, "kind": "terminal_critical",
             "text": "Atmosphere now critically low"},
            addressed(21, text="Independent environmental report confirms decline"),
        ]
        for later in (
            view(11.63, co2=2.90, minute=72, token="b" * 64),
            view(9.60, co2=4.50, minute=92, token="c" * 64),
            view(6.80, co2=5.10, minute=120, token="d" * 64),
        ):
            self.assertNotEqual(
                self.decide(later, events=events, sequence=21),
                "terminal_assess",
            )
            self.assertIsNone(self.policy.prognosis.pending)
        # GOAP did not merely decline to submit a new draft. It never
        # constructed or compared one while evidence was corroborative.
        self.policy.propose_assessment = lambda *_: self.fail(
            "Prognosis reconsidered without contrary evidence"
        )
        self.decide(view(5.80, co2=5.50, minute=132), sequence=21)

    def test_one_short_lived_oxygen_improvement_does_not_refute_survival_risk(self):
        self.accept_first()
        # Reserve gas may transiently improve oxygen, but CO2 continues to
        # increase and this is not a demonstrated sustainable alternative.
        after_bottle = view(
            13.10, co2=2.95, minute=68, token="b" * 64,
        )
        self.assertNotEqual(self.decide(after_bottle), "terminal_assess")

    def test_typed_report_contrary_to_known_prognosis_triggers_one_review(self):
        prior = self.accept_first()
        report = addressed(25, "possible_safe_refuge")
        self.assertEqual(self.decide(self.first, events=[report], sequence=25),
                         "terminal_assess")
        revision = self.policy.propose_assessment(self.first, 25)
        self.assertNotEqual(revision["claim"], prior["claim"])
        self.assertEqual(revision["evidence_sequence"], "25")
        self.policy.notice(
            "terminal_assess", "succeeded", self.first, 25,
            assessment=revision,
        )
        self.assertEqual(self.policy.prognosis.phase, "candidate")
        # Another "possible refuge" report confirms the standing revised
        # proposition; it does not contradict it or require another update.
        repeat = addressed(26, "possible_safe_refuge")
        self.assertNotEqual(self.decide(self.first, events=[repeat], sequence=26),
                            "terminal_assess")

    def test_refutation_of_candidate_allows_another_prognosis(self):
        self.accept_first()
        candidate = addressed(25, "possible_safe_refuge")
        self.assertEqual(self.decide(self.first, events=[candidate], sequence=25),
                         "terminal_assess")
        revision = self.policy.propose_assessment(self.first, 25)
        self.policy.notice("terminal_assess", "succeeded", self.first, 25,
                           assessment=revision)
        refutation = addressed(33, "refuge_candidate_disproved")
        self.assertEqual(self.decide(self.first, events=[refutation], sequence=33),
                         "terminal_assess")
        self.assertIn("contradicted",
                      self.policy.propose_assessment(self.first, 33)["claim"])

    def test_genuinely_sustained_stabilization_can_challenge_deterioration(self):
        self.accept_first()
        # Same readings from the actual character over a sufficiently long
        # period, including CO2 stability, contradict continuing deterioration.
        durable_stability = view(
            oxygen=12.25, co2=2.54, minute=88, token="e" * 64,
        )
        self.assertEqual(self.decide(durable_stability), "terminal_assess")
        self.assertEqual(self.policy.prognosis.pending.kind, "candidate")

    def test_rising_co2_blocks_false_stability_signal(self):
        self.accept_first()
        after_reserve = view(
            oxygen=12.35, co2=3.05, minute=88, token="f" * 64,
        )
        self.assertNotEqual(self.decide(after_reserve), "terminal_assess")

    def test_refused_identical_assessment_does_not_hot_loop(self):
        self.assertEqual(self.decide(self.first), "terminal_assess")
        authored = self.policy.propose_assessment(self.first, 1)
        self.policy.notice(
            "terminal_assess", "failed", self.first, 1,
            assessment=authored, refusal_reason="unchanged_assessment",
        )
        self.assertEqual(self.policy.prognosis.last_refused, authored)
        self.assertEqual(
            self.policy.prognosis.last_refusal_reason,
            "unchanged_assessment",
        )
        self.assertNotEqual(self.decide(self.first), "terminal_assess")

    def test_same_evidence_reinterpreted_without_counterevidence_is_not_solicited(self):
        self.accept_first()
        # The WORLD still accepts a materially different authored conclusion.
        # GOAP simply does not spontaneously reopen a prognosis without
        # discovering any disconfirming evidence.
        assert not self.policy.review_evidence(self.first, [])
        self.assertIsNone(self.policy.prognosis.pending)
        self.assertNotEqual(self.decide(self.first), "terminal_assess")

    def test_only_actual_addressed_typed_findings_are_counterevidence(self):
        self.accept_first()
        bad_events = [
            {"kind": "terminal_critical", "sequence": 35,
             "datum_evidence_code": "possible_safe_refuge"},
            addressed(36, text="Maybe something was found?"),
            addressed(37, "no_sealed_refuge_found"),
        ]
        self.assertNotEqual(
            self.decide(self.first, events=bad_events, sequence=37),
            "terminal_assess",
        )


if __name__ == "__main__":
    unittest.main()
