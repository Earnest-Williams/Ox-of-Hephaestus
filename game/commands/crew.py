"""Ordinary character commands for authenticated, world-owned crew cooperation."""
from __future__ import annotations

from evennia.commands.command import Command
from world import live_crew


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
        self.caller.msg(ox_inbox_done=([{
            "version": page["version"],
            "count": page["count"],
            "next_cursor": page["next_cursor"],
            "has_more": page["has_more"],
        }], {}))


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
        if (len(parts) not in (3, 5)
                or re.fullmatch(r"[0-9a-f]{32}", parts[0]) is None):
            self.caller.msg(usage)
            return
        request_id, operation, target = parts[:3]
        arguments = None
        if len(parts) == 5:
            arguments = {"hail_id": parts[3], "mode": parts[4]}
        try:
            result = execute_work(
                self.caller, request_id, operation, target,
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
        self.caller.msg(ox_receipt=([
            work_receipt(self.caller, request_id)
        ], {}))
