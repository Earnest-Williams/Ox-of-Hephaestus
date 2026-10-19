"""Versioned, world-owned skill catalogue; no classes or character levels.

Disciplines organise human-readable trades. Foundation identifiers describe
transferable conceptual knowledge but do not create an automatic proficiency
bonus. Task resolution and experience come in later changes.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from world.character_dimensions import APTITUDES

CATALOGUE_VERSION = 1
DISCIPLINES = (
    "mechanical", "electrical", "propulsion", "navigation",
    "freight", "environmental", "computing", "fabrication",
    "emergency", "medicine", "biology", "investigation",
    "command", "commerce", "communications", "security",
)

FOUNDATIONS = {
    "mechanical.rotating_machinery": "Rotating machinery",
    "mechanical.fluid_systems": "Fluid systems",
    "electrical.power_systems": "Electrical power systems",
    "propulsion.drives": "Propulsion and thermal transfer",
    "navigation.trajectory": "Motion and navigation",
    "freight.load_mechanics": "Freight mechanics",
    "environmental.life_support": "Shipboard environmental systems",
    "computing.control_systems": "Instrumentation and control",
    "fabrication.materials": "Manufacturing and materials",
    "emergency.survival": "Emergency shipboard operations",
    "medicine.human_health": "Human health",
    "biology.living_systems": "Living systems",
    "investigation.methods": "Scientific reasoning and evidence",
    "command.operations": "Shipboard management",
    "commerce.trade": "Trading and commercial obligations",
    "communications.social": "Social communication",
    "security.protection": "Protective operations",
}

_ID = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    skill_id: str
    label: str
    discipline: str
    foundation_id: str
    aptitudes: tuple[str, ...]


# One row groups skills with a common foundation and task-relevant aptitudes.
# A later task definition can select a more specific aptitude weighting.
_GROUPS = (
    ("mechanical", "mechanical.rotating_machinery", ("dexterity", "spatial_sense"),
     (("pump_service", "Pump servicing"), ("bearing_lubrication", "Bearing lubrication"),
      ("vibration_diagnostics", "Vibration diagnostics"),
      ("shaft_alignment", "Shaft alignment"), ("seal_fitting", "Seal fitting"))),
    ("electrical", "electrical.power_systems", ("attention", "reasoning"),
     (("power_distribution", "Power distribution"), ("motor_generators", "Motor-generators"),
      ("flywheel_control", "Flywheel energy control"))),
    ("propulsion", "propulsion.drives", ("reasoning", "spatial_sense"),
     (("drive_operations", "Drive operation"), ("thermal_management", "Thermal management"),
      ("coolant_chemistry", "Coolant chemistry"))),
    ("navigation", "navigation.trajectory", ("spatial_sense", "reasoning"),
     (("astrogation", "Astrogation"), ("docking", "Docking"),
      ("transit_planning", "FTL transit planning"))),
    ("freight", "freight.load_mechanics", ("spatial_sense", "agility"),
     (("cargo_rigging", "Cargo rigging"), ("cargo_inspection", "Cargo inspection"),
      ("load_balancing", "Load balancing"), ("hazardous_cargo", "Hazardous cargo handling"))),
    ("environmental", "environmental.life_support", ("perception", "reasoning"),
     (("atmosphere_maintenance", "Atmosphere maintenance"),
      ("atmosphere_diagnostics", "Atmosphere diagnostics"),
      ("pressure_control", "Pressure regulation"),
      ("water_reclamation", "Water reclamation"))),
    ("computing", "computing.control_systems", ("attention", "reasoning"),
     (("sensor_calibration", "Sensor calibration"), ("telemetry", "Telemetry"),
      ("automation", "Automation programming"))),
    ("fabrication", "fabrication.materials", ("dexterity", "spatial_sense"),
     (("machining", "Machining"), ("welding", "Welding"),
      ("metallurgy", "Metallurgy"))),
    ("emergency", "emergency.survival", ("nerve", "agility"),
     (("eva", "Pressure suit and EVA"), ("damage_control", "Damage control"),
      ("fire_suppression", "Fire suppression"))),
    ("medicine", "medicine.human_health", ("dexterity", "perception"),
     (("triage", "Medical triage"), ("trauma_care", "Trauma care"),
      ("long_voyage_health", "Long-voyage medicine"))),
    ("biology", "biology.living_systems", ("attention", "memory"),
     (("hydroponics", "Hydroponics"), ("microbiology", "Microbiology"),
      ("ecology", "Ecology"))),
    ("investigation", "investigation.methods", ("reasoning", "perception"),
     (("instrument_analysis", "Instrument analysis"),
      ("experimental_design", "Experimental design"),
      ("evidence_assessment", "Evidence assessment"))),
    ("command", "command.operations", ("attention", "social_insight"),
     (("ship_coordination", "Ship coordination"), ("delegation", "Delegation"),
      ("watch_management", "Watch management"),
      ("crisis_management", "Crisis management"), ("instruction", "Instruction"))),
    ("commerce", "commerce.trade", ("reasoning", "memory"),
     (("freight_contracts", "Freight contracts"), ("accounting", "Accounting"),
      ("procurement", "Procurement"), ("insurance", "Freight insurance"))),
    ("communications", "communications.social", ("social_insight", "memory"),
     (("mediation", "Mediation"), ("negotiation", "Negotiation"),
      ("linguistics", "Linguistics"))),
    ("security", "security.protection", ("perception", "nerve"),
     (("threat_assessment", "Threat assessment"),
      ("defence", "Shipboard defence"), ("subsistence", "Subsistence operations"))),
)


def _build_catalogue() -> dict[str, SkillDefinition]:
    result = {}
    seen_disciplines = set()
    for discipline, foundation, aptitudes, skills in _GROUPS:
        if discipline not in DISCIPLINES or foundation not in FOUNDATIONS:
            raise RuntimeError("Skill definition references an unknown group")
        if not aptitudes or len(set(aptitudes)) != len(aptitudes):
            raise RuntimeError("Skill aptitude definitions must be distinct")
        if any(apt not in APTITUDES for apt in aptitudes):
            raise RuntimeError("Skill definition references an unknown aptitude")
        seen_disciplines.add(discipline)
        for slug, label in skills:
            key = f"{discipline}.{slug}"
            if not _ID.fullmatch(key) or not label or key in result:
                raise RuntimeError(f"Invalid or duplicate skill definition: {key}")
            result[key] = SkillDefinition(key, label, discipline, foundation, aptitudes)
    if seen_disciplines != set(DISCIPLINES):
        raise RuntimeError("Every declared professional discipline needs skills")
    return result


SKILLS = _build_catalogue()

# Exactly the G3f labels. This is a one-time starting estimate conversion,
# never an ability or authority grant. Overlaps take MAXIMUM, not addition.
LEGACY_COMPETENCY_SKILLS = {
    "command": ("command.ship_coordination", "command.crisis_management",
                "command.delegation"),
    "coordination": ("command.watch_management", "command.delegation"),
    "engineering": ("mechanical.pump_service", "mechanical.seal_fitting",
                    "mechanical.vibration_diagnostics"),
    "environment": ("environmental.atmosphere_maintenance",
                    "environmental.atmosphere_diagnostics"),
    "cargo": ("freight.cargo_rigging", "freight.cargo_inspection"),
    "diagnostics": ("investigation.instrument_analysis",
                    "investigation.evidence_assessment"),
}
if set(skill for values in LEGACY_COMPETENCY_SKILLS.values() for skill in values) - set(SKILLS):
    raise RuntimeError("Legacy competency mapping includes unknown skills")


def legacy_proficiency(value: int) -> int:
    """Convert initial 0-4 captain-era estimates to 0-80 on the new scale."""
    if type(value) is not int or value not in range(5):
        raise ValueError("Legacy competence must be an integer from 0 to 4")
    return value * 20


def initial_skill_estimates(legacy: dict[str, int]) -> dict[str, int]:
    """Build separate skill estimates without counting an overlap twice."""
    if not isinstance(legacy, dict):
        raise ValueError("Expected a world-owned legacy competence mapping")
    if set(legacy) - set(LEGACY_COMPETENCY_SKILLS):
        raise ValueError("Unknown legacy competency source")
    estimates: dict[str, int] = {}
    for broad_key, value in legacy.items():
        converted = legacy_proficiency(value)
        for skill_id in LEGACY_COMPETENCY_SKILLS[broad_key]:
            estimates[skill_id] = max(estimates.get(skill_id, 0), converted)
    return estimates
