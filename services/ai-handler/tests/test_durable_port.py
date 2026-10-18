"""No-network proof that chat text cannot fabricate physical success."""
import asyncio
import unittest

from ox_ai.ports.base import ActionRequest
from ox_ai.ports.evennia.client import WebPacket
from ox_ai.ports.evennia.durable import DurableEvenniaPort


class FakeClient:
    authenticated = True
    character_dbref = "#42"

    def __init__(self):
        self.lines, self.packets = [], []

    async def send_line(self, line):
        self.lines.append(line)

    async def receive(self):
        if self.packets:
            return self.packets.pop(0)
        await asyncio.sleep(0.1)


class DurablePortTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_spoof_is_not_a_verified_outcome(self):
        c = FakeClient()
        request_id = "a" * 32
        c.packets = [
            WebPacket("text", ("OX_RECEIPT " + request_id + " succeeded",), {}),
            WebPacket("ox_receipt", ({
                "request_id": request_id, "actor_dbref": "#42",
                "status": "succeeded", "reason": "transition_applied",
                "source_event_id": "p01-0002",
            },), {}),
        ]
        result = await DurableEvenniaPort(c, timeout=0.2).submit(
            ActionRequest(request_id, "#42", "isolate_pump", "pump")
        )
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.source_event_id, "p01-0002")
        self.assertEqual(c.lines, ["oxaction " + request_id + " isolate"])

    async def test_evennia_legacy_keyword_form_is_world_receipt(self):
        c = FakeClient()
        request_id = "e" * 32
        c.packets = [WebPacket("ox_receipt", (), {
            "request_id": request_id, "actor_dbref": "#42",
            "status": "succeeded", "source_event_id": "p01-0007",
            "options": {},
        })]
        result = await DurableEvenniaPort(c).reconcile(request_id)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.source_event_id, "p01-0007")

    async def test_timeout_stays_unknown_and_does_not_replay(self):
        c = FakeClient()
        request_id = "b" * 32
        result = await DurableEvenniaPort(c, timeout=0.01).reconcile(request_id)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(c.lines, ["oxreceipt " + request_id])

    async def test_wrong_character_or_cross_user_result_is_rejected(self):
        c = FakeClient()
        request_id = "c" * 32
        port = DurableEvenniaPort(c)
        with self.assertRaises(PermissionError):
            await port.submit(ActionRequest(request_id, "#99", "isolate_pump", "pump"))
        c.packets = [WebPacket("ox_receipt", ({
            "request_id": request_id, "actor_dbref": "#99", "status": "succeeded",
        },), {})]
        with self.assertRaises(PermissionError):
            await port.reconcile(request_id)


if __name__ == "__main__":
    unittest.main()
