"""G3e-2 world-owned challenges, follow-up tests, and fallible reassessment.

World truth is a latent cause. Every diagnostic has false positives and false
negatives. Crew challenge/reconsideration is testimony, never authoritative
confirmation of the cause. This module is not imported into the AI handler.
"""
from __future__ import annotations

import random

from django.db import transaction
from evennia.objects.models import ObjectDB

from world.bootstrap import build_ship
from world.event_journal import emit
from world.investigation import CAUSES, SOURCES, _local_role, _open_case

# Each existing specialist can perform a distinct diagnostic at their
# installed station. These are observations, not additional physical fixtures.
# (name, hypothesis tested, true-positive %, false-positive %).
PROBES = {
    "ari": ("bus_reference", "bus_interference", 82, 23),
    "iona": ("thermal_reference", "scrubber_bypass", 73, 27),
    "mara": ("cargo_blank", "cargo_vapors", 82, 24),
    "teo": ("scrubber_differential", "scrubber_bypass", 84, 24),
}


def _specialist_here(actor, ship) -> str | None:
    role = _local_role(actor, ship)
    return role if role in PROBES else None


def _case(case_id):
    """World-open case, even if the bridge has not offered a diagnosis."""
    return _open_case(case_id)


def _authorized_inquiry(case, actor):
    """World-verified question or challenged hypothesis from this actor."""
    return actor.dbref in case.questions or actor.dbref in case.challenges


def _measurement(case, role: str) -> str:
    """Reproducible world-private draw; never publish its probability or cause."""
    name, candidate, true_positive, false_positive = PROBES[role]
    probability = true_positive if case.cause == candidate else false_positive
    # Earlier G3e-1 cases may predate probe_key; their case ID is stable.
    private_key = case.probe_key or case.case_id
    rng = random.Random(f"{private_key}:{role}:{name}")
    return "supports" if rng.randrange(100) < probability else "does_not_support"


@transaction.atomic
def file_challenge(actor, case_id: str, hypothesis: str) -> tuple[bool, str]:
    """One independently reported alternative from a firsthand specialist."""
    ship = build_ship()
    # The world case lock serializes mutations across independently
    # authenticated sessions. WorkReceipt itself holds the pump lock.
    case = _case(case_id)
    role = _specialist_here(actor, ship)
    if (case is None or not case.assessment or role is None
            or hypothesis not in CAUSES
            or hypothesis == case.assessment.get("hypothesis")
            or actor.dbref not in case.reports or _authorized_inquiry(case, actor)):
        return False, "No eligible firsthand alternative for this case"
    basis_id = case.reports[actor.dbref]
    data = {
        "case_id": case_id, "hypothesis": hypothesis,
        "basis_event_id": basis_id, "verification": "hypothesis",
    }
    first = emit(
        ship["pump"], actor, "anomaly_challenge_recorded", sender=actor,
        data=data, text="Your alternative explanation is recorded as a hypothesis.",
    )
    emit(
        ship["pump"], ship["officer"], "anomaly_challenge_received", sender=actor,
        data=data, text=f"{actor.key} questions the bridge explanation.",
    )
    challenges = dict(case.challenges)
    challenges[actor.dbref] = {
        "hypothesis": hypothesis, "event_id": first["event_id"],
        "basis_event_id": basis_id,
    }
    case.challenges = challenges
    case.save(update_fields=["challenges"])
    return True, "Alternative logged as testimony, not as world fact"


