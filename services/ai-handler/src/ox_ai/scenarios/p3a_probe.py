"""Real-server P3a smoke test, run in a separate OS process from Evennia."""

import asyncio
import json
import os
from pathlib import Path

from ox_ai.ports.evennia.client import EvenniaWebSocketClient, IdentityMismatch


async def read_only(client, line: str, expected: str) -> str:
    # Look/inspect are safe to repeat after a Server startup reload; do not
    # apply this policy to speech, repairs, valves or other side effects.
    for attempt in range(3):
        await client.send_line(line)
        try:
            return await client.expect_text(expected, timeout=6)
        except TimeoutError:
            if attempt == 2:
                raise
    raise RuntimeError("Read-only observation unavailable")


async def main() -> None:
    crew = json.loads(Path(".ox-state/p3a-ids.json").read_text())
    password = os.environ["OX_PROBE_PASSWORD"]
    url = "ws://127.0.0.1:4002"
    async with EvenniaWebSocketClient(
        url, "OxBotAri", password, crew["ari"], timeout=15,
    ) as ari:
        await read_only(ari, "look", "Engineering")
        await read_only(ari, "inspect pump", "Cooling Pump P-01")
        await ari.send_line("say reporting for engineering watch")
        await ari.expect_text("reporting for engineering watch")
    async with EvenniaWebSocketClient(
        url, "OxBotLin", password, crew["lin"], timeout=15,
    ) as lin:
        await read_only(lin, "look", "Bridge")
        await read_only(lin, "inspect console", "BRIDGE COOLING TELEMETRY")

    # A correct account but the wrong character must never be accepted.
    try:
        async with EvenniaWebSocketClient(
            url, "OxBotLin", password, crew["ari"], timeout=2,
        ):
            raise AssertionError("Lin took control of Ari without authorisation")
    except IdentityMismatch:
        pass
    print("OX_P3A_LIVE_EXTERNAL_WEBSOCKET_PASS")


if __name__ == "__main__":
    asyncio.run(main())
