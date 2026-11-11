"""Physical drum-3 gateway supply, raw vocabulary and read-only recovery."""

from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace

from world.ship_control_gateway import (
    PROFILE,
    SOURCES,
    gateway_power_rows,
    initial_gateway,
    raw_gateway_samples,
    step_gateway,
    survey_gateway_power,
    translate_gateway_samples,
    validate_gateway,
    validate_gateway_sources,
    verify_gateway_protocol,
)
from world.ship_mind_power import MindPowerError, default_design_path, load_design
from world.ship_mind_support import (
    connected_machines,
    load_support,
    proposed_support_rows,
    survey_signature,
)


class GatewayInfrastructureTests(unittest.TestCase):
    """Cables, electricity and understood words remain independent facts."""

    @classmethod
    def setUpClass(cls):
        """Use the actual candidate ship and its fixed local supply panel."""
        cls.ship = json.loads(
            default_design_path().with_name("ox_full_ship_v0.5_candidate.json").read_text()
        )
        cls.support = load_support()
        cls.design = load_design()

    def setUp(self):
        """Fit a dedicated supply and three existing controller registers."""
        self.rows = {
            k: SimpleNamespace(**v, revision=1)
            for k, v in gateway_power_rows(self.support, self.ship).items()
        }
        self.hardware = {
            k: SimpleNamespace(**v, revision=1)
            for k, v in proposed_support_rows(self.support, self.design, self.ship).items()
        }
        self.sources = {
            key: SimpleNamespace(
                key=key,
                revision=1,
                condition="serviceable",
                setting="closed",
                details={"physics_online": False},
            )
            for key in SOURCES
        }
        self.sources["equipment:LCS-DR-03"] = SimpleNamespace(condition="serviceable")
        self.power = {
            "nodes": {"NODE-LP-BE-05-SVC"},
            "essential_assured": True,
            "available_mw": 3,
            "requested_mw": 1,
        }
        self.account = initial_gateway()
        self.operating = set()

    def survey(self):
        """Measure the actual rated 50 W draw, without energy or authority credits."""
        self.account = survey_gateway_power(
            self.account,
            self.rows,
            measured_kw=0.05,
            evidence_id="fused-local-supply-test",
            thermal_path_verified=True,
        )

    def step(self, *, connected=True, now_s=1010):
        """Advance one physical interval against the real sampled registers."""
        self.account, mw = step_gateway(
            self.account,
            rows=self.rows,
            support_rows=self.hardware,
            source_rows=self.sources,
            power=self.power,
            connected=connected,
            seconds=10,
            now_s=now_s,
            heat_sink_available=True,
            operating_machines=self.operating,
        )
        return mw

    def confirmations(self):
        """Independent expected interpretations of the fixture's raw registers."""
        return {
            key: {
                "value": "closed" if key.startswith("isolator:") else False,
                "unit": "position" if key.startswith("isolator:") else "state",
                "meaning": "valve_position" if key.startswith("isolator:") else "running_feedback",
            }
            for key in SOURCES
        }

    def test_gateway_sources_keep_original_identity_location_and_reference(self):
        """A tampered device record cannot acquire a verified telemetry identity."""
        keys = set(SOURCES) | {"equipment:LCS-DR-03", "equipment:LP-BE-05-SVC"}
        rows = {}
        for section, category in (("equipment", "equipment"), ("isolation_points", "isolator")):
            for ref in self.ship[section]:
                key = category + ":" + ref["id"]
                if key in keys:
                    rows[key] = SimpleNamespace(
                        key=key,
                        category=category,
                        source_id=ref["id"],
                        space_id=ref["space_id"],
                        source_model=self.ship["model_version"],
                        reference=copy.deepcopy(ref),
                    )
        self.assertTrue(validate_gateway_sources(rows, self.ship))
        row = rows[SOURCES[0]]
        row.space_id = "BE-05-SVC"
        with self.assertRaises(MindPowerError):
            validate_gateway_sources(rows, self.ship)
        row.space_id = row.reference["space_id"]
        row.reference["kind"] = "invented_sensor"
        with self.assertRaises(MindPowerError):
            validate_gateway_sources(rows, self.ship)

    def test_unmeasured_supply_cannot_sample_or_draw_and_bad_tap_is_refused(self):
        """A gateway equipment record is neither energy nor protocol proof."""
        self.assertEqual(self.step(), 0)
        self.assertFalse(self.account["last"]["powered"])
        self.assertEqual(self.account["last"]["raw_samples"], {})
        wrong = copy.deepcopy(self.support)
        wrong["gateway_candidates"][0]["power_connection"]["panel_node"] = "PWR-PROT"
        with self.assertRaises(MindPowerError):
            gateway_power_rows(wrong, self.ship)
        with self.assertRaises(MindPowerError):
            survey_gateway_power(self.account, self.rows, measured_kw=100, evidence_id="bad-rating")

    def test_actual_energy_requires_its_fuse_and_original_panel(self):
        """A connected backbone cannot energise a dead local panel."""
        self.survey()
        self.assertAlmostEqual(self.step(), 0.00005)
        self.assertAlmostEqual(self.account["served_kwh"], 0.05 * 10 / 3600)
        self.power["nodes"] = set()
        self.assertEqual(self.step(now_s=1020), 0)
        self.assertFalse(self.account["last"]["readings"])
        self.power["nodes"] = {"NODE-LP-BE-05-SVC"}
        self.rows["isolator:ISO-PWR-GW-LCS-DR-03"].setting = "open"
        self.assertEqual(self.step(now_s=1030), 0)
        self.assertEqual(self.sources["isolator:ISO-DR-03-LT-IF"].setting, "closed")

    def test_gateway_cannot_draw_without_a_verified_intact_cool_thermal_path(self):
        """Unpressurised electronics require the real mount and a receiving sink."""
        with self.assertRaises(MindPowerError):
            survey_gateway_power(
                self.account, self.rows, measured_kw=0.05, evidence_id="no-heat-proof"
            )
        self.survey()
        after, mw = step_gateway(
            self.account,
            rows=self.rows,
            support_rows=self.hardware,
            source_rows=self.sources,
            power=self.power,
            connected=True,
            seconds=10,
            now_s=1010,
            heat_sink_available=False,
            operating_machines=self.operating,
        )
        self.assertEqual(mw, 0)
        self.assertEqual(after["served_kwh"], 0)
        self.rows["edge:THERM-GW-LCS-DR-03"].condition = "failed"
        self.assertEqual(self.step(), 0)

    def test_running_feedback_requires_current_served_operation_not_the_online_flag(self):
        """An energised gateway cannot turn an unserved machine flag into feedback."""
        self.survey()
        self.sources[SOURCES[0]].details["physics_online"] = True
        self.step()
        self.assertEqual(self.account["last"]["raw_samples"][SOURCES[0]]["raw_value"], 0)
        self.account = verify_gateway_protocol(
            self.account, profile=PROFILE, confirmations=self.confirmations(), observed_s=1010
        )
        self.step(now_s=1020)
        self.assertIs(self.account["last"]["readings"][SOURCES[0]]["value"], False)
        self.operating.add(SOURCES[0].split(":", 1)[1])
        self.step(now_s=1030)
        self.assertIs(self.account["last"]["readings"][SOURCES[0]]["value"], True)
        unknown = raw_gateway_samples(self.sources, now_s=1040)
        self.assertEqual(unknown[SOURCES[0]]["quality"], "unavailable")
        self.assertIsNone(unknown[SOURCES[0]]["raw_value"])

    def test_protocol_requires_fresh_actual_raw_frames_and_exact_meanings(self):
        """Wrong register meanings never receive a verified mapping revision."""
        self.survey()
        self.step()
        wrong = self.confirmations()
        wrong[SOURCES[0]]["meaning"] = "delivering_cooling"
        with self.assertRaises(MindPowerError):
            verify_gateway_protocol(
                self.account, profile=PROFILE, confirmations=wrong, observed_s=1010
            )
        with self.assertRaises(MindPowerError):
            verify_gateway_protocol(
                self.account, profile=PROFILE, confirmations=self.confirmations(), observed_s=1020
            )
        self.account = verify_gateway_protocol(
            self.account, profile=PROFILE, confirmations=self.confirmations(), observed_s=1010
        )
        self.step(now_s=1020)
        reading = self.account["last"]["readings"][SOURCES[0]]
        self.assertEqual(reading["raw_term"], "RUN_FB")
        self.assertEqual(reading["raw_value"], 0)
        self.assertEqual(reading["mapping_revision"], 1)
        self.assertEqual(reading["meaning"], "running_feedback")
        self.assertIs(reading["value"], False)
        self.assertFalse(self.account["last"]["remote_commands_enabled"])

    def test_lost_network_discards_old_readings_and_restores_only_fresh_samples(self):
        """There is no queued command replay or stale sample labelled current."""
        self.survey()
        self.step()
        self.account = verify_gateway_protocol(
            self.account, profile=PROFILE, confirmations=self.confirmations(), observed_s=1010
        )
        self.step(connected=False, now_s=1020)
        self.assertTrue(self.account["last"]["powered"])
        self.assertFalse(self.account["last"]["readings"])
        self.sources[SOURCES[0]].details["physics_online"] = True
        self.operating.add(SOURCES[0].split(":", 1)[1])
        self.sources[SOURCES[0]].revision += 1
        self.step(now_s=1030)
        reading = self.account["last"]["readings"][SOURCES[0]]
        self.assertIs(reading["value"], True)
        self.assertEqual(reading["source_time"], 1030)
        self.assertEqual(reading["source_revision"], 2)
        self.assertFalse(self.account["last"]["remote_commands_enabled"])
        corrupt = copy.deepcopy(self.account)
        corrupt["last"]["remote_commands_enabled"] = True
        with self.assertRaises(MindPowerError):
            validate_gateway(corrupt)

    def test_unknown_or_bad_raw_data_never_becomes_a_zero_measurement(self):
        """Keep the original term and raw failure while withholding translation."""
        samples = raw_gateway_samples(self.sources, now_s=1000, operating_machines=self.operating)
        samples[SOURCES[0]]["raw_value"] = 7
        decoded = translate_gateway_samples(samples, mapping_revision=1)
        self.assertEqual(decoded[SOURCES[0]]["raw_value"], 7)
        self.assertIsNone(decoded[SOURCES[0]]["value"])
        self.assertEqual(decoded[SOURCES[0]]["quality"], "unavailable")

    def test_gateway_is_not_a_bridge_and_both_local_cable_cuts_remove_its_view(self):
        """A/B rail reachability ends at consumers, including the gateway."""
        for row in self.hardware.values():
            if row.category == "edge" or row.source_id in {"NET-ROT-A", "NET-ROT-B"}:
                row.details["data_survey"] = {
                    "version": 1,
                    "row_revision": 1,
                    "observed_s": 1000,
                    "reference_sha256": survey_signature(row.reference),
                    "evidence_id": "continuity",
                    "pressure_penetrations": [],
                    "continuity_verified": True,
                    "pressure_verified": True,
                    "environment_verified": True,
                    "emi_verified": True,
                    "continuous_rpm": 3.6 if row.category == "equipment" else None,
                }
        args = dict(physical_rows=self.hardware, gateway_id="GW-LCS-DR-03")
        self.assertEqual(len(connected_machines(self.support, **args)), 9)
        for rail in ("A", "B"):
            self.hardware["edge:NET-GW-DROP-" + rail + "-DR-03"].condition = "severed"
        self.assertFalse(connected_machines(self.support, **args))
        self.assertEqual(len(connected_machines(self.support, physical_rows=self.hardware)), 9)


if __name__ == "__main__":
    unittest.main()
