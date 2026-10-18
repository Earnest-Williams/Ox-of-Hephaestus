"""Extend ordinary Evennia character commands with ship equipment verbs."""

from evennia.commands.default.cmdset_character import CharacterCmdSet as BaseCmdSet

from commands.ship import (
    CmdCommission,
    CmdInspect,
    CmdOxIdentity,
    CmdIsolate,
    CmdRepair,
    CmdShipEngineer,
    CmdShipFault,
)


class CharacterCmdSet(BaseCmdSet):
    """Ordinary game characters use the same ship commands as future AI."""

    key = "DefaultCharacter"

    def at_cmdset_creation(self) -> None:
        """Install equipment interactions alongside standard MUD commands."""
        super().at_cmdset_creation()
        for command in (
            CmdInspect,
            CmdOxIdentity,
            CmdIsolate,
            CmdRepair,
            CmdCommission,
            CmdShipFault,
            CmdShipEngineer,
        ):
            self.add(command())
