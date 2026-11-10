"""Ship-control backbone and thermal-support infrastructure acceptance."""
from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace

from world.ship_mind_power import (
    MindPowerError,
    default_design_path,
    fault_components,
    live_machines,
    load_design,
)
from world.ship_mind_support import (
    air_rejection_rates,
    connected_machines,
    data_penetrations,
    default_support_path,
    fault_domains,
    initial_cooling_ledger,
    load_support,
    lt_rejection_rates,
    migrate_cooling_ledger,
    proposed_heat_connection_rows,
    proposed_support_rows,
    single_fault_network_sweep,
    step_cooling_buffer,
    survey_cooling_buffer,
    survey_signature,
    validate_cooling_ledger,
    validate_support,
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
            "rotary_data_couplers":2,"thermal_islands":5,"machines":9,
            "gateway_hosts":1,"secured_racks":1})
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

    def test_joint_single_fault_power_network_and_two_minute_cooling(self):
        # A common room, source board, rotary coupler or machine-final part
        # can affect power and data simultaneously. Proving each graph alone
        # is insufficient; evaluate their intersection with finite heat
        # and reserves over the entire required 120-second interval.
        reserves={
            isl["local_reserve"]["id"]:1.0 for isl in self.design["islands"]}
        coolant=initial_cooling_ledger(self.support)
        for pod in self.support["cooling_islands"]:
            coolant=survey_cooling_buffer(
                self.support,coolant,pod["independent_buffer_id"],
                capacity_kj=720,free_kj=720)
        domains=sorted(set(fault_components(self.design))
                       |set(fault_domains(self.support)))
        self.assertGreater(len(domains),140)
        for domain in domains:
            with self.subTest(single_fault=domain):
                live=live_machines(
                    self.design,failed={domain},
                    surveyed_reserves=reserves)
                thermal=copy.deepcopy(coolant)
                failed=set()
                for _ in range(2):
                    thermal,trips,_=step_cooling_buffer(
                        self.support,thermal,
                        operating_machines=live,
                        seconds=60,failed={domain})
                    failed.update(trips)
                connected=connected_machines(
                    self.support,faults={domain},
                    available_machines=set(live)-failed)
                self.assertGreaterEqual(
                    len(connected),7,
                    "Joint 120-second failure removed too many: "+domain)

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
                         {"XCON-GAP-23","TRUNK-B-GAP-23"})
        self.assertIn("passable",self.support["design_decisions"][
            "rack_cross_connection"])

    def test_dual_homed_machine_is_not_an_implicit_cross_rail_router(self):
        # Cutting different rails at different ends must not allow the
        # same compute NIC to forward traffic between independent spines.
        # A real A/B network bridge would need its own commissioned row.
        cases={"NET-SPAN-A-10","NET-SPAN-B-21"}
        group=connected_machines(self.support,faults=cases)
        self.assertEqual(len(group),7)
        self.assertLess(len(group),9)

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

    def test_gateway_is_only_unverified_hardware_not_remote_permission(self):
        gateway=self.support["gateway_candidates"][0]
        self.assertFalse(gateway["remote_authority"])
        self.assertFalse(gateway["command_enabled"])
        self.assertEqual(gateway["mapping_revision"],0)
        self.assertEqual(gateway["host_equipment"],"LCS-DR-03")
        self.assertEqual(gateway["room"],"BE-05-SVC")
        a,b=gateway["rail_drops"]
        self.assertIn("TRUNK-B-DR-03",a["route_spaces"])
        self.assertIn("TRUNK-B-DR-03",b["route_spaces"])
        rows=proposed_support_rows(self.support,self.design,self.ship)
        fitted=rows["equipment:GW-LCS-DR-03"]["reference"]
        self.assertFalse(fitted["remote_authority"])
        self.assertFalse(fitted["power_verified"])
        self.assertFalse(fitted["command_enabled"])
        rack=rows["equipment:MIND-03-SECURE-RACK"]["reference"]
        self.assertFalse(rack["reader_commissioned"])
        self.assertEqual(rack["passage_doors_unchanged"],
            ["ACC-XCON-GAP-23-A","ACC-XCON-GAP-23-B"])
        unsafe=copy.deepcopy(self.support)
        unsafe["gateway_candidates"][0]["remote_authority"]=True
        with self.assertRaises(MindPowerError):
            validate_support(unsafe,self.design,self.ship)

    def test_proposed_rows_are_new_fitted_data_not_power_authority(self):
        rows=proposed_support_rows(self.support,self.design,self.ship)
        self.assertEqual(len(rows),153)
        self.assertEqual(sum(x["category"]=="node" for x in rows.values()),66)
        self.assertEqual(sum(x["category"]=="edge" for x in rows.values()),64)
        self.assertEqual(sum(x["category"]=="equipment" for x in rows.values()),23)
        self.assertEqual(len({x["key"] for x in rows.values()}),153)
        self.assertTrue(
            {row["source_id"] for row in rows.values()}
            <= set(fault_domains(self.support)))
        for r in rows.values():
            self.assertEqual(r["source_model"],"ox.ship-support/1")
            if r["category"] in {"edge","node"}:
                self.assertEqual(r["reference"]["network"],"mind_data")
        for pod in self.support["cooling_islands"]:
            self.assertIn("equipment:"+pod["independent_buffer_id"],rows)
        self.assertIn("equipment:NET-ROT-A",rows)
        self.assertIn("equipment:NET-ROT-B",rows)

    def test_fitted_conductors_need_surveys_and_repairs_invalidate_them(self):
        """Drawing a route and fitting a row cannot prove live continuity."""
        rows = {
            key: SimpleNamespace(**spec, revision=1)
            for key, spec in proposed_support_rows(self.support, self.design, self.ship).items()
        }
        self.assertFalse(connected_machines(self.support, physical_rows=rows))
        for row in rows.values():
            if row.category == "edge" or row.source_id in {"NET-ROT-A", "NET-ROT-B"}:
                row.details["data_survey"] = {
                    "version": 1,
                    "row_revision": 1,
                    "observed_s": 1000,
                    "reference_sha256": survey_signature(row.reference),
                    "evidence_id": "test-physical-continuity",
                    "pressure_penetrations": [],
                    "continuity_verified": True,
                    "pressure_verified": True,
                    "environment_verified": True,
                    "emi_verified": True,
                    "continuous_rpm": 3.6 if row.category == "equipment" else None,
                }
        self.assertEqual(len(connected_machines(self.support, physical_rows=rows)), 9)
        for rail in ("A", "B"):
            row = rows["equipment:NET-ROT-" + rail]
            row.condition = "failed"
            row.revision += 1
            row.condition = "serviceable"
            row.revision += 1
        self.assertEqual(len(connected_machines(self.support, physical_rows=rows)), 7)

    def test_penetrations_follow_actual_pressure_boundaries(self):
        """A drawn branch carries all intervening pressure-seal obligations."""
        rows = proposed_support_rows(self.support, self.design, self.ship)
        self.assertEqual(
            data_penetrations(rows["edge:NET-SPAN-A-00"]["reference"], self.ship),
            ["ACC-TRUNK-A-BOW-DR-01"],
        )
        drop = rows["edge:NET-DROP-A-MIND-01"]["reference"]
        self.assertGreater(len(data_penetrations(drop, self.ship)), 1)

    def test_thermal_pipes_do_not_invent_moving_frame_crossings(self):
        """HAB pipes start behind an original rotary LT interface."""
        rows = proposed_heat_connection_rows(self.support, self.design, self.ship)
        self.assertEqual(len(rows), 15)
        self.assertEqual(
            rows["edge:LT-FEED-HAB"]["reference"]["from_node"], "NODE-HAB-04-LT-COOLING-MAN"
        )
        self.assertEqual(rows["isolator:ISO-MIND-LT-BOW"]["setting"], "closed")
        wrong = copy.deepcopy(self.support)
        wrong["cooling_islands"][0]["lt_connection"]["route_spaces"] = ["ROTARY-UTIL-A", "ENV-FWD"]
        with self.assertRaises(MindPowerError):
            validate_support(wrong, self.design, self.ship)

    def test_lt_transfer_requires_actual_valves_and_one_finite_radiator_budget(self):
        """Surveyed nameplate output cannot bypass its source or double-spend LT."""
        support_rows = {
            key: SimpleNamespace(**spec, revision=1)
            for key, spec in proposed_support_rows(self.support, self.design, self.ship).items()
        }
        circuits = {
            key: SimpleNamespace(**spec, revision=1)
            for key, spec in proposed_heat_connection_rows(
                self.support, self.design, self.ship
            ).items()
        }
        for pod in self.support["cooling_islands"]:
            feed = pod["lt_connection"]
            valve = circuits["isolator:" + feed["isolator"]]
            valve.setting = "open"
            parts = [
                circuits[c + ":" + feed[k]]
                for c, k in (("edge", "id"), ("node", "node"), ("isolator", "isolator"))
            ]
            row = support_rows["equipment:" + pod["heat_rejector_id"]]
            row.details["cooling_survey"] = {
                "version": 1,
                "row_revision": 1,
                "observed_s": 1000,
                "reference_sha256": survey_signature(row.reference),
                "evidence_id": "actual-LT-output",
                "measured_kw": pod["peak_rejection_kw"],
                "sink_kind": "lt",
                "connection_revisions": {p.key: p.revision for p in parts},
            }
        args = dict(
            physical_rows=support_rows,
            connection_rows=circuits,
            connected_lt_nodes={"NODE-LT-PLANT", "NODE-HAB-04-LT-COOLING-MAN"},
            powered_machines={"MIND-%02d" % n for n in range(1, 10)},
            cooling_budget_kw=8,
        )
        self.assertEqual(sum(lt_rejection_rates(self.support, **args).values()), 8)
        self.assertEqual(
            sum(lt_rejection_rates(self.support, **dict(args, cooling_budget_kw=0)).values()), 0
        )
        self.assertEqual(
            sum(lt_rejection_rates(self.support, **dict(args, connected_lt_nodes=set())).values()),
            0,
        )
        pod = self.support["cooling_islands"][0]
        valve = circuits["isolator:" + pod["lt_connection"]["isolator"]]
        valve.setting = "closed"
        self.assertEqual(lt_rejection_rates(self.support, **args)[pod["id"]], 0)
        valve.setting = "open"
        valve.revision += 1
        self.assertEqual(lt_rejection_rates(self.support, **args)[pod["id"]], 0)


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

    def test_spare_rejection_recovers_only_actual_stored_heat(self):
        """Buffers recover by exporting the same heat to a receiving sink."""
        self.survey_all()
        pod = self.support["cooling_islands"][0]
        self.ledger, _, _ = step_cooling_buffer(
            self.support, self.ledger, operating_machines=pod["machines"], seconds=20
        )
        before = self.ledger["units"][pod["independent_buffer_id"]]
        self.assertEqual(before["free_kj"], 640)
        after, trips, receipts = step_cooling_buffer(
            self.support,
            self.ledger,
            operating_machines=pod["machines"],
            seconds=10,
            measured_rejection_kw={pod["id"]: 5},
        )
        bank = after["units"][pod["independent_buffer_id"]]
        self.assertFalse(trips)
        self.assertEqual(bank["free_kj"], 650)
        self.assertEqual(receipts[pod["id"]]["rejected_kj"], 50)
        self.assertEqual(bank["generated_kj"], 120)
        self.assertEqual(bank["absorbed_kj"], 80)
        self.assertEqual(bank["recovered_kj"], 10)
        corrupt = copy.deepcopy(after)
        corrupt["units"][pod["independent_buffer_id"]]["free_kj"] += 1
        with self.assertRaises(MindPowerError):
            validate_cooling_ledger(self.support, corrupt)

    def test_legacy_migration_preserves_used_cold_and_all_meters(self):
        """Upgrading custody fields cannot recharge a partially used store."""
        self.survey_all()
        self.ledger, _, _ = step_cooling_buffer(
            self.support, self.ledger, operating_machines=["MIND-01"], seconds=10
        )
        old = copy.deepcopy(self.ledger)
        old["version"] = 1
        for unit in old["units"].values():
            unit.pop("initial_free_kj")
            unit.pop("recovered_kj")
        self.assertEqual(migrate_cooling_ledger(self.support, old), self.ledger)
        self.assertEqual(migrate_cooling_ledger(self.support, self.ledger), self.ledger)
        corrupt = copy.deepcopy(old)
        bank = next(iter(corrupt["units"].values()))
        bank["free_kj"] = 720
        with self.assertRaises(MindPowerError):
            migrate_cooling_ledger(self.support, corrupt)

    def test_air_rejection_requires_survey_power_and_a_cool_pressurised_sink(self):
        """No fan power, hot/vacuum receiver or failed apparatus earns cooling."""
        rows = {}
        zones = {}
        cells = {}
        for pod in self.support["cooling_islands"]:
            name = pod["heat_rejector_id"]
            reference = {"id": name}
            rows["equipment:" + name] = SimpleNamespace(
                reference=reference, revision=1, condition="serviceable", details={}
            )
            zone = "PZ-" + pod["region"]
            zones[pod["service_room"]] = zone
            cells[zone] = {"temperature": 293.15, "capacity": 1000, "volume": 100, "mass": 120}
        args = dict(
            physical_rows=rows,
            cells=cells,
            room_zones=zones,
            seconds=10,
            powered_machines={"MIND-01", "MIND-02"},
        )
        pod = self.support["cooling_islands"][0]
        self.assertEqual(air_rejection_rates(self.support, **args)[pod["id"]], 0)
        row = rows["equipment:" + pod["heat_rejector_id"]]
        row.details["cooling_survey"] = {
            "version": 1,
            "row_revision": 1,
            "observed_s": 1000,
            "reference_sha256": survey_signature(row.reference),
            "evidence_id": "physical-air-output",
            "measured_kw": 5,
            "sink_kind": "air",
        }
        self.assertEqual(air_rejection_rates(self.support, **args)[pod["id"]], 5)
        self.assertEqual(
            air_rejection_rates(self.support, **dict(args, powered_machines=set()))[pod["id"]], 0
        )
        cell = cells[zones[pod["service_room"]]]
        cell["temperature"] = pod["normal_temperature_max_k"]
        self.assertEqual(air_rejection_rates(self.support, **args)[pod["id"]], 0)
        cell["temperature"] = 293.15
        cell["mass"] = 0
        self.assertEqual(air_rejection_rates(self.support, **args)[pod["id"]], 0)
        cell["mass"] = 120
        row.condition = "failed"
        self.assertEqual(air_rejection_rates(self.support, **args)[pod["id"]], 0)


if __name__=="__main__":
    unittest.main()
