"""Account-only first-watch commands for the bodiless lead mind.

These commands set a passive predicate on *future network deliveries*.
They cannot advance time, operate a hatch or query global world history.
"""
from __future__ import annotations

import json
import re
from evennia.commands.command import Command
from world.ship_mind_watch import ShipWatchError
from world.ship_network_access import NetworkAccessError


def _valid_nonce(value):
    return re.fullmatch(r"[0-9a-f]{32}", value) is not None


class CmdOxWatch(Command):
    key = "oxwatch"
    locks = "cmd:all()"

    def func(self):
        tokens = self.args.strip().split()
        if (len(tokens) != 2 or not _valid_nonce(tokens[0])
                or tokens[1] not in {"open", "closed"}):
            self.caller.msg("Usage: oxwatch <32-hex-request-id> <open|closed>")
            return
        from world.ship_mind_watch_world import arm_first_watch
        try:
            reply = arm_first_watch(self.caller, tokens[0], tokens[1])
        except (ShipWatchError, NetworkAccessError, PermissionError, ValueError):
            self.caller.msg("First ship watch unavailable or refused.")
            return
        self.caller.msg(ox_watch=([json.dumps(reply, sort_keys=True)], {}))


class CmdOxWatchCancel(Command):
    key = "oxwatchcancel"
    locks = "cmd:all()"

    def func(self):
        token = self.args.strip()
        if not _valid_nonce(token):
            self.caller.msg("Usage: oxwatchcancel <32-hex-request-id>")
            return
        from world.ship_mind_watch_world import cancel_first_watch
        try:
            reply = cancel_first_watch(self.caller, token)
        except (ShipWatchError, NetworkAccessError, PermissionError, ValueError):
            self.caller.msg("First ship watch cancellation refused.")
            return
        self.caller.msg(ox_watch_cancel=([json.dumps(reply, sort_keys=True)], {}))


class CmdOxWatchStatus(Command):
    key = "oxwatchstatus"
    locks = "cmd:all()"

    def func(self):
        if self.args.strip():
            self.caller.msg("Usage: oxwatchstatus")
            return
        from world.ship_mind_watch_world import first_watch_status
        try:
            reply = first_watch_status(self.caller)
        except (ShipWatchError, NetworkAccessError, PermissionError, ValueError):
            self.caller.msg("First ship watch status unavailable.")
            return
        self.caller.msg(ox_watch_status=([json.dumps(reply, sort_keys=True)], {}))
