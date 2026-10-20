"""Nonce-verified, actor-bound read of authoritative Evennia game seconds.

No local wall clock is accepted as a substitute; this port reads ONLY the
current authenticated puppet's ordinary read-only oxclock command.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import math
import re
import secrets

from ox_ai.ports.evennia.client import EvenniaWebSocketClient


@dataclass(frozen=True, slots=True)
class WorldClockSample:
    actor_dbref: str
    game_seconds: float

    @classmethod
    def parse(cls, data, *, actor_dbref: str, nonce: str) -> "WorldClockSample":
        if not (isinstance(nonce, str)
                and re.fullmatch(r"[0-9a-f]{32}", nonce)):
            raise ValueError("Invalid clock query nonce")
        if not isinstance(data, dict) or set(data) != {
                "version", "nonce", "actor_dbref", "game_seconds"}:
            raise ValueError("Malformed authoritative clock response")
        if type(data["version"]) is not int or data["version"] != 1:
            raise ValueError("Unknown world clock protocol version")
        if data["nonce"] != nonce:
            raise PermissionError("Clock response was not solicited by this actor")
        if data["actor_dbref"] != actor_dbref:
            raise PermissionError("Clock response belongs to another character")
        raw = data["game_seconds"]
        if (isinstance(raw, bool) or not isinstance(raw, (int, float))
                or not math.isfinite(raw) or raw < 0):
            raise ValueError("Invalid authoritative game timestamp")
        return cls(actor_dbref, float(raw))


class WorldClockPort:
    """Read time from the authenticated Evennia character, not the handler."""

    def __init__(self, client: EvenniaWebSocketClient, *, timeout: float = 10.0):
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or (
                not math.isfinite(timeout) or not 0 < timeout <= 60):
            raise ValueError("World clock read timeout must be bounded")
        self.client = client
        self.timeout = float(timeout)

    async def observe(self) -> WorldClockSample:
        if not self.client.authenticated:
            raise PermissionError("Game clock requires authenticated puppeting")
        nonce = secrets.token_hex(16)
        await self.client.send_line("oxclock " + nonce)

        def matching(packet):
            if packet.kind != "ox_clock":
                return False
            if len(packet.args) == 1 and isinstance(packet.args[0], str):
                raw = packet.args[0]
            elif not packet.args and isinstance(packet.options.get("payload"), str):
                raw = packet.options["payload"]
            else:
                return True  # malformed world reply: fail during parse
            if len(raw) > 1024:
                return True
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                return True
            return not (isinstance(data, dict)
                        and isinstance(data.get("nonce"), str)
                        and data["nonce"] != nonce)

        try:
            async with asyncio.timeout(self.timeout):
                packet = await self.client.receive_matching(
                    matching, frame_budget=256)
        except TimeoutError:
            raise TimeoutError("No authenticated world clock readout") from None
        if len(packet.args) == 1 and isinstance(packet.args[0], str):
            raw = packet.args[0]
        elif not packet.args and isinstance(packet.options.get("payload"), str):
            raw = packet.options["payload"]
        else:
            raise ValueError("Malformed world clock packet")
        if len(raw) > 1024:
            raise ValueError("Oversized world clock response")
        return WorldClockSample.parse(
            json.loads(raw),
            actor_dbref=self.client.character_dbref, nonce=nonce,
        )
