"""Ordinary character commands for authenticated, world-owned crew cooperation."""

from __future__ import annotations

from world import live_crew

from evennia.commands.command import Command


class _CrewCommand(Command):
    locks = "cmd:all()"
    func_name = ""

    def func(self) -> None:
        if self.args.strip():
            self.caller.msg("This action takes no arguments.")
            return
        succeeded, result = getattr(live_crew, self.func_name)(self.caller)
        self.caller.msg(result)


class CmdOxInbox(Command):
    """Read ONLY this character's stored private ship events after a cursor."""

    key = "oxinbox"
    locks = "cmd:all()"

    def func(self) -> None:
        from world.live_crew import inbox_page, wire_event

        try:
            since = int(self.args.strip() or "0")
            if since < 0:
                raise ValueError
        except ValueError:
            self.caller.msg("Usage: oxinbox <nonnegative-event-sequence>")
            return
        page = inbox_page(self.caller, after=since)
        for message in page["events"]:
            self.caller.msg(ox_event=([wire_event(message)], {}))
        # Flat fields are mandatory for Evennia's v1 websocket protocol.
        self.caller.msg(
            ox_inbox_done=(
                [
                    {
                        "version": page["version"],
                        "count": page["count"],
                        "next_cursor": page["next_cursor"],
                        "has_more": page["has_more"],
                    }
                ],
                {},
            )
        )


class CmdOxRadioAlarm(_CrewCommand):
    """Relay an authenticated bridge alarm to the current duty engineer."""

    key = "oxradio"
    func_name = "relay_alarm"


class CmdOxRequestRelease(_CrewCommand):
    key = "oxrequest"
    func_name = "request_release"


class CmdOxApproveRelease(_CrewCommand):
    key = "oxapprove"
    func_name = "approve_release"


class CmdOxResolve(_CrewCommand):
    key = "oxresolve"
    func_name = "report_resolution"


class CmdOxOfferWatch(_CrewCommand):
    key = "oxhandover"
    func_name = "offer_watch"


class CmdOxAcceptWatch(_CrewCommand):
    key = "oxaccept"
    func_name = "accept_watch"


class CmdOxHail(Command):
    """Request an addressed, bounded response from shipboard crew.

    Usage: oxhail <lin|ari|iona> = <message>
    """

    key = "oxhail"
    locks = "cmd:all()"

    def func(self) -> None:
        from world.crew_interaction import send_hail

        if "=" not in self.args:
            self.caller.msg("Usage: oxhail <lin|ari|iona> = <message>")
            return
        role, message = self.args.split("=", 1)
        _success, result = send_hail(self.caller, role.strip(), message)
        self.caller.msg(result)


class CmdOxAnswer(Command):
    """Answer one's own pending hail using world-grounded response types."""

    key = "oxanswer"
    locks = "cmd:all()"

    def func(self) -> None:
        from world.crew_interaction import answer_hail

        parts = self.args.strip().split()
        if len(parts) != 2:
            self.caller.msg("Usage: oxanswer <hail-id> <status|ack|decline>")
            return
        _success, result = answer_hail(self.caller, *parts)
        self.caller.msg(result)


