"""P3c OOB event framing must preserve recipient scoping and data."""
import unittest
import json
from ox_ai.ports.evennia.client import WebPacket
from ox_ai.scenarios.p3c_crew import next_event


class _Client:
    character_dbref = "#12"
    def __init__(self, packets):
        self._packets = list(packets)
    async def receive(self):
        return self._packets.pop(0)


class EventTests(unittest.IsolatedAsyncioTestCase):
    async def test_nested_map_wrapper(self):
        event = {"event_id": "oxevt-0001", "recipient_dbref": "#12",
                 "kind": "coolant_alarm", "data": {"alarm_id": "p01-0001"}}
        client = _Client([WebPacket("ox_event", (json.dumps(event),), {})])
        memory = []
        result = await next_event(client, "coolant_alarm", memory)
        self.assertEqual(result["data"]["alarm_id"], "p01-0001")
        self.assertEqual(len(memory), 1)

    async def test_other_recipient_denied(self):
        event = {"event_id": "oxevt-0001", "recipient_dbref": "#99",
                 "kind": "coolant_alarm", "data": {"alarm_id": "p01-0001"}}
        client = _Client([WebPacket("ox_event", (event,), {})])
        with self.assertRaises(PermissionError):
            await next_event(client, "coolant_alarm", [])
