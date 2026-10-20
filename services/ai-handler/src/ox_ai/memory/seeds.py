"""Authored, actor-private prehistory for new Concordia character minds.

Not world observations, witnessed events, skill evidence, or an authoritative
record of what really happened. No memory seed can grant world permissions.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

_SEED_ID = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,95}$")
KINDS = frozenset(("recollection", "testimony", "interpretation"))


@dataclass(frozen=True, slots=True)
class SeededMemory:
    memory_id: str
    text: str
    about: str
    kind: str = "recollection"
    confidence: int = 70
    salience: int = 50

    def __post_init__(self) -> None:
        if not isinstance(self.memory_id, str) or not _SEED_ID.fullmatch(self.memory_id):
            raise ValueError("Memory ID must be a unique safe 1-96 character identifier")
        if (not isinstance(self.text, str) or not self.text.strip()
                or len(self.text) > 600 or "\n" in self.text or "\r" in self.text):
            raise ValueError("Memory text must be nonempty, single-line, <=600 characters")
        if (not isinstance(self.about, str) or not self.about.strip()
                or len(self.about) > 120 or "\n" in self.about or "\r" in self.about):
            raise ValueError("Memory subject must be nonempty, single-line, <=120 characters")
        if self.kind not in KINDS:
            raise ValueError("Memory kind must be recollection, testimony, or interpretation")
        for label, score in (("confidence", self.confidence), ("salience", self.salience)):
            if type(score) is not int or not 0 <= score <= 100:
                raise ValueError(f"Memory {label} must be an integer 0-100")

    def render(self) -> str:
        """Mark authored information as uncertain recollection, not observation."""
        return (f"[authored-memory id={self.memory_id}; kind={self.kind}; "
                f"about={self.about}; confidence={self.confidence}; "
                f"salience={self.salience}; NOT world-verified] {self.text}")


def validate_seed_memories(memories: Sequence[SeededMemory]) -> tuple[SeededMemory, ...]:
    """Bound, type-check and deduplicate before creating an agent."""
    if isinstance(memories, (str, bytes)) or not isinstance(memories, Sequence):
        raise TypeError("Seed memories must be a sequence of SeededMemory")
    if len(memories) > 64:
        raise ValueError("At most 64 memory seeds per new character")
    if any(not isinstance(memory, SeededMemory) for memory in memories):
        raise TypeError("Seeded memories must be validated SeededMemory records")
    ids = [memory.memory_id for memory in memories]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate initial memory ID")
    return tuple(memories)
