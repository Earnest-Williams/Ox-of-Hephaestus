"""G19 finite evidence, alarm-history and failure isolation pure regressions."""
import copy
import unittest

from world.ship_instrumentation import (
    InstrumentError, alarm_key, initial_instrumentation, validate_instrumentation,
    sample_instrumentation, acknowledge_alarm, diagnostics, panel_readout,
    MAX_HISTORY,
)
from world.ship_instrumentation_world import (
    observed_panel_evidence, local_relay_summary, original_panel_roster,
)


class InstrumentationTests(unittest.TestCase):
    def setUp(self):
        self.a = "LP-TEST-A"
        self.b = "LP-TEST-B"
        self.ledger = initial_instrumentation(
            {self.a: "TEST-A-ROOM", self.b: "TEST-B-ROOM"},
            {self.a: "PZ-TEST-A", self.b: "PZ-TEST-B"},
            start_s=1000)

    def status(self, *, a="online", b="online", faults_a=(),
               pressure_a=101.0, burn_a=0.0, smoke_a=0.0):
        return {
            self.a: {"status": a, "metrics": (
                {"pressure_kpa": pressure_a, "oxygen_kpa": 21.0,
                 "temperature_k": 293.15, "burn_kg_s": burn_a,
                 "smoke_fraction": smoke_a}
                if a == "online" else {}),
                "faults": list(faults_a) if a == "online" else []},
            self.b: {"status": b, "metrics": (
                {"pressure_kpa": 101.0, "oxygen_kpa": 21.0,
                 "temperature_k": 293.15}
                if b == "online" else {}),
                "faults": []},
        }

    def tick(self, previous, when, **changes):
        return sample_instrumentation(previous, when, self.status(**changes))

    def test_first_observation_preserves_each_panel_and_does_not_oracle(self):
        first = self.tick(self.ledger, 1010)
        self.assertEqual(first["sample_count"], 1)
        self.assertEqual(first["panels"][self.a]["last_good_s"], 1010)
        self.assertFalse(any(a["active"] for a in first["alarms"].values()))
        self.assertTrue(validate_instrumentation(first))
        self.assertEqual(first["panels"][self.a]["metrics"]["pressure_kpa"], 101)

    def test_real_pressure_and_fire_record_separate_latched_alarm_edges(self):
        first = self.tick(self.ledger, 1010, pressure_a=52,
                          burn_a=.05, smoke_a=.001)
        self.assertEqual(
            {a["code"] for a in first["alarms"].values() if a["active"]},
            {"PRESSURE_LOW", "FIRE", "SMOKE"})
        repeat = self.tick(first, 1020, pressure_a=52,
                           burn_a=.05, smoke_a=.001)
        self.assertEqual(len(repeat["history"]), 3)
        self.assertEqual({a["occurrences"] for a in repeat["alarms"].values()}, {1})

    def test_acknowledge_is_not_repair_and_has_human_evidence(self):
        first = self.tick(self.ledger, 1010, pressure_a=52)
        key = alarm_key(self.a, "PRESSURE_LOW", "PZ-TEST-A")
        ack = acknowledge_alarm(first, self.a, key, actor="#57", now_s=1010)
        self.assertTrue(ack["alarms"][key]["active"])
        self.assertEqual(ack["alarms"][key]["ack_by"], "#57")
        self.assertEqual(len(ack["history"]), 2)
        self.assertIsNone(first["alarms"][key]["ack_by"])
        with self.assertRaises(InstrumentError):
            acknowledge_alarm(ack, self.a, key, actor="#57", now_s=1010)
        with self.assertRaises(InstrumentError):
            acknowledge_alarm(first, self.b, key, actor="#57", now_s=1010)

    def test_two_valid_samples_for_actual_fault_clear(self):
        fault = self.tick(self.ledger, 1010, pressure_a=35)
        one = self.tick(fault, 1020)
        key = alarm_key(self.a, "PRESSURE_LOW", "PZ-TEST-A")
        self.assertTrue(one["alarms"][key]["active"])
        two = self.tick(one, 1030)
        self.assertFalse(two["alarms"][key]["active"])
        self.assertEqual(
            [e["transition"] for e in two["history"]],
            ["raised", "resolved"])
        recurring = self.tick(two, 1040, pressure_a=35)
        self.assertTrue(recurring["alarms"][key]["active"])
        self.assertEqual(recurring["alarms"][key]["occurrences"], 2)
        self.assertEqual(recurring["history"][-1]["transition"], "reasserted")

    def test_dark_panel_keeps_last_known_hazard_and_reports_no_live_metrics(self):
        fault = self.tick(self.ledger, 1010, pressure_a=45)
        dark = self.tick(fault, 1020, a="dark")
        key = alarm_key(self.a, "PRESSURE_LOW", "PZ-TEST-A")
        self.assertTrue(dark["alarms"][key]["active"])
        self.assertTrue(dark["alarms"][
            alarm_key(self.a, "INSTRUMENT_LOST", self.a)]["active"])
        self.assertEqual(dark["panels"][self.a]["last_good_s"], 1010)
        reading = panel_readout(dark, self.a, now_s=1040)
        self.assertIsNone(reading["measurements"])
        self.assertEqual(reading["age_s"], 30)
        with self.assertRaises(InstrumentError):
            acknowledge_alarm(
                dark, self.a, key, actor="#57", now_s=1020)

    def test_broken_sensor_never_issues_healthy_measurement(self):
        with self.assertRaises(InstrumentError):
            self.tick(self.ledger, 1010, a="damaged", faults_a=(
                ("MACHINE_FAULT", "WATER-PROC-A"),))
        readings = self.status(a="dark")
        readings[self.a]["metrics"]["pressure_kpa"] = 101
        with self.assertRaises(InstrumentError):
            sample_instrumentation(self.ledger, 1010, readings)

    def test_faulted_machinery_and_breaker_report_provenance(self):
        first = self.tick(
            self.ledger, 1010, faults_a=(
                ("MACHINE_FAULT", "GEN-M"),
                ("BREAKER_TRIP", "ISO-GEN-M"),
                ("SERVICE_OUTAGE", "SHOP-CNC-MILL")))
        self.assertEqual(len(first["alarms"]), 3)
        for name in first["alarms"]:
            self.assertTrue(name.startswith(self.a + "|"))
        guided = diagnostics(
            first, alarm_key(self.a, "BREAKER_TRIP", "ISO-GEN-M"),
            panel_id=self.a)
        self.assertEqual(guided["family"], "electrical")
        self.assertTrue(guided["does_not_isolate_or_repair"])
        self.assertIn("reset", guided["next_physical_checks"])

    def test_fault_does_not_leak_into_other_room(self):
        first = self.tick(self.ledger, 1010, pressure_a=40)
        b = panel_readout(first, self.b, now_s=1010)
        self.assertEqual(b["active_alarms"], {})
        with self.assertRaises(InstrumentError):
            diagnostics(first, alarm_key(self.a, "PRESSURE_LOW", "PZ-TEST-A"),
                        panel_id=self.b)

    def test_invalid_samples_duplicate_time_and_unknown_panel_rejected(self):
        with self.assertRaises(InstrumentError):
            self.tick(self.ledger, 1000)
        with self.assertRaises(InstrumentError):
            self.tick(self.ledger, 1061)
        wrong = self.status()
        del wrong[self.b]
        with self.assertRaises(InstrumentError):
            sample_instrumentation(self.ledger, 1010, wrong)
        wrong = self.status(faults_a=(("NOT_A_SENSOR", "FAKE"),))
        with self.assertRaises(InstrumentError):
            sample_instrumentation(self.ledger, 1010, wrong)
        with self.assertRaises(InstrumentError):
            alarm_key("FAKE<PANEL", "FIRE", "PZ-TEST-A")

    def test_tampering_with_panel_or_history_fails_explicitly(self):
        first = self.tick(self.ledger, 1010, pressure_a=40)
        forgery = copy.deepcopy(first)
        forgery["panels"][self.a]["last_good_s"] = 9000
        with self.assertRaises(InstrumentError):
            validate_instrumentation(forgery)
        forgery = copy.deepcopy(first)
        forgery["alarms"][
            alarm_key(self.a, "PRESSURE_LOW", "PZ-TEST-A")]["panel"] = self.b
        with self.assertRaises(InstrumentError):
            validate_instrumentation(forgery)

    def test_bounded_history_without_dropping_active_alarm(self):
        current = self.tick(self.ledger, 1010, pressure_a=40)
        for n in range(1020, 1020 + (MAX_HISTORY + 20) * 10, 10):
            # maintain exactly one active fault without writing events
            current = self.tick(current, n, pressure_a=40)
        self.assertEqual(len(current["history"]), 1)
        self.assertTrue(current["alarms"][
            alarm_key(self.a, "PRESSURE_LOW", "PZ-TEST-A")]["active"])

    def test_malformed_panel_roster_is_not_invented(self):
        with self.assertRaises(InstrumentError):
            initial_instrumentation(
                {"FAKE-CONTROL": "MOON-ROOM"},
                {"FAKE-CONTROL": "PZ-FAKE"}, start_s=1000)
        with self.assertRaises(InstrumentError):
            validate_instrumentation(
                self.ledger, panel_rooms={self.a: "OTHER-ROOM"})
