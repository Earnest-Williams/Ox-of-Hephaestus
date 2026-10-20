"""Authenticated, ordinary Evennia WebSocket client; no server-side shortcuts.

The wire protocol is Evennia's v1.evennia.com JSON array protocol.
Authentication is via the regular connect/ic commands. A character-issued
nonce challenge proves that a session actually puppets the expected dbref.
This layer does NOT pretend arbitrary command output is an action receipt.
"""

from __future__ import annotations

import asyncio
from collections import deque
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


# Ox inherits Evennia's MAX_CHAR_LIMIT=6000 (settings_default.py).
# The transport's former 1024-character guard rejected world-valid 4096-token
# terminal assessments before Evennia could receive them.
MAX_COMMAND_CHARS = 6000
MAX_BUFFERED_PACKETS = 512


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
        # All reads on this character's socket are serialized. A response
        # waiter preserves unrelated world observations for the next reader.
        self._read_lock = asyncio.Lock()
        self._pending: deque[WebPacket] = deque()

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
        # During cold startup the Portal may accept sockets while the Server
        # is still completing initial setup or an internal reload. Retry ONLY
        # before a character has authenticated or issued a physical command.
        for attempt in range(3):
            self._socket = await connector(
                self.url, subprotocols=["v1.evennia.com"],
                open_timeout=self.timeout, close_timeout=self.timeout,
                max_size=65536,
            )
            try:
                await self._await_login_screen()
                await self._authenticate()
                return
            except (TimeoutError, ConnectionError, IdentityMismatch) as exc:
                await self.close()
                if ("authentication refused" in str(exc).lower()
                        or attempt == 2):
                    raise
                await asyncio.sleep(0.25 * (attempt + 1))
            except BaseException:
                await self.close()
                raise

    async def _await_login_screen(self) -> None:
        # The Portal opens the socket before the Server session can accept
        # commands. An early connect can be silently lost; wait for the normal
        # server-originated login banner instead of racing session setup.
        async with asyncio.timeout(self.timeout):
            for _ in range(64):
                packet = await self.receive()
                if packet.kind == "text" and packet.text:
                    return
        raise ConnectionError("Did not receive Evennia login screen")

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
        # Retain only event names and fixed classifications, not server text;
        # diagnostic messages must never include an echoed password.
        kinds = []
        notices = []
        samples = []
        try:
            async with asyncio.timeout(self.timeout):
                for _ in range(256):
                    packet = await self.receive()
                    kinds.append(packet.kind[:32])
                    message = packet.text.lower()
                    # CI-only synthetic ship troubleshooting; redacted and
                    # capped to prevent credentials in public runner logs.
                    if packet.text and len(samples) < 3:
                        from html import unescape
                        safe = re.sub(r"<[^>]*>", "", unescape(packet.text))
                        safe = safe.replace(self._password, "[REDACTED]")
                        samples.append(re.sub(r"\s+", " ", safe)[:180])
                    if packet.kind == "logged_in":
                        return
                    for needle, code in (
                        ("incorrect", "bad_credentials"),
                        ("login failures", "login_throttle"),
                        ("already connected", "existing_session"),
                        ("invalid", "invalid_command"),
                        ("welcome", "welcome"),
                    ):
                        if needle in message and code not in notices:
                            notices.append(code)
                    if "incorrect" in message or "login failures" in message:
                        raise IdentityMismatch("Account authentication refused: " + ",".join(notices))
        except TimeoutError as exc:
            raise IdentityMismatch(
                "No login acknowledgement; packet kinds="
                + ",".join(kinds[:15]) + " notices=" + ",".join(notices)
                + " server_text=" + repr(samples)
            ) from exc
        raise IdentityMismatch("No authenticated session acknowledgement")

    async def send_line(self, line: str) -> None:
        if self._socket is None:
            raise ConnectionError("Client is disconnected")
        if not line or len(line) > MAX_COMMAND_CHARS or any(ch in line for ch in "\r\n\x00"):
            raise ValueError("Exactly one bounded MUD command is required")
        await self._socket.send(json.dumps(["text", [line], {}]))

    async def _read_wire(self) -> WebPacket:
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

    async def receive(self) -> WebPacket:
        """Take the oldest unclaimed packet, never reading this socket in parallel."""
        async with self._read_lock:
            if self._pending:
                return self._pending.popleft()
            return await self._read_wire()

    async def receive_matching(
        self, predicate: Callable[[WebPacket], bool], *, frame_budget: int = 256,
        include_buffered: bool = True,
    ) -> WebPacket:
        """Await one typed response without consuming unrelated observations.

        A single socket has no independent response channels. Keep unmatched
        packets in wire order for receive() or another typed waiter; never
        accept one work receipt as proof of a different request. Limits are
        explicit and fail closed rather than silently dropping messages.
        Callers must still serialize independent commands on one character.
        """
        if not callable(predicate) or not 1 <= frame_budget <= 1024:
            raise ValueError("A bounded packet matcher is required")
        async with self._read_lock:
            if include_buffered:
                for index, packet in enumerate(self._pending):
                    if predicate(packet):
                        del self._pending[index]
                        return packet
            for _ in range(frame_budget):
                packet = await self._read_wire()
                if predicate(packet):
                    return packet
                if len(self._pending) >= MAX_BUFFERED_PACKETS:
                    raise RuntimeError("Unmatched character packets exceeded bounded buffer")
                self._pending.append(packet)
        raise RuntimeError("World response frame budget exhausted")

    async def expect_text(self, expected: str, *, timeout: float | None = None) -> str:
        if not expected:
            raise ValueError("Expected marker must not be empty")
        samples = []

        def matching(packet: WebPacket) -> bool:
            if expected in packet.text:
                return True
            if packet.text and len(samples) < 3:
                from html import unescape
                safe = re.sub(r"<[^>]*>", "", unescape(packet.text))
                samples.append(re.sub(
                    r"\s+", " ", safe.replace(self._password, "[REDACTED]")
                )[:180])
            return False

        try:
            async with asyncio.timeout(timeout if timeout is not None else self.timeout):
                return (await self.receive_matching(
                    matching, frame_budget=256, include_buffered=False,
                )).text
        except TimeoutError as exc:
            raise TimeoutError("Expected game observation missing: " + repr(samples)) from exc

    async def close(self) -> None:
        socket = self._socket
        self._socket = None
        self._verified = False
        self._pending.clear()
        if socket is not None:
            await socket.close()

    async def __aenter__(self) -> "EvenniaWebSocketClient":
        await self.open()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()
