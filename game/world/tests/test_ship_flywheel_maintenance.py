"""Measured-zero mechanical isolation, all 64 module lockout invariants."""
import unittest

from world.ship_flywheel_maintenance import (
    FlywheelServiceError, initial_flywheel_service,
    validate_flywheel_service, issue_permit, release_permit,
    permit_live, module_dead, module_room, module_breaker,
    bus_safe, service_pulse,
    begin_rundown, advance_rundowns, halt_rundown,
    migrate_flywheel_service_v1,
)
from world.ship_electrical_power import FLYWHEELS


def power(module, charge=0.0, mode="standby"):
    return {"flywheels": {module: {"charge_kwh": charge, "mode": mode}}}


def switches(module, setting="open", condition="serviceable"):
    return {module_breaker(module): {
        "setting": setting, "condition": condition,
    }}


class FlywheelMaintenanceTests(unittest.TestCase):
    def test_all_64_real_modules_have_own_bays_and_breakers(self):
        self.assertEqual(len(FLYWHEELS), 64)
        for m in FLYWHEELS:
            self.assertIn(module_room(m), {"F1-BAY", "F2-BAY"})
            self.assertEqual(module_breaker(m), "ISO-PWR-" + m)

    def test_stored_energy_can_never_be_hidden_by_open_switch(self):
        name = "F1-FW-01"
        for energy, mode, breaker in [
                (0.0001, "standby", "open"),
                (3906.25, "standby", "open"),
                (1, "discharge", "open"),
                (0, "charge", "open"),
                (0, "standby", "closed")]:
            with self.subTest(energy=energy, mode=mode, breaker=breaker):
                self.assertFalse(module_dead(
                    name, power(name, energy, mode),
                    switches(name, breaker)))
                with self.assertRaises(FlywheelServiceError):
                    issue_permit(initial_flywheel_service(), module=name,
                                 worker="#1", game_time=123,
                                 electrical=power(name, energy, mode),
                                 switches=switches(name, breaker))
        self.assertFalse(module_dead(
            name, power(name, 0), switches(name, condition="failed")))
        self.assertFalse(module_dead(name, {"flywheels": {}}, switches(name)))

    def test_permit_owned_and_nonresetting_even_when_work_pauses(self):
        name = "F2-FW-32"
        ledger = initial_flywheel_service()
        issued = issue_permit(ledger, module=name, worker="#33",
                              game_time=1000.0, electrical=power(name),
                              switches=switches(name))
        self.assertEqual(ledger["permits"], {})
        self.assertTrue(permit_live(issued, name, power(name), switches(name)))
        self.assertFalse(permit_live(
            issued, name, power(name, 1), switches(name)))
        self.assertTrue(validate_flywheel_service(issued))
        with self.assertRaises(FlywheelServiceError):
            issue_permit(issued, module=name, worker="#32",
                         game_time=1001, electrical=power(name),
                         switches=switches(name))
        with self.assertRaises(FlywheelServiceError):
            release_permit(issued, module=name, worker="#32")
        with self.assertRaises(FlywheelServiceError):
            release_permit(issued, module=name, worker="#33",
                           repair_active=True)
        released = release_permit(issued, module=name, worker="#33")
        self.assertEqual((released["issued"], released["released"]), (1, 1))
        self.assertFalse(released["permits"])

    def test_bank_bus_requires_all_hard_isolators_off(self):
        switches_f1 = {**{
            f"ISO-F1-BUS-IN-{n}": {
                "setting": "open", "condition": "serviceable"} for n in (1, 2)},
            **{module_breaker(m): {"setting": "open", "condition": "serviceable"}
               for m in FLYWHEELS if m.startswith("F1-")},
        }
        self.assertTrue(bus_safe("F1", switches_f1))
        switches_f1["ISO-PWR-F1-FW-24"]["setting"] = "closed"
        self.assertFalse(bus_safe("F1", switches_f1))
        switches_f1["ISO-PWR-F1-FW-24"]["setting"] = "open"
        switches_f1["ISO-F1-BUS-IN-2"]["condition"] = "failed"
        self.assertFalse(bus_safe("F1", switches_f1))
        self.assertFalse(bus_safe("F3", switches_f1))

    def test_attended_rundown_reconciles_delivered_energy_not_a_magic_spin_reset(self):
        name = "F1-FW-03"
        original = initial_flywheel_service()
        started = begin_rundown(
            original, module=name, worker="#9",
            charge_kwh=10, game_time=1000.0)
        self.assertEqual(original["rundowns"], {})
        self.assertEqual(started["rundowns"][name]["starting_kwh"], 10)
        with self.assertRaises(FlywheelServiceError):
            issue_permit(started, module=name, worker="#9",
                         game_time=1001, electrical=power(name),
                         switches=switches(name))
        after_idle, finished, delta = advance_rundowns(
            started,
            before_electrical={"flywheels": {name: {"charge_kwh": 10}},
                               "meter": {"flywheel_discharge_kwh": 0}},
            after_electrical={"flywheels": {name: {"charge_kwh": 10}},
                              "meter": {"flywheel_discharge_kwh": 0}})
        self.assertEqual(finished, ())
        self.assertEqual(delta, 0)
        self.assertEqual(after_idle, started)
        after_delivery, done, delta = advance_rundowns(
            after_idle,
            before_electrical={"flywheels": {name: {"charge_kwh": 10}},
                               "meter": {"flywheel_discharge_kwh": 0}},
            after_electrical={"flywheels": {name: {"charge_kwh": 6.5}},
                              "meter": {"flywheel_discharge_kwh": 3.5}})
        self.assertEqual(done, ())
        self.assertAlmostEqual(delta, 3.5)
        self.assertEqual(after_delivery["rundowns"][name]["remaining_kwh"], 6.5)
        finished_ledger, done, delta = advance_rundowns(
            after_delivery,
            before_electrical={"flywheels": {name: {"charge_kwh": 6.5}},
                               "meter": {"flywheel_discharge_kwh": 3.5}},
            after_electrical={"flywheels": {name: {"charge_kwh": 0.0}},
                              "meter": {"flywheel_discharge_kwh": 10.0}})
        self.assertEqual(done, (name,))
        self.assertEqual(delta, 6.5)
        self.assertEqual(finished_ledger["rundown_finished"], 1)
        self.assertEqual(finished_ledger["rundowns"], {})
        self.assertEqual(finished_ledger["rundown_delivered_kwh"], 10)

    def test_rundown_halt_leaves_measured_rotor_energy_outside_work_ledger(self):
        module = "F2-FW-12"
        started = begin_rundown(
            initial_flywheel_service(), module=module, worker="#1",
            charge_kwh=150, game_time=200)
        with self.assertRaises(FlywheelServiceError):
            halt_rundown(started, module=module, worker="#2")
        halted = halt_rundown(started, module=module, worker="#1")
        self.assertEqual(halted["rundown_halted"], 1)
        self.assertFalse(halted["rundowns"])
        self.assertEqual(halted["rundown_delivered_kwh"], 0)
        self.assertEqual(halted["rundown_started"], 1)

    def test_no_unmetered_energy_disappearance_or_rundown_recharge(self):
        module = "F1-FW-16"
        started = begin_rundown(
            initial_flywheel_service(), module=module, worker="#7",
            charge_kwh=5, game_time=120)
        before = {"flywheels": {module: {"charge_kwh": 5.0}},
                  "meter": {"flywheel_discharge_kwh": 9.0}}
        for after in (
                {"flywheels": {module: {"charge_kwh": 4.0}},
                 "meter": {"flywheel_discharge_kwh": 9.0}},
                {"flywheels": {module: {"charge_kwh": 6.0}},
                 "meter": {"flywheel_discharge_kwh": 9.0}},
                {"flywheels": {module: {"charge_kwh": float("nan")}},
                 "meter": {"flywheel_discharge_kwh": 9.0}}):
            with self.assertRaises(FlywheelServiceError):
                advance_rundowns(
                    started, before_electrical=before,
                    after_electrical=after)

    def test_nonresetting_migration_recovers_preexisting_padlocks(self):
        old = initial_flywheel_service()
        for name in ("rundowns", "rundown_started", "rundown_finished",
                     "rundown_halted", "rundown_delivered_kwh"):
            del old[name]
        old["permits"]["F1-FW-01"] = {
            "worker": "#2", "room": "F1-BAY",
            "breaker": "ISO-PWR-F1-FW-01",
            "issued_game_time": 10.0, "initial_charge_kwh": 0}
        old["issued"] = 1
        newer = migrate_flywheel_service_v1(old)
        self.assertEqual(newer["permits"], old["permits"])
        self.assertEqual(newer["issued"], 1)
        self.assertEqual(newer["rundowns"], {})
        self.assertEqual(migrate_flywheel_service_v1(newer), newer)


    def test_corrupted_custody_and_nonfinite_charge_fail(self):
        name = "F1-FW-02"
        for charge in (float("nan"), float("inf"), -1, True):
            self.assertFalse(module_dead(
                name, power(name, charge), switches(name)))
        original = issue_permit(initial_flywheel_service(),
                                module=name, worker="#1", game_time=1.0,
                                electrical=power(name), switches=switches(name))
        damaged = dict(original)
        damaged["issued"] = 3
        with self.assertRaises(FlywheelServiceError):
            validate_flywheel_service(damaged)
        damaged = issue_permit(initial_flywheel_service(),
                              module=name, worker="#1", game_time=1.0,
                              electrical=power(name), switches=switches(name))
        damaged["permits"][name]["room"] = "HAB-04-MED-TREAT"
        with self.assertRaises(FlywheelServiceError):
            validate_flywheel_service(damaged)

    def test_interruption_count_is_bounded_and_does_not_refill_energy(self):
        name = "F1-FW-01"
        issued = issue_permit(initial_flywheel_service(),
                              module=name, worker="#9", game_time=1,
                              electrical=power(name), switches=switches(name))
        pulsed = service_pulse(issued, interrupted=1, recovered=0)
        self.assertEqual(pulsed["interrupted_ticks"], 1)
        self.assertEqual(pulsed["permits"][name], issued["permits"][name])
        with self.assertRaises(FlywheelServiceError):
            service_pulse(issued, interrupted=2, recovered=0)


if __name__ == "__main__":
    unittest.main()
