"""Mechanical propulsion acceptance requires expended propellant AND delta-v."""
import unittest
from world.ship_propulsion_proof import (
    DriveProofError, initial_drive_proof, start_drive_proof,
    verify_drive_proof, validate_drive_proof,
)

def ship():
    return {"command": "coast", "drive_condition": "operational",
            "drive_firing": False, "expended_propellant_kg": 10.0,
            "velocity_m_s": [100.0, 0.0, 0.0],
            "ftl_leg": {"status": "idle"}}

class WitnessTests(unittest.TestCase):
    def test_no_output_or_one_signal_cannot_pass(self):
        initial = start_drive_proof(
            initial_drive_proof(), actor="#1", motion=ship(), game_time=100)
        with self.assertRaises(DriveProofError):
            verify_drive_proof(initial, actor="#1", motion=ship(), game_time=110)
        fuel_only = dict(ship(), expended_propellant_kg=12.0)
        with self.assertRaises(DriveProofError):
            verify_drive_proof(initial, actor="#1", motion=fuel_only, game_time=110)
        motion_only = dict(ship(), velocity_m_s=[102.0, 0, 0])
        with self.assertRaises(DriveProofError):
            verify_drive_proof(initial, actor="#1", motion=motion_only, game_time=110)
        with self.assertRaises(DriveProofError):
            verify_drive_proof(initial, actor="#2", motion=ship(), game_time=110)

    def test_real_elapsed_burn_can_be_proved_once(self):
        origin = ship()
        initial = start_drive_proof(
            initial_drive_proof(), actor="#1", motion=origin, game_time=100)
        after = dict(origin, expended_propellant_kg=17.0,
                     velocity_m_s=[103.0, 4.0, 0.0])
        verified = verify_drive_proof(
            initial, actor="#1", motion=after, game_time=150)
        self.assertTrue(validate_drive_proof(verified))
        self.assertEqual(verified["last_verified"]["propellant_kg"], 7)
        self.assertEqual(verified["last_verified"]["delta_v_m_s"], 5)
        self.assertEqual(verified["completed"], 1)
        with self.assertRaises(DriveProofError):
            verify_drive_proof(verified, actor="#1", motion=after, game_time=150)

    def test_no_witness_while_firing_or_ftl_or_inhibited(self):
        for altered in (
                {"command": "x+"}, {"drive_firing": True},
                {"drive_condition": "inhibited"},
                {"ftl_leg": {"status": "engaged"}}):
            with self.subTest(altered=altered), self.assertRaises(DriveProofError):
                start_drive_proof(
                    initial_drive_proof(), actor="#1",
                    motion=dict(ship(), **altered), game_time=100)

if __name__ == "__main__":
    unittest.main()
