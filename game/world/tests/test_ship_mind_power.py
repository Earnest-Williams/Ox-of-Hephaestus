"""Lead-mind core: electrical fault-domain and finite-reserve contracts."""
from __future__ import annotations

import copy
import json
import unittest

from world.ship_mind_power import (
    MIN_SURVIVORS, MindPowerError, default_design_path, fault_components,
    initial_reserve_ledger, live_machines, load_design, proposed_world_rows,
    single_fault_sweep, spend_reserve, survey_reserve, validate_design,
    validate_reserve_ledger, validate_fitted_source_routes,
)


class CorePowerTopologyTests(unittest.TestCase):
    def setUp(self):
        self.design = load_design()

    def test_loads_versioned_candidate_from_real_repo(self):
        self.assertTrue(default_design_path().exists())
        self.assertTrue(validate_design(self.design))
        islands = self.design["islands"]
        self.assertEqual(len(islands), 5)
        self.assertEqual(sum(len(i["machines"]) for i in islands), 9)
        self.assertEqual(sorted(len(i["machines"]) for i in islands), [1, 2, 2, 2, 2])
        self.assertEqual(self.design["source_nodes"], {
            "A": "PWR-MSB-A", "B": "PWR-MSB-B"})

    def test_all_single_domain_faults_leave_seven_machines(self):
        failed = single_fault_sweep(self.design)
        self.assertGreater(len(failed), 70)
        self.assertLessEqual(max(failed.values()), 2)
        for island in self.design["islands"]:
            self.assertEqual(failed[island["distribution_node"]],  # entire island
                             len(island["machines"]))
        self.assertEqual(failed["PWR-PROT"], 0)
        self.assertEqual(failed["BAT-COMMON-PROT"], 0)
        self.assertTrue(all(v <= 9 - MIN_SURVIVORS for v in failed.values()))

    def test_both_original_main_boards_are_true_alternatives(self):
        for working in ({"PWR-MSB-A"}, {"PWR-MSB-B"}):
            self.assertEqual(len(live_machines(
                self.design, energized_main_nodes=working)), 9)
        # Dead grid and unsurveyed reserves may never magically power compute.
        self.assertEqual(live_machines(
            self.design, energized_main_nodes=set()), frozenset())

    def test_one_final_contact_and_one_backbone_cut_are_local(self):
        island = self.design["islands"][0]
        a, b = island["machines"]
        self.assertNotIn(a["id"], live_machines(
            self.design, failed={a["isolator"]}))
        self.assertIn(b["id"], live_machines(
            self.design, failed={a["isolator"]}))
        self.assertIn(a["id"], live_machines(
            self.design, failed={a["backbone_links"][0]}))
        self.assertNotIn(a["id"], live_machines(
            self.design, failed=set(a["backbone_links"])))

    def test_reserved_energy_must_be_surveyed_before_any_credit(self):
        reserves = {island["local_reserve"]["id"]: 1.0
                    for island in self.design["islands"]}
        # Only a measured and explicitly supplied reserve ledger is credited.
        self.assertEqual(live_machines(
            self.design, energized_main_nodes=set()), frozenset())
        self.assertEqual(len(live_machines(
            self.design, energized_main_nodes=set(),
            surveyed_reserves=reserves)), 9)
        reserves[self.design["islands"][0]["local_reserve"]["id"]] = .001
        self.assertEqual(len(live_machines(
            self.design, energized_main_nodes=set(),
            surveyed_reserves=reserves)), 7)

    def test_ten_candidate_taps_follow_existing_installed_g19_paths(self):
        ship_file = default_design_path().with_name("ox_full_ship_v0.5_candidate.json")
        fitted = json.loads(ship_file.read_text(encoding="utf-8"))
        report = validate_fitted_source_routes(self.design, fitted)
        self.assertEqual(report["independent_input_routes"], 10)
        self.assertEqual(report["candidate_new_feed_routes_verified"], 10)
        self.assertEqual(report["candidate_machine_final_routes_verified"], 9)
        self.assertEqual(report["candidate_machines"], 9)
        self.assertEqual(report["candidate_islands"], 5)
        self.assertEqual(report["future_world_rows"], 96)
        self.assertGreaterEqual(report["original_feeders_traced"], 12)
        hab = next(i for i in self.design["islands"] if i["region"] == "HAB")
        b = next(f for f in hab["inputs"] if f["source"] == "B")
        self.assertIn("EDGE-ROT-PWR-B", b["route_domains"])
        self.assertIn("EDGE-PWR-B-BR-07", b["route_domains"])
        self.assertIn("EDGE-PWR-B-BR-04", b["route_domains"])
        self.assertEqual(b["tap_node"], "NODE-HAB-04-PDB-B")

    def test_fabricated_cable_shortcut_or_misplaced_terminal_is_rejected(self):
        fitted = json.loads(default_design_path().with_name(
            "ox_full_ship_v0.5_candidate.json").read_text(encoding="utf-8"))
        shortcuts = copy.deepcopy(self.design)
        cable = shortcuts["islands"][0]["inputs"][1]
        self.assertGreater(len(cable["proposed_cable_route_spaces"]), 2)
        cable["proposed_cable_route_spaces"] = [
            cable["proposed_cable_route_spaces"][0],
            cable["proposed_cable_route_spaces"][-1]]
        with self.assertRaises(MindPowerError):
            validate_fitted_source_routes(shortcuts, fitted)
        misplaced = copy.deepcopy(self.design)
        machine = misplaced["islands"][0]["machines"][0]
        machine["proposed_final_route_spaces"] = [
            misplaced["islands"][0]["control_room"], machine["room"]]
        with self.assertRaises(MindPowerError):
            validate_fitted_source_routes(misplaced, fitted)

    def test_shared_corridor_casualty_does_not_remove_three_machines(self):
        for corridor in ("TRUNK-A-BOW", "TRUNK-A-HAB-HUB-SERVICES",
                         "HAB-04-COR", "XCON-AFT"):
            with self.subTest(corridor=corridor):
                survivors = live_machines(self.design, failed={corridor})
                self.assertGreaterEqual(len(survivors), 7)
        # The HAB's two feeder routes share a local corridor: an actual
        # incident there removes both local feeds, unless surveyed reserve
        # sustains the island. An upstream A/B source selector cannot help.
        self.assertEqual(len(live_machines(
            self.design, failed={"HAB-04-COR"})), 7)

    def test_false_legacy_path_or_hidden_isolator_fails_source_proof(self):
        fitted = json.loads(default_design_path().with_name(
            "ox_full_ship_v0.5_candidate.json").read_text(encoding="utf-8"))
        damaged = copy.deepcopy(self.design)
        feed = damaged["islands"][0]["inputs"][0]
        feed["route_domains"][1] = "EDGE-DB-A-DR-01"
        with self.assertRaises(MindPowerError):
            validate_fitted_source_routes(damaged, fitted)
        damaged = copy.deepcopy(self.design)
        feed = damaged["islands"][0]["inputs"][0]
        feed["route_domains"].remove("ISO-DB-A-BOW")
        with self.assertRaises(MindPowerError):
            validate_fitted_source_routes(damaged, fitted)

    def test_protected_bus_or_battery_never_energises_an_island(self):
        elements = set(fault_components(self.design))
        self.assertIn("PWR-PROT", elements)
        self.assertIn("BAT-COMMON-PROT", elements)
        for island in self.design["islands"]:
            for feed in island["inputs"]:
                self.assertNotIn("PWR-PROT", feed["route_domains"])
                self.assertNotIn("BAT-COMMON-PROT", feed["route_domains"])

    def test_reject_shared_a_b_route_component(self):
        broken = copy.deepcopy(self.design)
        first, second = broken["islands"][0]["inputs"]
        second["route_domains"][1] = first["route_domains"][1]
        with self.assertRaises(MindPowerError):
            validate_design(broken)

    def test_reject_protected_bus_in_a_feed(self):
        broken = copy.deepcopy(self.design)
        broken["islands"][0]["inputs"][0]["route_domains"][1] = "PWR-PROT"
        with self.assertRaises(MindPowerError):
            validate_design(broken)

    def test_reject_duplicate_converter_across_islands(self):
        broken = copy.deepcopy(self.design)
        broken["islands"][1]["converter"] = broken["islands"][0]["converter"]
        with self.assertRaises(MindPowerError):
            validate_design(broken)

    def test_reject_three_compute_machines_behind_one_island(self):
        broken = copy.deepcopy(self.design)
        island = broken["islands"][0]
        island["machines"].append(copy.deepcopy(broken["islands"][1]["machines"][0]))
        with self.assertRaises(MindPowerError):
            validate_design(broken)

    def test_reject_bad_reserve_rate_and_parallel_inputs(self):
        for mutation in ("rating", "both", "neither"):
            broken = copy.deepcopy(self.design)
            island = broken["islands"][0]
            if mutation == "rating":
                island["local_reserve"]["max_discharge_kw"] = 0.01
            elif mutation == "both":
                island["inputs"][1]["selected"] = True
            else:
                island["inputs"][0]["selected"] = False
            with self.subTest(mutation=mutation), self.assertRaises(MindPowerError):
                validate_design(broken)

    def test_candidate_world_rows_have_explicit_separate_contacts(self):
        rows = proposed_world_rows(self.design)
        self.assertEqual(len(rows), 96)
        self.assertEqual(sum(row["category"] == "equipment"
                             for row in rows.values()), 19)
        self.assertEqual(sum(row["category"] == "node"
                             for row in rows.values()), 19)
        self.assertEqual(sum(row["category"] == "edge"
                             for row in rows.values()), 29)
        self.assertEqual(sum(row["category"] == "isolator"
                             for row in rows.values()), 29)
        self.assertEqual(len({row["key"] for row in rows.values()}), 96)
        for row in rows.values():
            self.assertEqual(row["source_model"], "ox.lead-mind-power/1")
            if row["category"] in ("node", "edge", "isolator"):
                self.assertEqual(row["reference"]["network"], "mind_power")
            self.assertNotIn("PWR-PROT", str(row["reference"]))
        self.assertEqual(sum(row["reference"].get("kind")
                             == "one_way_island_reserve"
                             for row in rows.values()), 5)
        self.assertEqual(sum(row["reference"].get("kind") == "island_infeed"
                             for row in rows.values()), 10)
        self.assertEqual(sum(row["reference"].get("kind")
                             == "dedicated_compute_feeder"
                             for row in rows.values()), 9)


