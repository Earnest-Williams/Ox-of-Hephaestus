"""Prognosis review is triggered by counterevidence, not by new data alone.

Operational urgency and a working hypothesis about the ship's ultimate
survivability are separate. An acknowledged deterioration, a more urgent
alarm or a second confirming report does not reopen an established prognosis.

GOAP cannot understand unconstrained natural-language contradiction. It
supports typed, actor-addressed contrary reports and a conservative
sustained-stability check based on the character's own sensor history.
This is an explicit limitation of this bounded experiment, not world truth.
"""
from __future__ import annotations

from dataclasses import dataclass

RECOVERY_SIGNALS = frozenset((
    "possible_sustained_recovery", "possible_safe_refuge", "possible_air_source",
))
CANDIDATE_REFUTATIONS = frozenset((
    "recovery_candidate_disproved", "refuge_candidate_disproved",
    "air_source_candidate_disproved",
))
RECOVERY_CONFIRMED = frozenset(("sustained_recovery_confirmed",))

# A single noisy reading, a temporary reserve discharge or an increasing
# danger band is not enough to challenge the standing prognosis.
STABILITY_MIN_MINUTES = 24
STABILITY_OXYGEN_TOLERANCE = 0.20
STABILITY_CO2_TOLERANCE = 0.15


@dataclass(frozen=True)
class ReviewReason:
    kind: str
    evidence_key: str


def _sample(view: dict) -> tuple[int, float, float]:
    return (int(view["minute"]), float(view["oxygen_kpa"]),
            float(view["co2_percent"]))


def _report_code(event: dict) -> str | None:
    if event.get("kind") != "terminal_report":
        return None
    data = event.get("data")
    from_data = data.get("evidence_code") if isinstance(data, dict) else None
    value = event.get("datum_evidence_code") or from_data
    return value if isinstance(value, str) else None


class PrognosisReview:
    """Maintain the last accepted belief and its genuine contradictions."""

    def __init__(self):
        self.phase: str | None = None
        self.baseline_sample: tuple[int, float, float] | None = None
        self.candidate_origin: str | None = None
        self.pending: ReviewReason | None = None
        self.handled: set[str] = set()
        self.last_accepted: dict | None = None
        self.last_refused: dict | None = None
        self.last_refusal_reason = ""

    def inspect(self, view: dict, recent: list[dict], *,
                has_firsthand_or_addressed_evidence: bool) -> bool:
        """Identify counterevidence; NEVER draft a prognosis just to poll it."""
        if self.pending is not None:
            return True
        if self.phase is None:
            if has_firsthand_or_addressed_evidence and "initial" not in self.handled:
                self.pending = ReviewReason("initial", "initial")
                return True
            return False

        for event in recent:
            code = _report_code(event)
            if code is None:
                continue
            sequence = event.get("sequence")
            if not isinstance(sequence, int) or sequence <= 0:
                continue
            evidence_key = f"report:{sequence}:{code}"
            if evidence_key in self.handled:
                continue
            if self.phase == "threat" and code in RECOVERY_SIGNALS:
                self.pending = ReviewReason("candidate", evidence_key)
                return True
            if self.phase == "candidate" and code in CANDIDATE_REFUTATIONS:
                self.pending = ReviewReason("refuted", evidence_key)
                return True
            if self.phase == "candidate" and code in RECOVERY_CONFIRMED:
                self.pending = ReviewReason("confirmed", evidence_key)
                return True
            if self.phase == "confirmed" and code in CANDIDATE_REFUTATIONS:
                self.pending = ReviewReason("refuted", evidence_key)
                return True

        current = _sample(view)
        baseline = self.baseline_sample
        if baseline is None:
            return False
        elapsed = current[0] - baseline[0]
        if elapsed < STABILITY_MIN_MINUTES:
            return False
        stable = (
            current[1] >= baseline[1] - STABILITY_OXYGEN_TOLERANCE
            and current[2] <= baseline[2] + STABILITY_CO2_TOLERANCE
        )
        if self.phase == "threat" and stable:
            key = f"stability:{baseline[0]}:{current[0]}"
            if key not in self.handled:
                self.pending = ReviewReason("candidate", key)
                return True
        elif (self.phase == "candidate" and self.candidate_origin == "stability"
              and (current[1] < baseline[1] - 0.8
                   or current[2] > baseline[2] + 0.3)):
            key = f"decline_after_stability:{baseline[0]}:{current[0]}"
            if key not in self.handled:
                self.pending = ReviewReason("refuted", key)
                return True
        return False

    def wording(self) -> tuple[str, str, str]:
        """Produce text ONLY after initial evidence or a contrary finding."""
        if self.pending is None:
            raise RuntimeError("No counterevidence warrants prognosis review")
        match self.pending.kind:
            case "initial":
                return (
                    "Continued atmospheric deterioration threatens survival; "
                    "no viable recovery route is presently known",
                    "tentative",
                    "Observed environmental conditions and available crew evidence "
                    "indicate an unresolved survival threat.",
                )
            case "candidate":
                return (
                    "New observations suggest a possible recovery or refuge; "
                    "its viability remains unverified",
                    "tentative",
                    "New information is inconsistent with the previous prognosis; "
                    "this possibility requires independent confirmation.",
                )
            case "confirmed":
                return (
                    "New evidence supports a viable sustained recovery",
                    "moderate",
                    "An independently addressed finding now supports recovery; "
                    "the assessment remains revisable.",
                )
            case "refuted":
                return (
                    "The previously reported recovery possibility was contradicted",
                    "moderate",
                    "New evidence invalidates the candidate that had justified "
                    "reconsideration.",
                )
            case _:
                raise AssertionError("Unsupported contrary evidence type")

    def note(self, status: str, proposal: dict, view: dict,
             *, refusal_reason: str = "") -> None:
        if self.pending is None:
            raise AssertionError("Cannot record an unsolicited prognosis update")
        reason = self.pending
        # Remember the attempted trigger even on refusal so an identical
        # rejected submission does not become a hot loop. A *new* contrary
        # finding remains eligible.
        self.handled.add(reason.evidence_key)
        if status == "succeeded":
            self.phase = (
                "threat" if reason.kind in ("initial", "refuted")
                else reason.kind
            )
            self.baseline_sample = _sample(view)
            self.candidate_origin = (
                "stability" if reason.evidence_key.startswith("stability:")
                else "report" if reason.kind == "candidate" else None
            )
            self.last_accepted = dict(proposal)
            self.last_refused = None
            self.last_refusal_reason = ""
        elif status == "failed":
            self.last_refused = dict(proposal)
            self.last_refusal_reason = refusal_reason
        else:
            raise ValueError("Only resolved world receipts update prognosis history")
        self.pending = None
