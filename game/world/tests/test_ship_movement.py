"""Movement mechanical state-machine regressions for Ox's fictional freighter.

These pure tests exercise meaningful casualty gates and conservation without
requiring an Evennia server or a NASA-quality flight dynamics package.
"""
import unittest

from world.ship_motion_machinery import (
    DRUMS, ROTORS, RotorError, initial_rotors, motion_power_mw,
    rotor_gravity, set_rotor_command, step_rotors,
)
from world.continuous_ship_physics import _advance_motion


POWER = dict(
    available_mw=3.3, requested_mw=1.35, dispatched_mw=1.35,
    assured=True, essential_assured=True,
)


def motion():
    return {
        "position_m": [0.0, 0.0, 0.0],
        "velocity_m_s": [0.0, 0.0, 0.0],
        "dry_mass_kg": 100_000_000.0,
        "cargo_mass_kg": 900_000_000.0,
        "cargo_capacity_kg": 900_000_000.0,
        "ftl_fuel_kg": 1_000_000.0,
        "mission_fluids_kg": 1_000_000.0,
        "propellant_kg": 10_000_000.0,
        "expended_propellant_kg": 0.0,
        "command": "x+",
        "attitude_rad": [0.0, 0.0, 0.0],
        "angular_velocity_rad_s": [0.0, 0.0, 0.0],
        "attitude_command": "hold",
    }


