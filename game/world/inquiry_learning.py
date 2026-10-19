"""G4h: earn investigative understanding from personally conducted inquiry.

Only prior predictions, authenticated firsthand reports and a bounded transfer
check can earn conceptual credit. Neither predictions nor diagnoses are graded
against the case's hidden cause. The grader never loads that cause or test noise.
"""

from __future__ import annotations

import json
import re
import secrets

from django.db import transaction
from world.bootstrap import find_fixture
from world.character_profiles import profile_for_actor
from world.event_journal import emit
from world.investigation import _local_role
from world.learning import _award_for_component
from world.models import (
    CrewEvent,
    InquiryLearningAttempt,
    InvestigationCase,
    WorkReceipt,
)
from world.skill_catalogue import FOUNDATIONS

from evennia.utils import gametime

FOUNDATION = "investigation.methods"
TASK_ID = "investigation.evidence_limits.v1"
MAX_MASTERY = 70
REVIEW_SECONDS = 300.0
ATTEMPT_LIFETIME = 86400.0
CREDIT_INTERVAL = 86400.0
READINGS = ("supports", "does_not_support")
INTERPRETATIONS = {
    "supports": "supported_unconfirmed",
    "does_not_support": "unsupported_not_excluded",
}
SOURCE_COUNTS = ("one_source", "two_sources")
_CASE_ID = re.compile(r"[0-9a-f]{32}")
if FOUNDATION not in FOUNDATIONS:
    raise RuntimeError("Inquiry learning references an unknown foundation")


def validate_arguments(operation: str, arguments: dict) -> dict:
    """Allow forecasts and reasoning choices, never a cause, score or evidence ID."""
    expected = {"case_id"}
    if operation == "inquiry_predict":
        expected.add("prediction")
    elif operation == "inquiry_reflect":
        expected |= {"interpretation", "independent_sources"}
    elif operation != "inquiry_review":
        raise ValueError("Unknown investigative learning activity")
    if (
        set(arguments) != expected
        or not isinstance(arguments.get("case_id"), str)
        or not _CASE_ID.fullmatch(arguments["case_id"])
    ):
        raise ValueError("A typed world case identity is required")
    if operation == "inquiry_predict" and arguments["prediction"] not in READINGS:
        raise ValueError("Prediction must concern the next local probe's reading")
    if operation == "inquiry_reflect" and (
        arguments["interpretation"] not in tuple(INTERPRETATIONS.values())
        or arguments["independent_sources"] not in SOURCE_COUNTS
    ):
        raise ValueError("Unsupported evidence interpretation")
    return dict(arguments)


def _case(case_id: str):
    """Load only case provenance; latent causes and random draws stay deferred."""
    return (
        InvestigationCase.objects.select_for_update()
        .only(
            "case_id",
            "status",
            "samples",
            "reports",
            "questions",
            "challenges",
            "probes",
        )
        .filter(pk=case_id)
        .first()
    )


def _local(actor) -> bool:
    """Reuse physical station/person authorization without rebuilding the world."""
    ship = {
        "officer": find_fixture("crew-bridge"),
        "watch": find_fixture("crew-watch"),
        "chief": find_fixture("crew-chief"),
        "cargo": find_fixture("crew-cargo"),
        "environment": find_fixture("crew-environment"),
        "operations": find_fixture("panel-operations"),
        "pump": find_fixture("pump-p01"),
        "cradle": find_fixture("cargo-cradle"),
        "scrubber": find_fixture("atmosphere-scrubber"),
    }
    return all(value is not None for value in ship.values()) and _local_role(actor, ship) in (
        "ari",
        "iona",
        "mara",
        "teo",
    )


def _source(actor, event_id: str, case_id: str, kinds: tuple[str, ...]):
    """Read only the actor's exact source event for this same case and stage."""
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 64:
        return None
    return CrewEvent.objects.filter(
        event_id=event_id,
        recipient_dbref=actor.dbref,
        kind__in=kinds,
        details__case_id=case_id,
    ).first()


def _receipt(actor, event_id: str, case_id: str, operations: tuple[str, ...]):
    """Require an already successful global work receipt for a real source report."""
    return WorkReceipt.objects.filter(
        actor_dbref=actor.dbref,
        target="ship",
        operation__in=operations,
        arguments__case_id=case_id,
        outcome__status="succeeded",
        outcome__reason="world_accepted",
        outcome__source_event_id=event_id,
    ).first()


def _event(actor, kind: str, attempt, *, text: str, data=None):
    """Keep the learning activity and its feedback private to its actual investigator."""
    return emit(
        find_fixture("pump-p01"),
        actor,
        kind,
        text=text,
        data={
            "case_id": attempt.case_id,
            "prediction_id": attempt.pk,
            **(data or {}),
        },
    )


