"""Turn an actor's ``ox.world.read/1`` pages into private G19 evidence.

SKETCH (ROADMAP Priority 2, belief side). Only the authenticated world port
may call this: it uses ``observe_verified`` with ``world_local`` evidence.
Nothing here asks the world what is true elsewhere; an engineer believes
exactly what their own panel reads and exits told them, with the sample time
the panel reported. Later silence leaves the belief in place and lets it
expire, which is the "possibly stale belief" the P5 test needs.

Capacity: ``AgentEpistemics.CAP`` is 128 observations per actor. 116 panels ×
8 metrics cannot fit, so facts are admitted by priority and the rest are
reported as deferred. Raising CAP or moving G19 evidence into the indexed
evidence store is a decision, not something to paper over here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, Protocol

from ox_contracts.world_read_model import (
    MAX_OBSERVATION_AGE_S,
    ActorWorldPage,
    EquipmentObservation,
)

Scalar = str | int | float | bool | None
Source = Literal["world_local", "world_receipt", "world_event"]

FACT_PREFIX: Final[str] = "g19"
# Admission order when capacity is short: health of the instrument first,
# then the readings that decide whether a space is survivable.
METRIC_PRIORITY: Final[tuple[str, ...]] = (
    "availability",
    "pressure_kpa",
    "oxygen_kpa",
    "smoke_fraction",
    "co2_fraction",
    "leak_kg_s",
    "burn_kg_s",
    "temperature_k",
    "cell_damage",
)


class EpistemicLedger(Protocol):
    """Typed view of ``AgentEpistemics``; the class conforms structurally."""

    CAP: int
    record: dict[str, Any]

    def observe_verified(
        self,
        fact: str,
        value: Scalar,
        *,
        evidence_id: str,
        at: float,
        valid_for: float = 0,
        source: str,
        surprise: bool = False,
    ) -> bool: ...

    def receive_event(self, event: Mapping[str, object]) -> bool: ...


@dataclass(frozen=True, slots=True)
class PendingFact:
    fact: str
    value: Scalar
    evidence_id: str
    at: float
    priority: int


@dataclass(frozen=True, slots=True)
class IngestReport:
    recorded: int
    unchanged: int
    events_proved: int
    deferred_for_capacity: tuple[str, ...]


def panel_fact(panel_id: str, metric: str) -> str:
    """Epistemic keys are lowercase; G19 IDs are ``[A-Z0-9-]`` so this inverts."""
    return FACT_PREFIX + ".panel." + panel_id.lower() + "." + metric


def exit_fact(link_id: str) -> str:
    return FACT_PREFIX + ".exit." + link_id.lower() + ".assessment"


def _priority(metric: str) -> int:
    return (
        METRIC_PRIORITY.index(metric)
        if metric in METRIC_PRIORITY
        else len(METRIC_PRIORITY)
    )


def _evidence_id(kind: str, source_id: str, at: float) -> str:
    return "wr-" + kind + "-" + source_id + "-" + str(int(at * 1000))


def _panel_facts(view: EquipmentObservation) -> list[PendingFact]:
    at: float = view.evidence.observed_game_s
    evidence: str = _evidence_id("panel", view.equipment_id, at)
    facts: list[PendingFact] = [
        PendingFact(
            fact=panel_fact(view.equipment_id, "availability"),
            value=view.availability,
            evidence_id=evidence,
            at=at,
            priority=0,
        )
    ]
    # A failed sample adds no values and erases none: older readings stay as
    # history and simply stop being currently verified.
    for reading in view.readings:
        facts.append(
            PendingFact(
                fact=panel_fact(view.equipment_id, reading.name),
                value=reading.value,
                evidence_id=evidence,
                at=at,
                priority=_priority(reading.name),
            )
        )
    return facts


def pending_facts(pages: Sequence[ActorWorldPage]) -> list[PendingFact]:
    facts: list[PendingFact] = []
    for page in pages:
        for view in page.equipment:
            facts.extend(_panel_facts(view))
        for exit_view in page.exits:
            at: float = exit_view.evidence.observed_game_s
            facts.append(
                PendingFact(
                    fact=exit_fact(exit_view.link_id),
                    value=exit_view.assessment,
                    evidence_id=_evidence_id("exit", exit_view.link_id, at),
                    at=at,
                    priority=len(METRIC_PRIORITY) + 1,
                )
            )
    return sorted(facts, key=lambda f: (f.priority, f.fact))


def ingest_actor_pages(
    ledger: EpistemicLedger, pages: Sequence[ActorWorldPage]
) -> IngestReport:
    if not pages:
        return IngestReport(0, 0, 0, ())
    owner: object = ledger.record.get("character_id")
    if any(page.character_id != owner for page in pages):
        raise PermissionError("World-read page belongs to another character")

    proved: int = 0
    for page in pages:
        for event in page.addressed_events:
            if ledger.receive_event(
                {
                    "event_id": event.event_id,
                    "recipient_dbref": event.recipient_character_id,
                    "kind": event.kind,
                    "game_time": event.occurred_game_s,
                }
            ):
                proved += 1

    recorded: int = 0
    unchanged: int = 0
    deferred: list[str] = []
    observations: dict[str, Any] = ledger.record["observations"]
    for item in pending_facts(pages):
        if item.fact not in observations and len(observations) >= ledger.CAP:
            deferred.append(item.fact)
            continue
        changed: bool = ledger.observe_verified(
            item.fact,
            item.value,
            evidence_id=item.evidence_id,
            at=item.at,
            valid_for=MAX_OBSERVATION_AGE_S,
            source="world_local",
        )
        if changed:
            recorded += 1
        else:
            unchanged += 1
    return IngestReport(recorded, unchanged, proved, tuple(deferred))
