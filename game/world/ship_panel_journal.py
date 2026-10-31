"""Journal an attended G19 panel read as an addressed world event.

SKETCH. Today ``oxplantread panel:ID`` replies with plain ``msg`` text, so the
reading never reaches the authenticated journal and the handler cannot prove
it later. This makes the read durable evidence for the reader only.

Wire-in (``continuous_ship_physics.local_physics_readout``, panel branch)::

    readout = panel_readout(ledger, panel, now_s=clock.details["last_game_time"])
    journal_panel_reading(actor, readout)
    return readout

The panel's own ``last_good_s`` is the sample time; the journal row's
``game_time`` is the read time. The actor projection derives freshness from
the sample time, so an old panel cannot look fresh because it was read now.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Final

from world.event_journal import emit

PANEL_READING_KIND: Final[str] = "panel_reading"


def panel_reading_details(readout: Mapping[str, Any]) -> dict[str, object]:
    """Flat scalar details; metrics carry a ``metric_`` prefix."""
    measurements: object = readout.get("measurements")
    details: dict[str, object] = {
        "panel": str(readout["panel"]),
        "room": str(readout["room"]),
        "zone": readout.get("zone"),
        "status": str(readout["status"]),
        "sampled_game_s": readout.get("last_good_s"),
        "active_alarm_count": len(readout.get("active_alarms") or {}),
    }
    if isinstance(measurements, Mapping):
        for name, value in measurements.items():
            if (
                isinstance(name, str)
                and name.isidentifier()
                and type(value) in (int, float)
                and math.isfinite(float(value))
            ):
                details["metric_" + name] = float(value)
    return details


def journal_panel_reading(actor: Any, readout: Mapping[str, Any]) -> dict[str, Any]:
    details: dict[str, object] = panel_reading_details(readout)
    text: str = "Local panel " + str(details["panel"]) + ": " + str(details["status"])
    event: dict[str, Any] = emit(
        None, actor, PANEL_READING_KIND, data=details, text=text
    )
    return event
