"""G19 movement through installed exits (not test-operator teleportation)."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    state, set_component_condition,
)
from world.continuous_ship_physics import (
    arm_continuous_physics, crew_physical_action, configure_scenario_casualty,
    tick_continuous_physics,
)
from world.models import CanonicalShipEvent, WorkReceipt
from world.ship_world import ensure_canonical_ship, find_ship_space, find_world_entity
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit


class RealExitMovementTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.tech = build_ship()["watch"]
        self.door = state("access", "ACC-BR-03-HAB-03")
        self.src = find_ship_space(self.door.reference["from"])
        self.dst = find_ship_space(self.door.reference["to"])
        self.exit = find_world_entity("access:ACC-BR-03-HAB-03:forward")
        self.tech.move_to(self.src, quiet=True)

    def test_rated_boundary_requires_real_open_hatch(self):
        with self.assertRaises(CrewTransitError):
            traverse_canonical_exit(self.tech, self.exit, self.dst,
                                    request_id="a" * 32)
        self.assertEqual(self.tech.location, self.src)
        self.assertFalse(WorkReceipt.objects.filter(pk="a" * 32).exists())
        crew_physical_action(self.tech, "b" * 32, "hatch",
                             "ACC-BR-03-HAB-03", "open")
        result = traverse_canonical_exit(
            self.tech, self.exit, self.dst, request_id="c" * 32)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(self.tech.location, self.dst)
        self.assertEqual(WorkReceipt.objects.get(pk="c" * 32).outcome, result)
        count = CanonicalShipEvent.objects.filter(operation="crew_traverse").count()
        self.assertEqual(
            traverse_canonical_exit(self.tech, self.exit, self.dst,
                                    request_id="c" * 32), result)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="crew_traverse").count(), count)
        with self.assertRaises(CrewTransitError):
            traverse_canonical_exit(self.tech, self.exit, self.dst,
                                    request_id="d" * 32)

    def test_hull_casualty_and_damaged_door_block_movement(self):
        crew_physical_action(self.tech, "1" * 32, "hatch",
                             "ACC-BR-03-HAB-03", "open")
        set_component_condition(
            "access", "ACC-BR-03-HAB-03", "jammed", operator=True)
        with self.assertRaises(CrewTransitError):
            traverse_canonical_exit(self.tech, self.exit, self.dst)
        set_component_condition(
            "access", "ACC-BR-03-HAB-03", "serviceable", operator=True)
        configure_scenario_casualty(
            "PZ-HAB-03", leak_kg_s=15, operator=True)
        tick_continuous_physics(now_game_time=1010)
        with self.assertRaises(CrewTransitError):
            traverse_canonical_exit(self.tech, self.exit, self.dst)
        self.assertEqual(self.tech.location, self.src)

    def test_deceased_or_incapacitated_never_traverses(self):
        crew_physical_action(self.tech, "2" * 32, "hatch",
                             "ACC-BR-03-HAB-03", "open")
        self.tech.db.ox_terminal_dead = True
        with self.assertRaises(CrewTransitError):
            traverse_canonical_exit(self.tech, self.exit, self.dst)
        self.tech.db.ox_terminal_dead = False
        self.assertEqual(self.tech.location, self.src)
