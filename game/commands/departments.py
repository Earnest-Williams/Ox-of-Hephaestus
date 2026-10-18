"""Ordinary location- and role-checked shipboard department commands."""
from __future__ import annotations

from evennia.commands.command import Command
from typeclasses.departments import CargoCradle, AtmosphereScrubber


class _DepartmentOperation(Command):
    """Invoke the real installed fixture, never a symbolic client-side effect."""

    equipment_type = None
    operation = ""

    def func(self) -> None:
        if not self.args.strip():
            self.caller.msg(f"Usage: {self.key} <equipment>")
            return
        target = self.caller.search(
            self.args.strip(), location=self.caller.location
        )
        if target is None:
            return
        if not isinstance(target, self.equipment_type):
            self.caller.msg("This action does not apply to that equipment.")
            return
        _success, result = getattr(target, self.operation)(self.caller)
        self.caller.msg(result)


class CmdRestow(_DepartmentOperation):
    """Restow locally inspected loose freight. Usage: restow cargo"""

    key = "restow"
    operation = "restow"
    equipment_type = CargoCradle
    locks = "cmd:all()"


class CmdCertify(_DepartmentOperation):
    """Certify freshly reinspected restowed cargo. Usage: certify cargo"""

    key = "certify"
    operation = "certify"
    equipment_type = CargoCradle
    locks = "cmd:all()"


class CmdReplaceCartridge(_DepartmentOperation):
    """Use a spare cartridge on isolated A-01. Usage: replace scrubber"""

    key = "replace"
    operation = "replace"
    equipment_type = AtmosphereScrubber
    locks = "cmd:all()"


class CmdRestartScrubber(_DepartmentOperation):
    """Restart freshly inspected serviced A-01. Usage: restart scrubber"""

    key = "restart"
    operation = "restart"
    equipment_type = AtmosphereScrubber
    locks = "cmd:all()"
