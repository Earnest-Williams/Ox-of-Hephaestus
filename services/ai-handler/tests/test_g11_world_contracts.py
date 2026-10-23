"""G11: real-world consequence boundaries, anti-forgery, restart and G8 safety."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


class G11EvaluatorSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod=load("g11_evaluate_test","scenarios/g8_soap_opera/g11_evaluate.py")

    def test_bogus_not_really_decider_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"state.json").write_text(json.dumps({
                "turn":205,"trace":[{} for _ in range(205)],
                "cognition_mode":"symbolic","contract_routing":True,
                "contract_audit":[],
            }))
            with self.assertRaises(PermissionError):
                self.mod.evaluate(p)

    def test_missing_opt_in_rejected_before_reading_private_crew(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"state.json").write_text(json.dumps({
                "turn":205,"trace":[{} for _ in range(205)],
                "cognition_mode":"decider","contract_routing":False,
                "contract_audit":[],
            }))
            with self.assertRaises(PermissionError):
                self.mod.evaluate(p)


@unittest.skipUnless(
    importlib.util.find_spec("concordia") is not None,
    "Native Concordia optional extra not installed",
)
class G11RealAgentGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod=load("g11_trial_unit","scenarios/g8_soap_opera/live_trial.py")

    def test_legacy_opt_in_is_explicit_and_immutable(self):
        m=self.mod
        with self.assertRaisesRegex(ValueError,"needs opt-in Decider"):
            m.Trial(241,Path("."),contract_routing=True)
        with self.assertRaises(ValueError):
            m.Trial(241,Path("."),cognition_mode="symbolic",
                    contract_routing="yes")
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            t=m.Trial(241,p)
            t._model=lambda: m.MockModel()
            t.bind({role:f"#{i+1}" for i,role in enumerate(m.ROSTER)})
            t.save()
            with self.assertRaisesRegex(PermissionError,"authority mode"):
                m.Trial(241,p,cognition_mode="symbolic",
                        contract_routing=True)

    def test_real_reply_goes_to_one_actor_only_and_is_still_a_proposal(self):
        m=self.mod
        from ox_ai.ports.base import ActionOutcome
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            t=m.Trial(241,root,cognition_mode="decider",contract_routing=True)
            from ox_ai.scenarios.personality_dilemmas import FixtureFirstChoice
            t._model=lambda: FixtureFirstChoice()
            ids={role:f"#{i+11}" for i,role in enumerate(m.ROSTER)}
            t.bind(ids)
            self.assertEqual(len(t.brains),6)
            self.assertTrue(all(b.blueprint is not None
                                for b in t.brains.values()))
            t.turn=9
            agreement_id="g11-unique-world-agreement-1"
            t.agreements[agreement_id]={
                "proposer":"ari","recipient":"iona","state":"pending",
                "revision":1,"turn":8,
            }
            choice, proposal, audit=asyncio.run(
                t.g11_routed_contract_reply(
                    "iona","ari","decline",agreement_id,ids,40,68,True,
                ))
            self.assertIn(choice,("accept","defer","decline"))
            self.assertIsNotNone(proposal)
            self.assertEqual(audit["baseline"],"decline")
            self.assertEqual(audit["chosen"],choice)
            self.assertEqual(proposal.action.character_id,ids["iona"])
            self.assertEqual(proposal.action.verb,"reply_"+choice)
            self.assertEqual(proposal.action.target,"social")
            self.assertEqual(t.agreements[agreement_id]["state"],"pending")
            self.assertEqual(len(t.contract_audit),0)
            if proposal.route.selected=="llm":
                self.assertEqual(len(t.brains["iona"].pending_requests),1)
                self.assertEqual(len(t.brains["ari"].pending_requests),0)
            else:
                self.assertEqual(choice,"decline")
                self.assertFalse(t.brains["iona"].pending_requests)
            self.assertTrue(all(x["state"]=="pending"
                                for x in t.agreements.values()))
            with self.assertRaises(PermissionError):
                asyncio.run(t.g11_routed_contract_reply(
                    "lin","ari","accept",agreement_id,ids,50,50,False))
            with self.assertRaises(PermissionError):
                asyncio.run(t.g11_routed_contract_reply(
                    "iona","captain","accept",agreement_id,ids,50,50,False))
            # A checkpoint during an undecided/unknown world reply cannot
            # be restarted as though the previous offer was never seen.
            t.save()
            with self.assertRaisesRegex(RuntimeError,"world reconciliation"):
                m.Trial(241,root,cognition_mode="decider",
                        contract_routing=True)


if __name__=="__main__":
    unittest.main()
