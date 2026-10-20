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
    # All times share the supplied monotonic simulation-turn clock.
    occurred_turn: int = -100
    learned_turn: int = 0
    trust_effect: int = 0
    interest_effect: int = 0
    # Optional assertion about a proposition. These are not world truths.
    claim_key: str | None = None
    claim_subject: str | None = None
    claim_stance: int = 0
    source_group: str | None = None
    claim_credibility: int = 70

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
        if type(self.occurred_turn) is not int or type(self.learned_turn) is not int:
            raise ValueError("Temporal memory dates must be integer scenario turns")
        if self.learned_turn < self.occurred_turn:
            raise ValueError("A recollection cannot be learned before its event")
        for label, effect in (("trust", self.trust_effect), ("interest", self.interest_effect)):
            if type(effect) is not int or not -40 <= effect <= 40:
                raise ValueError(f"Subjective {label} effect must be an integer -40..40")
        if self.claim_key is None:
            if self.claim_subject is not None or self.source_group is not None or self.claim_stance != 0:
                raise ValueError("An unlabelled memory cannot assert a hypothesis")
        else:
            if not isinstance(self.claim_key, str) or not _SEED_ID.fullmatch(self.claim_key):
                raise ValueError("Invalid claim key")
            if type(self.claim_stance) is not int or self.claim_stance not in (-1, 1):
                raise ValueError("Claim must support or dispute a hypothesis")
            if self.claim_subject is not None and (
                not isinstance(self.claim_subject, str) or not self.claim_subject.strip()
                or len(self.claim_subject) > 120
            ):
                raise ValueError("Invalid claim subject")
            if self.source_group is not None and (
                not isinstance(self.source_group, str) or not self.source_group.strip()
                or len(self.source_group) > 128
            ):
                raise ValueError("Invalid claim source group")
        if type(self.claim_credibility) is not int or not 0 <= self.claim_credibility <= 100:
            raise ValueError("Claim credibility must be an integer 0-100")

    def render(self) -> str:
        """Mark authored information as uncertain recollection, not observation."""
        return (f"[authored-memory id={self.memory_id}; kind={self.kind}; "
                f"about={self.about}; confidence={self.confidence}; "
                f"salience={self.salience}; occurred_turn={self.occurred_turn}; "
                f"learned_turn={self.learned_turn}; claim={self.claim_key or 'none'}; "
                f"NOT world-verified] {self.text}")


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
