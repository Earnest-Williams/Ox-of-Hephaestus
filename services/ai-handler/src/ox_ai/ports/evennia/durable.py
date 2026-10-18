"""Authoritative per-character operation receipts over normal Evennia sockets."""
from __future__ import annotations

import asyncio
import re

from ox_ai.ports.base import ActionOutcome, ActionRequest
from ox_ai.ports.evennia.client import EvenniaWebSocketClient

_VERBS = {
    ("isolate_pump", "pump"): "isolate",
    ("repair_pump", "pump"): "repair",
    ("commission_pump", "pump"): "commission",
    ("restow_cargo", "cargo"): "restow",
    ("certify_cargo", "cargo"): "certify",
    ("isolate_scrubber", "scrubber"): "isolate",
    ("replace_scrubber", "scrubber"): "replace",
    ("restart_scrubber", "scrubber"): "restart",
}


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
                    if len(packet.args) == 1 and isinstance(packet.args[0], dict):
                        entry = packet.args[0]
                    elif not packet.args and "request_id" in packet.options:
                        # Some Evennia versions normalize a singleton dict
                        # into OOB kwargs rather than positional args.
                        entry = packet.options
                    else:
                        raise ValueError("Malformed authenticated world receipt")
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
        if request.arguments:
            raise ValueError("Equipment actions do not take free-form arguments")
        op = _VERBS.get((request.verb, request.target))
        if op is None or re.fullmatch(r"[0-9a-f]{32}", request.request_id) is None:
            raise ValueError("Unknown typed operation or request ID")
        suffix = "" if request.target == "pump" else " " + request.target
        await self.client.send_line(f"oxaction {request.request_id} {op}{suffix}")
        return await self._receipt(request.request_id)

    async def reconcile(self, request_id: str, *, target: str = "pump") -> ActionOutcome:
        if not self.client.authenticated:
            raise PermissionError("Unauthenticated session")
        if re.fullmatch(r"[0-9a-f]{32}", request_id) is None:
            raise ValueError("Invalid request ID")
        if target not in ("pump", "cargo", "scrubber"):
            raise ValueError("Unknown equipment receipt namespace")
        suffix = "" if target == "pump" else " " + target
        await self.client.send_line(f"oxreceipt {request_id}{suffix}")
        return await self._receipt(request_id)


    async def submit_work(self, request: ActionRequest) -> ActionOutcome:
        """Submit one typed world-work intent using the global receipt ID.

        Caller must persist the same request ID before invoking this method.
        Keep the historic submit() path until all legacy supervisors migrate.
        """
        if not self.client.authenticated:
            raise PermissionError("Unauthenticated session")
        if request.character_id != self.client.character_dbref:
            raise PermissionError("Work belongs to another character")
        if re.fullmatch(r"[0-9a-f]{32}", request.request_id) is None:
            raise ValueError("Invalid work request ID")

        if request.target == "ship":
            if request.verb not in (
                "radio", "request", "approve", "resolve", "offer",
                "accept", "answer",
            ):
                raise ValueError("Unsupported shipboard operation")
            operation = request.verb
            if operation == "answer":
                arguments = dict(request.arguments)
                hail_id = arguments.get("hail_id")
                mode = arguments.get("mode")
                if (set(arguments) != {"hail_id", "mode"}
                        or not isinstance(hail_id, str)
                        or re.fullmatch(r"hail-[0-9]{4,}", hail_id) is None
                        or mode not in ("status", "ack", "decline")):
                    raise ValueError("Invalid typed hail answer")
                suffix = f" {hail_id} {mode}"
            else:
                if request.arguments:
                    raise ValueError("Ship work does not permit free-form arguments")
                suffix = ""
        elif request.target == "inventory":
            operation = request.verb
            if operation == "request_supply":
                if request.arguments:
                    raise ValueError("Supply request takes no freeform arguments")
                suffix = ""
            elif operation in ("accept_supply", "collect_supply", "deliver_supply"):
                args = dict(request.arguments)
                order_id = args.get("order_id")
                if (set(args) != {"order_id"} or not isinstance(order_id, str)
                        or re.fullmatch(r"[0-9a-f]{32}", order_id) is None):
                    raise ValueError("Supply work requires one typed world order ID")
                suffix = " " + order_id
            else:
                raise ValueError("Unsupported inventory operation")
        else:
            operation = _VERBS.get((request.verb, request.target))
            if operation is None or request.arguments:
                raise ValueError("Unsupported typed equipment work")
            suffix = ""

        await self.client.send_line(
            f"oxwork {request.request_id} {operation} {request.target}{suffix}"
        )
        return await self._receipt(request.request_id)

    async def reconcile_work(self, request_id: str) -> ActionOutcome:
        """Check global world receipt; never retransmit an unknown operation."""
        if not self.client.authenticated:
            raise PermissionError("Unauthenticated session")
        if re.fullmatch(r"[0-9a-f]{32}", request_id) is None:
            raise ValueError("Invalid work request ID")
        await self.client.send_line(f"oxworkreceipt {request_id}")
        return await self._receipt(request_id)
