"""Original aft engine plume EVA permission and residual heat invariants."""
import unittest
from world.ship_propulsion_exterior import (
    FACE, BASE, LINK, STATION, GATE_S, PlumeAccessError,
    initial_propulsion_exterior, validate_propulsion_exterior,
    survey_propulsion_exterior, propulsion_face_safe,
    issue_propulsion_permit, inspect_propulsion,
    release_propulsion_permit,
)


def motion():
    return {"command": "coast", "attitude_command": "hold",
            "drive_condition": "inhibited", "rcs_condition": "inhibited",
            "drive_firing": False, "attitude_firing": False, "ftl_leg": None,
            "drive_heat_kj": 100, "angular_velocity_rad_s": [0., 0., 0.],
            "expended_propellant_kg": 123, "expended_ftl_fuel_kg": 9}


def safe(s=None):
    m = motion()
    ledger = survey_propulsion_exterior(
        s or initial_propulsion_exterior(), temperature_k=280.,
        plume_clear=True, motion=m, game_time=100)
    return ledger, m


class AftPropulsionExteriorTests(unittest.TestCase):
    def test_only_original_120_s_placement_and_unsigned_initial_face(self):
        self.assertEqual((FACE, BASE, LINK, STATION, GATE_S),
                         ("EXT-PROP-AFT", "EXT-AFT",
                          "ACC-EXT-AFT-EXT-PROP-AFT", "PROP-CTRL", 120))
        self.assertTrue(validate_propulsion_exterior(initial_propulsion_exterior()))
        self.assertFalse(propulsion_face_safe(
            initial_propulsion_exterior(), motion=motion(), hardware_ready=True))

    def test_hot_or_negative_plume_attestation_fails_closed(self):
        m = motion()
        for temp, plume in ((400, True), (280, False)):
            with self.subTest(temp=temp, plume=plume):
                led = survey_propulsion_exterior(
                    initial_propulsion_exterior(), temperature_k=temp,
                    plume_clear=plume, motion=m, game_time=1)
                self.assertFalse(propulsion_face_safe(
                    led, motion=m, hardware_ready=True))
        with self.assertRaises(PlumeAccessError):
            survey_propulsion_exterior(
                initial_propulsion_exterior(), temperature_k=float("nan"),
                plume_clear=True, motion=m, game_time=1)

    def test_actual_drive_inhibit_rcs_ftl_attitude_and_heat(self):
        led, m = safe()
        self.assertTrue(propulsion_face_safe(led, motion=m, hardware_ready=True))
        for changes in (
                {"drive_condition": "operational"},
                {"rcs_condition": "operational"},
                {"command": "ahead"},
                {"attitude_command": "rotate"},
                {"drive_heat_kj": 4_000_000},
                {"ftl_leg": {"status": "engaged"}},
                {"angular_velocity_rad_s": [0.01, 0, 0]},
                {"drive_firing": True},
                {"attitude_firing": True},
                {"expended_propellant_kg": 124},
                {"expended_ftl_fuel_kg": 10}):
            check = {**m, **changes}
            with self.subTest(changes=changes):
                self.assertFalse(propulsion_face_safe(
                    led, motion=check, hardware_ready=True))
        self.assertFalse(propulsion_face_safe(
            led, motion=m, hardware_ready=False))

    def test_owned_permit_and_survey_cannot_be_forged_mid_occupancy(self):
        led, m = safe()
        grant = issue_propulsion_permit(
            led, actor="#11", motion=m, game_time=105,
            hardware_ready=True)
        self.assertEqual(grant["issued"], 1)
        self.assertTrue(validate_propulsion_exterior(grant))
        self.assertIsNone(led["permit"])
        with self.assertRaises(PlumeAccessError):
            survey_propulsion_exterior(
                grant, temperature_k=270, plume_clear=True,
                motion=m, game_time=110)
        with self.assertRaises(PlumeAccessError):
            inspect_propulsion(grant, actor="#12", motion=m,
                               hardware_ready=True)
        completed = inspect_propulsion(
            grant, actor="#11", motion=m, hardware_ready=True)
        self.assertEqual(completed["inspected"], 1)
        with self.assertRaises(PlumeAccessError):
            release_propulsion_permit(
                completed, actor="#11", occupied=True)
        with self.assertRaises(PlumeAccessError):
            release_propulsion_permit(
                completed, actor="#11", transit_active=True)
        restored = release_propulsion_permit(completed, actor="#11")
        self.assertEqual(restored["released"], 1)
        self.assertIsNone(restored["permit"])

    def test_inconsistent_counters_burn_and_bad_temperature_rejected(self):
        led, m = safe()
        bad = dict(led)
        bad["issued"] = 1
        with self.assertRaises(PlumeAccessError):
            validate_propulsion_exterior(bad)
        for temp in (float("inf"), -1, 801):
            with self.subTest(temp=temp), self.assertRaises(
                    PlumeAccessError):
                survey_propulsion_exterior(
                    led, temperature_k=temp, plume_clear=True,
                    motion=m, game_time=101)


if __name__ == "__main__":
    unittest.main()
