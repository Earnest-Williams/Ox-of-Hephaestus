"""Authoritative per-character operation receipts over normal Evennia sockets."""
from __future__ import annotations

import asyncio
import re

from ox_ai.ports.base import ActionOutcome, ActionRequest
from ox_ai.ports.evennia.client import EvenniaWebSocketClient

_VERBS = {"isolate_pump": "isolate", "repair_pump": "repair",
          "commission_pump": "commission"}


class DurableEvenniaPort:
    """Never confuse chat text or command delivery with a verified transition."""

    def __init__(self, client: EvenniaWebSocketClient, *, timeout: float = 10.0):
        self.client = client
        self.timeout = timeout

    async def _receipt(self, request_id: str) -> ActionOutcome:
        try:
            async with asyncio.timeout(self.timeout):
                for _ in range(128):
                    packet = await self.client.receive()
                    if packet.kind != "ox_receipt":
                        continue
                    if len(packet.args) != 1 or not isinstance(packet.args[0], dict):
                        raise ValueError("Malformed authenticated world receipt")
                    entry = packet.args[0]
                    if entry.get("request_id") != request_id:
                        raise ValueError("Unexpected world request ID")
                    if entry.get("actor_dbref") != self.client.character_dbref:
                        raise PermissionError("Receipt addressed to a different character")
                    status = entry.get("status")
                    if status not in ("succeeded", "failed", "unknown"):
                        raise ValueError("Invalid authoritative receipt status")
                    return ActionOutcome(request_id, status,
                                         str(entry.get("reason", "")),
                                         entry.get("source_event_id"))
        except TimeoutError:
            return ActionOutcome(request_id, "unknown", "No authoritative receipt")
        raise RuntimeError("World response budget exhausted")

    async def submit(self, request: ActionRequest) -> ActionOutcome:
        if not self.client.authenticated:
            raise PermissionError("Unauthenticated session")
        if request.character_id != self.client.character_dbref:
            raise PermissionError("Action addressed to another character")
        if request.target != "pump" or request.arguments:
            raise ValueError("Unsupported request or arguments")
        op = _VERBS.get(request.verb)
        if op is None or re.fullmatch(r"[0-9a-f]{32}", request.request_id) is None:
            raise ValueError("Unknown operation or request ID")
        await self.client.send_line(f"oxaction {request.request_id} {op}")
        return await self._receipt(request.request_id)

    async def reconcile(self, request_id: str) -> ActionOutcome:
        if not self.client.authenticated:
            raise PermissionError("Unauthenticated session")
        if re.fullmatch(r"[0-9a-f]{32}", request_id) is None:
            raise ValueError("Invalid request ID")
        await self.client.send_line(f"oxreceipt {request_id}")
        return await self._receipt(request_id)
