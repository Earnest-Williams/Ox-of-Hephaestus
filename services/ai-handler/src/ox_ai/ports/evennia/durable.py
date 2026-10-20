"""Authoritative per-character operation receipts over normal Evennia sockets."""

from __future__ import annotations

import asyncio
import base64
import json
import re

from ox_ai.ports.base import ActionOutcome, ActionRequest
from ox_ai.ports.evennia.client import EvenniaWebSocketClient

_VERBS = {
    ("isolate_pump", "pump"): "isolate",
    ("repair_pump", "pump"): "repair",
    ("commission_pump", "pump"): "commission",
    ("restow_cargo", "cargo"): "restow",
    ("certify_cargo", "cargo"): "certify",
    ("isolate_scrubber", "scrubber"): "isolate",
    ("replace_scrubber", "scrubber"): "replace",
    ("restart_scrubber", "scrubber"): "restart",
    ("retension_cargo", "cargo"): "retension",
    ("purge_scrubber", "scrubber"): "purge",
}


class DurableEvenniaPort:
    """Never confuse chat text or command delivery with a verified transition."""

    def __init__(self, client: EvenniaWebSocketClient, *, timeout: float = 10.0):
        self.client = client
        self.timeout = timeout

    async def _receipt(self, request_id: str) -> ActionOutcome:
        def entry(packet):
            if len(packet.args) == 1 and isinstance(packet.args[0], dict):
                return packet.args[0]
            if not packet.args and "request_id" in packet.options:
                # Some Evennia versions normalize a singleton dict into
                # OOB keyword arguments rather than positional args.
                return packet.options
            raise ValueError("Malformed authenticated world receipt")

        def matches(packet):
            if packet.kind != "ox_receipt":
                return False
            # A delayed receipt for a previous request belongs to that
            # request; preserve it rather than misattributing or discarding it.
            return entry(packet).get("request_id") == request_id

        try:
            async with asyncio.timeout(self.timeout):
                packet = await self.client.receive_matching(
                    matches, frame_budget=128,
                )
                result = entry(packet)
                if result.get("actor_dbref") != self.client.character_dbref:
                    raise PermissionError("Receipt addressed to a different character")
                status = result.get("status")
                if status not in ("succeeded", "failed", "unknown"):
                    raise ValueError("Invalid authoritative receipt status")
                return ActionOutcome(
                    request_id, status, str(result.get("reason", "")),
                    result.get("source_event_id"),
                )
        except TimeoutError:
            return ActionOutcome(request_id, "unknown", "No authoritative receipt")

    async def submit(self, request: ActionRequest) -> ActionOutcome:
        if not self.client.authenticated:
            raise PermissionError("Unauthenticated session")
        if request.character_id != self.client.character_dbref:
            raise PermissionError("Action addressed to another character")
        if request.arguments:
            raise ValueError("Equipment actions do not take free-form arguments")
        op = _VERBS.get((request.verb, request.target))
        if op is None or re.fullmatch(r"[0-9a-f]{32}", request.request_id) is None:
            raise ValueError("Unknown typed operation or request ID")
        suffix = "" if request.target == "pump" else " " + request.target
        await self.client.send_line(f"oxaction {request.request_id} {op}{suffix}")
        return await self._receipt(request.request_id)

    async def reconcile(self, request_id: str, *, target: str = "pump") -> ActionOutcome:
        if not self.client.authenticated:
            raise PermissionError("Unauthenticated session")
        if re.fullmatch(r"[0-9a-f]{32}", request_id) is None:
            raise ValueError("Invalid request ID")
        if target not in ("pump", "cargo", "scrubber"):
            raise ValueError("Unknown equipment receipt namespace")
        suffix = "" if target == "pump" else " " + target
        await self.client.send_line(f"oxreceipt {request_id}{suffix}")
        return await self._receipt(request_id)

    async def submit_work(self, request: ActionRequest) -> ActionOutcome:
        """Submit one typed world-work intent using the global receipt ID.

        Caller must persist the same request ID before invoking this method.
        Keep the historic submit() path until all legacy supervisors migrate.
        """
        if not self.client.authenticated:
            raise PermissionError("Unauthenticated session")
        if request.character_id != self.client.character_dbref:
            raise PermissionError("Work belongs to another character")
        if re.fullmatch(r"[0-9a-f]{32}", request.request_id) is None:
            raise ValueError("Invalid work request ID")

        if request.target == "ship":
            if request.verb not in (
                "radio",
                "request",
                "approve",
                "resolve",
                "offer",
                "accept",
                "answer",
                "round_report",
                "anomaly_report",
                "anomaly_assess",
                "anomaly_question",
                "anomaly_challenge",
                "anomaly_probe_report",
                "anomaly_reconsider",
                "anomaly_reassess",
                "captain_claim",
                "captain_inspect",
                "captain_assign",
                "captain_answer",
                "captain_review",
                "captain_escalate",
                "terminal_survey",
                "terminal_crosscheck",
                "terminal_reroute",
                "terminal_patch",
                "terminal_replace",
                "terminal_search",
                "terminal_route",
                "terminal_command",
                "terminal_reserve",
                "terminal_broadcast",
                "terminal_archive",
                "terminal_comfort",
                "terminal_assess",
            ):
                raise ValueError("Unsupported shipboard operation")
            operation = request.verb
            if operation.startswith("captain_"):
                args = dict(request.arguments)
                identity = args.get("ticket_id")
                if not isinstance(identity, str) or re.fullmatch(r"[0-9a-f]{32}", identity) is None:
                    raise ValueError("Captain work requires world obligation ID")
                if operation in (
                    "captain_claim",
                    "captain_inspect",
                    "captain_review",
                    "captain_escalate",
                ):
                    if set(args) != {"ticket_id"}:
                        raise ValueError("Unexpected captain work data")
                    suffix = " " + identity
                elif operation == "captain_assign":
                    if set(args) != {"ticket_id", "role"} or args["role"] not in (
                        "ari",
                        "iona",
                        "mara",
                        "teo",
                    ):
                        raise ValueError("Unqualified captain work target")
                    suffix = " " + identity + " " + args["role"]
                else:
                    if set(args) != {"ticket_id", "mode"} or args["mode"] not in (
                        "accept",
                        "decline",
                        "blocked",
                    ):
                        raise ValueError("Malformed assigned-crew response")
                    suffix = " " + identity + " " + args["mode"]
            elif operation in (
                "anomaly_report",
                "anomaly_assess",
                "anomaly_question",
                "anomaly_challenge",
                "anomaly_probe_report",
                "anomaly_reconsider",
                "anomaly_reassess",
            ):
                args = dict(request.arguments)
                case_id = args.get("case_id")
                if not isinstance(case_id, str) or re.fullmatch(r"[0-9a-f]{32}", case_id) is None:
                    raise ValueError("Case ID required")
                if operation in ("anomaly_report", "anomaly_question", "anomaly_probe_report"):
                    if set(args) != {"case_id"}:
                        raise ValueError("Report accepts case ID only")
                    suffix = " " + case_id
                else:
                    if set(args) != {"case_id", "hypothesis"} or args["hypothesis"] not in (
                        "cargo_vapors",
                        "scrubber_bypass",
                        "bus_interference",
                    ):
                        raise ValueError("Invalid provisional hypothesis")
                    suffix = " " + case_id + " " + args["hypothesis"]
            elif operation == "terminal_assess":
                # One opaque command argument, validated again by the world.
                # Plain-text claims may contain whitespace and are never
                # interpolated directly into the Evennia command parser.
                arguments = dict(request.arguments)
                if not arguments or not all(
                    isinstance(k, str) and isinstance(v, str)
                    for k, v in arguments.items()
                ):
                    raise ValueError("An actor-authored typed assessment is required")
                encoded = base64.urlsafe_b64encode(
                    json.dumps(arguments, sort_keys=True, separators=(",", ":"))
                    .encode("utf-8")
                ).decode("ascii").rstrip("=")
                if len(encoded) > 4096:
                    raise ValueError("Assessment exceeds authenticated work command budget")
                suffix = " " + encoded
            elif operation == "round_report":
                arguments = dict(request.arguments)
                station = arguments.get("station")
                if set(arguments) != {"station"} or station not in (
                    "operations",
                    "pump",
                    "cargo",
                    "scrubber",
                ):
                    raise ValueError("Round report requires a typed station")
                suffix = " " + station
            elif operation == "answer":
                arguments = dict(request.arguments)
                hail_id = arguments.get("hail_id")
                mode = arguments.get("mode")
                if (
                    set(arguments) != {"hail_id", "mode"}
                    or not isinstance(hail_id, str)
                    or re.fullmatch(r"hail-[0-9]{4,}", hail_id) is None
                    or mode not in ("status", "ack", "decline")
                ):
                    raise ValueError("Invalid typed hail answer")
                suffix = f" {hail_id} {mode}"
            else:
                if request.arguments:
                    raise ValueError("Ship work does not permit free-form arguments")
                suffix = ""
        elif request.target == "learning":
            operation = request.verb
            args = dict(request.arguments)
            if operation in ("inquiry_predict", "inquiry_review", "inquiry_reflect"):
                case_id = args.get("case_id")
                expected = {"case_id"}
                if operation == "inquiry_predict":
                    expected.add("prediction")
                elif operation == "inquiry_reflect":
                    expected |= {"interpretation", "independent_sources"}
                if (
                    set(args) != expected
                    or not isinstance(case_id, str)
                    or re.fullmatch(r"[0-9a-f]{32}", case_id) is None
                ):
                    raise ValueError("Investigative learning requires a typed world case")
                suffix = " " + case_id
                if operation == "inquiry_predict":
                    if args["prediction"] not in ("supports", "does_not_support"):
                        raise ValueError("Unsupported local-probe prediction")
                    suffix += " " + args["prediction"]
                elif operation == "inquiry_reflect":
                    if args["interpretation"] not in (
                        "supported_unconfirmed",
                        "unsupported_not_excluded",
                    ) or args["independent_sources"] not in ("one_source", "two_sources"):
                        raise ValueError("Unsupported investigative-method answer")
                    suffix += f" {args['interpretation']} {args['independent_sources']}"
            elif operation == "lesson_offer":
                course_id, learner = args.get("course_id"), args.get("learner_dbref")
                if (
                    set(args) != {"course_id", "learner_dbref"}
                    or not isinstance(course_id, str)
                    or re.fullmatch(r"[a-z][a-z0-9_.]{1,95}", course_id) is None
                    or not isinstance(learner, str)
                    or re.fullmatch(r"#[1-9][0-9]*", learner) is None
                ):
                    raise ValueError("Lesson offer requires a course and a world learner")
                suffix = f" {course_id} {learner}"
            elif operation in ("lesson_begin", "lesson_answer"):
                lesson_id = args.get("lesson_id")
                expected = {"lesson_id"}
                if operation == "lesson_answer":
                    expected |= {"supported_factor", "controlled_factor"}
                if (
                    set(args) != expected
                    or not isinstance(lesson_id, str)
                    or re.fullmatch(r"[0-9a-f]{32}", lesson_id) is None
                ):
                    raise ValueError("A typed world lesson identity is required")
                suffix = " " + lesson_id
                if operation == "lesson_answer":
                    if args["supported_factor"] not in (
                        "drive_bus",
                        "speed",
                        "insufficient_evidence",
                    ) or args["controlled_factor"] not in ("drive_bus", "speed", "none"):
                        raise ValueError("Unsupported transfer-exercise answer")
                    suffix += f" {args['supported_factor']} {args['controlled_factor']}"
            else:
                raise ValueError("Unsupported learning activity")
        elif request.target == "inventory":
            operation = request.verb
            if operation == "request_supply":
                if request.arguments:
                    raise ValueError("Supply request takes no freeform arguments")
                suffix = ""
            elif operation in ("accept_supply", "collect_supply", "deliver_supply"):
                args = dict(request.arguments)
                order_id = args.get("order_id")
                if (
                    set(args) != {"order_id"}
                    or not isinstance(order_id, str)
                    or re.fullmatch(r"[0-9a-f]{32}", order_id) is None
                ):
                    raise ValueError("Supply work requires one typed world order ID")
                suffix = " " + order_id
            else:
                raise ValueError("Unsupported inventory operation")
        else:
            operation = _VERBS.get((request.verb, request.target))
            if operation is None or request.arguments:
                raise ValueError("Unsupported typed equipment work")
            suffix = ""

        await self.client.send_line(
            f"oxwork {request.request_id} {operation} {request.target}{suffix}"
        )
        return await self._receipt(request.request_id)

    async def reconcile_work(self, request_id: str) -> ActionOutcome:
        """Check global world receipt; never retransmit an unknown operation."""
        if not self.client.authenticated:
            raise PermissionError("Unauthenticated session")
        if re.fullmatch(r"[0-9a-f]{32}", request_id) is None:
            raise ValueError("Invalid work request ID")
        await self.client.send_line(f"oxworkreceipt {request_id}")
        return await self._receipt(request_id)
