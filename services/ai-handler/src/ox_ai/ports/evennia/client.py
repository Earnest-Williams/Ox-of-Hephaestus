"""Authenticated, ordinary Evennia WebSocket client; no server-side shortcuts.

The wire protocol is Evennia's v1.evennia.com JSON array protocol.
Authentication is via the regular connect/ic commands. A character-issued
nonce challenge proves that a session actually puppets the expected dbref.
This layer does NOT pretend arbitrary command output is an action receipt.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import re
import secrets
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class WebPacket:
    kind: str
    args: tuple[Any, ...]
    options: dict[str, Any]

    @property
    def text(self) -> str:
        if self.kind not in {"text", "prompt"}:
            return ""
        return str(self.args[0]) if self.args else ""


class IdentityMismatch(PermissionError):
    """The server never proved ownership of the requested character."""


class EvenniaWebSocketClient:
    """One authenticated ordinary client session bound to one character.

    The caller supplies credentials for a *non-privileged* account that owns
    the character. No server API, omniscient state or account impersonation.
    WebSocket support is installed through the optional 'transport' extra.
    """

    def __init__(
        self, url: str, username: str, password: str, character_dbref: str,
        *, timeout: float = 12.0, connector: Callable[..., Any] | None = None,
    ) -> None:
        if not (url.startswith("ws://") or url.startswith("wss://")):
            raise ValueError("Evennia requires ws:// or wss://")
        if url.startswith("ws://") and not re.match(
            r"^ws://(?:127\.0\.0\.1|localhost|\[::1\])(?::\d+)?(?:/|$)", url
        ):
            raise ValueError("Unencrypted WebSocket credentials require loopback")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,39}", username):
            raise ValueError("Use a simple dedicated bot account name")
        if not re.fullmatch(r"[A-Za-z0-9_-]{12,128}", password):
            raise ValueError("Use a random single-token account password")
        if not re.fullmatch(r"#[1-9][0-9]*", character_dbref):
            raise ValueError("Expected a persisted Evennia character dbref")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.url = url
        self.username = username
        self._password = password
        self.character_dbref = character_dbref
        self.timeout = timeout
        self._connector = connector
        self._socket = None
        self._verified = False

    @property
    def authenticated(self) -> bool:
        return self._verified

    async def open(self) -> None:
        if self._socket is not None:
            raise RuntimeError("Client already connected")
        connector = self._connector
        if connector is None:
            from websockets.asyncio.client import connect
            connector = connect
        self._socket = await connector(
            self.url, subprotocols=["v1.evennia.com"],
            open_timeout=self.timeout, close_timeout=self.timeout,
            max_size=65536,
        )
        try:
            await self._authenticate()
        except BaseException:
            await self.close()
            raise

    async def _authenticate(self) -> None:
        challenge = secrets.token_hex(16)
        # All three commands traverse the normal inputfunc command parser.
        # Ordering on one WebSocket is preserved. An incorrect password,
        # unauthorized puppet or stale session cannot answer the challenge.
        await self.send_line("connect " + self.username + " " + self._password)
        # Login is asynchronous in Evennia's Portal/Server bridge. Sending
        # puppet commands before the logged_in OOB acknowledgement races
        # the authenticated session transition (particularly for account 2).
        await self._await_login()
        await self.send_line("ic " + self.character_dbref)
        await self.send_line("oxidentity " + challenge)
        marker = "OX_IDENTITY " + challenge + " " + self.character_dbref
        try:
            await self.expect_text(marker, timeout=self.timeout)
        except (TimeoutError, ConnectionError, RuntimeError) as exc:
            raise IdentityMismatch("Character identity challenge failed") from exc
        self._verified = True

    async def _await_login(self) -> None:
        try:
            async with asyncio.timeout(self.timeout):
                for _ in range(256):
                    packet = await self.receive()
                    if packet.kind == "logged_in":
                        return
                    if "incorrect" in packet.text.lower() or "login failures" in packet.text.lower():
                        raise IdentityMismatch("Account authentication refused")
        except TimeoutError as exc:
            raise IdentityMismatch("Timed out before authenticated session acknowledgement") from exc
        raise IdentityMismatch("No authenticated session acknowledgement")

    async def send_line(self, line: str) -> None:
        if self._socket is None:
            raise ConnectionError("Client is disconnected")
        if not line or len(line) > 1024 or any(ch in line for ch in "\r\n\x00"):
            raise ValueError("Exactly one bounded MUD command is required")
        await self._socket.send(json.dumps(["text", [line], {}]))

    async def receive(self) -> WebPacket:
        if self._socket is None:
            raise ConnectionError("Client is disconnected")
        raw = await self._socket.recv()
        data = json.loads(raw)
        if (not isinstance(data, list) or len(data) != 3
                or not isinstance(data[0], str)
                or not isinstance(data[1], list)
                or not isinstance(data[2], dict)):
            raise ValueError("Unexpected Evennia WebSocket frame")
        return WebPacket(data[0], tuple(data[1]), data[2])

    async def expect_text(self, expected: str, *, timeout: float | None = None) -> str:
        if not expected:
            raise ValueError("Expected marker must not be empty")
        # Preserve the total deadline over an arbitrary number of frames.
        async with asyncio.timeout(timeout if timeout is not None else self.timeout):
            for _ in range(256):
                packet = await self.receive()
                if expected in packet.text:
                    return packet.text
        raise RuntimeError("Expected character output not observed")

    async def close(self) -> None:
        socket = self._socket
        self._socket = None
        self._verified = False
        if socket is not None:
            await socket.close()

    async def __aenter__(self) -> "EvenniaWebSocketClient":
        await self.open()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()
