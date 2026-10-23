"""G14 structural, fail-closed, and optional Concordia profile controls."""
import importlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path("scenarios/g8_soap_opera").resolve()))


class G14AssessorTests(unittest.TestCase):
    def test_absent_actor_rejected_even_in_minimal_scaffold(self):
        from g14_assess import assess
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(FileNotFoundError):
                assess(Path(root))


    def test_balanced_aggregate_rejects_repeat_prompt_tamper(self):
        import json
        from g14_assess import assess, ROLES, CASES, ARMS, ORDERS, ACTIONS, POSITIONS
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for role in ROLES:
                rows = []
                for case in CASES:
                    opts = ACTIONS[case]
                    for arm in ARMS:
                        for order in ORDERS:
                            offered = [opts[i] for i in POSITIONS[order]]
                            rows.append({
                                "role": role, "case": case, "arm": arm, "order": order,
                                "choice": opts[0], "position": offered.index(opts[0]),
                                "offered_actions": offered,
                                "scores": {x: (0.9 if x == opts[0] else 0.05) for x in opts},
                                "goap_baseline": opts[0], "evidence_digest": "e" * 64,
                                "prompt_control_sha256": "a" * 64, "model_calls": 1,
                                "world_commands_sent": 0, "hypothetical_only": True,
                            })
                repeats = [
                    dict(next(x for x in rows if x["case"] == case
                              and x["arm"] == "numeric_original"
                              and x["order"] == "canonical"))
                    for case in CASES
                ]
                record = {
                    "schema": 2, "status": "g14_matched_balanced_profile_arms_complete",
                    "engine": "decider-q4", "role": role, "source_g9_run": 39872687597,
                    "source_world_maintenance_receipts": 5, "hypothetical_only": True,
                    "world_commands_sent": 0, "native_model_calls": 52,
                    "evidence_digest": "e" * 64, "rows": rows,
                    "repeat_controls": repeats,
                }
                (root / (role + ".json")).write_text(json.dumps(record))
            self.assertTrue(assess(root)["position_balanced"])
            path = root / (ROLES[0] + ".json")
            record = json.loads(path.read_text())
            record["repeat_controls"][0]["prompt_control_sha256"] = "b" * 64
            path.write_text(json.dumps(record))
            with self.assertRaises(PermissionError):
                assess(root)


@unittest.skipUnless(
    importlib.util.find_spec("concordia") is not None,
    "Optional Concordia absent from minimal engine scaffold",
)
class G14NativeStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = importlib.import_module("g14_profile_salience")

    def test_complete_factorial_and_real_symbolic_baselines(self):
        m = self.mod
        self.assertEqual((len(m.CASES), len(m.ORDERS), len(m.ARMS)), (4,3,4))
        self.assertEqual(m.ORDERS, ("canonical", "cycle_left", "cycle_right"))
        for semantic_index in range(3):
            self.assertEqual(
                sorted(m.POSITIONS[o].index(semantic_index) for o in m.ORDERS),
                [0, 1, 2],
            )
        self.assertEqual(len(set(c.key for c in m.CASES)),4)
        self.assertEqual(
            sum(len(m.menu(case, "Ari", order))
                for case in m.CASES for order in m.ORDERS),36)
        for c in m.CASES:
            self.assertEqual(len(c.options),3)
            self.assertEqual(len({x[0] for x in c.options}),3)
            self.assertEqual(m.goap_baseline(c),c.baseline)
            options=m.menu(c,"Ari","canonical")
            for order in m.ORDERS:
                self.assertEqual(
                    {(x.label,x.verb,x.target) for x in options},
                    {(x.label,x.verb,x.target)
                     for x in m.menu(c,"Ari",order)},
                )

    def test_narrative_trait_intervention_is_bounded_and_reversible(self):
        from ox_ai.agents.crew_blueprints import compose_blueprint
        m=self.mod
        original_profile=compose_blueprint("g14.unit","Test Crewmember")
        original_text=original_profile.cognition_context()
        saved={
            "identity":{"character_id":"#155"},
            "character_blueprint":original_profile.to_record(),
            "concordia_state":{
                "CharacterProfile":{"state":original_text},
                "Memories":{"state":["Kept original historical observation."]},
            },
            "temporal_memories":[{"source_event_id":"world:event-144"}],
            "cognition_revision":12,
        }
        original_evidence=m.evidence_digest(saved)
        for arm in m.ARMS:
            fork,blueprint,text=m.treatment(saved,arm)
            self.assertEqual(m.evidence_digest(fork),original_evidence)
            self.assertEqual(saved["identity"],fork["identity"])
            self.assertEqual(saved["temporal_memories"],fork["temporal_memories"])
            self.assertEqual(fork["concordia_state"]["CharacterProfile"]["state"],
                             text)
            self.assertEqual(fork["character_blueprint"]["traits"],
                             dict(blueprint.traits))
            if arm.startswith("prose"):
                self.assertIn("tendencies",text)
                self.assertNotIn("starting traits (0-100)",text)
                self.assertNotIn("must accept",text.lower())
                self.assertLessEqual(len(text),1800)
                self.assertIn("Formative aptitudes (1-10): ",text)
                self.assertEqual(text.split("Formative aptitudes (1-10): ",1)[1],
                                 blueprint.cognition_context().split("Formative aptitudes (1-10): ",1)[1])
        self.assertEqual(saved["concordia_state"]["CharacterProfile"]["state"],
                         original_text)
        with self.assertRaises(ValueError):
            m.treatment(saved,"anything_unregistered")

    def test_trait_interpretation_changes_only_personal_language(self):
        from ox_ai.agents.crew_blueprints import compose_blueprint
        m=self.mod
        careful=compose_blueprint("g14.trait.a","Careful",
            trait_overrides={"risk_tolerance":10,"collaboration":90})
        independent=compose_blueprint("g14.trait.a","Careful",
            trait_overrides={"risk_tolerance":90,"collaboration":10})
        a=m.prose_profile(careful)
        b=m.prose_profile(independent)
        self.assertIn("cautious about uncertain outcomes",a)
        self.assertIn("comfortable with uncertain outcomes",b)
        self.assertIn("collective solutions",a)
        self.assertIn("independent action",b)
        self.assertNotEqual(a,b)


if __name__=="__main__":
    unittest.main()
