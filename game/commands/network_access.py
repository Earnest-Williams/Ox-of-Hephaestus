"""Authenticated *out-of-character* network access for the bodiless ship mind.

No character cmdset contains these commands. A client has no way to choose
its principal, world scope, sensor set, source event IDs, or hidden cursor.
"""

from __future__ import annotations

import json
import re

from evennia.commands.command import Command
from world.ship_network_access import NetworkAccessError


class CmdOxNetAccess(Command):
    """Read the next acknowledged page of physically delivered access data."""

    key = "oxnet"
    locks = "cmd:all()"

    def func(self):
        if self.args.strip():
            self.caller.msg("Usage: oxnet")
            return
        from world.ship_network_access_world import access_page
        try:
            answer = access_page(self.caller)
        except (NetworkAccessError, PermissionError, ValueError):
            self.caller.msg("Network access unavailable to this account.")
            return
        self.caller.msg(
            ox_network_access=([json.dumps(answer, sort_keys=True)], {}),
        )


class CmdOxNetAck(Command):
    """Acknowledge an opaque, previously issued network access page."""

    key = "oxack"
    locks = "cmd:all()"

    def func(self):
        token = self.args.strip()
        if re.fullmatch(r"v1\.[0-9a-f]{1,16}\.[0-9a-f]{64}", token) is None:
            self.caller.msg("Usage: oxack <opaque receipt token>")
            return
        from world.ship_network_access_world import acknowledge_page
        try:
            result = acknowledge_page(self.caller, token)
        except (NetworkAccessError, PermissionError, ValueError):
            self.caller.msg("Network acknowledgement refused.")
            return
        self.caller.msg(
            ox_network_ack=([json.dumps(result, sort_keys=True)], {}),
        )
