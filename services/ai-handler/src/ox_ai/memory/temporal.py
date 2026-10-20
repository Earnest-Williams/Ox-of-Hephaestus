"""Actor-private, source-aware temporal memories for bounded GOAP appraisal.

All times are IN A SINGLE caller-supplied monotonic simulation-turn domain.
The journal never asserts the contents of a recollection as world truth.
World events establish that an encounter occurred, not the truth of a claim.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Mapping, Sequence

_CLAIM_KEY = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,95}$")

KINDS = frozenset((
    "recollection", "testimony", "interpretation", "witnessed_speech",
    "world_receipt",
))
SOURCE_WEIGHTS = {
    "recollection": 0.85,
    "testimony": 0.60,
    "interpretation": 0.55,
    "witnessed_speech": 0.93,
    "world_receipt": 1.0,
}
MAX_ENTRIES = 1024
RECALL_HALF_LIFE = 110.0
EVENT_HALF_LIFE = 300.0


def _integer(value, label, *, minimum=None, maximum=None):
    if type(value) is not int or (minimum is not None and value < minimum) or (
        maximum is not None and value > maximum
    ):
        raise ValueError(f"{label} is an out-of-range integer")
    return value


@dataclass(slots=True)
class TemporalMemory:
    memory_id: str
    subject: str
    text: str
    kind: str
    occurred_turn: int
    learned_turn: int
    confidence: int
    salience: int
    trust_effect: int = 0
    interest_effect: int = 0
    last_recalled_turn: int | None = None
    recall_count: int = 0
    source_event_id: str | None = None
    claim_key: str | None = None
    claim_subject: str | None = None
    claim_stance: int = 0
    source_group: str | None = None
    claim_credibility: int = 70

    def __post_init__(self):
        if (not isinstance(self.memory_id, str) or not self.memory_id
                or len(self.memory_id) > 128 or "\n" in self.memory_id):
            raise ValueError("Invalid memory identifier")
        if (not isinstance(self.subject, str) or not self.subject
                or len(self.subject) > 120):
            raise ValueError("Invalid memory subject")
        if (not isinstance(self.text, str) or not self.text.strip()
                or len(self.text) > 600 or any(c in self.text for c in "\r\n\x00")):
            raise ValueError("Memory must be bounded single-line text")
        if self.kind not in KINDS:
            raise ValueError("Unrecognized subjective memory provenance")
        _integer(self.occurred_turn, "occurrence")
        _integer(self.learned_turn, "learning", minimum=self.occurred_turn)
        _integer(self.confidence, "confidence", minimum=0, maximum=100)
        _integer(self.salience, "salience", minimum=0, maximum=100)
        _integer(self.trust_effect, "trust effect", minimum=-40, maximum=40)
        _integer(self.interest_effect, "interest effect", minimum=-40, maximum=40)
        _integer(self.recall_count, "recall count", minimum=0, maximum=100000)
        if self.last_recalled_turn is not None:
            _integer(self.last_recalled_turn, "last recall", minimum=self.learned_turn)
        if self.source_event_id is not None and (
            not isinstance(self.source_event_id, str)
            or not 1 <= len(self.source_event_id) <= 128
        ):
            raise ValueError("Invalid source event identifier")
        if self.claim_key is None:
            if self.claim_subject is not None or self.source_group is not None or self.claim_stance != 0:
                raise ValueError("Unlabelled memory cannot contain claim metadata")
        else:
            if not isinstance(self.claim_key, str) or not _CLAIM_KEY.fullmatch(self.claim_key):
                raise ValueError("Invalid interpretable proposition")
            if type(self.claim_stance) is not int or self.claim_stance not in (-1, 1):
                raise ValueError("Claim must be support or opposition, not a truth value")
            if self.claim_subject is not None and (
                not isinstance(self.claim_subject, str) or not self.claim_subject.strip()
                or len(self.claim_subject) > 120
            ):
                raise ValueError("Claim subject is invalid")
            if self.source_group is not None and (
                not isinstance(self.source_group, str) or not self.source_group.strip()
                or len(self.source_group) > 128
            ):
                raise ValueError("Correlated evidence group is invalid")
        _integer(self.claim_credibility, "source credibility", minimum=0, maximum=100)

    def importance(self, now_turn: int) -> float:
        """Independent event-age and rehearsal-age components, no future leakage."""
        _integer(now_turn, "current turn", minimum=self.learned_turn)
        age = max(0, now_turn - self.occurred_turn)
        if self.last_recalled_turn is not None and now_turn < self.last_recalled_turn:
            raise ValueError("Cannot appraise a memory before its latest recall")
        recall_age = now_turn - (
            self.last_recalled_turn if self.last_recalled_turn is not None
            else self.learned_turn
        )
        age_weight = 0.20 + 0.80 * 2 ** (-age / EVENT_HALF_LIFE)
        recall_weight = 0.30 + 0.70 * 2 ** (-recall_age / RECALL_HALF_LIFE)
        rehearsal = 1.0 + min(0.30, math.log1p(self.recall_count) * 0.06)
        intensity = 0.25 + 0.75 * self.salience / 100
        return (SOURCE_WEIGHTS[self.kind] * (self.confidence / 100)
                * intensity * age_weight * recall_weight * rehearsal)


class TemporalMemoryBank:
    """Per-character cognitive index, never an alternative world facts ledger."""

    def __init__(self, entries: Sequence[TemporalMemory] = ()):
        self._entries: dict[str, TemporalMemory] = {}
        for entry in entries:
            self.add(entry)

    @classmethod
    def from_seeds(cls, seeds):
        return cls(tuple(
            TemporalMemory(
                memory_id=s.memory_id, subject=s.about, text=s.text,
                kind=s.kind, occurred_turn=s.occurred_turn,
                learned_turn=s.learned_turn,
                confidence=s.confidence, salience=s.salience,
                trust_effect=s.trust_effect, interest_effect=s.interest_effect,
                claim_key=s.claim_key, claim_subject=s.claim_subject,
                claim_stance=s.claim_stance, source_group=s.source_group,
                claim_credibility=s.claim_credibility,
            ) for s in seeds
        ))

    def add(self, entry: TemporalMemory) -> bool:
        if not isinstance(entry, TemporalMemory):
            raise TypeError("Only typed subjective memories may be stored")
        old = self._entries.get(entry.memory_id)
        if old is not None:
            if (asdict(old) | {"last_recalled_turn": None, "recall_count": 0}
                    != asdict(entry) | {"last_recalled_turn": None, "recall_count": 0}):
                raise ValueError("Conflicting memory identity; not a second event")
            return False
        if len(self._entries) >= MAX_ENTRIES:
            # Preserve authored backstory while evicting oldest learned events.
            eligible = [x for x in self._entries.values()
                        if x.kind in ("world_receipt", "witnessed_speech")]
            if not eligible:
                raise ValueError("Memory capacity reached with no transient events")
            victim = min(eligible, key=lambda x: (x.learned_turn, x.memory_id))
            del self._entries[victim.memory_id]
        self._entries[entry.memory_id] = entry
        return True

    def retrieve(self, subject: str, now_turn: int, *,
                 limit: int = 4, rehearse: bool = False,
                 affective_only: bool = False) -> tuple[TemporalMemory, ...]:
        _integer(now_turn, "current turn")
        _integer(limit, "retrieval limit", minimum=1, maximum=32)
        found = [x for x in self._entries.values()
                 if x.subject == subject and x.learned_turn <= now_turn
                 and (not affective_only
                      or x.trust_effect != 0 or x.interest_effect != 0)]
        found.sort(key=lambda x: (-x.importance(now_turn), -x.occurred_turn, x.memory_id))
        result = tuple(found[:limit])
        if rehearse:
            for entry in result:
                entry.last_recalled_turn = now_turn
                entry.recall_count += 1
        return result

    def appraisal(self, subject: str, now_turn: int) -> tuple[int, int, tuple[str, ...]]:
        """Bounded subjective adjustment; NOT changes to world relationship truth."""
        items = self.retrieve(subject, now_turn, limit=5, affective_only=True)
        if not items:
            return 0, 0, ()
        weights = [x.importance(now_turn) for x in items]
        total = sum(weights)
        if total <= 0:
            return 0, 0, ()
        # Add evidence with diminishing returns; repeated encounters have a
        # ceiling and can outweigh historical seeds without deleting them.
        strength = min(1.4, total / 1.2)
        trust = round(sum(x.trust_effect * w for x, w in zip(items, weights))
                      / total * strength)
        interest = round(sum(x.interest_effect * w for x, w in zip(items, weights))
                         / total * strength)
        return (max(-40, min(40, trust)),
                max(-40, min(40, interest)),
                tuple(x.memory_id for x in items))

    def get(self, memory_id: str) -> TemporalMemory | None:
        """Return a character-local record by exact immutable event identity."""
        return self._entries.get(memory_id)

    def to_records(self) -> list[dict]:
        return [asdict(x) for x in self._entries.values()]

    @classmethod
    def from_records(cls, values) -> "TemporalMemoryBank":
        if not isinstance(values, list) or len(values) > MAX_ENTRIES:
            raise ValueError("Invalid bounded memory checkpoint")
        return cls(tuple(TemporalMemory(**dict(item)) for item in values))

    def __len__(self):
        return len(self._entries)
