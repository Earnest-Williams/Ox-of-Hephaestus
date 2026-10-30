"""Finite RCS attitude acceptance needs actual torque and expended fuel."""
import unittest

from world.ship_rcs_proof import (
    RCSProofError, initial_rcs_proof, validate_rcs_proof,
    start_rcs_proof, verify_rcs_proof,
)


def motion():
    return {
        "command": "coast", "attitude_command": "hold",
        "drive_condition": "inhibited", "rcs_condition": "operational",
        "drive_firing": False, "attitude_firing": False,
        "ftl_leg": None, "expended_propellant_kg": 10.0,
        "angular_velocity_rad_s": [0.0, 0.0, 0.0],
    }


class TrueTorqueTests(unittest.TestCase):
    def start(self):
        return start_rcs_proof(
            initial_rcs_proof(), actor="#1", motion=motion(), game_time=1000)

    def test_no_fuel_only_or_angle_only_claim(self):
        first = self.start()
        with self.assertRaises(RCSProofError):
            verify_rcs_proof(first, actor="#1", motion=motion(),
                             game_time=1010)
        with self.assertRaises(RCSProofError):
            verify_rcs_proof(
                first, actor="#1",
                motion=dict(motion(), expended_propellant_kg=11),
                game_time=1010)
        with self.assertRaises(RCSProofError):
            verify_rcs_proof(
                first, actor="#1",
                motion=dict(motion(), angular_velocity_rad_s=[1e-5,0,0]),
                game_time=1010)
        with self.assertRaises(RCSProofError):
            verify_rcs_proof(
                first, actor="#2",
                motion=dict(motion(), expended_propellant_kg=11,
                            angular_velocity_rad_s=[1e-5,0,0]),
                game_time=1010)

    def test_actual_safed_attitude_burn_can_be_verified_once(self):
        first = self.start()
        after = dict(
            motion(), expended_propellant_kg=10.8,
            angular_velocity_rad_s=[0, 7.5e-6, 0])
        proven = verify_rcs_proof(
            first, actor="#1", motion=after, game_time=1020)
        self.assertTrue(validate_rcs_proof(proven))
        self.assertEqual(proven["completed"],1)
        self.assertAlmostEqual(
            proven["last_verified"]["delta_omega_rad_s"], 7.5e-6)
        self.assertAlmostEqual(proven["last_verified"]["spent_kg"],.8)
        with self.assertRaises(RCSProofError):
            verify_rcs_proof(
                proven, actor="#1", motion=after, game_time=1030)

    def test_burn_in_progress_dead_controller_and_ftl_forbidden(self):
        for altered in (
            {"attitude_command":"yaw+"},
            {"attitude_firing":True},
            {"drive_firing":True},
            {"rcs_condition":"inhibited"},
            {"ftl_leg":{"status":"engaged"}},
            {"command":"x+"},
        ):
            with self.subTest(altered=altered), self.assertRaises(RCSProofError):
                start_rcs_proof(initial_rcs_proof(), actor="#1",
                                motion=dict(motion(), **altered),
                                game_time=1000)
        old = self.start()
        during = dict(
            motion(), attitude_command="yaw+", attitude_firing=True,
            expended_propellant_kg=10.8,
            angular_velocity_rad_s=[0,7.5e-6,0])
        with self.assertRaises(RCSProofError):
            verify_rcs_proof(
                old, actor="#1", motion=during, game_time=1010)


if __name__ == "__main__":
    unittest.main()
