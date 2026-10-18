"""In-world commands for Ox's first playable engineering compartment.

A model-controlled character will eventually use these same commands through
an ordinary Evennia client. No command trusts a claimed model outcome.
"""

from __future__ import annotations

from evennia.commands.command import Command

from typeclasses.ship import CoolingPump
from typeclasses.departments import CargoCradle, AtmosphereScrubber


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
        if isinstance(target, CoolingPump):
            from world.live_crew import note_inspection
            note_inspection(self.caller, target)
        elif isinstance(target, (CargoCradle, AtmosphereScrubber)):
            target.note_inspection(self.caller)


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
            if not (self.operation == "isolate"
                    and isinstance(target, AtmosphereScrubber)):
                self.caller.msg("This operation is not supported by that equipment.")
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
    """Introduce a synthetic equipment fault (developers only).

    Usage:
        shipfault <pump|cargo|scrubber>
    """

    key = "shipfault"
    locks = "cmd:perm(Developer)"

    def func(self) -> None:
        """Allow only authorised operators to inject a physical-world fault."""
        if not self.caller.check_permstring("Developer"):
            self.caller.msg("Only developers may inject test faults.")
            return
        lookup = {
            "pump": "pump", "p-01": "pump", "p01": "pump",
            "cargo": "cargo", "c-01": "cargo",
            "scrubber": "scrubber", "a-01": "scrubber",
        }
        name = lookup.get(self.args.strip().lower())
        if name is None:
            self.caller.msg("Usage: shipfault <pump|cargo|scrubber>")
            return
        target = self.caller.search(name, location=self.caller.location)
        if not isinstance(target, (CoolingPump, CargoCradle, AtmosphereScrubber)):
            self.caller.msg("That equipment is not within reach.")
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


class CmdShipRole(Command):
    """Assume a specialist test duty in a disposable development world.

    Usage: shiprole <cargo|environment>

    Not an in-world promotion system. No production player can change
    their own specialist qualifications or engineering authority this way.
    """

    key = "shiprole"
    locks = "cmd:perm(Developer)"

    def func(self) -> None:
        if not self.caller.check_permstring("Developer"):
            self.caller.msg("Only developers may assume a test department role.")
            return
        assignments = {
            "cargo": ("cargo_officer", "Cargo test duty"),
            "environment": ("environment_tech", "Environmental test duty"),
        }
        role = assignments.get(self.args.strip().lower())
        if role is None:
            self.caller.msg("Usage: shiprole <cargo|environment>")
            return
        self.caller.db.crew_role, self.caller.db.duty_title = role
        self.caller.msg("Developer specialist duty set; physical access still required.")



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

class CmdOxAction(Command):
    """Identified game-authorised pump operation, same physics as normal verbs."""

    key = "oxaction"
    locks = "cmd:all()"

    def func(self) -> None:
        import re
        from world.bootstrap import find_fixture
        args = self.args.strip().split()
        if (len(args) != 2 or not re.fullmatch(r"[0-9a-f]{32}", args[0])
                or args[1] not in ("isolate", "repair", "commission")):
            self.caller.msg("Usage: oxaction <request-id> <isolate|repair|commission>")
            return
        pump = find_fixture("pump-p01")
        if not isinstance(pump, CoolingPump):
            self.caller.msg("P-01 unavailable.")
            return
        try:
            result = pump.durable_action(args[0], args[1], self.caller)
        except PermissionError:
            result = {"request_id": args[0], "actor_dbref": self.caller.dbref,
                      "operation": args[1], "status": "failed",
                      "reason": "request_collision", "source_event_id": None}
        self.caller.msg(ox_receipt=([result], {}))


class CmdOxReceipt(Command):
    """Reconcile one's own previously submitted game operation."""

    key = "oxreceipt"
    locks = "cmd:all()"

    def func(self) -> None:
        import re
        from world.bootstrap import find_fixture
        request_id = self.args.strip()
        if not re.fullmatch(r"[0-9a-f]{32}", request_id):
            self.caller.msg("Usage: oxreceipt <request-id>")
            return
        pump = find_fixture("pump-p01")
        if not isinstance(pump, CoolingPump):
            self.caller.msg("P-01 unavailable.")
            return
        self.caller.msg(ox_receipt=([pump.durable_receipt(request_id, self.caller)], {}))
