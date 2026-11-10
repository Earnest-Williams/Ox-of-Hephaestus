"""Finite cooldown, retained protection latches and attended restart rules."""

import copy
import unittest
from types import SimpleNamespace

from world.ship_auxiliary_electrical import MOTORS, _specs, auxiliary_ids
from world.ship_mind_power import MindPowerError
from world.ship_mind_service import (
    SERVICE_KEY,
    advance_cooldown,
    machine_mode,
    request_service,
    service_signature,
    service_state,
)
from world.ship_mind_support import load_support
from world.ship_process_outputs import FIELD, step_process_output

class MindServiceTests(unittest.TestCase):
    """Physical reset permission must follow measured recovery, not elapsed wall time."""

    def setUp(self):
        """Use an authentic thermal-trip revision with finite measured headroom."""
        self.row = SimpleNamespace(
            condition="faulted",
            revision=3,
            details={"physics_mind_thermal_trip": True, "physics_mind_trip_revision": 3},
        )
        self.pod = load_support()["cooling_islands"][0]
        self.bank = {"surveyed": True, "free_kj": 720}
        self.signature = "a" * 64

    def apply(self, record):
        """Simulate the world adapter's trusted controller revision update."""
        self.row.details[SERVICE_KEY] = record
        self.row.revision = record["row_revision"]
        self.row.details["physics_mind_trip_revision"] = self.row.revision

    def request(self, command, **changes):
        """Submit a local control against explicit current physical evidence."""
        args = dict(
            now_s=1030, signature=self.signature, pod=self.pod, bank=self.bank, temperature_k=293.15
        )
        args.update(changes)
        return request_service(self.row, command, **args)

    def prove(self):
        """Accumulate three actually observed powered cooling intervals."""
        self.apply(self.request("cooldown"))
        for now in (1010, 1020, 1030):
            self.apply(
                advance_cooldown(
                    self.row,
                    seconds=10,
                    now_s=now,
                    good=True,
                    hazardous=False,
                    signature=self.signature,
                )
            )

    def test_trip_latch_survives_cooldown_and_requires_a_new_restart_command(self):
        """Measured recovery never automatically turns the computer back on."""
        self.assertEqual(machine_mode(self.row), "stopped")
        self.prove()
        self.assertEqual(machine_mode(self.row), "cooldown")
        self.assertTrue(self.row.details["physics_mind_thermal_trip"])
        self.assertEqual(self.request("restart")["mode"], "running")
        self.assertEqual(self.row.condition, "faulted")
        self.assertEqual(self.bank["free_kj"], 720)

    def test_restart_rejects_stale_changed_hot_or_unfunded_evidence(self):
        """Each restart gate has a distinct failing physical counterexample."""
        self.prove()
        for changes in (
            {"now_s": 1040},
            {"signature": "b" * 64},
            {"temperature_k": 313.15},
            {"bank": {"surveyed": True, "free_kj": 479}},
            {"bank": {"surveyed": False, "free_kj": 720}},
        ):
            with self.subTest(changes=changes), self.assertRaises(MindPowerError):
                self.request("restart", **changes)

    def test_supply_or_hardware_change_restarts_consecutive_observation(self):
        """Losing output or revising hardware removes the previous ready proof."""
        self.prove()
        lost = advance_cooldown(
            self.row, seconds=10, now_s=1040, good=False, hazardous=False, signature=self.signature
        )
        self.assertEqual(lost["verified_s"], 0)
        changed = advance_cooldown(
            self.row, seconds=10, now_s=1040, good=True, hazardous=False, signature="b" * 64
        )
        self.assertEqual(changed["verified_s"], 10)
        gap = advance_cooldown(
            self.row, seconds=10, now_s=1050, good=True, hazardous=False, signature=self.signature
        )
        self.assertEqual(gap["verified_s"], 10)

    def test_new_machine_damage_cannot_be_cleared_as_the_old_thermal_trip(self):
        """An intervening physical mutation invalidates the original trip revision."""
        self.prove()
        self.row.revision += 1
        self.assertEqual(machine_mode(self.row), "stopped")
        for command in ("restart", "cooldown"):
            with self.assertRaises(MindPowerError):
                self.request(command)
        stopped = advance_cooldown(
            self.row, seconds=10, now_s=1040, good=False, hazardous=False, signature=self.signature
        )
        self.assertEqual(stopped["mode"], "stopped")

    def test_hazard_stops_auxiliaries_and_retains_damage(self):
        """Uncontained heat or overtemperature trips the service controller too."""
        self.prove()
        stopped = advance_cooldown(
            self.row, seconds=10, now_s=1040, good=False, hazardous=True, signature=self.signature
        )
        self.assertEqual(stopped["mode"], "stopped")
        self.assertEqual(stopped["verified_s"], 0)
        self.assertEqual(self.row.condition, "faulted")

    def test_corrupt_service_progress_is_rejected(self):
        """Persisted garbage cannot manufacture a completed cooling observation."""
        self.prove()
        baseline = copy.deepcopy(self.row.details)
        for field, bad in (
            ("verified_s", float("nan")),
            ("verified_s", 1000),
            ("row_revision", True),
            ("mode", "auto_restart"),
        ):
            self.row.details = copy.deepcopy(baseline)
            self.row.details[SERVICE_KEY][field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(MindPowerError):
                service_state(self.row)

    def test_process_receipts_preserve_proof_but_lt_hardware_changes_invalidate_it(self):
        """Running and stopped consumers cannot block otherwise verified cooling."""
        rows = {key: SimpleNamespace(**spec, revision=1) for key, spec in _specs().items()}
        for name in {*MOTORS, "GEN-M", self.pod["heat_rejector_id"]}:
            key = "equipment:" + name
            rows[key] = SimpleNamespace(
                category="equipment",
                source_id=name,
                revision=1,
                condition="serviceable",
                setting="unverified",
                reference={},
                details={},
            )
        self.signature = service_signature(rows, "essential", self.pod)
        self.apply(self.request("cooldown"))
        for now in (1010, 1020, 1030):
            for name in ("BE-01-LUBE-N", "SPINE-AIR-FWD"):
                motor = rows["equipment:" + name]
                motor.details[FIELD] = step_process_output(
                    name,
                    motor.details.get(FIELD),
                    dt_s=10,
                    now_s=now,
                    driven=name == "BE-01-LUBE-N" and now == 1010,
                )
                motor.revision += 1
            signature = service_signature(rows, "essential", self.pod)
            self.assertEqual(signature, self.signature)
            self.apply(
                advance_cooldown(
                    self.row, seconds=10, now_s=now, good=True, hazardous=False, signature=signature
                )
            )
        self.assertEqual(self.request("restart")["mode"], "running")
        lt_keys = [
            category + ":" + name
            for category, name in zip(
                ("node", "edge", "isolator"), auxiliary_ids("LT-PLANT", motor=True)
            )
        ]
        for key in lt_keys + [
            "equipment:LT-PLANT",
            "equipment:GEN-M",
            "equipment:" + self.pod["heat_rejector_id"],
        ]:
            with self.subTest(component=key):
                rows[key].revision += 1
                with self.assertRaises(MindPowerError):
                    self.request(
                        "restart", signature=service_signature(rows, "essential", self.pod)
                    )
                rows[key].revision -= 1
