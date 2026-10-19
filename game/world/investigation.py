"""G3e-1: one opt-in uncertain investigation with independent local evidence.

Evennia privately owns the latent cause. An alert describes a symptom,
not a solution; each character can sample only their installed station.
Intermittent readings have overlapping likelihoods across all three causes.
Reports are verified firsthand testimony, while any diagnosis remains a
provisional, fallible hypothesis. The handler never imports this module.
"""
from __future__ import annotations

import random
import re
import secrets
import uuid

from django.db import transaction
from evennia.objects.models import ObjectDB
from evennia.utils import gametime

from world.bootstrap import build_ship
from world.event_journal import emit
from world.models import InvestigationCase

CAUSES = ("cargo_vapors", "scrubber_bypass", "bus_interference")
# No sensor is a ground-truth oracle. Any individual elevated or baseline
# measurement is possible under every cause. Cross-station evidence shifts
# probabilities; a wrong assessment remains a legitimate outcome.
LIKELIHOODS = {
    "cargo_vapors": {"ari": 25, "iona": 20, "mara": 80, "teo": 65},
    "scrubber_bypass": {"ari": 20, "iona": 35, "mara": 40, "teo": 80},
    "bus_interference": {"ari": 80, "iona": 70, "mara": 25, "teo": 35},
}
# role -> authoritative ship member, crew_role, local fixture, station, dial
SOURCES = {
    "lin": ("officer", "bridge_officer", "operations", "operations", "analyzer_disagreement"),
    "ari": ("watch", "watch_engineer", "pump", "pump", "drive_bus_ripple"),
    "iona": ("chief", "chief_engineer", "pump", "pump", "thermal_witness"),
    "mara": ("cargo", "cargo_officer", "cradle", "cargo", "headspace_trace"),
    "teo": ("environment", "environment_tech", "scrubber", "scrubber", "intake_delta"),
}
CASE_ID = re.compile(r"[0-9a-f]{32}")


def _valid_case_id(case_id: str) -> bool:
    return isinstance(case_id, str) and CASE_ID.fullmatch(case_id) is not None


def _local_role(actor, ship) -> str | None:
    if actor is None:
        return None
    for role, (crew, title, fixture, _station, _dial) in SOURCES.items():
        if (actor == ship[crew] and getattr(actor.db, "crew_role", None) == title
                and actor.location == ship[fixture].location):
            return role
    return None


def _open_case(case_id: str) -> InvestigationCase | None:
    if not _valid_case_id(case_id):
        return None
    return InvestigationCase.objects.select_for_update().filter(
        pk=case_id, status="open",
    ).first()


@transaction.atomic
def arm_anomaly(*, cause: str | None = None, seed: int | None = None) -> str:
    """Operator-only: opt in once to a world-secret physical explanation.

    A supplied seed and cause are for reproducible disposable trials, not
    character actions. Starting an ordinary ship never starts this case.
    """
    if cause is not None and cause not in CAUSES:
        raise ValueError("Unsupported latent cause")
    if seed is not None and (type(seed) is not int or not 0 <= seed < 2**64):
        raise ValueError("Seed must be a bounded integer")
    ship = build_ship()
    ObjectDB.objects.select_for_update().get(pk=ship["pump"].pk)
    if InvestigationCase.objects.filter(status="open").exists():
        raise RuntimeError("There is already an open investigation")
    rng = random.Random(secrets.randbits(64) if seed is None else seed)
    selected = cause or rng.choice(CAUSES)
    signals = {"lin": "disagreement"}
    for role, probability in LIKELIHOODS[selected].items():
        signals[role] = "elevated" if rng.randrange(100) < probability else "baseline"
    case_id = uuid.uuid4().hex
    InvestigationCase.objects.create(
        case_id=case_id, status="open", cause=selected, signals=signals,
        probe_key=format(rng.getrandbits(64), "016x"),
        created_game_time=float(gametime.gametime(absolute=True)),
    )
    # Each character receives the same ambiguous alert, not the cause or
    # the readings of other people. These emissions are rollback-atomic.
    for role, (crew, _title, _fixture, _station, _dial) in SOURCES.items():
        emit(
            ship["pump"], ship[crew], "anomaly_notice",
            data={"case_id": case_id, "symptom": "analyzer_disagreement"},
            text="Intermittent atmospheric analyzer disagreement. Cause not established.",
        )
    return case_id


