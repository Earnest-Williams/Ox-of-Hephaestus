"""G4g: bounded conceptual learning from a supervised, assessed lesson.

Normal clients choose activities and submit answers, never mastery or credit.
Every lesson transition runs under execute_work's common ship transaction.
The authored training exercise has no connection to hidden ship fault causes.
"""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q
from world.bootstrap import find_fixture
from world.character_profiles import profile_for_actor
from world.event_journal import emit
from world.learning import _award_for_component
from world.models import CharacterKnowledge, ConceptLesson, CrewEvent, WorkReceipt
from world.skill_catalogue import FOUNDATIONS

from evennia.objects.models import ObjectDB
from evennia.utils import gametime

_ID = re.compile(r"[0-9a-f]{32}")
_DBREF = re.compile(r"#[1-9][0-9]*")
ANSWER_OPTIONS = ("drive_bus", "speed", "insufficient_evidence")
CONTROL_OPTIONS = ("drive_bus", "speed", "none")
OFFER_LIFETIME = 3600.0
LESSON_LIFETIME = 7200.0
REPEAT_INTERVAL = 86400.0


@dataclass(frozen=True, slots=True)
class Course:
    """World-authored instruction with an explicit foundation and teaching ceiling."""

    course_id: str
    title: str
    foundation_id: str
    minimum_instructor_mastery: int
    maximum_learner_mastery: int
    duration: float
    instruction: str


COURSE = Course(
    "mechanical.controlled_comparison.v1",
    "Controlled comparisons in rotating machinery",
    "mechanical.rotating_machinery",
    60,
    70,
    900.0,
    "A change in vibration can accompany a change in shaft speed or electrical drive-bus "
    "loading. Compare repeated runs that change one factor while holding the other fixed. "
    "When both change together, the comparison cannot distinguish them. A supported "
    "factor in a training comparison is not a diagnosis of an actual ship fault.",
)
COURSES = {COURSE.course_id: COURSE}
if COURSE.foundation_id not in FOUNDATIONS:
    raise RuntimeError("Concept course references an unknown theoretical foundation")


def validate_arguments(operation: str, arguments: dict) -> dict:
    """Accept typed activity parameters, excluding scores, evidence and rubrics."""
    if operation == "lesson_offer":
        if (
            set(arguments) == {"course_id", "learner_dbref"}
            and isinstance(arguments["course_id"], str)
            and arguments["course_id"] in COURSES
            and isinstance(arguments["learner_dbref"], str)
            and _DBREF.fullmatch(arguments["learner_dbref"])
        ):
            return dict(arguments)
    elif operation in ("lesson_begin", "lesson_answer"):
        expected = {"lesson_id"}
        if operation == "lesson_answer":
            expected |= {"supported_factor", "controlled_factor"}
        if (
            set(arguments) == expected
            and isinstance(arguments["lesson_id"], str)
            and _ID.fullmatch(arguments["lesson_id"])
            and (
                operation != "lesson_answer"
                or (
                    arguments["supported_factor"] in ANSWER_OPTIONS
                    and arguments["controlled_factor"] in CONTROL_OPTIONS
                )
            )
        ):
            return dict(arguments)
    raise ValueError("Invalid supervised lesson arguments")


def _mastery(person, foundation_id: str) -> int:
    """Read the person's actual theoretical record, never their role or skill proxy."""
    return (
        CharacterKnowledge.objects.filter(person=person, foundation_id=foundation_id)
        .values_list("mastery", flat=True)
        .first()
        or 0
    )


def _qualified(instructor, learner, course: Course) -> bool:
    """A competent instructor must understand more than the learner currently does."""
    teacher_score = _mastery(instructor, course.foundation_id)
    learner_score = _mastery(learner, course.foundation_id)
    return (
        instructor.pk != learner.pk
        and teacher_score >= course.minimum_instructor_mastery
        and teacher_score >= learner_score + 10
        and learner_score < course.maximum_learner_mastery
    )


def _actors_here(teacher, learner, room_dbref: str) -> bool:
    """Require both separately bound bodies at the installed teaching bench."""
    room = find_fixture("room-workshop")
    return bool(
        room
        and room.dbref == room_dbref
        and teacher
        and learner
        and teacher.location == room
        and learner.location == room
    )


def _recent_attempt(learner, course_id: str, now: float) -> bool:
    """Space completed assessments, including failed guesses, by one game day."""
    return ConceptLesson.objects.filter(
        learner=learner,
        course_id=course_id,
        status__in=("passed", "failed"),
        completed_game_time__gt=now - REPEAT_INTERVAL,
    ).exists()


