"""Model-free contract tests for the P4b supervisor's pure boundaries."""
import unittest

from ox_ai.ports.evennia.client import WebPacket
from ox_ai.runtime.watch_service import (
    active_watch_from_roster, decode_event, newest_unseen_alarm,
)


class SupervisorContractTests(unittest.TestCase):
    def test_read_authoritative_roster_role_not_placeholder_metadata(self):
        self.assertEqual(
            active_watch_from_roster(
                "Engineer Ari Sen: Watch\nActive engineering watch: Engineer Ari Sen"
            ), "ari"
        )
        self.assertEqual(
            active_watch_from_roster(
                "Chief Engineer Iona Vek\nActive engineering watch: Chief Engineer Iona Vek"
            ), "iona"
        )
        with self.assertRaises(RuntimeError):
            active_watch_from_roster("Watch assigned to everybody")

    def test_role_private_world_event_scope_and_flat_oob_contract(self):
        packet = WebPacket("ox_event", ({
            "event_id": "oxevt-0040", "recipient_dbref": "#10",
            "kind": "radio_alert", "datum_alarm_id": "p01-0005",
            "game_time": 1234.5,
        },), {})
        result = decode_event(packet, "#10")
        self.assertEqual(result["data"]["alarm_id"], "p01-0005")
        with self.assertRaises(PermissionError):
            decode_event(packet, "#11")
        with self.assertRaises(ValueError):
            decode_event(WebPacket("ox_event", ({
                "event_id": "fake", "recipient_dbref": "#10",
                "data": {"world_state": "omniscient"},
            },), {}), "#10")
        self.assertIsNone(decode_event(WebPacket("text", ("hello",), {}), "#10"))

    def test_catch_up_prefers_latest_unknown_alarm_once(self):
        events = [
            {"event_id": "oxevt-0002", "kind": "coolant_alarm",
             "data": {"alarm_id": "p01-0001"}},
            {"event_id": "oxevt-0015", "kind": "coolant_alarm",
             "data": {"alarm_id": "p01-0005"}},
        ]
        newest, history = newest_unseen_alarm(events, set())
        self.assertEqual(newest["data"]["alarm_id"], "p01-0005")
        self.assertEqual(history, {"p01-0001", "p01-0005"})
        self.assertIsNone(newest_unseen_alarm(events, history)[0])


if __name__ == "__main__":
    unittest.main()
