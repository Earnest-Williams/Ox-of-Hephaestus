"""Private world-side read-only shadow evaluation of existing crew.

Not exposed via OOB, local capabilities, ordinary character commands or the
AI handler: task IDs, benchmark difficulties and score components may expose
operator knowledge. There are no skill gains or machine-state consequences.

G4d has no independently verified theory/procedure familiarity ledger yet.
A same-foundation practical-skill aggregate is *explicitly a proxy* for the
former, and equipment familiarity is held at zero. Do not use it for live
diagnostic outcomes until evidence-backed components exist.
"""
from __future__ import annotations

from dataclasses import dataclass

from world.character_dimensions import validate_profile
from world.character_profiles import profile_for_actor, skill_for_actor
from world.models import CharacterSkill
from world.skill_catalogue import SKILLS
from world.task_resolution import TASKS, ShadowEvaluation, evaluate_shadow


@dataclass(frozen=True, slots=True)
class WorldShadowComparison:
    person_id: str
    evaluation: ShadowEvaluation
    knowledge_source: str
    familiarity_source: str


def evaluate_world_shadow(actor, task_id: str) -> WorldShadowComparison:
    """Operator-only, side-effect-free world character comparison."""
    if task_id not in TASKS:
        raise ValueError("Unknown task")
    profile = profile_for_actor(actor)
    if profile is None:
        raise ValueError("No authoritative world profile for this character")
    validate_profile(profile.aptitudes, profile.psychology)
    task = TASKS[task_id]
    foundation_id = SKILLS[task.skill_id].foundation_id
    same_foundation = tuple(
        definition.skill_id for definition in SKILLS.values()
        if definition.foundation_id == foundation_id
    )
    # Proxy is deliberately explicit: vocational practice is not identical
    # to theoretical knowledge, and this is only a calibration comparison.
    known = CharacterSkill.objects.filter(
        person=profile, skill_id__in=same_foundation,
    ).values_list("proficiency", flat=True)
    conceptual_proxy = max(known, default=0)
    evaluation = evaluate_shadow(
        task_id,
        proficiency=skill_for_actor(actor, task.skill_id),
        knowledge=conceptual_proxy,
        familiarity=0,  # G4d records no learned equipment procedure
        aptitudes={key: profile.aptitudes[key] for key in task.relevant_aptitudes},
    )
    return WorldShadowComparison(
        person_id=profile.person_id,
        evaluation=evaluation,
        knowledge_source="provisional_same_foundation_skill_proxy",
        familiarity_source="not_yet_world_modelled",
    )
