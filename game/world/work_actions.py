"""Unified world-authoritative, idempotent shipboard work requests.

The external handler must persist one stable request ID before submission.
Evennia validates the authenticated character's location and duty, applies
at most one world effect, and records an immutable receipt in one transaction.

Existing legacy oxaction/oxreceipt routes continue to work, so migration is
additive. The new global namespace prevents cross-fixture request-ID reuse.
"""
from __future__ import annotations

from collections.abc import Mapping
import re

from django.db import transaction
from evennia.objects.models import ObjectDB
from evennia.utils import gametime

from world.bootstrap import find_fixture
from world.models import CrewEvent, WorkReceipt

_REQUEST_ID = re.compile(r"[0-9a-f]{32}")
_EQUIPMENT = {
    "pump": (
        "pump-p01",
        frozenset({"isolate", "repair", "commission"}),
    ),
    "cargo": (
        "cargo-cradle",
        frozenset({"restow", "certify", "retension"}),
    ),
    "scrubber": (
        "atmosphere-scrubber",
        frozenset({"isolate", "replace", "restart", "purge"}),
    ),
}
_SOCIAL = {
    "radio": "relay_alarm",
    "request": "request_release",
    "approve": "approve_release",
    "resolve": "report_resolution",
    "offer": "offer_watch",
    "accept": "accept_watch",
    "answer": "answer_hail",
    "round_report": "file_round_report",
    "anomaly_report": "report_sample",
    "anomaly_assess": "file_assessment",
    "anomaly_question": "file_question",
    "anomaly_challenge": "file_challenge",
    "anomaly_probe_report": "report_probe",
    "anomaly_reconsider": "file_reconsideration",
    "anomaly_reassess": "file_reassessment",
    "captain_inspect": "inspect",
    "captain_claim": "claim",
    "captain_assign": "assign",
    "captain_answer": "answer",
    "captain_review": "review",
    "captain_escalate": "escalate",
}


def _arguments(operation: str, target: str, arguments: Mapping | None) -> dict:
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, Mapping):
        raise ValueError("Work arguments must be a mapping")
    if target == "ship":
        if operation not in _SOCIAL:
            raise ValueError("Unknown shipboard work operation")
        if operation in (
            "captain_claim", "captain_inspect", "captain_assign", "captain_answer",
            "captain_review", "captain_escalate",
        ):
            ticket_id = arguments.get("ticket_id")
            if (not isinstance(ticket_id, str)
                    or _REQUEST_ID.fullmatch(ticket_id) is None):
                raise ValueError("Captain work requires typed obligation ID")
            if operation in ("captain_claim", "captain_inspect", "captain_review", "captain_escalate"):
                if set(arguments) == {"ticket_id"}:
                    return {"ticket_id": ticket_id}
            elif operation == "captain_assign":
                if (set(arguments) == {"ticket_id", "role"}
                        and arguments["role"] in ("ari", "iona", "mara", "teo")):
                    return {"ticket_id": ticket_id, "role": arguments["role"]}
            elif operation == "captain_answer":
                if (set(arguments) == {"ticket_id", "mode"}
                        and arguments["mode"] in ("accept", "decline", "blocked")):
                    return {"ticket_id": ticket_id, "mode": arguments["mode"]}
            raise ValueError("Unsupported captain task arguments")
        if operation in (
            "anomaly_question", "anomaly_challenge", "anomaly_probe_report",
            "anomaly_reconsider", "anomaly_reassess",
        ):
            from world.investigation import CAUSES
            case_id = arguments.get("case_id")
            if not isinstance(case_id, str) or _REQUEST_ID.fullmatch(case_id) is None:
                raise ValueError("A world case ID is required")
            if operation in ("anomaly_question", "anomaly_probe_report"):
                if set(arguments) == {"case_id"}:
                    return {"case_id": case_id}
                raise ValueError("Follow-up report takes only its case identity")
            if set(arguments) != {"case_id", "hypothesis"}:
                raise ValueError("Typed hypothesis and case ID required")
            if arguments["hypothesis"] not in CAUSES:
                raise ValueError("Unknown diagnostic hypothesis")
            return {"case_id": case_id, "hypothesis": arguments["hypothesis"]}
        if operation in ("anomaly_report", "anomaly_assess"):
            case_id = arguments.get("case_id")
            if not isinstance(case_id, str) or _REQUEST_ID.fullmatch(case_id) is None:
                raise ValueError("Anomaly action requires a world case ID")
            if operation == "anomaly_report" and set(arguments) == {"case_id"}:
                return {"case_id": case_id}
            if operation == "anomaly_assess" and set(arguments) == {"case_id", "hypothesis"}:
                from world.investigation import CAUSES
                if arguments["hypothesis"] in CAUSES:
                    return {"case_id": case_id, "hypothesis": arguments["hypothesis"]}
            raise ValueError("Malformed typed anomaly work")
        if operation == "round_report":
            if set(arguments) != {"station"} or arguments["station"] not in (
                "operations", "pump", "cargo", "scrubber",
            ):
                raise ValueError("Round report requires one typed station")
            return {"station": arguments["station"]}
        if operation == "answer":
            if set(arguments) != {"hail_id", "mode"}:
                raise ValueError("Answer requires a hail ID and response mode")
            hail_id = arguments["hail_id"]
            mode = arguments["mode"]
            if (not isinstance(hail_id, str) or
                    re.fullmatch(r"hail-[0-9]{4,}", hail_id) is None or
                    mode not in ("status", "ack", "decline")):
                raise ValueError("Invalid hail response parameters")
            return {"hail_id": hail_id, "mode": mode}
        if arguments:
            raise ValueError("This shipboard work takes no extra arguments")
        return {}
    if target == "inventory":
        if operation not in (
            "request_supply", "accept_supply", "collect_supply",
            "deliver_supply",
        ):
            raise ValueError("Unknown supply workflow action")
        if operation == "request_supply":
            if arguments:
                raise ValueError("Supply request does not accept custom arguments")
            return {}
        if set(arguments) != {"order_id"}:
            raise ValueError("Handoff requires one world-owned order ID")
        order_id = arguments["order_id"]
        if not isinstance(order_id, str) or _REQUEST_ID.fullmatch(order_id) is None:
            raise ValueError("Malformed world order identity")
        return {"order_id": order_id}
    spec = _EQUIPMENT.get(target)
    if spec is None or operation not in spec[1] or arguments:
        raise ValueError("Unsupported equipment work or arguments")
    return {}


