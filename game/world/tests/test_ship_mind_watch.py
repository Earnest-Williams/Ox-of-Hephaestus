"""Pure first-watch trust rules: one delivered observation, no hidden state."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from world.ship_access_contact import LINK, OBSERVED, SENSOR
from world.ship_mind_watch import (
    KEY, SCHEMA, SOURCE, ShipWatchError, arm_details,
    empty_details, match_delivery, reference, validate_watch,
)
from world.ship_network_access import DELIVERED, PRINCIPAL, capture

EPOCH = "a" * 32
REQUEST = "b" * 32


def state():
    return SimpleNamespace(
        key=KEY, category="control", source_id=SOURCE,
        source_model=SCHEMA, space_id=None, condition="serviceable",
        setting="idle", reference=reference(), details=empty_details(),
    )


def delivery():
    sensor = SimpleNamespace(
        operation=OBSERVED, component_key="equipment:" + SENSOR,
        sequence=78, source_event_id="77",
        before={"setting": "closed"},
        after={
            "setting": "open", "link_id": LINK,
            "sensor_revision": 2, "cable_revision": 1,
        },
        actor_dbref=None, request_id=None, game_time=1080.0,
    )
    return SimpleNamespace(
        sequence=79, operation=DELIVERED,
        component_key=PRINCIPAL,
        source_event_id="78",
        before={}, after={**capture(sensor), "epoch": EPOCH},
        actor_dbref=None, request_id=None, game_time=1080.0,
    )


def armed():
    row = state()
    row.details = arm_details(
        row, request_id=REQUEST, owner_pk=12,
        epoch=EPOCH, desired="open", after_sequence=75,
    )
    row.setting = "armed"
    return row


class FirstWatchPolicyTests(unittest.TestCase):
    def test_world_state_and_single_owner_with_immutable_anchor(self):
        row = armed()
        self.assertTrue(validate_watch(row))
        self.assertEqual(row.details["generation"], 1)
        self.assertFalse(row.reference["automatic_physical_action"])
        self.assertFalse(row.reference["controls_time"])
        with self.assertRaises(ShipWatchError):
            arm_details(row, request_id="c" * 32, owner_pk=12,
                        epoch=EPOCH, desired="closed", after_sequence=80)
        row.setting = "fired"
        with self.assertRaises(ShipWatchError):
            validate_watch(row)
        row.details["delivery_sequence"] = 79
        row.details["source_time"] = 1080.0
        self.assertTrue(validate_watch(row))
        row.reference = dict(row.reference, controls_time=True)
        with self.assertRaises(ShipWatchError):
            validate_watch(row)

    def test_only_matching_future_delivered_hatch_state_fires(self):
        row, sample = armed(), delivery()
        result = match_delivery(row, sample, owner_pk=12, epoch=EPOCH)
        self.assertEqual(result, {
            "delivery_sequence": 79,
            "source_time": 1080.0,
            "desired": "open",
        })
        scenarios = [
            ("wrong account", lambda r, d: None, 13, EPOCH),
            ("wrong epoch", lambda r, d: None, 12, "c" * 32),
            ("prior delivery", lambda r, d: setattr(d, "sequence", 74), 12, EPOCH),
            ("wrong position", lambda r, d: d.after.update(setting_after="closed"), 12, EPOCH),
            ("wrong principal", lambda r, d: setattr(d, "component_key", "principal:other"), 12, EPOCH),
            ("wrong reader", lambda r, d: d.after.update(reader_id="sensor:other"), 12, EPOCH),
            ("foreign epoch", lambda r, d: d.after.update(epoch="f" * 32), 12, EPOCH),
            ("fake movement", lambda r, d: d.after.update(setting_before="open"), 12, EPOCH),
            ("not a delivery", lambda r, d: setattr(d, "operation", "crew_hatch"), 12, EPOCH),
        ]
        for name, transform, pk, epoch in scenarios:
            with self.subTest(name=name):
                r, d = armed(), deepcopy(sample)
                transform(r, d)
                self.assertIsNone(match_delivery(
                    r, d, owner_pk=pk, epoch=epoch))
        row.setting = "fired"
        row.details.update(delivery_sequence=79, source_time=1080.0)
        self.assertIsNone(match_delivery(row, sample, owner_pk=12, epoch=EPOCH))

    def test_rejects_bad_request_or_idle_phantom(self):
        row = state()
        row.details["desired"] = "open"
        with self.assertRaises(ShipWatchError):
            validate_watch(row)
        for value in (None, "b" * 31, "B" * 32, "not-a-uuid"):
            with self.subTest(request_id=value):
                with self.assertRaises(ShipWatchError):
                    arm_details(state(), request_id=value, owner_pk=12,
                                epoch=EPOCH, desired="open", after_sequence=10)
