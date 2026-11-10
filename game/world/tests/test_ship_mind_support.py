"""Ship-control backbone and thermal-support infrastructure acceptance."""
from __future__ import annotations

import copy
import json
import unittest

from world.ship_mind_power import (
    MindPowerError, load_design, default_design_path,
    live_machines,
)
from world.ship_mind_support import (
    connected_machines, default_support_path, fault_domains,
    initial_cooling_ledger, load_support, proposed_support_rows,
    single_fault_network_sweep, step_cooling_buffer, survey_cooling_buffer,
    validate_cooling_ledger, validate_support,
)


class ShipSupportDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ship=json.loads(default_design_path().with_name(
            "ox_full_ship_v0.5_candidate.json").read_text(encoding="utf-8"))
        cls.design=load_design()
        cls.support=load_support()

    def test_actual_ship_geometry_and_two_physically_separate_rails(self):
        self.assertTrue(default_support_path().exists())
        report=validate_support(self.support,self.design,self.ship)
        self.assertEqual(report,{
            "backbone_spans":44,"machine_drops":18,
            "rotary_data_couplers":2,"thermal_islands":5,"machines":9})
        self.assertEqual(len(connected_machines(self.support)),9)
        self.assertEqual(len(fault_domains(self.support)) > 90,True)

    def test_every_single_data_fault_leaves_a_seven_machine_cohort(self):
        result=single_fault_network_sweep(
            self.support,self.design,self.ship)
        self.assertGreater(len(result),90)
        self.assertLessEqual(max(result.values()),2)
        for token in ("NET-ROT-A","NET-ROT-B","TRUNK-A-HAB-HUB-SERVICES",
                      "TRUNK-B-GAP-23","NET-SPAN-A-13"):
            self.assertIn(token,result)
            self.assertLessEqual(result[token],2)

    def test_two_independent_hab_crossings_not_passenger_indexer(self):
        drops=[d for d in self.support["backbone"]["drops"]
               if d["region"]=="HAB"]
        self.assertEqual(len(drops),4)
        self.assertEqual({d["rotary_coupler"] for d in drops},
                         {"NET-ROT-A","NET-ROT-B"})
        for drop in drops:
            self.assertNotIn("IX-A-CAPSULE",drop["route_spaces"])
            self.assertNotIn("IX-B-CAPSULE",drop["route_spaces"])
        broken=copy.deepcopy(self.support)
        drop=next(d for d in broken["backbone"]["drops"]
                  if d["region"]=="HAB" and d["rail"]=="B")
        drop["rotary_coupler"]="NET-ROT-A"
        with self.assertRaises(MindPowerError):
            validate_support(broken,self.design,self.ship)

    def test_cross_trunk_rack_does_not_lock_crew_passage(self):
        matches=[l for l in self.ship["access_links"]
                 if l["id"] in {"ACC-XCON-GAP-23-A","ACC-XCON-GAP-23-B"}]
        self.assertEqual(len(matches),2)
        self.assertEqual({l["to"] for l in matches},
                         {"TRUNK-A-GAP-23","TRUNK-B-GAP-23"}
                         if False else {"XCON-GAP-23","TRUNK-B-GAP-23"})
        self.assertIn("passable",self.support["design_decisions"][
            "rack_cross_connection"])

    def test_fabricated_tunnel_and_shared_data_coupler_fail_design(self):
        wrong=copy.deepcopy(self.support)
        wrong["backbone"]["rail_rooms"]["A"][4]="TRUNK-B-GAP-23"
        with self.assertRaises(MindPowerError):
            validate_support(wrong,self.design,self.ship)
        wrong=copy.deepcopy(self.support)
        drop=wrong["backbone"]["drops"][0]
        drop["route_spaces"]=[drop["route_spaces"][0],drop["route_spaces"][-1]]
        with self.assertRaises(MindPowerError):
            validate_support(wrong,self.design,self.ship)
        wrong=copy.deepcopy(self.support)
        wrong["backbone"]["couplers"][1]["fixed_room"]="HUB-FIXED-A"
        with self.assertRaises(MindPowerError):
            validate_support(wrong,self.design,self.ship)

    def test_surviving_power_is_not_the_same_as_surviving_comms(self):
        powered=live_machines(self.design,failed={"PWR-PROT"})
        self.assertEqual(len(powered),9)
        reachable=connected_machines(
            self.support,faults={"NET-ROT-A"},available_machines=powered)
        self.assertEqual(len(reachable),9)
        neither=connected_machines(self.support,
            faults={"NET-ROT-A","NET-ROT-B"},available_machines=powered)
        self.assertEqual(len(neither),7)
        self.assertEqual(len(connected_machines(
            self.support,available_machines={"MIND-01","MIND-02"})),2)

    def test_proposed_rows_are_new_fitted_data_not_power_authority(self):
        rows=proposed_support_rows(self.support,self.design,self.ship)
        self.assertEqual(len(rows),147)
        self.assertEqual(sum(x["category"]=="node" for x in rows.values()),64)
        self.assertEqual(sum(x["category"]=="edge" for x in rows.values()),62)
        self.assertEqual(sum(x["category"]=="equipment" for x in rows.values()),21)
        self.assertEqual(len({x["key"] for x in rows.values()}),147)
        for r in rows.values():
            self.assertEqual(r["source_model"],"ox.ship-support/1")
            if r["category"] in {"edge","node"}:
                self.assertEqual(r["reference"]["network"],"mind_data")
        for pod in self.support["cooling_islands"]:
            self.assertIn("equipment:"+pod["independent_buffer_id"],rows)
        self.assertIn("equipment:NET-ROT-A",rows)
        self.assertIn("equipment:NET-ROT-B",rows)


class ShipSupportThermalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.support=load_support()
        cls.design=load_design()

    def setUp(self):
        self.ledger=initial_cooling_ledger(self.support)
        self.assertTrue(validate_cooling_ledger(self.support,self.ledger))

    def survey_all(self):
        for pod in self.support["cooling_islands"]:
            name=pod["independent_buffer_id"]
            self.ledger=survey_cooling_buffer(self.support,self.ledger,name,
                capacity_kj=720,free_kj=720)

    def test_unmeasured_cold_is_not_free_endurance(self):
        after,trips,receipts=step_cooling_buffer(
            self.support,self.ledger,operating_machines=["MIND-01"],
            seconds=10)
        self.assertEqual(trips,frozenset({"MIND-01"}))
        self.assertEqual(receipts[self.support["cooling_islands"][0]["id"]][
            "unabsorbed_kj"],20)
        self.assertTrue(validate_cooling_ledger(self.support,after))

    def test_all_nine_survive_two_minutes_on_five_surveyed_local_stores(self):
        self.survey_all()
        for _ in range(12):
            self.ledger,trips,_=step_cooling_buffer(
                self.support,self.ledger,operating_machines=sorted(
                    ["MIND-%02d"%i for i in range(1,10)]),seconds=10)
            self.assertFalse(trips)
        for pod in self.support["cooling_islands"]:
            remaining=self.ledger["units"][pod["independent_buffer_id"]]["free_kj"]
            self.assertGreaterEqual(remaining,240 if len(pod["machines"])==2 else 480)
        self.assertTrue(validate_cooling_ledger(self.support,self.ledger))

    def test_one_faulty_thermal_store_only_affects_its_assigned_machines(self):
        self.survey_all()
        for pod in self.support["cooling_islands"]:
            _,trips,_=step_cooling_buffer(
                self.support,self.ledger,
                operating_machines=["MIND-%02d"%i for i in range(1,10)],
                seconds=10,failed={pod["independent_buffer_id"]})
            self.assertEqual(trips,frozenset(pod["machines"]))

    def test_no_infinite_cold_buffer_and_no_heat_lost(self):
        self.survey_all()
        for _ in range(18):
            self.ledger,trips,_=step_cooling_buffer(
                self.support,self.ledger,operating_machines=["MIND-01","MIND-02"],
                seconds=10)
            self.assertFalse(trips)
        _,trips,_=step_cooling_buffer(
            self.support,self.ledger,
            operating_machines=["MIND-01","MIND-02"],seconds=10)
        self.assertEqual(trips,frozenset({"MIND-01","MIND-02"}))
        self.assertTrue(validate_cooling_ledger(self.support,self.ledger))

    def test_rejection_requires_explicit_measured_rate_and_conserves_heat(self):
        self.survey_all()
        name=self.support["cooling_islands"][0]["id"]
        after,trips,receipts=step_cooling_buffer(
            self.support,self.ledger,operating_machines=["MIND-01","MIND-02"],
            seconds=10,measured_rejection_kw={name:4.0})
        self.assertFalse(trips)
        self.assertEqual(receipts[name]["rejected_kj"],40)
        self.assertEqual(receipts[name]["absorbed_kj"],0)
        self.assertEqual(after["units"][self.support["cooling_islands"][0][
            "independent_buffer_id"]]["free_kj"],720)
        with self.assertRaises(MindPowerError):
            step_cooling_buffer(self.support,self.ledger,
                operating_machines=["MIND-01"],seconds=10,
                measured_rejection_kw={name:1000})

    def test_survey_cannot_create_new_cold_or_erase_existing_state(self):
        pod=self.support["cooling_islands"][0]
        name=pod["independent_buffer_id"]
        with self.assertRaises(MindPowerError):
            survey_cooling_buffer(self.support,self.ledger,name,
                                  capacity_kj=721,free_kj=720)
        self.ledger=survey_cooling_buffer(self.support,self.ledger,name,
            capacity_kj=550,free_kj=180)
        with self.assertRaises(MindPowerError):
            survey_cooling_buffer(self.support,self.ledger,name,
                capacity_kj=550,free_kj=550)
        before=copy.deepcopy(self.ledger)
        with self.assertRaises(MindPowerError):
            step_cooling_buffer(self.support,self.ledger,
                operating_machines=["MIND-01"],seconds=61)
        self.assertEqual(self.ledger,before)


if __name__=="__main__":
    unittest.main()
