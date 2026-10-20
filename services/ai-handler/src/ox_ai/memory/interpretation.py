"""Private, revisable interpretations of *claims about* remembered events.

A person can remember precisely what was said while changing their opinion
about the claim. Statements carry evidence of *speech*, not proof of truth.
Only a typed, relevant, independently sourced change prompts reconsideration.

This is a deterministic epistemic layer for GOAP, not a facts database,
truth oracle, therapist, or automatic romance/consent system.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Mapping

from ox_ai.memory.temporal import TemporalMemory

MAX_BELIEFS = 128
MAX_SOURCES = 24
MAX_REVISIONS = 96
SCHEMA_VERSION = 1
# Verifying that someone *said* X does not verify X.
CLAIM_WEIGHTS = {
    "recollection": 0.72,
    "testimony": 0.46,
    "interpretation": 0.32,
    "witnessed_speech": 0.52,
    "world_receipt": 1.0,  # Only claims entailed by the exact receipt.
}


def _int(value, name, lo=None, hi=None):
    if type(value) is not int or (lo is not None and value < lo) or (
        hi is not None and value > hi
    ):
        raise ValueError(f"Invalid {name}")
    return value


def _status(confidence: int) -> str:
    return "favoured" if confidence >= 65 else (
        "doubted" if confidence <= 35 else "unsettled"
    )


@dataclass(frozen=True, slots=True)
class ClaimSignal:
    """An immutable account of a person's *source* for one proposition."""

    memory_id: str
    group: str
    stance: int
    kind: str
    occurred_turn: int
    learned_turn: int
    confidence: int
    salience: int
    credibility: int

    def __post_init__(self):
        if (not isinstance(self.memory_id, str) or not self.memory_id
                or len(self.memory_id) > 128):
            raise ValueError("Invalid claim memory identity")
        if (not isinstance(self.group, str) or not self.group
                or len(self.group) > 128):
            raise ValueError("Invalid correlated source group")
        if self.stance not in (-1, 1) or type(self.stance) is not int:
            raise ValueError("Evidence must support or oppose a specific claim")
        if self.kind not in CLAIM_WEIGHTS:
            raise ValueError("Unrecognized claim provenance")
        _int(self.occurred_turn, "occurrence time")
        _int(self.learned_turn, "learning time", self.occurred_turn)
        for label in ("confidence", "salience", "credibility"):
            _int(getattr(self, label), label, 0, 100)

    @classmethod
    def from_memory(cls, memory: TemporalMemory) -> "ClaimSignal":
        if memory.claim_key is None or memory.claim_stance not in (-1, 1):
            raise ValueError("Only an explicit typed claim is interpretable")
        return cls(
            memory_id=memory.memory_id,
            group=memory.source_group or ("unique:" + memory.memory_id),
            stance=memory.claim_stance,
            kind=memory.kind,
            occurred_turn=memory.occurred_turn,
            learned_turn=memory.learned_turn,
            confidence=memory.confidence,
            salience=memory.salience,
            credibility=memory.claim_credibility,
        )

    def weight(self, at_turn: int) -> float:
        _int(at_turn, "appraisal time", self.learned_turn)
        # The floor retains older formative evidence; it does not dominate
        # unconditionally. Reception and occurrence dates remain distinct.
        age = max(0, at_turn - self.occurred_turn)
        recency = 0.25 + 0.75 * 2 ** (-age / 300)
        importance = 0.30 + 0.70 * self.salience / 100
        credibility = 0.25 + 0.75 * self.credibility / 100
        return (
            CLAIM_WEIGHTS[self.kind] * recency * importance * credibility
            * self.confidence / 100
        )


@dataclass(frozen=True, slots=True)
class InterpretationRevision:
    turn: int
    evidence_id: str
    source_group: str
    reason: str
    previous_confidence: int
    new_confidence: int
    previous_view: str
    new_view: str
    opposing_sources: bool

    def __post_init__(self):
        _int(self.turn, "revision turn")
        _int(self.previous_confidence, "previous confidence", 1, 99)
        _int(self.new_confidence, "new confidence", 1, 99)
        if self.previous_view != _status(self.previous_confidence):
            raise ValueError("Previous view disagrees with confidence")
        if self.new_view != _status(self.new_confidence):
            raise ValueError("New view disagrees with confidence")
        if self.reason not in (
            "first_account", "corroboration", "counterevidence",
            "source_revised",
        ):
            raise ValueError("Unknown reason for revision")
        if type(self.opposing_sources) is not bool:
            raise ValueError("Opposition flag must be boolean")
        if (not self.evidence_id or not self.source_group):
            raise ValueError("Revisions require exact source attribution")


