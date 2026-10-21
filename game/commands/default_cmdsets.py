"""Explicit Ox ship command allowlist; no inherited generic MUD bypasses."""

from evennia.commands.cmdset import CmdSet
from evennia.commands.default import general, help

from commands.social import CmdOxSocialStatus
from commands.terminal import CmdOxTerminal
from commands.capabilities import CmdOxCapabilities
from commands.inventory import CmdOxInventory
from commands.clock import CmdOxClock

from commands.crew import (
    CmdOxInbox, CmdOxEvent, CmdOxJournal, CmdOxRadioAlarm, CmdOxRequestRelease,
    CmdOxApproveRelease, CmdOxResolve, CmdOxOfferWatch, CmdOxAcceptWatch,
    CmdOxHail, CmdOxAnswer, CmdOxWork, CmdOxWorkReceipt, CmdOxSample, CmdOxProbe, CmdOxCaptainInspect,
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


class CharacterCmdSet(CmdSet):
    """Ordinary game characters use the same ship commands as future AI."""

    key = "DefaultCharacter"

    def at_cmdset_creation(self) -> None:
        """Install ship actions and safe local communication only.

        Stock get/drop/give/home, description editing and builder commands
        bypass Ox inventory, identity and world work policies.
        """
        for command in (
            general.CmdLook,
            general.CmdSay,
            general.CmdWhisper,
            general.CmdPose,
            help.CmdHelp,
            CmdInspect,
            CmdOxCapabilities,
            CmdOxTerminal,
            CmdOxInventory,
            CmdOxClock,
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
            CmdOxEvent,
            CmdOxJournal,
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
            CmdOxSocialStatus,
            CmdOxSample,
            CmdOxProbe,
            CmdOxCaptainInspect,
        ):
            self.add(command())
