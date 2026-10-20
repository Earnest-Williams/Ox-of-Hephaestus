"""Pure client-side formatting of actor-authored assessment intentions.

Never consults operator world state. Passed observation proof was delivered
through that actor's authenticated Evennia sensor command.
"""
from __future__ import annotations

import hashlib


def compose_assessment(view: dict, *, claim: str, confidence: str,
                       rationale: str, evidence_sequence: int) -> dict[str, str]:
    if type(evidence_sequence) is not int or evidence_sequence < 0:
        raise ValueError("Only an addressed event sequence can be cited")
    if not isinstance(view.get("reading_proof"), str):
        raise ValueError("An authenticated character observation is required")
    return {
        "claim": claim,
        "confidence": confidence,
        "rationale": rationale,
        "reading_proof": view["reading_proof"],
        "reading_minute": str(view["minute"]),
        "oxygen_kpa": f"{view['oxygen_kpa']:.2f}",
        "co2_percent": f"{view['co2_percent']:.2f}",
        "evidence_sequence": str(evidence_sequence),
        "finding_digest": hashlib.sha256(
            view.get("own_finding", "").encode("utf-8"),
        ).hexdigest(),
    }