@dataclass(slots=True)
class Interpretation:
    """One character's defeasible belief, never a canonical world property."""

    subject: str
    claim_key: str
    prior: int = 50
    confidence: int = 50
    last_assessed_turn: int | None = None
    sources: dict[str, ClaimSignal] = field(default_factory=dict)
    revisions: list[InterpretationRevision] = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.subject, str) or not self.subject:
            raise ValueError("Interpretation requires an attributed subject")
        if not isinstance(self.claim_key, str) or not self.claim_key:
            raise ValueError("Interpretation requires an explicit proposition")
        _int(self.prior, "interpretation prior", 2, 98)
        _int(self.confidence, "belief confidence", 1, 99)
        if self.last_assessed_turn is not None:
            _int(self.last_assessed_turn, "last assessment turn")
        if len(self.sources) > MAX_SOURCES or len(self.revisions) > MAX_REVISIONS:
            raise ValueError("Oversized interpretation checkpoint")

    @property
    def view(self) -> str:
        return _status(self.confidence)

    @property
    def contradictory(self) -> bool:
        return any(s.stance > 0 for s in self.sources.values()) and any(
            s.stance < 0 for s in self.sources.values()
        )

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(sorted(x.memory_id for x in self.sources.values()))


class InterpretationBank:
    """Independently owned, bounded, checkpointable subjective hypotheses."""

    def __init__(self, priors: Mapping[tuple[str, str], int] | None = None):
        self._states: dict[tuple[str, str], Interpretation] = {}
        self._priors = {}
        for key, prior in (priors or {}).items():
            if not isinstance(key, tuple) or len(key) != 2 or not all(
                isinstance(v, str) and v for v in key
            ):
                raise ValueError("Prior keys must be (subject, claim_key)")
            self._priors[key] = _int(prior, "prior confidence", 2, 98)

    def _calculate(self, state: Interpretation, at_turn: int) -> int:
        # A log-odds-like update is bounded and deliberately leaves room for
        # doubt. Only one effective account per correlated origin contributes.
        prior_logit = math.log(state.prior / (100 - state.prior))
        signed = sum(
            signal.stance * signal.weight(at_turn)
            for signal in state.sources.values()
        )
        logit = max(-4.0, min(4.0, prior_logit + signed * 3.2))
        return max(2, min(98, round(100 / (1 + math.exp(-logit)))))

    def admit(
        self, memory: TemporalMemory, *, at_turn: int | None = None,
    ) -> InterpretationRevision | None:
        """Reinterpret ONLY a new relevant claim; returns a meaningful change.

        The caller first proves that the person actually received the episode.
        Idempotent replay and repeated same-source assertions cannot create
        false corroboration. An opposing statement from the same source
        replaces that source's earlier stance without changing the memory.
        """
        if not isinstance(memory, TemporalMemory):
            raise TypeError("Interpretation requires a typed private memory")
        if memory.claim_key is None:
            return None
        now = memory.learned_turn if at_turn is None else at_turn
        _int(now, "interpretation turn", memory.learned_turn)
        key = (memory.claim_subject or memory.subject, memory.claim_key)
        state = self._states.get(key)
        signal = ClaimSignal.from_memory(memory)
        if state is None:
            if len(self._states) >= MAX_BELIEFS:
                raise ValueError("Private interpretation capacity exhausted")
            prior = self._priors.get(key, 50)
            state = Interpretation(key[0], key[1], prior=prior, confidence=prior)
        if state.last_assessed_turn is not None and now < state.last_assessed_turn:
            raise ValueError("Cannot reconsider a belief earlier than its last assessment")
        earlier = state.sources.get(signal.group)
        if earlier is not None:
            if earlier.memory_id == signal.memory_id:
                if earlier != signal:
                    raise ValueError("Reused memory identity changed its claim")
                return None
            if earlier.stance == signal.stance:
                # Repetition, even emphatic repetition, is not new evidence.
                # A later retraction (opposite stance) IS meaningful.
                return None
        elif len(state.sources) >= MAX_SOURCES:
            raise ValueError("Too many independent claim sources")

        old_sources = list(state.sources.values())
        old = state.confidence
        old_view = state.view
        if earlier is not None:
            reason = "source_revised"
        elif not old_sources:
            reason = "first_account"
        elif any(s.stance != signal.stance for s in old_sources):
            reason = "counterevidence"
        else:
            reason = "corroboration"
        state.sources[signal.group] = signal
        updated = self._calculate(state, now)
        state.last_assessed_turn = now
        state.confidence = updated
        self._states[key] = state
        # Weak or uninformative evidence is recorded, but it does not count
        # as a substantive *reinterpretation* or trigger repeated dialogue.
        if abs(updated - old) < 3 and state.view == old_view:
            return None
        revision = InterpretationRevision(
            turn=now, evidence_id=signal.memory_id, source_group=signal.group,
            reason=reason, previous_confidence=old, new_confidence=updated,
            previous_view=old_view, new_view=state.view,
            opposing_sources=state.contradictory,
        )
        state.revisions.append(revision)
        if len(state.revisions) > MAX_REVISIONS:
            # The memory bank preserves original source records. The bounded
            # interpretation ledger retains its most recent revisions.
            state.revisions = state.revisions[-MAX_REVISIONS:]
        return revision

    def get(self, subject: str, claim_key: str) -> Interpretation | None:
        return self._states.get((subject, claim_key))

    def views(self) -> tuple[Interpretation, ...]:
        """Read-only consumers inspect the character's current hypotheses."""
        return tuple(self._states[key] for key in sorted(self._states))

    def for_subject(self, subject: str) -> tuple[Interpretation, ...]:
        return tuple(
            self._states[k] for k in sorted(self._states)
            if k[0] == subject
        )

    def all_revisions(self) -> tuple[InterpretationRevision, ...]:
        return tuple(
            revision for key in sorted(self._states)
            for revision in self._states[key].revisions
        )

    def to_records(self) -> dict:
        return {
            "version": SCHEMA_VERSION,
            "priors": [
                {"subject": subject, "claim_key": claim, "prior": value}
                for (subject, claim), value in sorted(self._priors.items())
            ],
            "states": [
                {
                    "subject": x.subject, "claim_key": x.claim_key,
                    "prior": x.prior, "confidence": x.confidence,
                    "last_assessed_turn": x.last_assessed_turn,
                    "sources": [asdict(v) for _, v in sorted(x.sources.items())],
                    "revisions": [asdict(v) for v in x.revisions],
                }
                for _, x in sorted(self._states.items())
            ],
        }

    @classmethod
    def from_records(cls, payload: Mapping) -> "InterpretationBank":
        if not isinstance(payload, dict) or payload.get("version") != SCHEMA_VERSION:
            raise ValueError("Unsupported private interpretation checkpoint")
        prior_data = payload.get("priors")
        state_data = payload.get("states")
        if not isinstance(prior_data, list) or not isinstance(state_data, list):
            raise ValueError("Malformed interpretation checkpoint")
        if len(prior_data) > MAX_BELIEFS or len(state_data) > MAX_BELIEFS:
            raise ValueError("Interpretation checkpoint exceeds limits")
        priors = {}
        for raw in prior_data:
            key = (raw["subject"], raw["claim_key"])
            if key in priors:
                raise ValueError("Duplicate private belief prior")
            priors[key] = raw["prior"]
        bank = cls(priors)
        for row in state_data:
            sources = row["sources"]
            revisions = row["revisions"]
            if not isinstance(sources, list) or not isinstance(revisions, list):
                raise ValueError("Malformed belief evidence or revisions")
            if len(sources) > MAX_SOURCES or len(revisions) > MAX_REVISIONS:
                raise ValueError("Oversized belief history")
            items = [ClaimSignal(**source) for source in sources]
            by_group = {x.group: x for x in items}
            if len(by_group) != len(items):
                raise ValueError("Duplicated correlated source in checkpoint")
            history = [InterpretationRevision(**rev) for rev in revisions]
            state = Interpretation(
                subject=row["subject"], claim_key=row["claim_key"],
                prior=row["prior"], confidence=row["confidence"],
                last_assessed_turn=row["last_assessed_turn"],
                sources=by_group, revisions=history,
            )
            key = (state.subject, state.claim_key)
            if key in bank._states:
                raise ValueError("Duplicated interpretation state")
            # Several tiny corroborations may accumulate after the most recent
            # substantive revision. Their identities persist in sources even
            # though they deliberately did not trigger separate revisions.
            bank._states[key] = state
        return bank

    @classmethod
    def rebuild(cls, memory_bank) -> "InterpretationBank":
        """Migrate old snapshots with no interpretation field, once."""
        bank = cls()
        entries = sorted(memory_bank.to_records(), key=lambda v: (
            v["learned_turn"], v["occurred_turn"], v["memory_id"]
        ))
        for data in entries:
            entry = TemporalMemory(**data)
            if entry.claim_key is not None:
                bank.admit(entry, at_turn=entry.learned_turn)
        return bank
