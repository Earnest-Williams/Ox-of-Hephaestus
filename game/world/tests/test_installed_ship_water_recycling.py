"""G19 water treatment on installed Evennia equipment, valves and ledgers."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_water,
    verify_g19_hydrogen_outlet, survey_g19_water_material,
    configure_water_casualty, crew_physical_action, local_physics_readout,
    tick_continuous_physics,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_component_condition, set_isolator, state,
)
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_world import build_canonical_ship, find_ship_space


class InstalledWaterRecyclingTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000.0)
        self.assertTrue(commission_g19_water(operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_water(operator_approved=True)["commissioned"])
        # All lines remain independent equipment; this is an operator
        # commissioning scenario, not fabricated fluid transfers.
        set_isolator("ISO-GEN-M", "closed", operator=True)
        for row in CanonicalShipState.objects.filter(category="isolator"):
            if row.reference.get("network") in {
                    "potable_water", "greywater", "blackwater"}:
                if row.condition in {"serviceable", "degraded"}:
                    set_isolator(row.source_id, "open", operator=True)
        self.tech = build_ship()["watch"]

    def _water(self):
        return CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["water"]

    def test_installed_network_delivers_and_recycles_with_real_receivers(self):
        stock = state("inventory", "INV-WATER-NORMAL").quantity
        report = tick_continuous_physics(now_game_time=1060)
        self.assertTrue(report["advanced"])
        self.assertIsNotNone(report["water"])
        water = report["water"]
        self.assertGreater(water["cumulative"]["domestic_used_kg"], 0)
        self.assertGreater(water["cumulative"]["water_recovered_kg"], 0)
        self.assertGreater(water["cumulative"]["sanitary_solids_kg"], 0)
        self.assertLess(state("inventory", "INV-WATER-NORMAL").quantity, stock)
        self.assertAlmostEqual(
            state("inventory", "INV-WASTE-RESIDUE").quantity * 1000,
            sum(self._water()["cassettes"]["sanitary"].values()), places=6)
        self.assertEqual(state("inventory", "INV-WATER-RESERVE").quantity, 70)
        self.assertEqual(report["water"]["cumulative"]["oxygen_from_electrolysis_kg"], 0)
        before = self._water()["cumulative"]["domestic_used_kg"]
        self.assertFalse(tick_continuous_physics(now_game_time=1060)["advanced"])
        self.assertEqual(before, self._water()["cumulative"]["domestic_used_kg"])

    def test_one_treatment_train_fails_other_carries_domestic_load(self):
        set_component_condition("equipment",
                                "WATER-PROC-A", "failed", operator=True)
        result = tick_continuous_physics(now_game_time=1060)
        self.assertGreater(result["water"]["cumulative"]["domestic_used_kg"], 0)
        self.assertGreater(result["water"]["cumulative"]["water_recovered_kg"], 0)

    def test_double_treatment_casualty_halts_recovery_not_creating_water(self):
        for side in "AB":
            set_component_condition("equipment", "WASTE-PROC-" + side,
                                    "failed", operator=True)
        result = tick_continuous_physics(now_game_time=1060)
        self.assertEqual(result["water"]["cumulative"]["water_recovered_kg"], 0)
        self.assertGreater(result["water"]["cumulative"]["domestic_used_kg"], 0)
        self.assertGreater(sum(result["water"]["fixed_kg"].values()) +
                           sum(sum(r.values()) for r in result["water"]["local_kg"].values()), 0)

    def test_local_receipt_replay_rejects_remote_and_wrong_roles(self):
        self.tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        with self.assertRaises(PermissionError):
            crew_physical_action(self.tech, "a" * 32, "water",
                                 "POTABLE-TANK-MAIN", "reserve_open")
        self.tech.move_to(find_ship_space("WATER-FWD"), quiet=True)
        first = crew_physical_action(self.tech, "a" * 32, "water",
                                     "POTABLE-TANK-MAIN", "reserve_open")
        self.assertEqual(first["status"], "succeeded")
        count = CanonicalShipEvent.objects.count()
        self.assertEqual(crew_physical_action(
            self.tech, "a" * 32, "water",
            "POTABLE-TANK-MAIN", "reserve_open"), first)
        self.assertEqual(count, CanonicalShipEvent.objects.count())
        self.assertTrue(self._water()["reserve_released"])
        with self.assertRaises(PermissionError):
            crew_physical_action(self.tech, "a" * 32, "water",
                                 "POTABLE-TANK-MAIN", "reserve_close")
        self.assertEqual(local_physics_readout(self.tech, "water")[
            "protected_reserve_kg"], 70000)

    def test_contamination_requires_actual_finite_filtration_and_sample(self):
        configure_water_casualty(operator=True, contaminated_kg=1.5)
        self.tech.move_to(find_ship_space("WATER-FWD"), quiet=True)
        bad = crew_physical_action(
            self.tech, "1" * 32, "water", "POTABLE-TANK-MAIN", "sample")
        self.assertEqual(bad["status"], "succeeded")
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.tech, "2" * 32, "water", "POTABLE-TANK-MAIN", "clear")
        # Chemistry filters are not available merely because an inventory
        # account exists. Physically survey the correct storage room, have
        # the worker carry them, and load the actual purifier in person.
        start_filters = state("inventory", "INV-DC-CONSUMABLES").quantity
        survey_g19_water_material(
            operator_approved=True, source="INV-DC-CONSUMABLES",
            room_id="STORE-CRIT-SPARES", verified_kg=1)
        self.tech.move_to(find_ship_space("STORE-CRIT-SPARES"), quiet=True)
        crew_physical_action(
            self.tech, "6" * 32, "water", "INV-DC-CONSUMABLES", "pickup_filter:1")
        self.assertLess(state("inventory", "INV-DC-CONSUMABLES").quantity, start_filters)
        self.assertEqual(self._water()["filter_carried_kg"][self.tech.dbref], 1)
        self.tech.move_to(find_ship_space("HAB-06-ECLSS-A"), quiet=True)
        crew_physical_action(
            self.tech, "7" * 32, "water", "WATER-PROC-A", "load_filter:1")
        self.assertEqual(self._water()["filter_carried_kg"][self.tech.dbref], 0)
        crew_physical_action(
            self.tech, "3" * 32, "water", "WATER-PROC-A", "decontaminate")
        result = tick_continuous_physics(now_game_time=1060)
        self.assertGreater(result["water"]["last_step"]["decontaminated_kg"], 0)
        self.assertGreater(self._water()["cumulative"]["decontaminated_kg"], 0)
        self.assertLess(self._water()["filter_staged_kg"]["A"], 1.0)
        self.assertGreater(state("inventory", "INV-HAZARDOUS-RESIDUE").quantity, 0)
        self.tech.move_to(find_ship_space("WATER-FWD"), quiet=True)
        crew_physical_action(
            self.tech, "4" * 32, "water", "POTABLE-TANK-MAIN", "sample")
        crew_physical_action(
            self.tech, "5" * 32, "water", "POTABLE-TANK-MAIN", "clear")
        self.assertFalse(self._water()["potable_quarantined"])
        self.assertFalse(WorkReceipt.objects.filter(pk="2" * 32).exists())


    def test_hydrogen_byproduct_has_no_unapproved_vacuum_route(self):
        self.assertFalse(self._water()["oxygen_outlet_verified"]["A"])
        with self.assertRaises(PermissionError):
            verify_g19_hydrogen_outlet(
                "A", exterior_clearance_verified=True)
        with self.assertRaises(PhysicsError):
            verify_g19_hydrogen_outlet(
                "C", operator_approved=True, exterior_clearance_verified=True)
        verify_g19_hydrogen_outlet(
            "A", operator_approved=True, exterior_clearance_verified=True)
        set_isolator("ISO-BYP-A-H2-SOURCE", "open", operator=True)
        set_isolator("ISO-BYP-A-H2-HULL", "open", operator=True)
        before = state("pressure", "PZ-HAB-06").details["physics_oxygen_kg"]
        result = tick_continuous_physics(now_game_time=1060)
        self.assertGreater(result["water"]["cumulative"]["oxygen_from_electrolysis_kg"], 0)
        self.assertGreater(result["water"]["cumulative"]["hydrogen_from_electrolysis_kg"], 0)
        self.assertGreater(state("pressure", "PZ-HAB-06").details["physics_oxygen_kg"], before)
        verify_g19_hydrogen_outlet(
            "A", operator_approved=True, exterior_clearance_verified=False)
        tick_continuous_physics(now_game_time=1070)
        self.assertEqual(self._water()["oxygen_outlet_verified"]["A"], False)

    def test_closed_network_isolation_blocks_real_water_transfer(self):
        for row in CanonicalShipState.objects.filter(category="isolator"):
            if row.reference.get("network") == "potable_water":
                set_isolator(row.source_id, "closed", operator=True)
        before = self._water()["working_kg"]
        result = tick_continuous_physics(now_game_time=1060)
        self.assertEqual(result["water"]["cumulative"]["domestic_used_kg"], 0)
        self.assertAlmostEqual(self._water()["working_kg"], before)


    def test_local_classified_spares_disposal_requires_survey_and_receipt(self):
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="SPARES-CENTRAL", verified_kg=3.0)
        self.tech.move_to(find_ship_space("SPARES-CENTRAL"), quiet=True)
        before = state("inventory", "INV-SPARES").quantity
        receipt = crew_physical_action(
            self.tech, "e" * 32, "waste",
            "IND-SCRAP-HOLD-A", "deposit:INV-SPARES:2")
        self.assertEqual(receipt["status"], "succeeded")
        self.assertAlmostEqual(
            state("inventory", "INV-SPARES").quantity, before - .002, places=7)
        self.assertAlmostEqual(
            state("inventory", "INV-INDUSTRIAL-SCRAP").quantity, .002, places=7)
        self.assertAlmostEqual(self._water()["cassettes"]["industrial"]["A"], 2)
        self.assertEqual(self._water()["source_surveys"]["INV-SPARES"]["SPARES-CENTRAL"], 1)
        self.assertEqual(
            crew_physical_action(self.tech, "e" * 32, "waste",
                "IND-SCRAP-HOLD-A", "deposit:INV-SPARES:2"), receipt)
        with self.assertRaises(PhysicsError):
            crew_physical_action(self.tech, "f" * 32, "waste",
                "HAZ-ISO-HOLD-A", "deposit:INV-SPARES:1")
        self.assertFalse(WorkReceipt.objects.filter(pk="f" * 32).exists())

    def test_broken_rotary_waste_interface_cannot_reach_fixed_receiver(self):
        from world.continuous_ship_physics import _water_hardware, _power
        equipment = {x.source_id: x for x in
                     CanonicalShipState.objects.filter(category="equipment")}
        edges = list(CanonicalShipState.objects.filter(category="edge"))
        isolators = {x.source_id: x for x in
                     CanonicalShipState.objects.filter(category="isolator")}
        nodes = list(CanonicalShipState.objects.filter(category="node"))
        power = _power(equipment, edges, isolators, "normal")
        healthy = _water_hardware(self._water(), equipment, edges, isolators, nodes, power)
        self.assertTrue(healthy["fixed"]["grey"])
        self.assertTrue(healthy["fixed"]["black"])
        set_component_condition("equipment", "ROT-GREYWATER-A",
                                "failed", operator=True)
        equipment["ROT-GREYWATER-A"] = state("equipment", "ROT-GREYWATER-A")
        one_left = _water_hardware(self._water(), equipment, edges, isolators, nodes, power)
        self.assertTrue(one_left["fixed"]["grey"])
        set_component_condition("equipment", "ROT-GREYWATER-B",
                                "failed", operator=True)
        equipment["ROT-GREYWATER-B"] = state("equipment", "ROT-GREYWATER-B")
        stopped = _water_hardware(self._water(), equipment, edges, isolators, nodes, power)
        self.assertFalse(stopped["fixed"]["grey"])
        self.assertTrue(stopped["fixed"]["black"])

    def test_unsealed_cassette_cannot_collect_sanitary_or_hazardous_waste(self):
        self.tech.move_to(find_ship_space("STORE-FLUID-AFT"), quiet=True)
        crew_physical_action(
            self.tech, "9" * 32, "waste", "WASTE-RESIDUE-HOLD-A", "unseal")
        self.assertFalse(self._water()["cassette_sealed"]["sanitary"]["A"])
        self.assertEqual(state("inventory", "INV-WASTE-RESIDUE").quantity, 0)
        # The second cassette remains available; both would be a casualty.
        result = tick_continuous_physics(now_game_time=1060)
        self.assertGreater(result["water"]["cumulative"]["sanitary_solids_kg"], 0)
        self.assertEqual(self._water()["cassettes"]["sanitary"]["A"], 0)


if __name__ == "__main__":
    import unittest
    unittest.main()