def _draw_exercise() -> dict:
    """Generate new toy measurements and a private deterministic grading rubric."""
    variant = secrets.choice(("drive_bus", "speed", "confounded"))
    base_speed = 600 + 100 * secrets.randbelow(6)
    low = 1 + secrets.randbelow(4)
    high = low + 3 + secrets.randbelow(4)
    observations = []
    for _repeat in range(2):
        for changed in (False, True):
            observations.append(
                {
                    "shaft_rpm": (
                        base_speed * 2 if changed and variant != "drive_bus" else base_speed
                    ),
                    "drive_bus": ("loaded" if changed or variant == "speed" else "idle"),
                    "vibration_mm_s": high if changed else low,
                }
            )
    return {
        "observations": observations,
        "question": "Which single tested factor is supported by this comparison, and "
        "which factor was held fixed? Use insufficient_evidence and none "
        "when both factors changed together. These are idealised training runs.",
        "supported_options": list(ANSWER_OPTIONS),
        "controlled_options": list(CONTROL_OPTIONS),
        "expected": {
            "supported_factor": variant if variant != "confounded" else "insufficient_evidence",
            "controlled_factor": (
                {"drive_bus": "speed", "speed": "drive_bus"}.get(variant, "none")
            ),
        },
    }


def _event(actor, kind: str, lesson: ConceptLesson, *, text: str, data=None) -> dict:
    """Emit only the named participant's observation, with no rubric or mastery score."""
    return emit(
        find_fixture("pump-p01"),
        actor,
        kind,
        text=text,
        data={
            "lesson_id": lesson.pk,
            "course_id": lesson.course_id,
            **(data or {}),
        },
    )


def _refused() -> tuple[bool, str | None]:
    """Use a private, non-enumerating refusal with no learning effect."""
    return False, None


def _offer(actor, request_id: str, arguments: dict, now: float) -> tuple[bool, str | None]:
    """Offer an authored lesson; no learner is enrolled without accepting it."""
    instructor = profile_for_actor(actor)
    pupil = ObjectDB.objects.filter(pk=int(arguments["learner_dbref"][1:])).first()
    learner = profile_for_actor(pupil) if pupil else None
    teacher = actor
    course = COURSES[arguments["course_id"]]
    room = find_fixture("room-workshop")
    if (
        not instructor
        or not learner
        or not room
        or not _actors_here(teacher, pupil, room.dbref)
        or not _qualified(instructor, learner, course)
        or _recent_attempt(learner, course.course_id, now)
        or ConceptLesson.objects.filter(
            instructor=instructor, status__in=("offered", "active"), expires_game_time__gt=now
        ).exists()
        or ConceptLesson.objects.filter(
            Q(instructor=instructor) | Q(learner=instructor),
            status="active",
            expires_game_time__gt=now,
        ).exists()
    ):
        return _refused()
    lesson = ConceptLesson.objects.create(
        lesson_id=request_id,
        course_id=course.course_id,
        instructor=instructor,
        learner=learner,
        room_dbref=room.dbref,
        offered_game_time=now,
        expires_game_time=now + OFFER_LIFETIME,
    )
    event = _event(
        pupil,
        "lesson_offered",
        lesson,
        text=f"{teacher.key} offers {course.title} at the Machine Shop bench.",
        data={"instructor_dbref": teacher.dbref, "room_dbref": room.dbref},
    )
    return True, event["event_id"]


