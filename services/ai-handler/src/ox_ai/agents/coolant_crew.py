"""Event-driven P2 cooling crew: scoped memories, GOAP, and radio coordination.

Lin relays bridge telemetry; Ari handles local engineering using the shared
GOAP search engine; Iona approves commissioning only after her own inspection.
No controller reads MockCoolantWorld internals or another agent's memories.
"""

from __future__ import annotations

from dataclasses import asdict

from ox_ai.agents.crew import CrewIdentity
from ox_ai.agents.mock_watch import MockWatchAgent, default_watch_agents
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.ports.base import ActionOutcome, ActionRequest, WorldObservation


_PUMP_FACTS = frozenset({
    "pump_normal", "pump_low_pressure", "pump_isolated", "pump_repaired",
})


def coolant_actions() -> tuple[GoapAction, ...]:
    """Authored equipment expertise; live condition is learned by inspection."""
    return (
        GoapAction(
            "isolate", frozenset({"pump_low_pressure"}),
            frozenset({"pump_isolated"}), frozenset({"pump_low_pressure"}),
            verb="isolate_pump", target="pump",
        ),
        GoapAction(
            "repair", frozenset({"pump_isolated"}),
            frozenset({"pump_repaired"}), frozenset({"pump_isolated"}),
            verb="repair_pump", target="pump",
        ),
        GoapAction(
            "commission", frozenset({"pump_repaired", "chief_release"}),
            frozenset({"pump_normal"}), frozenset({"pump_repaired"}),
            verb="commission_pump", target="pump",
        ),
    )


