"""Private world-side read-only shadow evaluation of existing crew.

Not exposed via OOB, local capabilities, ordinary character commands or the
AI handler: task IDs, benchmark difficulties and score components may expose
operator knowledge. There are no skill gains or machine-state consequences.

G4e uses independently stored foundation understanding and exact procedure
familiarity. Initial records are explicitly labelled starting estimates,
not independently verified learning evidence. They do not yet affect live
physical task outcomes or confer authority.
"""
from __future__ import annotations

from dataclasses import dataclass

from world.character_dimensions import validate_profile
from world.character_profiles import profile_for_actor, skill_for_actor
from world.models import CharacterKnowledge, CharacterTechnique
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
    foundation = CharacterKnowledge.objects.filter(
        person=profile, foundation_id=foundation_id,
    ).first()
    technique = (CharacterTechnique.objects.filter(
        person=profile, technique_id=task.technique_id,
    ).first() if task.technique_id is not None else None)
    evaluation = evaluate_shadow(
        task_id,
        proficiency=skill_for_actor(actor, task.skill_id),
        knowledge=foundation.mastery if foundation else 0,
        familiarity=technique.familiarity if technique else 0,
        aptitudes={key: profile.aptitudes[key] for key in task.relevant_aptitudes},
    )
    return WorldShadowComparison(
        person_id=profile.person_id,
        evaluation=evaluation,
        knowledge_source=foundation.source if foundation else "not_recorded",
        familiarity_source=(
            technique.source if technique else
            ("not_recorded" if task.technique_id else "no_technique_required")
        ),
    )
