"""G19 electrical physics: real source graph, finite energy and safety contracts."""
from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace as Row

from world.ship_electrical_power import (
    ElectricalError, audit_topology, connected_nodes, initial_electrical,
    validate_electrical, source_dispatch, survey_battery, step_energy,
    register_fault, step_protection, reset_protection, survey_flywheel,
    migrate_v1_electrical, FLYWHEELS,
)


def eq(online=True):
    return Row(condition="serviceable", details={"physics_online": online})


def switch(name, setting="closed"):
    return Row(source_id=name, reference={"id": name, "network": "power",
        "kind": "breaker", "current_state": setting}, condition="serviceable",
        setting=setting)


def edge(name, a, b, *, setting="available", kind="source_feed"):
    return Row(source_id=name, reference={
        "id": name, "network": "power", "from_node": a, "to_node": b,
        "isolator_ids": ["ISO-" + name[5:]], "kind": kind},
        condition="serviceable", setting=setting)


def grid():
    e = [
        edge("EDGE-GEN-M", "NODE-GEN-M", "PWR-MSB-A"),
        edge("EDGE-GEN-A", "NODE-GEN-A", "PWR-MSB-A"),
        edge("EDGE-GEN-B", "NODE-GEN-B", "PWR-MSB-B"),
        edge("EDGE-PWR-MSB-A-PROT", "PWR-MSB-A", "PWR-PROT"),
        edge("EDGE-PWR-MSB-B-PROT", "PWR-MSB-B", "PWR-PROT",
             setting="standby"),
        edge("EDGE-MSB-XTIE", "PWR-MSB-A", "PWR-MSB-B",
             setting="standby", kind="cross_tie"),
        edge("EDGE-BAT-COMMON-PROT", "NODE-BAT-COMMON-PROT", "PWR-PROT"),
        edge("EDGE-BAT-COMMON-OPS", "NODE-BAT-COMMON-OPS", "PWR-MSB-B"),
        edge("EDGE-SHORE-PWR", "NODE-SHORE-PWR", "PWR-MSB-A"),
    ]
    switches = {x.reference["isolator_ids"][0]:
                switch(x.reference["isolator_ids"][0]) for x in e}
    equipment = {"GEN-M": eq(True), "GEN-A": eq(False),
                 "GEN-B": eq(True), "BAT-COMMON-PROT": eq(), "BAT-COMMON-OPS": eq(),
                 "SHORE-PWR": eq()}
    nodes = [Row(source_id=n, reference={"id": n, "network": "power"})
             for n in sorted(set(
                 [x.reference["from_node"] for x in e] +
                 [x.reference["to_node"] for x in e]))]
    return nodes, e, switches, equipment


