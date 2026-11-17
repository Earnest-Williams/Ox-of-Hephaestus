"""Pure invariants for request-only hatch handover."""
from types import SimpleNamespace
import unittest

from world.ship_dr03_hatch_policy import (
    HatchHandoverError, KEY, LINK, ROOM, SCHEMA, SOURCE,
    clear_pending, pending_state, reference, request_id_valid,
    validate_control,
)


def control():
    return SimpleNamespace(
        key=KEY, category="control", source_id=SOURCE,
        source_model=SCHEMA, space_id=ROOM, condition="serviceable",
        setting="idle", reference=reference(),
        details={
            "request_id": None, "request_event": None,
            "desired": None, "requester": None, "epoch": 0,
        },
    )


class HatchHandoverPolicyTests(unittest.TestCase):
    def test_never_invents_hatch_motor_or_second_actuator(self):
        row = control()
        self.assertTrue(validate_control(row))
        self.assertEqual(row.reference["link"], LINK)
        self.assertFalse(row.reference["remote_door_motor"])
        self.assertEqual(row.reference["remote_role"], "request_only")
        row.reference = dict(row.reference, remote_door_motor=True)
        with self.assertRaises(HatchHandoverError):
            validate_control(row)

    def test_pending_request_has_one_owner_and_immutable_event(self):
        row = control()
        details = pending_state(row, "a" * 32, "open", "account:12", 17)
        row.details = details
        row.setting = "pending"
        self.assertTrue(validate_control(row))
        self.assertEqual(row.details["request_event"], 17)
        self.assertEqual(row.details["epoch"], 1)
        with self.assertRaises(HatchHandoverError):
            pending_state(row, "b" * 32, "closed", "account:12", 18)
        with self.assertRaises(HatchHandoverError):
            clear_pending(row, "b" * 32)
        row.details = clear_pending(row, "a" * 32)
        row.setting = "idle"
        self.assertTrue(validate_control(row))
        self.assertEqual(row.details["epoch"], 2)

    def test_rejects_fake_account_bad_ids_and_phantom_state(self):
        row = control()
        for token in ("", "A" * 32, "a" * 31, None):
            with self.subTest(token=token):
                with self.assertRaises(HatchHandoverError):
                    request_id_valid(token)
        for principal in ("#5", "account:0", "account:-1", "account:foo"):
            with self.subTest(principal=principal):
                with self.assertRaises(HatchHandoverError):
                    pending_state(row, "1" * 32, "open", principal, 1)
        with self.assertRaises(HatchHandoverError):
            pending_state(row, "1" * 32, "open", "account:8", 0)
        row.details["desired"] = "open"
        with self.assertRaises(HatchHandoverError):
            validate_control(row)
