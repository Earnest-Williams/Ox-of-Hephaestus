"""Read-only typed capability discovery for an ordinary authenticated character."""
from __future__ import annotations

import json
from evennia.commands.command import Command
from world.capabilities import local_capabilities


class CmdOxCapabilities(Command):
    """Return this character's local exits and currently eligible equipment actions.

    Usage:
      oxcapabilities <32-lowercase-hex-request-nonce>

    OOB protocol ox_capabilities: one JSON-encoded snapshot. Never accepts a
    requested actor or room; the game's session chooses the actual caller.
    """

    key = "oxcapabilities"
    locks = "cmd:all()"

    def func(self) -> None:
        try:
            snapshot = local_capabilities(self.caller, self.args.strip())
        except (ValueError, PermissionError):
            self.caller.msg("Usage: oxcapabilities <32 lowercase hex nonce>")
            return
        # JSON string avoids Evennia variants reshaping nested dicts into
        # OOB kwargs. The response is not a source of authority for execution.
        self.caller.msg(ox_capabilities=([json.dumps(snapshot, sort_keys=True)], {}))
