"""In-world commands for Ox's first playable engineering compartment.

A model-controlled character will eventually use these same commands through
an ordinary Evennia client. No command trusts a claimed model outcome.
"""

from __future__ import annotations

from evennia.commands.command import Command

from typeclasses.ship import CoolingPump


class CmdInspect(Command):
    """Inspect local ship machinery or a nearby bridge console.

    Usage:
        inspect <equipment>
    """

    key = "inspect"
    aliases = ["readout"]
    locks = "cmd:all()"

    def func(self) -> None:
        """Read a fixture visible in the caller's current compartment."""
        if not self.args.strip():
            self.caller.msg("Inspect what? Try 'inspect pump' or 'inspect console'.")
            return
        target = self.caller.search(self.args.strip(), location=self.caller.location)
        if target is None:
            return
        if not callable(getattr(target, "readout", None)):
            self.caller.msg("That object has no shipboard readout.")
            return
        self.caller.msg(target.readout())


class _CmdPumpOperation(Command):
    """Find a local pump and request a validated game-side transition."""

    operation = ""

    def func(self) -> None:
        """Execute the game command against local authoritative equipment."""
        if not self.args.strip():
            self.caller.msg(f"{self.key.capitalize()} what? Try '{self.key} pump'.")
            return
        target = self.caller.search(self.args.strip(), location=self.caller.location)
        if target is None:
            return
        if not isinstance(target, CoolingPump):
            self.caller.msg("That is not a cooling pump.")
            return
        _success, message = getattr(target, self.operation)(self.caller)
        self.caller.msg(message)


class CmdIsolate(_CmdPumpOperation):
    """Isolate a faulted coolant pump.

    Usage:
        isolate pump
    """

    key = "isolate"
    operation = "isolate"
    locks = "cmd:all()"


class CmdRepair(_CmdPumpOperation):
    """Repair an isolated coolant pump.

    Usage:
        repair pump
    """

    key = "repair"
    operation = "repair"
    locks = "cmd:all()"


class CmdCommission(_CmdPumpOperation):
    """Return a repaired coolant pump to service.

    Usage:
        commission pump
    """

    key = "commission"
    operation = "commission"
    locks = "cmd:all()"


class CmdShipFault(Command):
    """Introduce a test cooling-pump failure (developers only).

    Usage:
        shipfault pump
    """

    key = "shipfault"
    locks = "cmd:perm(Developer)"

    def func(self) -> None:
        """Allow only authorised operators to inject a physical-world fault."""
        if not self.caller.check_permstring("Developer"):
            self.caller.msg("Only developers may inject test faults.")
            return
        if self.args.strip().lower() not in ("pump", "p-01", "p01"):
            self.caller.msg("Usage: shipfault pump")
            return
        target = self.caller.search("pump", location=self.caller.location)
        if not isinstance(target, CoolingPump):
            self.caller.msg("Cooling pump P-01 is not within reach.")
            return
        _success, message = target.inject_fault(self.caller)
        self.caller.msg(message)


class CmdShipEngineer(Command):
    """Assume a test engineering role for the current character (developer).

    Usage:
        shipengineer

    This changes game-side authorisation for testing; it is not an AI power.
    """

    key = "shipengineer"
    locks = "cmd:perm(Developer)"

    def func(self) -> None:
        """Give a developer-controlled body the prototype watch role."""
        if not self.caller.check_permstring("Developer"):
            self.caller.msg("Only developers may assume the prototype watch.")
            return
        self.caller.db.crew_role = "watch_engineer"
        self.caller.db.duty_title = "Engineering watch (developer test)"
        self.caller.msg("You are authorised for the prototype engineering watch.")


class CmdOxIdentity(Command):
    """Report the caller's own character dbref in response to a fresh nonce.

    This is a normal, non-privileged, character-scoped command. It exposes
    nothing beyond the identity of the character issuing the command.
    """

    key = "oxidentity"
    locks = "cmd:all()"

    def func(self) -> None:
        import re
        nonce = self.args.strip()
        if not re.fullmatch(r"[0-9a-f]{32}", nonce):
            self.caller.msg("Usage: oxidentity <32 hex digit challenge>")
            return
        self.caller.msg(f"OX_IDENTITY {nonce} {self.caller.dbref}")
