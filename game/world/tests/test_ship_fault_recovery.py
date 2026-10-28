"""Physical-repair provenance and restart interlock regressions."""
import unittest
from world.ship_fault_recovery import (
    FaultRecoveryError, initial_fault_cases, validate_fault_cases,
    feeders_for, inspect_fault, isolate_fault, begin_verified_work,
    finished_verified_work, check_repair, authorize_restart, verify_restart,
)


class FaultRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.name = "SHOP-CNC-MILL"
        self.first = inspect_fault(
            initial_fault_cases(), self.name, room="SHOP-MECH",
            actor="#12", now_s=100, condition="failed", revision=4,
            repair_stamp=None, cumulative_spares_kg=0,
            feeder_tripped=False, restart_latched=False)
        self.assertEqual(feeders_for(self.name), ("ISO-G19-SVC-SHOP-CNC-MILL",))

    def test_physical_sequence_and_two_independent_restart_samples(self):
        with self.assertRaises(FaultRecoveryError):
            isolate_fault(self.first, self.name, actor="#12", now_s=100,
                          open_feeders=False, stopped=True, worksite_safe=True)
        isolated = isolate_fault(self.first, self.name, actor="#12", now_s=100,
                                open_feeders=True, stopped=True, worksite_safe=True)
        doing = begin_verified_work(isolated, self.name, isolated=True)
        done = finished_verified_work(doing, self.name, stamp=401, installed_kg=3)
        with self.assertRaises(FaultRecoveryError):
            check_repair(done, self.name, actor="#12", now_s=402,
                         condition="serviceable", open_feeders=True,
                         stopped=True, tripped=False, active_work=False,
                         repair_stamp=401, cumulative_spares_kg=0)
        inspected = check_repair(
            done, self.name, actor="#12", now_s=402,
            condition="serviceable", open_feeders=True, stopped=True,
            tripped=False, active_work=False, repair_stamp=401,
            cumulative_spares_kg=3)
        with self.assertRaises(FaultRecoveryError):
            authorize_restart(
                inspected, self.name, actor="#12", now_s=402,
                sample_count=21, sound_hardware=True, live_feeder=False,
                tripped=False, active_work=False)
        allowed = authorize_restart(
            inspected, self.name, actor="#12", now_s=403,
            sample_count=21, sound_hardware=True, live_feeder=True,
            tripped=False, active_work=False)
        for count in (21, 22):
            with self.assertRaises(FaultRecoveryError):
                verify_restart(
                    allowed, self.name, actor="#12", now_s=410,
                    sample_count=count, running=True, live_feeder=True,
                    condition="serviceable", tripped=False,
                    alarm_active=False, panel_live=True)
        verified = verify_restart(
            allowed, self.name, actor="#12", now_s=424,
            sample_count=23, running=True, live_feeder=True,
            condition="serviceable", tripped=False,
            alarm_active=False, panel_live=True)
        self.assertEqual(verified["verified"], 1)
        self.assertEqual(verified["cases"][self.name]["stage"], "verified")
        self.assertTrue(validate_fault_cases(verified))
        self.assertEqual(self.first["cases"][self.name]["stage"], "inspected")

    def test_no_fabricated_fault_or_unaudited_machine(self):
        with self.assertRaises(FaultRecoveryError):
            feeders_for("INVISIBLE-MACHINE")
        with self.assertRaises(FaultRecoveryError):
            inspect_fault(initial_fault_cases(), self.name,
                          room="SHOP-MECH", actor="#2", now_s=0,
                          condition="serviceable", revision=1, repair_stamp=None,
                          cumulative_spares_kg=0, feeder_tripped=False,
                          restart_latched=False)
        self.assertEqual(len(feeders_for("FIRE-PUMP-FWD")), 2)

    def test_restart_on_breaker_trip_requires_real_cleared_protection(self):
        name = "FIRE-PUMP-FWD"
        case = inspect_fault(initial_fault_cases(), name, room="WATER-FWD",
                             actor="#4", now_s=1, condition="serviceable",
                             revision=0, repair_stamp=None,
                             cumulative_spares_kg=0,
                             feeder_tripped=True, restart_latched=False)
        lock = isolate_fault(case, name, actor="#4", now_s=2,
                             open_feeders=True, stopped=True, worksite_safe=True)
        checked = check_repair(lock, name, actor="#4", now_s=3,
                               condition="serviceable", open_feeders=True,
                               stopped=True, tripped=False, active_work=False,
                               repair_stamp=None, cumulative_spares_kg=0)
        self.assertEqual(checked["cases"][name]["fault_type"], "protection")
        with self.assertRaises(FaultRecoveryError):
            authorize_restart(checked, name, actor="#4", now_s=4,
                              sample_count=1, sound_hardware=True,
                              live_feeder=True, tripped=True, active_work=False)

    def test_changing_machinery_condition_does_not_forge_completed_work(self):
        isolated = isolate_fault(self.first, self.name, actor="#12", now_s=110,
                                 open_feeders=True, stopped=True, worksite_safe=True)
        with self.assertRaises(FaultRecoveryError):
            check_repair(isolated, self.name, actor="#12", now_s=200,
                         condition="serviceable", open_feeders=True,
                         stopped=True, tripped=False, active_work=False,
                         repair_stamp=None, cumulative_spares_kg=0)
        with self.assertRaises(FaultRecoveryError):
            finished_verified_work(isolated, self.name, stamp=300, installed_kg=3)

    def test_exact_role_and_timestamp_are_validated(self):
        with self.assertRaises(FaultRecoveryError):
            inspect_fault(initial_fault_cases(), self.name, room="SHOP-MECH",
                          actor="fake", now_s=100, condition="failed", revision=0,
                          repair_stamp=None, cumulative_spares_kg=0,
                          feeder_tripped=False, restart_latched=False)
        with self.assertRaises(FaultRecoveryError):
            isolate_fault(self.first, self.name, actor="#1", now_s=99,
                          open_feeders=True, stopped=True, worksite_safe=True)


if __name__ == "__main__":
    unittest.main()
