"""``ox.handler.inspect/1``: one character's private epistemic state, read-only.

SKETCH. Published by the AI handler, never by Evennia. It mirrors
``AgentEpistemics`` without adding interpretation: observations carry their
own evidence time and validity window, so a consumer compares them with a
world page's ``game_time_s`` rather than trusting a label computed elsewhere.
Beliefs remain hypotheses; nothing here is world truth.

Authorization is the handler's job (see ``ox_ai.inspection``): a developer
may read any character, a character's owner only their own, and everyone
else gets the same "not found" as a nonexistent character.
"""

from __future__ import annotations

import math
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator
from pydantic import model_validator

SCHEMA = "ox.handler.inspect/1"
STRICT = ConfigDict(extra="forbid", frozen=True, strict=True)
FACT = r"^[a-z][a-z0-9_.:-]{0,95}$"
EVIDENCE = r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$"
CHARACTER = r"^#[1-9][0-9]{0,15}$"
MAX_ENTRIES = 128

Scalar = str | int | float | bool | None


def _finite_time(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError("Times must be finite and non-negative")
    return float(value)


def _scalar(value: Scalar) -> Scalar:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite epistemic value")
    if isinstance(value, str) and len(value) > 256:
        raise ValueError("Epistemic text value too long")
    return value


class InspectRecord(BaseModel):
    model_config = STRICT


class PriorEvidence(InspectRecord):
    value: Scalar
    evidence_id: str = Field(pattern=EVIDENCE)
    observed_game_s: float
    source: Literal["world_local", "world_receipt", "world_event"]

    _value = field_validator("value")(_scalar)
    _time = field_validator("observed_game_s", mode="before")(_finite_time)


class ObservationView(InspectRecord):
    """Authenticated world evidence, as of its own observation time."""

    fact: str = Field(pattern=FACT)
    value: Scalar
    evidence_id: str = Field(pattern=EVIDENCE)
    source: Literal["world_local", "world_receipt", "world_event"]
    observed_game_s: float
    valid_for_s: float
    history: tuple[PriorEvidence, ...] = Field(default=(), max_length=4)

    _value = field_validator("value")(_scalar)
    _times = field_validator("observed_game_s", "valid_for_s", mode="before")(
        _finite_time
    )

    def verified_at(self, game_time_s: float) -> bool:
        """Same rule as ``AgentEpistemics.assess``."""
        return (
            self.observed_game_s
            <= game_time_s
            <= self.observed_game_s + self.valid_for_s
        )


class BeliefView(InspectRecord):
    """Hypothesis or testimony; never world truth, whatever its confidence."""

    fact: str = Field(pattern=FACT)
    value: Scalar
    confidence: float = Field(ge=0, le=1)
    basis: str = Field(min_length=1, max_length=192)
    state: Literal["hypothesis", "refuted"]

    _value = field_validator("value")(_scalar)


class QuestionView(InspectRecord):
    fact: str = Field(pattern=FACT)
    reason: str = Field(min_length=1, max_length=192)
    status: Literal["open", "answered"]


class InspectionPage(InspectRecord):
    schema_version: Literal["ox.handler.inspect/1"]
    character_id: str = Field(pattern=CHARACTER)
    role: str = Field(min_length=1, max_length=64)
    # SHA-256 of the checkpoint bytes this page was built from.
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    # Newest world time this actor holds any evidence for; not handler wall time.
    evidence_horizon_game_s: float
    observations: tuple[ObservationView, ...] = Field(
        default=(), max_length=MAX_ENTRIES
    )
    beliefs: tuple[BeliefView, ...] = Field(default=(), max_length=MAX_ENTRIES)
    questions: tuple[QuestionView, ...] = Field(default=(), max_length=MAX_ENTRIES)
    event_proof_count: int = Field(ge=0, le=512)

    _horizon = field_validator("evidence_horizon_game_s", mode="before")(_finite_time)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        for keys in (
            [o.fact for o in self.observations],
            [b.fact for b in self.beliefs],
            [q.fact for q in self.questions],
        ):
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate fact in one section")
        if any(
            o.observed_game_s > self.evidence_horizon_game_s for o in self.observations
        ):
            raise ValueError("Observation newer than the evidence horizon")
        return self


INSPECTION_ADAPTER: TypeAdapter[InspectionPage] = TypeAdapter(InspectionPage)


def parse_inspection_json(raw: bytes) -> InspectionPage:
    """JSON mode: strict scalars, arrays admitted as the frozen tuples."""
    return INSPECTION_ADAPTER.validate_json(raw)
