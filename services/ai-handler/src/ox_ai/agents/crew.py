"""Single Concordia-powered Ox crew member: Prototype 1, gate P1.

The member receives only character-scoped world observations. Its Concordia
entity selects *proposed* commands from caller-supplied choices; no selected
text can directly mutate the authoritative world. The handler can checkpoint
native Concordia state and reconcile outstanding requests after restoration.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any
import uuid

from ox_ai.inference.usage import MeteredModel
from ox_ai.memory.seeds import SeededMemory, validate_seed_memories
from ox_ai.memory.temporal import TemporalMemory, TemporalMemoryBank
from ox_ai.memory.interpretation import InterpretationBank
from ox_ai.memory.views import InterpretationReadView, TemporalMemoryReadView
from ox_ai.memory.clock import MemoryClockBridge
from ox_ai.ports.base import ActionOutcome, ActionRequest, WorldObservation


@dataclass(frozen=True, slots=True)
class CrewIdentity:
    """Stable Ox agent-to-game-character identity and current brief."""

    agent_id: str
    character_id: str
    name: str
    duty: str
    goal: str


@dataclass(frozen=True, slots=True)
class CommandOption:
    """A single proposed world command; world rules still validate it."""

    label: str
    verb: str
    target: str | None = None
    arguments: Mapping[str, str] = field(default_factory=dict)


class StaleAgentRevision(ValueError):
    """A decision was based on an obsolete agent observation revision."""


class CrewAgent:
    """Own one native Concordia entity and its Ox-side action accounting.

    This synchronous P1 component deliberately has no game transport or
    background scheduler. A later supervisor will decide when it is invoked.
    """

    CHECKPOINT_VERSION = 1

    def __init__(
        self,
        identity: CrewIdentity,
        model: Any,
        *,
        journal_path: Path | None = None,
        blueprint: Any | None = None,
        initial_memories: Sequence[SeededMemory] = (),
        memory_projection_enabled: bool = True,
    ) -> None:
        """Construct the Concordia component graph around a supplied model.

        Args:
            identity: One durable agent and its corresponding game character.
            model: Any Concordia LanguageModel-compatible inference client.
            journal_path: Optional append-only JSONL diagnostic journal.
        """
        from concordia.agents.entity_agent_with_logging import EntityAgentWithLogging
        from concordia.components.agent import concat_act_component
        from concordia.components.agent import constant
        from concordia.components.agent import memory
        from concordia.components.agent import observation
        from ox_ai.memory.concordia_context import OxMemoryContext

        self.identity = identity
        # Kept only inside this mind; cloned snapshots can use the same model
        # backend without sharing observations or mutable Concordia components.
        self._model = model
        if blueprint is not None:
            from ox_ai.agents.crew_blueprints import CrewBlueprint
            if not isinstance(blueprint, CrewBlueprint):
                raise TypeError("Blueprint must be a validated CrewBlueprint")
            if identity.agent_id != f"ox.person.{blueprint.person_id}" or identity.name != blueprint.name:
                raise PermissionError("Blueprint identity does not match this agent")
        self.blueprint = blueprint
        if type(memory_projection_enabled) is not bool:
            raise TypeError("Memory projection mode must be boolean")
        self._memory_projection_enabled = memory_projection_enabled
        # Authored recollections are private cognitive data, never world events.
        # Restored agents supply none here: native memory is restored verbatim.
        seeded = validate_seed_memories(initial_memories)
        self._temporal_memories = TemporalMemoryBank.from_seeds(seeded)
        # A person's interpretation is distinct from the event recollection.
        self._interpretations = InterpretationBank.rebuild(self._temporal_memories)
        self.usage = MeteredModel(model)
        self._journal_path = Path(journal_path) if journal_path else None
        self._revision = 0
        # Observation and private-cognition changes independently invalidate
        # detached inference. The latter must not overwrite newly admitted
        # memories simply because no WorldObservation arrived.
        self._cognition_revision = 0
        self._memory_now_turn = 0
        self._memory_clock: MemoryClockBridge | None = None
        self._memory_query_text = ""
        self._seen_observations: set[str] = set()
        self._pending: dict[str, ActionRequest] = {}
        self._last_game_time: float | None = None

        components = {
            "Identity": constant.Constant(
                state=f"You are {identity.name}, a member of the spaceship crew.",
                pre_act_label="Identity",
            ),
            "Duty": constant.Constant(
                state=identity.duty,
                pre_act_label="Assigned duty",
            ),
            "Goal": constant.Constant(
                state=identity.goal,
                pre_act_label="Goal",
            ),
            # Read only: projects relevant Ox private histories at PRE_ACT.
            # It must be bound to this agent (not its original when forked).
            "OxMemoryContext": OxMemoryContext(self),
            "ObservationToMemory": observation.ObservationToMemory(),
            observation.DEFAULT_OBSERVATION_COMPONENT_KEY: (
                observation.LastNObservations(history_length=32)
            ),
            memory.DEFAULT_MEMORY_COMPONENT_KEY: memory.ListMemory(
                [seed.render() for seed in seeded]
            ),
        }
        if blueprint is not None:
            components["CharacterProfile"] = constant.Constant(
                state=blueprint.cognition_context(),
                pre_act_label="Individual behavioural tendencies (not authority)",
            )
        self._entity = EntityAgentWithLogging(
            agent_name=identity.name,
            act_component=concat_act_component.ConcatActComponent(
                model=self.usage,
                component_order=tuple(components),
                randomize_choices=False,
                prefix_entity_name=False,
            ),
            context_components=components,
        )

    @property
    def entity(self) -> Any:
        """Expose the actual Concordia entity for controlled inspection."""
        return self._entity

    @property
    def revision(self) -> int:
        """Return the observation revision that decisions must reference."""
        return self._revision

    @property
    def cognition_revision(self) -> int:
        """Revision for decision-relevant private cognition, not observations."""
        return self._cognition_revision

    @property
    def memory_projection_enabled(self) -> bool:
        """Explicit experimental control; normal cognition includes Ox context."""
        return self._memory_projection_enabled

    @property
    def memory_now_turn(self) -> int:
        """Current simulated memory time, advanced even without new episodes."""
        return self._memory_now_turn

    @property
    def memory_clock(self) -> MemoryClockBridge | None:
        """Optional explicit mapping of authoritative Evennia game seconds."""
        return self._memory_clock

    def bind_memory_clock(self, bridge: MemoryClockBridge) -> None:
        """Bind one stable clock domain; never silently rebase old memories."""
        if not isinstance(bridge, MemoryClockBridge):
            raise TypeError("An explicit MemoryClockBridge is required")
        if self._memory_clock is not None and bridge != self._memory_clock:
            raise ValueError("Cannot silently replace a bound memory time frame")
        self._memory_clock = bridge

    def advance_memory_turn(self, now_turn: int) -> bool:
        """Set the owner-authorized simulated time independently of memory arrivals.

        A later time changes recall importance even when no event is admitted.
        It therefore invalidates stale model inference via cognition_revision.
        """
        if type(now_turn) is not int or now_turn < 0:
            raise ValueError("Memory time must be a nonnegative integer turn")
        if now_turn < self._memory_now_turn:
            raise ValueError("Simulation memory time cannot run backward")
        if now_turn == self._memory_now_turn:
            return False
        self._memory_now_turn = now_turn
        self._cognition_revision += 1
        self._record("memory_time_advanced", now_turn=now_turn)
        return True

    def advance_game_time(self, game_time: float) -> bool:
        """Project authenticated Evennia game time via an explicit time frame."""
        if self._memory_clock is None:
            raise RuntimeError("Bind the authoritative game-time frame first")
        mapped = self._memory_clock.turn_at(game_time)
        # Late recipient deliveries must never rewind local cognition.
        if mapped <= self._memory_now_turn:
            return False
        return self.advance_memory_turn(mapped)

    @property
    def temporal_memories(self) -> TemporalMemoryReadView:
        """Expose private recollections read-only, with detached return values."""
        return TemporalMemoryReadView(self._temporal_memories)

    @property
    def interpretations(self) -> InterpretationReadView:
        """Expose private hypotheses read-only, with detached return values."""
        return InterpretationReadView(self._interpretations)

    def rehearse_memories(
        self, subject: str, now_turn: int, *, limit: int = 3,
        affective_only: bool = False,
    ) -> tuple[TemporalMemory, ...]:
        """Consciously rehearse private episodes through their sole owner.

        The model's automatic prompt retrieval remains read-only. Explicit
        rehearsal affects future accessibility and invalidates stale inference.
        """
        if now_turn < self._memory_now_turn or (
            self._memory_clock is not None and now_turn != self._memory_now_turn
        ):
            raise ValueError("Rehearsal must use current simulated memory time")
        selected = self._temporal_memories.retrieve(
            subject, now_turn, limit=limit, affective_only=affective_only
        )
        if any(entry.recall_count >= 100000 for entry in selected):
            raise ValueError("Memory rehearsal counter exhausted")
        if not selected:
            return ()
        rehearsed = self._temporal_memories.retrieve(
            subject, now_turn, limit=limit, rehearse=True,
            affective_only=affective_only,
        )
        self._cognition_revision += 1
        self._record("subjective_rehearsal", memory_ids=[
            entry.memory_id for entry in rehearsed
        ], at_turn=now_turn)
        return tuple(TemporalMemory(**asdict(entry)) for entry in rehearsed)

    def reconsider_memory(
        self, memory_id: str, *, at_turn: int | None = None,
    ) -> bool:
        """Update an interpretation only from an already-held typed memory.

        Return True for *any* source-state mutation, including weak evidence
        that does not warrant a reported view change. Replays are no-ops.
        """
        entry = self._temporal_memories.get(memory_id)
        if entry is None or entry.claim_key is None:
            raise ValueError("Reconsideration requires an admitted typed claim")
        revised = InterpretationBank.from_records(
            self._interpretations.to_records())
        previous = self._interpretations.to_records()
        if at_turn is None:
            at_turn = max(entry.learned_turn, self._memory_now_turn)
        if at_turn < self._memory_now_turn or (
            self._memory_clock is not None and at_turn != self._memory_now_turn
        ):
            raise ValueError("Reconsideration must use current simulated time")
        change = revised.admit(entry, at_turn=at_turn)
        if revised.to_records() == previous:
            return False
        self._interpretations = revised
        self._cognition_revision += 1
        self._record("interpretation_evidence_admitted",
                     memory_id=memory_id, at_turn=at_turn)
        if change is not None:
            self._record("reinterpreted", claim_key=entry.claim_key,
                         claim_subject=entry.claim_subject or entry.subject,
                         evidence_id=memory_id,
                         previous_view=change.previous_view,
                         new_view=change.new_view,
                         previous_confidence=change.previous_confidence,
                         new_confidence=change.new_confidence,
                         reason=change.reason)
        return True

    @property
    def pending_requests(self) -> tuple[ActionRequest, ...]:
        """Return attempts needing world acknowledgment or reconciliation."""
        return tuple(self._pending.values())

    @property
    def memories(self) -> tuple[str, ...]:
        """Read the agent's own Concordia ListMemory, not canonical facts."""
        from concordia.components.agent import memory

        bank = self._entity.get_component(memory.DEFAULT_MEMORY_COMPONENT_KEY)
        return tuple(bank.get_all_memories_as_text())

    def remember_timed(self, entry: TemporalMemory) -> bool:
        """Store private cognition only after an addressed, verified encounter.

        The subjective record never grants authority or proves a claim.
        """
        if not isinstance(entry, TemporalMemory):
            raise TypeError("Only typed personal episodes can be remembered")
        # Never retain the caller's mutable object as internal owned memory.
        entry = TemporalMemory(**asdict(entry))
        if entry.last_recalled_turn is not None or entry.recall_count != 0:
            raise ValueError("A new witnessed episode cannot arrive pre-rehearsed")
        if (self._memory_clock is not None
                and entry.learned_turn > self._memory_now_turn):
            raise ValueError("A world-timed episode cannot be learned in the future")
        if entry.kind not in ("witnessed_speech", "world_receipt"):
            raise ValueError("Only observed new events may enter this route")
        if not entry.source_event_id:
            raise ValueError("New episode needs its source identity")
        # Preserve exact idempotent delivery even if it is retried much later.
        prior = self._temporal_memories.get(entry.memory_id)
        if prior is not None:
            return self._temporal_memories.add(entry)
        revision = None
        revised = None
        if entry.claim_key is not None:
            # Validate interpretation capacity/chronology before mutating
            # the event bank, so a rejected assessment cannot orphan an entry.
            revised = InterpretationBank.from_records(
                self._interpretations.to_records())
            revision = revised.admit(
                entry, at_turn=max(entry.learned_turn, self._memory_now_turn)
            )
        accepted = self._temporal_memories.add(entry)
        if accepted:
            # Event admission may bring an unbound G8 virtual clock forward.
            # It never substitutes for subsequent no-event clock advancement.
            self._memory_now_turn = max(self._memory_now_turn, entry.learned_turn)
            self._cognition_revision += 1
            if revised is not None:
                self._interpretations = revised
            self._record("subjective_episode", memory_id=entry.memory_id,
                         source_event_id=entry.source_event_id,
                         occurred_turn=entry.occurred_turn)
            if revision is not None:
                self._record(
                    "reinterpreted", claim_key=entry.claim_key,
                    claim_subject=entry.claim_subject or entry.subject,
                    evidence_id=entry.memory_id,
                    previous_view=revision.previous_view,
                    new_view=revision.new_view,
                    previous_confidence=revision.previous_confidence,
                    new_confidence=revision.new_confidence,
                    reason=revision.reason,
                )
        return accepted

    def _record(self, kind: str, **details: Any) -> None:
        """Append a trace with separate world-time and wall-time provenance."""
        if self._journal_path is None:
            return
        event = {
            "event_type": kind,
            "agent_id": self.identity.agent_id,
            "character_id": self.identity.character_id,
            "agent_revision": self._revision,
            "cognition_revision": self._cognition_revision,
            "memory_now_turn": self._memory_now_turn,
            "game_time": self._last_game_time,
            "wall_time_utc": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self._journal_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def observe(self, observation: WorldObservation) -> bool:
        """Incorporate an authorised observation once; reject wrong recipients.

        Returns:
            True if the Concordia entity accepted a new observation, else
            False when the observation ID had already been consumed.
        """
        if observation.character_id != self.identity.character_id:
            raise PermissionError("Observation belongs to another character")
        if observation.observation_id in self._seen_observations:
            return False

        annotated = (
            f"Game time {observation.game_time}; "
            f"observation {observation.observation_id}: {observation.text}"
        )
        game_time = float(observation.game_time)
        if not math.isfinite(game_time) or game_time < 0:
            raise ValueError("Invalid authoritative world observation time")
        if self._memory_clock is not None:
            self._memory_clock.turn_at(game_time)  # validate before native state mutation
        self._entity.observe(annotated)
        self._seen_observations.add(observation.observation_id)
        self._last_game_time = max(self._last_game_time or 0.0, game_time)
        if self._memory_clock is not None:
            self.advance_game_time(game_time)
        self._revision += 1
        self._record(
            "observation",
            observation_id=observation.observation_id,
            source_event_id=observation.source_event_id,
            text=observation.text,
        )
        return True

    def fork_for_inference(self) -> CrewAgent:
        """Detached copy of cognition state; no live pending world intents.

        Construct the fork on the event loop before scheduling the expensive
        model invocation in a thread. Only the fork is mutated in the worker.
        """
        fork = CrewAgent(
            self.identity, self._model, blueprint=self.blueprint,
            memory_projection_enabled=self._memory_projection_enabled,
        )
        fork._entity.set_state(deepcopy(self._entity.get_state()))
        fork._temporal_memories = TemporalMemoryBank.from_records(
            self._temporal_memories.to_records())
        fork._interpretations = InterpretationBank.from_records(
            self._interpretations.to_records())
        fork._revision = self._revision
        fork._cognition_revision = self._cognition_revision
        fork._memory_now_turn = self._memory_now_turn
        fork._memory_clock = self._memory_clock
        fork._seen_observations = set(self._seen_observations)
        fork._last_game_time = self._last_game_time
        return fork

    def adopt_inference(
        self, fork: CrewAgent, draft: ActionRequest,
        offered: Sequence[CommandOption], *, expected_revision: int,
        expected_cognition_revision: int,
    ) -> ActionRequest:
        """Commit a validated *proposal* from a snapshot, never a world effect.

        Called synchronously on the live agent's event-loop owner after a
        bounded off-thread inference. Invalid/stale results cannot enter the
        pending request ledger or overwrite newer observations.
        """
        if (not isinstance(fork, CrewAgent) or fork is self
                or fork.identity != self.identity or fork.blueprint != self.blueprint
                or fork.memory_projection_enabled != self.memory_projection_enabled):
            raise PermissionError("Detached inference belongs to another person")
        if (self._revision != expected_revision
                or fork.revision != expected_revision
                or self._cognition_revision != expected_cognition_revision
                or fork.cognition_revision != expected_cognition_revision):
            self._record(
                "stale_decision_discarded",
                inferred_revision=expected_revision,
                inferred_cognition_revision=expected_cognition_revision,
            )
            raise StaleAgentRevision(
                "World observation or private cognition changed during inference"
            )
        if (not isinstance(draft, ActionRequest)
                or draft.character_id != self.identity.character_id
                or draft.agent_revision != expected_revision
                or fork._pending.get(draft.request_id) != draft
                or draft.request_id in self._pending):
            raise PermissionError("Unbound or previously adopted inference proposal")
        # The model may only select a command in the original supplied menu.
        if not any(
            x.verb == draft.verb and x.target == draft.target
            and dict(x.arguments) == dict(draft.arguments)
            for x in offered
        ):
            raise PermissionError("Inferred action not in the finite offered menu")
        # No suspension between the revision gate and state/proposal adoption.
        # Preserve any native Concordia act-state evolution on successful work.
        self._entity.set_state(fork._entity.get_state())
        self._temporal_memories = TemporalMemoryBank.from_records(
            fork._temporal_memories.to_records())
        self._interpretations = InterpretationBank.from_records(
            fork._interpretations.to_records())
        self.usage.choice_calls += fork.usage.choice_calls
        self.usage.text_calls += fork.usage.text_calls
        self._pending[draft.request_id] = draft
        self._record(
            "action_proposed", request_id=draft.request_id,
            verb=draft.verb, target=draft.target,
            model_requests=fork.usage.total_calls,
            inference_mode="detached",
        )
        return draft

    def decide(
        self,
        choices: Sequence[CommandOption],
        *,
        expected_revision: int | None = None,
    ) -> ActionRequest:
        """Ask Concordia to choose a validated command attempt, not an outcome.

        Args:
            choices: The caller's currently offered commands; not a grant of
                authority to execute them.
            expected_revision: Optional optimistic observation revision.

        Raises:
            StaleAgentRevision: If knowledge changed before or during choice.
            ValueError: If choices are empty, ambiguous, or model-invalid.
        """
        from concordia.typing import entity as entity_lib

        if expected_revision is not None and expected_revision != self._revision:
            raise StaleAgentRevision("Observation revision changed")
        if not choices:
            raise ValueError("A choice requires at least one command option")
        by_label = {option.label: option for option in choices}
        if len(by_label) != len(choices) or any(
            not option.label or not option.verb for option in choices
        ):
            raise ValueError("Commands need unique nonempty labels and verbs")

        revision_at_start = self._revision
        cognition_at_start = self._cognition_revision
        calls_before = self.usage.total_calls
        # Labels alone can omit equipment names or the person being addressed.
        # Convey the offered option's verb/target/arguments to the *local*
        # read-only prompt projection, never to the world as new evidence.
        self._memory_query_text = " ".join(
            str(piece)
            for option in choices
            for piece in (
                option.label, option.verb, option.target or "",
                *tuple(str(value) for _, value in sorted(option.arguments.items())),
            )
        )
        try:
            choice = self._entity.act(
                entity_lib.choice_action_spec(
                    call_to_action=(
                        "What should {name} attempt next on watch? "
                        "Choose one of the supplied commands. "
                        "Your choice is a request, not a completed action."
                    ),
                    options=tuple(by_label),
                    tag="ox_command_attempt",
                )
            )
        finally:
            # Never let one decision's target contaminate a later prompt.
            self._memory_query_text = ""
        if (self._revision != revision_at_start
                or self._cognition_revision != cognition_at_start):
            self._record("stale_decision_discarded", chosen_label=choice)
            raise StaleAgentRevision(
                "Observation or private cognition changed during inference"
            )
        if choice not in by_label:
            self._record("invalid_decision", chosen_label=choice)
            raise ValueError("Concordia returned a command that was not offered")

        selected = by_label[choice]
        request = ActionRequest(
            request_id=uuid.uuid4().hex,
            character_id=self.identity.character_id,
            verb=selected.verb,
            target=selected.target,
            arguments=dict(selected.arguments),
            agent_revision=revision_at_start,
        )
        self._pending[request.request_id] = request
        self._record(
            "action_proposed",
            request_id=request.request_id,
            chosen_label=choice,
            verb=request.verb,
            target=request.target,
            model_requests=self.usage.total_calls - calls_before,
        )
        return request

    def record_outcome(self, outcome: ActionOutcome) -> None:
        """Record what the world reported without declaring unknown a failure."""
        if outcome.request_id not in self._pending:
            raise KeyError(f"No pending request {outcome.request_id}")
        self._record(
            "world_outcome",
            request_id=outcome.request_id,
            status=outcome.status,
            source_event_id=outcome.source_event_id,
            description=outcome.description,
        )
        if outcome.status in ("succeeded", "failed"):
            del self._pending[outcome.request_id]

    def snapshot(self) -> dict[str, Any]:
        """Return native Concordia state and Ox-owned pending action metadata."""
        return {
            "checkpoint_version": self.CHECKPOINT_VERSION,
            "memory_projection_enabled": self._memory_projection_enabled,
            "identity": asdict(self.identity),
            **({"character_blueprint": self.blueprint.to_record()} if self.blueprint is not None else {}),
            "revision": self._revision,
            # Optional checkpoint addition; existing checkpoint_version=1
            # files remain restorable with the default below.
            "cognition_revision": self._cognition_revision,
            "memory_now_turn": self._memory_now_turn,
            "memory_clock": (
                self._memory_clock.to_record() if self._memory_clock is not None
                else None
            ),
            "seen_observations": sorted(self._seen_observations),
            "last_game_time": self._last_game_time,
            "pending_requests": [asdict(item) for item in self.pending_requests],
            "concordia_state": self._entity.get_state(),
            "temporal_memories": self._temporal_memories.to_records(),
            "interpretations": self._interpretations.to_records(),
        }

    def save_checkpoint(self, path: Path) -> None:
        """Atomically persist the native component snapshot as JSON."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(self.snapshot(), stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    @classmethod
    def from_checkpoint(
        cls,
        path: Path,
        model: Any,
        *,
        journal_path: Path | None = None,
    ) -> CrewAgent:
        """Restore native Concordia memory; never replay pending commands."""
        checkpoint = json.loads(Path(path).read_text(encoding="utf-8"))
        if checkpoint.get("checkpoint_version") != cls.CHECKPOINT_VERSION:
            raise ValueError("Unsupported crew checkpoint version")
        blueprint = None
        if "character_blueprint" in checkpoint:
            from ox_ai.agents.crew_blueprints import CrewBlueprint
            blueprint = CrewBlueprint.from_record(checkpoint["character_blueprint"])
        crew = cls(
            CrewIdentity(**checkpoint["identity"]),
            model,
            journal_path=journal_path,
            blueprint=blueprint,
            memory_projection_enabled=checkpoint.get(
                "memory_projection_enabled", True),
        )
        crew._entity.set_state(checkpoint["concordia_state"])
        # Existing pre-G8 checkpoints contain only native Concordia memory.
        crew._temporal_memories = TemporalMemoryBank.from_records(
            checkpoint.get("temporal_memories", []))
        # Legacy checkpoints predate this optional private interpretation
        # snapshot. Rebuild only their first-generation hypothesis index;
        # never duplicate or silently rewrite an existing revision history.
        if "interpretations" in checkpoint:
            crew._interpretations = InterpretationBank.from_records(
                checkpoint["interpretations"])
        else:
            crew._interpretations = InterpretationBank.rebuild(
                crew._temporal_memories)
        crew._revision = checkpoint["revision"]
        saved_cognition = checkpoint.get("cognition_revision", 0)
        if (type(saved_cognition) is not int or saved_cognition < 0):
            raise ValueError("Invalid persisted private cognition revision")
        crew._cognition_revision = saved_cognition
        # Existing G8/G9 version-one checkpoints have no explicit time frame.
        # Their latest observed memory-domain date preserves existing ranking.
        fallback_turn = max((0,) + tuple(
            max(entry.learned_turn,
                entry.last_recalled_turn
                if entry.last_recalled_turn is not None else entry.learned_turn)
            for entry in crew._temporal_memories.entries()
        ))
        now_turn = checkpoint.get("memory_now_turn", fallback_turn)
        if type(now_turn) is not int or now_turn < 0:
            raise ValueError("Invalid persisted private memory clock cursor")
        crew._memory_now_turn = now_turn
        saved_frame = checkpoint.get("memory_clock")
        crew._memory_clock = (
            MemoryClockBridge.from_record(saved_frame)
            if saved_frame is not None else None
        )
        crew._seen_observations = set(checkpoint["seen_observations"])
        crew._last_game_time = checkpoint["last_game_time"]
        crew._pending = {
            request["request_id"]: ActionRequest(**request)
            for request in checkpoint["pending_requests"]
        }
        crew._record(
            "restored",
            pending_request_ids=sorted(crew._pending),
        )
        return crew
