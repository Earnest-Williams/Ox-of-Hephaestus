"""G4d read-only competency comparisons, never live task outcomes.

Task profiles isolate how practical skill, theoretical knowledge, formative
aptitudes and equipment familiarity *might* affect relative performance.
No randomness, physical transition, resource consumption, work receipt,
XP, agent plan, or hidden-cause observation is emitted by this module.

The numerical policy is PROVISIONAL calibration, not a chance-of-success
formula. The live captain qualification gate separately checks one canonical
world skill and is not derived from these shadow scores.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from world.character_dimensions import APTITUDES
from world.skill_catalogue import SKILLS

# Ordered: practical skill, conceptual knowledge, formative aptitude,
# equipment/procedure familiarity. Each profile sums to exactly 100.
WEIGHTS: dict[str, tuple[int, int, int, int]] = {
    "routine": (65, 15, 15, 5),
    "unfamiliar_repair": (60, 15, 20, 5),
    "novel_investigation": (35, 25, 35, 5),
}


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    task_id: str
    skill_id: str
    profile: str
    relevant_aptitudes: tuple[str, ...]
    difficulty: int
    knowledge_floor: int = 0


@dataclass(frozen=True, slots=True)
class ShadowEvaluation:
    """Only an indicative comparison, NOT an authorisation or outcome."""

    task_id: str
    mode: str
    skill_id: str
    primary_skill: int
    conceptual_knowledge: int
    aptitude_score: float
    familiarity: int
    provisional_score: float
    provisional_margin: float
    theoretical_foothold: bool
    difficulty: int


TASKS: dict[str, TaskDefinition] = {
    "pump.routine_service": TaskDefinition(
        "pump.routine_service", "mechanical.pump_service", "routine",
        ("dexterity", "spatial_sense"), 55,
    ),
    "pump.unfamiliar_repair": TaskDefinition(
        "pump.unfamiliar_repair", "mechanical.pump_service",
        "unfamiliar_repair", ("dexterity", "spatial_sense", "reasoning"), 65,
        knowledge_floor=15,
    ),
    "pump.novel_interference": TaskDefinition(
        "pump.novel_interference", "mechanical.vibration_diagnostics",
        "novel_investigation", ("reasoning", "attention", "perception"), 70,
        knowledge_floor=20,
    ),
    "analyzer.inconsistent_readings": TaskDefinition(
        "analyzer.inconsistent_readings", "investigation.instrument_analysis",
        "novel_investigation", ("reasoning", "perception", "attention"), 65,
        knowledge_floor=20,
    ),
    "cargo.restow": TaskDefinition(
        "cargo.restow", "freight.cargo_rigging", "routine",
        ("agility", "spatial_sense", "dexterity"), 50,
    ),
    "environment.scrubber_service": TaskDefinition(
        "environment.scrubber_service", "environmental.atmosphere_maintenance",
        "routine", ("dexterity", "attention"), 50,
    ),
    "captain.bridge_instrument_review": TaskDefinition(
        "captain.bridge_instrument_review", "investigation.instrument_analysis",
        "routine", ("perception", "attention"), 45,
    ),
}


def _percent(value: int, field: str) -> int:
    if type(value) is not int or not 0 <= value <= 100:
        raise ValueError(f"{field} must be an integer 0-100")
    return value


def evaluate_shadow(
    task_id: str,
    *,
    proficiency: int,
    knowledge: int,
    familiarity: int,
    aptitudes: Mapping[str, int],
) -> ShadowEvaluation:
    """Compare capabilities; never determine whether work physically succeeds.

    Input scores are to be provided by trusted world state or synthetic test
    fixtures. This function is not a client-requestable command or contract.
    """
    try:
        task = TASKS[task_id]
    except (KeyError, TypeError) as exc:
        raise ValueError("Unrecognised shadow task") from exc
    p = _percent(proficiency, "Proficiency")
    k = _percent(knowledge, "Conceptual knowledge")
    f = _percent(familiarity, "Equipment familiarity")
    if not isinstance(aptitudes, Mapping) or set(aptitudes) != set(task.relevant_aptitudes):
        raise ValueError("All and only task-relevant aptitudes are required")
    if any(type(value) is not int or not 1 <= value <= 10
           for value in aptitudes.values()):
        raise ValueError("Aptitudes must be integers from 1 through 10")
    aptitude_score = sum(aptitudes.values()) * 10 / len(task.relevant_aptitudes)
    sw, kw, aw, fw = WEIGHTS[task.profile]
    score = (p * sw + k * kw + aptitude_score * aw + f * fw) / 100
    return ShadowEvaluation(
        task_id=task.task_id,
        mode="shadow",
        skill_id=task.skill_id,
        primary_skill=p,
        conceptual_knowledge=k,
        aptitude_score=round(aptitude_score, 3),
        familiarity=f,
        provisional_score=round(score, 3),
        provisional_margin=round(score - task.difficulty, 3),
        theoretical_foothold=k >= task.knowledge_floor,
        difficulty=task.difficulty,
    )


def compare_shadow(task_id: str, candidates: Mapping[str, dict]) -> dict[str, ShadowEvaluation]:
    """Deterministic synthetic trials with no world access or effects."""
    if not isinstance(candidates, Mapping):
        raise ValueError("Candidates must be named task-input mappings")
    return {
        name: evaluate_shadow(task_id, **inputs)
        for name, inputs in candidates.items()
    }


for _task in TASKS.values():
    if _task.skill_id not in SKILLS or _task.profile not in WEIGHTS:
        raise RuntimeError(f"Invalid shadow task {_task.task_id}")
    if (not _task.relevant_aptitudes
            or len(_task.relevant_aptitudes) != len(set(_task.relevant_aptitudes))
            or set(_task.relevant_aptitudes) - set(APTITUDES)):
        raise RuntimeError(f"Invalid shadow task aptitudes: {_task.task_id}")
    if (type(_task.difficulty) is not int or not 0 <= _task.difficulty <= 100
            or type(_task.knowledge_floor) is not int
            or not 0 <= _task.knowledge_floor <= 100):
        raise RuntimeError(f"Invalid shadow task calibration: {_task.task_id}")
if any(sum(weights) != 100 or any(w < 0 for w in weights)
       for weights in WEIGHTS.values()):
    raise RuntimeError("Shadow weights must sum to 100")
