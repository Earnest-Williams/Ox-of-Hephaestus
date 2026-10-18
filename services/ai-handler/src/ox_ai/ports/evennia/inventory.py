"""Character-scoped local physical stock observations over authenticated sockets.

Remote stock not locally observed is None (unknown), never zero. A work
order message is not a local stock observation, and an agent may not pass
its own actor/room identity to the game.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import math
import re
import secrets


_REF = re.compile(r"#[1-9][0-9]*")
_ITEM = re.compile(r"oxitem-[0-9a-f]{32}")


@dataclass(frozen=True)
class InventoryObservation:
    actor_dbref: str
    room_dbref: str | None
    local_cartridges: int | None
    game_time: float
    carried_items: tuple[str, ...]

    @classmethod
    def parse(cls, raw, *, actor_dbref: str, nonce: str):
        if not isinstance(raw, dict) or set(raw) != {
            "version", "nonce", "actor_dbref", "room_dbref",
            "local_cartridges", "carried", "game_time"
        } or type(raw["version"]) is not int or raw["version"] != 1:
            raise ValueError("Invalid world inventory observation protocol")
        if (not isinstance(actor_dbref, str) or not _REF.fullmatch(actor_dbref)
                or raw["actor_dbref"] != actor_dbref
                or raw["nonce"] != nonce
                or not isinstance(nonce, str)
                or not re.fullmatch(r"[0-9a-f]{32}", nonce)):
            raise PermissionError("Inventory response does not belong to this session")
        room = raw["room_dbref"]
        if room is not None and (not isinstance(room, str) or not _REF.fullmatch(room)):
            raise ValueError("Invalid room evidence")
        count = raw["local_cartridges"]
        if count is not None and (
            type(count) is not int or not 0 <= count <= 1000000 or room is None
        ):
            raise ValueError("Missing/unobservable stock cannot be asserted zero")
        game_time = raw["game_time"]
        if (type(game_time) not in (int, float)
                or not math.isfinite(game_time) or game_time < 0):
            raise ValueError("Inventory evidence has no valid world timestamp")
        carried = raw["carried"]
        if (not isinstance(carried, list) or len(carried) > 16
                or any(not isinstance(x, str) or not _ITEM.fullmatch(x) for x in carried)
                or len(set(carried)) != len(carried)):
            raise ValueError("Invalid self-carried inventory")
        return cls(actor_dbref, room, count, float(game_time), tuple(carried))


class InventoryPort:
    def __init__(self, client, *, timeout: float = 12):
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            raise ValueError("Bounded world observation timeout required")
        self.client = client
        self.timeout = float(timeout)

    async def observe(self) -> InventoryObservation:
        if not self.client.authenticated:
            raise PermissionError("Physical inventory requires authenticated character")
        nonce = secrets.token_hex(16)
        await self.client.send_line("oxinventory " + nonce)
        try:
            async with asyncio.timeout(self.timeout):
                for _ in range(256):
                    packet = await self.client.receive()
                    if packet.kind != "ox_inventory":
                        continue
                    if len(packet.args) != 1 or not isinstance(packet.args[0], str):
                        raise ValueError("Malformed inventory OOB")
                    raw = packet.args[0]
                    if len(raw) > 16384:
                        raise ValueError("Oversized inventory OOB")
                    return InventoryObservation.parse(
                        json.loads(raw),
                        actor_dbref=self.client.character_dbref, nonce=nonce,
                    )
        except TimeoutError:
            raise TimeoutError("No authenticated inventory response") from None
        raise RuntimeError("Inventory world response budget exhausted")