@transaction.atomic
def file_question(actor, case_id: str) -> tuple[bool, str]:
    """Independently pursue an unanswered symptom with one diagnostic.

    A specialist must have filed firsthand initial evidence and be at their
    own installed station. There is no prerequisite bridge hypothesis,
    disagreement or permission from another character.
    """
    ship = build_ship()
    case = _case(case_id)
    role = _specialist_here(actor, ship)
    if (case is None or role is None or actor.dbref not in case.reports
            or _authorized_inquiry(case, actor)):
        return False, "No eligible local, firsthand unanswered question"
    indicator, candidate, _tp, _fp = PROBES[role]
    data = {
        "case_id": case_id, "question": "cause_of_analyzer_disagreement",
        "indicator": indicator, "tested_hypothesis": candidate,
        "basis_event_id": case.reports[actor.dbref],
        "status": "open",
    }
    recorded = emit(
        ship["pump"], actor, "anomaly_question_recorded", sender=actor,
        data=data, text="Your independent diagnostic question was registered; no diagnosis is required.",
    )
    emit(
        ship["pump"], ship["officer"], "anomaly_question_received", sender=actor,
        data=data, text=f"{actor.key} requested a second independent instrument reading.",
    )
    questions = dict(case.questions)
    questions[actor.dbref] = {
        "question": data["question"], "indicator": indicator,
        "basis_event_id": data["basis_event_id"],
        "event_id": recorded["event_id"], "status": "open",
    }
    case.questions = questions
    case.save(update_fields=["questions"])
    return True, "World accepted one independent diagnostic question"


@transaction.atomic
def take_probe(actor, case_id: str) -> dict | None:
    """Perform a role-specific diagnostic at the existing physical station.

    Reconnect/retry gets the same persisted result without drawing a new
    sample or generating another event. No authenticated actor may sample
    the hidden cause or another character's instrument remotely.
    """
    ship = build_ship()
    case = _case(case_id)
    role = _specialist_here(actor, ship)
    if (case is None or role is None or not _authorized_inquiry(case, actor)
            or actor.dbref not in case.reports):
        return None
    name, tested, _true, _false = PROBES[role]
    existing = dict(case.probes).get(actor.dbref)
    if existing is not None:
        return {
            "case_id": case_id, "indicator": name, "tested_hypothesis": tested,
            "reading": existing["reading"], "quality": "indicative_only",
            "event_id": existing["sample_event_id"],
        }
    reading = _measurement(case, role)
    data = {
        "case_id": case_id, "indicator": name, "tested_hypothesis": tested,
        "reading": reading, "quality": "indicative_only",
    }
    sample = emit(
        ship["pump"], actor, "anomaly_probe_sampled", data=data,
        text=f"Controlled {name} returns {reading}, not a confirmed cause.",
    )
    probes = dict(case.probes)
    probes[actor.dbref] = {
        "indicator": name, "tested_hypothesis": tested,
        "reading": reading, "sample_event_id": sample["event_id"],
    }
    case.probes = probes
    case.save(update_fields=["probes"])
    return {**data, "event_id": sample["event_id"]}


@transaction.atomic
def report_probe(actor, case_id: str) -> tuple[bool, str]:
    """Report one actual local experiment, not a model-generated measurement."""
    ship = build_ship()
    case = _case(case_id)
    role = _specialist_here(actor, ship)
    if case is None or role is None or not _authorized_inquiry(case, actor):
        return False, "No eligible local diagnostic question or challenge"
    observed = dict(case.probes).get(actor.dbref)
    if observed is None or "report_event_id" in observed:
        return False, "No unreported firsthand experiment"
    data = {
        "case_id": case_id,
        "indicator": observed["indicator"],
        "tested_hypothesis": observed["tested_hypothesis"],
        "reading": observed["reading"],
        "sample_event_id": observed["sample_event_id"],
    }
    first = emit(
        ship["pump"], actor, "anomaly_probe_report_recorded",
        sender=actor, data=data,
        text="Your measured diagnostic result was recorded, without interpretation.",
    )
    emit(
        ship["pump"], ship["officer"], "anomaly_probe_report",
        sender=actor, data=data,
        text=f"{actor.key} supplied a firsthand independent follow-up test.",
    )
    probes = dict(case.probes)
    probes[actor.dbref] = {**observed, "report_event_id": first["event_id"]}
    case.probes = probes
    case.save(update_fields=["probes"])
    return True, "Experiment report forwarded with source provenance"