class CmdOxWork(Command):
    """Submit a world-owned, idempotent ship or equipment request.

    Usage:
        oxwork <32-hex-id> <radio|request|approve|resolve|offer|accept> ship
        oxwork <32-hex-id> answer ship <hail-id> <status|ack|decline>
        oxwork <32-hex-id> <operation> <pump|cargo|scrubber>
        oxwork <32-hex-id> round_report ship <operations|pump|cargo|scrubber>
        oxwork <32-hex-id> request_supply inventory
        oxwork <32-hex-id> <accept_supply|collect_supply|deliver_supply> inventory <order-id>
        oxwork <32-hex-id> lesson_offer learning <course-id> <learner-dbref>
        oxwork <32-hex-id> lesson_begin learning <lesson-id>
        oxwork <32-hex-id> lesson_answer learning <lesson-id> <supported-factor> <controlled-factor>

    Every command is checked again by the world. No client may grant its
    own work permission by offering a model-generated command.
    """

    key = "oxwork"
    locks = "cmd:all()"

    def func(self) -> None:
        import re

        from world.work_actions import execute_work

        parts = self.args.strip().split()
        usage = "Usage: oxwork <32-hex-id> <operation> <target> [hail-id mode]"
        if len(parts) not in (3, 4, 5, 6) or re.fullmatch(r"[0-9a-f]{32}", parts[0]) is None:
            self.caller.msg(usage)
            return
        request_id, operation, target = parts[:3]
        arguments = None
        if target == "learning":
            if operation == "lesson_offer" and len(parts) == 5:
                arguments = {"course_id": parts[3], "learner_dbref": parts[4]}
            elif operation == "lesson_begin" and len(parts) == 4:
                arguments = {"lesson_id": parts[3]}
            elif operation == "lesson_answer" and len(parts) == 6:
                arguments = {
                    "lesson_id": parts[3],
                    "supported_factor": parts[4],
                    "controlled_factor": parts[5],
                }
            else:
                self.caller.msg(usage)
                return
        elif len(parts) == 6:
            self.caller.msg(usage)
            return
        elif len(parts) == 5:
            if target == "ship" and operation in (
                "anomaly_assess",
                "anomaly_challenge",
                "anomaly_reconsider",
                "anomaly_reassess",
                "captain_assign",
                "captain_answer",
            ):
                if operation == "captain_assign":
                    arguments = {"ticket_id": parts[3], "role": parts[4]}
                elif operation == "captain_answer":
                    arguments = {"ticket_id": parts[3], "mode": parts[4]}
                else:
                    arguments = {"case_id": parts[3], "hypothesis": parts[4]}
            elif target != "ship" or operation != "answer":
                self.caller.msg(usage)
                return
            else:
                arguments = {"hail_id": parts[3], "mode": parts[4]}
        elif len(parts) == 4:
            if target == "ship" and operation in (
                "captain_claim",
                "captain_inspect",
                "captain_review",
                "captain_escalate",
            ):
                arguments = {"ticket_id": parts[3]}
            elif target == "ship" and operation in (
                "anomaly_report",
                "anomaly_question",
                "anomaly_probe_report",
            ):
                arguments = {"case_id": parts[3]}
            elif target == "ship" and operation == "round_report":
                arguments = {"station": parts[3]}
            elif target == "inventory" and operation in (
                "accept_supply",
                "collect_supply",
                "deliver_supply",
            ):
                arguments = {"order_id": parts[3]}
            else:
                self.caller.msg(usage)
                return
        try:
            result = execute_work(
                self.caller,
                request_id,
                operation,
                target,
                arguments=arguments,
            )
        except (ValueError, PermissionError):
            # Never leak details about another character's receipt.
            result = {
                "request_id": request_id,
                "actor_dbref": self.caller.dbref,
                "status": "failed",
                "reason": "invalid_or_colliding_request",
                "source_event_id": None,
            }
        self.caller.msg(ox_receipt=([result], {}))


class CmdOxWorkReceipt(Command):
    """Reconcile one work request against the private world-owned ledger."""

    key = "oxworkreceipt"
    locks = "cmd:all()"

    def func(self) -> None:
        import re

        from world.work_actions import work_receipt

        request_id = self.args.strip()
        if re.fullmatch(r"[0-9a-f]{32}", request_id) is None:
            self.caller.msg("Usage: oxworkreceipt <32-hex-id>")
            return
        self.caller.msg(ox_receipt=([work_receipt(self.caller, request_id)], {}))


class CmdOxSample(Command):
    """Locally sample an open uncertain world case; no root-cause disclosure."""

    key = "oxsample"
    locks = "cmd:all()"

    def func(self) -> None:
        from world.investigation import take_sample

        result = take_sample(self.caller, self.args.strip())
        if result is None:
            self.caller.msg("No open case or authorized local instrument here.")
        else:
            self.caller.msg(
                "OX_ANOMALY_SAMPLE "
                + result["case_id"]
                + " "
                + result["station"]
                + " "
                + result["indicator"]
                + " "
                + result["reading"]
            )


class CmdOxProbe(Command):
    """Run one's own installed, fallible follow-up diagnostic.

    Usage: oxprobe <case-id>
    No actor can remotely query another instrument or the latent root cause.
    """

    key = "oxprobe"
    locks = "cmd:all()"

    def func(self) -> None:
        from world.investigation_followup import take_probe

        result = take_probe(self.caller, self.args.strip())
        if result is None:
            self.caller.msg("No authorized local follow-up diagnostic available.")
        else:
            self.caller.msg(
                "OX_ANOMALY_PROBE "
                + result["case_id"]
                + " "
                + result["indicator"]
                + " "
                + result["reading"]
            )


class CmdOxCaptainInspect(Command):
    """Qualified captain's first-hand bridge check, not a root-cause oracle."""

    key = "oxcaptaininspect"
    locks = "cmd:all()"

    def func(self) -> None:
        from world.captain import captain_qualified_observation

        sampled = captain_qualified_observation(self.caller, self.args.strip())
        if sampled is None:
            self.caller.msg("Captain must have diagnostics >=2 and be at the bridge.")
        else:
            self.caller.msg(
                "OX_CAPTAIN_INSPECTION " + sampled["ticket_id"] + " " + sampled["reading"]
            )
