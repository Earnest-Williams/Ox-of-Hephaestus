"""Actor-private open-world epistemics; world observations do not equal beliefs.

An absent fact is not false. A world observation proves what was observed at
a time, not what remains true forever. A hypothesis is never promoted to
knowledge merely by repetition. A world fact may ALREADY be an unknown unknown relative to this actor,
even when an operator can identify it. This private ledger must never be
given hidden world facts. A later recorded surprise is a different event.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
import re

_FACT = re.compile(r"[a-z][a-z0-9_.:-]{0,95}")
_EVIDENCE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}")


def _fact(value):
    if not isinstance(value, str) or _FACT.fullmatch(value) is None:
        raise ValueError("Invalid epistemic proposition")
    return value


def _evidence(value):
    if not isinstance(value, str) or _EVIDENCE.fullmatch(value) is None:
        raise ValueError("Invalid evidence reference")
    return value


def _time(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0):
        raise ValueError("Invalid nonnegative finite world time")
    return float(value)


def _scalar(value):
    if not isinstance(value, (type(None), str, bool, int, float)):
        raise ValueError("Facts must be bounded JSON scalars")
    if isinstance(value, str) and (
        len(value) > 256 or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("Invalid text value")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Invalid nonfinite value")
    if type(value) is int and abs(value) > 10**15:
        raise ValueError("Invalid enormous integer")
    return value


class AgentEpistemics:
    """Evidence, beliefs, known questions and retrospective surprises per body.

    observe_verified is exclusively for the trusted authenticated world-port
    boundary. LLM output and crew testimony may use believe/ask but must not
    call observe_verified. The ledger does not itself grant world authority.
    """
    VERSION = 1
    CAP = 128

    def __init__(self, record: dict, *, role: str, character_id: str):
        if not isinstance(record, dict) or not isinstance(role, str) or not role:
            raise ValueError("Invalid agent epistemic record")
        if not isinstance(character_id, str) or not re.fullmatch(r"#[1-9][0-9]*", character_id):
            raise ValueError("Invalid character identity")
        if not record:
            record.update({
                "version": self.VERSION, "role": role, "character_id": character_id,
                "observations": {}, "beliefs": {}, "questions": {},
                "events": {}, "surprises": [], "concepts": [],
            })
        if (set(record) != {
            "version", "role", "character_id", "observations", "beliefs",
            "questions", "events", "surprises", "concepts",
        } or type(record["version"]) is not int or record["version"] != self.VERSION
                or record["role"] != role or record["character_id"] != character_id
                or not all(isinstance(record[n], dict) for n in (
                    "observations", "beliefs", "questions", "events"))
                or not all(isinstance(record[n], list) for n in ("surprises", "concepts"))
                or any(len(record[n]) > self.CAP for n in (
                    "observations", "beliefs", "questions", "surprises", "concepts"))
                or len(record["events"]) > 512):
            raise PermissionError("Foreign or invalid private epistemic record")
        for key, observation in record["observations"].items():
            _fact(key)
            if not isinstance(observation, dict) or set(observation) != {
                "value", "source", "evidence_id", "at", "valid_for", "history"
            } or observation["source"] not in (
                "world_local", "world_receipt", "world_event"
            ):
                raise ValueError("Malformed persisted observation")
            _scalar(observation["value"])
            _evidence(observation["evidence_id"])
            _time(observation["at"])
            _time(observation["valid_for"])
            if not isinstance(observation["history"], list) or len(observation["history"]) > 4:
                raise ValueError("Unbounded evidence history")
        for key, entry in record["beliefs"].items():
            _fact(key)
            if not isinstance(entry, dict) or set(entry) != {
                "value", "confidence", "basis", "state"
            }:
                raise ValueError("Invalid persisted belief")
            _scalar(entry["value"])
            if (type(entry["confidence"]) not in (int, float)
                    or not math.isfinite(entry["confidence"])
                    or not 0 <= entry["confidence"] <= 1
                    or entry["state"] not in ("hypothesis", "refuted")
                    or not isinstance(entry["basis"], str)
                    or not 1 <= len(entry["basis"]) <= 192):
                raise ValueError("Invalid belief provenance")
        for key, entry in record["questions"].items():
            _fact(key)
            if not isinstance(entry, dict) or set(entry) != {"reason", "status"}:
                raise ValueError("Invalid known unknown")
            if (not isinstance(entry["reason"], str)
                    or not 1 <= len(entry["reason"]) <= 192
                    or entry["status"] not in ("open", "answered")):
                raise ValueError("Invalid question")
        for key, event in record["events"].items():
            _evidence(key)
            if not isinstance(event, dict) or set(event) != {"kind", "at"}:
                raise ValueError("Invalid private event proof")
            _fact(event["kind"])
            _time(event["at"])
        for s in record["surprises"]:
            if not isinstance(s, dict) or set(s) != {
                "fact", "evidence_id", "classification"
            } or s["classification"] != "previously_unmodeled":
                raise ValueError("Invalid surprise")
            _fact(s["fact"])
            _evidence(s["evidence_id"])
        for concept in record["concepts"]:
            _fact(concept)
        self.record = record
        self.role = role
        self.character_id = character_id

    def ask(self, fact: str, *, reason: str):
        """A known unknown is an explicit question, not a guessed value."""
        fact = _fact(fact)
        if not isinstance(reason, str) or not 1 <= len(reason) <= 192:
            raise ValueError("Question must explain what is not known")
        entries = self.record["questions"]
        if fact not in entries and len(entries) >= self.CAP:
            raise ValueError("Too many unanswered questions")
        entries.setdefault(fact, {"reason": reason, "status": "open"})

    def believe(self, fact: str, value, *, confidence: float, basis: str):
        """Hypothesis or testimony: never world truth, regardless of confidence."""
        fact, value = _fact(fact), _scalar(value)
        if (type(confidence) not in (int, float) or not math.isfinite(confidence)
                or not 0 <= confidence <= 1 or not isinstance(basis, str)
                or not 1 <= len(basis) <= 192):
            raise ValueError("Belief must have finite confidence and basis")
        entries = self.record["beliefs"]
        if fact not in entries and len(entries) >= self.CAP:
            raise ValueError("Belief capacity reached")
        entries[fact] = {"value": value, "confidence": float(confidence),
                         "basis": basis, "state": "hypothesis"}
        self._add_concept(fact)

    def _add_concept(self, fact):
        concept = fact.split(".")[0]
        concepts = self.record["concepts"]
        if concept not in concepts:
            if len(concepts) >= self.CAP:
                raise ValueError("Concept capacity reached")
            concepts.append(concept)

    def observe_verified(
        self, fact: str, value, *, evidence_id: str, at: float,
        valid_for: float = 0, source: str, surprise: bool = False,
    ) -> bool:
        """Record authenticated world evidence, with bounded current validity.

        A surprise is optional retrospective evidence of newly encountered
        information. An unknown unknown is a hidden world fact relative to
        an actor *before* discovery, and exists whether or not discovery
        ever happens; agents must not enumerate such world facts.
        """
        fact, value, evidence_id = _fact(fact), _scalar(value), _evidence(evidence_id)
        at, valid_for = _time(at), _time(valid_for)
        if source not in ("world_local", "world_receipt", "world_event"):
            raise PermissionError("Beliefs or hearsay cannot assert world facts")
        entries = self.record["observations"]
        old = entries.get(fact)
        if old and old["evidence_id"] == evidence_id:
            if (old["value"] != value or old["source"] != source
                    or old["at"] != at or old["valid_for"] != valid_for):
                raise PermissionError("Evidence collision")
            return False
        if old and at < old["at"]:
            return False  # replay cannot make recent knowledge older
        if old is None and len(entries) >= self.CAP:
            raise ValueError("Observation capacity reached")
        concept = fact.split(".")[0]
        was_unmodeled = (fact not in entries and fact not in self.record["beliefs"]
                         and fact not in self.record["questions"]
                         and concept not in self.record["concepts"])
        history = ([] if old is None else old["history"] + [
            {k: old[k] for k in ("value", "evidence_id", "at", "source")}
        ])[-4:]
        entries[fact] = {
            "value": value, "evidence_id": evidence_id,
            "source": source, "at": at, "valid_for": valid_for,
            "history": history,
        }
        belief = self.record["beliefs"].get(fact)
        if belief and belief["value"] != value:
            belief["state"] = "refuted"
        question = self.record["questions"].get(fact)
        if question:
            question["status"] = "answered"
        self._add_concept(fact)
        if surprise and was_unmodeled:
            surprises = self.record["surprises"]
            if len(surprises) >= self.CAP:
                raise ValueError("Surprise log full")
            surprises.append({
                "fact": fact, "evidence_id": evidence_id,
                "classification": "previously_unmodeled",
            })
        return True

    def receive_event(self, event: Mapping):
        """Prove receipt of addressed event; never treat sender prose as fact."""
        if (not isinstance(event, Mapping)
                or event.get("recipient_dbref") != self.character_id):
            raise PermissionError("Event addressed to another crewmember")
        identity = _evidence(event.get("event_id"))
        kind, when = _fact(event.get("kind")), _time(event.get("game_time"))
        entries = self.record["events"]
        proof = {"kind": kind, "at": when}
        if identity in entries:
            if entries[identity] != proof:
                raise PermissionError("Conflicting world event identity")
            return False
        if len(entries) >= 512:
            raise ValueError("Evidence retention capacity reached")
        entries[identity] = proof
        return True

    def assess(self, fact: str, *, now: float) -> dict:
        """Actor-local query: no world truth, secret inventory or default false."""
        fact, now = _fact(fact), _time(now)
        observed = self.record["observations"].get(fact)
        if observed and observed["at"] <= now <= observed["at"] + observed["valid_for"]:
            return {"status": "observed", "value": observed["value"],
                    "evidence_id": observed["evidence_id"], "at": observed["at"]}
        belief = self.record["beliefs"].get(fact)
        if belief and belief["state"] == "hypothesis":
            return {"status": "believed", "value": belief["value"],
                    "confidence": belief["confidence"], "basis": belief["basis"]}
        question = self.record["questions"].get(fact)
        if question:
            return {"status": "known_unknown", "reason": question["reason"]}
        if observed:
            return {"status": "historically_observed",
                    "value": observed["value"], "at": observed["at"],
                    "evidence_id": observed["evidence_id"],
                    "currently_verified": False}
        return {"status": "unmodeled", "value": None}
