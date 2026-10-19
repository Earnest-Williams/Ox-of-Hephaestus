"""G3f: command responsibility for unresolved problems, not omniscience.

The captain owns FOLLOW-THROUGH. Specialists retain their own expertise,
individual observations and refusal authority. A diagnosis or an assignment
never resolves a problem; only independently verified physical outcomes do.
All writes occur inside the caller's world transaction and global work lock.
"""
from __future__ import annotations

import uuid

from django.db import transaction
from evennia.utils import gametime

from world.bootstrap import build_ship, find_fixture
from world.event_journal import emit
from world.models import CaptainObligation, CrewEvent, InvestigationCase

REVIEW_INTERVAL = 1800.0  # game seconds, driven by the existing world clock
CREW_ROLES = ("ari", "iona", "mara", "teo")
QUALIFIED = {
    "analyzer_anomaly": CREW_ROLES,
    "atmosphere_alarm": ("teo",),
}


def _now() -> float:
    return float(gametime.gametime(absolute=True))


def _captain(actor, ship) -> bool:
    return bool(actor == ship["captain"]
                and getattr(actor.db, "crew_role", None) == "captain")


def _record(ticket, kind, **details) -> None:
    entry = {"kind": kind, "at_game_time": _now(), **details}
    ticket.history = [*ticket.history, entry][-64:]
    ticket.due_game_time = _now() + REVIEW_INTERVAL


def open_obligation(kind: str, source_ref: str, *, priority: int,
                    ticket_id: str | None = None) -> str:
    """Called by world events, never by actor/model input."""
    if kind not in QUALIFIED or not isinstance(source_ref, str) or not source_ref:
        raise ValueError("Unsupported world-created command obligation")
    ship = build_ship()
    with transaction.atomic():
        existing = CaptainObligation.objects.select_for_update().filter(
            kind=kind, source_ref=source_ref, status="open",
        ).first()
        if existing is not None:
            return existing.ticket_id
        identity = ticket_id or uuid.uuid4().hex
        ticket = CaptainObligation.objects.create(
            ticket_id=identity, kind=kind, source_ref=source_ref,
            priority=priority, captain_dbref=ship["captain"].dbref,
            due_game_time=_now() + REVIEW_INTERVAL,
        )
        emit(
            ship["pump"], ship["captain"], "captain_problem_open",
            data={
                "ticket_id": identity, "kind": kind,
                "priority": priority, "status": "open",
            },
            text="Unresolved ship problem: maintain accountable follow-up.",
        )
        return ticket.ticket_id


def _ticket(ticket_id: str):
    if not isinstance(ticket_id, str) or len(ticket_id) != 32:
        return None
    if any(c not in "0123456789abcdef" for c in ticket_id):
        return None
    return CaptainObligation.objects.select_for_update().filter(
        ticket_id=ticket_id, status="open",
    ).first()


@transaction.atomic
def claim(actor, ticket_id: str) -> tuple[bool, str]:
    """Captain assumes the open obligation; cannot pronounce it resolved."""
    ship = build_ship()
    item = _ticket(ticket_id)
    if item is None or not _captain(actor, ship) or item.captain_dbref != actor.dbref:
        return False, "Only this ship's captain can claim an open obligation"
    if any(h["kind"] == "claim" for h in item.history):
        return False, "Captain already has this open obligation"
    _record(item, "claim", actor=actor.dbref)
    emit(
        ship["pump"], actor, "captain_claim_recorded",
        sender=actor, data={"ticket_id": ticket_id, "status": "open"},
        text="Ownership acknowledged; unresolved work must continue.",
    )
    item.save(update_fields=["history", "due_game_time"])
    return True, "Captain accepted open-world follow-up responsibility"


@transaction.atomic
def assign(actor, ticket_id: str, role: str) -> tuple[bool, str]:
    """Delegate a concrete next check, without ordering a diagnosis or fix."""
    ship = build_ship()
    item = _ticket(ticket_id)
    if (item is None or not _captain(actor, ship)
            or role not in QUALIFIED.get(item.kind, ())):
        return False, "Invalid captain or unqualified specialist"
    if not any(h["kind"] == "claim" for h in item.history):
        return False, "Captain must first accept command responsibility"
    old = dict(item.assignment)
    if old and old.get("status") in ("assigned", "accepted"):
        return False, "A still-open assignment cannot be silently replaced"
    member = ship[{"ari": "watch", "iona": "chief",
                   "mara": "cargo", "teo": "environment"}[role]]
    if member.dbref == actor.dbref:
        return False, "Command cannot self-authorize technical work"
    if item.kind == "analyzer_anomaly":
        case = InvestigationCase.objects.filter(pk=item.source_ref).first()
        if case is None:
            return False, "No source investigation for this ticket"
        if case.probes.get(member.dbref, {}).get("report_event_id"):
            return False, "A completed old experiment cannot satisfy new orders"
    # An unproductive repeat of the exact same existing probe does not
    # count as a fresh investigation. A new role is required after a report.
    if item.kind == "analyzer_anomaly" and any(
        h["kind"] == "assign" and h.get("role") == role for h in item.history
    ):
        return False, "This specialist's one follow-up is already assigned"
    order_id = uuid.uuid4().hex
    entry = {
        "order_id": order_id, "role": role, "assignee": member.dbref,
        "status": "assigned", "kind": item.kind,
        "source_ref": item.source_ref,
    }
    data = {
        "ticket_id": ticket_id, "order_id": order_id, "kind": item.kind,
        "source_ref": item.source_ref, "role": role, "status": "assigned",
    }
    receipt = emit(
        ship["pump"], actor, "captain_assignment_recorded",
        sender=actor, data=data,
        text="World records one actionable assignment; no repair is implied.",
    )
    emit(
        ship["pump"], member, "captain_order_received",
        sender=actor, data=data,
        text="Captain requests a locally authorized verification or diagnostic.",
    )
    entry["source_event_id"] = receipt["event_id"]
    _record(item, "assign", role=role, order_id=order_id)
    item.assignment = entry
    item.save(update_fields=["assignment", "history", "due_game_time"])
    return True, "One expert received a world-authorized follow-up request"


