"""Authenticated, local-only ship inventory readout with nonce binding."""
from __future__ import annotations

import json
from evennia.commands.command import Command
from world.supply import local_stock_for


class CmdOxInventory(Command):
    """Only this character's local consumables and actually carried items."""

    key = "oxinventory"
    locks = "cmd:all()"

    def func(self):
        try:
            observation = local_stock_for(self.caller, self.args.strip())
        except (ValueError, PermissionError):
            self.caller.msg("Usage: oxinventory <32 lowercase hexadecimal nonce>")
            return
        self.caller.msg(ox_inventory=([json.dumps(observation, sort_keys=True)], {}))
