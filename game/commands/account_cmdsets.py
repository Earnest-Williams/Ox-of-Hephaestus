"""Narrow authenticated account commands for the Ox ship.

Never inherit stock MUD account commands that let ordinary users create
characters, remove characters, page others outside ship radio, browse global
channels, execute Python, or run server-admin operations. Evennia still owns
the actual login, session transport, puppet authentication and permissions.
"""
from evennia.commands.cmdset import CmdSet
from evennia.commands.default import account, help


class AccountCmdSet(CmdSet):
    """Ordinary account functions, not in-world character development."""

    key = "DefaultAccount"
    priority = -10

    def at_cmdset_creation(self) -> None:
        # Preserve only the commands required to authenticate/control a
        # provisioned ship character and manage ordinary account access.
        for command in (
            account.CmdOOCLook,
            account.CmdIC,
            account.CmdOOC,
            account.CmdOption,
            account.CmdQuit,
            account.CmdPassword,
            help.CmdHelp,
        ):
            self.add(command())
