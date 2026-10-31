"""Actor-scope ``ox.world.read/1`` over the character's own Evennia socket.

SKETCH. Mirrors ``CapabilityPort``: a fresh nonce per request, a typed matcher
that leaves unrelated frames buffered, and strict validation through the
shared contract. The handler never reads the world database or another
character's page; the world chooses the actor from the authenticated session.
"""

from __future__ import annotations

import asyncio
import secrets
from typing import Final

import orjson
from ox_contracts.world_read_model import ActorWorldPage, parse_world_read_page

from ox_ai.ports.evennia.client import EvenniaWebSocketClient, WebPacket

MAX_FRAME_BYTES: Final[int] = 1_048_576
MAX_PAGES: Final[int] = 16
ENVELOPE_KEYS: Final[frozenset[str]] = frozenset({"nonce", "status", "page"})


class StaleWorldCursor(RuntimeError):
    """The world moved on mid-series; restart from page 1."""


def _raw(packet: WebPacket) -> str | None:
    if len(packet.args) == 1 and isinstance(packet.args[0], str):
        return packet.args[0]
    payload: object = packet.options.get("payload")
    return payload if not packet.args and isinstance(payload, str) else None


def parse_envelope(raw: str, *, nonce: str, actor_dbref: str) -> ActorWorldPage | None:
    """Return the page, None for a stale cursor, or raise on anything else."""
    if len(raw) > MAX_FRAME_BYTES:
        raise ValueError("Oversized world-read frame")
    envelope: object = orjson.loads(raw)
    if not isinstance(envelope, dict) or set(envelope) != ENVELOPE_KEYS:
        raise ValueError("Malformed world-read envelope")
    if envelope["nonce"] != nonce:
        raise PermissionError("World-read reply is not for this challenge")
    status: object = envelope["status"]
    if status == "stale_cursor":
        return None
    if status != "ok":
        raise RuntimeError("World read unavailable: " + str(status))
    page = parse_world_read_page(envelope["page"])
    if not isinstance(page, ActorWorldPage):
        raise PermissionError("Actor socket received a developer projection")
    if page.character_id != actor_dbref:
        raise PermissionError("World-read page belongs to another character")
    return page


class WorldReadPort:
    def __init__(
        self, client: EvenniaWebSocketClient, *, timeout: float = 10.0
    ) -> None:
        if not 0 < timeout <= 60:
            raise ValueError("World-read timeout must be bounded")
        self.client: EvenniaWebSocketClient = client
        self.timeout: float = timeout

    async def read_page(self, cursor: str | None) -> ActorWorldPage | None:
        if not self.client.authenticated:
            raise PermissionError("World read requires authenticated puppeting")
        nonce: str = secrets.token_hex(16)
        command: str = "oxworldread " + nonce
        if cursor is not None:
            command = command + " " + cursor
        await self.client.send_line(command)

        def matches(packet: WebPacket) -> bool:
            if packet.kind != "ox_world_read":
                return False
            raw: str | None = _raw(packet)
            # Claim malformed frames so they are rejected, not buffered forever.
            return raw is None or nonce in raw[:256]

        try:
            async with asyncio.timeout(self.timeout):
                packet: WebPacket = await self.client.receive_matching(
                    matches, frame_budget=256
                )
        except TimeoutError:
            raise TimeoutError("No world-read response") from None
        raw: str | None = _raw(packet)
        if raw is None:
            raise ValueError("Malformed world-read OOB frame")
        actor: str = str(self.client.character_dbref)
        return parse_envelope(raw, nonce=nonce, actor_dbref=actor)

    async def read_series(self) -> tuple[ActorWorldPage, ...]:
        """All pages of one publication, or StaleWorldCursor to retry."""
        pages: list[ActorWorldPage] = []
        cursor: str | None = None
        for _ in range(MAX_PAGES):
            page: ActorWorldPage | None = await self.read_page(cursor)
            if page is None:
                raise StaleWorldCursor("World advanced during a paged read")
            if pages and (
                page.world_id != pages[0].world_id
                or page.publication_seq != pages[0].publication_seq
                or page.models != pages[0].models
            ):
                raise StaleWorldCursor("Pages from different publications")
            pages.append(page)
            if page.page.complete:
                return tuple(pages)
            cursor = page.page.next_cursor
        raise RuntimeError("World-read series exceeded its page budget")
