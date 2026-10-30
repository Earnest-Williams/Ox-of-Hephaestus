"""Real F1/F2 flywheel service cycles using existing issued EVA suits."""
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.ship_world import build_canonical_ship, find_ship_space, find_world_entity
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition,
)
from world.continuous_ship_physics import (
    arm_continuous_physics, commission_g19_eva,
    commission_g19_crew_physiology,
    commission_g19_flywheel_access, survey_g19_flywheel_access,
    crew_physical_action, tick_continuous_physics, _clock,
    local_physics_readout,
)
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.ship_hazardous_access import CYCLE_S
from world.models import WorkReceipt


class InstalledFlywheelServiceAccess(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        crew = build_ship()
        self.workers = (crew["watch"], crew["chief"])
        for worker in self.workers:
            worker.move_to(find_ship_space("TRUNK-A-F1"), quiet=True)
        commission_g19_crew_physiology(
            actor_dbrefs=[worker.dbref for worker in self.workers],
            operator_approved=True)
        commission_g19_eva(operator_approved=True)
        self.assertTrue(
            commission_g19_flywheel_access(operator_approved=True)["commissioned"])
        self.now = 1000
        self.counter = 0

    def rid(self):
        self.counter += 1
        return f"{self.counter:032x}"

    def op(self, actor, action, target, value):
        return crew_physical_action(
            actor, self.rid(), action, target, value)

    def suit(self, actor):
        actor.move_to(find_ship_space("ENG-LOCKER"), quiet=True)
        self.op(actor, "eva", "INV-DC-CONSUMABLES", "stage:0.75")
        actor.move_to(find_ship_space("EVA-FWD"), quiet=True)
        self.op(actor, "eva", "EVA-FWD", "checkout")

    def cross(self, actor, link, direction, request=None):
        door = find_world_entity(f"access:{link}:{direction}")
        self.assertIsNotNone(door)
        return traverse_canonical_exit(
            actor, door, door.destination,
            request_id=request or self.rid())

    def tick(self, seconds):
        while seconds:
            dt = min(60, seconds)
            self.now += dt
            tick_continuous_physics(now_game_time=self.now)
            seconds -= dt

    def survey(self):
        for bay in ("F1-BAY", "F2-BAY"):
            self.assertTrue(
                survey_g19_flywheel_access(
                    bay_id=bay, operator_approved=True)["changed"])

    def test_outbound_and_return_keep_trunk_gas_and_use_real_suit_stock(self):
        self.survey()
        actor = self.workers[0]
        self.suit(actor)
        actor.move_to(find_ship_space("TRUNK-A-F1"), quiet=True)
        oxygen_before = _clock().details["eva"]["suits"]["EVA-FWD-SUIT-1"][
            "exposure"]["suit_oxygen_kg"]
        receipt = self.cross(actor, "ACC-F1-BAY", "forward")
        self.assertEqual(receipt["status"], "queued")
        self.assertEqual(receipt["travel_seconds"], CYCLE_S)
        self.tick(120)
        self.assertEqual(actor.location, find_ship_space("TRUNK-A-F1"))
        self.tick(60)
        self.assertEqual(actor.location, find_ship_space("F1-BAY"))
        self.assertEqual(
            local_physics_readout(actor, "bay_access")[
                "local_locks"]["ACC-F1-BAY"]["surveyed"], True)
        self.assertLess(_clock().details["eva"]["suits"][
            "EVA-FWD-SUIT-1"]["exposure"]["suit_oxygen_kg"], oxygen_before)
        receipt = self.cross(actor, "ACC-F1-BAY", "reverse")
        self.assertEqual(receipt["status"], "queued")
        self.tick(180)
        self.assertEqual(actor.location, find_ship_space("TRUNK-A-F1"))
        self.assertEqual(_clock().details["bay_access"]["completed"], 2)
        self.assertEqual(WorkReceipt.objects.filter(
            operation="traverse", target="ship_physics").count(), 2)

    def test_both_existing_bays_are_independently_accessible(self):
        self.survey()
        for actor in self.workers:
            self.suit(actor)
        for i, actor in enumerate(self.workers, 1):
            actor.move_to(find_ship_space(f"TRUNK-A-F{i}"), quiet=True)
            self.cross(actor, f"ACC-F{i}-BAY", "forward")
        self.assertEqual(len(_clock().details["bay_access"]["jobs"]), 2)
        self.tick(180)
        for i, actor in enumerate(self.workers, 1):
            self.assertEqual(actor.location, find_ship_space(f"F{i}-BAY"))
        self.assertEqual(_clock().details["bay_access"]["completed"], 2)

    def test_missing_suit_or_survey_cannot_enter_unknown_atmosphere(self):
        actor = self.workers[0]
        with self.assertRaises(CrewTransitError):
            self.cross(actor, "ACC-F1-BAY", "forward")
        self.suit(actor)
        actor.move_to(find_ship_space("TRUNK-A-F1"), quiet=True)
        with self.assertRaises(CrewTransitError):
            self.cross(actor, "ACC-F1-BAY", "forward")
        self.survey()
        self.cross(actor, "ACC-F1-BAY", "forward")
        with self.assertRaises(CrewTransitError):
            self.cross(actor, "ACC-F1-BAY", "forward")

    def test_failed_original_hatch_pauses_then_resumes_without_teleport(self):
        self.survey()
        actor = self.workers[0]
        self.suit(actor)
        actor.move_to(find_ship_space("TRUNK-A-F1"), quiet=True)
        self.cross(actor, "ACC-F1-BAY", "forward")
        self.tick(60)
        set_component_condition("access", "ACC-F1-BAY", "faulted", operator=True)
        self.tick(60)
        self.assertEqual(actor.location, find_ship_space("TRUNK-A-F1"))
        self.assertEqual(_clock().details["bay_access"]["jobs"][
            actor.dbref]["remaining_s"], 120)
