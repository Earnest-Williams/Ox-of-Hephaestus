"""Disposable operator-only setup for authenticated G2c pathfinding acceptance.

No in-world command invokes this module. It provisions ordinary crew
accounts and changes the world only before launching the test server.
"""
from __future__ import annotations

from world.bootstrap import build_ship, find_fixture, _exit
from world.transport_probe import provision


def prepare(mode: str) -> dict[str, str]:
    if mode not in ("direct", "blocked", "reroute"):
        raise ValueError("Unknown navigation verification scenario")
    identities = provision()
    ship = build_ship()
    ari = ship["watch"]
    if not ari.move_to(ship["mess"], quiet=True):
        raise RuntimeError("Fixture cannot place crew at mess for trial")
    if mode in ("blocked", "reroute"):
        hatch = find_fixture("exit-passage-engineering")
        hatch.locks.add("traverse:false()")
        if hatch.access(ari, "traverse"):
            raise RuntimeError("World hatch traverse lock was not enforced")
    if mode == "reroute":
        # Additional *world-owned* accessible doors, not an AI shortcut.
        _exit("exit-mess-workshop-g2c", "shop", ship["mess"], ship["workshop"])
        _exit("exit-workshop-mess-g2c", "galley", ship["workshop"], ship["mess"])
    if ship["pump"].state != "normal":
        raise RuntimeError("Navigation tests may not change pump state")
    return identities
