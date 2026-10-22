"""P4k: native forty-person authenticated evidence recovery acceptance.

Reuses CrewWatchSupervisor's production actor-private, nonce-attested journal
path without inheriting its hard-coded three-person initialization or procedural
ship duties. This harness is an explicit forty-person test controller, not a
replacement for autonomous shipboard GOAP or the production five-crew service.
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from ox_ai.agents.crew import CrewAgent, CrewIdentity
from ox_ai.agents.live_concordia import make_model
from ox_ai.memory.clock import MemoryClockBridge
from ox_ai.ports.base import WorldObservation
from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.runtime.supervisor_lease import SupervisorLease
from ox_ai.runtime.watch_service import (
    CrewWatchSupervisor, ROOT, URL, atomic_json,
)


FLEET_COUNT = 40
FLEET_ROLES = tuple(f"fleet{i:02d}" for i in range(FLEET_COUNT))
_ROSTER_FIELDS = {"username", "character_dbref", "name", "duty"}
_ACTOR = re.compile(r"#[1-9][0-9]*")


def validated_fleet_roster(data: object) -> dict[str, dict[str, str]]:
    """Refuse duplicate bodies, renamed accounts, or partial fleet startup."""
    if not isinstance(data, dict) or set(data) != set(FLEET_ROLES):
        raise ValueError("The fleet must contain exactly forty named roles")
    result = {}
    dbrefs = set()
    names = set()
    for role in FLEET_ROLES:
        record = data[role]
        if not isinstance(record, dict) or set(record) != _ROSTER_FIELDS:
            raise ValueError("Fleet roster entry has an invalid schema")
        if any(not isinstance(value, str) for value in record.values()):
            raise ValueError("Fleet roster fields must be strings")
        if record["username"] != "OxFleet" + role.removeprefix("fleet"):
            raise PermissionError("Fleet account identity does not match slot")
        if _ACTOR.fullmatch(record["character_dbref"]) is None:
            raise ValueError("Fleet body must be one world character DBREF")
        if (not 1 <= len(record["name"]) <= 100
                or not 1 <= len(record["duty"]) <= 256):
            raise ValueError("Fleet character has an invalid name or duty")
        if record["character_dbref"] in dbrefs or record["name"] in names:
            raise PermissionError("Fleet identities may not share bodies or names")
        dbrefs.add(record["character_dbref"])
        names.add(record["name"])
        result[role] = dict(record)
    return result


def fleet_identity(role: str, record: dict[str, str]) -> CrewIdentity:
    return CrewIdentity(
        agent_id=f"ox.person.fleet-{role[-2:]}",
        character_id=record["character_dbref"],
        name=record["name"],
        duty=record["duty"],
        goal="Carry out posted duties using only authenticated personal evidence",
    )


class FleetCrewBrain:
    """One native Concordia CrewAgent bound to one persisted Evennia body."""

    def __init__(self, role: str, record: dict[str, str], path: Path) -> None:
        self.role = role
        self.identity = fleet_identity(role, record)
        self.checkpoint_path = path
        if path.is_file():
            self.agent = CrewAgent.from_checkpoint(path, make_model())
            if self.agent.identity != self.identity:
                raise PermissionError("Fleet checkpoint identity differs from world roster")
        else:
            self.agent = CrewAgent(self.identity, make_model())

    @property
    def character_id(self) -> str:
        return self.identity.character_id

    def observe_event(self, event: dict) -> bool:
        if event.get("recipient_dbref") != self.character_id:
            raise PermissionError("Fleet observation addressed to another character")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("Fleet observation lacks a world event ID")
        game_time = event.get("game_time")
        if (type(game_time) not in (int, float)
                or not math.isfinite(game_time) or game_time < 0):
            raise ValueError("Fleet observation has invalid authoritative time")
        if not isinstance(event.get("data"), dict):
            raise ValueError("Fleet world observation data must be a mapping")
        if self.agent.memory_clock is None:
            self.agent.bind_memory_clock(MemoryClockBridge(
                game_epoch_seconds=float(game_time),
                memory_epoch_turn=self.agent.memory_now_turn,
                seconds_per_turn=1.0,
            ))
        accepted = self.agent.observe(WorldObservation(
            observation_id=event_id,
            character_id=self.character_id,
            game_time=float(game_time),
            text=(str(event["kind"]) + ": " + str(event.get("text", ""))),
            source_event_id=event_id,
            kind=str(event["kind"]),
        ))
        if accepted:
            self.agent.advance_game_time(float(game_time))
        return accepted

    def save_checkpoint(self) -> None:
        self.agent.save_checkpoint(self.checkpoint_path)


class FleetRecoverySupervisor(CrewWatchSupervisor):
    """Forty authenticated clients sharing existing fail-closed archive logic.

    Inheriting only the verified inbox, lease and WebSocket handling preserves
    all P4f archive and nonce checks. Original three/five-person duty policies
    are intentionally not run for these arbitrary fleet roles.
    """

    def __init__(self, *, root: Path = ROOT / "p4k") -> None:
        self.root = Path(root)
        self.state_path = self.root / "supervisor.json"
        roster_file = self.root / "roster.json"
        self.roster = validated_fleet_roster(json.loads(
            roster_file.read_text(encoding="utf-8")
        ))
        self.ids = {
            role: record["character_dbref"]
            for role, record in self.roster.items()
        }
        roster_digest = hashlib.sha256(json.dumps(
            self.roster, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        if self.state_path.is_file():
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        else:
            self.state = {
                "version": 1, "phase": "idle", "inbox_cursors": {},
                "roster_digest": roster_digest, "pending_work": None,
            }
        if (not isinstance(self.state, dict)
                or self.state.get("version") != 1
                or self.state.get("roster_digest") != roster_digest
                or not isinstance(self.state.get("inbox_cursors"), dict)
                or any(role not in self.ids for role in self.state["inbox_cursors"])):
            raise PermissionError("Fleet checkpoint/roster continuity failed")
        password = os.environ["OX_PROBE_PASSWORD"]
        self.clients = {
            role: EvenniaWebSocketClient(
                URL, record["username"], password,
                record["character_dbref"], timeout=20,
            )
            for role, record in self.roster.items()
        }
        self.brains = {
            role: FleetCrewBrain(
                role, record, self.root / "checkpoints" / (role + ".json")
            )
            for role, record in self.roster.items()
        }
        self.memories = {role: deque(maxlen=256) for role in self.clients}
        self._evidence_temporary = tempfile.TemporaryDirectory(
            prefix="ox-p4k-private-evidence-"
        )
        self._journal_continuity = True
        self._evidence_root = self.root / "attested-evidence-v1"
        self._evidence_indexes = {}
        self._inbox_hydrated = set()
        self._inbox_role_locks = {}
        self._fleet_read_lock = asyncio.Lock()
        self._checkpoint_role: str | None = None
        # The same single-host ship lease as the real three/five-crew
        # supervisors; two competing controllers must never share a ship.
        self.lease = SupervisorLease(
            ROOT / "supervisor.lock", owner="FleetRecoverySupervisor",
        )

    def checkpoint(self) -> None:
        """Persist the addressed brain *before* advancing its global cursor."""
        if self._checkpoint_role is None:
            # Used only for the bounded manual durable-work preparation.
            for brain in self.brains.values():
                brain.save_checkpoint()
        else:
            self.brains[self._checkpoint_role].save_checkpoint()
        atomic_json(self.state_path, self.state)

    async def read_inbox(self, role: str):
        if role not in self.clients:
            raise PermissionError("Unknown fleet actor")
        self.lease.assert_held()
        # P4f measured serial prefix verification as faster on shared runners;
        # this also serializes brain->state durable checkpoint publication.
        async with self._fleet_read_lock:
            self._checkpoint_role = role
            try:
                return await super().read_inbox(role)
            finally:
                self._checkpoint_role = None

    async def serve(self) -> None:
        raise RuntimeError(
            "Fleet recovery harness does not implement autonomous duty dispatch"
        )
