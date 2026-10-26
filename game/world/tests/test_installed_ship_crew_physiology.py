"""Actual installed crew respiratory coupling, deliberately only two actors.

No 40-character autonomous voyage or AI dialogue is exercised.
"""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.ship_world import build_canonical_ship, find_ship_space
from world.full_ship_operations import (
    install_candidate, install_pressure_cells,
    initialize_nominal_atmosphere, state, set_isolator,
)
from world.continuous_ship_physics import (
    PhysicsError, _clock, _topology, arm_continuous_physics,
    commission_g19_crew_physiology, commission_g19_eva,
    configure_scenario_casualty, local_physics_readout,
    crew_physical_action, tick_continuous_physics,
)
from world.models import CanonicalShipState
from world.ship_crew_access import CrewTransitError, _health_gate


class InstalledCrewPhysiologyTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        crew = build_ship()
        self.tech = crew["watch"]
        self.cargo = crew["cargo"]
        self.tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        self.cargo.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        self.zone = _topology()[0]["CMD-PRIMARY"]
        self.now = 1000
        self.id = 100

    def tick(self, seconds):
        remaining = seconds
        while remaining > 0:
            n = min(60, remaining)
            self.now += n
            tick_continuous_physics(now_game_time=self.now)
            remaining -= n

    def health(self, actor):
        return CanonicalShipState.objects.get(pk="crew_health:" + actor.dbref)

    def action(self, action, target, value):
        self.id += 1
        return crew_physical_action(
            self.tech, f"{self.id:032x}", action, target, value)

    def test_two_named_crew_breathe_real_cell_gas_with_restart_safe_ticks(self):
        oxygen_before = sum(
            p.details["physics_oxygen_kg"] for p in
            CanonicalShipState.objects.filter(category="pressure"))
        gas_total_before = (
            sum(p.quantity for p in
                CanonicalShipState.objects.filter(category="pressure"))
            + _clock().details["co2_captured_kg"])
        registered = commission_g19_crew_physiology(
            actor_dbrefs=[self.tech.dbref, self.cargo.dbref],
            operator_approved=True)
        self.assertEqual(registered["registered"], 2)
        self.assertEqual(commission_g19_crew_physiology(
            actor_dbrefs=[self.tech.dbref],
            operator_approved=True)["registered"], 0)
        self.tick(60)
        oxygen_after = sum(
            p.details["physics_oxygen_kg"] for p in
            CanonicalShipState.objects.filter(category="pressure"))
        gas_total_after = (
            sum(p.quantity for p in
                CanonicalShipState.objects.filter(category="pressure"))
            + _clock().details["co2_captured_kg"])
        self.assertLess(oxygen_after, oxygen_before)
        self.assertAlmostEqual(gas_total_after, gas_total_before, delta=.00001)
        self.assertEqual(self.health(self.tech).condition, "fit")
        self.assertEqual(self.health(self.cargo).condition, "fit")
        self.assertGreater(self.health(self.tech).details["water_deficit_kg"], 0)
        summary = _clock().details["summary"]
        self.assertEqual(summary["crew_exposure_registered"], 2)
        self.assertAlmostEqual(summary["crew_o2_used_this_tick_kg"], .0012, delta=.000001)
        self.assertAlmostEqual(summary["crew_co2_added_this_tick_kg"],
                               summary["crew_o2_used_this_tick_kg"])
        revision = self.health(self.tech).revision
        self.assertFalse(tick_continuous_physics(
            now_game_time=self.now)["advanced"])
        self.assertEqual(self.health(self.tech).revision, revision)
        self.assertEqual(local_physics_readout(
            self.tech, "crew")["scope"],
            "own_physically_measured_crew_health_only")

    def test_unprotected_crew_in_a_real_leaking_lock_becomes_incapacitated(self):
        self.tech.move_to(find_ship_space("EVA-FWD"), quiet=True)
        self.assertEqual(commission_g19_crew_physiology(
            actor_dbrefs=[self.tech.dbref],
            operator_approved=True)["registered"], 1)
        set_isolator("ISO-AIR-FIXED-EVA-FWD", "closed", operator=True)
        configure_scenario_casualty(
            "PZ-BOW-EVA", leak_kg_s=5, operator=True)
        self.tick(360)
        current = self.health(self.tech)
        self.assertIn(current.condition, {"incapacitated", "critical", "dead"})
        self.assertGreaterEqual(current.details["hypoxia_s"], 180)
        with self.assertRaises(CrewTransitError):
            _health_gate(self.tech)
        with self.assertRaisesRegex(
                CrewTransitError, "Crew casualty cannot operate physical ship controls"):
            self.action("switch", "ISO-GEN-M", "closed")

    def test_real_eva_suit_is_one_breathing_source_not_two(self):
        self.tech.move_to(find_ship_space("EVA-FWD"), quiet=True)
        commission_g19_crew_physiology(
            actor_dbrefs=[self.tech.dbref], operator_approved=True)
        commission_g19_eva(operator_approved=True)
        self.tech.move_to(find_ship_space("ENG-LOCKER"), quiet=True)
        self.action("eva", "INV-DC-CONSUMABLES", "stage:0.75")
        self.tech.move_to(find_ship_space("EVA-FWD"), quiet=True)
        self.action("eva", "EVA-FWD", "checkout")
        initial = _clock().details["eva"]["suits"]["EVA-FWD-SUIT-1"][
            "exposure"]["suit_oxygen_kg"]
        self.tick(60)
        book = _clock().details["eva"]
        suit = book["suits"]["EVA-FWD-SUIT-1"]["exposure"]
        self.assertLess(suit["suit_oxygen_kg"], initial)
        self.assertAlmostEqual(initial - suit["suit_oxygen_kg"], .0006, delta=.000001)
        self.assertAlmostEqual(self.health(self.tech).details[
            "hypoxia_s"], suit["hypoxia_s"])
        self.assertAlmostEqual(self.health(self.tech).details[
            "water_deficit_kg"], suit["water_deficit_kg"])
        self.assertEqual(_clock().details["summary"]["crew_o2_used_this_tick_kg"], 0)

    def test_operator_must_enrol_named_real_ship_character(self):
        with self.assertRaises(PermissionError):
            commission_g19_crew_physiology(
                actor_dbrefs=[self.tech.dbref], operator_approved=False)
        with self.assertRaises(PhysicsError):
            commission_g19_crew_physiology(
                actor_dbrefs=["#99999999"], operator_approved=True)
        self.assertFalse(CanonicalShipState.objects.filter(
            category="crew_health").exists())
