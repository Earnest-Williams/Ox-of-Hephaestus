"""G13 experiment invariants independent of actual GGUF outcomes."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path("scenarios/g8_soap_opera").resolve()))
from g13_matched_personality import (ARMS,CASES,ORDERS,TRAIT_INTERVENTIONS,
    menu,isolated_snapshot,profile_for,evidence_digest)


class G13StructuralTests(unittest.TestCase):
    def test_factorial(self):
        self.assertEqual((len(ARMS),len(CASES),len(ORDERS)),(3,4,3))
        self.assertEqual(len(TRAIT_INTERVENTIONS),2)
        self.assertEqual(len(set(c.key for c in CASES)),4)
        self.assertEqual(sum(len(menu(c,"Mara",o)) for c in CASES for o in ORDERS),36)

    def test_order_does_not_alter_offered_semantics(self):
        for case in CASES:
            canonical=menu(case,"Lin","canonical")
            for order in ORDERS:
                offered=menu(case,"Lin",order)
                self.assertEqual({(x.verb,x.target,x.label) for x in canonical},
                                 {(x.verb,x.target,x.label) for x in offered})
            self.assertNotEqual(canonical,menu(case,"Lin","reverse"))
        with self.assertRaises(ValueError):
            menu(CASES[0],"Lin","unknown")

    def test_modified_profile_state_reversible(self):
        from ox_ai.agents.crew_blueprints import compose_blueprint
        bp=compose_blueprint("g13.unit","Example",history=("Same memories",))
        old_context=bp.cognition_context()
        saved={
            "identity":{"character_id":"#111"},
            "character_blueprint":bp.to_record(),
            "concordia_state":{"CharacterProfile":{"state":old_context},
                                "memory":{"state":["fixed, private recollection"]}},
            "temporal_memories":[{"source_event_id":"world:event-1"}],
            "cognition_revision":4,
        }
        baseline=evidence_digest(saved)
        for arm in ARMS:
            copy,chosen=isolated_snapshot(saved,arm)
            self.assertEqual(evidence_digest(copy),baseline)
            self.assertEqual(copy["temporal_memories"],saved["temporal_memories"])
            self.assertEqual(copy["identity"],saved["identity"])
            self.assertEqual(copy["concordia_state"]["CharacterProfile"]["state"],
                             chosen.cognition_context())
        self.assertEqual(saved["concordia_state"]["CharacterProfile"]["state"],old_context)

    def test_rejects_missing_reports(self):
        import tempfile
        from g13_assess import assess
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                assess(Path(d))


if __name__=="__main__":
    unittest.main()
