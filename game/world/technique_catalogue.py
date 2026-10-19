"""Canonical personal equipment-and-procedure familiarity definitions.

A technique is NOT a general skill, a theoretical foundation, or a job role.
The fixture marker identifies the specific Ox installation and the procedure
distinguishes tasks on the same physical equipment. Replacing the actual
machinery with a different model later requires a versioned technique identity.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from world.skill_catalogue import SKILLS

TECHNIQUE_CATALOGUE_VERSION = 1
_ID = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,4}$")
_MARKER = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class TechniqueDefinition:
    technique_id: str
    label: str
    fixture_marker: str
    relevant_skill_id: str


TECHNIQUES: dict[str, TechniqueDefinition] = {
    "pump.p01.routine_service": TechniqueDefinition(
        "pump.p01.routine_service", "P-01 routine service",
        "pump-p01", "mechanical.pump_service",
    ),
    "pump.p01.unfamiliar_repair": TechniqueDefinition(
        "pump.p01.unfamiliar_repair", "P-01 unusual mechanical intervention",
        "pump-p01", "mechanical.pump_service",
    ),
    "pump.p01.vibration_analyzer": TechniqueDefinition(
        "pump.p01.vibration_analyzer", "P-01 interference diagnostics",
        "pump-p01", "mechanical.vibration_diagnostics",
    ),
    "analyzer.bridge.inconsistent_readings": TechniqueDefinition(
        "analyzer.bridge.inconsistent_readings", "Bridge analyzer cross-check",
        "panel-bridge", "investigation.instrument_analysis",
    ),
    "cargo.c01.restow": TechniqueDefinition(
        "cargo.c01.restow", "C-01 freight restraint restow",
        "cargo-cradle", "freight.cargo_rigging",
    ),
    "environment.a01.scrubber_service": TechniqueDefinition(
        "environment.a01.scrubber_service", "A-01 filter cartridge service",
        "atmosphere-scrubber", "environmental.atmosphere_maintenance",
    ),
    "captain.bridge.instrument_review": TechniqueDefinition(
        "captain.bridge.instrument_review", "Command bridge limited instrument review",
        "panel-bridge", "investigation.instrument_analysis",
    ),
}

for _name, _tech in TECHNIQUES.items():
    if (_name != _tech.technique_id or not _ID.fullmatch(_name)
            or not _tech.label or not _MARKER.fullmatch(_tech.fixture_marker)
            or _tech.relevant_skill_id not in SKILLS):
        raise RuntimeError(f"Invalid canonical technique: {_name}")