class CoreReserveAccountingTests(unittest.TestCase):
    def setUp(self):
        self.design = load_design()
        self.island = self.design["islands"][0]
        self.name = self.island["local_reserve"]["id"]
        self.ledger = initial_reserve_ledger(self.design)

    def test_uncommissioned_nameplate_is_not_energy(self):
        self.assertTrue(validate_reserve_ledger(self.design, self.ledger))
        self.assertFalse(self.ledger["units"][self.name]["surveyed"])
        self.assertEqual(self.ledger["units"][self.name]["charge_kwh"], 0)
        result, powered = spend_reserve(
            self.design, self.ledger, self.island["id"], seconds=30)
        self.assertFalse(powered)
        self.assertEqual(result["meter"]["delivered_kwh"], 0)
        self.assertAlmostEqual(result["meter"]["unserved_kwh"], 4 * 30 / 3600)

    def test_survey_and_bounded_draw_reconcile(self):
        ledger = survey_reserve(self.design, self.ledger, self.name,
                                capacity_kwh=.5, charge_kwh=.25)
        self.assertEqual(self.ledger["units"][self.name]["charge_kwh"], 0)
        after, powered = spend_reserve(
            self.design, ledger, self.island["id"], seconds=30)
        self.assertTrue(powered)
        self.assertAlmostEqual(after["meter"]["delivered_kwh"], 4 * 30 / 3600)
        self.assertAlmostEqual(after["units"][self.name]["charge_kwh"],
                               .25 - 4 * 30 / 3600)
        self.assertTrue(validate_reserve_ledger(self.design, after))
        with self.assertRaises(MindPowerError):
            survey_reserve(self.design, after, self.name,
                           capacity_kwh=.5, charge_kwh=.5)

    def test_exhaustion_records_unserved_energy(self):
        ledger = survey_reserve(self.design, self.ledger, self.name,
                                capacity_kwh=.01, charge_kwh=.01)
        after, powered = spend_reserve(
            self.design, ledger, self.island["id"], seconds=30)
        self.assertFalse(powered)
        self.assertAlmostEqual(after["units"][self.name]["charge_kwh"], 0)
        self.assertAlmostEqual(after["meter"]["delivered_kwh"], .01)
        self.assertAlmostEqual(after["meter"]["unserved_kwh"],
                               4 * 30 / 3600 - .01)
        again, powered = spend_reserve(
            self.design, after, self.island["id"], seconds=10)
        self.assertFalse(powered)
        self.assertAlmostEqual(again["meter"]["delivered_kwh"], .01)

    def test_reserves_cannot_be_transferred_between_islands(self):
        ledger = survey_reserve(self.design, self.ledger, self.name,
                                capacity_kwh=.5, charge_kwh=.5)
        other = self.design["islands"][4]
        other_name = other["local_reserve"]["id"]
        ledger = survey_reserve(self.design, ledger, other_name,
                                capacity_kwh=.5, charge_kwh=.4)
        updated, powered = spend_reserve(
            self.design, ledger, self.island["id"], seconds=40)
        self.assertTrue(powered)
        self.assertEqual(updated["units"][other_name], ledger["units"][other_name])

    def test_no_oversurvey_or_negative_or_oversized_tick(self):
        for capacity, charge in ((1.01, 1.0), (1.0, 1.01),
                                 (0.0, 0.0), (1.0, -1)):
            with self.subTest(capacity=capacity, charge=charge):
                with self.assertRaises(MindPowerError):
                    survey_reserve(self.design, self.ledger, self.name,
                                   capacity_kwh=capacity, charge_kwh=charge)
        with self.assertRaises(MindPowerError):
            spend_reserve(self.design, self.ledger, self.island["id"], seconds=61)

    def test_corrupt_meter_and_conservation_fail_closed(self):
        broken = copy.deepcopy(self.ledger)
        broken["meter"]["delivered_kwh"] += 1
        with self.assertRaises(MindPowerError):
            validate_reserve_ledger(self.design, broken)
        broken = copy.deepcopy(self.ledger)
        broken["units"][self.name]["charge_kwh"] = 1
        with self.assertRaises(MindPowerError):
            validate_reserve_ledger(self.design, broken)


if __name__ == "__main__":
    unittest.main()
