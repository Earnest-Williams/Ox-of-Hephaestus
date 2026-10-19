"""Operator-only provisioning and independent verification for disposable G4h CI.

The handler never imports this module or reads its world-side baseline file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from world.bootstrap import find_fixture
from world.character_profiles import profile_for_actor
from world.investigation import arm_anomaly
from world.models import (
    CaptainObligation,
    CharacterKnowledge,
    CharacterLearningEvidence,
    CharacterSkill,
    CharacterTechnique,
    CrewEvent,
    InquiryLearningAttempt,
    InvestigationCase,
    WorkReceipt,
)
from world.transport_probe import provision

BASELINE = Path("../.ox-state/g4h-world-baseline.json")


def _snapshot() -> dict:
    """Record independent ledgers and role without exposing physical case secrets."""
    actor = find_fixture("crew-watch")
    person = profile_for_actor(actor)
    return {
        "role": actor.db.crew_role,
        "skills": list(
            CharacterSkill.objects.filter(person=person)
            .order_by("skill_id")
            .values("skill_id", "proficiency", "practice_progress")
        ),
        "techniques": list(
            CharacterTechnique.objects.filter(person=person)
            .order_by("technique_id")
            .values("technique_id", "familiarity", "practice_progress")
        ),
        "knowledge": list(
            CharacterKnowledge.objects.filter(person=person)
            .order_by("foundation_id")
            .values("foundation_id", "mastery", "study_progress")
        ),
    }


def provision_probe() -> None:
    """Create fresh ordinary accounts and one real uncertain, unclosed case."""
    if os.environ.get("OX_INQUIRY_LEARNING_CI") != "1":
        raise RuntimeError("Disposable inquiry provisioning requires explicit opt-in")
    if BASELINE.exists():
        raise RuntimeError("Refusing to replace the existing world-side baseline")
    provision()
    arm_anomaly(cause="scrubber_bypass", seed=6)
    BASELINE.write_text(json.dumps(_snapshot(), sort_keys=True), encoding="utf-8")


def verify_probe() -> None:
    """Independently check sole credit, replay, private evidence and unchanged ledgers."""
    if os.environ.get("OX_INQUIRY_LEARNING_CI") != "1":
        raise RuntimeError("Disposable inquiry verification requires explicit opt-in")
    actor = find_fixture("crew-watch")
    attempt = InquiryLearningAttempt.objects.get(status="passed")
    evidence = CharacterLearningEvidence.objects.get()
    assert attempt.person_id == profile_for_actor(actor).pk == evidence.person_id
    assert (evidence.component_kind, evidence.component_id, evidence.credit_units) == (
        "knowledge",
        "investigation.methods",
        1,
    )
    assert attempt.completion_receipt_id == evidence.receipt_id
    assert evidence.event_key == "inquiry:" + attempt.case_id
    assert attempt.prediction_receipt.operation == "inquiry_predict"
    assert attempt.report_receipt.operation == "anomaly_probe_report"
    assert (
        WorkReceipt.objects.filter(operation="inquiry_reflect", outcome__status="succeeded").count()
        == 1
    )
    assert CrewEvent.objects.filter(kind="inquiry_reflected").count() == 1
    assert InvestigationCase.objects.only("status").get(pk=attempt.case_id).status == "open"
    assert CaptainObligation.objects.get(pk=attempt.case_id).status == "open"
    for event in CrewEvent.objects.filter(kind__startswith="inquiry_"):
        assert event.recipient_dbref == actor.dbref
        assert not {"cause", "signals", "probe_key", "assessment", "probability"} & set(
            event.details
        )
    before, after = json.loads(BASELINE.read_text()), _snapshot()
    expected = next(
        row for row in before["knowledge"] if row["foundation_id"] == "investigation.methods"
    )
    expected["study_progress"] += 1
    assert before == after, (before, after)
    print("OX_G4H_WORLD_VERIFIED_ONCE")
