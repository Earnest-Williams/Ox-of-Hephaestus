"""Operator-only G3e scenario transcript and independent world verification.

NOT an in-game command and never imported into the agent process. It reads
world secrets only AFTER execution, for a synthetic, disposable trial. No
model provider credentials, prompts, or actor-private text are exported.
"""
from __future__ import annotations

import json
from pathlib import Path

from world.bootstrap import build_ship
from world.models import CrewEvent, InvestigationCase, WorkReceipt

ROLES = {
    "lin": ("officer", "Lin Sato"),
    "ari": ("watch", "Ari Sen"),
    "iona": ("chief", "Iona Vek"),
    "mara": ("cargo", "Mara Voss"),
    "teo": ("environment", "Teo"),
}
ORDER = ("lin", "ari", "iona", "mara", "teo")
EVENT_FIELDS = (
    "symptom", "station", "indicator", "reading", "tested_hypothesis",
    "hypothesis", "previous_hypothesis", "changed", "verification",
    "evidence_count", "quality",
)


def _pending_actions(role_record):
    """Only summarize confirmed script-shaped checkpoint metadata."""
    if not isinstance(role_record, dict):
        return {}
    return {
        key: role_record.get(key)
        for key in (
            "selected", "done", "assessment_done", "hypothesis",
            "challenge_choice", "reconsider_choice",
        )
        if key in role_record
    }


def collect(*, scenario: str, provider: str, state_path: str = "../.ox-state/p4e-supervisor.json") -> dict:
    """Read one disposable ship and its single, operator-authorized case."""
    cases = list(InvestigationCase.objects.order_by("created_game_time"))
    if len(cases) != 1:
        raise RuntimeError("Expected exactly one world-owned synthetic case")
    case = cases[0]
    ship = build_ship()
    char = {role: ship[key] for role, (key, _) in ROLES.items()}
    body_to_role = {body.dbref: role for role, body in char.items()}
    state_file = Path(state_path)
    if not state_file.is_file():
        raise RuntimeError("Investigation supervisor did not persist its checkpoint")
    state = json.loads(state_file.read_text(encoding="utf-8"))
    primary = state.get("g3e_investigations", {})
    follow = state.get("g3e_followup", {})
    if not isinstance(primary, dict) or not isinstance(follow, dict):
        raise RuntimeError("Malformed crew scenario state")

    results = {}
    for role in ORDER:
        body = char[role]
        original = primary.get(role, {})
        late = follow.get(role, {})
        probe = case.probes.get(body.dbref, {})
        challenge = case.challenges.get(body.dbref, {})
        reconsidered = case.reconsiderations.get(body.dbref, {})
        beliefs = state.get("epistemics", {}).get(role, {}).get("beliefs", {})
        evidence = state.get("epistemics", {}).get(role, {}).get("observations", {})
        results[role] = {
            "name": ROLES[role][1],
            "joined_initial_investigation": original.get("selected"),
            "filed_initial_report": body.dbref in case.reports,
            "initial_instrument": case.signals.get(role) if body.dbref in case.samples else None,
            "initial_decision": _pending_actions(original),
            "followup_decision": _pending_actions(late),
            "challenge": challenge.get("hypothesis"),
            "probe": (
                {k: probe[k] for k in ("indicator", "tested_hypothesis", "reading")
                 if k in probe} if probe else None
            ),
            "probe_was_reported": "report_event_id" in probe,
            "post_test_hypothesis": reconsidered.get("hypothesis"),
            "private_belief": beliefs.get("anomaly." + case.case_id + ".cause"),
            "verified_private_probe": (
                evidence.get("anomaly." + case.case_id + ".probe", {}).get("value")
                if role in ("ari", "iona", "mara", "teo") else None
            ),
        }

    events = []
    for e in CrewEvent.objects.order_by("sequence"):
        d = dict(e.details)
        if d.get("case_id") != case.case_id:
            continue
        events.append({
            "seq": int(e.sequence),
            "actor": body_to_role.get(e.recipient_dbref, "?"),
            "source": body_to_role.get(e.sender_dbref, "world") if e.sender_dbref else "world",
            "kind": e.kind,
            "data": {k: d[k] for k in EVENT_FIELDS if k in d},
        })

    receipted = list(WorkReceipt.objects.values(
        "operation", "actor_dbref", "target", "outcome"
    ))
    action_counts = {}
    for row in receipted:
        key = row["operation"]
        status = row["outcome"].get("status", "?")
        action_counts.setdefault(key, {})
        action_counts[key][status] = action_counts[key].get(status, 0) + 1

    initial = case.assessment.get("hypothesis")
    revised = case.reassessment.get("hypothesis")
    return {
        "scenario": scenario,
        "provider": provider,
        "epistemic_boundary": "Operator audit only; world truth was never sent to models",
        "world_truth": {
            "cause": case.cause,
            "station_signals": dict(case.signals),
            "probe_key": "withheld from all crew",
            "status": case.status,
        },
        "first_diagnosis": {
            "hypothesis": initial,
            "correct": (initial == case.cause) if initial else None,
            "verification": case.assessment.get("verification"),
        },
        "second_diagnosis": {
            "hypothesis": revised,
            "correct": (revised == case.cause) if revised else None,
            "changed": revised != initial if revised and initial else None,
            "verification": case.reassessment.get("verification"),
        },
        "crew": results,
        "world_action_counts": action_counts,
        "timeline": events,
    }


def emit_report(*, scenario: str, provider: str) -> None:
    payload = collect(scenario=scenario, provider=provider)
    print("OX_SCENARIO_RESULT_BEGIN")
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    print("OX_SCENARIO_RESULT_END")