def _validate(actor, request_id: str, operation: str, target: str,
              arguments: Mapping | None) -> dict:
    if actor is None or not isinstance(getattr(actor, "dbref", None), str):
        raise PermissionError("An authenticated character must issue work")
    if not isinstance(request_id, str) or _REQUEST_ID.fullmatch(request_id) is None:
        raise ValueError("Work ID must contain 32 lowercase hex digits")
    if not isinstance(operation, str) or not isinstance(target, str):
        raise ValueError("Invalid requested work")
    return _arguments(operation, target, arguments)


def _social_action(actor, operation: str, arguments: dict) -> tuple[bool, str]:
    from world import live_crew
    from world.crew_interaction import answer_hail
    if operation == "answer":
        return answer_hail(actor, arguments["hail_id"], arguments["mode"])
    if operation.startswith("captain_"):
        from world import captain
        if operation == "captain_claim":
            return captain.claim(actor, arguments["ticket_id"])
        if operation == "captain_inspect":
            return captain.inspect(actor, arguments["ticket_id"])
        if operation == "captain_assign":
            return captain.assign(actor, arguments["ticket_id"], arguments["role"])
        if operation == "captain_answer":
            return captain.answer(actor, arguments["ticket_id"], arguments["mode"])
        if operation == "captain_review":
            return captain.review(actor, arguments["ticket_id"])
        if operation == "captain_escalate":
            return captain.escalate(actor, arguments["ticket_id"])
    if operation == "anomaly_report":
        from world.investigation import report_sample
        return report_sample(actor, arguments["case_id"])
    if operation == "anomaly_assess":
        from world.investigation import file_assessment
        return file_assessment(actor, arguments["case_id"], arguments["hypothesis"])
    if operation in (
        "anomaly_question", "anomaly_challenge", "anomaly_probe_report",
        "anomaly_reconsider", "anomaly_reassess",
    ):
        from world import investigation_followup as followup
        if operation == "anomaly_question":
            return followup.file_question(actor, arguments["case_id"])
        if operation == "anomaly_challenge":
            return followup.file_challenge(
                actor, arguments["case_id"], arguments["hypothesis"],
            )
        if operation == "anomaly_probe_report":
            return followup.report_probe(actor, arguments["case_id"])
        if operation == "anomaly_reconsider":
            return followup.file_reconsideration(
                actor, arguments["case_id"], arguments["hypothesis"],
            )
        return followup.file_reassessment(
            actor, arguments["case_id"], arguments["hypothesis"],
        )
    if operation == "round_report":
        from world.independent_rounds import file_round_report
        return file_round_report(actor, arguments["station"])
    return getattr(live_crew, _SOCIAL[operation])(actor)


