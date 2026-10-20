"""G6b actor-authored assessments with world-verified evidence provenance.

The world validates the submitted observation reference and authorship, NOT
whether a character's proposition or confidence is rational or correct.

Identical means the *entire normalized actor submission* is unchanged, not
that the world observed no new sensor readings or addressed report.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re

from django.conf import settings
from world.models import CrewEvent

FIELD_NAMES = frozenset({
    "claim", "confidence", "rationale", "reading_proof",
    "reading_minute", "oxygen_kpa", "co2_percent",
    "evidence_sequence", "finding_digest",
})
EVIDENCE_KINDS = frozenset((
    "terminal_alarm", "terminal_report", "terminal_critical",
    "terminal_assistance",
))
DUPLICATE_REASON = "unchanged_assessment"
_HEX64 = re.compile(r"[0-9a-f]{64}")


def finding_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reading_proof(case_id: str, actor_dbref: str, minute: int,
                  oxygen_kpa: str, co2_percent: str) -> str:
    """Deterministic proof of one recipient's authentic sensor reading.

    Existing character commands can replay previously observed readings when
    reconsidering them; a fresh timestamp is never required to change a belief.
    """
    payload = json.dumps(
        ["g6b-reading-v1", case_id, actor_dbref, minute,
         oxygen_kpa, co2_percent],
        separators=(",", ":"), ensure_ascii=True,
    )
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def validate_shape(arguments: dict) -> dict[str, str]:
    if not isinstance(arguments, dict) or set(arguments) != FIELD_NAMES:
        raise ValueError("Assessment requires claim, confidence, rationale and observed evidence")
    if any(not isinstance(v, str) for v in arguments.values()):
        raise ValueError("Assessment fields must be bounded text values")
    outcome = dict(arguments)
    for key in ("claim", "rationale"):
        outcome[key] = " ".join(outcome[key].split())
    if not 1 <= len(outcome["claim"]) <= 180:
        raise ValueError("Assessment claim must be a substantive proposition")
    if not 1 <= len(outcome["rationale"]) <= 300:
        raise ValueError("Assessment must state an interpretation or reason")
    if outcome["confidence"] not in {"tentative", "moderate", "strong"}:
        raise ValueError("Confidence must be tentative, moderate or strong")
    if _HEX64.fullmatch(outcome["reading_proof"]) is None:
        raise ValueError("Invalid sensor provenance token")
    if _HEX64.fullmatch(outcome["finding_digest"]) is None:
        raise ValueError("Invalid firsthand evidence fingerprint")
    for key in ("reading_minute", "evidence_sequence"):
        if re.fullmatch(r"(0|[1-9][0-9]{0,9})", outcome[key]) is None:
            raise ValueError("Malformed observation reference")
    for key, maximum in (("oxygen_kpa", 30.0), ("co2_percent", 100.0)):
        if re.fullmatch(r"(0|[1-9][0-9]{0,2})\.[0-9]{2}", outcome[key]) is None:
            raise ValueError("Sensor values must be explicitly measured to two decimals")
        value = float(outcome[key])
        if value < 0 or value > maximum:
            raise ValueError("Out-of-bounds instrument reading")
    return outcome


def verify_actor_evidence(actor, case: dict, arguments: dict) -> dict:
    """Authenticate observed data; never evaluate the stated conclusion."""
    proposal = validate_shape(arguments)
    minute = int(proposal["reading_minute"])
    if minute > case["minute"]:
        raise PermissionError("Assessment cannot cite a future observation")
    valid_proof = reading_proof(
        case["id"], actor.dbref, minute,
        proposal["oxygen_kpa"], proposal["co2_percent"],
    )
    if not hmac.compare_digest(proposal["reading_proof"], valid_proof):
        raise PermissionError("Assessment does not belong to an issued actor observation")
    observed_finding = str(case["findings"].get(actor.dbref, ""))
    if not hmac.compare_digest(
        proposal["finding_digest"], finding_digest(observed_finding),
    ):
        raise PermissionError("Assessment claims an unverified firsthand finding")

    seq = int(proposal["evidence_sequence"])
    if seq and not CrewEvent.objects.filter(
        sequence=seq, recipient_dbref=actor.dbref, kind__in=EVIDENCE_KINDS,
    ).exists():
        raise PermissionError("Assessment references an unaddressed observation")
    return proposal


def genuinely_identical(previous: dict | None, proposal: dict) -> bool:
    """No-op only for the same actual authored content and evidence.

    Changed measurements, a newly received report, or a revised *interpretation*
    must all remain eligible; case minute and request ID are not part of this
    comparison.
    """
    return previous is not None and previous == proposal
