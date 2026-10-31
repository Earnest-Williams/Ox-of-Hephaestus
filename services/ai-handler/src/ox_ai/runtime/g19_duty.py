"""One G19 engineering duty step: attend a real panel, then learn from it.

SKETCH (ROADMAP Priority 2, steps 1 and 3). The step is ordinary character
behaviour: the engineer must already stand in the panel's room (reached by
GOAP over world-advertised exits), issues the same ``oxplantread panel:ID``
a player would, then reads back its own journaled evidence through
``oxworldread``. The plain-text readout is never parsed into beliefs: only
the authenticated journal row, projected by the world, becomes evidence.

Known blockers before this runs on the installed ship:

- ``CapabilitySnapshot.parse`` rejects rooms with more than 16 exits; the
  four HAB arc corridors have 20.
- ``FixtureCapability`` admits only pump/cargo/scrubber targets, so G19
  panels are not advertised as capabilities yet.
- The world must journal panel reads (``world/ship_panel_journal.py``).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Final

from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.ports.evennia.world_read import StaleWorldCursor, WorldReadPort
from ox_ai.runtime.g19_beliefs import EpistemicLedger, IngestReport, ingest_actor_pages

PANEL_REPLY_MARKER: Final[str] = (
    '"scope": "physically_attended_original_local_panel_only"'
)
MAX_SERIES_RETRIES: Final[int] = 2


@dataclass(frozen=True, slots=True)
class PanelDuty:
    """An authored duty: which panel, in which room. Not a belief."""

    panel_id: str
    room_id: str


async def attend_panel(
    client: EvenniaWebSocketClient,
    ledger: EpistemicLedger,
    duty: PanelDuty,
    *,
    timeout: float = 12.0,
) -> IngestReport:
    await client.send_line("oxplantread panel:" + duty.panel_id)
    # The readout text only confirms the command ran; refusals come back as
    # plain text and leave no journal row, so nothing is learned from them.
    await client.expect_text(PANEL_REPLY_MARKER, timeout=timeout)
    port: WorldReadPort = WorldReadPort(client, timeout=timeout)
    for attempt in range(MAX_SERIES_RETRIES + 1):
        try:
            pages = await port.read_series()
        except StaleWorldCursor:
            if attempt == MAX_SERIES_RETRIES:
                raise
            await asyncio.sleep(0)
            continue
        return ingest_actor_pages(ledger, pages)
    raise RuntimeError("unreachable")
