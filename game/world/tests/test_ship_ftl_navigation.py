"""Pure FTL mission-contract regressions: finite bunker, time and outages."""
import unittest

from world.ship_ftl_navigation import (
    NavigationError, leg_fuel_kg, prepare_leg, command_leg, advance_leg,
)


def motion():
    return {
        "dry_mass_kg": 275_000_000.0,
        "cargo_mass_kg": 900_000_000.0,
        "ftl_fuel_kg": 6_000_000.0,
        "expended_ftl_fuel_kg": 0.0,
        "mission_fluids_kg": 1_500_000.0,
        "propellant_kg": 5_000_000.0,
        "angular_velocity_rad_s": [0.0, 0.0, 0.0],
        "command": "coast", "attitude_command": "hold",
        "ftl_leg": None, "nav_location": "unknown",
    }


class FtlContracts(unittest.TestCase):
    def test_economy_cost_matches_authored_v05_curve(self):
        self.assertAlmostEqual(
            leg_fuel_kg(1.0, 5.0, 1_187_500_000),
            400_000 * 1_187_500 / 1_200_000)
        self.assertGreater(
            leg_fuel_kg(1.0, 100.0, 1_187_500_000),
            leg_fuel_kg(1.0, 5.0, 1_187_500_000))
        for speed in (0.0, 4.99, 101.0, float("nan")):
            with self.assertRaises(NavigationError):
                leg_fuel_kg(1.0, speed, 1_187_500_000)

    def test_commissioned_leg_cannot_spend_emergency_bunker(self):
        with self.assertRaises(NavigationError):
            prepare_leg(
                motion(), route_id="IMPOSSIBLE", destination="FAR",
                distance_ly=15.0, speed_c=5.0)
        planned = prepare_leg(
            motion(), route_id="A1", destination="B1",
            distance_ly=1.0, speed_c=5.0)
        self.assertEqual(planned["ftl_leg"]["status"], "planned")
        with self.assertRaises(NavigationError):
            prepare_leg(
                planned, route_id="A2", destination="B2",
                distance_ly=1.0, speed_c=5.0)

    def test_progress_reduces_bunker_exactly_and_arrives(self):
        planned = prepare_leg(
            motion(), route_id="A1", destination="B1",
            distance_ly=0.01, speed_c=5.0)
        underway = command_leg(planned, "A1", "engage")
        original = underway["ftl_fuel_kg"]
        cost = underway["ftl_leg"]["total_fuel_kg"]
        remaining = underway["ftl_leg"]["duration_s"]
        while remaining > 0:
            step = min(60, remaining)
            underway, draw = advance_leg(
                underway, step, field_healthy=True, power_headroom_mw=0.3)
            self.assertAlmostEqual(draw, 0.20)
            remaining = underway["ftl_leg"]["remaining_s"]
        self.assertEqual(underway["ftl_leg"]["status"], "arrived")
        self.assertEqual(underway["nav_location"], "B1")
        self.assertAlmostEqual(
            underway["ftl_fuel_kg"] + underway["expended_ftl_fuel_kg"],
            original, places=5)
        self.assertAlmostEqual(underway["expended_ftl_fuel_kg"], cost, places=5)

    def test_ftl_freezes_actual_departure_mass_after_port_activity(self):
        light = motion()
        light["cargo_mass_kg"] -= 200_000_000
        planned = prepare_leg(
            light, route_id="DEPART", destination="PORT2",
            distance_ly=0.5, speed_c=5)
        self.assertEqual(planned["ftl_leg"]["status"], "planned")
        previous_cost = planned["ftl_leg"]["total_fuel_kg"]
        # Dockside loading occurs after the plan but before departure.
        loaded = dict(planned, cargo_mass_kg=900_000_000)
        engaged = command_leg(loaded, "DEPART", "engage")
        self.assertGreater(engaged["ftl_leg"]["total_fuel_kg"], previous_cost)
        mass = sum(engaged[k] for k in (
            "dry_mass_kg", "cargo_mass_kg", "ftl_fuel_kg",
            "mission_fluids_kg", "propellant_kg"))
        self.assertAlmostEqual(
            engaged["ftl_leg"]["total_fuel_kg"], leg_fuel_kg(0.5, 5, mass))
        self.assertEqual(engaged["ftl_leg"]["departure_mass_kg"], mass)
        # A heavier ship cannot consume a cheaper pre-loading plan.
        long_plan = prepare_leg(
            light, route_id="TIGHT", destination="PORT2",
            distance_ly=13.0, speed_c=5)
        too_heavy = dict(long_plan, cargo_mass_kg=900_000_000)
        with self.assertRaises(NavigationError):
            command_leg(too_heavy, "TIGHT", "engage")
        self.assertEqual(long_plan["ftl_leg"]["status"], "planned")

    def test_power_or_field_failure_does_not_teleport(self):
        planned = prepare_leg(
            motion(), route_id="A1", destination="B1",
            distance_ly=1.0, speed_c=5.0)
        active = command_leg(planned, "A1", "engage")
        for healthy, power in [(False, 1.0), (True, 0.0)]:
            failed, draw = advance_leg(
                active, 10, field_healthy=healthy, power_headroom_mw=power)
            self.assertEqual(failed["ftl_leg"]["status"], "aborted")
            self.assertEqual(failed["nav_location"], "unknown")
            self.assertEqual(draw, 0)
            self.assertEqual(failed["ftl_fuel_kg"], 6_000_000)

    def test_helm_or_attitude_motion_blocks_translation(self):
        for key, value in [("command", "x+"),
                           ("attitude_command", "yaw+")]:
            altered = motion()
            altered[key] = value
            planned = prepare_leg(
                altered, route_id="A1", destination="B1",
                distance_ly=1, speed_c=5)
            with self.assertRaises(NavigationError):
                command_leg(planned, "A1", "engage")


if __name__ == "__main__":
    unittest.main()
