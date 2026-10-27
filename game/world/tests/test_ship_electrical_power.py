"""G19 electrical physics: real source graph, finite energy and safety contracts."""
from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace as Row

from world.ship_electrical_power import (
    ElectricalError, audit_topology, connected_nodes, initial_electrical,
    validate_electrical, source_dispatch, survey_battery, step_energy,
    register_fault, step_protection, reset_protection,
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
                                 capacity_kwh=1.0, charge_kwh=.02,
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
        self.assertAlmostEqual(bank["discharged_kwh"], .65 * 10 / 3600)
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
        self.assertAlmostEqual(bank["charge_kwh"], .3 + .2 / 360)
        self.assertAlmostEqual(after["meter"]["battery_charge_kwh"],
                               .2 / 360)
        self.assertAlmostEqual(after["meter"]["generation_kwh"],
                               (1.35 + .2) / 360)
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

    def test_operational_common_battery_supplies_only_its_main_board(self):
        _, edges, switches, equipment = grid()
        equipment["GEN-M"] = eq(False)
        equipment["GEN-B"] = eq(False)
        ledger = survey_battery(initial_electrical(), "BAT-COMMON-OPS",
                                capacity_kwh=.2, charge_kwh=.02,
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
            .65 / 360)
        self.assertAlmostEqual(result["meter"]["battery_discharge_kwh"], .65 / 360)
        self.assertEqual(result["meter"]["generation_kwh"], 0)
        self.assertAlmostEqual(result["meter"]["served_kwh"], .65 / 360)
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
        self.assertAlmostEqual(updated["shore"]["import_kwh"], .65 / 360)
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

    def test_damage_to_installed_feeder_is_not_virtual_dispatch(self):
        _, edges, switches, equipment = grid()
        edges[0].condition = "severed"
        supply = source_dispatch(equipment, edges, switches, "normal")
        self.assertEqual(supply["available_mw"], .65)
        self.assertFalse(supply["assured"])
        self.assertNotIn("GEN-M", supply["active_generators"])


if __name__ == "__main__":
    unittest.main()
