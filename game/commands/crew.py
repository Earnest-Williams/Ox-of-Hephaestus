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
        from world.live_crew import inbox, wire_event
        try:
            since = int(self.args.strip() or "0")
            if since < 0:
                raise ValueError
        except ValueError:
            self.caller.msg("Usage: oxinbox <nonnegative-event-sequence>")
            return
        messages = inbox(self.caller, after=since)
        for message in messages:
            self.caller.msg(ox_event=([wire_event(message)], {}))
        self.caller.msg(ox_inbox_done=([{"count": len(messages)}], {}))


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
