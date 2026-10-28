"""Actual installed main-drive output proof: real helm burn and finite fuel."""
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.ship_world import build_canonical_ship, find_ship_space
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition, state,
)
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, crew_physical_action,
    tick_continuous_physics, local_physics_readout, _clock,
    commission_g19_water, commission_g19_repairs,
)
from world.models import WorkReceipt


class RealDriveOutputWitness(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        crew = build_ship()
        self.engineer, self.helm = crew["watch"], crew["officer"]
        self.engineer.move_to(find_ship_space("PROP-CTRL"), quiet=True)
        self.helm.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        self.serial = 1

    def action(self, actor, action, target, value, request=None):
        self.serial += 1
        return crew_physical_action(
            actor, request or f"{self.serial:032x}",
            action, target, value)

    def test_real_propellant_and_inertial_delta_v_prove_drive(self):
        before = _clock().details["motion"]
        self.assertEqual(before["command"], "coast")
        start = self.action(
            self.engineer, "drive", "MAIN", "prove_start")
        self.assertEqual(start, self.action(
            self.engineer, "drive", "MAIN", "prove_start",
            request=start["request_id"]))
        self.assertEqual(_clock().details["drive_proof"]["completed"], 0)
        self.action(self.helm, "helm", "HELM", "x+")
        result = tick_continuous_physics(now_game_time=1010)
        self.assertTrue(result["advanced"])
        during = _clock().details["motion"]
        self.assertTrue(during["drive_firing"])
        self.assertGreater(during["expended_propellant_kg"],
                           before["expended_propellant_kg"])
        self.assertGreater(during["velocity_m_s"][0],
                           before["velocity_m_s"][0])
        self.action(self.helm, "helm", "HELM", "coast")
        tick_continuous_physics(now_game_time=1020)
        after = self.action(
            self.engineer, "drive", "MAIN", "prove_verify")
        self.assertEqual(after["status"], "succeeded")
        witness = local_physics_readout(
            self.engineer, "drive_proof")["witness"]
        self.assertEqual(witness["completed"], 1)
        self.assertGreater(witness["last_verified"]["propellant_kg"], 0)
        self.assertGreater(witness["last_verified"]["delta_v_m_s"], 0)
        self.assertEqual(WorkReceipt.objects.filter(
            operation="drive", arguments__value="prove_verify").count(), 1)
        with self.assertRaises(PhysicsError):
            self.action(self.engineer, "drive", "MAIN", "prove_verify")

    def test_propulsion_service_bay_is_not_a_remote_repair_shortcut(self):
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        set_component_condition("equipment", "LCS-PROP", "failed", operator=True)
        self.assertEqual(state("equipment", "LCS-PROP").space_id, "PROP-SVC")
        # The control station is a different real pressure cell. An
        # engineer standing here cannot perform hands-on work at the
        # atmosphere-unsurveyed original propulsion service room.
        with self.assertRaises(PermissionError):
            self.action(self.engineer, "repair", "equipment:LCS-PROP", "start")
        with self.assertRaises(PermissionError):
            local_physics_readout(self.helm, "drive_proof")

    def test_idle_drive_and_damaged_controller_cannot_verify_output(self):
        self.action(self.engineer, "drive", "MAIN", "prove_start")
        tick_continuous_physics(now_game_time=1010)
        with self.assertRaises(PhysicsError):
            self.action(self.engineer, "drive", "MAIN", "prove_verify")
        self.action(self.helm, "helm", "HELM", "x+")
        tick_continuous_physics(now_game_time=1020)
        self.action(self.helm, "helm", "HELM", "coast")
        tick_continuous_physics(now_game_time=1030)
        set_component_condition(
            "equipment", "LCS-PROP", "failed", operator=True)
        with self.assertRaises(PhysicsError):
            self.action(self.engineer, "drive", "MAIN", "prove_verify")
        self.assertIsNotNone(_clock().details["drive_proof"]["pending"])


if __name__ == "__main__":
    import unittest
    unittest.main()
