"""G18b: physically coupled world casualties and authorised crew interventions.

The test runs against the actual installed 421-space/133-cell/808-equipment
Evennia world. Characters are deliberately staged at canon rooms by the test
operator; this is NOT proof that unverified traversal is live.
"""
from __future__ import annotations

from types import SimpleNamespace

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    PhysicsError, _physical_passage, _topology, arm_continuous_physics,
    configure_scenario_casualty, crew_physical_action, local_physics_readout,
    tick_continuous_physics,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_component_condition, set_isolator, state,
)
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_world import build_canonical_ship, find_ship_space


class CoupledShipCasualtyTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)

    def _total_gas(self):
        return sum(
            x.quantity for x in CanonicalShipState.objects.filter(category="pressure")
        )

    def _tech(self):
        return build_ship()["watch"]

    def test_local_manual_valve_contains_finite_service_leak_and_cannot_unjam(self):
        zones = _topology()[0]
        pressure = set(CanonicalShipState.objects.filter(category="pressure")
                       .values_list("source_id", flat=True))
        candidates = [
            x for x in CanonicalShipState.objects.filter(category="isolator")
            if (x.reference.get("network") == "atmosphere"
                and x.reference.get("manual_operation")
                and ("valve" in str(x.reference.get("kind", "")).lower()
                     or "damper" in str(x.reference.get("kind", "")).lower())
                and zones.get(x.space_id) in pressure)
        ]
        self.assertTrue(candidates, "Canonical pressure-zone manual dampers missing")
        valve = sorted(candidates, key=lambda x: x.key)[0]
        zone = zones[valve.space_id]
        set_isolator(valve.source_id, "open", operator=True)
        configure_scenario_casualty(
            zone, leak_kg_s=0.1, leak_isolator_id=valve.source_id, operator=True)
        initial = self._total_gas()
        tick_continuous_physics(now_game_time=1010)
        self.assertAlmostEqual(initial - self._total_gas(), 1.0, delta=1e-5)

        tech = self._tech()
        tech.move_to(find_ship_space(valve.space_id), quiet=True)
        receipt = crew_physical_action(
            tech, "a" * 32, "switch", valve.source_id, "closed")
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(
            crew_physical_action(tech, "a" * 32, "switch", valve.source_id, "closed"),
            receipt)
        sealed = self._total_gas()
        tick_continuous_physics(now_game_time=1020)
        self.assertAlmostEqual(self._total_gas(), sealed, delta=1e-5)
        self.assertFalse(tick_continuous_physics(now_game_time=1020)["advanced"])

        # Mechanically jammed open is not an electrical OFF indication.
        set_isolator(valve.source_id, "open", operator=True)
        set_component_condition("isolator", valve.source_id, "jammed", operator=True)
        self.assertTrue(_physical_passage(state("isolator", valve.source_id)))
        with self.assertRaises(PhysicsError):
            crew_physical_action(tech, "b" * 32, "switch", valve.source_id, "closed")
        before = self._total_gas()
        tick_continuous_physics(now_game_time=1030)
        self.assertAlmostEqual(before - self._total_gas(), 1.0, delta=1e-5)
        self.assertFalse(WorkReceipt.objects.filter(pk="b" * 32).exists())

    def test_rated_bridge_hatch_moves_smoke_and_blocks_second_end(self):
        first = state("access", "ACC-BR-03-HAB-03")
        second = state("access", "ACC-BR-03-HAB-04")
        self.assertTrue(first.reference["pressure_boundary"])
        zones, _, node_zones = _topology()
        self.assertEqual(
            {zones[first.reference["from"]], zones[first.reference["to"]]},
            {"PZ-HAB-03", "PZ-BR-03"})
        # The independent HAB bridge duct is closed so any later BR-03
        # smoke must cross the actually opened pressure hatch.
        for e in CanonicalShipState.objects.filter(category="edge"):
            r = e.reference
            if (r["network"] == "atmosphere"
                    and "PZ-BR-03" in {
                        node_zones.get(r["from_node"]),
                        node_zones.get(r["to_node"])}):
                for iso in r["isolator_ids"]:
                    set_isolator(iso, "closed", operator=True)

        tech = self._tech()
        tech.move_to(find_ship_space(first.reference["from"]), quiet=True)
        opened = crew_physical_action(
            tech, "c" * 32, "hatch", first.source_id, "open")
        self.assertEqual(opened["status"], "succeeded")
        self.assertEqual(state("access", first.source_id).setting, "open")
        self.assertEqual(local_physics_readout(tech, first.source_id)["setting"], "open")

        tech.move_to(find_ship_space(second.reference["from"]), quiet=True)
        with self.assertRaises(PhysicsError):
            crew_physical_action(tech, "d" * 32, "hatch", second.source_id, "open")
        self.assertEqual(state("access", second.source_id).setting, "closed")
        self.assertFalse(WorkReceipt.objects.filter(pk="d" * 32).exists())

        configure_scenario_casualty(
            "PZ-HAB-03", fire_fuel_kg=5, fire_burn_kg_s=0.25,
            operator=True)
        tick_continuous_physics(now_game_time=1010)
        tick_continuous_physics(now_game_time=1020)
        bridge_smoke = state("pressure", "PZ-BR-03").details["physics_smoke_kg"]
        self.assertGreater(bridge_smoke, 0.0)
        self.assertGreater(state("pressure", "PZ-HAB-03")
                           .details["physics_smoke_kg"], 0.0)

        tech.move_to(find_ship_space(first.reference["from"]), quiet=True)
        receipt = crew_physical_action(
            tech, "e" * 32, "hatch", first.source_id, "closed")
        self.assertEqual(receipt["status"], "succeeded")
        tick_continuous_physics(now_game_time=1030)
        self.assertAlmostEqual(
            state("pressure", "PZ-BR-03").details["physics_smoke_kg"],
            bridge_smoke, delta=1e-4)
        # A directly exposed fire/unsafe atmosphere cannot reopen it.
        with self.assertRaises(PhysicsError):
            crew_physical_action(tech, "f" * 32, "hatch", first.source_id, "open")

    def test_power_cooling_fire_and_damage_remain_causally_coupled(self):
        set_isolator("ISO-GEN-M", "closed", operator=True)
        baseline = tick_continuous_physics(now_game_time=1010)
        self.assertTrue(baseline["power_assured"])
        self.assertGreaterEqual(baseline["available_mw"], 3.0)

        tech = self._tech()
        generator = state("equipment", "GEN-M")
        tech.move_to(find_ship_space(generator.space_id), quiet=True)
        crew_physical_action(tech, "1" * 32, "plant", "GEN-M", "off")
        configure_scenario_casualty(
            "PZ-HAB-03", fire_fuel_kg=300, fire_burn_kg_s=3.0,
            operator=True)
        blackout = tick_continuous_physics(now_game_time=1020)
        self.assertFalse(blackout["power_assured"])
        self.assertEqual(blackout["cooling_kw"], 0.0)
        self.assertFalse(blackout["ventilation_powered"])

        first = state("pressure", "PZ-HAB-03")
        self.assertGreater(first.details["physics_smoke_kg"], 0)
        self.assertLess(first.details["physics_oxygen_kg"],
                        first.quantity * 0.232)

        # Qualified local operation starts the plant, but startup takes game
        # time and cannot clear burned fuel, heat or physical damage.
        crew_physical_action(tech, "2" * 32, "plant", "GEN-M", "on")
        startup = tick_continuous_physics(now_game_time=1030)
        self.assertFalse(startup["power_assured"])
        restarted = tick_continuous_physics(now_game_time=1050)
        self.assertTrue(restarted["power_assured"])

        last = restarted
        for minute in (1110, 1170, 1230):
            last = tick_continuous_physics(now_game_time=minute)
        cell = state("pressure", "PZ-HAB-03")
        self.assertGreater(cell.details["physics_damage_index"], 0)
        self.assertGreater(last["smoke_kg"], 0)
        self.assertGreater(last["burned_fuel_kg"] if "burned_fuel_kg" in last else
                           CanonicalShipState.objects.get(
                               pk="meta:continuous-physics").details["burned_fuel_kg"], 0)
        self.assertTrue(CanonicalShipEvent.objects.filter(
            operation__in=["thermal_exposure_damage", "severe_thermal_damage"]).exists())
        self.assertFalse(tick_continuous_physics(now_game_time=1230)["advanced"])

    def test_heat_trip_requires_safe_local_manual_reset_not_instant_repair(self):
        set_isolator("ISO-GEN-M", "closed", operator=True)
        configure_scenario_casualty(
            "PZ-HAB-06", fire_fuel_kg=95, fire_burn_kg_s=3.0,
            operator=True)
        for instant in (1010, 1020, 1030, 1040):
            tick_continuous_physics(now_game_time=instant)
        train = state("equipment", "ECLSS-A")
        self.assertEqual(train.condition, "faulted")
        self.assertEqual(
            train.details["physics_trip_reason"], "local_overtemperature_protection")
        self.assertFalse(train.details["physics_online"])

        tech = build_ship()["environment"]
        tech.move_to(find_ship_space(train.space_id), quiet=True)
        with self.assertRaises(PhysicsError):
            crew_physical_action(tech, "3" * 32, "service", "ECLSS-A", "reset")
        # Shutting down a tripped plant remains possible and is not a reset.
        crew_physical_action(tech, "4" * 32, "plant", "ECLSS-A", "off")
        with self.assertRaises(PhysicsError):
            crew_physical_action(tech, "5" * 32, "service", "ECLSS-A", "reset")
        self.assertFalse(WorkReceipt.objects.filter(pk="5" * 32).exists())
        self.assertTrue(CanonicalShipEvent.objects.filter(
            operation="thermal_protection_trip",
            component_key="equipment:ECLSS-A").exists())
