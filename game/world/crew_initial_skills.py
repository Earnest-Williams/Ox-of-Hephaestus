"""Canonical first-ship starting skill estimates tied to people, never job roles.

These are the preserved results of G3f's initial six individual vectors
converted at G4b. They are now ordinary 0-100 initial world estimates.
No actor receives experience or authorization from a job-title change.
Legacy Evennia .db.ox_skills is read only when upgrading a pre-G4d world.
"""
from __future__ import annotations

from world.skill_catalogue import SKILLS

PERSON_STARTING_SKILLS: dict[str, dict[str, int]] = {
    "crew.captain-initial": {
        "command.crisis_management": 80,
        "command.delegation": 80,
        "command.ship_coordination": 80,
        "command.watch_management": 80,
        "environmental.atmosphere_diagnostics": 20,
        "environmental.atmosphere_maintenance": 20,
        "freight.cargo_inspection": 20,
        "freight.cargo_rigging": 20,
        "investigation.evidence_assessment": 20,
        "investigation.instrument_analysis": 20,
        "mechanical.pump_service": 20,
        "mechanical.seal_fitting": 20,
        "mechanical.vibration_diagnostics": 20,
    },
    "crew.lin-sato": {
        "command.crisis_management": 40,
        "command.delegation": 60,
        "command.ship_coordination": 40,
        "command.watch_management": 60,
        "environmental.atmosphere_diagnostics": 20,
        "environmental.atmosphere_maintenance": 20,
        "freight.cargo_inspection": 20,
        "freight.cargo_rigging": 20,
        "investigation.evidence_assessment": 40,
        "investigation.instrument_analysis": 40,
        "mechanical.pump_service": 20,
        "mechanical.seal_fitting": 20,
        "mechanical.vibration_diagnostics": 20,
    },
    "crew.ari-sen": {
        "command.crisis_management": 0,
        "command.delegation": 20,
        "command.ship_coordination": 0,
        "command.watch_management": 20,
        "environmental.atmosphere_diagnostics": 20,
        "environmental.atmosphere_maintenance": 20,
        "freight.cargo_inspection": 0,
        "freight.cargo_rigging": 0,
        "investigation.evidence_assessment": 60,
        "investigation.instrument_analysis": 60,
        "mechanical.pump_service": 60,
        "mechanical.seal_fitting": 60,
        "mechanical.vibration_diagnostics": 60,
    },
    "crew.iona-vek": {
        "command.crisis_management": 20,
        "command.delegation": 40,
        "command.ship_coordination": 20,
        "command.watch_management": 40,
        "environmental.atmosphere_diagnostics": 40,
        "environmental.atmosphere_maintenance": 40,
        "freight.cargo_inspection": 0,
        "freight.cargo_rigging": 0,
        "investigation.evidence_assessment": 80,
        "investigation.instrument_analysis": 80,
        "mechanical.pump_service": 80,
        "mechanical.seal_fitting": 80,
        "mechanical.vibration_diagnostics": 80,
    },
    "crew.mara-voss": {
        "command.crisis_management": 20,
        "command.delegation": 40,
        "command.ship_coordination": 20,
        "command.watch_management": 40,
        "environmental.atmosphere_diagnostics": 20,
        "environmental.atmosphere_maintenance": 20,
        "freight.cargo_inspection": 80,
        "freight.cargo_rigging": 80,
        "investigation.evidence_assessment": 40,
        "investigation.instrument_analysis": 40,
        "mechanical.pump_service": 0,
        "mechanical.seal_fitting": 0,
        "mechanical.vibration_diagnostics": 0,
    },
    "crew.teo-hale": {
        "command.crisis_management": 0,
        "command.delegation": 20,
        "command.ship_coordination": 0,
        "command.watch_management": 20,
        "environmental.atmosphere_diagnostics": 80,
        "environmental.atmosphere_maintenance": 80,
        "freight.cargo_inspection": 0,
        "freight.cargo_rigging": 0,
        "investigation.evidence_assessment": 60,
        "investigation.instrument_analysis": 60,
        "mechanical.pump_service": 20,
        "mechanical.seal_fitting": 20,
        "mechanical.vibration_diagnostics": 20,
    },
}


def starting_skills_for_person(person_id: str) -> dict[str, int]:
    """Copy a stable person's initial estimates, never a mutable shared seed."""
    try:
        result = PERSON_STARTING_SKILLS[person_id]
    except KeyError as exc:
        raise ValueError("Unrecognised canonical founding crewmember") from exc
    return dict(result)


for _person, _estimates in PERSON_STARTING_SKILLS.items():
    if set(_estimates) - set(SKILLS):
        raise RuntimeError(f"Unknown canonical skill seed for {_person}")
    if any(type(score) is not int or not 0 <= score <= 100
           for score in _estimates.values()):
        raise RuntimeError(f"Invalid canonical skill seed for {_person}")
