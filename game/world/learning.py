"""G4f practice credit from completed, world-owned consequential work.

This function is called ONLY inside the authoritative execute_work transaction
AFTER a WorkReceipt exists. It never accepts model-generated evidence, raw
client arguments or unsupported claims of training. Work-event/source IDs
and existing world locks control replay and concurrency.

Current training is deliberately narrow: a physical repair/restow/replacement
improves practical skill and familiarity with that precise procedure, NOT
theoretical knowledge or psychological traits. G4g conceptual instruction
and G4h inquiry enter through separately validated learning activities. Learning
from well-diagnosed physical failures still requires its own evidence type.
"""

from __future__ import annotations

from django.db import transaction
from world.character_profiles import profile_for_actor
from world.models import (
    CharacterKnowledge,
    CharacterLearningEvidence,
    CharacterSkill,
    CharacterTechnique,
    WorkReceipt,
)
from world.task_resolution import TASKS

LEARNING_WINDOW_SECONDS = 3600.0
MAX_CREDITED_REPETITIONS = 3

# Only genuinely executed, receipt-backed physical work; no inspections,
# alarms, attempted/refused actions, private descriptions, hails or reports.
ELIGIBLE_WORK: dict[tuple[str, str], str] = {
    ("pump", "repair"): "pump.routine_service",
    ("cargo", "restow"): "cargo.restow",
    ("scrubber", "replace"): "environment.scrubber_service",
}


def progression_threshold(level: int) -> int:
    """Increasing actual work needed for a single proficiency point."""
    if type(level) is not int or not 0 <= level <= 100:
        raise ValueError("Proficiency must be between zero and one hundred")
    if level < 25:
        return 4
    if level < 50:
        return 7
    if level < 75:
        return 12
    if level < 90:
        return 20
    return 30


def _award_for_component(
    person,
    receipt,
    event_key: str,
    task_id: str,
    component_kind: str,
    component_id: str,
    *,
    score_limit: int = 100,
    credit_allowed: bool = True,
    knowledge_source: str = "world_verified_instruction",
) -> bool:
    """Record one verified event and bounded progress on one independent ledger.

    Callers must first verify the activity's provenance and eligibility. A
    curriculum ceiling prevents an elementary course teaching expert mastery.
    """
    if component_kind == "skill":
        instance, _ = CharacterSkill.objects.select_for_update().get_or_create(
            person=person,
            skill_id=component_id,
            defaults={"proficiency": 0, "source": "world_practice_first_success"},
        )
        score_field = "proficiency"
    elif component_kind == "technique":
        instance, _ = CharacterTechnique.objects.select_for_update().get_or_create(
            person=person,
            technique_id=component_id,
            defaults={"familiarity": 0, "source": "world_practice_first_success"},
        )
        score_field = "familiarity"
    elif component_kind == "knowledge":
        instance, _ = CharacterKnowledge.objects.select_for_update().get_or_create(
            person=person,
            foundation_id=component_id,
            defaults={
                "mastery": 0,
                "source": knowledge_source,
                "first_recorded_game_time": receipt.game_time,
            },
        )
        score_field = "mastery"
    else:
        raise ValueError("Unknown learning component")
    progress_field = "study_progress" if component_kind == "knowledge" else "practice_progress"

    # If the same physical event was rewrapped under another request ID,
    # do not credit it twice and do not create a second evidence row.
    if CharacterLearningEvidence.objects.filter(
        person=person,
        event_key=event_key,
        component_kind=component_kind,
        component_id=component_id,
    ).exists():
        return False

    recent = CharacterLearningEvidence.objects.filter(
        person=person,
        component_kind=component_kind,
        component_id=component_id,
        game_time__gt=receipt.game_time - LEARNING_WINDOW_SECONDS,
        game_time__lte=receipt.game_time,
        credit_units__gt=0,
    ).count()
    previous_score = getattr(instance, score_field)
    previous_progress = getattr(instance, progress_field)
    credit = int(
        credit_allowed and previous_score < score_limit and recent < MAX_CREDITED_REPETITIONS
    )
    next_score = previous_score
    next_progress = previous_progress + credit
    if (
        credit
        and next_progress >= progression_threshold(previous_score)
        and previous_score < score_limit
    ):
        next_score += 1
        next_progress -= progression_threshold(previous_score)
    if credit and next_score >= score_limit:
        next_progress = 0
    if credit:
        setattr(instance, score_field, next_score)
        setattr(instance, progress_field, next_progress)
        instance.save(update_fields=[score_field, progress_field])

    CharacterLearningEvidence.objects.create(
        person=person,
        receipt=receipt,
        event_key=event_key,
        task_id=task_id,
        component_kind=component_kind,
        component_id=component_id,
        credit_units=credit,
        score_before=previous_score,
        score_after=next_score,
        progress_before=previous_progress,
        progress_after=next_progress,
        game_time=receipt.game_time,
    )
    return True


def record_work_experience(actor, receipt: WorkReceipt) -> int:
    """Authoritative post-work hook. Must share execute_work's transaction."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Experience requires the physical work transaction")
    if (
        receipt.actor_dbref != getattr(actor, "dbref", None)
        or receipt.outcome.get("request_id") != receipt.request_id
        or receipt.outcome.get("actor_dbref") != receipt.actor_dbref
    ):
        raise PermissionError("Work experience cannot be claimed for another actor")

    task_id = ELIGIBLE_WORK.get((receipt.target, receipt.operation))
    if task_id is None or receipt.outcome.get("status") != "succeeded":
        return 0
    if receipt.outcome.get("reason") != "transition_applied":
        raise RuntimeError("Unexpected accepted-work provenance for credit")
    source_event_id = receipt.outcome.get("source_event_id")
    if not isinstance(source_event_id, str) or not source_event_id or len(source_event_id) > 96:
        raise RuntimeError("Completed physical work must name its world event")

    person = profile_for_actor(actor)
    if person is None:
        return 0  # unregistered world actor; no fabricated person records
    task = TASKS[task_id]
    if not task.technique_id:
        raise RuntimeError("Learning-eligible work lacks a canonical procedure")
    event_key = f"{receipt.target}:{source_event_id}"
    result = 0
    for kind, topic in (
        ("skill", task.skill_id),
        ("technique", task.technique_id),
    ):
        result += int(
            _award_for_component(
                person,
                receipt,
                event_key,
                task_id,
                kind,
                topic,
            )
        )
    return result


for _work, _task_id in ELIGIBLE_WORK.items():
    if _task_id not in TASKS or not TASKS[_task_id].technique_id:
        raise RuntimeError(f"Learning operation references unsupported task: {_work}")
