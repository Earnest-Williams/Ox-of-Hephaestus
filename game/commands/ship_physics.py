"""Crew-facing local controls for the G18 canonical full-ship scenario."""
from __future__ import annotations

import json
import re
from evennia.commands.command import Command

from world.full_ship_operations import ShipOperationsError


class CmdOxPhysicsRead(Command):
    """Local air/plant readings. Usage: oxplantread <air|helm|cargo|rotor-id|equipment-id|isolator-id>"""

    key = "oxplantread"
    locks = "cmd:all()"

    def func(self):
        from world.continuous_ship_physics import local_physics_readout
        name = self.args.strip()
        if not name:
            self.caller.msg("Usage: oxplantread <air|helm|cargo|rotor-id|equipment-id|isolator-id>")
            return
        try:
            result = local_physics_readout(self.caller, name)
        except (ShipOperationsError, PermissionError) as exc:
            self.caller.msg(str(exc))
            return
        self.caller.msg(json.dumps(result, sort_keys=True))


class CmdOxPhysicsOperate(Command):
    """Request receipted local machinery work.

    Usage: oxplant <32hex-request-id> <switch|plant|schedule|mist|hatch|service|helm|attitude|rotor|drive|freight|ftl> <id> <value>
    """

    key = "oxplant"
    locks = "cmd:all()"

    def func(self):
        from world.continuous_ship_physics import crew_physical_action
        parts = self.args.strip().split()
        if len(parts) != 4 or not re.fullmatch("[0-9a-f]{32}", parts[0]):
            self.caller.msg("Usage: oxplant <32hex-id> <switch|plant|schedule|mist|hatch|service|helm|attitude|rotor|drive|freight|ftl> <id> <value>")
            return
        try:
            result = crew_physical_action(self.caller, *parts)
        except (ShipOperationsError, PermissionError) as exc:
            result = {"request_id": parts[0], "status": "failed",
                      "reason": str(exc), "source_event_id": None}
        self.caller.msg(ox_receipt=([result], {}))