@transaction.atomic
def take_sample(actor, case_id: str) -> dict | None:
    """A real nearby character collects one world-persisted local sample.

    A reconnect may repeat the command, but does not create a second
    observation or redraw noise. Nothing is inferred from model text.
    """
    case = _open_case(case_id)
    if case is None:
        return None
    ship = build_ship()
    role = _local_role(actor, ship)
    if role is None:
        return None
    member, _title, _fixture, station, indicator = SOURCES[role]
    if actor != ship[member]:
        return None
    sample = dict(case.samples).get(actor.dbref)
    if sample is not None:
        return {
            "case_id": case_id, "station": station, "indicator": indicator,
            "reading": case.signals[role], "event_id": sample,
        }
    entry = emit(
        ship["pump"], actor, "anomaly_sampled",
        data={
            "case_id": case_id, "station": station, "indicator": indicator,
            "reading": case.signals[role], "quality": "indicative_only",
        },
        text=f"Your local {indicator} instrument reads {case.signals[role]}.",
    )
    samples = dict(case.samples)
    samples[actor.dbref] = entry["event_id"]
    case.samples = samples
    case.save(update_fields=["samples"])
    return {
        "case_id": case_id, "station": station, "indicator": indicator,
        "reading": case.signals[role], "event_id": entry["event_id"],
    }


def report_sample(actor, case_id: str) -> tuple[bool, str]:
    """File an immutable actor-local measurement under global WorkReceipt.

    execute_work already holds the pump lock and outer DB transaction.
    This nested atomic block uses a fresh locked case record.
    """
    with transaction.atomic():
        case = _open_case(case_id)
        if case is None:
            return False, "No open investigation for that identity"
        ship = build_ship()
        role = _local_role(actor, ship)
        if role is None or actor.dbref not in case.samples:
            return False, "Firsthand local evidence required"
        if actor.dbref in case.reports:
            return False, "This person already filed a report"
        _member, _title, _fixture, station, indicator = SOURCES[role]
        data = {
            "case_id": case_id, "station": station, "indicator": indicator,
            "reading": case.signals[role],
            "sample_event_id": case.samples[actor.dbref],
        }
        recorded = emit(
            ship["pump"], actor, "anomaly_report_recorded",
            data=data,
            text="Your measured signal was filed as evidence, not a diagnosis.",
        )
        emit(
            ship["pump"], ship["officer"], "anomaly_crew_report", sender=actor,
            data=data,
            text=f"{actor.key} sent a firsthand {station} instrument reading.",
        )
        reports = dict(case.reports)
        reports[actor.dbref] = recorded["event_id"]
        case.reports = reports
        case.save(update_fields=["reports"])
        return True, "World accepted one witnessed, non-diagnostic reading"


def file_assessment(actor, case_id: str, hypothesis: str) -> tuple[bool, str]:
    """Bridge may record a potentially wrong hypothesis, never hidden truth."""
    with transaction.atomic():
        case = _open_case(case_id)
        if case is None or hypothesis not in CAUSES:
            return False, "No compatible open investigation"
        ship = build_ship()
        if actor != ship["officer"] or _local_role(actor, ship) != "lin":
            return False, "Only the bridge officer can record an assessment"
        if case.assessment:
            return False, "This case already has a provisional assessment"
        refs = case.reports
        # Do not credit hearsay as an independent second instrument. At
        # least one engineer and one specialist must have filed along with Lin.
        if not (
            actor.dbref in refs
            and any(ship[r].dbref in refs for r in ("watch", "chief"))
            and any(ship[r].dbref in refs for r in ("cargo", "environment"))
        ):
            return False, "Bridge needs engineering and specialist firsthand reports"
        evidence = sorted(refs.values())
        data = {
            "case_id": case_id, "hypothesis": hypothesis,
            "evidence_count": len(evidence), "verification": "unconfirmed",
        }
        emit(
            ship["pump"], actor, "anomaly_assessment_recorded", sender=actor,
            data=data, text="Provisional assessment logged; cause remains unverified.",
        )
        for role, (crew, _title, _fixture, _station, _dial) in SOURCES.items():
            if role != "lin":
                emit(
                    ship["pump"], ship[crew], "anomaly_hypothesis_shared",
                    sender=actor, data=data,
                    text="Bridge circulated an unconfirmed explanation, not a finding.",
                )
        case.assessment = {
            "hypothesis": hypothesis, "assessor": actor.dbref,
            "report_event_ids": evidence, "verification": "unconfirmed",
        }
        case.save(update_fields=["assessment"])
        return True, "Hypothesis recorded as unconfirmed, not validated"
