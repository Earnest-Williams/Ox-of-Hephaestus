"""Offline WebSocket framing and identity-bound client checks."""

import asyncio
import json
import unittest

from ox_ai.ports.evennia.client import EvenniaWebSocketClient, IdentityMismatch


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


if __name__ == "__main__":
    unittest.main()
