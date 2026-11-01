"""Installed Evennia proof of genuinely propellant-consuming attitude torque."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.ship_world import ensure_canonical_ship, find_ship_space
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition,
)
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, crew_physical_action,
    tick_continuous_physics, local_physics_readout, _clock,
)
from world.models import WorkReceipt, CanonicalShipEvent


class InstalledRCSTorqueProof(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        crew = build_ship()
        self.engineer, self.helm = crew["watch"], crew["officer"]
        self.assertTrue(self.engineer.move_to(
            find_ship_space("PROP-CTRL"),quiet=True))
        self.assertTrue(self.helm.move_to(
            find_ship_space("CMD-PRIMARY"),quiet=True))
        self.serial = 1

    def action(self, actor, category, target, value, request=None):
        self.serial += 1
        return crew_physical_action(
            actor, request or f"{self.serial:032x}",
            category, target, value)

    def test_original_thruster_output_measured_before_and_after_real_burn(self):
        initial = _clock().details["motion"]
        self.assertEqual(initial["attitude_command"], "hold")
        before_rate = list(initial["angular_velocity_rad_s"])
        start = self.action(self.engineer, "drive", "RCS", "prove_start")
        self.assertEqual(start, self.action(
            self.engineer, "drive", "RCS", "prove_start",
            request=start["request_id"]))
        self.action(self.helm, "attitude", "HELM", "yaw+")
        tick_continuous_physics(now_game_time=1010)
        during = _clock().details["motion"]
        self.assertTrue(during["attitude_firing"])
        self.assertGreater(during["expended_propellant_kg"],
                           initial["expended_propellant_kg"])
        self.assertGreater(during["angular_velocity_rad_s"][1],
                           before_rate[1])
        with self.assertRaises(PhysicsError):
            self.action(self.engineer, "drive", "RCS", "prove_verify")
        self.action(self.helm, "attitude", "HELM", "hold")
        tick_continuous_physics(now_game_time=1020)
        finished = self.action(
            self.engineer, "drive", "RCS", "prove_verify")
        self.assertEqual(finished["status"], "succeeded")
        witness = local_physics_readout(
            self.engineer,"rcs_proof")["witness"]
        self.assertEqual(witness["completed"],1)
        self.assertGreater(witness["last_verified"]["spent_kg"],0)
        self.assertGreater(
            witness["last_verified"]["delta_omega_rad_s"],0)
        self.assertEqual(WorkReceipt.objects.filter(
            operation="drive",arguments__value="prove_verify",
            arguments__target="RCS").count(),1)
        event = CanonicalShipEvent.objects.filter(
            operation="crew_drive").order_by("-sequence").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.after["rcs_proof"]["completed"],1)
        self.assertIsNone(event.after["rcs_proof"]["pending"])
        with self.assertRaises(PhysicsError):
            self.action(self.engineer,"drive","RCS","prove_verify")

    def test_inhibited_or_damaged_original_rcs_cannot_be_signed_off(self):
        self.action(self.engineer,"drive","RCS","inhibit")
        with self.assertRaises(PhysicsError):
            self.action(self.engineer,"drive","RCS","prove_start")
        self.action(self.engineer,"drive","RCS","release")
        witness=self.action(self.engineer,"drive","RCS","prove_start")
        self.assertEqual(witness["status"],"succeeded")
        set_component_condition(
            "equipment","LCS-PROP","failed",operator=True)
        with self.assertRaises(PhysicsError):
            self.action(self.engineer,"drive","RCS","prove_verify")
        self.assertIsNotNone(_clock().details["rcs_proof"]["pending"])


if __name__ == "__main__":
    import unittest
    unittest.main()
