"""Hatch requests from the lead mind; decisions only at the local console."""
import json
import re

from evennia.commands.command import Command

from world.ship_dr03_hatch_policy import HatchHandoverError


def _id(value):
    return re.fullmatch(r"[0-9a-f]{32}", value) is not None


class CmdOxHatchRequest(Command):
    key = "oxhatchreq"
    locks = "cmd:all()"

    def func(self):
        bits = self.args.strip().split()
        if len(bits) != 2 or not _id(bits[0]) or bits[1] not in {"open", "closed"}:
            self.caller.msg("Usage: oxhatchreq <32-hex-request-id> <open|closed>")
            return
        from world.ship_dr03_hatch_handover_world import request_dr03_hatch
        try:
            outcome = request_dr03_hatch(self.caller, *bits)
        except (HatchHandoverError, PermissionError, ValueError):
            self.caller.msg("Drum-3 hatch request unavailable or refused.")
            return
        self.caller.msg(ox_hatch_request=([json.dumps(outcome, sort_keys=True)], {}))


class CmdOxHatchRequestStatus(Command):
    key = "oxhatchstatus"
    locks = "cmd:all()"

    def func(self):
        token = self.args.strip()
        if not _id(token):
            self.caller.msg("Usage: oxhatchstatus <32-hex-original-request-id>")
            return
        from world.ship_dr03_hatch_handover_world import dr03_hatch_request_status
        try:
            outcome = dr03_hatch_request_status(self.caller, token)
        except (HatchHandoverError, PermissionError, ValueError):
            self.caller.msg("Drum-3 hatch request status unavailable.")
            return
        self.caller.msg(ox_hatch_status=([json.dumps(outcome, sort_keys=True)], {}))


class CmdOxHatchLocalDecision(Command):
    key = "oxhatchreply"
    locks = "cmd:all()"

    def func(self):
        bits = self.args.strip().split()
        if (len(bits) != 3 or not _id(bits[0]) or not _id(bits[1])
                or bits[2] not in {"accept", "decline"}):
            self.caller.msg(
                "Usage: oxhatchreply <32-hex-decision-id> "
                "<32-hex-original-request-id> <accept|decline>")
            return
        from world.ship_dr03_hatch_handover_world import decide_dr03_hatch
        try:
            outcome = decide_dr03_hatch(self.caller, *bits)
        except (HatchHandoverError, PermissionError, ValueError):
            self.caller.msg("Local hatch handover unavailable or refused.")
            return
        self.caller.msg(ox_hatch_local=([json.dumps(outcome, sort_keys=True)], {}))