class ShipMovementRegressions(unittest.TestCase):
    def test_independent_rotors_and_slow_start(self):
        rotors = initial_rotors()
        self.assertEqual(set(rotors), set(ROTORS))
        self.assertEqual(len(DRUMS), 6)
        rotors = set_rotor_command(rotors, "WR-01", "start")
        rotors = step_rotors(rotors, 10.0, powered=True)
        self.assertGreater(rotors["WR-01"]["rpm"], 0)
        self.assertLess(rotors["WR-01"]["rpm"], 3.45)
        self.assertEqual(rotors["HAB"]["rpm"], 0)
        self.assertGreater(rotor_gravity(rotors, "WR-01"), 0)
        self.assertGreater(motion_power_mw(rotors), 0)

    def test_workshop_freight_requires_slow_carriage_retraction(self):
        rotors = initial_rotors()
        with self.assertRaises(RotorError):
            set_rotor_command(rotors, "WR-01", "freight_extend")
        rotors = set_rotor_command(rotors, "WR-01", "radius:24")
        for _ in range(100):
            rotors = step_rotors(rotors, 10, powered=True)
        wr = rotors["WR-01"]
        self.assertAlmostEqual(wr["work_radius_m"], 24.0)
        self.assertAlmostEqual(wr["stores_radius_m"], 8.0)
        rotors = set_rotor_command(rotors, "WR-01", "freight_extend")
        with self.assertRaises(RotorError):
            set_rotor_command(rotors, "WR-01", "start")
        rotors = set_rotor_command(rotors, "WR-01", "freight_retract")
        rotors = set_rotor_command(rotors, "WR-01", "radius:60")
        for _ in range(100):
            rotors = step_rotors(rotors, 10, powered=True)
        self.assertAlmostEqual(rotors["WR-01"]["work_radius_m"], 60)

    def test_freight_and_passenger_interlocks(self):
        rotors = initial_rotors()
        rotors = set_rotor_command(rotors, "DR-01", "freight_extend")
        with self.assertRaises(RotorError):
            set_rotor_command(rotors, "DR-01", "passenger_extend")
        with self.assertRaises(RotorError):
            set_rotor_command(rotors, "DR-01", "start")
        rotors = set_rotor_command(rotors, "DR-01", "freight_retract")
        rotors = set_rotor_command(rotors, "DR-01", "start")
        rotors = step_rotors(rotors, 10, powered=True)
        with self.assertRaises(RotorError):
            set_rotor_command(rotors, "DR-01", "hardlock")

    def test_rotary_freight_realign_requires_index_and_power(self):
        rotors = set_rotor_command(initial_rotors(), "DR-02", "start")
        rotors = step_rotors(rotors, 10, powered=True)
        rotors = set_rotor_command(rotors, "DR-02", "stop")
        for _ in range(100):
            rotors = step_rotors(rotors, 10, powered=True)
            if rotors["DR-02"]["rpm"] == 0:
                break
        self.assertEqual(rotors["DR-02"]["rpm"], 0)
        with self.assertRaises(RotorError):
            set_rotor_command(rotors, "DR-02", "hardlock")
        rotors = set_rotor_command(rotors, "DR-02", "index")
        phase = rotors["DR-02"]["phase_rad"]
        rotors = step_rotors(rotors, 10, powered=False)
        self.assertAlmostEqual(rotors["DR-02"]["phase_rad"], phase)
        for _ in range(40):
            rotors = step_rotors(rotors, 10, powered=True)
            if not rotors["DR-02"]["indexing"]:
                break
        self.assertEqual(rotors["DR-02"]["phase_rad"], 0)
        self.assertFalse(rotors["DR-02"]["indexing"])
        rotors = set_rotor_command(rotors, "DR-02", "hardlock")
        self.assertTrue(rotors["DR-02"]["hardlock"])

    def test_nominal_bearing_heat_stabilises(self):
        rotors = set_rotor_command(initial_rotors(), "WR-01", "start")
        for _ in range(5000):
            rotors = step_rotors(rotors, 10, powered=True)
        self.assertNotEqual(rotors["WR-01"]["condition"], "faulted")
        self.assertGreater(rotors["WR-01"]["bearing_hours"], 0)

    def test_failed_rotor_spins_down_not_instant_stop(self):
        rotors = set_rotor_command(initial_rotors(), "HAB", "start")
        rotors = step_rotors(rotors, 10, powered=True)
        spinning = rotors["HAB"]["rpm"]
        rotors = step_rotors(rotors, 10, powered=False,
                            equipment_ok={"HAB": False})
        self.assertGreater(rotors["HAB"]["rpm"], 0)
        self.assertLess(rotors["HAB"]["rpm"], spinning)
        self.assertEqual(rotors["HAB"]["mode"], "TRIPPED")

    def test_finite_propellant_and_mass_dependence(self):
        m = motion()
        heavy = _advance_motion(m, 10.0, POWER)
        light = dict(m, cargo_mass_kg=0.0)
        lighter = _advance_motion(light, 10.0, POWER)
        self.assertGreater(lighter["velocity_m_s"][0],
                           heavy["velocity_m_s"][0])
        self.assertGreater(heavy["velocity_m_s"][0], 0)
        self.assertAlmostEqual(
            heavy["propellant_kg"] + heavy["expended_propellant_kg"],
            m["propellant_kg"], places=6)

    def test_independent_rcs_consumes_propellant_without_main_thrust(self):
        m = motion()
        m["command"] = "coast"
        m["attitude_command"] = "yaw+"
        result = _advance_motion(m, 10, POWER, drive_operational=False)
        self.assertFalse(result["drive_firing"])
        self.assertTrue(result["attitude_firing"])
        self.assertGreater(result["angular_velocity_rad_s"][1], 0)
        self.assertLess(result["propellant_kg"], m["propellant_kg"])
        self.assertAlmostEqual(
            result["propellant_kg"] + result["expended_propellant_kg"],
            m["propellant_kg"], places=6)

    def test_attitude_rotates_engine_thrust(self):
        m = motion()
        m["attitude_rad"] = [1.5707963267948966, 0, 0]
        result = _advance_motion(m, 10, POWER)
        self.assertAlmostEqual(result["velocity_m_s"][0], 0.0, places=8)
        self.assertLess(result["velocity_m_s"][2], 0)

    def test_yaw_rotates_forward_thrust_onto_ship_y_axis(self):
        m = motion()
        m["attitude_rad"] = [0, 1.5707963267948966, 0]
        result = _advance_motion(m, 10, POWER)
        self.assertAlmostEqual(result["velocity_m_s"][0], 0.0, places=8)
        self.assertGreater(result["velocity_m_s"][1], 0.0)
        self.assertAlmostEqual(result["velocity_m_s"][2], 0.0, places=8)

    def test_blackout_coasts_without_extra_propellant(self):
        m = motion()
        m["velocity_m_s"] = [3.0, 0.0, 0.0]
        blacked_out = dict(POWER, available_mw=0.0,
                           dispatched_mw=0.0, assured=False,
                           essential_assured=False)
        result = _advance_motion(m, 10, blacked_out)
        self.assertEqual(result["position_m"][0], 30.0)
        self.assertEqual(result["propellant_kg"], m["propellant_kg"])


if __name__ == "__main__":
    unittest.main()
