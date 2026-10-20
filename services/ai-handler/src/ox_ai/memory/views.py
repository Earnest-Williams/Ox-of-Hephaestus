"""Defensive read-only projections of one CrewAgent's private cognition.

These are application-level capability boundaries, not security sandboxes.
Mutation remains available to standalone domain banks but not through the
CrewAgent public API. Every returned mutable record is detached.
"""
from __future__ import annotations

from copy import deepcopy

from ox_ai.memory.temporal import TemporalMemoryBank, TemporalMemory
from ox_ai.memory.interpretation import InterpretationBank, Interpretation, InterpretationRevision


class TemporalMemoryReadView:
    """Read an owner's private episodes without exposing writable records."""

    __slots__ = ("__source",)

    def __init__(self, source: TemporalMemoryBank) -> None:
        self.__source = source

    def get(self, memory_id: str) -> TemporalMemory | None:
        return deepcopy(self.__source.get(memory_id))

    def entries(self) -> tuple[TemporalMemory, ...]:
        return deepcopy(self.__source.entries())

    def retrieve(
        self, subject: str, now_turn: int, *,
        limit: int = 4, rehearse: bool = False,
        affective_only: bool = False,
    ) -> tuple[TemporalMemory, ...]:
        if rehearse:
            raise PermissionError("Use CrewAgent.rehearse_memories to mutate recall")
        return deepcopy(self.__source.retrieve(
            subject, now_turn, limit=limit, affective_only=affective_only,
        ))

    def appraisal(self, subject: str, now_turn: int) -> tuple[int, int, tuple[str, ...]]:
        return self.__source.appraisal(subject, now_turn)

    def to_records(self) -> list[dict]:
        return self.__source.to_records()

    def __len__(self) -> int:
        return len(self.__source)


class InterpretationReadView:
    """Read current private hypotheses without exposing the mutable ledger."""

    __slots__ = ("__source",)

    def __init__(self, source: InterpretationBank) -> None:
        self.__source = source

    def get(self, subject: str, claim_key: str) -> Interpretation | None:
        return deepcopy(self.__source.get(subject, claim_key))

    def views(self) -> tuple[Interpretation, ...]:
        return deepcopy(self.__source.views())

    def for_subject(self, subject: str) -> tuple[Interpretation, ...]:
        return deepcopy(self.__source.for_subject(subject))

    def all_revisions(self) -> tuple[InterpretationRevision, ...]:
        return self.__source.all_revisions()

    def to_records(self) -> dict:
        return self.__source.to_records()
