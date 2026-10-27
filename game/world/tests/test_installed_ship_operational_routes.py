"""G19 continuous, physically interlocked crew routes through real exits.

These are attended, deterministic two-person station tests, not a 40-crew
voyage. Crew never teleport between the first boarding hatch and final exit.
"""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    _clock, arm_continuous_physics, commission_g19_personnel_transfers,
    commission_g19_hab_sync, crew_physical_action, tick_continuous_physics,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, state,
)
from world.models import CanonicalShipEvent, WorkReceipt
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.ship_world import build_canonical_ship, find_ship_space, find_world_entity


class InstalledContinuousCrewRoutes(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        commission_g19_personnel_transfers(operator_approved=True)
        crew = build_ship()
        self.engineer, self.passenger = crew["watch"], crew["cargo"]
        self.now = 1000
        self.sequence = 0

    def rid(self):
        self.sequence += 1
        return f"{self.sequence:032x}"

    def action(self, action, target, value):
        return crew_physical_action(
            self.engineer, self.rid(), action, target, value)

    def transit(self, actor, link, direction):
        exit_obj = find_world_entity(f"access:{link}:{direction}")
        self.assertIsNotNone(exit_obj)
        destination = exit_obj.destination
        outcome = traverse_canonical_exit(
            actor, exit_obj, destination, request_id=self.rid())
        self.assertIn(outcome["status"], {"queued", "succeeded"})
        return outcome

    def advance(self, seconds):
        while seconds > 0:
            delta = min(60, seconds)
            self.now += delta
            tick_continuous_physics(now_game_time=self.now)
            seconds -= delta

    def test_fixed_spine_to_drum_and_back_uses_all_real_hatches(self):
        """No crew teleport through the fixed hatch, indexer, or return."""
        spine = find_ship_space("TRUNK-A-DR-01")
        lock = find_ship_space("DR-01-SERVICE-LOCK")
        hub = find_ship_space("DR-01-HUB")
        self.engineer.move_to(spine, quiet=True)  # initial test staging only
        self.passenger.move_to(spine, quiet=True)
        self.action("hatch", "ACC-DR-01-LOCK-FIX", "open")
        self.assertEqual(
            self.transit(self.passenger, "ACC-DR-01-LOCK-FIX",
                         "forward")["status"], "succeeded")
        self.assertEqual(self.passenger.location, lock)
        self.assertEqual(
            self.transit(self.engineer, "ACC-DR-01-LOCK-FIX",
                         "forward")["status"], "succeeded")
        self.assertEqual(self.engineer.location, lock)

        self.action("hatch", "ACC-DR-01-LOCK-FIX", "closed")
        self.action("rotor", "DR-01", "passenger_extend")
        outbound = self.transit(
            self.passenger, "ACC-DR-01-LOCK-ROT", "forward")
        self.assertEqual(outbound["status"], "queued")
        self.assertEqual(outbound["travel_seconds"], 180)
        self.assertEqual(self.passenger.location, lock)
        with self.assertRaises(CrewTransitError):
            self.transit(
                self.passenger, "ACC-DR-01-LOCK-FIX", "reverse")
        self.advance(180)
        self.assertEqual(self.passenger.location, hub)
        inbound = self.transit(
            self.passenger, "ACC-DR-01-LOCK-ROT", "reverse")
        self.assertEqual(inbound["status"], "queued")
        self.advance(180)
        self.assertEqual(self.passenger.location, lock)
        self.assertEqual(
            _clock().details["personnel_transfers"]["completed"], 2)

        self.action("rotor", "DR-01", "passenger_retract")
        self.action("hatch", "ACC-DR-01-LOCK-FIX", "open")
        self.assertEqual(
            self.transit(self.passenger, "ACC-DR-01-LOCK-FIX",
                         "reverse")["status"], "succeeded")
        self.assertEqual(
            self.transit(self.engineer, "ACC-DR-01-LOCK-FIX",
                         "reverse")["status"], "succeeded")
        self.assertEqual(self.passenger.location, spine)
        self.assertEqual(self.engineer.location, spine)
        self.assertEqual(
            CanonicalShipEvent.objects.filter(
                operation="crew_indexed_transfer_complete").count(), 2)
        self.assertFalse(_clock().details["personnel_transfers"]["jobs"])
        self.assertEqual(WorkReceipt.objects.filter(
            operation="traverse", target="ship_physics").count(), 6)

    def test_rotating_hab_capsule_is_boarded_and_returned_through_fixed_hatch(self):
        """Actual fixed hatch, synchronised moving ring, and return chain."""
        commission_g19_hab_sync(operator_approved=True)
        self.engineer.move_to(find_ship_space("ENG-CONTROL"), quiet=True)
        self.action("rotor", "HAB", "start")
        self.advance(360)
        self.assertGreater(_clock().details["rotors"]["HAB"]["rpm"], .30)
        fixed = find_ship_space("HUB-FIXED-A")
        capsule = find_ship_space("IX-A-CAPSULE")
        vestibule = find_ship_space("IX-A-ROT-VEST")
        self.engineer.move_to(fixed, quiet=True)  # initial station staging
        self.passenger.move_to(fixed, quiet=True)
        self.action("hatch", "ACC-IX-A-FIX", "open")
        self.assertEqual(self.transit(
            self.passenger, "ACC-IX-A-FIX",
            "forward")["status"], "succeeded")
        self.assertEqual(self.passenger.location, capsule)
        self.action("hatch", "ACC-IX-A-FIX", "closed")
        self.action("rotor", "HAB", "sync:A")
        for _ in range(20):
            self.advance(60)
            if _clock().details["hab_sync"]["captured"]:
                break
        self.assertTrue(_clock().details["hab_sync"]["captured"])
        self.assertGreater(_clock().details["rotors"]["HAB"]["rpm"], .30)
        outward = self.transit(
            self.passenger, "ACC-IX-A-ROT", "forward")
        self.assertEqual(outward["status"], "queued")
        self.assertEqual(outward["travel_seconds"], 300)
        self.advance(300)
        self.assertEqual(self.passenger.location, vestibule)

        returned = self.transit(
            self.passenger, "ACC-IX-A-ROT", "reverse")
        self.assertEqual(returned["status"], "queued")
        self.advance(300)
        self.assertEqual(self.passenger.location, capsule)
        self.action("rotor", "HAB", "sync_release")
        self.action("hatch", "ACC-IX-A-FIX", "open")
        self.assertEqual(self.transit(
            self.passenger, "ACC-IX-A-FIX",
            "reverse")["status"], "succeeded")
        self.assertEqual(self.passenger.location, fixed)
        self.assertFalse(_clock().details["personnel_transfers"]["jobs"])
        self.assertEqual(
            _clock().details["personnel_transfers"]["completed"], 2)
        self.assertGreater(_clock().details["rotors"]["HAB"]["rpm"], .30)

    def test_ordinary_ship_doors_are_crew_operated_at_the_real_local_hatch(self):
        """Seven non-carrier installed door families traverse both directions."""
        cases = (
            ("ACC-TRUNK-A-BOW-DR-01", "pressure_door"),
            ("ACC-GEN-M-ROOM", "service_door"),
            ("ACC-HAB-01-CAB-01", "cabin_door"),
            ("ACC-DR-01-SEC-01", "cargo_service_door"),
            ("ACC-HAB-01-SG1-CUPBOARD", "service_panel"),
            ("ACC-WR-SHOP-WELD", "fire_door"),
            ("ACC-STORE-CRIT-SPARES-STORES-GALLERY", "store_door"),
        )
        for identifier, category in cases:
            with self.subTest(door=identifier):
                door = state("access", identifier)
                self.assertEqual(door.reference["kind"], category)
                start = find_ship_space(door.reference["from"])
                end = find_ship_space(door.reference["to"])
                self.engineer.move_to(start, quiet=True)  # next isolated test site
                self.action("hatch", identifier, "open")
                self.assertEqual(state("access", identifier).setting, "open")
                self.assertEqual(
                    self.transit(self.engineer, identifier,
                                 "forward")["status"], "succeeded")
                self.assertEqual(self.engineer.location, end)
                self.assertEqual(
                    self.transit(self.engineer, identifier,
                                 "reverse")["status"], "succeeded")
                self.assertEqual(self.engineer.location, start)
                self.action("hatch", identifier, "closed")
                self.assertEqual(state("access", identifier).setting, "closed")

    def test_generic_hatch_controls_cannot_open_vacuum_or_freight_mechanisms(self):
        """The expanded crew-door control cannot spoof dedicated mechanisms."""
        from world.continuous_ship_physics import PhysicsError
        for link in (
            "ACC-F1-BAY", "ACC-DR-01-FREIGHT-CAPTURE",
            "ACC-EVA-AFT-EXT", "ACC-DR-01-LOCK-ROT",
        ):
            with self.subTest(mechanism=link):
                door = state("access", link)
                self.engineer.move_to(
                    find_ship_space(door.reference["from"]), quiet=True)
                prior = door.setting
                with self.assertRaises(PhysicsError):
                    self.action("hatch", link, "open")
                self.assertEqual(state("access", link).setting, prior)
