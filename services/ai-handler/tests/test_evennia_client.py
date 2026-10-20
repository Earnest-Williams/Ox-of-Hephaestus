"""Offline WebSocket framing and identity-bound client checks."""

import asyncio
import json
import unittest

from ox_ai.ports.evennia.client import EvenniaWebSocketClient, IdentityMismatch, MAX_COMMAND_CHARS


class FakeSocket:
    def __init__(self, correct="#42"):
        self.sent = []
        self.correct = correct
        self.closed = False
        self.frames = [json.dumps(["text", ["Evennia welcome"], {}])]
        self.next_notice = None

    async def send(self, frame):
        command = json.loads(frame)[1][0]
        self.sent.append(command)
        if command.startswith("connect "):
            self.frames.append(json.dumps(["logged_in", [], {}]))
        elif command.startswith("oxidentity "):
            challenge = command.split(" ")[1]
            self.frames.append(json.dumps([
                "text", ["OX_IDENTITY " + challenge + " " + self.correct], {}
            ]))
        elif command == "look":
            self.frames.append(json.dumps(["text", ["Engineering"], {}]))

    async def recv(self):
        while not self.frames:
            await asyncio.sleep(0)
        return self.frames.pop(0)

    async def close(self):
        self.closed = True


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_command_frames_and_verified_character_binding(self):
        socket = FakeSocket()
        async def connector(*args, **kwargs):
            self.assertEqual(kwargs["subprotocols"], ["v1.evennia.com"])
            return socket
        client = EvenniaWebSocketClient(
            "ws://127.0.0.1:4002", "OxBotAri",
            "AnEphemeralPass_123456", "#42", connector=connector,
        )
        async with client:
            self.assertTrue(client.authenticated)
            self.assertEqual(socket.sent[:2], [
                "connect OxBotAri AnEphemeralPass_123456", "ic #42",
            ])
            await client.send_line("look")
            self.assertIn("Engineering", await client.expect_text("Engineering"))
            with self.assertRaises(ValueError):
                await client.send_line("look\nshipfault pump")
        self.assertTrue(socket.closed)
        self.assertFalse(client.authenticated)

    async def test_another_character_cannot_complete_identity_handshake(self):
        sockets = []
        async def connector(*args, **kwargs):
            socket = FakeSocket(correct="#77")
            sockets.append(socket)
            return socket
        client = EvenniaWebSocketClient(
            "ws://localhost:4002", "OxBotAri",
            "AnEphemeralPass_123456", "#42",
            connector=connector, timeout=0.015,
        )
        with self.assertRaises(IdentityMismatch):
            await client.open()
        self.assertTrue(all(socket.closed for socket in sockets))
        self.assertFalse(client.authenticated)

    async def test_guard_against_credential_exposure_and_bad_frames(self):
        with self.assertRaises(ValueError):
            EvenniaWebSocketClient(
                "ws://outside.example:4002", "OxBotAri",
                "AnEphemeralPass_123456", "#42",
            )
        with self.assertRaises(ValueError):
            EvenniaWebSocketClient(
                "ws://localhost:4002", "OxBotAri",
                "short", "#42",
            )
        socket = FakeSocket()
        
        async def connector(*args, **kwargs):
            return socket
        client = EvenniaWebSocketClient(
            "ws://localhost:4002", "OxBotAri",
            "AnEphemeralPass_123456", "#42", connector=connector,
        )
        # Authentication succeeds first; a later malformed frame is rejected.
        await client.open()
        socket.frames.append(json.dumps({"world_state": "omnipotent"}))
        with self.assertRaises(ValueError):
            await client.receive()
        await client.close()


    async def test_transport_command_limit_matches_world_size(self):
        socket = FakeSocket()
        async def connector(*args, **kwargs):
            return socket
        client = EvenniaWebSocketClient("ws://localhost:4002", "OxBotAri",
            "AnEphemeralPass_123456", "#42", connector=connector)
        await client.open()
        try:
            await client.send_line("a" * MAX_COMMAND_CHARS)
            with self.assertRaises(ValueError):
                await client.send_line("a" * (MAX_COMMAND_CHARS + 1))
            self.assertEqual(len(socket.sent[-1]), MAX_COMMAND_CHARS)
        finally:
            await client.close()

    async def test_receive_buffer_overflow_fails_loudly_and_close_clears_it(self):
        from ox_ai.ports.evennia.client import MAX_BUFFERED_PACKETS
        socket = FakeSocket()
        async def connector(*args, **kwargs):
            return socket
        client = EvenniaWebSocketClient("ws://localhost:4002", "OxBotAri",
            "AnEphemeralPass_123456", "#42", connector=connector)
        await client.open()
        try:
            socket.frames.extend(
                json.dumps(["text", ["unrelated"], {}])
                for _ in range(MAX_BUFFERED_PACKETS + 1)
            )
            with self.assertRaisesRegex(RuntimeError, "bounded buffer"):
                await client.receive_matching(lambda p: p.kind == "ox_receipt",
                                              frame_budget=MAX_BUFFERED_PACKETS + 1)
            self.assertEqual(len(client._pending), MAX_BUFFERED_PACKETS)
        finally:
            await client.close()
        self.assertEqual(len(client._pending), 0)

    async def test_interleaved_observations_and_out_of_order_receipts_survive(self):
        socket = FakeSocket()
        async def connector(*args, **kwargs):
            return socket
        client = EvenniaWebSocketClient("ws://localhost:4002", "OxBotAri",
            "AnEphemeralPass_123456", "#42", connector=connector)
        await client.open()
        try:
            socket.frames.extend([
                json.dumps(["text", ["Lin says important words"], {}]),
                json.dumps(["ox_event", [{"event_id": "oxevt-v2-0001", "recipient_dbref": "#42"}], {}]),
                json.dumps(["ox_receipt", [{"request_id": "a" * 32}], {}]),
                json.dumps(["ox_receipt", [{"request_id": "b" * 32}], {}]),
            ])
            wanted = lambda rid: lambda p: p.kind == "ox_receipt" and p.args[0]["request_id"] == rid
            self.assertEqual((await client.receive_matching(wanted("b" * 32))).args[0]["request_id"], "b" * 32)
            self.assertIn("important", (await client.receive()).text)
            self.assertEqual((await client.receive()).kind, "ox_event")
            self.assertEqual((await client.receive_matching(wanted("a" * 32))).args[0]["request_id"], "a" * 32)
        finally:
            await client.close()


if __name__ == "__main__":
    unittest.main()