class ElectricalPhysicalContracts(unittest.TestCase):
    def test_source_dispatch_bounded_by_generators_and_ship_envelope(self):
        _, edges, switches, equipment = grid()
        result = source_dispatch(equipment, edges, switches, "normal")
        self.assertEqual(result["available_mw"], 3.3)
        self.assertTrue(result["assured"])
        self.assertEqual(result["active_generators"], ("GEN-B", "GEN-M"))

    def test_main_trip_requires_explicit_shedding_and_no_protected_backfeed(self):
        _, edges, switches, equipment = grid()
        equipment["GEN-M"] = eq(False)
        first = source_dispatch(equipment, edges, switches, "normal")
        self.assertEqual(first["available_mw"], .65)
        self.assertFalse(first["assured"])
        self.assertNotIn("PWR-MSB-A", first["nodes"])
        self.assertNotIn("PWR-PROT", first["nodes"])
        switches["ISO-PWR-MSB-B-PROT"].setting = "closed"
        edges[3].setting, edges[4].setting = "standby", "available"
        resumed = source_dispatch(equipment, edges, switches, "essential")
        self.assertTrue(resumed["assured"])
        self.assertIn("PWR-PROT", resumed["nodes"])
        self.assertNotIn("PWR-MSB-A", resumed["nodes"])

    def test_real_cross_tie_is_only_bidirectional_feeder(self):
        _, edges, switches, equipment = grid()
        edges[5].setting = "available"
        from_b = connected_nodes(edges, switches, ["PWR-MSB-B"])
        self.assertIn("PWR-MSB-A", from_b)
        edges[5].setting = "standby"
        self.assertNotIn("PWR-MSB-A",
                         connected_nodes(edges, switches, ["PWR-MSB-B"]))

    def test_backfeed_from_protected_bus_cannot_run_the_main(self):
        _, edges, switches, equipment = grid()
        reachable = connected_nodes(edges, switches, ["PWR-PROT"])
        self.assertNotIn("PWR-MSB-A", reachable)
        self.assertNotIn("PWR-MSB-B", reachable)

    def test_unrated_battery_not_credited_for_any_duration(self):
        _, edges, switches, equipment = grid()
        equipment["GEN-M"] = eq(False)
        equipment["GEN-B"] = eq(False)
        result = source_dispatch(equipment, edges, switches, "essential",
                                 ledger=initial_electrical())
        self.assertEqual(result["available_mw"], 0)
        self.assertEqual(result["battery_dispatched_mw"], 0)
        self.assertFalse(result["assured"])

    def test_finite_protected_battery_and_energy_conservation(self):
        _, edges, switches, equipment = grid()
        equipment["GEN-M"] = eq(False)
        equipment["GEN-B"] = eq(False)
        initial = survey_battery(initial_electrical(), "BAT-COMMON-PROT",
                                 capacity_kwh=10.0, charge_kwh=5,
                                 max_charge_mw=.1, max_discharge_mw=.65)
        initial["banks"]["BAT-COMMON-PROT"]["mode"] = "discharge"
        original = copy.deepcopy(initial)
        first = source_dispatch(equipment, edges, switches, "essential",
                                ledger=initial, dt_s=10)
        self.assertTrue(first["protected_assured"])
        self.assertTrue(first["assured"])
        self.assertEqual(first["battery_dispatched_mw"], .65)
        after = step_energy(initial, first, 10)
        bank = after["banks"]["BAT-COMMON-PROT"]
        self.assertAlmostEqual(bank["discharged_kwh"], .65 * 10 / 3.6)
        self.assertAlmostEqual(bank["charge_kwh"] + bank["discharged_kwh"],
                               bank["initial_kwh"])
        self.assertEqual(initial, original)
        self.assertTrue(validate_electrical(after))

    def test_charging_uses_only_fitted_live_feeder_and_real_surplus(self):
        _, edges, switches, equipment = grid()
        baseline = survey_battery(initial_electrical(), "BAT-COMMON-PROT",
                                  capacity_kwh=1.0, charge_kwh=.3,
                                  max_charge_mw=.2, max_discharge_mw=.4)
        baseline["banks"]["BAT-COMMON-PROT"]["mode"] = "charge"
        # Two active generators and a real protected supply provide surplus.
        full = source_dispatch(equipment, edges, switches, "normal",
                               ledger=baseline, dt_s=10)
        self.assertIn("BAT-COMMON-PROT", full["charge_feeders"])
        after = step_energy(baseline, full, 10)
        bank = after["banks"]["BAT-COMMON-PROT"]
        self.assertAlmostEqual(bank["charge_kwh"], .3 + .2 * 10 / 3.6)
        self.assertAlmostEqual(after["meter"]["battery_charge_kwh"],
                               .2 * 10 / 3.6)
        self.assertAlmostEqual(after["meter"]["generation_kwh"],
                               (1.35 + .2) * 10 / 3.6)
        self.assertTrue(validate_electrical(after))
        self.assertEqual(baseline["banks"]["BAT-COMMON-PROT"]["charge_kwh"], .3)

        switches["ISO-BAT-COMMON-PROT"].setting = "open"
        isolated = source_dispatch(equipment, edges, switches, "normal",
                                   ledger=baseline, dt_s=10)
        self.assertEqual(isolated["charge_feeders"], [])
        uncharged = step_energy(baseline, isolated, 10)
        self.assertAlmostEqual(uncharged["banks"]["BAT-COMMON-PROT"]["charge_kwh"],
                               .3)
        switches["ISO-BAT-COMMON-PROT"].setting = "closed"
        # A live but wholly utilised 0.65 MW auxiliary has no spare power.
        equipment["GEN-M"] = eq(False)
        maxed = source_dispatch(equipment, edges, switches, "essential",
                                ledger=baseline, dt_s=10)
        no_surplus = step_energy(baseline, maxed, 10)
        self.assertAlmostEqual(no_surplus["meter"]["battery_charge_kwh"], 0)

    def test_battery_does_not_supply_normal_cargo_or_drives(self):
        _, edges, switches, equipment = grid()
        equipment["GEN-M"] = eq(False)
        s = survey_battery(initial_electrical(), "BAT-COMMON-PROT",
                           capacity_kwh=10, charge_kwh=10,
                           max_charge_mw=.1, max_discharge_mw=1)
        s["banks"]["BAT-COMMON-PROT"]["mode"] = "discharge"
        power = source_dispatch(equipment, edges, switches, "normal",
                                ledger=s)
        self.assertFalse(power["assured"])
        self.assertEqual(power["available_mw"], .65)
        self.assertLessEqual(power["battery_dispatched_mw"], .1)

    def test_sixty_four_real_flywheel_names_and_nameplate_invariant(self):
        self.assertEqual(len(FLYWHEELS), 64)
        self.assertEqual(FLYWHEELS[0], "F1-FW-01")
        self.assertEqual(FLYWHEELS[-1], "F2-FW-32")
        s = survey_flywheel(initial_electrical(), "F1-FW-01",
                            capacity_kwh=3906.25, charge_kwh=12,
                            max_charge_mw=.5, max_discharge_mw=1)
        self.assertTrue(validate_electrical(s))
        with self.assertRaises(ElectricalError):
            survey_flywheel(s, "F1-FW-01", capacity_kwh=1,
                            charge_kwh=0, max_charge_mw=.1,
                            max_discharge_mw=.1)
        with self.assertRaises(ElectricalError):
            survey_flywheel(initial_electrical(), "F2-FW-32",
                            capacity_kwh=3906.26, charge_kwh=0,
                            max_charge_mw=.2, max_discharge_mw=.2)

    def test_flywheel_island_safes_against_parallel_sources_and_saves_energy(self):
        _, edges, switches, equipment = grid()
        edges.extend((
            edge("EDGE-F1-BUS-IN-1", "PWR-MSB-A", "NODE-F1-BUS",
                 kind="bank_infeed"),
            edge("EDGE-PWR-F1-FW-01", "NODE-F1-BUS",
                 "NODE-PWR-F1-FW-01", kind="module_feeder"),
        ))
        switches["ISO-F1-BUS-IN-1"] = switch("ISO-F1-BUS-IN-1")
        switches["ISO-PWR-F1-FW-01"] = switch("ISO-PWR-F1-FW-01")
        equipment["F1-FW-01"] = eq()
        account = survey_flywheel(initial_electrical(), "F1-FW-01",
                                  capacity_kwh=3906.25, charge_kwh=10,
                                  max_charge_mw=.4, max_discharge_mw=.8)
        account["flywheels"]["F1-FW-01"]["mode"] = "discharge"
        equipment["GEN-M"] = eq(False)
        equipment["GEN-B"] = eq(False)
        backup = source_dispatch(equipment, edges, switches, "essential",
                                 ledger=account, dt_s=10)
        self.assertTrue(backup["assured"])
        self.assertEqual(backup["main_available_mw"], .8)
        self.assertIn("PWR-MSB-A", backup["main_nodes"])
        self.assertEqual(backup["flywheel_available_mw"], .8)
        after = step_energy(account, backup, 10)
        self.assertAlmostEqual(after["flywheels"]["F1-FW-01"]["discharged_kwh"],
                               .65 * 10 / 3.6)
        self.assertAlmostEqual(after["meter"]["flywheel_discharge_kwh"], .65 * 10 / 3.6)
        self.assertEqual(after["meter"]["generation_kwh"], 0)
        self.assertTrue(validate_electrical(after))
        # A broken module feeder removes its energy source, not its custody.
        switches["ISO-PWR-F1-FW-01"].setting = "open"
        isolated = source_dispatch(equipment, edges, switches, "essential",
                                   ledger=after)
        self.assertFalse(isolated["assured"])
        self.assertEqual(isolated["flywheel_available_mw"], 0)
        switches["ISO-PWR-F1-FW-01"].setting = "closed"
        # No unsynchronised flywheel parallel supply while GEN-M is running.
        equipment["GEN-M"] = eq(True)
        produced = source_dispatch(equipment, edges, switches, "normal",
                                   ledger=after)
        self.assertEqual(produced["flywheel_available_mw"], 0)

    def test_flywheel_recharge_requires_live_generator_and_selected_bank(self):
        _, edges, switches, equipment = grid()
        edges.extend((
            edge("EDGE-F2-BUS-IN-1", "PWR-MSB-B", "NODE-F2-BUS",
                 kind="bank_infeed"),
            edge("EDGE-PWR-F2-FW-01", "NODE-F2-BUS",
                 "NODE-PWR-F2-FW-01", kind="module_feeder"),
        ))
        switches["ISO-F2-BUS-IN-1"] = switch("ISO-F2-BUS-IN-1")
        switches["ISO-PWR-F2-FW-01"] = switch("ISO-PWR-F2-FW-01")
        equipment["F2-FW-01"] = eq()
        s = survey_flywheel(initial_electrical(), "F2-FW-01",
                            capacity_kwh=3906.25, charge_kwh=0,
                            max_charge_mw=.2, max_discharge_mw=.5)
        s["flywheels"]["F2-FW-01"]["mode"] = "charge"
        supply = source_dispatch(equipment, edges, switches, "essential",
                                 ledger=s)
        self.assertIn("F2-FW-01", supply["charge_feeders"])
        after = step_energy(s, supply, 10)
        self.assertAlmostEqual(after["meter"]["flywheel_charge_kwh"],
                               .2 * 10 / 3.6)
        self.assertAlmostEqual(after["flywheels"]["F2-FW-01"]["charge_kwh"],
                               .2 * 10 / 3.6)
        self.assertEqual(s["flywheels"]["F2-FW-01"]["charge_kwh"], 0)
        switches["ISO-F2-BUS-IN-1"].setting = "open"
        blocked = source_dispatch(equipment, edges, switches, "essential",
                                  ledger=s)
        self.assertNotIn("F2-FW-01", blocked["charge_feeders"])

    def test_v1_electrical_migration_preserves_every_old_energy_count(self):
        v1 = initial_electrical()
        v1["version"] = 1
        del v1["flywheels"]
        del v1["meter"]["flywheel_charge_kwh"]
        del v1["meter"]["flywheel_discharge_kwh"]
        v1["meter"]["served_kwh"] = 56
        after = migrate_v1_electrical(v1)
        self.assertEqual(after["version"], 2)
        self.assertEqual(after["meter"]["served_kwh"], 56)
        self.assertTrue(validate_electrical(after))
        self.assertNotIn("flywheels", v1)

    def test_operational_common_battery_supplies_only_its_main_board(self):
        _, edges, switches, equipment = grid()
        equipment["GEN-M"] = eq(False)
        equipment["GEN-B"] = eq(False)
        ledger = survey_battery(initial_electrical(), "BAT-COMMON-OPS",
                                capacity_kwh=20, charge_kwh=10,
                                max_charge_mw=.1, max_discharge_mw=.8)
        ledger["banks"]["BAT-COMMON-OPS"]["mode"] = "discharge"
        grid_state = source_dispatch(equipment, edges, switches, "essential",
                                     ledger=ledger, dt_s=10)
        self.assertTrue(grid_state["assured"])
        self.assertIn("PWR-MSB-B", grid_state["nodes"])
        self.assertNotIn("PWR-MSB-A", grid_state["nodes"])
        self.assertEqual(grid_state["main_available_mw"], .8)
        self.assertEqual(grid_state["protected_battery_dispatched_mw"], 0)
        result = step_energy(ledger, grid_state, 10)
        self.assertAlmostEqual(
            result["banks"]["BAT-COMMON-OPS"]["discharged_kwh"],
            .65 * 10 / 3.6)
        self.assertAlmostEqual(result["meter"]["battery_discharge_kwh"], .65 * 10 / 3.6)
        self.assertEqual(result["meter"]["generation_kwh"], 0)
        self.assertAlmostEqual(result["meter"]["served_kwh"], .65 * 10 / 3.6)
        self.assertTrue(validate_electrical(result))

    def test_unconnected_main_bus_does_not_forge_delivered_energy(self):
        _, edges, switches, equipment = grid()
        # The initially cold fitted ship has very many open load breakers.
        # A live generator and main switchboard by themselves are not loads.
        branch = edge("EDGE-TEST-LOAD", "PWR-MSB-A", "NODE-ACTUAL-LOAD",
                      kind="equipment_branch")
        edges.append(branch)
        switches["ISO-TEST-LOAD"] = switch("ISO-TEST-LOAD", "open")
        supply = source_dispatch(equipment, edges, switches, "normal",
                                 ledger=initial_electrical())
        self.assertFalse(supply["assured"])
        self.assertFalse(supply["has_live_load"])
        meter = step_energy(initial_electrical(), supply, 10)
        self.assertEqual(meter["meter"]["served_kwh"], 0)
        self.assertGreater(meter["meter"]["unserved_kwh"], 0)
        switches["ISO-TEST-LOAD"].setting = "closed"
        fed = source_dispatch(equipment, edges, switches, "normal",
                              ledger=initial_electrical())
        self.assertTrue(fed["has_live_load"])
        self.assertTrue(fed["assured"])
        credited = step_energy(initial_electrical(), fed, 10)
        self.assertGreater(credited["meter"]["served_kwh"], 0)

    def test_operational_backup_cannot_add_above_ship_dispatch_envelope(self):
        _, edges, switches, equipment = grid()
        backup = survey_battery(initial_electrical(), "BAT-COMMON-OPS",
                                capacity_kwh=20, charge_kwh=20,
                                max_charge_mw=1, max_discharge_mw=3)
        backup["banks"]["BAT-COMMON-OPS"]["mode"] = "discharge"
        fed = source_dispatch(equipment, edges, switches, "demanding",
                              ledger=backup)
        self.assertEqual(fed["available_mw"], 3.3)
        self.assertEqual(fed["operational_battery_available_mw"], 0)
        after = step_energy(backup, fed, 10)
        self.assertEqual(after["meter"]["battery_discharge_kwh"], 0)

    def test_shore_needs_real_mooring_source_and_no_parallel_generator(self):
        _, edges, switches, equipment = grid()
        s = initial_electrical()
        s["shore"] = {"rated_mw": 1.2, "connected": True, "import_kwh": 0.0}
        no_mooring = source_dispatch(equipment, edges, switches, "normal",
                                     ledger=s, moored=False)
        self.assertFalse(no_mooring["shore_active"])
        equipment["GEN-M"] = eq(False)
        equipment["GEN-B"] = eq(False)
        moored = source_dispatch(equipment, edges, switches, "essential",
                                  ledger=s, moored=True)
        self.assertTrue(moored["shore_active"])
        self.assertEqual(moored["available_mw"], 1.2)
        updated = step_energy(s, moored, 10)
        self.assertAlmostEqual(updated["shore"]["import_kwh"], .65 * 10 / 3.6)
        self.assertEqual(updated["meter"]["generation_kwh"], 0)

    def test_breaker_protection_trips_once_and_requires_cleared_fault(self):
        _, edges, switches, equipment = grid()
        s = register_fault(initial_electrical(), "ISO-GEN-M",
                           rating_mw=1.0, observed_mw=2.0)
        after, tripped = step_protection(s, switches, 10)
        self.assertEqual(tripped, ("ISO-GEN-M",))
        after2, again = step_protection(after, switches, 10)
        self.assertFalse(again)
        with self.assertRaises(ElectricalError):
            reset_protection(after2, "ISO-GEN-M")
        after2["faults"]["ISO-GEN-M"]["observed_mw"] = 0
        reset = reset_protection(after2, "ISO-GEN-M")
        self.assertFalse(reset["faults"])

    def test_nonphysical_survey_and_corrupt_ledger_refused(self):
        for bad in (float("nan"), float("inf"), -1, True):
            with self.subTest(bad=bad):
                with self.assertRaises(ElectricalError):
                    survey_battery(initial_electrical(), "BAT-COMMON-PROT",
                                   capacity_kwh=5, charge_kwh=bad,
                                   max_charge_mw=.1, max_discharge_mw=.1)
        s = survey_battery(initial_electrical(), "BAT-COMMON-PROT",
                           capacity_kwh=5, charge_kwh=2,
                           max_charge_mw=.1, max_discharge_mw=.1)
        s["banks"]["BAT-COMMON-PROT"]["charge_kwh"] += 1
        with self.assertRaises(ElectricalError):
            validate_electrical(s)

    def test_audit_checks_endpoints_and_real_breakers(self):
        nodes, edges, switches, _ = grid()
        self.assertEqual(len(audit_topology(nodes, edges, switches,
                                            strict=False)[1]), 9)
        with self.assertRaises(ElectricalError):
            audit_topology(nodes, edges, switches, strict=True)
        edges[0].reference["from_node"] = "NODE-MAGIC"
        with self.assertRaises(ElectricalError):
            audit_topology(nodes, edges, switches, strict=False)

    def test_destroyed_actual_msb_or_branch_panel_blocks_current(self):
        nodes, edges, switches, equipment = grid()
        equipment["MSB-A"] = eq(True)
        equipment["MSB-B"] = eq(True)
        equipment["CAB-LP"] = eq(True)
        nodes.extend([
            Row(source_id="PWR-MSB-A", reference={
                "id": "PWR-MSB-A", "network": "power",
                "owner_type": "equipment", "owner_id": "MSB-A"}),
            Row(source_id="PWR-MSB-B", reference={
                "id": "PWR-MSB-B", "network": "power",
                "owner_type": "equipment", "owner_id": "MSB-B"}),
            Row(source_id="NODE-CAB-LP", reference={
                "id": "NODE-CAB-LP", "network": "power",
                "owner_type": "equipment", "owner_id": "CAB-LP"}),
        ])
        edges.append(edge("EDGE-CAB-LP", "PWR-MSB-A", "NODE-CAB-LP",
                          kind="room_feeder"))
        switches["ISO-CAB-LP"] = switch("ISO-CAB-LP")
        ready = source_dispatch(equipment, edges, switches, "normal",
                                ledger=initial_electrical(), nodes=nodes)
        self.assertIn("NODE-CAB-LP", ready["nodes"])
        equipment["CAB-LP"].condition = "failed"
        panel_failed = source_dispatch(equipment, edges, switches, "normal",
                                       ledger=initial_electrical(), nodes=nodes)
        self.assertNotIn("NODE-CAB-LP", panel_failed["nodes"])
        self.assertFalse(panel_failed["has_live_load"])
        equipment["CAB-LP"].condition = "serviceable"
        equipment["MSB-A"].condition = "destroyed"
        board_failed = source_dispatch(equipment, edges, switches, "normal",
                                       ledger=initial_electrical(), nodes=nodes)
        self.assertNotIn("PWR-MSB-A", board_failed["nodes"])
        self.assertNotIn("NODE-CAB-LP", board_failed["nodes"])
        self.assertNotIn("GEN-M", board_failed["active_generators"])
        self.assertFalse(board_failed["assured"])

    def test_damage_to_installed_feeder_is_not_virtual_dispatch(self):
        _, edges, switches, equipment = grid()
        edges[0].condition = "severed"
        supply = source_dispatch(equipment, edges, switches, "normal")
        self.assertEqual(supply["available_mw"], .65)
        self.assertFalse(supply["assured"])
        self.assertNotIn("GEN-M", supply["active_generators"])


if __name__ == "__main__":
    unittest.main()
