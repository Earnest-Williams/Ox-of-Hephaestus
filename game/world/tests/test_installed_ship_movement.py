"""Authoritative G19 movement commissioning and crew operation tests.

Runs against installed 421-space Evennia ship and its selected 0.5 mass
contract. Tests intentionally stage actors; they do not assert crew routing.
"""
import math

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_movement,
    _clock,
    survey_cargo_lot, commission_ftl_route, commission_commercial_port,
    crew_physical_action, local_physics_readout, tick_continuous_physics,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells,
    initialize_nominal_atmosphere, load_candidate, set_isolator, state,
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
        # The installed generator feeder is normally isolated: explicitly
        # energise it before expecting motor, navigation or drive work.
        set_isolator("ISO-GEN-M", "closed", operator=True)

    def test_mass_commission_matches_authored_departure(self):
        contract = load_candidate()["mass"]
        motion = _clock().details["motion"]
        expected = contract["reference_departure_t"] * 1000
        actual = sum(motion[k] for k in (
            "dry_mass_kg", "cargo_mass_kg", "ftl_fuel_kg",
            "mission_fluids_kg", "propellant_kg"))
        self.assertAlmostEqual(actual, expected)
        self.assertGreater(actual, 1e9)
        self.assertEqual(
            commission_g19_movement(operator_approved=True)["commissioned"],
            False)
        self.assertEqual(len(_clock().details["rotors"]), 8)

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
            _clock().details["rotors"]["HAB"]["rpm"],
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
        self.assertEqual(_clock().details[
            "motion"]["drive_condition"], "inhibited")
        self.assertEqual(
            crew_physical_action(tech, "6" * 32, "drive", "MAIN", "inhibit"),
            first)
        crew_physical_action(tech, "7" * 32, "drive", "MAIN", "release")
        self.assertEqual(_clock().details[
            "motion"]["drive_condition"], "operational")
        tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        with self.assertRaises(PermissionError):
            crew_physical_action(tech, "8" * 32, "drive", "MAIN", "inhibit")

    def test_propulsion_heat_trips_and_requires_cooled_local_reset(self):
        officer = build_ship()["officer"]
        officer.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        crew_physical_action(officer, "9" * 32, "helm", "HELM", "x+")
        clock = _clock()
        details = dict(clock.details)
        movement = dict(details["motion"])
        movement["drive_heat_kj"] = 149_999_000.0
        details["motion"] = movement
        clock.details = details
        clock.save(update_fields=["details"])
        tick_continuous_physics(now_game_time=1010)
        motion = _clock().details["motion"]
        self.assertEqual(motion["drive_condition"], "thermal_trip")
        self.assertEqual(motion["command"], "coast")
        tech = build_ship()["watch"]
        tech.move_to(find_ship_space("PROP-CTRL"), quiet=True)
        with self.assertRaises(PhysicsError):
            crew_physical_action(tech, "a" * 32, "drive", "MAIN", "inhibit")
        with self.assertRaises(PhysicsError):
            crew_physical_action(tech, "b" * 32, "drive", "MAIN", "reset")

    def test_cargo_survey_and_declared_balance_preserve_ship_mass(self):
        with self.assertRaises(PermissionError):
            survey_cargo_lot(
                operation="declare", lot_id="UNIT001", mass_kg=100,
                drum="DR-01", azimuth_deg=0, radius_m=20)
        first = survey_cargo_lot(
            operator_approved=True, operation="declare", lot_id="UNIT001",
            mass_kg=100, drum="DR-01", azimuth_deg=0, radius_m=20,
            kind="sled")
        self.assertEqual(first["lots"], 1)
        survey_cargo_lot(
            operator_approved=True, operation="verify", drum="DR-01")
        clock = _clock()
        cargo = clock.details["cargo"]
        self.assertEqual(cargo["lots"]["UNIT001"]["location"], "DR-01")
        self.assertEqual(cargo["unlocated_onboard_kg"],
                         clock.details["motion"]["cargo_mass_kg"] - 100)
        tick_continuous_physics(now_game_time=1010)
        clock = _clock()
        self.assertAlmostEqual(
            clock.details["rotors"]["DR-01"]["imbalance_kg_m"], 2000)
        self.assertEqual(
            clock.details["motion"]["cargo_mass_kg"], 900_000_000.0)
        with self.assertRaises(PhysicsError):
            survey_cargo_lot(
                operator_approved=True, operation="declare",
                lot_id="IMPOSSIBLE", mass_kg=900_000_000,
                drum="DR-02", azimuth_deg=0, radius_m=20)

    def test_installed_propulsion_controller_casualty_prevents_thrust(self):
        officer = build_ship()["officer"]
        officer.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        panel = state("equipment", "LP-CMD-PRIMARY")
        panel.condition = "failed"
        panel.save(update_fields=["condition"])
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                officer, "a" * 31 + "0", "helm", "HELM", "x+")
        panel.condition = "serviceable"
        panel.save(update_fields=["condition"])
        crew_physical_action(
            officer, "a" * 31 + "1", "helm", "HELM", "x+")
        controller = state("equipment", "LCS-PROP")
        controller.condition = "failed"
        controller.save(update_fields=["condition"])
        tick_continuous_physics(now_game_time=1010)
        self.assertFalse(_clock().details["motion"]["drive_firing"])
        controller.condition = "serviceable"
        controller.save(update_fields=["condition"])
        tick_continuous_physics(now_game_time=1020)
        self.assertTrue(_clock().details["motion"]["drive_firing"])
        self.assertGreater(_clock().details["motion"]["velocity_m_s"][0], 0)

    def test_freight_action_requires_local_environmental_proof(self):
        survey_cargo_lot(
            operator_approved=True, operation="declare",
            lot_id="FRT001", mass_kg=1000, drum="DR-01",
            azimuth_deg=0, radius_m=0.5, kind="sled")
        survey_cargo_lot(
            operator_approved=True, operation="verify", drum="DR-01")
        tech = build_ship()["cargo"]
        tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        with self.assertRaises(PermissionError):
            crew_physical_action(
                tech, "c" * 32, "freight", "FRT001", "to_lock")
        self.assertFalse(
            __import__("world.models", fromlist=["WorkReceipt"]).WorkReceipt
            .objects.filter(pk="c" * 32).exists())

    def test_ftl_plan_engages_only_with_authorised_bridge_watch(self):
        with self.assertRaises(PermissionError):
            commission_ftl_route(
                route_id="TEST01", destination="TARGET", distance_ly=0.5,
                cruise_c=5)
        plan = commission_ftl_route(
            operator_approved=True, route_id="TEST01",
            destination="TARGET", distance_ly=0.5, cruise_c=5)
        self.assertEqual(plan["status"], "planned")
        officer = build_ship()["officer"]
        officer.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        result = crew_physical_action(
            officer, "d" * 32, "ftl", "TEST01", "engage")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(
            crew_physical_action(officer, "d" * 32, "ftl", "TEST01", "engage"),
            result)
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                officer, "e" * 32, "helm", "HELM", "x+")
        original = _clock().details[
            "motion"]["ftl_fuel_kg"]
        tick_continuous_physics(now_game_time=1010)
        after = _clock().details["motion"]
        self.assertLess(after["ftl_fuel_kg"], original)
        self.assertEqual(after["ftl_leg"]["status"], "engaged")
        self.assertFalse(after["drive_firing"])
        crew_physical_action(
            officer, "f" * 32, "ftl", "TEST01", "abort")
        self.assertEqual(
            _clock().details[
                "motion"]["ftl_leg"]["status"], "aborted")
        self.assertNotEqual(
            _clock().details[
                "motion"]["nav_location"], "TARGET")

    def test_docked_berth_prevents_helm_ftl_and_drum_release(self):
        with self.assertRaises(PermissionError):
            commission_commercial_port(
                operation="dock", portal_id="DR-01-P1", berth_id="BERTH-1")
        contact = commission_commercial_port(
            operator_approved=True, operation="dock",
            portal_id="DR-01-P1", berth_id="BERTH-1")
        self.assertEqual(contact["docked"], ["DR-01-P1"])
        officer = build_ship()["officer"]
        officer.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                officer, "0" * 32, "helm", "HELM", "x+")
        commission_ftl_route(
            operator_approved=True, route_id="MOOR01", destination="ASTAR",
            distance_ly=0.5, cruise_c=5)
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                officer, "e" * 32, "ftl", "MOOR01", "engage")
        tech = build_ship()["watch"]
        tech.move_to(find_ship_space("DR-01-FREIGHT-LOCK"), quiet=True)
        for cmd in ("start", "release", "index", "freight_extend"):
            with self.assertRaises(PhysicsError):
                crew_physical_action(
                    tech, {"start": "1", "release": "2", "index": "3",
                           "freight_extend": "4"}[cmd] * 32,
                    "rotor", "DR-01", cmd)
        commission_commercial_port(
            operator_approved=True, operation="undock",
            portal_id="DR-01-P1", berth_id="BERTH-1")
        crew_physical_action(
            officer, "5" * 32, "helm", "HELM", "x+")

    def test_real_port_transfer_reversal_updates_ship_mass_incrementally(self):
        survey_cargo_lot(
            operator_approved=True, operation="declare", lot_id="OREPORT",
            mass_kg=200_000, drum="DR-01", azimuth_deg=0, radius_m=0.01)
        commission_commercial_port(
            operator_approved=True, operation="dock",
            portal_id="DR-01-P1", berth_id="BERTH-TEST")
        worker = build_ship()["cargo"]
        worker.move_to(find_ship_space("CARGO-CTRL-FWD"), quiet=True)
        receipt = crew_physical_action(
            worker, "1" * 31 + "a", "port", "DR-01-P1", "unload:OREPORT")
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(crew_physical_action(
            worker, "1" * 31 + "a", "port", "DR-01-P1", "unload:OREPORT"),
            receipt)
        tick_continuous_physics(now_game_time=1060)
        tick_continuous_physics(now_game_time=1070)
        motion = _clock().details["motion"]
        self.assertEqual(motion["cargo_mass_kg"], 900_000_000 - 15_000)
        self.assertEqual(_clock().details["cargo"]["delivered_offship_kg"],
                         15_000)
        with self.assertRaises(PhysicsError):
            commission_commercial_port(
                operator_approved=True, operation="undock",
                portal_id="DR-01-P1", berth_id="BERTH-TEST")
        crew_physical_action(
            worker, "2" * 31 + "a", "port", "DR-01-P1", "pause:OREPORT")
        tick_continuous_physics(now_game_time=1080)
        self.assertEqual(_clock().details["motion"]["cargo_mass_kg"],
                         900_000_000 - 15_000)
        crew_physical_action(
            worker, "3" * 31 + "a", "port", "DR-01-P1", "abort:OREPORT")
        tick_continuous_physics(now_game_time=1140)
        self.assertEqual(_clock().details["motion"]["cargo_mass_kg"],
                         900_000_000 - 15_000)
        tick_continuous_physics(now_game_time=1150)
        self.assertEqual(_clock().details["motion"]["cargo_mass_kg"],
                         900_000_000)
        self.assertFalse(_clock().details["cargo"]["port_jobs"])
        commission_commercial_port(
            operator_approved=True, operation="undock",
            portal_id="DR-01-P1", berth_id="BERTH-TEST")

    def test_explicit_migration_preserves_motion_and_reconciles_mass(self):
        clock = _clock()
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
        updated = _clock().details["motion"]
        self.assertEqual(updated["position_m"], [1000, 2000, -800])
        self.assertEqual(updated["velocity_m_s"], [3, 0, 0])
        contract = load_candidate()["mass"]
        self.assertAlmostEqual(
            updated["propellant_kg"] + updated["expended_propellant_kg"],
            contract["sublight_reaction_mass_t"] * 1000)
