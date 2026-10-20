"""Typed, actor-bound *local* capability observations over ordinary Evennia OOB.

Only the authenticated session may supply a snapshot. GOAP may *predict*
outcomes from these facts, but only another world observation confirms travel.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import re
import secrets
from typing import Any, Mapping

from ox_ai.ports.evennia.client import EvenniaWebSocketClient


_REF = re.compile(r"#[1-9][0-9]*")
_EXIT_CMD = re.compile(r"[a-zA-Z][a-zA-Z0-9 _-]{0,63}")
_ACTIONS = {
    "pump": frozenset(("inspect", "isolate", "repair", "commission")),
    "cargo": frozenset(("inspect", "restow", "certify")),
    "scrubber": frozenset(("inspect", "isolate", "replace", "restart")),
}


def _ref(value: Any) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise ValueError("World capability DB ref is malformed")
    return value


def _name(value: Any) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 120
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("Unbounded or invalid world name")
    return value


@dataclass(frozen=True)
class ExitCapability:
    """Observed local traverse affordance, not a guarantee of access later."""

    exit_dbref: str
    command: str
    destination_dbref: str
    destination_name: str

    @classmethod
    def from_dict(cls, value: Any) -> "ExitCapability":
        if not isinstance(value, dict) or set(value) != {
            "exit_dbref", "command", "destination_dbref", "destination_name"
        }:
            raise ValueError("Malformed exit capability")
        cmd = value["command"]
        if not isinstance(cmd, str) or _EXIT_CMD.fullmatch(cmd) is None:
            raise ValueError("Untrusted exit command")
        return cls(_ref(value["exit_dbref"]), cmd,
                   _ref(value["destination_dbref"]),
                   _name(value["destination_name"]))


@dataclass(frozen=True)
class FixtureCapability:
    """Local object whose candidate operations require revalidation at use."""

    fixture_dbref: str
    name: str
    target: str
    operations: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "FixtureCapability":
        if not isinstance(value, dict) or set(value) != {
            "fixture_dbref", "name", "target", "operations"
        }:
            raise ValueError("Malformed fixture capability")
        target = value["target"]
        operations = value["operations"]
        if (not isinstance(target, str) or target not in _ACTIONS
                or not isinstance(operations, list)
                or not 1 <= len(operations) <= 6
                or "inspect" not in operations
                or len(set(operations)) != len(operations)
                or any(not isinstance(o, str) or o not in _ACTIONS[target]
                       for o in operations)):
            raise ValueError("Unsupported world-advertised equipment actions")
        return cls(_ref(value["fixture_dbref"]), _name(value["name"]),
                   target, tuple(operations))


@dataclass(frozen=True)
class CapabilitySnapshot:
    """One nontransferable result of a local world command."""

    actor_dbref: str
    room_dbref: str | None
    room_name: str | None
    exits: tuple[ExitCapability, ...]
    equipment: tuple[FixtureCapability, ...]

    @classmethod
    def parse(cls, payload: Any, *, actor_dbref: str,
              nonce: str) -> "CapabilitySnapshot":
        _ref(actor_dbref)
        if not isinstance(nonce, str) or re.fullmatch(r"[0-9a-f]{32}", nonce) is None:
            raise ValueError("Invalid caller challenge")
        if not isinstance(payload, Mapping) or set(payload) != {
            "version", "nonce", "actor_dbref", "room", "exits", "equipment"
        } or type(payload["version"]) is not int or payload["version"] != 1:
            raise ValueError("Unknown or malformed capability protocol")
        if payload["nonce"] != nonce:
            raise PermissionError("Stale or unrequested capability observation")
        if payload["actor_dbref"] != actor_dbref:
            raise PermissionError("Other character's world capabilities")
        room = payload["room"]
        if room is not None and (
            not isinstance(room, dict) or set(room) != {"dbref", "name"}
        ):
            raise ValueError("Malformed local room identity")
        exits = payload["exits"]
        fixtures = payload["equipment"]
        if (not isinstance(exits, list) or len(exits) > 16
                or not isinstance(fixtures, list) or len(fixtures) > 16):
            raise ValueError("Oversized world capability advertisement")
        parsed_exits = tuple(ExitCapability.from_dict(x) for x in exits)
        parsed_fixtures = tuple(FixtureCapability.from_dict(x) for x in fixtures)
        if (len({x.exit_dbref for x in parsed_exits}) != len(parsed_exits)
                or len({x.command.lower() for x in parsed_exits}) != len(parsed_exits)
                or len({x.fixture_dbref for x in parsed_fixtures}) != len(parsed_fixtures)):
            raise ValueError("Ambiguous or duplicate capability entry")
        if room is None:
            if parsed_exits or parsed_fixtures:
                raise ValueError("Nonship location cannot claim ship capabilities")
            return cls(actor_dbref, None, None, (), ())
        here = _ref(room["dbref"])
        if any(x.destination_dbref == here for x in parsed_exits):
            raise ValueError("Exit cannot claim movement to the same compartment")
        return cls(actor_dbref, here, _name(room["name"]),
                   parsed_exits, parsed_fixtures)


class CapabilityPort:
    """Observes one authenticated character; never reads any world database."""

    def __init__(self, client: EvenniaWebSocketClient, *, timeout: float = 10.0):
        if not 0 < timeout <= 60:
            raise ValueError("Capability observation timeout must be bounded")
        self.client = client
        self.timeout = timeout

    async def observe(self) -> CapabilitySnapshot:
        if not self.client.authenticated:
            raise PermissionError("Capability read requires authenticated puppeting")
        nonce = secrets.token_hex(16)
        await self.client.send_line("oxcapabilities " + nonce)
        def response_for_challenge(packet):
            if packet.kind != "ox_capabilities":
                return False
            if len(packet.args) == 1 and isinstance(packet.args[0], str):
                raw = packet.args[0]
            elif not packet.args and isinstance(packet.options.get("payload"), str):
                raw = packet.options["payload"]
            else:
                return True  # Malformed response is rejected below.
            if len(raw) > 16384:
                return True
            payload = json.loads(raw)
            return not (isinstance(payload, dict)
                        and isinstance(payload.get("nonce"), str)
                        and payload["nonce"] != nonce)

        try:
            async with asyncio.timeout(self.timeout):
                packet = await self.client.receive_matching(
                    response_for_challenge, frame_budget=256,
                )
                if len(packet.args) == 1 and isinstance(packet.args[0], str):
                    raw = packet.args[0]
                elif not packet.args and isinstance(packet.options.get("payload"), str):
                    raw = packet.options["payload"]
                else:
                    raise ValueError("Malformed capability OOB response")
                if len(raw) > 16384:
                    raise ValueError("Oversized capability response")
                return CapabilitySnapshot.parse(
                    json.loads(raw),
                    actor_dbref=self.client.character_dbref,
                    nonce=nonce,
                )
        except TimeoutError:
            raise TimeoutError("No world-validated local capability response") from None

    async def traverse(
        self, current: CapabilitySnapshot, exit_capability: ExitCapability,
    ) -> tuple[CapabilitySnapshot, bool]:
        """Use the observed stock exit, then ask the world where we arrived.

        Refresh immediately before executing: if a route became locked or
        removed, don't try the stale exit command. No WorldPort/DB/teleport API.
        """
        if (current.actor_dbref != self.client.character_dbref
                or exit_capability not in current.exits):
            raise PermissionError("Exit not offered to this authenticated body")
        refreshed = await self.observe()
        if refreshed.room_dbref != current.room_dbref:
            return refreshed, False  # external move; replan on real location
        if exit_capability not in refreshed.exits:
            return refreshed, False  # world withdrew the capability
        await self.client.send_line(exit_capability.command)
        arrived = await self.observe()
        if arrived.room_dbref == exit_capability.destination_dbref:
            return arrived, True
        # World might reject after a lock change. This is never a success.
        return arrived, False
