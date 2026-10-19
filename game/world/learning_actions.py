"""One bounded world-work entry point for independently verified learning activities."""

from __future__ import annotations

from world import concept_learning, inquiry_learning

LESSON_OPERATIONS = frozenset(("lesson_offer", "lesson_begin", "lesson_answer"))
INQUIRY_OPERATIONS = frozenset(("inquiry_predict", "inquiry_review", "inquiry_reflect"))


def _activity(operation: str):
    """Choose only an explicitly registered world activity, never client-authored code."""
    if operation in LESSON_OPERATIONS:
        return concept_learning
    if operation in INQUIRY_OPERATIONS:
        return inquiry_learning
    raise ValueError("Unsupported world learning activity")


def validate_arguments(operation: str, arguments: dict) -> dict:
    """Retain each activity's strict parameter schema and provenance boundary."""
    return _activity(operation).validate_arguments(operation, arguments)


def execute_learning(actor, request_id: str, operation: str, arguments: dict):
    """Dispatch under the existing common ship lock and world-work transaction."""
    activity = _activity(operation)
    if activity is concept_learning:
        return activity.execute_lesson(actor, request_id, operation, arguments)
    return activity.execute_inquiry(actor, request_id, operation, arguments)


def record_learning(actor, receipt) -> int:
    """Let the owning activity validate its newly committed authoritative receipt."""
    activity = _activity(receipt.operation)
    if activity is concept_learning:
        return activity.record_concept_experience(actor, receipt)
    return activity.record_inquiry_experience(actor, receipt)
