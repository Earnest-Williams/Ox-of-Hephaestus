"""Physical-repair provenance and restart interlock regressions."""
import unittest
from types import SimpleNamespace
from world.ship_fault_recovery import (
    FaultRecoveryError, initial_fault_cases, validate_fault_cases,
    feeders_for, verified_open_feeders, verified_restored_feeders,
    inspect_fault, isolate_fault, begin_verified_work,
    finished_verified_work, check_repair, authorize_restart, verify_restart,
    advance_restart_evidence,
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
                    alarm_active=False, panel_live=True, signal_quality_clear=True)
        fresh_1 = advance_restart_evidence(
            allowed, now_s=413, observed_good={self.name: True})
        fresh_2 = advance_restart_evidence(
            fresh_1, now_s=420, observed_good={self.name: True})
        with self.assertRaises(FaultRecoveryError):
            verify_restart(
                fresh_2, self.name, actor="#12", now_s=424,
                sample_count=23, running=True, live_feeder=True,
                condition="serviceable", tripped=False,
                alarm_active=False, panel_live=True,
                signal_quality_clear=False)
        verified = verify_restart(
            fresh_2, self.name, actor="#12", now_s=424,
            sample_count=23, running=True, live_feeder=True,
            condition="serviceable", tripped=False,
            alarm_active=False, panel_live=True, signal_quality_clear=True)
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

    def test_all_real_feeders_require_correct_network_location_and_open_breaker(self):
        from world.ship_auxiliary_electrical import MOTORS
        from world.ship_equipment_services import SERVICE_LOADS
        identities = set(MOTORS) | set(SERVICE_LOADS)
        self.assertEqual(len(identities), 98)
        for machine in sorted(identities):
            room = (SERVICE_LOADS[machine] if machine in SERVICE_LOADS
                    else MOTORS[machine])[0]
            rows = {}
            for feeder in feeders_for(machine):
                network = ("g19_equipment_service" if machine in SERVICE_LOADS
                           else "g19_motor_protected"
                           if feeder.startswith("ISO-G19-PROT-") else "g19_motor")
                rows[feeder] = SimpleNamespace(
                    category="isolator", source_id=feeder, space_id=room,
                    condition="serviceable", setting="open",
                    reference={"kind": "breaker", "network": network,
                               "manual_operation": True})
            self.assertTrue(verified_open_feeders(machine, rows), machine)
            for wrong in ("closed", "damaged"):
                feeder = next(iter(rows))
                original = rows[feeder]
                if wrong == "closed":
                    rows[feeder] = SimpleNamespace(**{**vars(original), "setting": wrong})
                else:
                    rows[feeder] = SimpleNamespace(**{**vars(original), "condition": wrong})
                self.assertFalse(verified_open_feeders(machine, rows), (machine,wrong))
                rows[feeder] = original
            missing = dict(rows)
            missing.pop(next(iter(rows)))
            self.assertFalse(verified_open_feeders(machine, missing))
            feeder = next(iter(rows))
            tampered = dict(rows)
            tampered[feeder] = SimpleNamespace(
                **{**vars(rows[feeder]), "space_id": "SOMEONE-ELSES-ROOM"})
            self.assertFalse(verified_open_feeders(machine, tampered))

    def test_blackout_or_failed_output_resets_two_good_samples(self):
        isolated = isolate_fault(self.first, self.name,
            actor="#12", now_s=105, open_feeders=True,
            stopped=True, worksite_safe=True)
        work = begin_verified_work(isolated, self.name, isolated=True)
        done = finished_verified_work(work, self.name,
                                      stamp=400, installed_kg=3)
        checked = check_repair(
            done, self.name, actor="#12", now_s=401,
            condition="serviceable", open_feeders=True, stopped=True,
            tripped=False, active_work=False, repair_stamp=400,
            cumulative_spares_kg=3)
        authorized = authorize_restart(
            checked, self.name, actor="#12", now_s=402, sample_count=50,
            sound_hardware=True, live_feeder=True, tripped=False,
            active_work=False)
        one = advance_restart_evidence(
            authorized, now_s=412, observed_good={self.name: True})
        self.assertEqual(one["cases"][self.name]["restart_consecutive_good"], 1)
        with self.assertRaises(FaultRecoveryError):
            advance_restart_evidence(one, now_s=412,
                                     observed_good={self.name: True})
        dark = advance_restart_evidence(
            one, now_s=422, observed_good={self.name: False})
        self.assertEqual(dark["cases"][self.name]["restart_consecutive_good"], 0)
        first_after = advance_restart_evidence(
            dark, now_s=432, observed_good={self.name: True})
        with self.assertRaises(FaultRecoveryError):
            verify_restart(first_after, self.name, actor="#12",
                now_s=432, sample_count=54, running=True,
                live_feeder=True, condition="serviceable", tripped=False,
                alarm_active=False, panel_live=True, signal_quality_clear=True)
        second_after = advance_restart_evidence(
            first_after, now_s=442, observed_good={self.name: True})
        self.assertEqual(second_after["cases"][self.name]["restart_consecutive_good"], 2)
        accepted = verify_restart(second_after, self.name, actor="#12",
            now_s=442, sample_count=55, running=True,
            live_feeder=True, condition="serviceable", tripped=False,
            alarm_active=False, panel_live=True, signal_quality_clear=True)
        self.assertEqual(accepted["cases"][self.name]["stage"], "verified")
        self.assertEqual(accepted["verified"], 1)

    def test_restored_all_98_feeds_need_real_manual_close_and_later_measurement(self):
        from world.ship_auxiliary_electrical import MOTORS
        from world.ship_equipment_services import SERVICE_LOADS
        for name in sorted(set(MOTORS) | set(SERVICE_LOADS)):
            room = (SERVICE_LOADS[name] if name in SERVICE_LOADS
                    else MOTORS[name])[0]
            feeders = {}
            for key in feeders_for(name):
                network = ("g19_equipment_service" if name in SERVICE_LOADS
                           else "g19_motor_protected"
                           if key.startswith("ISO-G19-PROT-") else "g19_motor")
                feeders[key] = SimpleNamespace(
                    source_id=key, category="isolator", space_id=room,
                    setting="closed", condition="serviceable",
                    reference={"network": network, "kind": "breaker",
                               "manual_operation": True},
                    details={"physics_manual_close_game_s": 205.0})
            self.assertTrue(verified_restored_feeders(
                name, feeders, checked_s=205, last_good_s=215), name)
            self.assertFalse(verified_restored_feeders(
                name, feeders, checked_s=205, last_good_s=205), name)
            self.assertFalse(verified_restored_feeders(
                name, feeders, checked_s=206, last_good_s=215), name)
            altered = dict(feeders)
            first = next(iter(altered))
            altered[first] = SimpleNamespace(
                **{**vars(feeders[first]), "details": {}})
            self.assertFalse(verified_restored_feeders(
                name, altered, checked_s=205, last_good_s=215), name)
            if len(feeders) > 1:
                partial = dict(feeders)
                partial.pop(first)
                self.assertFalse(verified_restored_feeders(
                    name, partial, checked_s=205, last_good_s=215), name)

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