class CoolantCrewAgent(MockWatchAgent):
    """A role-local policy; GOAP effects are predictions, never actual facts."""

    def __init__(self, identity: CrewIdentity, assignment: str) -> None:
        super().__init__(identity, assignment)
        self._planner = GoapPlanner(coolant_actions())
        self._actions = {a.name: a for a in self._planner.actions}
        self._facts: set[str] = set()
        self._plan: tuple[GoapAction, ...] = ()
        self._plan_goal: frozenset[str] = frozenset()
        self._alarm_id: str | None = None
        self._release_request_id: str | None = None
        self._release_requested = False
        self._chief_inspected = False
        self._need_inspection = False
        self._verified_normal = False
        self._alert_sent = False
        self._report_sent = False
        self.planning_calls = 0
        self.expanded_states = 0
        self.replans = 0

    @property
    def beliefs(self) -> frozenset[str]:
        return frozenset(self._facts)

    @property
    def plan_names(self) -> tuple[str, ...]:
        return tuple(action.name for action in self._plan)

    def _set_pump(self, state: str) -> None:
        if state not in {"normal", "low_pressure", "isolated", "repaired"}:
            raise ValueError("Unsupported character-visible pump state")
        self._facts.difference_update(_PUMP_FACTS)
        self._facts.add(f"pump_{state}")

    def _plan_for(self, goal: frozenset[str]) -> GoapAction:
        if (
            self._plan_goal != goal
            or not self._plan
            or not self._plan[0].applicable(self._facts)
        ):
            planned = self._planner.plan(self._facts, goal)
            if not planned.actions:
                raise RuntimeError("GOAP has no work despite unmet objective")
            self._plan = planned.actions
            self._plan_goal = goal
            self.planning_calls += 1
            self.expanded_states += planned.expanded_states
        return self._plan[0]

    def _next_action(self) -> ActionRequest | None:
        """React only when an event arrived or a lost-ACK was reconciled."""
        if self.pending_requests:
            return None
        if self.assignment == "bridge":
            if self._alarm_id and not self._alert_sent:
                self._alert_sent = True
                return self._request(
                    "radio_alert", "ari", {"alarm_id": self._alarm_id},
                )
            return None
        if self.assignment == "relief_engineer":
            if self._release_request_id and not self._chief_inspected:
                self._chief_inspected = True  # inspection attempt is pending
                return self._request("inspect_pump", "pump", {})
            if (
                self._release_request_id
                and self._chief_inspected
                and "pump_repaired" in self._facts
                and "chief_release" not in self._facts
            ):
                self._facts.add("chief_release")  # records intent, not effect
                return self._request(
                    "approve_release", "pump",
                    {"request_id": self._release_request_id},
                )
            return None
        if self.assignment != "outgoing_engineer" or not self._alarm_id:
            return None

        if self._need_inspection or not (_PUMP_FACTS & self._facts):
            self._need_inspection = False  # will be confirmed by readout event
            return self._request("inspect_pump", "pump", {})
        if "pump_low_pressure" in self._facts or "pump_isolated" in self._facts:
            action = self._plan_for(frozenset({"pump_repaired"}))
            return self._request(action.verb, action.target or "pump", {})
        if "pump_repaired" in self._facts:
            if "chief_release" not in self._facts:
                if not self._release_requested:
                    self._release_requested = True
                    return self._request("request_release", "pump", {})
                return None
            action = self._plan_for(frozenset({"pump_normal"}))
            return self._request(action.verb, action.target or "pump", {})
        if "pump_normal" in self._facts:
            if not self._verified_normal:
                return self._request("inspect_pump", "pump", {})
            if not self._report_sent:
                self._report_sent = True
                return self._request(
                    "report_resolved", "pump", {"alarm_id": self._alarm_id},
                )
        return None

    def observe(
        self,
        observation: WorldObservation,
        *,
        expected_revision: int | None = None,
    ) -> ActionRequest | None:
        if observation.observation_id in self._seen:
            # Base observe verifies recipient and revision for new events.
            return super().observe(
                observation, expected_revision=expected_revision
            )
        original = super().observe(
            observation, expected_revision=expected_revision
        )
        if original is not None:
            return original
        kind = observation.kind
        data = observation.data
        if kind == "coolant_alarm" and self.assignment == "bridge":
            self._alarm_id = observation.observation_id
        elif kind == "radio_alert" and self.assignment == "outgoing_engineer":
            self._alarm_id = data["alarm_id"]
            self._need_inspection = True
        elif kind == "release_request" and self.assignment == "relief_engineer":
            self._release_request_id = data["request_id"]
            self._chief_inspected = False
        elif kind == "pump_readout":
            self._set_pump(data["state"])
            if self.assignment == "outgoing_engineer":
                self._need_inspection = False
                self._verified_normal = data["state"] == "normal"
                if data["chief_released"] == "yes":
                    self._facts.add("chief_release")
            elif self.assignment == "relief_engineer":
                self._chief_inspected = True
        elif kind == "pump_transition":
            if self.assignment == "outgoing_engineer":
                operation = data["operation"]
                self._set_pump(data["state"])
                self._verified_normal = False
                if self._plan and self._plan[0].verb == operation:
                    self._plan = self._plan[1:]
                else:
                    self._plan = ()
                    self._plan_goal = frozenset()
                    self.replans += 1
        elif kind == "pump_refusal":
            if self.assignment == "outgoing_engineer":
                self._set_pump(data["state"])
                self._need_inspection = True
                self._verified_normal = False
                self._plan = ()
                self._plan_goal = frozenset()
                self.replans += 1
        elif kind == "urgent_recheck" and self.assignment == "outgoing_engineer":
            self._need_inspection = True
            self._verified_normal = False
            self._plan = ()
            self._plan_goal = frozenset()
            self.replans += 1
        elif kind == "release_granted" and self.assignment == "outgoing_engineer":
            if data.get("approver_id") == "iona":
                self._facts.add("chief_release")
        elif kind == "release_recorded" and self.assignment == "relief_engineer":
            self._facts.add("chief_release")
        # A completed radio report cannot mutate the agent's pump beliefs.
        return self._next_action()

    def continue_after_reconciliation(self) -> ActionRequest | None:
        """Only advance after the world resolved an ambiguous request ID."""
        return self._next_action()

    def discard_stale(self, request: ActionRequest) -> None:
        """Reject an undelivered decision superseded by a newer observation."""
        if request.agent_revision >= self.revision:
            raise ValueError("Only a stale proposal may be discarded")
        if self._pending.get(request.request_id) != request:
            raise KeyError("Unknown proposal")
        del self._pending[request.request_id]

    def record_outcome(self, outcome: ActionOutcome) -> None:
        previous = self._pending.get(outcome.request_id)
        super().record_outcome(outcome)
        if previous is not None and outcome.status == "failed":
            if self.assignment == "outgoing_engineer":
                self._need_inspection = True
                self._verified_normal = False
                self._plan = ()
                self._plan_goal = frozenset()
                self.replans += 1
            if previous.verb == "radio_alert":
                self._alert_sent = False
            if previous.verb == "request_release":
                self._release_requested = False
            if previous.verb == "report_resolved":
                self._report_sent = False

    def snapshot(self) -> dict:
        result = super().snapshot()
        result["coolant"] = {
            "facts": sorted(self._facts),
            "plan": [a.name for a in self._plan],
            "plan_goal": sorted(self._plan_goal),
            "alarm_id": self._alarm_id,
            "release_request_id": self._release_request_id,
            "release_requested": self._release_requested,
            "chief_inspected": self._chief_inspected,
            "need_inspection": self._need_inspection,
            "verified_normal": self._verified_normal,
            "alert_sent": self._alert_sent,
            "report_sent": self._report_sent,
            "planning_calls": self.planning_calls,
            "expanded_states": self.expanded_states,
            "replans": self.replans,
        }
        return result

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> CoolantCrewAgent:
        agent = super().from_snapshot(snapshot)
        state = snapshot["coolant"]
        agent._facts = set(state["facts"])
        agent._plan = tuple(agent._actions[key] for key in state["plan"])
        agent._plan_goal = frozenset(state["plan_goal"])
        agent._alarm_id = state["alarm_id"]
        agent._release_request_id = state["release_request_id"]
        agent._release_requested = state["release_requested"]
        agent._chief_inspected = state["chief_inspected"]
        agent._need_inspection = state["need_inspection"]
        agent._verified_normal = state["verified_normal"]
        agent._alert_sent = state["alert_sent"]
        agent._report_sent = state["report_sent"]
        agent.planning_calls = state["planning_calls"]
        agent.expanded_states = state["expanded_states"]
        agent.replans = state["replans"]
        return agent


def default_coolant_agents() -> dict[str, CoolantCrewAgent]:
    """Reuse the same three identity/duty briefs as watch handover."""
    return {
        key: CoolantCrewAgent(base.identity, base.assignment)
        for key, base in default_watch_agents().items()
    }
