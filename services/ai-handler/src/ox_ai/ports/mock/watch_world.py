"""Deterministic mock ship: authoritative clock, roster and scoped messages.

No model, Concordia scheduler, timer thread or Evennia database is involved.
Only the world may advance the game clock or change active-watch assignments.
Each observation has ONE recipient and is delivered through its event queue.
World event history is privileged test/operator data, never agent context.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque

from ox_ai.ports.base import ActionOutcome, ActionRequest, WorldObservation


@dataclass(frozen=True, slots=True)
class MockCrewMember:
    character_id: str
    name: str
    role: str
    location: str


@dataclass(frozen=True, slots=True)
class WorldEvent:
    event_id: str
    minute: int
    kind: str
    actor_id: str | None
    recipient_id: str | None
    text: str


class MockWatchWorld:
    """Small event-sourced fixture, not a remotely exposed game API."""

    ENGINEERING_HANDOVER_MINUTE = 7 * 60 + 55

    def __init__(self) -> None:
        self.minute = 0
        self.crew = {
            "ari": MockCrewMember(
                "ari", "Ari Sen", "watch_engineer", "engineering"
            ),
            "iona": MockCrewMember(
                "iona", "Iona Vek", "chief_engineer", "engineering"
            ),
            "lin": MockCrewMember(
                "lin", "Lin Sato", "bridge_officer", "bridge"
            ),
        }
        self.active_watch = {"engineering": "ari", "bridge": "lin"}
        self._next_event = 1
        self._queued: Deque[tuple[str, WorldObservation]] = deque()
        self._history: list[WorldEvent] = []
        self._results: dict[str, tuple[ActionRequest, ActionOutcome]] = {}
        self._reports: dict[str, tuple[str, str]] = {}
        self._handover_due = False

    @property
    def events(self) -> tuple[WorldEvent, ...]:
        """Operator-only audit log: NEVER pass this to an agent."""
        return tuple(self._history)

    @property
    def pending_observations(self) -> int:
        return len(self._queued)

    @property
    def game_time(self) -> float:
        return float(self.minute * 60)

    def advance_to(self, minute: int) -> None:
        """Explicit mock-clock advancement, never a real-time spin loop."""
        if not isinstance(minute, int) or minute < self.minute:
            raise ValueError("World clock must advance monotonically in minutes")
        self.minute = minute

    def _emit(
        self,
        recipient_id: str,
        *,
        kind: str,
        text: str,
        actor_id: str | None = None,
        data: dict[str, str] | None = None,
    ) -> str:
        if recipient_id not in self.crew:
            raise KeyError("Unknown mock recipient")
        event_id = f"mock-{self._next_event:05d}"
        self._next_event += 1
        self._history.append(WorldEvent(
            event_id, self.minute, kind, actor_id, recipient_id, text
        ))
        observation = WorldObservation(
            observation_id=event_id,
            character_id=recipient_id,
            game_time=self.game_time,
            text=text,
            source_event_id=event_id,
            kind=kind,
            data=dict(data or {}),
        )
        self._queued.append((recipient_id, observation))
        return event_id

    def next_observation(self) -> tuple[str, WorldObservation] | None:
        """Deliver one event to its sole authorised recipient."""
        return self._queued.popleft() if self._queued else None

    def sense_pressure_drift(self, summary: str) -> str:
        """Fixture injects a sensor observation at the active engineer's station.

        This is only an observed *unverified concern*, not proof of a broken
        pump or a repair command. Neither on-call chief nor bridge officer
        automatically receives it.
        """
        if not summary.strip() or len(summary) > 320:
            raise ValueError("Sensor summary must contain at most 320 characters")
        watch_id = self.active_watch["engineering"]
        if self.crew[watch_id].location != "engineering":
            raise RuntimeError("Active engineer is away from local instruments")
        return self._emit(
            watch_id, kind="sensor_concern",
            text=f"Local engineering indicator: {summary}",
            data={"summary": summary},
        )

    def bridge_navigation_update(self, summary: str) -> str:
        """Deliver a routine bridge instrument event to its duty officer only."""
        if not summary.strip() or len(summary) > 320:
            raise ValueError("Bridge status must contain at most 320 characters")
        watch_id = self.active_watch["bridge"]
        if self.crew[watch_id].location != "bridge":
            raise RuntimeError("Bridge officer is not at the console")
        return self._emit(
            watch_id, kind="bridge_status",
            text=f"Bridge plot: {summary}",
            data={"summary": summary},
        )

    def announce_handover_due(self) -> bool:
        """One world-authorised duty event, due at 07:55 game time."""
        if self.minute < self.ENGINEERING_HANDOVER_MINUTE:
            raise ValueError("Engineering handover not due yet")
        if self._handover_due or self.active_watch["engineering"] != "ari":
            return False
        self._handover_due = True
        self._emit(
            "ari", kind="handover_due",
            text="Engineering relief due: brief Iona Vek before 08:00.",
            data={"relief_id": "iona"},
        )
        return True

    def _perform(self, request: ActionRequest) -> ActionOutcome:
        actor_id = request.character_id
        if actor_id not in self.crew:
            return ActionOutcome(request.request_id, "failed", "Unknown character")
        if request.verb == "report_handover":
            if not (
                self._handover_due
                and actor_id == self.active_watch["engineering"] == "ari"
                and request.target == "iona"
                and self.crew[actor_id].location == self.crew["iona"].location
            ):
                return ActionOutcome(
                    request.request_id, "failed",
                    "Relief report requires a due watch and co-located personnel",
                )
            # Assertions about machine state remain the sender's statements.
            note = request.arguments.get("summary", "")
            if not isinstance(note, str) or not note.strip() or len(note) > 512:
                return ActionOutcome(
                    request.request_id, "failed", "Invalid handover note"
                )
            if self._reports:
                return ActionOutcome(
                    request.request_id, "failed", "Handover already reported"
                )
            event_id = self._emit(
                "iona", kind="handover_report",
                actor_id=actor_id,
                text=f"Ari reports for relief: {note}",
                data={"sender_id": "ari", "summary": note},
            )
            self._reports[event_id] = (actor_id, "iona")
            self._emit(
                "ari", kind="report_delivered", actor_id=actor_id,
                text=f"Handover report delivered to Iona ({event_id}).",
                data={"report_id": event_id},
            )
            return ActionOutcome(
                request.request_id, "succeeded",
                "Report delivered to relief engineer; watch not yet transferred",
                source_event_id=event_id,
            )
        if request.verb == "accept_watch":
            report_id = request.arguments.get("report_id")
            if not (
                actor_id == "iona"
                and request.target == "ari"
                and self.active_watch["engineering"] == "ari"
                and self._reports.get(report_id) == ("ari", "iona")
                and self.crew["ari"].location == self.crew["iona"].location
            ):
                return ActionOutcome(
                    request.request_id, "failed",
                    "Cannot accept duty without a delivered, matching briefing",
                )
            self.active_watch["engineering"] = "iona"
            event_id = self._emit(
                "iona", kind="watch_transferred", actor_id=actor_id,
                text="Iona accepted engineering watch from Ari.",
                data={"active_engineer_id": "iona", "report_id": report_id},
            )
            self._emit(
                "ari", kind="watch_transferred", actor_id=actor_id,
                text="Iona accepted engineering watch; Ari is relieved.",
                data={"active_engineer_id": "iona", "report_id": report_id},
            )
            return ActionOutcome(
                request.request_id, "succeeded",
                "Engineering watch transferred after acknowledgement",
                source_event_id=event_id,
            )
        return ActionOutcome(
            request.request_id, "failed", "Unsupported mock ship action"
        )

    def submit(
        self, request: ActionRequest, *, drop_ack: bool = False
    ) -> ActionOutcome:
        """Authoritatively execute at most once for each request ID.

        A lost acknowledgment returns 'unknown' *without undoing* the
        committed action. Reconciliation queries the recorded outcome.
        """
        prior = self._results.get(request.request_id)
        if prior is not None:
            original, recorded = prior
            if request != original:
                raise ValueError("Request ID collision with changed action data")
        else:
            recorded = self._perform(request)
            self._results[request.request_id] = (request, recorded)
        if drop_ack:
            return ActionOutcome(
                request.request_id, "unknown", "Acknowledgment lost"
            )
        return recorded

    def reconcile(
        self, request_id: str, *, character_id: str
    ) -> ActionOutcome:
        """Check the outcome without replaying the physical/social action."""
        recorded = self._results.get(request_id)
        if recorded is None:
            return ActionOutcome(request_id, "unknown", "No recorded outcome")
        if recorded[0].character_id != character_id:
            raise PermissionError("Cannot inspect another character's action")
        return recorded[1]
