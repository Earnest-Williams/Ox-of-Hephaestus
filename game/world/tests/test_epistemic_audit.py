"""Operator-only unknown unknown classification; never disclose hidden truths."""
from __future__ import annotations

import copy
import json
import unittest

from world.epistemic_audit import OperatorFactAssessment, classify_world_fact


PIRATE = "pirate.moon_far_side_waiting"
MOON = "moon.unobserved_far_side"


def mind(character_id="#11", role="lin"):
    return {
        "version": 1, "character_id": character_id, "role": role,
        "observations": {}, "beliefs": {}, "questions": {},
        "events": {}, "surprises": [], "concepts": [],
    }


def inspect(record, *, proposition=PIRATE, actual_world_value=True,
            exposed=False, at=12):
    return classify_world_fact(
        proposition=proposition, actual_world_value=actual_world_value,
        actor_epistemics=record, actor_dbref=record["character_id"],
        world_time=at, evidence_disclosed_to_actor=exposed,
    )


class WorldRelativeEpistemicsTests(unittest.TestCase):
    def test_known_to_world_unknown_unknown_to_character_right_now(self):
        lin = mind()
        before = json.dumps(lin, sort_keys=True)
        assessment = inspect(lin)
        self.assertEqual(assessment, OperatorFactAssessment("unknown_unknown"))
        # No 'future revelation' or surprise is necessary for the operator
        # to classify this ACTUAL hidden pirate as unknown unknown.
        self.assertEqual(lin["surprises"], [])
        self.assertEqual(json.dumps(lin, sort_keys=True), before)
        self.assertNotIn("pirate", json.dumps(lin))
        self.assertNotIn("moon", json.dumps(lin))

    def test_broad_question_does_not_reveal_hidden_specific_pirate(self):
        lin = mind()
        lin["questions"][MOON] = {
            "reason": "Far side is not currently visible",
            "status": "open",
        }
        self.assertEqual(inspect(lin, proposition=MOON).relation, "known_unknown")
        self.assertEqual(inspect(lin, proposition=PIRATE).relation, "unknown_unknown")
        self.assertNotIn(PIRATE, json.dumps(lin))

    def test_same_world_fact_relative_to_independent_minds(self):
        lin, mara, teo = mind("#11", "lin"), mind("#41", "mara"), mind("#52", "teo")
        mara["questions"][PIRATE] = {
            "reason": "Could a raider be concealed beyond the moon?",
            "status": "open",
        }
        teo["observations"][PIRATE] = {
            "value": True, "at": 10.0, "valid_for": 5.0,
            "source": "world_local", "evidence_id": "radar-77", "history": [],
        }
        self.assertEqual(inspect(lin).relation, "unknown_unknown")
        self.assertEqual(inspect(mara).relation, "known_unknown")
        self.assertEqual(inspect(teo).relation, "known_known")
        self.assertEqual(inspect(teo, at=20).relation, "known_unknown")

    def test_assumption_is_not_world_knowledge_even_if_correct(self):
        lin = mind()
        lin["beliefs"][PIRATE] = {
            "value": True, "state": "hypothesis",
            "confidence": 0.35, "basis": "Another officer's rumor",
        }
        self.assertEqual(inspect(lin), OperatorFactAssessment(
            "modeled_belief", True,
        ))
        self.assertEqual(inspect(lin, actual_world_value=False),
                         OperatorFactAssessment("modeled_belief", False))
        self.assertFalse(bool(lin["observations"]))

    def test_disclosed_but_not_assimilated_is_an_audit_warning(self):
        lin = mind()
        self.assertEqual(inspect(lin, exposed=True).relation,
                         "exposed_unassimilated")
        self.assertNotIn(PIRATE, json.dumps(lin))
        # An authenticated observation becomes known after the agent
        # separately receives it, not when the operator labels it.
        lin["observations"][PIRATE] = {
            "value": True, "at": 12, "valid_for": 1,
            "source": "world_local", "evidence_id": "radar-78",
            "history": [],
        }
        self.assertEqual(inspect(lin, exposed=True).relation, "known_known")

    def test_false_observation_is_not_known_known(self):
        lin = mind()
        lin["observations"][PIRATE] = {
            "value": False, "at": 10, "valid_for": 5,
            "source": "world_local", "evidence_id": "sensor-error",
            "history": [],
        }
        self.assertEqual(inspect(lin).relation, "mistaken_observation")

    def test_no_cross_character_join_or_invalid_world_inputs(self):
        lin = mind()
        with self.assertRaises(PermissionError):
            classify_world_fact(
                proposition=PIRATE, actual_world_value=True,
                actor_epistemics=lin, actor_dbref="#99",
                world_time=12, evidence_disclosed_to_actor=False,
            )
        for malformed in (
            {"proposition": "<secret>"},
            {"world_time": float("nan")},
            {"evidence_disclosed_to_actor": "false"},
            {"actual_world_value": {"location": "moon"}},
        ):
            params = {
                "proposition": PIRATE, "actual_world_value": True,
                "actor_epistemics": copy.deepcopy(lin),
                "actor_dbref": "#11", "world_time": 12,
                "evidence_disclosed_to_actor": False,
            }
            params.update(malformed)
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                classify_world_fact(**params)


if __name__ == "__main__":
    unittest.main()