def _unknown(actor, request_id: str) -> dict:
    return {
        "request_id": request_id,
        "actor_dbref": actor.dbref,
        "status": "unknown",
        "reason": "no_authorised_receipt",
        "source_event_id": None,
    }


def execute_work(
    actor, request_id: str, operation: str, target: str = "ship",
    *, arguments: Mapping | None = None,
) -> dict:
    """Commit one validated social or physical world transition and receipt.

    Lock the common ship fixture to serialize competing ship work on
    PostgreSQL. SQLite's coarse write locking still cannot be used as
    evidence of production concurrent-writer safety.
    """
    validated = _validate(actor, request_id, operation, target, arguments)
    pump = find_fixture("pump-p01")
    if pump is None:
        raise RuntimeError("No authoritative ship equipment is installed")
    with transaction.atomic():
        # A single contention point prevents two overlapping work requests
        # from consuming an identical scarce resource on PostgreSQL.
        ObjectDB.objects.select_for_update().get(pk=pump.pk)
        old = WorkReceipt.objects.filter(pk=request_id).first()
        if old is not None:
            if (old.actor_dbref != actor.dbref or old.target != target
                    or old.operation != operation or old.arguments != validated):
                raise PermissionError("Request ID already belongs to other work")
            return dict(old.outcome)

        if target == "inventory":
            from world.supply import execute_supply
            succeeded, source_event = execute_supply(
                actor, request_id, operation, validated,
            )
            outcome = {
                "request_id": request_id,
                "actor_dbref": actor.dbref,
                "operation": operation,
                "target": target,
                "status": "succeeded" if succeeded else "failed",
                "reason": "world_accepted" if succeeded else "world_refused",
                "source_event_id": source_event,
                "game_time": float(gametime.gametime(absolute=True)),
            }
        elif target != "ship":
            fixture = find_fixture(_EQUIPMENT[target][0])
            if fixture is None:
                raise RuntimeError("Requested equipment is absent")
            # Existing per-fixture legacy durable receipts remain for old
            # clients and are incorporated in the common transaction.
            result = fixture.durable_action(request_id, operation, actor)
            outcome = {**result, "target": target}
        else:
            before = (
                CrewEvent.objects.order_by("-sequence")
                .values_list("sequence", flat=True).first() or 0
            )
            succeeded, message = _social_action(actor, operation, validated)
            first_event = (
                CrewEvent.objects.filter(sequence__gt=before)
                .order_by("sequence").first()
            )
            outcome = {
                "request_id": request_id,
                "actor_dbref": actor.dbref,
                "operation": operation,
                "target": target,
                "status": "succeeded" if succeeded else "failed",
                "reason": "world_accepted" if succeeded else "world_refused",
                "source_event_id": (
                    first_event.event_id if first_event else None
                ),
                "game_time": float(gametime.gametime(absolute=True)),
            }
            # This is a world-authored diagnostic, never an LLM claim.
            if not succeeded and not message:
                raise RuntimeError("World refused work without a reason")

        receipt = WorkReceipt.objects.create(
            request_id=request_id,
            actor_dbref=actor.dbref,
            target=target,
            operation=operation,
            arguments=validated,
            outcome=outcome,
            game_time=float(gametime.gametime(absolute=True)),
        )
        # Actual work and its limited learning evidence commit together.
        # On retry the existing receipt returns above without granting XP.
        from world.learning import record_work_experience
        record_work_experience(actor, receipt)
        return dict(outcome)


def work_receipt(actor, request_id: str) -> dict:
    """Read only the authenticated actor's previously committed work."""
    if actor is None or not isinstance(getattr(actor, "dbref", None), str):
        raise PermissionError("An authenticated character is required")
    if not isinstance(request_id, str) or _REQUEST_ID.fullmatch(request_id) is None:
        raise ValueError("Invalid work ID")
    stored = WorkReceipt.objects.filter(pk=request_id,
                                        actor_dbref=actor.dbref).first()
    return dict(stored.outcome) if stored is not None else _unknown(actor, request_id)