def _exercise() -> dict:
    """Generate case-independent transfer material about copied versus separate samples."""
    source = "training-" + secrets.token_hex(8)
    second_source = source if secrets.choice((True, False)) else "training-" + secrets.token_hex(8)
    first_reading = secrets.choice(READINGS)
    return {
        "reports": [
            {"source_id": source, "reading": first_reading},
            {
                "source_id": second_source,
                "reading": first_reading if source == second_source else secrets.choice(READINGS),
            },
        ],
        "question": "In this separate training example, each distinct source ID identifies "
        "one independently collected measurement. Repeated IDs quote that same "
        "measurement. How many independent measurement sources are represented?",
        "options": list(SOURCE_COUNTS),
    }


def _predict(actor, person, case, request_id: str, arguments: dict, now: float):
    """Record a next-probe forecast only after real initial evidence and before sampling."""
    if (
        actor.dbref in case.probes
        or InquiryLearningAttempt.objects.filter(person=person, case=case).exists()
    ):
        return False, None
    initial_id = case.reports.get(actor.dbref)
    inquiry = case.questions.get(actor.dbref) or case.challenges.get(actor.dbref)
    inquiry_id = inquiry.get("event_id") if inquiry else None
    initial = _source(actor, initial_id, case.pk, ("anomaly_report_recorded",))
    registered = _source(
        actor, inquiry_id, case.pk, ("anomaly_question_recorded", "anomaly_challenge_recorded")
    )
    if (
        not initial
        or not registered
        or initial.sequence >= registered.sequence
        or not _receipt(actor, initial_id, case.pk, ("anomaly_report",))
        or not _receipt(actor, inquiry_id, case.pk, ("anomaly_question", "anomaly_challenge"))
    ):
        return False, None
    attempt = InquiryLearningAttempt.objects.create(
        prediction_id=request_id,
        person=person,
        case=case,
        prediction=arguments["prediction"],
        initial_report_event_id=initial_id,
        inquiry_event_id=inquiry_id,
        prediction_event_id="",
        created_game_time=now,
        expires_game_time=now + ATTEMPT_LIFETIME,
    )
    event = _event(
        actor,
        "inquiry_prediction_recorded",
        attempt,
        text="Your forecast of the next local probe's reading was saved before the test.",
        data={"prediction": attempt.prediction, "basis_event_id": inquiry_id},
    )
    attempt.prediction_event_id = event["event_id"]
    attempt.save(update_fields=["prediction_event_id"])
    return True, event["event_id"]


def _review(actor, case, attempt, now: float):
    """Bind the subsequent actual sample and its authenticated firsthand report."""
    probe = case.probes.get(actor.dbref, {})
    sample_id, report_id = probe.get("sample_event_id"), probe.get("report_event_id")
    sample = _source(actor, sample_id, case.pk, ("anomaly_probe_sampled",))
    report = _source(actor, report_id, case.pk, ("anomaly_probe_report_recorded",))
    prediction = _source(
        actor, attempt.prediction_event_id, case.pk, ("inquiry_prediction_recorded",)
    )
    receipt = _receipt(actor, report_id, case.pk, ("anomaly_probe_report",))
    if (
        attempt.status != "predicted"
        or not attempt.prediction_receipt_id
        or not sample
        or not report
        or not prediction
        or not receipt
        or not prediction.sequence < sample.sequence < report.sequence
        or sample.details.get("quality") != "indicative_only"
        or sample.details.get("reading") not in READINGS
        or sample.details.get("reading") != probe.get("reading")
        or report.details.get("sample_event_id") != sample_id
        or report.details.get("reading") != sample.details["reading"]
        or report.details.get("tested_hypothesis") != sample.details.get("tested_hypothesis")
    ):
        return False, None
    attempt.status = "reviewing"
    attempt.sample_event_id = sample_id
    attempt.report_event_id = report_id
    attempt.report_receipt = receipt
    attempt.reading = sample.details["reading"]
    attempt.tested_hypothesis = sample.details["tested_hypothesis"]
    attempt.due_game_time = now + REVIEW_SECONDS
    attempt.exercise = _exercise()
    attempt.save()
    event = _event(
        actor,
        "inquiry_review_ready",
        attempt,
        text="Review your personally reported indicative test. Support does not confirm a "
        "cause; lack of support does not exclude it. A copied report is not another "
        "independent measurement. Apply these principles to your result and the "
        "separate training example.",
        data={
            "reading": attempt.reading,
            "tested_hypothesis": attempt.tested_hypothesis,
            "prediction": attempt.prediction,
            "sample_event_id": sample_id,
            "report_event_id": report_id,
            "due_game_time": attempt.due_game_time,
            "transfer_exercise": json.dumps(attempt.exercise, sort_keys=True),
        },
    )
    return True, event["event_id"]


