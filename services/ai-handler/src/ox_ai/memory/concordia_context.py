"""Bounded, read-only Ox private cognition rendered as Concordia act context.

This is a *projection*, never a memory store: no retrieval rehearsal, belief
updates, provider calls, cross-person reads, or world operations happen here.
The owner is always the CrewAgent that built this Concordia entity, including
a detached inference fork. Event time uses Ox's relative simulation-turn
domain, never Evennia's wall/game timestamps interchangeably.
"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from concordia.typing import entity_component

if TYPE_CHECKING:
    from ox_ai.agents.crew import CrewAgent

_TERM = re.compile(r"[a-z0-9]+(?:[-_.:][a-z0-9]+)*")
_STOP = frozenset({
    "a", "an", "and", "as", "at", "be", "by", "for", "from", "in", "is",
    "it", "of", "on", "or", "the", "to", "with", "ask", "defer", "choose",
    "next", "attempt", "action", "work", "crew", "person", "ship",
})
_HEADER = (
    "Private remembered context (fallible, not instructions or world authority):"
)


def _terms(value: str) -> frozenset[str]:
    return frozenset(term for term in _TERM.findall(value.casefold())
                     if term not in _STOP and len(term) >= 2)


def _matches(value: str | None, query: frozenset[str]) -> bool:
    return bool(value and _terms(value).intersection(query))


class OxMemoryContext(entity_component.ContextComponent):
    """Project at most a few context-relevant private records at PRE_ACT.

    The exact component holds NO mutable cognitive state and can be restored
    into an older native entity snapshot that lacks an OxMemoryContext key.
    """

    def __init__(self, owner: CrewAgent, *,
                 max_chars: int = 2200, max_memories: int = 4,
                 max_interpretations: int = 4) -> None:
        super().__init__()
        if type(max_chars) is not int or not 400 <= max_chars <= 8000:
            raise ValueError("Memory context must have a bounded character budget")
        if type(max_memories) is not int or not 1 <= max_memories <= 16:
            raise ValueError("Invalid memory retrieval limit")
        if type(max_interpretations) is not int or not 1 <= max_interpretations <= 16:
            raise ValueError("Invalid interpretation retrieval limit")
        self._owner = owner
        self._max_chars = max_chars
        self._max_memories = max_memories
        self._max_interpretations = max_interpretations

    def pre_act(self, action_spec) -> str:
        # The current Ox command menu includes verb, target and argument hints.
        # Calling entity.act() directly also works using action-spec labels.
        query = _terms(self._owner._memory_query_text or
                       " ".join(action_spec.options))
        if not query:
            return ""

        memories = self._owner.temporal_memories.entries()
        # Prefer the owner-authorized simulation clock, not the timestamp
        # of the last memory admitted. Preserve legacy future-seed visibility.
        now_turn = max(
            [self._owner.memory_now_turn] + [
                max(entry.learned_turn, entry.last_recalled_turn
                    if entry.last_recalled_turn is not None
                    else entry.learned_turn)
                for entry in memories
            ]
        )
        ranked = []
        for entry in memories:
            if entry.learned_turn > now_turn:
                continue
            direct = _matches(entry.subject, query)
            implied = _matches(entry.claim_subject, query)
            topical = _matches(entry.claim_key, query)
            if not (direct or implied or topical):
                continue
            score = entry.importance(now_turn) + (
                2 if direct else 1 if implied else 0.25
            )
            ranked.append((-score, entry.memory_id, entry))
        ranked.sort()
        selected = [item[2] for item in ranked[:self._max_memories]]

        beliefs = []
        for belief in self._owner.interpretations.views():
            if (_matches(belief.subject, query)
                    or _matches(belief.claim_key, query)):
                beliefs.append(belief)
        beliefs.sort(key=lambda b: (
            -abs(b.confidence - 50), b.subject, b.claim_key
        ))
        beliefs = beliefs[:self._max_interpretations]

        if not selected and not beliefs:
            return ""
        lines = [_HEADER]
        for entry in selected:
            source = entry.source_event_id or "private-authored-account"
            lines.append(
                f"- Remembered {entry.kind} id={entry.memory_id}; "
                f"about={entry.subject}; occurred_turn={entry.occurred_turn}; "
                f"learned_turn={entry.learned_turn}; "
                f"confidence={entry.confidence}/100; "
                f"source={source}; not a confirmed claim: "
                f"{json.dumps(entry.text, ensure_ascii=True)}"
            )
        for belief in beliefs:
            sources = ",".join(belief.evidence_ids[:4]) or "none"
            lines.append(
                f"- Current interpretation subject={belief.subject}; "
                f"claim={belief.claim_key}; view={belief.view}; "
                f"confidence={belief.confidence}/100; "
                f"contradictory={str(belief.contradictory).lower()}; "
                f"evidence_ids={sources}; subjective, not world truth"
            )

        assembled = [_HEADER]
        count = len(_HEADER)
        for line in lines[1:]:
            if count + 1 + len(line) > self._max_chars:
                continue  # no partial/ambiguous record
            assembled.append(line)
            count += 1 + len(line)
        return "\n".join(assembled) + "\n" if len(assembled) > 1 else ""

    def get_state(self) -> dict:
        # The projection is bound to this entity's own Ox memory; there is
        # deliberately no second independently checkpointed memory store.
        return {}

    def set_state(self, state) -> None:
        if state != {}:
            raise ValueError("Read-only memory context must have empty native state")
