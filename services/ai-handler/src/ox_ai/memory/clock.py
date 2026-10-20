"""Explicit mapping between G8-relative memory turns and Evennia game seconds.

Evennia's world clock is authoritative for live transport. The G8 experiment
uses a deterministic virtual-turn axis; neither axis is wall-clock time. A
bridge always declares its epoch and its game-seconds-per-memory-turn scale.
Never infer the scale from how often a memory was written or retrieved.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping


@dataclass(frozen=True, slots=True)
class MemoryClockBridge:
    """One immutable affine mapping into integer memory-domain time."""

    game_epoch_seconds: float
    memory_epoch_turn: int = 0
    seconds_per_turn: float = 1.0

    def __post_init__(self) -> None:
        if (isinstance(self.game_epoch_seconds, bool)
                or not isinstance(self.game_epoch_seconds, (int, float))
                or not math.isfinite(self.game_epoch_seconds)
                or self.game_epoch_seconds < 0):
            raise ValueError("Invalid authoritative game-time epoch")
        if type(self.memory_epoch_turn) is not int or self.memory_epoch_turn < 0:
            raise ValueError("Invalid memory-turn epoch")
        if (isinstance(self.seconds_per_turn, bool)
                or not isinstance(self.seconds_per_turn, (int, float))
                or not math.isfinite(self.seconds_per_turn)
                or self.seconds_per_turn <= 0):
            raise ValueError("A positive finite game-seconds-per-turn is required")

    def turn_at(self, game_time_seconds: float) -> int:
        if (isinstance(game_time_seconds, bool)
                or not isinstance(game_time_seconds, (int, float))
                or not math.isfinite(game_time_seconds)
                or game_time_seconds < 0):
            raise ValueError("Invalid authoritative game time")
        # Floor, do not round to the nearest future time tick.
        return self.memory_epoch_turn + math.floor(
            (game_time_seconds - self.game_epoch_seconds)
            / self.seconds_per_turn
        )

    def game_time_at(self, memory_turn: int) -> float:
        if type(memory_turn) is not int:
            raise ValueError("Memory-domain time must be integer")
        return (self.game_epoch_seconds
                + (memory_turn - self.memory_epoch_turn) * self.seconds_per_turn)

    def to_record(self) -> dict:
        return asdict(self)

    @classmethod
    def from_record(cls, record: Mapping) -> "MemoryClockBridge":
        if not isinstance(record, dict) or set(record) != {
                "game_epoch_seconds", "memory_epoch_turn", "seconds_per_turn"}:
            raise ValueError("Invalid persisted memory-time mapping")
        return cls(**record)