def execute_inquiry(actor, request_id: str, operation: str, arguments: dict):
    """Perform one actor-local learning stage under execute_work's common lock."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Investigative learning requires the world work transaction")
    person = profile_for_actor(actor)
    case = _case(arguments["case_id"])
    if person is None or case is None or not _local(actor):
        return False, None
    now = float(gametime.gametime(absolute=True))
    if operation == "inquiry_predict":
        if case.status != "open":
            return False, None
        return _predict(actor, person, case, request_id, arguments, now)
    attempt = (
        InquiryLearningAttempt.objects.select_for_update()
        .filter(
            person=person,
            case=case,
        )
        .first()
    )
    if attempt is None or now < attempt.created_game_time or now >= attempt.expires_game_time:
        return False, None
    if operation == "inquiry_review":
        return _review(actor, case, attempt, now)
    if attempt.status != "reviewing" or now < attempt.due_game_time:
        return False, None
    expected_sources = (
        "one_source"
        if len({r["source_id"] for r in attempt.exercise["reports"]}) == 1
        else "two_sources"
    )
    attempt.answers = {key: arguments[key] for key in ("interpretation", "independent_sources")}
    passed = (
        attempt.answers["interpretation"] == INTERPRETATIONS[attempt.reading]
        and attempt.answers["independent_sources"] == expected_sources
    )
    attempt.status = "passed" if passed else "failed"
    attempt.completed_game_time = now
    event = _event(
        actor,
        "inquiry_reflected",
        attempt,
        text=(
            "Your explanation passed the evidence-limits and source-independence check."
            if passed
            else "Your explanation did not pass this investigative-method check."
        ),
        data={"result": attempt.status},
    )
    attempt.result_event_id = event["event_id"]
    attempt.save()
    return True, event["event_id"]


def record_inquiry_experience(actor, receipt: WorkReceipt) -> int:
    """Attribute genuine reflective learning once, without consulting latent truth."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Investigative learning requires the world work transaction")
    if receipt.target != "learning" or receipt.operation == "inquiry_review":
        return 0
    if (
        receipt.actor_dbref != getattr(actor, "dbref", None)
        or receipt.outcome.get("actor_dbref") != receipt.actor_dbref
        or receipt.outcome.get("request_id") != receipt.pk
    ):
        raise PermissionError("Investigative learning belongs to the actual investigator")
    if receipt.outcome.get("status") != "succeeded":
        return 0
    attempt = InquiryLearningAttempt.objects.select_for_update().get(
        person=profile_for_actor(actor),
        case_id=receipt.arguments["case_id"],
    )
    predicting = receipt.operation == "inquiry_predict"
    event_id = attempt.prediction_event_id if predicting else attempt.result_event_id
    event_kind = "inquiry_prediction_recorded" if predicting else "inquiry_reflected"
    if (
        receipt.outcome.get("reason") != "world_accepted"
        or receipt.outcome.get("source_event_id") != event_id
        or not _source(actor, event_id, attempt.case_id, (event_kind,))
    ):
        raise RuntimeError("Investigative learning requires its exact world source event")
    if predicting:
        if attempt.prediction_receipt_id is None:
            attempt.prediction_receipt = receipt
            attempt.save(update_fields=["prediction_receipt"])
        return 0
    if attempt.completion_receipt_id is not None:
        return 0
    if (
        attempt.status not in ("passed", "failed")
        or {key: receipt.arguments.get(key) for key in attempt.answers} != attempt.answers
    ):
        raise RuntimeError("Assessment receipt does not match the completed reflection")
    attempt.completion_receipt = receipt
    attempt.save(update_fields=["completion_receipt"])
    if attempt.status != "passed":
        return 0
    spaced = (
        not InquiryLearningAttempt.objects.filter(
            person=attempt.person,
            status__in=("passed", "failed"),
            completed_game_time__gt=receipt.game_time - CREDIT_INTERVAL,
            completed_game_time__lte=receipt.game_time,
        )
        .exclude(pk=attempt.pk)
        .exists()
    )
    return int(
        _award_for_component(
            attempt.person,
            receipt,
            f"inquiry:{attempt.case_id}",
            TASK_ID,
            "knowledge",
            FOUNDATION,
            score_limit=MAX_MASTERY,
            credit_allowed=spaced,
            knowledge_source="world_verified_inquiry",
        )
    )
