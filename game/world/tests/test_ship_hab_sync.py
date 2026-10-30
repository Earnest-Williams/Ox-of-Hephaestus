"""Moving HAB phase synchronisation does not stop the habitat."""
import unittest

from world.ship_hab_sync import (
    HabSyncError, initial_hab_sync, validate_hab_sync,
    command_hab_sync, step_hab_sync, moving_hab_ready,
)

class MovingHabTests(unittest.TestCase):
    def test_two_installed_stations_are_exclusive_and_finite(self):
        base = initial_hab_sync()
        with self.assertRaises(HabSyncError):
            command_hab_sync(base, "sync:A", hab_rpm=0)
        with self.assertRaises(HabSyncError):
            command_hab_sync(base, "sync:A", hab_rpm=2.0, parked_indexer=True)
        s = command_hab_sync(base, "sync:A", hab_rpm=2.0)
        self.assertEqual(s["mode"], "seeking")
        with self.assertRaises(HabSyncError):
            command_hab_sync(s, "sync:B", hab_rpm=2)
        self.assertEqual(base["mode"], "stowed")

    def test_independent_carrier_reaches_live_rotation_by_finite_acceleration(self):
        s = command_hab_sync(initial_hab_sync(), "sync:A", hab_rpm=2)
        for step in range(1, 51):
            phase = (2.0 * step * 10 * 3.141592653589793 / 30) % (2 * 3.141592653589793)
            old_rpm = s["rpm"]
            s = step_hab_sync(
                s, 10, hab_rpm=2, hab_phase_rad=phase,
                powered=True, hardware_ok=True)
            self.assertLessEqual(abs(s["rpm"] - old_rpm), .650001)
            if s["captured"]:
                self.assertTrue(moving_hab_ready(
                    s, station="A", hab_rpm=2,
                    hab_phase_rad=phase, powered=True, hardware_ok=True))
                self.assertFalse(moving_hab_ready(
                    s, station="B", hab_rpm=2,
                    hab_phase_rad=phase, powered=True, hardware_ok=True))
                break
        else:
            self.fail("Realistic moving indexer never synchronised")
        self.assertGreater(s["seconds_synchronising"], 10)
        with self.assertRaises(HabSyncError):
            command_hab_sync(s, "release", hab_rpm=2, occupied=True)
        released = command_hab_sync(s, "release", hab_rpm=2)
        self.assertEqual(released["mode"], "stowed")

    def test_loss_of_power_pauses_capture_and_a_live_transit(self):
        s = command_hab_sync(initial_hab_sync(), "sync:B", hab_rpm=1.0)
        u = step_hab_sync(s, 10, hab_rpm=1, hab_phase_rad=2,
                          powered=False, hardware_ok=True)
        self.assertFalse(u["captured"])
        self.assertEqual(u["rpm"], 0)
        for i in range(1, 40):
            p = (i * 10 * 1.0 * 3.141592653589793 / 30) % (2 * 3.141592653589793)
            u = step_hab_sync(u, 10, hab_rpm=1, hab_phase_rad=p,
                              powered=True, hardware_ok=True)
            if u["captured"]:
                self.assertFalse(moving_hab_ready(
                    u, station="B", hab_rpm=1, hab_phase_rad=p,
                    powered=False, hardware_ok=True))
                damaged = step_hab_sync(
                    u, 10, hab_rpm=1, hab_phase_rad=p,
                    powered=True, hardware_ok=False)
                self.assertFalse(damaged["captured"])
                break
        else:
            self.fail("Indexing station never captured")

    def test_nan_corruption_and_retrograde_time_refused(self):
        for bad in (float("nan"), float("inf"), -1, 10.01):
            with self.assertRaises(HabSyncError):
                step_hab_sync(initial_hab_sync(), bad,
                              hab_rpm=1, hab_phase_rad=0,
                              powered=True, hardware_ok=True)
        damaged = initial_hab_sync()
        damaged["captured"] = True
        with self.assertRaises(HabSyncError):
            validate_hab_sync(damaged)

if __name__ == "__main__":
    unittest.main()
