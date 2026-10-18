"""P2 cooling incident on the existing authoritative mock watch world.

No NPC gets this world's pump_state, event journal or roster directly.
They receive individually addressed observations from legitimate instruments,
radios or their own command attempts. All equipment effects are adjudicated
here, with request-id deduplication inherited from MockWatchWorld.
"""

from __future__ import annotations

from dataclasses import dataclass

from ox_ai.ports.base import ActionOutcome, ActionRequest
from ox_ai.ports.mock.watch_world import MockWatchWorld


@dataclass(frozen=True, slots=True)
class PumpEvent:
    event_id: str
    minute: int
    operation: str
    before: str
    after: str
    actor_id: str | None


class MockCoolantWorld(MockWatchWorld):
    """Minimal world-side cooling subsystem and role-aware communications."""

    TRANSITIONS = {
        "isolate_pump": ("low_pressure", "isolated"),
        "repair_pump": ("isolated", "repaired"),
        "commission_pump": ("repaired", "normal"),
    }

    def __init__(self) -> None:
        super().__init__()
        self.pump_state = "normal"
        self.chief_release_required = True
        self.chief_released = False
        self._pump_seq = 0
        self._pump_version = 0
        self._pump_history: list[PumpEvent] = []
        self._active_alarm: str | None = None
        self._release_request: str | None = None
        self._release_inspection_version: int | None = None
        self._last_inspected_version: dict[str, int] = {}
        self._safety_epoch = 0
        self._inspected_safety_epoch: dict[str, int] = {}
        self._drop_ack_once: set[str] = set()
        self._incident_closed = False

    @property
    def pump_history(self) -> tuple[PumpEvent, ...]:
        """Operator-only ground truth, never an agent observation."""
        return tuple(self._pump_history)

    @property
    def incident_closed(self) -> bool:
        return self._incident_closed

    def _record_pump(
        self, operation: str, before: str, after: str, actor: str | None
    ) -> None:
        self._pump_seq += 1
        self._pump_version += 1
        self._pump_history.append(PumpEvent(
            f"p01-{self._pump_seq:04d}", self.minute,
            operation, before, after, actor,
        ))

    def trigger_fault(self) -> str:
        """Operator injects fault; bridge telemetry is the initial observer."""
        if self.pump_state != "normal" or self._active_alarm is not None:
            raise ValueError("A cooling fault is already active")
        before = self.pump_state
        self.pump_state = "low_pressure"
        self.chief_released = False
        self._incident_closed = False
        self._record_pump("fault", before, self.pump_state, None)
        bridge = self.active_watch["bridge"]
        if bridge != "lin" or self.crew[bridge].location != "bridge":
            raise RuntimeError("No on-duty officer at the bridge telemetry")
        self._active_alarm = self._emit(
            bridge,
            kind="coolant_alarm",
            text="BRIDGE TELEMETRY: P-01 coolant pressure LOW. Check engineering.",
            data={"equipment": "P-01", "reading": "low_pressure"},
        )
        return self._active_alarm

    def drop_next_ack(self, verb: str) -> None:
        """Operator fault injection: commit command, lose only its response."""
        self._drop_ack_once.add(verb)

    def submit(
        self, request: ActionRequest, *, drop_ack: bool = False
    ) -> ActionOutcome:
        lose = request.verb in self._drop_ack_once
        if lose:
            self._drop_ack_once.remove(request.verb)
        return super().submit(request, drop_ack=drop_ack or lose)

    def urgent_safety_recheck(self) -> str:
        """Urgent interruption invalidates an engineer's previous clearance."""
        if self.pump_state == "normal" or not self._active_alarm:
            raise ValueError("No active incident to interrupt")
        self._safety_epoch += 1
        return self._emit(
            "ari",
            kind="urgent_recheck",
            text="URGENT: new safety telemetry. Reinspect P-01 before more work.",
            data={"reason": "new safety telemetry"},
        )

    def _allowed(
        self, actor: str, role: str, target: str | None
    ) -> bool:
        if target != "pump" or actor not in self.crew:
            return False
        if self.crew[actor].location != "engineering":
            return False
        if role == "watch":
            return (
                actor == "ari"
                and self.active_watch["engineering"] == "ari"
                and self.crew[actor].role == "watch_engineer"
            )
        if role == "chief":
            return actor == "iona" and self.crew[actor].role == "chief_engineer"
        return False

    def _inspection(self, actor: str, request: ActionRequest) -> ActionOutcome:
        self._last_inspected_version[actor] = self._pump_version
        self._inspected_safety_epoch[actor] = self._safety_epoch
        observation_id = self._emit(
            actor,
            actor_id=actor,
            kind="pump_readout",
            text=(
                f"Local P-01: {self.pump_state.upper()}; "
                f"chief release {'GRANTED' if self.chief_released else 'REQUIRED'}."
            ),
            data={
                "state": self.pump_state,
                "chief_released": "yes" if self.chief_released else "no",
                "version": str(self._pump_version),
            },
        )
        return ActionOutcome(
            request.request_id, "succeeded",
            "Local engineering readout delivered", observation_id,
        )

    def _operation(self, request: ActionRequest) -> ActionOutcome:
        actor = request.character_id
        verb = request.verb
        before, after = self.TRANSITIONS[verb]
        if not self._allowed(actor, "watch", request.target):
            return ActionOutcome(
                request.request_id, "failed", "Engineering duty and proximity required",
            )
        if self.pump_state != before:
            return self._refuse(
                request, f"Wrong pump state: currently {self.pump_state}"
            )
        if self._inspected_safety_epoch.get(actor, -1) < self._safety_epoch:
            return self._refuse(request, "Urgent safety reinspection required")
        if verb == "commission_pump" and (
            self.chief_release_required and not self.chief_released
        ):
            return self._refuse(request, "Chief engineer release required")
        self.pump_state = after
        self._record_pump(verb.removesuffix("_pump"), before, after, actor)
        event_id = self._emit(
            actor,
            actor_id=actor,
            kind="pump_transition",
            text=f"P-01: {before} -> {after}.",
            data={
                "operation": verb,
                "before": before,
                "state": after,
                "version": str(self._pump_version),
            },
        )
        return ActionOutcome(
            request.request_id, "succeeded",
            f"World applied {verb}: {before} -> {after}", event_id,
        )

    def _refuse(self, request: ActionRequest, reason: str) -> ActionOutcome:
        event_id = self._emit(
            request.character_id,
            actor_id=request.character_id,
            kind="pump_refusal",
            text=f"P-01 operation refused: {reason}.",
            data={"state": self.pump_state, "reason": reason},
        )
        return ActionOutcome(request.request_id, "failed", reason, event_id)

    def _radio_alert(self, request: ActionRequest) -> ActionOutcome:
        if (
            request.character_id != self.active_watch["bridge"]
            or self.crew[request.character_id].location != "bridge"
            or request.target != "ari"
            or request.arguments.get("alarm_id") != self._active_alarm
        ):
            return ActionOutcome(
                request.request_id, "failed", "No authorised bridge alarm to relay",
            )
        event_id = self._emit(
            "ari", actor_id="lin", kind="radio_alert",
            text="Lin reports bridge cooling alarm for P-01; inspect locally.",
            data={"sender_id": "lin", "alarm_id": self._active_alarm},
        )
        return ActionOutcome(
            request.request_id, "succeeded", "Bridge radio alert sent", event_id,
        )

    def _request_release(self, request: ActionRequest) -> ActionOutcome:
        if not self._allowed(request.character_id, "watch", request.target):
            return ActionOutcome(
                request.request_id, "failed", "On-duty engineer must request release",
            )
        if self.pump_state != "repaired" or self.chief_released:
            return self._refuse(request, "No repaired pump awaiting chief release")
        if self._release_request is not None:
            return self._refuse(request, "Release already requested")
        self._release_request = request.request_id
        event_id = self._emit(
            "iona", actor_id="ari", kind="release_request",
            text="Ari requests chief review of repaired P-01 before commissioning.",
            data={"sender_id": "ari", "request_id": request.request_id},
        )
        self._emit(
            "ari", actor_id="ari", kind="release_requested",
            text="Chief release request delivered to Iona.",
            data={"request_id": request.request_id},
        )
        return ActionOutcome(
            request.request_id, "succeeded", "Chief review requested", event_id,
        )

    def _approve_release(self, request: ActionRequest) -> ActionOutcome:
        if not self._allowed(request.character_id, "chief", request.target):
            return ActionOutcome(
                request.request_id, "failed", "Chief must be physically at P-01",
            )
        if (
            self._release_request is None
            or request.arguments.get("request_id") != self._release_request
            or self.pump_state != "repaired"
            or self._last_inspected_version.get("iona") != self._pump_version
            or self.chief_released
        ):
            return ActionOutcome(
                request.request_id, "failed",
                "Chief approval needs an outstanding request and fresh local inspection",
            )
        self.chief_released = True
        event_id = self._emit(
            "ari", actor_id="iona", kind="release_granted",
            text="Iona verified P-01 locally and authorised commissioning.",
            data={"approver_id": "iona", "request_id": self._release_request},
        )
        self._emit(
            "iona", actor_id="iona", kind="release_recorded",
            text="Chief release recorded for P-01.",
            data={"request_id": self._release_request},
        )
        return ActionOutcome(
            request.request_id, "succeeded", "Chief release authorised", event_id,
        )

    def _report_resolved(self, request: ActionRequest) -> ActionOutcome:
        if (
            not self._allowed(request.character_id, "watch", request.target)
            or self.pump_state != "normal"
            or self._last_inspected_version.get("ari") != self._pump_version
            or self._incident_closed
            or request.arguments.get("alarm_id") != self._active_alarm
        ):
            return ActionOutcome(
                request.request_id, "failed",
                "Verified normal-pressure readout required before closing incident",
            )
        self._incident_closed = True
        event_id = self._emit(
            "lin", actor_id="ari", kind="incident_resolved",
            text="Ari reports P-01 repaired, commissioned and checked NORMAL.",
            data={"sender_id": "ari", "alarm_id": self._active_alarm},
        )
        self._emit(
            "iona", actor_id="ari", kind="incident_resolved",
            text="Ari confirms normal P-01 pressure after chief release.",
            data={"sender_id": "ari", "alarm_id": self._active_alarm},
        )
        return ActionOutcome(
            request.request_id, "succeeded", "Incident report delivered", event_id,
        )

    def _perform(self, request: ActionRequest) -> ActionOutcome:
        verb = request.verb
        if verb == "radio_alert":
            return self._radio_alert(request)
        if verb == "inspect_pump":
            if not (
                self._allowed(request.character_id, "watch", request.target)
                or self._allowed(request.character_id, "chief", request.target)
            ):
                return ActionOutcome(
                    request.request_id, "failed", "No local engineering access",
                )
            return self._inspection(request.character_id, request)
        if verb in self.TRANSITIONS:
            return self._operation(request)
        if verb == "request_release":
            return self._request_release(request)
        if verb == "approve_release":
            return self._approve_release(request)
        if verb == "report_resolved":
            return self._report_resolved(request)
        return super()._perform(request)
