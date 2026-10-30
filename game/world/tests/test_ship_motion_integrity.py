"""F6-2: persisted rotor booleans and drive flags are authoritative hardware truth."""
import copy
import unittest

from world.ship_motion_machinery import (
    RotorError, initial_rotors, validate_rotors,
    validate_motion_safety, set_rotor_command, step_rotors,
)


class MotionIntegrityRegressions(unittest.TestCase):
    def test_valid_transitions_and_post_step_workshop_state(self):
        park = initial_rotors()
        self.assertTrue(validate_rotors(park))
        spinning = set_rotor_command(park, "DR-01", "start")
        stepped = step_rotors(spinning, 10, powered=True)
        self.assertTrue(validate_rotors(stepped))
        self.assertGreater(stepped["DR-01"]["rpm"], 0)
        self.assertTrue(validate_rotors(set_rotor_command(park, "HAB", "passenger_extend:A")))
        self.assertTrue(validate_rotors(
            step_rotors(set_rotor_command(park, "WR-01", "radius:24"), 10,
                        powered=True)))

    def test_unknown_interlocks_are_never_treated_as_disengaged(self):
        for field in ("hardlock", "brake", "indexing",
                      "freight_collar", "passenger_indexer"):
            for bad in (None, 0, 1, "false"):
                with self.subTest(field=field, value=bad):
                    broken = copy.deepcopy(initial_rotors())
                    broken["DR-01"][field] = bad
                    with self.assertRaises(RotorError):
                        validate_rotors(broken)
                    with self.assertRaises(RotorError):
                        set_rotor_command(broken, "DR-01", "start")
                    with self.assertRaises(RotorError):
                        step_rotors(broken, 10, powered=True)

    def test_missing_extra_numeric_and_inconsistent_states_rejected(self):
        for field, bad in (("rpm", float("nan")),
                           ("phase_rad", float("inf")),
                           ("rpm", 1e30),
                           ("condition", "pretend_ok"),
                           ("mode", "NOT_A_MODE")):
            with self.subTest(field=field):
                broken = copy.deepcopy(initial_rotors())
                broken["DR-01"][field] = bad
                with self.assertRaises(RotorError):
                    validate_rotors(broken)
        broken = copy.deepcopy(initial_rotors())
        broken["DR-01"]["freight_collar"] = True
        broken["DR-01"]["hardlock"] = False
        with self.assertRaises(RotorError):
            validate_rotors(broken)
        broken = copy.deepcopy(initial_rotors())
        broken["DR-01"]["fuzz_extra_field"] = True
        with self.assertRaises(RotorError):
            validate_rotors(broken)
        del broken["DR-01"]["fuzz_extra_field"]
        del broken["DR-01"]["hardlock"]
        with self.assertRaises(RotorError):
            validate_rotors(broken)

    def test_drive_unknown_values_rejected(self):
        safe = dict(drive_condition="inhibited", rcs_condition="operational",
                    drive_firing=False, attitude_firing=False, command="coast",
                    attitude_command="hold")
        self.assertTrue(validate_motion_safety(safe))
        for field, bad in (("drive_condition", "made_up"),
                           ("drive_condition", None),
                           ("rcs_condition", None),
                           ("drive_firing", 0),
                           ("attitude_firing", "false"),
                           ("command", "faster")):
            with self.subTest(field=field):
                broken = dict(safe, **{field: bad})
                with self.assertRaises(RotorError):
                    validate_motion_safety(broken)


if __name__ == "__main__":
    unittest.main()
