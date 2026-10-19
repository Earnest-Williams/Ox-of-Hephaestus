"""Individually authored INITIAL estimates, not verified learning receipts.

These reflect the first ship's already-established staffing and routine
operational assignments, without inventing formal education or biographical
events. World evidence may later change them independently of practical skill.
These values are not inferred from skills during evaluation or derived from
a person's mutable crew_role during bootstrap.
"""
from __future__ import annotations

from world.skill_catalogue import FOUNDATIONS
from world.technique_catalogue import TECHNIQUES

PERSON_STARTING_FOUNDATIONS: dict[str, dict[str, int]] = {
    "crew.iona-vek": {
        "mechanical.rotating_machinery": 75,
        "investigation.methods": 55,
        "environmental.life_support": 35,
    },
    "crew.ari-sen": {
        "mechanical.rotating_machinery": 55,
        "investigation.methods": 50,
        "environmental.life_support": 20,
    },
    "crew.lin-sato": {
        "command.operations": 60,
        "investigation.methods": 50,
        "navigation.trajectory": 45,
    },
    "crew.mara-voss": {
        "freight.load_mechanics": 70,
        "investigation.methods": 35,
        "command.operations": 30,
    },
    "crew.teo-hale": {
        "environmental.life_support": 70,
        "investigation.methods": 55,
        "biology.living_systems": 30,
    },
    "crew.captain-initial": {
        "command.operations": 70,
        "investigation.methods": 20,
        "navigation.trajectory": 25,
    },
}

PERSON_STARTING_TECHNIQUES: dict[str, dict[str, int]] = {
    "crew.iona-vek": {
        "pump.p01.routine_service": 80,
        "pump.p01.unfamiliar_repair": 30,
        "pump.p01.vibration_analyzer": 55,
    },
    "crew.ari-sen": {
        "pump.p01.routine_service": 60,
        "pump.p01.unfamiliar_repair": 15,
        "pump.p01.vibration_analyzer": 45,
    },
    "crew.lin-sato": {
        "analyzer.bridge.inconsistent_readings": 55,
    },
    "crew.mara-voss": {
        "cargo.c01.restow": 75,
    },
    "crew.teo-hale": {
        "environment.a01.scrubber_service": 75,
    },
    "crew.captain-initial": {
        "captain.bridge.instrument_review": 30,
    },
}


def _initial(mapping: dict[str, dict[str, int]], person_id: str) -> dict[str, int]:
    try:
        return dict(mapping[person_id])
    except KeyError as exc:
        raise ValueError("Unrecognised original crew person ID") from exc


def starting_foundations_for_person(person_id: str) -> dict[str, int]:
    return _initial(PERSON_STARTING_FOUNDATIONS, person_id)


def starting_techniques_for_person(person_id: str) -> dict[str, int]:
    return _initial(PERSON_STARTING_TECHNIQUES, person_id)


if set(PERSON_STARTING_FOUNDATIONS) != set(PERSON_STARTING_TECHNIQUES):
    raise RuntimeError("Original crew learning estimate tables disagree")
for _person, _items in PERSON_STARTING_FOUNDATIONS.items():
    if set(_items) - set(FOUNDATIONS):
        raise RuntimeError(f"Unknown theoretical foundation for {_person}")
for _person, _items in PERSON_STARTING_TECHNIQUES.items():
    if set(_items) - set(TECHNIQUES):
        raise RuntimeError(f"Unknown equipment familiarity technique for {_person}")
for _items in (*PERSON_STARTING_FOUNDATIONS.values(),
               *PERSON_STARTING_TECHNIQUES.values()):
    if any(type(value) is not int or not 0 <= value <= 100
           for value in _items.values()):
        raise RuntimeError("Initial knowledge and familiarity must be 0-100")
