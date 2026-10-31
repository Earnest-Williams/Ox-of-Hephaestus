"""Project one persisted ``AgentEpistemics`` record into ``ox.handler.inspect/1``.

SKETCH. Pure: takes the checkpoint bytes the supervisor already wrote with
``atomic_json``, never the live supervisor object, so inspection cannot race
or mutate cognition. A record that fails the contract is refused, not fixed.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import orjson
from ox_contracts.handler_inspection import (
    BeliefView,
    InspectionPage,
    ObservationView,
    PriorEvidence,
    QuestionView,
)


class InspectionUnavailable(LookupError):
    """No such character in this checkpoint (or not authorized: same answer)."""


def find_record(state: Mapping[str, Any], character_id: str) -> Mapping[str, Any]:
    epistemics: object = state.get("epistemics")
    if not isinstance(epistemics, dict):
        raise InspectionUnavailable(character_id)
    for record in epistemics.values():
        if isinstance(record, dict) and record.get("character_id") == character_id:
            return record
    raise InspectionUnavailable(character_id)


def _observation(fact: str, entry: Mapping[str, Any]) -> ObservationView:
    history: tuple[PriorEvidence, ...] = tuple(
        PriorEvidence(
            value=prior["value"],
            evidence_id=prior["evidence_id"],
            observed_game_s=prior["at"],
            source=prior["source"],
        )
        for prior in entry["history"]
    )
    return ObservationView(
        fact=fact,
        value=entry["value"],
        evidence_id=entry["evidence_id"],
        source=entry["source"],
        observed_game_s=entry["at"],
        valid_for_s=entry["valid_for"],
        history=history,
    )


def inspection_page(checkpoint: bytes, character_id: str) -> InspectionPage:
    state: object = orjson.loads(checkpoint)
    if not isinstance(state, dict):
        raise InspectionUnavailable(character_id)
    record: Mapping[str, Any] = find_record(state, character_id)
    observations: tuple[ObservationView, ...] = tuple(
        _observation(fact, entry)
        for fact, entry in sorted(record["observations"].items())
    )
    times: list[float] = [o.observed_game_s for o in observations] + [
        float(event["at"]) for event in record["events"].values()
    ]
    return InspectionPage(
        schema_version="ox.handler.inspect/1",
        character_id=character_id,
        role=str(record["role"]),
        checkpoint_sha256=hashlib.sha256(checkpoint).hexdigest(),
        evidence_horizon_game_s=max(times, default=0.0),
        observations=observations,
        beliefs=tuple(
            BeliefView(
                fact=fact,
                value=entry["value"],
                confidence=float(entry["confidence"]),
                basis=entry["basis"],
                state=entry["state"],
            )
            for fact, entry in sorted(record["beliefs"].items())
        ),
        questions=tuple(
            QuestionView(fact=fact, reason=entry["reason"], status=entry["status"])
            for fact, entry in sorted(record["questions"].items())
        ),
        event_proof_count=len(record["events"]),
    )