@transaction.atomic
def answer(actor, ticket_id: str, mode: str) -> tuple[bool, str]:
    """Assignee may accept, refuse or report blocked; the case remains open."""
    item = _ticket(ticket_id)
    order = dict(item.assignment) if item else {}
    if (not item or actor is None or actor.dbref != order.get("assignee")
            or mode not in ("accept", "decline", "blocked")
            or order.get("status") != "assigned"):
        return False, "Only the assigned specialist can answer this order once"
    ship = build_ship()
    expected = ship[{"ari": "watch", "iona": "chief",
                     "mara": "cargo", "teo": "environment"}[order["role"]]]
    if actor != expected:
        return False, "Wrong specialist identity"
    new_status = {"accept": "accepted", "decline": "declined",
                  "blocked": "blocked"}[mode]
    order["status"] = new_status
    item.assignment = order
    _record(item, "answer", role=order["role"],
            order_id=order["order_id"], status=new_status)
    data = {
        "ticket_id": ticket_id, "order_id": order["order_id"],
        "role": order["role"], "status": new_status,
    }
    emit(
        ship["pump"], actor, "captain_order_answered", sender=actor,
        data=data, text="Your decision was recorded without a fabricated work result.",
    )
    emit(
        ship["pump"], ship["captain"], "captain_order_response",
        sender=actor, data=data,
        text="Assigned crewmember answered; command obligation remains open.",
    )
    item.save(update_fields=["assignment", "history", "due_game_time"])
    return True, "Specialist's decision was reported to captain"


@transaction.atomic
def reported_experiment(case_id: str, actor, source_event_id: str) -> None:
    """From the world-verified probe report, never from model testimony."""
    item = _ticket(case_id)
    if not item or item.kind != "analyzer_anomaly":
        return
    order = dict(item.assignment)
    if (order.get("assignee") != actor.dbref
            or order.get("status") not in ("assigned", "accepted")):
        return
    # Global work ledger holds the shared pump lock; the source event already
    # exists in the same transaction. No previously-recorded result qualifies.
    event = CrewEvent.objects.filter(event_id=source_event_id).first()
    original = CrewEvent.objects.filter(
        event_id=order.get("source_event_id"),
    ).first()
    if event is None or original is None or event.sequence <= original.sequence:
        return
    order["status"] = "reported"
    order["result_event_id"] = source_event_id
    item.assignment = order
    _record(item, "experiment_reported",
            role=order["role"], result_event_id=source_event_id)
    ship = build_ship()
    emit(
        ship["pump"], ship["captain"], "captain_followup_evidence",
        sender=actor,
        data={"ticket_id": case_id, "order_id": order["order_id"],
              "role": order["role"], "report_event_id": source_event_id,
              "status": "open"},
        text="World-confirmed report received. Cause remains unverified.",
    )
    item.save(update_fields=["assignment", "history", "due_game_time"])


