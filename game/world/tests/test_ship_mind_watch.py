"""Pure first-watch trust rules: one delivered observation, no hidden state."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from world.ship_access_contact import LINK, OBSERVED, SENSOR
from world.ship_mind_watch import (
    KEY, SCHEMA, SOURCE, FIRED, ShipWatchError, arm_details,
    committed_watch_notice, empty_details, match_delivery, reference,
    source_after_arm, validate_watch,
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

    def test_old_physical_event_cannot_be_republished_as_new_delivery(self):
        row = armed()  # Armed after world event 75.
        physical = SimpleNamespace(sequence=70)
        observation = SimpleNamespace(sequence=72)
        self.assertFalse(source_after_arm(row, physical, observation))
        # An old physical action cannot become eligible merely because
        # a new sensor or delivery envelope is created much later.
        observation.sequence = 90
        self.assertFalse(source_after_arm(row, physical, observation))
        physical.sequence = 76
        observation.sequence = 77
        self.assertTrue(source_after_arm(row, physical, observation))
        observation.sequence = 75
        self.assertFalse(source_after_arm(row, physical, observation))

    def test_committed_notice_is_bound_to_exact_world_firing(self):
        row = armed()
        row.setting = "fired"
        row.details.update(delivery_sequence=79, source_time=1080.0)
        event = SimpleNamespace(
            sequence=80, component_key=KEY, operation=FIRED,
            source_event_id="79", actor_dbref=None, request_id=None,
            before={"generation": 1, "desired": "open"},
            after={
                "generation": 1, "desired": "open",
                "delivery_event_id": "ox-net-79",
                "source_time": 1080.0,
                "controls_time": False, "physical_actuation": False,
            },
            game_time=1080.0,
        )
        expected = committed_watch_notice(
            row, event, owner_pk=12, epoch=EPOCH,
        )
        self.assertEqual(expected, {
            "schema_version": "ox.ship-mind-watch-wake/1",
            "status": "fired", "request_id": REQUEST,
            "desired": "open", "wake_event_id": "ox-watch-80",
            "delivery_event_id": "ox-net-79",
            "source_time": 1080.0,
            "controls_time": False, "physical_actuation": False,
        })
        self.assertNotIn("actor_dbref", expected)
        self.assertNotIn("location", expected)
        self.assertIsNone(committed_watch_notice(
            row, event, owner_pk=13, epoch=EPOCH))
        self.assertIsNone(committed_watch_notice(
            row, event, owner_pk=12, epoch="f" * 32))
        scenarios = [
            ("old watch", lambda r, e: setattr(r, "setting", "armed")),
            ("wrong source", lambda r, e: setattr(e, "source_event_id", "78")),
            ("wrong operation", lambda r, e: setattr(e, "operation", "crew_hatch")),
            ("other component", lambda r, e: setattr(e, "component_key", "other")),
            ("fake request", lambda r, e: setattr(e, "request_id", REQUEST)),
            ("crew identity", lambda r, e: setattr(e, "actor_dbref", "#7")),
            ("unexpected data", lambda r, e: e.after.update(actor_dbref="#7")),
            ("unauthorized clock", lambda r, e: e.after.update(controls_time=True)),
            ("fictitious actuator", lambda r, e: e.after.update(physical_actuation=True)),
            ("different reading", lambda r, e: e.after.update(desired="closed")),
            ("different sensor time", lambda r, e: e.after.update(source_time=1090.0)),
            ("different firing generation", lambda r, e: e.after.update(generation=2)),
            ("old firing sequence", lambda r, e: setattr(e, "sequence", 79)),
            ("misleading firing time", lambda r, e: setattr(e, "game_time", 1081.0)),
        ]
        for title, mutate in scenarios:
            with self.subTest(title=title):
                changed_row = deepcopy(row)
                changed_event = deepcopy(event)
                mutate(changed_row, changed_event)
                self.assertIsNone(committed_watch_notice(
                    changed_row, changed_event, owner_pk=12, epoch=EPOCH))