@transaction.atomic
def file_reconsideration(actor, case_id: str, hypothesis: str) -> tuple[bool, str]:
    """One specialist's updated position after a genuine new measurement."""
    ship = build_ship()
    case = _case(case_id)
    role = _specialist_here(actor, ship)
    if (case is None or role is None or hypothesis not in CAUSES
            or not _authorized_inquiry(case, actor)
            or actor.dbref in case.reconsiderations):
        return False, "No eligible reconsideration"
    probe = dict(case.probes).get(actor.dbref)
    if probe is None or "report_event_id" not in probe:
        return False, "An independently reported follow-up test is required"
    prior = case.challenges.get(actor.dbref, {}).get("hypothesis")
    data = {
        "case_id": case_id, "hypothesis": hypothesis,
        "previous_hypothesis": prior,
        "changed": None if prior is None else hypothesis != prior,
        "basis_event_id": probe["report_event_id"],
        "verification": "hypothesis",
    }
    first = emit(
        ship["pump"], actor, "anomaly_reconsideration_recorded",
        sender=actor, data=data,
        text="Your revised or retained hypothesis is recorded as unverified.",
    )
    emit(
        ship["pump"], ship["officer"], "anomaly_crew_reconsidered",
        sender=actor, data=data,
        text=f"{actor.key} reviewed a diagnostic result and updated their position.",
    )
    reconsiderations = dict(case.reconsiderations)
    reconsiderations[actor.dbref] = {
        "hypothesis": hypothesis, "previous_hypothesis": prior,
        "basis_event_id": probe["report_event_id"],
        "event_id": first["event_id"],
    }
    case.reconsiderations = reconsiderations
    case.save(update_fields=["reconsiderations"])
    return True, "Reconsidered position logged without world validation"


@transaction.atomic
def file_reassessment(actor, case_id: str, hypothesis: str) -> tuple[bool, str]:
    """Bridge revises OR retains a theory after independent contrary evidence."""
    ship = build_ship()
    case = _case(case_id)
    if (case is None or actor != ship["officer"]
            or _local_role(actor, ship) != "lin"
            or hypothesis not in CAUSES or case.reassessment):
        return False, "No authorized outstanding bridge reassessment"
    # Legacy challenge-based G3e-2 requires post-test views. If at
    # least one independent question was opened, raw firsthand reports are
    # sufficient: a specialist needn't guess a cause to contribute data.
    if case.questions:
        evidence_by_actor = {
            dbref: entry["report_event_id"]
            for dbref, entry in case.probes.items()
            if "report_event_id" in entry
            and (dbref in case.questions or dbref in case.challenges)
        }
    else:
        evidence_by_actor = {
            dbref: entry["basis_event_id"]
            for dbref, entry in case.reconsiderations.items()
        }
    if not (
        any(ship[r].dbref in evidence_by_actor for r in ("watch", "chief"))
        and any(ship[r].dbref in evidence_by_actor for r in ("cargo", "environment"))
    ):
        return False, "Independent engineering and specialist evidence required"
    evidence = sorted(evidence_by_actor.values())
    original = case.assessment.get("hypothesis")
    data = {
        "case_id": case_id, "hypothesis": hypothesis,
        "previous_hypothesis": original,
        "changed": None if original is None else hypothesis != original,
        "evidence_count": len(evidence), "verification": "unconfirmed",
    }
    first = emit(
        ship["pump"], actor, "anomaly_reassessment_recorded",
        sender=actor, data=data,
        text="Follow-up assessment logged; the hidden cause is still unverified.",
    )
    for role, (member, _title, _fixture, _station, _dial) in SOURCES.items():
        if role != "lin":
            emit(
                ship["pump"], ship[member], "anomaly_reassessment_shared",
                sender=actor, data=data,
                text="Bridge shared a tentative revised or retained interpretation.",
            )
    case.reassessment = {
        "hypothesis": hypothesis, "previous_hypothesis": original,
        "assessor": actor.dbref, "evidence_event_ids": evidence,
        "source_event_id": first["event_id"],
        "verification": "unconfirmed",
    }
    case.save(update_fields=["reassessment"])
    return True, "World recorded unconfirmed follow-up assessment"
