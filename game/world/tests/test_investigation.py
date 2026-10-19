"""G3e-1: one hidden physical cause with independent, fallible evidence."""
from unittest.mock import patch
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.investigation import arm_anomaly, take_sample
from world.event_journal import inbox
from world.models import InvestigationCase, WorkReceipt, CrewEvent
from world.work_actions import execute_work

class InvestigationTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()
        self.cid = arm_anomaly(cause="scrubber_bypass", seed=7)

    def test_initial_notices_do_not_reveal_solution_or_other_samples(self):
        for name in ("officer", "watch", "chief", "cargo", "environment"):
            notices = [e for e in inbox(self.ship[name]) if e["kind"] == "anomaly_notice"]
            self.assertEqual(len(notices), 1)
            self.assertEqual(notices[0]["data"], {"case_id": self.cid, "symptom": "analyzer_disagreement"})
            self.assertNotIn("scrubber_bypass", str(notices))
            self.assertNotIn("elevated", str(notices))
        with self.assertRaises(RuntimeError):
            arm_anomaly(seed=8)

    def test_firsthand_sample_authority_and_one_world_reading(self):
        mara = self.ship["cargo"]
        original = take_sample(mara, self.cid)
        self.assertIn(original["reading"], ("baseline", "elevated"))
        self.assertEqual(take_sample(mara, self.cid), original)
        self.assertEqual([e["kind"] for e in inbox(mara)].count("anomaly_sampled"), 1)
        mara.move_to(self.ship["bridge"], quiet=True)
        self.assertIsNone(take_sample(mara, self.cid))
        denied = execute_work(mara, "a"*32, "anomaly_report", arguments={"case_id":self.cid})
        self.assertEqual(denied["status"], "failed")
        mara.move_to(self.ship["cargo_room"], quiet=True) if "cargo_room" in self.ship else mara.move_to(self.ship["cradle"].location, quiet=True)
        self.assertEqual(execute_work(mara,"b"*32,"anomaly_report",arguments={"case_id":self.cid})["status"],"succeeded")

    def test_case_cannot_be_assessed_without_cross_department_reports(self):
        lin = self.ship["officer"]
        refusal = execute_work(lin, "c"*32, "anomaly_assess",arguments={"case_id":self.cid,"hypothesis":"cargo_vapors"})
        self.assertEqual(refusal["status"],"failed")
        for role in ("officer", "watch", "cargo"):
            person=self.ship[role]
            self.assertIsNotNone(take_sample(person,self.cid))
            result=execute_work(person, {"officer":"1","watch":"2","cargo":"3"}[role]*32,"anomaly_report",arguments={"case_id":self.cid})
            self.assertEqual(result["status"],"succeeded")
        verdict=execute_work(lin,"4"*32,"anomaly_assess",arguments={"case_id":self.cid,"hypothesis":"cargo_vapors"})
        self.assertEqual(verdict["status"],"succeeded")
        self.assertEqual(execute_work(lin,"4"*32,"anomaly_assess",arguments={"case_id":self.cid,"hypothesis":"cargo_vapors"}),verdict)
        case=InvestigationCase.objects.get(pk=self.cid)
        self.assertEqual(case.cause,"scrubber_bypass")
        self.assertEqual(case.assessment["hypothesis"],"cargo_vapors")
        self.assertEqual(case.assessment["verification"],"unconfirmed")
        self.assertNotIn("scrubber_bypass",str([e for e in inbox(lin) if e["kind"].startswith("anomaly_")]))
        self.assertEqual(execute_work(lin,"5"*32,"anomaly_assess",arguments={"case_id":self.cid,"hypothesis":"scrubber_bypass"})["status"],"failed")

    def test_failed_second_notification_rolls_back_report_and_receipt(self):
        from world import investigation
        mara=self.ship["cargo"]
        take_sample(mara,self.cid)
        before=CrewEvent.objects.count()
        original=investigation.emit
        calls=0
        def broken(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==2: raise RuntimeError("injected journal failure")
            return original(*args,**kwargs)
        with patch.object(investigation,"emit",side_effect=broken):
            with self.assertRaises(RuntimeError):
                execute_work(mara,"f"*32,"anomaly_report",arguments={"case_id":self.cid})
        self.assertEqual(CrewEvent.objects.count(),before)
        self.assertFalse(WorkReceipt.objects.filter(pk="f"*32).exists())
        self.assertEqual(InvestigationCase.objects.get(pk=self.cid).reports,{})
        self.assertEqual(execute_work(mara,"f"*32,"anomaly_report",arguments={"case_id":self.cid})["status"],"succeeded")
