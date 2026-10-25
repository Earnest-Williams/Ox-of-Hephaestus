"""Authoritative G19 movement commissioning and crew operation tests.

Runs against installed 421-space Evennia ship and its selected 0.5 mass
contract. Tests intentionally stage actors; they do not assert crew routing.
"""
import math

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_movement,
    crew_physical_action, local_physics_readout, tick_continuous_physics,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells,
    initialize_nominal_atmosphere, load_candidate, state,
)
from world.ship_world import build_canonical_ship, find_ship_space


class InstalledMovementTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)

    def test_mass_commission_matches_authored_departure(self):
        contract = load_candidate()["mass"]
        motion = state("meta", "continuous-physics").details["motion"]
        expected = contract["reference_departure_t"] * 1000
        actual = sum(motion[k] for k in (
            "dry_mass_kg", "cargo_mass_kg", "ftl_fuel_kg",
            "mission_fluids_kg", "propellant_kg"))
        self.assertAlmostEqual(actual, expected)
        self.assertGreater(actual, 1e9)
        self.assertEqual(
            commission_g19_movement(operator_approved=True)["commissioned"],
            False)
        self.assertEqual(len(state("meta", "continuous-physics").details["rotors"]), 8)

    def test_crew_rotor_control_is_local_and_receipted(self):
        tech = build_ship()["watch"]
        tech.move_to(find_ship_space("DR-01-FREIGHT-LOCK"), quiet=True)
        request_id = "1" * 32
        receipt = crew_physical_action(
            tech, request_id, "rotor", "DR-01", "start")
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(
            crew_physical_action(tech, request_id, "rotor", "DR-01", "start"),
            receipt)
        tick_continuous_physics(now_game_time=1010)
        gauge = local_physics_readout(tech, "DR-01")
        self.assertGreater(gauge["rpm"], 0)
        self.assertEqual(
            state("meta", "continuous-physics").details["rotors"]["HAB"]["rpm"],
            0.0)
        with self.assertRaises(PhysicsError):
            crew_physical_action(tech, "2" * 32,
                                 "rotor", "DR-01", "freight_extend")

    def test_nonlocal_rotor_control_denied(self):
        tech = build_ship()["watch"]
        tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        with self.assertRaises(PermissionError):
            crew_physical_action(tech, "3" * 32, "rotor", "DR-01", "start")

    def test_helm_is_not_engine_room_generator_switch(self):
        officer = build_ship()["officer"]
        officer.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        receipt = crew_physical_action(
            officer, "4" * 32, "helm", "HELM", "x+")
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(local_physics_readout(officer, "helm")["motion"]["command"], "x+")
        tech = build_ship()["watch"]
        tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        with self.assertRaises(PermissionError):
            crew_physical_action(tech, "5" * 32, "helm", "HELM", "x+")

    def test_aft_propulsion_inhibit_is_local_and_recoverable(self):
        tech = build_ship()["watch"]
        tech.move_to(find_ship_space("PROP-CTRL"), quiet=True)
        first = crew_physical_action(tech, "6" * 32, "drive", "MAIN", "inhibit")
        self.assertEqual(first["status"], "succeeded")
        self.assertEqual(state("meta", "continuous-physics").details[
            "motion"]["drive_condition"], "inhibited")
        self.assertEqual(
            crew_physical_action(tech, "6" * 32, "drive", "MAIN", "inhibit"),
            first)
        crew_physical_action(tech, "7" * 32, "drive", "MAIN", "release")
        self.assertEqual(state("meta", "continuous-physics").details[
            "motion"]["drive_condition"], "operational")
        tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        with self.assertRaises(PermissionError):
            crew_physical_action(tech, "8" * 32, "drive", "MAIN", "inhibit")

    def test_propulsion_heat_trips_and_requires_cooled_local_reset(self):
        officer = build_ship()["officer"]
        officer.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        crew_physical_action(officer, "9" * 32, "helm", "HELM", "x+")
        clock = state("meta", "continuous-physics")
        details = dict(clock.details)
        movement = dict(details["motion"])
        movement["drive_heat_kj"] = 149_999_000.0
        details["motion"] = movement
        clock.details = details
        clock.save(update_fields=["details"])
        tick_continuous_physics(now_game_time=1010)
        motion = state("meta", "continuous-physics").details["motion"]
        self.assertEqual(motion["drive_condition"], "thermal_trip")
        self.assertEqual(motion["command"], "coast")
        tech = build_ship()["watch"]
        tech.move_to(find_ship_space("PROP-CTRL"), quiet=True)
        with self.assertRaises(PhysicsError):
            crew_physical_action(tech, "a" * 32, "drive", "MAIN", "inhibit")
        with self.assertRaises(PhysicsError):
            crew_physical_action(tech, "b" * 32, "drive", "MAIN", "reset")

    def test_explicit_migration_preserves_motion_and_reconciles_mass(self):
        clock = state("meta", "continuous-physics")
        previous = dict(clock.details)
        legacy = dict(previous["motion"])
        legacy["position_m"] = [1000.0, 2000.0, -800.0]
        legacy["velocity_m_s"] = [3.0, 0.0, 0.0]
        legacy["expended_propellant_kg"] = 42.0
        for key in ("dry_mass_kg", "ftl_fuel_kg",
                    "mission_fluids_kg", "cargo_capacity_kg"):
            legacy.pop(key)
        legacy["cargo_mass_kg"] = 0.0
        legacy["propellant_kg"] = 240000.0 - 42.0
        previous["motion"] = legacy
        previous.pop("rotors")
        clock.details = previous
        clock.save(update_fields=["details"])
        with self.assertRaises(PermissionError):
            commission_g19_movement()
        report = commission_g19_movement(operator_approved=True)
        self.assertTrue(report["commissioned"])
        updated = state("meta", "continuous-physics").details["motion"]
        self.assertEqual(updated["position_m"], [1000, 2000, -800])
        self.assertEqual(updated["velocity_m_s"], [3, 0, 0])
        contract = load_candidate()["mass"]
        self.assertAlmostEqual(
            updated["propellant_kg"] + updated["expended_propellant_kg"],
            contract["sublight_reaction_mass_t"] * 1000)
