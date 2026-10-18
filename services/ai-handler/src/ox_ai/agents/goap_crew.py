"""Zero-inference shipboard engineer using belief-driven GOAP.

This adapter deliberately does NOT construct Concordia or call any model.
It implements the small observe/decide/outcome surface already consumed by
the real Evennia command harness, using the same character-scoped text.
Only observation of an executed command can confirm a planned effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Sequence
import uuid

from ox_ai.agents.crew import CommandOption, CrewIdentity, StaleAgentRevision
from ox_ai.planning.goap import GoapAction, GoapPlanner, PlanUnavailable
from ox_ai.ports.base import ActionOutcome, ActionRequest, WorldObservation


_LOCATION_FACTS = frozenset({"at_bridge", "at_passage", "at_engineering"})
_PUMP_FACTS = frozenset({
    "pump_normal", "pump_low_pressure", "pump_isolated", "pump_repaired"
})
_STATE_FACT = {
    "normal": "pump_normal",
    "low pressure": "pump_low_pressure",
    "isolated": "pump_isolated",
    "repaired": "pump_repaired",
}
_ROOMS = {
    "Bridge": "at_bridge",
    "Connecting Passage": "at_passage",
    "Engineering": "at_engineering",
}
_ROOM_PATTERN = re.compile(
    r"(?m)^(Bridge|Connecting Passage|Engineering)\s*$"
)
_READOUT = re.compile(
    r"(?mi)^Cooling Pump P-01:\s*(NORMAL|LOW PRESSURE|ISOLATED|REPAIRED)\s*$"
)
_TRANSITION = re.compile(
    r"(?mi)^P-01:\s*(?:normal|low pressure|isolated|repaired)"
    r"\s*->\s*(normal|low pressure|isolated|repaired)\.\s*$"
)
_REJECTED_STATE = re.compile(
    r"(?mi)^Cannot (?:isolate|repair|commission) P-01 while it is "
    r"(normal|low pressure|isolated|repaired)\.\s*$"
)


def pump_action_model() -> tuple[GoapAction, ...]:
    """Known ship layout, command affordances and expected causal effects.

    This represents an engineer's training and map knowledge, not access to
    current machine state. Missing tools, permissions and extra prerequisites
    would require their own authored actions and predicates in later domains.
    """
    return (
        GoapAction(
            "inspect_bridge_console", frozenset({"at_bridge"}),
            frozenset({"status_known"}), verb="inspect", target="console",
        ),
        GoapAction(
            "inspect_engineering_pump", frozenset({"at_engineering"}),
            frozenset({"status_known"}), verb="inspect", target="pump",
        ),
        GoapAction(
            "move_aft", frozenset({"at_bridge"}),
            frozenset({"at_passage"}), frozenset({"at_bridge"}), verb="aft",
        ),
        GoapAction(
            "move_fore", frozenset({"at_passage"}),
            frozenset({"at_bridge"}), frozenset({"at_passage"}), verb="fore",
        ),
        GoapAction(
            "move_engineering", frozenset({"at_passage"}),
            frozenset({"at_engineering"}), frozenset({"at_passage"}),
            verb="engineering",
        ),
        GoapAction(
            "move_out", frozenset({"at_engineering"}),
            frozenset({"at_passage"}), frozenset({"at_engineering"}), verb="out",
        ),
        GoapAction(
            "isolate_pump",
            frozenset({"at_engineering", "pump_low_pressure"}),
            frozenset({"pump_isolated"}), frozenset({"pump_low_pressure"}),
            verb="isolate", target="pump",
        ),
        GoapAction(
            "repair_pump",
            frozenset({"at_engineering", "pump_isolated"}),
            frozenset({"pump_repaired", "repair_done"}),
            frozenset({"pump_isolated"}), verb="repair", target="pump",
        ),
        GoapAction(
            "commission_pump",
            frozenset({"at_engineering", "pump_repaired"}),
            frozenset({"pump_normal"}), frozenset({"pump_repaired"}),
            verb="commission", target="pump",
        ),
        GoapAction(
            "verify_normal",
            frozenset({"at_engineering", "pump_normal"}),
            frozenset({"normal_verified"}), verb="inspect", target="pump",
        ),
    )


@dataclass(frozen=True, slots=True)
class ZeroInferenceUsage:
    """This policy does not have an inference client or network fallback."""

    total_calls: int = 0


class GoapCrewAgent:
    """Belief-based GOAP controller with world-observation reconciliation."""

    def __init__(
        self,
        identity: CrewIdentity,
        *,
        journal_path: Path | None = None,
    ) -> None:
        self.identity = identity
        self.usage = ZeroInferenceUsage()
        self._planner = GoapPlanner(pump_action_model())
        self._journal_path = Path(journal_path) if journal_path else None
        self._revision = 0
        self._observations: set[str] = set()
        self._last_game_time: float | None = None
        self._facts: set[str] = set()
        self._plan: tuple[GoapAction, ...] = ()
        self._plan_goal: frozenset[str] = frozenset()
        self._pending: dict[str, tuple[ActionRequest, GoapAction | None]] = {}
        self._awaiting: tuple[ActionRequest, GoapAction] | None = None
        self._blocked: set[str] = set()
        self._terminal = False
        self.planning_calls = 0
        self.planning_expansions = 0
        self.replans = 0

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def beliefs(self) -> frozenset[str]:
        return frozenset(self._facts)

    @property
    def pending_requests(self) -> tuple[ActionRequest, ...]:
        return tuple(req for req, _ in self._pending.values())

    @property
    def remaining_plan(self) -> tuple[str, ...]:
        return tuple(action.name for action in self._plan)

    def _record(self, event_type: str, **details: object) -> None:
        if self._journal_path is None:
            return
        event = {
            "event_type": event_type,
            "agent_id": self.identity.agent_id,
            "character_id": self.identity.character_id,
            "revision": self._revision,
            "game_time": self._last_game_time,
            "wall_time_utc": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self._journal_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _command(action: GoapAction) -> str:
        return action.verb + (f" {action.target}" if action.target else "")

    def _set_pump_state(self, state: str) -> None:
        self._facts.difference_update(_PUMP_FACTS)
        self._facts.add(_STATE_FACT[state.lower()])
        self._facts.add("status_known")
        # Any changed or uncertain state requires another physical inspection.
        self._facts.discard("normal_verified")

    def observe(self, observation: WorldObservation) -> bool:
        """Update beliefs from only this character's delivered world text."""
        if observation.character_id != self.identity.character_id:
            raise PermissionError("Observation addressed to another character")
        if observation.observation_id in self._observations:
            return False
        self._observations.add(observation.observation_id)
        self._revision += 1
        self._last_game_time = observation.game_time

        before = frozenset(self._facts)
        # Evennia location headings use |c and |n markup in the MUD output.
        plain = observation.text.replace("|c", "").replace("|n", "")
        rooms = list(_ROOM_PATTERN.finditer(plain))
        if rooms:
            self._facts.difference_update(_LOCATION_FACTS)
            self._facts.add(_ROOMS[rooms[-1].group(1)])

        readouts = list(_READOUT.finditer(plain))
        transitions = list(_TRANSITION.finditer(plain))
        refusals = list(_REJECTED_STATE.finditer(plain))
        if readouts:
            self._set_pump_state(readouts[-1].group(1))
        elif transitions:
            self._set_pump_state(transitions[-1].group(1))
        elif refusals:
            # A rejection with an explicit actual state is useful evidence.
            self._set_pump_state(refusals[-1].group(1))

        awaiting = self._awaiting
        if awaiting is not None:
            request, action = awaiting
            marker = f"Command '{self._command(action)}' returned:\n"
            if marker in observation.text:
                # These are confirmed *observed* effects. A successful submit
                # receipt alone never marks an action as physically successful.
                if action.name.startswith("move_"):
                    confirmed = bool(rooms) and action.adds.issubset(self._facts)
                elif action.name == "verify_normal":
                    confirmed = bool(readouts) and (
                        readouts[-1].group(1).lower() == "normal"
                    )
                    if confirmed:
                        self._facts.add("normal_verified")
                elif action.name.startswith("inspect_"):
                    confirmed = bool(readouts)
                else:
                    confirmed = bool(transitions) and action.adds.intersection(
                        _PUMP_FACTS
                    ).issubset(self._facts)
                    if confirmed and action.name == "repair_pump":
                        self._facts.add("repair_done")

                if confirmed and self._plan and self._plan[0] == action:
                    self._plan = self._plan[1:]
                    self._record("action_confirmed", action=action.name)
                else:
                    self._plan = ()
                    self._plan_goal = frozenset()
                    self.replans += 1
                    if frozenset(self._facts) == before:
                        # Do not blindly repeat an action that returned no
                        # evidence of its effect. It needs changed evidence.
                        self._blocked.add(action.name)
                    self._record(
                        "plan_invalidated",
                        action=action.name,
                        observed_state=sorted(self._facts),
                    )
                self._awaiting = None

        if frozenset(self._facts) != before:
            # New world information can make a previously blocked action safe
            # to reconsider; otherwise avoid retry loops.
            self._blocked.clear()
        self._record(
            "observation",
            observation_id=observation.observation_id,
            source_event_id=observation.source_event_id,
            facts=sorted(self._facts),
            text=observation.text,
        )
        return True

    def _current_goal(self) -> frozenset[str]:
        if "status_known" not in self._facts:
            return frozenset({"status_known"})
        return frozenset({"repair_done", "normal_verified"})

    def decide(
        self,
        choices: Sequence[CommandOption],
        *,
        expected_revision: int | None = None,
    ) -> ActionRequest:
        """Plan from beliefs, select a CURRENTLY offered command, never mutate."""
        if expected_revision is not None and expected_revision != self._revision:
            raise StaleAgentRevision("GOAP observation revision changed")
        if self._pending or self._awaiting:
            raise PlanUnavailable(
                "Unreconciled action; cannot safely issue another command"
            )
        if self._terminal:
            raise PlanUnavailable("The engineer has already finished")
        if len(_LOCATION_FACTS & self._facts) != 1:
            raise PlanUnavailable("Engineer has not observed a known location")

        options = {(o.verb, o.target): o for o in choices}
        if len(options) != len(choices):
            raise ValueError("Command options must be unique")
        goal = self._current_goal()
        if goal.issubset(self._facts):
            if ("finish", None) not in options:
                raise PlanUnavailable("Finish is not currently offered")
            action = None
            option = options[("finish", None)]
        else:
            if (
                self._plan_goal != goal
                or not self._plan
                or not self._plan[0].applicable(self._facts)
            ):
                self.planning_calls += 1
                planned = self._planner.plan(
                    self._facts, goal, excluded=self._blocked
                )
                self.planning_expansions += planned.expanded_states
                if not planned.actions:
                    raise PlanUnavailable("Goal not met, but no action was planned")
                self._plan = planned.actions
                self._plan_goal = goal
                self._record(
                    "plan_generated",
                    goal=sorted(goal),
                    actions=[a.name for a in planned.actions],
                    cost=planned.total_cost,
                    expanded_states=planned.expanded_states,
                )
            action = self._plan[0]
            option = options.get((action.verb, action.target))
            if option is None:
                # Known procedures are not permission to execute a command:
                # the game must actually offer it at the current location.
                raise PlanUnavailable(
                    f"Planned action {action.name} is not currently offered"
                )

        request = ActionRequest(
            request_id=uuid.uuid4().hex,
            character_id=self.identity.character_id,
            verb=option.verb,
            target=option.target,
            arguments=dict(option.arguments),
            agent_revision=self._revision,
        )
        self._pending[request.request_id] = (request, action)
        self._record(
            "action_proposed",
            request_id=request.request_id,
            command=option.verb,
            target=option.target,
            planned_action=action.name if action else "finish",
            model_requests=0,
        )
        return request

    def record_outcome(self, outcome: ActionOutcome) -> None:
        """Distinguish command delivery from confirmed game-side effects."""
        if outcome.request_id not in self._pending:
            raise KeyError(f"Unknown GOAP request {outcome.request_id}")
        request, action = self._pending[outcome.request_id]
        self._record(
            "world_outcome",
            request_id=request.request_id,
            status=outcome.status,
            description=outcome.description,
            source_event_id=outcome.source_event_id,
        )
        if outcome.status == "unknown" or outcome.status == "pending":
            # No blind retry after a possibly executed physical operation.
            return
        del self._pending[request.request_id]
        if action is None:
            if outcome.status != "succeeded":
                raise PlanUnavailable("Finish was not acknowledged")
            self._terminal = True
        elif outcome.status == "succeeded":
            # The harness currently reports that the command was delivered;
            # only the subsequent in-world text can confirm its effects.
            self._awaiting = (request, action)
        else:
            self._blocked.add(action.name)
            self._plan = ()
            self._plan_goal = frozenset()
            self.replans += 1