def execute_lesson(
    actor, request_id: str, operation: str, arguments: dict
) -> tuple[bool, str | None]:
    """Apply a lesson stage inside the existing globally receipted work transaction."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Lessons require the authoritative work transaction")
    now = float(gametime.gametime(absolute=True))
    if operation == "lesson_offer":
        return _offer(actor, request_id, arguments, now)
    person = profile_for_actor(actor)
    lesson = (
        ConceptLesson.objects.select_for_update()
        .filter(
            pk=arguments["lesson_id"],
            learner=person,
        )
        .first()
        if person
        else None
    )
    if lesson is None or now >= lesson.expires_game_time:
        return _refused()
    teacher = ObjectDB.objects.filter(pk=int(lesson.instructor.character_dbref[1:])).first()
    course = COURSES[lesson.course_id]
    if not _actors_here(teacher, actor, lesson.room_dbref) or not _qualified(
        lesson.instructor, person, course
    ):
        return _refused()
    if operation == "lesson_begin":
        if (
            lesson.status != "offered"
            or now < lesson.offered_game_time
            or _recent_attempt(person, lesson.course_id, now)
            or ConceptLesson.objects.filter(
                Q(instructor__in=(person, lesson.instructor))
                | Q(learner__in=(person, lesson.instructor)),
                status="active",
                expires_game_time__gt=now,
            ).exists()
        ):
            return _refused()
        lesson.status = "active"
        lesson.started_game_time = now
        lesson.due_game_time = now + course.duration
        lesson.expires_game_time = now + LESSON_LIFETIME
        lesson.qualification = {
            "instructor_person_id": lesson.instructor_id,
            "instructor_mastery": _mastery(lesson.instructor, course.foundation_id),
            "learner_mastery": _mastery(person, course.foundation_id),
            "foundation_id": course.foundation_id,
        }
        lesson.exercise = _draw_exercise()
        lesson.save()
        public_exercise = {
            key: value for key, value in lesson.exercise.items() if key != "expected"
        }
        event = _event(
            actor,
            "lesson_started",
            lesson,
            text=course.instruction,
            data={
                "instructor_dbref": teacher.dbref,
                "due_game_time": lesson.due_game_time,
                "exercise": json.dumps(public_exercise, sort_keys=True),
            },
        )
        return True, event["event_id"]
    if lesson.status != "active" or now < lesson.due_game_time:
        return _refused()
    lesson.answers = {key: arguments[key] for key in ("supported_factor", "controlled_factor")}
    lesson.status = "passed" if lesson.answers == lesson.exercise["expected"] else "failed"
    lesson.completed_game_time = now
    event = _event(
        actor,
        "lesson_assessed",
        lesson,
        text=(
            "The transfer exercise demonstrates this principle."
            if lesson.status == "passed"
            else "The transfer exercise has not demonstrated this principle."
        ),
        data={"result": lesson.status},
    )
    lesson.result_event_id = event["event_id"]
    lesson.save()
    _event(
        teacher,
        "lesson_reviewed",
        lesson,
        text=f"{actor.key} completed the supervised transfer exercise: {lesson.status}.",
        data={"learner_dbref": actor.dbref, "result": lesson.status},
    )
    return True, event["event_id"]


def record_concept_experience(actor, receipt: WorkReceipt) -> int:
    """Credit a passed, actor-owned assessment once, in the same world transaction."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Conceptual learning requires the work transaction")
    if receipt.target != "learning" or receipt.operation != "lesson_answer":
        return 0
    if receipt.actor_dbref != getattr(actor, "dbref", None):
        raise PermissionError("Conceptual evidence belongs to the assessed learner")
    if receipt.outcome.get("status") != "succeeded":
        return 0
    person = profile_for_actor(actor)
    lesson = (
        ConceptLesson.objects.select_for_update()
        .filter(
            pk=receipt.arguments["lesson_id"],
            learner=person,
        )
        .first()
    )
    if lesson is None or lesson.completion_receipt_id is not None:
        return 0
    if (
        receipt.outcome.get("request_id") != receipt.pk
        or receipt.outcome.get("actor_dbref") != actor.dbref
        or receipt.outcome.get("reason") != "world_accepted"
        or receipt.outcome.get("source_event_id") != lesson.result_event_id
        or {key: receipt.arguments.get(key) for key in lesson.answers} != lesson.answers
        or not CrewEvent.objects.filter(
            event_id=lesson.result_event_id,
            recipient_dbref=actor.dbref,
            kind="lesson_assessed",
            details__lesson_id=lesson.pk,
        ).exists()
    ):
        raise RuntimeError("Assessment receipt lacks world-owned lesson provenance")
    lesson.completion_receipt = receipt
    lesson.save(update_fields=["completion_receipt"])
    if lesson.status != "passed":
        return 0
    course = COURSES[lesson.course_id]
    return int(
        _award_for_component(
            person,
            receipt,
            f"learning:{lesson.pk}",
            lesson.course_id,
            "knowledge",
            course.foundation_id,
            score_limit=course.maximum_learner_mastery,
        )
    )


def interrupt_lessons(actor) -> None:
    """Leaving the teaching room ends active instruction; returning cannot restore it."""
    person = profile_for_actor(actor)
    if person is None:
        return
    with transaction.atomic():
        # Use the same serialization order as execute_work, including on PostgreSQL.
        pump = find_fixture("pump-p01")
        if pump is None:
            return
        ObjectDB.objects.select_for_update().get(pk=pump.pk)
        for lesson in ConceptLesson.objects.select_for_update().filter(
            Q(instructor=person) | Q(learner=person),
            status="active",
        ):
            if actor.location is not None and actor.location.dbref == lesson.room_dbref:
                continue
            lesson.status = "interrupted"
            lesson.completed_game_time = float(gametime.gametime(absolute=True))
            lesson.save(update_fields=["status", "completed_game_time"])
            for participant in (lesson.instructor, lesson.learner):
                body = ObjectDB.objects.filter(pk=int(participant.character_dbref[1:])).first()
                if body:
                    _event(
                        body,
                        "lesson_interrupted",
                        lesson,
                        text="Supervised instruction ended when a participant left the bench.",
                    )
