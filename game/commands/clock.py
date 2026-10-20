"""Authenticated character command for reading Evennia's game clock.

The caller can observe the world's public simulated time but cannot advance
it, change the watch roster, or obtain any private character/world state.
"""
from __future__ import annotations

import json
import math
import re

from evennia.commands.command import Command
from evennia.utils import gametime


class CmdOxClock(Command):
    """Read world-authoritative simulated seconds for this character.

    Usage: oxclock <32 hex nonce>
    Replies on the existing character WebSocket with one ox_clock OOB packet.
    """

    key = "oxclock"
    locks = "cmd:all()"

    def func(self) -> None:
        nonce = self.args.strip()
        if re.fullmatch(r"[0-9a-f]{32}", nonce) is None:
            self.caller.msg("Usage: oxclock <32 lowercase hex nonce>")
            return
        seconds = float(gametime.gametime(absolute=True))
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Invalid authoritative game clock")
        payload = {
            "version": 1,
            "nonce": nonce,
            "actor_dbref": self.caller.dbref,
            "game_seconds": seconds,
        }
        self.caller.msg(ox_clock=([json.dumps(payload, sort_keys=True)], {}))
