"""Real Evennia WebSocket acceptance for recipient-scoped exact event proofs.

The world fixture and account passwords are provisioned by CI, not by this
external client. Neither session has an operator view or database access.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.ports.evennia.evidence import WorldEventPort
from ox_ai.ports.evennia.journal import WorldJournalPort

URL = "ws://127.0.0.1:4002"


async def run() -> None:
    ids = json.loads(Path(".ox-state/p3a-ids.json").read_text(encoding="utf-8"))
    proofs = json.loads(
        Path(".ox-state/p4f-event-ids.json").read_text(encoding="utf-8")
    )
    password = os.environ["OX_PROBE_PASSWORD"]

    async with EvenniaWebSocketClient(
        URL, "OxBotLin", password, ids["lin"], timeout=15,
    ) as lin:
        source = await WorldEventPort(lin).lookup(proofs["lin"])
        item = source.require(kind="world_exact_trial")
        assert item["recipient_dbref"] == ids["lin"]
        assert item["data"]["case_id"] == "lin-private"
        certificate = await WorldJournalPort(lin).attest(item["sequence"])
        assert certificate.prefix_digest is not None
        assert certificate.head_cursor >= item["sequence"]
        foreign_prefix = await WorldJournalPort(lin).attest(
            int(proofs["ari"].split("-")[-1])
        )
        assert foreign_prefix.prefix_digest is None
        hidden = await WorldEventPort(lin).lookup(proofs["ari"])
        assert hidden.status == "missing" and hidden.event is None
        unknown = await WorldEventPort(lin).lookup("oxevt-v2-999999999999")
        assert unknown.status == hidden.status and unknown.event is None

    async with EvenniaWebSocketClient(
        URL, "OxBotAri", password, ids["ari"], timeout=15,
    ) as ari:
        own = await WorldEventPort(ari).lookup(proofs["ari"])
        assert own.require(kind="world_exact_trial")["data"]["case_id"] == "ari-private"
        ari_certificate = await WorldJournalPort(ari).attest(
            own.event["sequence"]
        )
        assert ari_certificate.prefix_digest is not None
        assert ari_certificate.generation == certificate.generation
        denied = await WorldEventPort(ari).lookup(proofs["lin"])
        assert denied.status == "missing" and denied.event is None

    # Re-establish a fresh normal session and nonce to prove that the event
    # identity is stable across connection loss, not a one-session cache.
    async with EvenniaWebSocketClient(
        URL, "OxBotLin", password, ids["lin"], timeout=15,
    ) as lin_again:
        restored = await WorldEventPort(lin_again).lookup(proofs["lin"])
        assert restored.require(kind="world_exact_trial") == item
        restart_certificate = await WorldJournalPort(lin_again).attest(
            item["sequence"],
        )
        assert restart_certificate.generation == certificate.generation
        assert restart_certificate.prefix_digest == certificate.prefix_digest
        assert restart_certificate.requested_cursor == certificate.requested_cursor
    print("OX_P4F_AUTHENTICATED_EXACT_EVENT_RESTART_AND_PRIVACY_PASS")


if __name__ == "__main__":
    asyncio.run(run())
