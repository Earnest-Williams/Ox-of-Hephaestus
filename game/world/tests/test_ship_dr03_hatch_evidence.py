"""Pure evidence-chain rejection of guesses and undelivered hatch movement."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from world.ship_access_contact import LINK, OBSERVED, SENSOR
from world.ship_dr03_hatch_evidence import verified_hatch_completion
from world.ship_dr03_hatch_policy import DECIDED, KEY
from world.ship_network_access import DELIVERED, PRINCIPAL, capture


REQUEST_ID = "1" * 32
EPOCH = "a" * 32


def evidence():
    decision = SimpleNamespace(
        sequence=10, operation=DECIDED, component_key=KEY,
        actor_dbref="#22", game_time=1010.0,
        after={
            "original_request_id": REQUEST_ID,
            "local_decision": "accept", "desired": "open",
            "status": "accepted_for_manual_action",
        },
    )
    physical = SimpleNamespace(
        sequence=11, operation="crew_hatch", component_key="access:" + LINK,
        actor_dbref="#22", request_id="4" * 32, game_time=1020.0,
        before={"setting": "closed"},
        after={"setting": "open", "requested_value": "open"},
    )
    observation = SimpleNamespace(
        sequence=12, operation=OBSERVED, component_key="equipment:" + SENSOR,
        source_event_id="11", actor_dbref=None, request_id=None,
        game_time=1020.0, before={"setting": "closed"},
        after={
            "setting": "open", "link_id": LINK,
            "sensor_revision": 2, "cable_revision": 0,
        },
    )
    delivery = SimpleNamespace(
        sequence=13, operation=DELIVERED, component_key=PRINCIPAL,
        source_event_id="12", actor_dbref=None, request_id=None,
        game_time=1020.0, after={**capture(observation), "epoch": EPOCH},
    )
    return decision, physical, observation, delivery


def verify(parts, epoch=EPOCH):
    return verified_hatch_completion(
        *parts, original_request_id=REQUEST_ID,
        desired="open", principal_epoch=epoch,
    )


class HatchCompletionEvidenceTests(unittest.TestCase):
    def test_requires_matching_attended_action_and_event_time_delivery(self):
        result = verify(evidence())
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "world_confirmed_at_source_time")
        self.assertEqual(result["physical_hatch_event_id"], "11")
        self.assertEqual(result["sensor_event_id"], "12")
        self.assertEqual(result["delivery_event_id"], "ox-net-13")
        self.assertEqual(result["source_time"], 1020.0)

    def test_refuses_noop_unrelated_actor_early_action_or_decline(self):
        cases = [
            ("other worker", lambda d,p,o,n: setattr(p,"actor_dbref","#23")),
            ("no effect", lambda d,p,o,n: p.before.update(setting="open")),
            ("not accepted", lambda d,p,o,n: d.after.update(
                local_decision="decline", status="declined_by_crew")),
            ("too early", lambda d,p,o,n: setattr(p,"sequence",9)),
            ("wrong position", lambda d,p,o,n: p.after.update(setting="closed")),
            ("bad request association", lambda d,p,o,n: d.after.update(
                original_request_id="5" * 32)),
            ("different requested value", lambda d,p,o,n: p.after.update(
                requested_value="closed")),
        ]
        for name, alter in cases:
            with self.subTest(name=name):
                parts = deepcopy(evidence())
                alter(*parts)
                self.assertIsNone(verify(parts))

    def test_refuses_forged_or_unavailable_sensor_and_network_evidence(self):
        cases = [
            ("no delivery", lambda d,p,o,n: None),
            ("wrong epoch", lambda d,p,o,n: n.after.update(epoch="b" * 32)),
            ("wrong physical event", lambda d,p,o,n: setattr(
                o, "source_event_id", "999")),
            ("fictitious contact", lambda d,p,o,n: o.after.update(
                link_id="ACC-OTHER")),
            ("delivery from another contact", lambda d,p,o,n: n.after.update(
                physical_hatch_event_id="999")),
            ("tampered sensor", lambda d,p,o,n: n.after.update(
                sensor_revision=99)),
            ("wrong delivery source", lambda d,p,o,n: setattr(
                n, "source_event_id", "999")),
            ("wrong delivery timing", lambda d,p,o,n: setattr(
                n, "game_time", 1021.0)),
            ("wrong read principal", lambda d,p,o,n: setattr(
                n, "component_key", "principal:other")),
        ]
        for name, alter in cases:
            with self.subTest(name=name):
                parts = list(deepcopy(evidence()))
                if name == "no delivery":
                    parts[3] = None
                else:
                    alter(*parts)
                self.assertIsNone(verify(parts))

    def test_rejects_an_observation_without_an_account_delivery(self):
        dec, physical, observed, delivery = evidence()
        self.assertIsNone(verify((dec, physical, observed, None)))
        self.assertIsNone(verify((dec, physical, observed, delivery),
                                 epoch="c" * 32))
