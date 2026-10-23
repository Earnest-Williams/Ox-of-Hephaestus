"""G13 experiment invariants; optional Concordia stays optional in scaffold."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path("scenarios/g8_soap_opera").resolve()))


class G13AssessorTests(unittest.TestCase):
    def test_rejects_missing_reports_without_native_dependencies(self):
        from g13_assess import assess
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                assess(Path(d))


@unittest.skipUnless(
    importlib.util.find_spec("concordia") is not None,
    "G13 native experiment needs optional Concordia; scaffold does not",
)
class G13StructuralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = importlib.import_module("g13_matched_personality")

    def test_factorial(self):
        m = self.mod
        self.assertEqual((len(m.ARMS), len(m.CASES), len(m.ORDERS)), (3, 4, 3))
        self.assertEqual(len(m.TRAIT_INTERVENTIONS), 2)
        self.assertEqual(len({c.key for c in m.CASES}), 4)
        self.assertEqual(sum(len(m.menu(c, "Mara", o))
                             for c in m.CASES for o in m.ORDERS), 36)

    def test_order_does_not_alter_offered_semantics(self):
        m = self.mod
        for case in m.CASES:
            canonical = m.menu(case, "Lin", "canonical")
            for order in m.ORDERS:
                offered = m.menu(case, "Lin", order)
                self.assertEqual({(x.verb, x.target, x.label) for x in canonical},
                                 {(x.verb, x.target, x.label) for x in offered})
            self.assertNotEqual(canonical, m.menu(case, "Lin", "reverse"))
        with self.assertRaises(ValueError):
            m.menu(m.CASES[0], "Lin", "unknown")

    def test_modified_profile_state_reversible(self):
        from ox_ai.agents.crew_blueprints import compose_blueprint
        m = self.mod
        bp = compose_blueprint("g13.unit", "Example", history=("Same memories",))
        old_context = bp.cognition_context()
        saved = {
            "identity": {"character_id": "#111"},
            "character_blueprint": bp.to_record(),
            "concordia_state": {
                "CharacterProfile": {"state": old_context},
                "memory": {"state": ["fixed, private recollection"]},
            },
            "temporal_memories": [{"source_event_id": "world:event-1"}],
            "cognition_revision": 4,
        }
        baseline = m.evidence_digest(saved)
        for arm in m.ARMS:
            copy, chosen = m.isolated_snapshot(saved, arm)
            self.assertEqual(m.evidence_digest(copy), baseline)
            self.assertEqual(copy["temporal_memories"], saved["temporal_memories"])
            self.assertEqual(copy["identity"], saved["identity"])
            self.assertEqual(copy["concordia_state"]["CharacterProfile"]["state"],
                             chosen.cognition_context())
            self.assertEqual(
                copy["character_blueprint"]["traits"], dict(chosen.traits)
            )
        self.assertEqual(
            saved["concordia_state"]["CharacterProfile"]["state"], old_context
        )


if __name__ == "__main__":
    unittest.main()
