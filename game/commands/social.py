"""Authenticated party-only query of durable negotiated world obligations."""
from __future__ import annotations

from evennia.commands.command import Command


class CmdOxSocialStatus(Command):
    """Read an agreement addressed to this character: oxsocialstatus <id>."""

    key = 'oxsocialstatus'
    locks = 'cmd:all()'

    def func(self):
        from world.social_authority import agreement_summary

        agreement_id = self.args.strip()
        try:
            outcome = agreement_summary(self.caller, agreement_id)
        except (ValueError, PermissionError):
            self.caller.msg('Usage: oxsocialstatus <32-hex-agreement-id>')
            return
        # Evennia v1 first-level-only OOB payload. Unknown and unauthorized
        # agreements share the same response to prevent third-party inference.
        self.caller.msg(ox_social_status=([outcome], {}))