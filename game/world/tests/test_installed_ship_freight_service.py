"""Installed G19 attended maintenance of all thirteen freight-only machines.

A real worker passes through the source-model gate from the actual LOGI/WR
station. No test grants crew free movement on active freight conveyors.
"""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    _clock, PhysicsError, arm_continuous_physics, commission_g19_freight_service,
    commission_g19_repairs, commission_g19_water, crew_physical_action,
    survey_g19_water_material, tick_continuous_physics,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_component_condition, state,
)
from world.models import CanonicalShipEvent, WorkReceipt
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.ship_freight_service import GATES, WORKSITES
from world.ship_world import ensure_canonical_ship, find_ship_space, find_world_entity


class InstalledFreightServiceAccess(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.assertTrue(
            commission_g19_freight_service(operator_approved=True)["commissioned"])
        self.assertFalse(
            commission_g19_freight_service(operator_approved=True)["commissioned"])
        crew = build_ship()
        self.tech, self.cargo = crew["watch"], crew["cargo"]
        self.serial = 0
        self.now = 1000

    def rid(self):
        self.serial += 1
        return f"{self.serial:032x}"

    def action(self, operator, category, target, value):
        return crew_physical_action(operator, self.rid(), category, target, value)

    def cross(self, operator, link, direction):
        exit_obj = find_world_entity(f"access:{link}:{direction}")
        return traverse_canonical_exit(
            operator, exit_obj, exit_obj.destination, request_id=self.rid())

    def advance(self, seconds):
        while seconds:
            dt = min(60, seconds)
            self.now += dt
            tick_continuous_physics(now_game_time=self.now)
            seconds -= dt

    def test_nine_existing_service_gates_board_and_return_thirteen_worksites(self):
        self.assertEqual(len(GATES), 9)
        self.assertEqual(len(WORKSITES), 13)
        for link, (control, site, kind, boundary, rotor) in sorted(GATES.items()):
            with self.subTest(service_link=link):
                self.tech.move_to(find_ship_space(control), quiet=True)
                sealed = state("access", link)
                self.assertEqual(sealed.setting, "closed")
                self.assertEqual(sealed.reference["kind"], kind)
                self.action(self.tech, "freight_service", link, "open")
                self.assertEqual(state("access", link).setting, "open")
                self.assertEqual(
                    self.cross(self.tech, link, "forward")["status"],
                    "succeeded")
                self.assertEqual(self.tech.location.db.ox_space_id, site)
                with self.assertRaises(PermissionError):
                    self.action(self.tech, "freight_service", link, "close")
                self.assertEqual(
                    self.cross(self.tech, link, "reverse")["status"],
                    "succeeded")
                self.assertEqual(self.tech.location.db.ox_space_id, control)
                self.action(self.tech, "freight_service", link, "close")
                self.assertEqual(state("access", link).setting, "closed")
                with self.assertRaises(CrewTransitError):
                    self.cross(self.tech, link, "forward")
        self.assertEqual(_clock().details["freight_service"]["releases_completed"], 9)
        self.assertEqual(_clock().details["freight_service"]["secured_links"], [])
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="crew_attended_freight_service_gate").count(), 18)
        self.assertEqual(WorkReceipt.objects.filter(
            operation="freight_service").count(), 18)

    def test_occupied_worksite_blocks_release_and_active_freight_motion(self):
        link = "ACC-LOGI-STOP-HAB-HUB-SERVICES-MAIN"
        control, destination, _, _, _ = GATES[link]
        self.tech.move_to(find_ship_space(control), quiet=True)
        self.cargo.move_to(find_ship_space(control), quiet=True)
        self.action(self.tech, "freight_service", link, "open")
        self.assertEqual(self.cross(
            self.cargo, link, "forward")["status"], "succeeded")
        with self.assertRaisesRegex(PhysicsError, "remains"):
            self.action(self.tech, "freight_service", link, "close")
        with self.assertRaisesRegex(PhysicsError, "inhibits"):
            self.action(self.tech, "freight", "LOT-ABSENT", "to_spine")
        with self.assertRaisesRegex(PhysicsError, "inhibits"):
            self.action(self.tech, "helm", "MAIN", "thrust")
        with self.assertRaisesRegex(PhysicsError, "holds rotary"):
            self.action(self.tech, "rotor", "WR-01", "start")
        self.assertEqual(self.cargo.location.db.ox_space_id, destination)
        self.assertEqual(state("access", link).setting, "open")
        self.assertEqual(self.cross(
            self.cargo, link, "reverse")["status"], "succeeded")
        self.action(self.tech, "freight_service", link, "close")

    def test_unsafe_hardware_and_no_commissioned_entry_bypass(self):
        gate = "ACC-DR-01-FREIGHT-LOCK-LOGI"
        control = GATES[gate][0]
        self.tech.move_to(find_ship_space(control), quiet=True)
        # An open hatch without the world-owned permit grants no clearance.
        door = state("access", gate, lock=True)
        door.setting = "open"
        door.revision += 1
        door.save(update_fields=["setting", "revision"])
        with self.assertRaises(CrewTransitError):
            self.cross(self.tech, gate, "forward")
        door.setting = "closed"
        door.revision += 1
        door.save(update_fields=["setting", "revision"])
        set_component_condition(
            "access", "ACC-DR-01-FREIGHT-CAPTURE", "failed",
            operator=True)
        with self.assertRaises(PhysicsError):
            self.action(self.tech, "freight_service", gate, "open")
        set_component_condition(
            "access", "ACC-DR-01-FREIGHT-CAPTURE", "serviceable",
            operator=True)
        self.tech.move_to(find_ship_space("DR-01-FREIGHT-LOCK"), quiet=True)
        self.action(self.tech, "rotor", "DR-01", "release")
        self.tech.move_to(find_ship_space(control), quiet=True)
        with self.assertRaises(PhysicsError):
            self.action(self.tech, "freight_service", gate, "open")

    def test_repair_and_spares_progress_only_inside_actual_service_enclosure(self):
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        self.tech.move_to(find_ship_space("TOOL-CRIB"), quiet=True)
        self.action(self.tech, "repair", "TOOL-CRIB", "pickup_toolkit")
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=2)
        self.tech.move_to(find_ship_space("STORE-CRIT-SPARES"), quiet=True)
        self.action(self.tech, "repair", "INV-SPARES", "pickup:0.5")
        name = "LOGI-SLED-01"
        link = WORKSITES[name][1]
        room, _ = WORKSITES[name]
        set_component_condition("equipment", name, "degraded", operator=True)
        self.tech.move_to(find_ship_space(room), quiet=True)
        with self.assertRaises(PhysicsError):
            self.action(self.tech, "repair", "equipment:" + name, "start")
        self.tech.move_to(find_ship_space(GATES[link][0]), quiet=True)
        self.action(self.tech, "freight_service", link, "open")
        self.cross(self.tech, link, "forward")
        self.action(self.tech, "repair", "equipment:" + name, "start")
        self.assertIn("equipment:" + name, _clock().details["repairs"]["jobs"])
        self.cross(self.tech, link, "reverse")
        with self.assertRaisesRegex(PhysicsError, "Finish on-site maintenance"):
            self.action(self.tech, "freight_service", link, "close")
        self.cross(self.tech, link, "forward")
        self.advance(120)
        self.assertEqual(state("equipment", name).condition, "serviceable")
        self.assertEqual(_clock().details["repairs"]["completed"], 1)
        self.assertAlmostEqual(_clock().details["repairs"]["installed_kg"], 0.5)
        self.cross(self.tech, link, "reverse")
        self.action(self.tech, "freight_service", link, "close")
