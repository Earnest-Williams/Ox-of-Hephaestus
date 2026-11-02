"""G19 real 180/300-second passenger carriage operations in installed Evennia.

Small, controlled engineering tests: never a 40-crew autonomous voyage.
"""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics,
    commission_g19_personnel_transfers, crew_physical_action,
    local_physics_readout, tick_continuous_physics, _clock,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition, state,
)
from world.models import CanonicalShipEvent, WorkReceipt
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.ship_world import ensure_canonical_ship, find_ship_space, find_world_entity


class InstalledPersonnelIndexers(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        self.assertTrue(
            commission_g19_personnel_transfers(operator_approved=True)["commissioned"])
        self.assertFalse(
            commission_g19_personnel_transfers(operator_approved=True)["commissioned"])
        crew = build_ship()
        self.tech, self.passenger = crew["watch"], crew["cargo"]

    def action(self, who, digit, kind, target, value):
        return crew_physical_action(who, digit * 32, kind, target, value)

    def advance(self, start, seconds):
        now = start
        for _ in range(int(seconds // 60)):
            now += 60
            tick_continuous_physics(now_game_time=now)
        return now

    def drum(self):
        self.tech.move_to(find_ship_space("DR-01-SERVICE-LOCK"), quiet=True)
        self.action(self.tech, "0", "rotor", "DR-01", "passenger_extend")
        return (find_world_entity("access:ACC-DR-01-LOCK-ROT:forward"),
                find_ship_space("DR-01-HUB"))

    def test_real_cargo_drum_passenger_and_return_cycles(self):
        outgoing, hub = self.drum()
        source = self.tech.location
        receipt = traverse_canonical_exit(
            self.tech, outgoing, hub, request_id="1" * 32)
        self.assertEqual(receipt["status"], "queued")
        self.assertEqual(receipt["travel_seconds"], 180)
        self.assertEqual(self.tech.location, source)
        self.assertEqual(local_physics_readout(self.tech, "personnel")[
            "stations_here"]["ACC-DR-01-LOCK-ROT"]["active_job"]["remaining_s"], 180)
        self.assertEqual(
            traverse_canonical_exit(self.tech, outgoing, hub, request_id="1" * 32),
            receipt)
        self.advance(1000, 120)
        self.assertEqual(self.tech.location, source)
        self.assertEqual(_clock().details["personnel_transfers"]["jobs"][
            "DR-01"]["remaining_s"], 60)
        tick_continuous_physics(now_game_time=1180)
        self.assertEqual(self.tech.location, hub)
        self.assertFalse(_clock().details["personnel_transfers"]["jobs"])
        self.assertEqual(_clock().details["personnel_transfers"]["completed"], 1)
        reverse = find_world_entity("access:ACC-DR-01-LOCK-ROT:reverse")
        back = traverse_canonical_exit(
            self.tech, reverse, source, request_id="2" * 32)
        self.assertEqual(back["status"], "queued")
        self.advance(1180, 180)
        self.assertEqual(self.tech.location, source)
        self.assertEqual(_clock().details["personnel_transfers"]["completed"], 2)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="crew_indexed_transfer_complete").count(), 2)
        self.assertEqual(WorkReceipt.objects.filter(pk="1" * 32).count(), 1)
        self.assertEqual(
            traverse_canonical_exit(self.tech, outgoing, hub, request_id="1" * 32),
            receipt)
        self.assertFalse(_clock().details["personnel_transfers"]["jobs"])

    def test_hardware_failure_and_power_loss_suspend_without_moving_crew(self):
        exit_obj, hub = self.drum()
        origin = self.tech.location
        traverse_canonical_exit(self.tech, exit_obj, hub, request_id="3" * 32)
        with self.assertRaisesRegex(PermissionError, "moving personnel carriage"):
            self.action(self.tech, "4", "rotor", "DR-01", "passenger_retract")
        set_isolator("ISO-GEN-M", "open", operator=True)
        tick_continuous_physics(now_game_time=1060)
        self.assertEqual(_clock().details["personnel_transfers"]["jobs"][
            "DR-01"]["remaining_s"], 180)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        set_component_condition(
            "equipment", "DR-01-PERSONNEL-INDEXER", "failed", operator=True)
        tick_continuous_physics(now_game_time=1120)
        self.assertEqual(_clock().details["personnel_transfers"]["jobs"][
            "DR-01"]["remaining_s"], 180)
        self.assertEqual(self.tech.location, origin)
        set_component_condition(
            "equipment", "DR-01-PERSONNEL-INDEXER", "serviceable", operator=True)
        self.advance(1120, 180)
        self.assertEqual(self.tech.location, hub)
        self.assertEqual(_clock().details["personnel_transfers"]["completed"], 1)

    def test_fixed_drum_hatch_and_rotary_capture_are_mutually_sealed(self):
        self.tech.move_to(find_ship_space("TRUNK-A-DR-01"), quiet=True)
        hatch = "ACC-DR-01-LOCK-FIX"
        fixed_exit = find_world_entity("access:" + hatch + ":forward")
        lock = find_ship_space("DR-01-SERVICE-LOCK")
        self.action(self.tech, "5", "hatch", hatch, "open")
        self.assertEqual(traverse_canonical_exit(
            self.tech, fixed_exit, lock, request_id="7" * 32)["status"],
            "succeeded")
        with self.assertRaises(PhysicsError):
            self.action(self.tech, "6", "rotor", "DR-01", "passenger_extend")
        self.assertEqual(state("access", hatch).setting, "open")
        self.action(self.tech, "8", "hatch", hatch, "closed")
        self.action(self.tech, "9", "rotor", "DR-01", "passenger_extend")
        with self.assertRaises(PhysicsError):
            self.action(self.tech, "a", "hatch", hatch, "open")
        self.assertEqual(state("access", hatch).setting, "closed")
        self.action(self.tech, "b", "rotor", "DR-01", "passenger_retract")
        self.action(self.tech, "c", "hatch", hatch, "open")
        self.assertEqual(state("access", hatch).setting, "open")

    def test_independent_hab_a_capture_and_300_second_transfer(self):
        fixed_hatch = "ACC-IX-A-FIX"
        self.tech.move_to(find_ship_space("HUB-FIXED-A"), quiet=True)
        self.passenger.move_to(find_ship_space("HUB-FIXED-A"), quiet=True)
        self.action(self.tech, "d", "hatch", fixed_hatch, "open")
        fixed_exit = find_world_entity("access:ACC-IX-A-FIX:forward")
        capsule = find_ship_space("IX-A-CAPSULE")
        self.assertEqual(traverse_canonical_exit(
            self.passenger, fixed_exit, capsule,
            request_id="e" * 32)["status"], "succeeded")
        self.action(self.tech, "f", "hatch", fixed_hatch, "closed")
        self.action(self.tech, "0", "rotor", "HAB", "passenger_extend:A")
        station_b = find_ship_space("HUB-FIXED-B")
        self.tech.move_to(station_b, quiet=True)
        with self.assertRaises(PhysicsError):
            self.action(self.tech, "1", "rotor", "HAB", "passenger_extend:B")
        self.tech.move_to(find_ship_space("HUB-FIXED-A"), quiet=True)
        exit_obj = find_world_entity("access:ACC-IX-A-ROT:forward")
        vest = find_ship_space("IX-A-ROT-VEST")
        receipt = traverse_canonical_exit(
            self.passenger, exit_obj, vest, request_id="2" * 32)
        self.assertEqual(receipt["travel_seconds"], 300)
        self.advance(1000, 240)
        self.assertEqual(self.passenger.location, capsule)
        tick_continuous_physics(now_game_time=1300)
        self.assertEqual(self.passenger.location, vest)
        self.assertEqual(_clock().details["personnel_transfers"]["completed"], 1)

    def test_workshop_rotor_indexer_and_20_second_personnel_transit(self):
        self.tech.move_to(find_ship_space("WR-FIXED-TRANSFER"), quiet=True)
        self.passenger.move_to(find_ship_space("WR-FIXED-TRANSFER"), quiet=True)
        self.action(self.tech, "a", "hatch", "ACC-WR-FIXED-IX", "open")
        capsule = find_ship_space("WR-IX-CAPSULE")
        fixed_exit = find_world_entity("access:ACC-WR-FIXED-IX:forward")
        self.assertEqual(traverse_canonical_exit(
            self.passenger, fixed_exit, capsule,
            request_id="b" * 32)["status"], "succeeded")
        self.action(self.tech, "c", "hatch", "ACC-WR-FIXED-IX", "closed")
        self.tech.move_to(find_ship_space("WR-ROTOR-MACHINERY"), quiet=True)
        self.action(self.tech, "d", "rotor", "WR-01", "passenger_extend")
        carrier_exit = find_world_entity("access:ACC-WR-IX-HUB:forward")
        hub = find_ship_space("WR-HUB")
        receipt = traverse_canonical_exit(
            self.passenger, carrier_exit, hub, request_id="e" * 32)
        self.assertEqual(receipt["status"], "queued")
        self.assertEqual(receipt["travel_seconds"], 20)
        tick_continuous_physics(now_game_time=1010)
        self.assertEqual(self.passenger.location, capsule)
        tick_continuous_physics(now_game_time=1020)
        self.assertEqual(self.passenger.location, hub)
        self.assertEqual(_clock().details["personnel_transfers"]["completed"], 1)
        self.assertEqual(_clock().details["rotors"]["WR-01"]["rpm"], 0)
        self.assertTrue(_clock().details["rotors"]["WR-01"]["passenger_indexer"])

    def test_hab_stays_rotating_during_actual_synchronised_boarding(self):
        from world.continuous_ship_physics import commission_g19_hab_sync
        self.assertTrue(commission_g19_hab_sync(
            operator_approved=True)["commissioned"])
        self.tech.move_to(find_ship_space("ENG-CONTROL"), quiet=True)
        self.action(self.tech, "0", "rotor", "HAB", "start")
        # Operate the real HAB drive for six game minutes: do not inject
        # a fictional stationary or pre-aligned carrier.
        self.advance(1000, 360)
        self.assertGreater(_clock().details["rotors"]["HAB"]["rpm"], 0.30)
        self.tech.move_to(find_ship_space("HUB-FIXED-A"), quiet=True)
        self.passenger.move_to(find_ship_space("IX-A-CAPSULE"), quiet=True)
        first = self.action(self.tech, "1", "rotor", "HAB", "sync:A")
        self.assertEqual(first["status"], "succeeded")
        self.tech.move_to(find_ship_space("ENG-CONTROL"), quiet=True)
        with self.assertRaises(PhysicsError):
            self.action(self.tech, "2", "rotor", "HAB", "sync:B")
        self.tech.move_to(find_ship_space("HUB-FIXED-A"), quiet=True)
        now = 1360
        for _ in range(20):
            now += 60
            tick_continuous_physics(now_game_time=now)
            if _clock().details["hab_sync"]["captured"]:
                break
        self.assertTrue(_clock().details["hab_sync"]["captured"])
        self.assertGreater(_clock().details["rotors"]["HAB"]["rpm"], 0.30)
        dest = find_ship_space("IX-A-ROT-VEST")
        exit_obj = find_world_entity("access:ACC-IX-A-ROT:forward")
        receipt = traverse_canonical_exit(
            self.passenger, exit_obj, dest, request_id="3" * 32)
        self.assertEqual(receipt["status"], "queued")
        self.assertEqual(self.passenger.location.db.ox_space_id, "IX-A-CAPSULE")
        for _ in range(5):
            now += 60
            tick_continuous_physics(now_game_time=now)
        self.assertEqual(self.passenger.location, dest)
        self.assertGreater(_clock().details["rotors"]["HAB"]["rpm"], 0.30)
        self.assertTrue(_clock().details["hab_sync"]["captured"])
        self.assertFalse(_clock().details["personnel_transfers"]["jobs"])
        self.action(self.tech, "4", "rotor", "HAB", "sync_release")
        self.assertEqual(_clock().details["hab_sync"]["mode"], "stowed")

    def test_bad_pressure_stops_initial_carriage_capture(self):
        from world.continuous_ship_physics import configure_scenario_casualty
        self.tech.move_to(find_ship_space("DR-02-SERVICE-LOCK"), quiet=True)
        self.action(self.tech, "3", "rotor", "DR-02", "passenger_extend")
        configure_scenario_casualty(
            "PZ-DR-02-SVC", leak_kg_s=5, operator=True)
        dest = find_ship_space("DR-02-HUB")
        exit_obj = find_world_entity("access:ACC-DR-02-LOCK-ROT:forward")
        with self.assertRaises(CrewTransitError):
            traverse_canonical_exit(
                self.tech, exit_obj, dest, request_id="4" * 32)
        self.assertFalse(WorkReceipt.objects.filter(pk="4" * 32).exists())


