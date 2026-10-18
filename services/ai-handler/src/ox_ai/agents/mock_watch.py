"""Three distinct, non-generative watchkeepers with private event memories.

This is a narrow P2 policy, not a language model or simulated personality.
The supervisor never reads an agent's memories to choose world actions.
"""

from __future__ import annotations

from dataclasses import asdict
import uuid

from ox_ai.agents.crew import CrewIdentity, StaleAgentRevision
from ox_ai.ports.base import ActionOutcome, ActionRequest, WorldObservation


class MockWatchAgent:
    """Handle routine events using only this character's actual observations."""

    def __init__(self, identity: CrewIdentity, assignment: str):
        if assignment not in ("outgoing_engineer", "relief_engineer", "bridge"):
            raise ValueError("Unknown watch assignment")
        self.identity = identity
        self.assignment = assignment
        self.revision = 0
        self._seen: set[str] = set()
        self._memories: list[dict] = []
        self._concerns: list[tuple[str, str]] = []
        self._pending: dict[str, ActionRequest] = {}
        self._active_watch = assignment != "relief_engineer"
        self.inference_calls = 0

    @property
    def memories(self) -> tuple[dict, ...]:
        """Private event journal; an operator may inspect, other agents may not."""
        return tuple(dict(item) for item in self._memories)

    @property
    def pending_requests(self) -> tuple[ActionRequest, ...]:
        return tuple(self._pending.values())

    @property
    def active_watch(self) -> bool:
        return self._active_watch

    def _request(
        self, verb: str, target: str, arguments: dict[str, str]
    ) -> ActionRequest:
        if self._pending:
            raise RuntimeError("Unreconciled action: never retry or stack requests")
        result = ActionRequest(
            request_id=uuid.uuid4().hex,
            character_id=self.identity.character_id,
            verb=verb,
            target=target,
            arguments=arguments,
            agent_revision=self.revision,
        )
        self._pending[result.request_id] = result
        return result

    def observe(
        self,
        observation: WorldObservation,
        *,
        expected_revision: int | None = None,
    ) -> ActionRequest | None:
        """Consume one character-scoped event; optionally propose an action."""
        if expected_revision is not None and expected_revision != self.revision:
            raise StaleAgentRevision("Mock watch revision changed before delivery")
        if observation.character_id != self.identity.character_id:
            raise PermissionError("Private event addressed to another character")
        if observation.observation_id in self._seen:
            return None
        self._seen.add(observation.observation_id)
        self.revision += 1
        self._memories.append({
            "observation_id": observation.observation_id,
            "source_event_id": observation.source_event_id,
            "game_time": observation.game_time,
            "kind": observation.kind,
            "text": observation.text,
            "data": dict(observation.data),
        })

        if observation.kind == "sensor_concern":
            if self.assignment == "outgoing_engineer":
                self._concerns.append((
                    observation.source_event_id or observation.observation_id,
                    observation.data["summary"],
                ))
        elif observation.kind == "handover_due":
            if self.assignment == "outgoing_engineer" and self._active_watch:
                # Not an established machine fact, just what Ari observed.
                summary = (
                    "; ".join(
                        f"Unverified observation {event_id}: {note}"
                        for event_id, note in self._concerns
                    )
                    if self._concerns else
                    "No outstanding concerns reported on this watch."
                )
                return self._request(
                    "report_handover",
                    observation.data["relief_id"],
                    {"summary": summary},
                )
        elif observation.kind == "handover_report":
            if self.assignment == "relief_engineer" and not self._active_watch:
                return self._request(
                    "accept_watch", observation.data["sender_id"],
                    {"report_id": observation.observation_id},
                )
        elif observation.kind == "watch_transferred":
            if self.assignment == "outgoing_engineer":
                self._active_watch = False
            elif self.assignment == "relief_engineer":
                self._active_watch = True
        return None

    def record_outcome(self, outcome: ActionOutcome) -> None:
        """A lost ACK leaves its request unresolved, not eligible for retry."""
        if outcome.request_id not in self._pending:
            raise KeyError("No matching pending character request")
        if outcome.status in ("succeeded", "failed"):
            del self._pending[outcome.request_id]

    def snapshot(self) -> dict:
        """Serializable private memory and unacknowledged action metadata."""
        return {
            "identity": asdict(self.identity),
            "assignment": self.assignment,
            "revision": self.revision,
            "seen": sorted(self._seen),
            "memories": list(self._memories),
            "concerns": [list(item) for item in self._concerns],
            "pending": [asdict(item) for item in self._pending.values()],
            "active_watch": self._active_watch,
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> MockWatchAgent:
        agent = cls(
            CrewIdentity(**snapshot["identity"]), snapshot["assignment"]
        )
        agent.revision = snapshot["revision"]
        agent._seen = set(snapshot["seen"])
        agent._memories = list(snapshot["memories"])
        agent._concerns = [tuple(item) for item in snapshot["concerns"]]
        agent._pending = {
            item["request_id"]: ActionRequest(**item)
            for item in snapshot["pending"]
        }
        agent._active_watch = snapshot["active_watch"]
        return agent


def default_watch_agents() -> dict[str, MockWatchAgent]:
    """Distinct identities; never construct one shared global NPC brain."""
    return {
        "ari": MockWatchAgent(CrewIdentity(
            agent_id="ox.crew.ari",
            character_id="ari",
            name="Ari Sen",
            duty="Engineering watch 00:00-08:00",
            goal="Keep a reliable maintenance log and brief my relief",
        ), "outgoing_engineer"),
        "iona": MockWatchAgent(CrewIdentity(
            agent_id="ox.crew.iona",
            character_id="iona",
            name="Iona Vek",
            duty="Chief engineer, on-call relief at 07:55",
            goal="Accept verified watch handovers and retain reported concerns",
        ), "relief_engineer"),
        "lin": MockWatchAgent(CrewIdentity(
            agent_id="ox.crew.lin",
            character_id="lin",
            name="Lin Sato",
            duty="Bridge watch 00:00-08:00",
            goal="Maintain my assigned bridge watch",
        ), "bridge"),
    }
