"""Extend ordinary Evennia character commands with ship equipment verbs."""

from evennia.commands.default.cmdset_character import CharacterCmdSet as BaseCmdSet

from commands.capabilities import CmdOxCapabilities
from commands.inventory import CmdOxInventory

from commands.crew import (
    CmdOxInbox, CmdOxRadioAlarm, CmdOxRequestRelease,
    CmdOxApproveRelease, CmdOxResolve, CmdOxOfferWatch, CmdOxAcceptWatch,
    CmdOxHail, CmdOxAnswer, CmdOxWork, CmdOxWorkReceipt,
)

from commands.departments import (
    CmdRestow, CmdCertify, CmdReplaceCartridge, CmdRestartScrubber,
)

from commands.ship import (
    CmdCommission,
    CmdInspect,
    CmdOxIdentity,
    CmdOxAction,
    CmdOxReceipt,
    CmdIsolate,
    CmdRepair,
    CmdShipEngineer,
    CmdShipRole,
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
            CmdOxCapabilities,
            CmdOxInventory,
            CmdOxIdentity,
            CmdOxAction,
            CmdOxReceipt,
            CmdIsolate,
            CmdRepair,
            CmdCommission,
            CmdShipFault,
            CmdShipEngineer,
            CmdShipRole,
            CmdRestow,
            CmdCertify,
            CmdReplaceCartridge,
            CmdRestartScrubber,
            CmdOxInbox,
            CmdOxRadioAlarm,
            CmdOxRequestRelease,
            CmdOxApproveRelease,
            CmdOxResolve,
            CmdOxOfferWatch,
            CmdOxAcceptWatch,
            CmdOxHail,
            CmdOxAnswer,
            CmdOxWork,
            CmdOxWorkReceipt,
        ):
            self.add(command())
