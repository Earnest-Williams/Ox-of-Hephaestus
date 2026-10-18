"""World-owned, recipient-scoped advertisement of *local* ship capabilities.

An advertisement describes current possible actions; it is NOT a grant and
must never be used to bypass the actual exit, fixture or WorkReceipt checks.
No remote equipment, invisible compartments, global map or handler-only
knowledge is exposed.
"""
from __future__ import annotations

import re

from evennia.objects.objects import DefaultExit
from typeclasses.ship import ShipRoom, CoolingPump
from typeclasses.departments import CargoCradle, AtmosphereScrubber


_NONCE = re.compile(r"[0-9a-f]{32}")
_COMMAND = re.compile(r"[a-zA-Z][a-zA-Z0-9 _-]{0,63}")


def local_capabilities(actor, nonce: str) -> dict:
    """Return only exits and fixture actions visible to this character."""
    if (actor is None or not isinstance(getattr(actor, "dbref", None), str)
            or not isinstance(nonce, str) or _NONCE.fullmatch(nonce) is None):
        raise PermissionError("A verified character and challenge are required")
    room = getattr(actor, "location", None)
    if not isinstance(room, ShipRoom):
        # Never enumerate objects in limbo or non-ship world areas.
        return {
            "version": 1, "nonce": nonce, "actor_dbref": actor.dbref,
            "room": None, "exits": [], "equipment": [],
        }
    exits = []
    fixtures = []
    for obj in room.contents:
        if isinstance(obj, DefaultExit):
            dest = obj.destination
            if (not isinstance(dest, ShipRoom)
                    or not _COMMAND.fullmatch(obj.key)
                    or not obj.access(actor, "traverse", default=True)):
                continue
            exits.append({
                "exit_dbref": obj.dbref,
                "command": obj.key,
                "destination_dbref": dest.dbref,
                "destination_name": dest.key,
            })
            continue
        # Installed stationary fixtures only. Never expose another room's
        # detailed machine state or claim skills inferred from a template.
        if isinstance(obj, CoolingPump):
            operations = ["inspect"]
            if obj._is_engineer_here(actor):
                if obj.state == "low_pressure":
                    operations.append("isolate")
                elif obj.state == "isolated":
                    operations.append("repair")
                elif obj.state == "repaired" and (
                    not obj.db.ox_chief_gate or obj.db.ox_chief_released
                ):
                    operations.append("commission")
            target = "pump"
        elif isinstance(obj, CargoCradle):
            operations = ["inspect"]
            if obj._authorized(actor, "cargo_officer"):
                if obj.state == "unsecured" and obj._fresh_inspection(actor):
                    operations.append("restow")
                elif obj.state == "restowed" and obj._fresh_inspection(actor):
                    operations.append("certify")
            target = "cargo"
        elif isinstance(obj, AtmosphereScrubber):
            operations = ["inspect"]
            if obj._authorized(actor, "environment_tech"):
                if obj.state == "saturated" and obj._fresh_inspection(actor):
                    operations.append("isolate")
                elif obj.state == "isolated" and int(obj.db.spare_cartridges or 0) > 0:
                    operations.append("replace")
                elif obj.state == "serviced" and obj._fresh_inspection(actor):
                    operations.append("restart")
            target = "scrubber"
        else:
            continue
        fixtures.append({
            "fixture_dbref": obj.dbref, "target": target,
            "name": obj.key, "operations": operations,
        })
    return {
        "version": 1, "nonce": nonce, "actor_dbref": actor.dbref,
        "room": {"dbref": room.dbref, "name": room.key},
        "exits": sorted(exits, key=lambda e: (e["command"], e["exit_dbref"])),
        "equipment": sorted(fixtures, key=lambda e: e["fixture_dbref"]),
    }