@transaction.atomic
def review(actor, ticket_id: str) -> tuple[bool, str]:
    """One accountability check; a theory can never close the ticket."""
    ship = build_ship()
    item = _ticket(ticket_id)
    if item is None or not _captain(actor, ship):
        return False, "Only captain may review an unresolved problem"
    if item.kind == "atmosphere_alarm":
        scrubber = ship["scrubber"]
        if scrubber.state == "nominal" and any(
            e.get("after") == "nominal" and e.get("operation") == "restart"
            and e.get("game_time", 0) >= item.history[0].get("at_game_time", 0)
            for e in (scrubber.db.event_history or [])
        ):
            _record(item, "world_verified_resolution", equipment="A-01")
            item.status = "resolved"
            emit(
                ship["pump"], actor, "captain_world_resolved",
                data={"ticket_id": ticket_id, "status": "resolved"},
                text="A-01 physical restart and nominal state verified by Evennia.",
            )
            item.save(update_fields=["status", "history", "due_game_time"])
            return True, "Physical atmosphere restoration independently verified"
    assignment = dict(item.assignment)
    state = assignment.get("status", "unassigned")
    if state == "accepted":
        # Accepted is NOT completed, even after multiple watch cycles.
        label = "awaiting_verified_work"
    elif state in ("declined", "blocked", "reported"):
        label = "requires_new_assignment_or_escalation"
    else:
        label = "unassigned_or_pending"
    _record(item, "review", result=label)
    emit(
        ship["pump"], actor, "captain_problem_unresolved",
        data={"ticket_id": ticket_id, "kind": item.kind,
              "status": "open", "assignment_status": state,
              "next_action": label},
        text="Problem remains unresolved; keep follow-up on the command agenda.",
    )
    item.save(update_fields=["history", "due_game_time"])
    return True, "Unresolved problem remains open with explicit follow-up"


@transaction.atomic
def escalate(actor, ticket_id: str) -> tuple[bool, str]:
    """No available diagnostic is never a reason to silently close the case."""
    ship = build_ship()
    item = _ticket(ticket_id)
    if item is None or not _captain(actor, ship):
        return False, "Captain identity required"
    # Escalation can repeat after new evidence, but must not busy-loop without
    # new world events. The captain's due-time reminder is the next wakeup.
    last = item.history[-1] if item.history else {}
    if last.get("kind") == "escalate":
        return False, "Await a subsequent world event before repeating escalation"
    _record(item, "escalate", reason="unresolved_without_new_verification")
    emit(
        ship["pump"], actor, "captain_escalation_recorded",
        data={"ticket_id": ticket_id, "status": "open"},
        text="Unresolved priority remains on command duty until world resolution.",
    )
    emit(
        ship["pump"], ship["officer"], "captain_escalation_received",
        sender=actor,
        data={"ticket_id": ticket_id, "kind": item.kind,
              "status": "open"},
        text="Captain requests continued reporting and fresh evidence.",
    )
    item.save(update_fields=["history", "due_game_time"])
    return True, "Escalation registered; unresolved obligation retained"


@transaction.atomic
def report_equipment_change(*, kind: str, source_ref: str, state: str) -> None:
    """World-issued physical progress notification, without declaring success."""
    item = CaptainObligation.objects.select_for_update().filter(
        kind=kind, source_ref=source_ref, status="open",
    ).first()
    if item is None:
        return
    ship = build_ship()
    emit(
        ship["pump"], ship["captain"], "captain_equipment_change",
        data={"ticket_id": item.ticket_id, "kind": kind,
              "reported_state": state, "status": "open"},
        text="Equipment changed physically; captain must verify actual resolution.",
    )


def captain_qualified_observation(actor, ticket_id: str) -> dict | None:
    """Optional direct fact-finding only if actual character skills qualify.

    This provides a bridge instrument state, not the hidden anomaly cause.
    Authority to delegate is separate and does not depend on technical skill.
    """
    ship = build_ship()
    if not _captain(actor, ship) or actor.location != ship["bridge"]:
        return None
    if int((actor.db.ox_skills or {}).get("diagnostics", 0)) < 2:
        return None
    item = CaptainObligation.objects.filter(
        ticket_id=ticket_id, status="open",
    ).first()
    if item is None:
        return None
    if item.kind == "atmosphere_alarm":
        reading = ship["scrubber"].state
    else:
        reading = "analyzer_disagreement"  # bridge-level signal only
    entry = emit(
        ship["pump"], actor, "captain_firsthand_observation",
        data={"ticket_id": ticket_id, "indicator": "bridge_telemetry",
              "reading": reading, "quality": "limited"},
        text="You personally inspected bridge status, not the latent cause.",
    )
    return {"ticket_id": ticket_id, "reading": reading,
            "event_id": entry["event_id"]}


def tick_captain_obligations(*, now_game_time: float | None = None) -> int:
    """World-clock reminders require zero model inference while idle."""
    now = _now() if now_game_time is None else float(now_game_time)
    count = 0
    for candidate in CaptainObligation.objects.filter(
        status="open", due_game_time__lte=now,
    ).order_by("due_game_time")[:32]:
        with transaction.atomic():
            item = CaptainObligation.objects.select_for_update().get(
                pk=candidate.pk,
            )
            if item.status != "open" or item.due_game_time > now:
                continue
            ship = build_ship()
            emit(
                ship["pump"], ship["captain"], "captain_review_due",
                data={"ticket_id": item.ticket_id, "kind": item.kind,
                      "priority": item.priority, "status": "open"},
                text="World-timed captain review: unresolved duty must be revisited.",
            )
            item.last_reminded_game_time = now
            item.due_game_time = now + REVIEW_INTERVAL
            item.save(update_fields=["last_reminded_game_time", "due_game_time"])
            count += 1
    return count
